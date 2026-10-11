"""Drinking-water pipe sizing (DIN 1988-300), decision 0035.

A `norm` calculator, not yet reviewed. For each section (Teilstrecke) of the cold and hot
networks derived from the model (`geometry.py`):

    ΣV̇_R  the design flows of the fixtures beyond it (cold, or hot; a tank that heats drinking
           water counts on the cold side with the hot flows of its fixtures)
    V̇_S   = a · (ΣV̇_R)^b − c, at most ΣV̇_R and at least the largest single V̇_R
    size  the smallest of the pipe system whose velocity at V̇_S stays within v_max
    Δp    = R · l + Σζ · ρv²/2      (hydraulics.py; ζ: the bends of the rectilinear run, a tee
                                     where it leaves another section)

Each fixture must keep its minimum flow pressure:

    p_min,V − Δp_meter − Δp_geo − Σ Δp (− Δp_tank for hot water) ≥ p_min,Fl

Where a fixture falls short, the section with the largest loss on its way that can grow is made
one size larger, until each fixture has its pressure or no section can grow. V̇_R and p_min,Fl
by fixture, a, b, c by building use and v_max come from the office's tables; the supply
pressure and the apparatus losses from the model (the meter, the tank's type), the pipe sizes,
roughness and ζ from the pipe system's type.
"""

from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.heat.kinds import TankType
from uea.packs.hydraulics import Temp, full, geodetic
from uea.packs.net import Section
from uea.packs.pipes import Bore
from uea.packs.plumb.geometry import plumb_type
from uea.packs.plumb.kinds import FIXTURES, Meter, PipeType, San

VERSION = "0.1.0"
NORM = "DIN 1988-300:2012-05"

FIXTURE_FLOW = Spec(
    "fixture-flow",
    "Design flow and minimum flow pressure by fixture",
    "DIN 1988-300",
    (
        Col("fixture", "text", "fixture, as UEA names it", FIXTURES),
        Col("vr-cold", "num", "design flow V̇_R of cold water, l/s", sign="zero"),
        Col("vr-hot", "num", "design flow V̇_R of hot water, l/s", sign="zero"),
        Col("pmin", "num", "minimum flow pressure p_min,Fl, hPa", sign="zero"),
    ),
    ("fixture",),
    "One row for each fixture the project has.",
)
PEAK_FLOW = Spec(
    "peak-flow",
    "Peak flow constants by building use",
    "DIN 1988-300",
    (
        Col("building", "text", "building use, as building= of the calculator names it"),
        Col("a", "num", "constant a"),
        Col("b", "num", "constant b"),
        Col("c", "num", "constant c", sign="zero"),
    ),
    ("building",),
    "V̇_S = a · (ΣV̇_R)^b − c.",
)
WATER_FACTORS = Spec(
    "water-factors",
    "Limits of the drinking-water sizing",
    "DIN 1988-300",
    (
        Col("name", "text", "which value", ("vmax",)),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "vmax: the highest flow velocity in the pipes, m/s.",
)
PARAMS = (Param("building", str, "residential", "building use, a row of the table peak-flow"),)


@dataclass
class Sized:
    """A section with its flows and its size."""

    s: Section
    temp: Temp
    net: str
    sum_vr: float
    vs: float
    zeta: float
    sizes: tuple[Bore, ...]
    k: float
    i: int = 0
    v: float = 0.0
    r: float = 0.0
    dp: float = 0.0

    @property
    def bore(self) -> Bore:
        return self.sizes[self.i]

    def compute(self) -> None:
        f = full(self.vs, self.bore.di, self.k, self.temp)
        self.v, self.r = f.v, f.r
        self.dp = f.r * self.s.length + self.zeta * f.dyn


@dataclass
class Way:
    """A fixture's way from the meter, with what it loses."""

    fixture: str
    temp: Temp
    sections: list[Sized]
    pmin: float
    height: float
    tank: float = 0.0
    supply: float = 0.0
    meter: float = 0.0

    @property
    def pipes(self) -> float:
        return sum(x.dp for x in self.sections)

    @property
    def reserve(self) -> float:
        return self.supply - self.meter - self.height - self.tank - self.pipes - self.pmin


@dataclass
class Result:
    sized: list[Sized] = field(default_factory=list[Sized])
    ways: list[Way] = field(default_factory=list[Way])
    vmax: float = 0.0
    abc: tuple[float, float, float] = (0.0, 0.0, 0.0)
    meter: str = ""
    pipe: str = ""


def peak(sum_vr: float, largest: float, abc: tuple[float, float, float]) -> float:
    """V̇_S from ΣV̇_R, at most ΣV̇_R and at least the largest single flow."""
    a, b, c = abc
    return min(sum_vr, max(largest, a * sum_vr**b - c))


def calculate(d: Derived, env: Env) -> Result:
    p, m = d.plumb, d.model
    if p.cold is None:
        raise ValueError("there is no meter, or nothing takes water")
    meter = m[p.cold.root]
    assert isinstance(meter, Meter)
    if meter.p is None or meter.dp is None:
        raise ValueError(
            f"{meter.id} needs p= (the lowest supply pressure the water supplier states, bar)"
            " and dp= (the loss of the meter and apparatus, hPa)"
        )
    pipe = plumb_type(m, meter, PipeType, "pipe")
    if pipe is None:
        raise ValueError(f"{meter.id} has no pipe type, and none is marked default")
    fixtures = {k: m[k] for k in p.at if m[k].kind == "san"}
    flows = env.table(FIXTURE_FLOW)
    used = sorted({f.fixture for f in fixtures.values() if isinstance(f, San)})
    missing = [x for x in used if flows.find(fixture=x) is None]
    if missing:
        raise ValueError(f"the table fixture-flow has no row for {', '.join(missing)}: add it")
    building = env.param("building")
    row = env.table(PEAK_FLOW).find(building=building)
    if row is None:
        raise ValueError(f"the table peak-flow has no row for the building use {building}")
    abc = (float(row["a"]), float(row["b"]), float(row["c"]))
    vrow = env.table(WATER_FACTORS).find(name="vmax")
    if vrow is None:
        raise ValueError("the table water-factors has no row for vmax")
    res = Result(vmax=float(vrow["value"]), abc=abc, meter=meter.id, pipe=pipe.id)

    def vr(k: str, temp: Temp) -> float:
        if k in p.hot:  # a tank: the hot flows of its fixtures
            return sum(vr(x, "hot") for x, t in p.hot_from.items() if t == k)
        el = fixtures[k]
        assert isinstance(el, San)
        r = flows.find(fixture=el.fixture)
        assert r is not None
        if temp == "cold" and el.supply == "none":
            return 0.0
        return float(r["vr-cold" if temp == "cold" else "vr-hot"])

    by: dict[tuple[str, str], Sized] = {}
    for temp, net in [("cold", p.cold), *(("hot", n) for n in p.hot.values())]:
        t: Temp = "cold" if temp == "cold" else "hot"
        for s in net.sections:
            each = [vr(k, t) for k in s.serves]
            total = sum(each)
            zeta = s.bends * pipe.bend + (pipe.tee if s.a != net.root else 0.0)
            vs = peak(total, max(each, default=0.0), abc)
            x = Sized(s, t, net.root, total, vs, zeta, pipe.sizes.items, pipe.k)
            while x.i < len(x.sizes) - 1 and _speed(x) > res.vmax:
                x.i += 1
            x.compute()
            res.sized.append(x)
            by[(net.root, s.b)] = x
    z0 = d.plumb.at[meter.id].z
    for k, el in sorted(fixtures.items(), key=lambda kv: natural(kv[0])):
        assert isinstance(el, San)
        r = flows.find(fixture=el.fixture)
        assert r is not None
        z = p.at[k].z
        if el.supply != "none" and p.cold.has(k):
            ways = [by[(p.cold.root, s.b)] for s in p.cold.path(k)]
            res.ways.append(Way(k, "cold", ways, float(r["pmin"]), geodetic(z - z0)))
        tank = p.hot_from.get(k)
        if tank is not None and tank in p.hot:
            ttype = plumb_type(m, m[tank], TankType, "tank")
            if ttype is None or ttype.dp is None:
                raise ValueError(
                    f"the type of {tank} needs dp= (its loss on the drinking-water side, hPa)"
                )
            ways = [by[(p.cold.root, s.b)] for s in p.cold.path(tank)]
            ways += [by[(tank, s.b)] for s in p.hot[tank].path(k)]
            res.ways.append(Way(k, "hot", ways, float(r["pmin"]), geodetic(z - z0), ttype.dp))
    for w in res.ways:
        w.supply, w.meter = meter.p * 1000, meter.dp
    _enlarge(res)
    return res


def _speed(x: Sized) -> float:
    return full(x.vs, x.bore.di, x.k, x.temp).v


def _enlarge(res: Result) -> None:
    """Make the section with the largest loss on the worst way one size larger, until each
    fixture keeps its pressure or nothing can grow."""
    while True:
        short = [w for w in res.ways if w.reserve < 0]
        if not short:
            return
        worst = min(short, key=lambda w: (w.reserve, natural(w.fixture)))
        grow = [x for x in worst.sections if x.i < len(x.sizes) - 1]
        if not grow:
            return
        x = max(grow, key=lambda x: x.dp)
        x.i += 1
        x.compute()


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("water sizes the whole building: leave out the scope")
    res = calculate(d, env)
    meter = d.model[res.meter]
    assert isinstance(meter, Meter) and meter.p is not None
    a, b, c = res.abc
    lines = [
        f"{meter.id} {meter.p:g} bar, apparatus {meter.dp:g} hPa · pipe {res.pipe}"
        f" · V̇S = {a:g}·ΣV̇R^{b:g} − {c:g} ({env.param('building')}) · vmax {res.vmax:g} m/s"
    ]
    fast = False
    for x in res.sized:
        flag = ""
        if x.v > res.vmax + 1e-9:
            flag, fast = " (too fast: the largest size)", True
        lines.append(
            f"{x.temp} {x.s.name} {x.s.length:.1f} m {x.bore.name}: ΣVR {x.sum_vr:.2f} VS"
            f" {x.vs:.2f} l/s, v {x.v:.2f} m/s, R {x.r:.1f} hPa/m, ζ {x.zeta:g}, Δp {x.dp:.0f}"
            f" hPa{flag}"
        )
    for w in res.ways:
        el = d.model[w.fixture]
        assert isinstance(el, San)
        tank = f", tank {w.tank:.0f}" if w.temp == "hot" else ""
        lines.append(
            f"{w.fixture} {el.fixture} {w.temp}: reserve {w.reserve:.0f} hPa (pipes {w.pipes:.0f},"
            f" height {w.height:.0f}{tank}, pmin {w.pmin:.0f})"
            + (" short" if w.reserve < 0 else "")
        )
    ok = not fast and all(w.reserve >= 0 for w in res.ways)
    data = {
        "sections": [
            {
                "net": x.net,
                "temp": x.temp,
                "a": x.s.a,
                "b": x.s.b,
                "length": round(x.s.length, 3),
                "serves": x.s.serves,
                "sum_vr": round(x.sum_vr, 4),
                "vs": round(x.vs, 4),
                "size": x.bore.name,
                "di": round(x.bore.di, 3),
                "v": round(x.v, 3),
                "r": round(x.r, 3),
                "zeta": x.zeta,
                "dp": round(x.dp, 2),
            }
            for x in res.sized
        ],
        "fixtures": [
            {
                "fixture": w.fixture,
                "temp": w.temp,
                "reserve": round(w.reserve, 1),
                "pipes": round(w.pipes, 1),
                "height": round(w.height, 1),
                "tank": w.tank,
                "pmin": w.pmin,
            }
            for w in res.ways
        ],
    }
    return Output(
        lines=lines,
        report=report(d, res, env),
        data=data,
        inputs={"meter": meter.id, "p": meter.p, "dp": meter.dp, "pipe": res.pipe},
        ok=ok,
    )


TEMP_DE = {"cold": "PWC", "hot": "PWH"}


def report(d: Derived, res: Result, env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    meter = d.model[res.meter]
    assert isinstance(meter, Meter) and meter.p is not None and meter.dp is not None
    a, b, c = res.abc
    out = [
        f"# Trinkwasser-Rohrbemessung: {title}",
        "",
        f"Mindestversorgungsdruck {de(meter.p, 1)} bar am Hausanschluss {meter.id}, Druckverlust"
        f" Wasserzähler und Apparate {de(meter.dp, 0)} hPa. Rohrsystem {res.pipe}."
        f" Spitzendurchfluss V̇_S = {de(a, 3)} · (ΣV̇_R)^{de(b, 3)} − {de(c, 3)}"
        f" (Gebäudeart {env.param('building')}), v_max = {de(res.vmax, 1)} m/s.",
        "",
    ]
    for root in dict.fromkeys(x.net for x in res.sized):
        rows = [
            [
                x.s.name.replace(">", " → "),
                de(x.s.length, 1),
                de(x.sum_vr, 2),
                de(x.vs, 2),
                x.bore.name,
                de(x.v, 2),
                de(x.r, 1),
                de(x.zeta, 1),
                de(x.dp, 0),
            ]
            for x in res.sized
            if x.net == root
        ]
        temp = next(x.temp for x in res.sized if x.net == root)
        out += [
            f"## {TEMP_DE[temp]} ab {root}",
            "",
            md_table(
                [
                    "Teilstrecke",
                    "l m",
                    "ΣV̇_R l/s",
                    "V̇_S l/s",
                    "Rohr",
                    "v m/s",
                    "R hPa/m",
                    "Σζ",
                    "Δp hPa",
                ],
                rows,
                right=(1, 2, 3, 5, 6, 7, 8),
            ),
            "",
        ]
    rows = [
        [
            w.fixture,
            TEMP_DE[w.temp],
            de(w.supply, 0),
            de(w.meter, 0),
            de(w.height, 0),
            de(w.tank, 0) if w.temp == "hot" else "–",
            de(w.pipes, 0),
            de(w.pmin, 0),
            f"**{de(w.reserve, 0)}**" if w.reserve < 0 else de(w.reserve, 0),
        ]
        for w in res.ways
    ]
    out += [
        "## Fließwege",
        "",
        md_table(
            [
                "Entnahmestelle",
                "",
                "p_min,V",
                "Apparate",
                "Δp_geo",
                "Speicher",
                "Rohre",
                "p_min,Fl",
                "Reserve hPa",
            ],
            rows,
            right=(2, 3, 4, 5, 6, 7, 8),
        ),
        "",
        "## Verfahren",
        "",
        "- Teilstrecken aus dem Modell: je Netz der kürzeste Baum über die rechtwinkligen"
        " Abstände vom Hausanschluss (Kaltwasser) bzw. vom Trinkwassererwärmer (Warmwasser),"
        " über die Steigleitungen in die anderen Geschosse. Längen sind Untergrenzen.",
        "- ΣV̇_R der Entnahmestellen hinter der Teilstrecke (Tabelle `fixture-flow`); der"
        " Trinkwassererwärmer zählt kaltseitig mit den Warmwasser-Durchflüssen seiner"
        " Entnahmestellen. V̇_S = a · (ΣV̇_R)^b − c (Tabelle `peak-flow`), höchstens ΣV̇_R,"
        " mindestens der größte einzelne V̇_R.",
        "- Kleinste Nennweite des Rohrsystems mit v ≤ v_max (Tabelle `water-factors`)."
        " Rohrreibung nach Darcy-Weisbach mit λ nach Colebrook-White, Wasser 10 °C (PWC)"
        " bzw. 60 °C (PWH). Einzelwiderstände: ζ des Rohrsystems für jeden Bogen des"
        " rechtwinkligen Laufs und ein T-Stück am Abzweig.",
        "- Druckbilanz je Entnahmestelle: p_min,V − Δp Apparate − Δp_geo − Σ(R · l + Z)"
        " (− Δp Trinkwassererwärmer) ≥ p_min,Fl. Reicht sie nicht, wird auf dem ungünstigsten"
        " Fließweg die Teilstrecke mit dem größten Druckverlust eine Nennweite größer.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Ein v_max für alle Teilstrecken, ohne Unterscheidung nach Leitungsart, Fließdauer"
        " und Armaturen.",
        "- Einzelwiderstände pauschal aus Bögen und T-Stücken des rechtwinkligen Laufs, ohne"
        " Absperr- und Sonderarmaturen. Keine Dauerverbraucher, keine Zirkulation.",
        "- Mindestdurchfluss-Regel V̇_S zwischen dem größten einzelnen V̇_R und ΣV̇_R.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


WATER = Calculator(
    "water",
    "Trinkwasser-Rohrbemessung",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (FIXTURE_FLOW, PEAK_FLOW, WATER_FACTORS),
)

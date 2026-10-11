"""Duct sizing of the central units (decision 0038).

A `norm` calculator, not yet reviewed. The flows come from `airflow` (DIN 1946-6): each supply
and extract terminal its room's flow, the outdoor and exhaust air terminals what their unit
supplies and extracts. For each section of the derived ducts:

    q     the flows of the terminals beyond it
    size  the smallest diameter of the duct system whose velocity stays within v_max (`vmax=`)
    Δp    = R · l + Σζ · ρv²/2      Darcy-Weisbach and Colebrook-White, air at 20 °C

The supply fan moves the outdoor air in and the supply air out; the extract fan the extract air in
and the exhaust air out. Each side's worst way sets the pressure the unit must deliver, against
the external pressure of its type; every other terminal is throttled by the difference.
"""

from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.hydraulics import full
from uea.packs.net import Section
from uea.packs.vent import airflow
from uea.packs.vent.geometry import ahu_type, duct_type

VERSION = "0.1.0"
NORM = "Luftvolumenströme nach DIN 1946-6:2019-12; Druckverlust nach Darcy-Weisbach"
PARAMS = (*airflow.PARAMS, Param("vmax", float, None, "the highest air velocity in the ducts, m/s"))
SIDE = {"oda": "sup", "sup": "sup", "ext": "ext", "eha": "ext"}
ROLE_DE = {"oda": "Außenluft", "sup": "Zuluft", "ext": "Abluft", "eha": "Fortluft"}


@dataclass
class Duct:
    unit: str
    role: str
    s: Section
    q: float
    """m³/h."""
    d: float = 0.0
    v: float = 0.0
    r: float = 0.0
    """Pa/m."""
    zeta: float = 0.0
    dp: float = 0.0
    """Pa."""


@dataclass
class Way:
    terminal: str
    unit: str
    role: str
    dp: float
    throttle: float = 0.0


@dataclass
class Blower:
    unit: str
    side: str
    q: float
    need: float
    index: str
    has: float | None


@dataclass
class Result:
    ducts: list[Duct] = field(default_factory=list[Duct])
    ways: list[Way] = field(default_factory=list[Way])
    fans: list[Blower] = field(default_factory=list[Blower])
    duct: str = ""
    vmax: float = 0.0


def size(q: float, sizes: tuple[float, ...], k: float, vmax: float) -> tuple[float, float, float]:
    """The smallest diameter within vmax (else the largest), with v (m/s) and R (Pa/m)."""
    for di in sizes:
        f = full(q / 3.6, di, k, "air")
        if f.v <= vmax or di == sizes[-1]:
            return di, f.v, f.r * 100
    raise AssertionError("no sizes")


def calculate(d: Derived, env: Env) -> Result:
    v = d.vent
    vmax = float(env.param("vmax"))
    if vmax <= 0:
        raise ValueError("vmax must be more than 0")
    if not v.ducts:
        raise ValueError("there are no ducts: add an ahu and its air terminals to vent.uea")
    t = duct_type(d)
    if t is None:
        raise ValueError(
            "no duct type is marked default: add type <name> duct sizes=... k= bend= tee= default"
        )
    air = airflow.calculate(d, env)
    res = Result(duct=t.id, vmax=vmax)
    for (unit, role), net in sorted(
        v.ducts.items(), key=lambda kv: (natural(kv[0][0]), list(SIDE).index(kv[0][1]))
    ):
        by: dict[str, Duct] = {}
        for s in net.sections:
            q = sum(air.terminal.get(k, 0.0) for k in s.serves)
            di, vel, r = size(q, t.sizes.items, t.k, vmax)
            zeta = s.bends * t.bend + (t.tee if s.a != unit else 0.0)
            dyn = full(q / 3.6, di, t.k, "air").dyn * 100
            x = Duct(unit, role, s, q, di, vel, r, zeta, r * s.length + zeta * dyn)
            by[s.b] = x
            res.ducts.append(x)
        for k in sorted((k for k in net.nodes if k != unit), key=natural):
            res.ways.append(Way(k, unit, role, sum(by[s.b].dp for s in net.path(k))))
    for el in d.model.of_kind("ahu"):
        u = el.id
        mine = [w for w in res.ways if w.unit == u]
        if not mine:
            continue
        ty = ahu_type(d, el)
        for side in ("sup", "ext"):
            outer = "oda" if side == "sup" else "eha"
            outs = [w for w in mine if w.role == outer]
            ins = [w for w in mine if w.role == side]
            worst_out = max(outs, key=lambda w: w.dp, default=None)
            worst_in = max(ins, key=lambda w: (w.dp, natural(w.terminal)), default=None)
            for group, worst in ((outs, worst_out), (ins, worst_in)):
                for w in group:
                    w.throttle = (worst.dp if worst else 0.0) - w.dp
            need = (worst_out.dp if worst_out else 0.0) + (worst_in.dp if worst_in else 0.0)
            sup, ext, _ = air.units.get(u, (0.0, 0.0, None))
            q = sup if side == "sup" else ext
            index = worst_in.terminal if worst_in else (worst_out.terminal if worst_out else u)
            res.fans.append(Blower(u, side, q, need, index, ty.dp if ty is not None else None))
    return res


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("ducts sizes every central unit: leave out the scope")
    res = calculate(d, env)
    lines = [f"duct {res.duct} · vmax {res.vmax:g} m/s · air 20 °C"]
    fast = False
    for x in res.ducts:
        flag = ""
        if x.v > res.vmax + 1e-9:
            flag, fast = " (too fast: the largest size)", True
        lines.append(
            f"{x.role} {x.s.name} {x.s.length:.1f} m Ø{x.d:g}: {x.q:.0f} m³/h, v {x.v:.2f} m/s,"
            f" R {x.r:.2f} Pa/m, ζ {x.zeta:g}, Δp {x.dp:.1f} Pa{flag}"
        )
    for w in res.ways:
        if w.throttle >= 0.5:
            lines.append(f"{w.terminal} {w.role}: throttle {w.throttle:.1f} Pa")
    weak = False
    for f in res.fans:
        has = f" of {f.has:g}" if f.has is not None else ""
        flag = ""
        if f.has is not None and f.need > f.has + 1e-9:
            flag, weak = " (too little)", True
        lines.append(
            f"{f.unit} {'supply' if f.side == 'sup' else 'extract'}: {f.q:.0f} m³/h,"
            f" {f.need:.1f} Pa{has} (index {f.index}){flag}"
        )
    data = {
        "ducts": [
            {
                "unit": x.unit,
                "role": x.role,
                "a": x.s.a,
                "b": x.s.b,
                "length": round(x.s.length, 3),
                "q": round(x.q, 2),
                "d": x.d,
                "v": round(x.v, 3),
                "r": round(x.r, 4),
                "zeta": x.zeta,
                "dp": round(x.dp, 3),
            }
            for x in res.ducts
        ],
        "terminals": {
            w.terminal: {"dp": round(w.dp, 3), "throttle": round(w.throttle, 3)} for w in res.ways
        },
        "fans": [
            {
                "unit": f.unit,
                "side": f.side,
                "q": round(f.q, 2),
                "need": round(f.need, 3),
                "index": f.index,
                "has": f.has,
            }
            for f in res.fans
        ],
    }
    return Output(
        lines=lines,
        report=report(d, res),
        data=data,
        inputs={"duct": res.duct},
        ok=not (fast or weak),
    )


def report(d: Derived, res: Result) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    rows = [
        [
            ROLE_DE[x.role],
            x.s.name.replace(">", " → "),
            de(x.s.length, 1),
            de(x.q, 0),
            f"Ø {x.d:g}",
            de(x.v, 2),
            de(x.r, 2),
            de(x.zeta, 1),
            de(x.dp, 1),
        ]
        for x in res.ducts
    ]
    out = [
        f"# Luftleitungen: {title}",
        "",
        f"Kanalsystem {res.duct}, v_max = {de(res.vmax, 1)} m/s, Luft 20 °C. Volumenströme der"
        " Luftdurchlässe aus dem Lüftungskonzept (Rechenverfahren `airflow`).",
        "",
        "## Teilstrecken",
        "",
        md_table(
            [
                "Luftart",
                "Teilstrecke",
                "l m",
                "V̇ m³/h",
                "Kanal",
                "v m/s",
                "R Pa/m",
                "Σζ",
                "Δp Pa",
            ],
            rows,
            right=(2, 3, 5, 6, 7, 8),
        ),
        "",
        "## Luftdurchlässe",
        "",
        md_table(
            ["Durchlass", "Gerät", "Luftart", "Δp Weg Pa", "Drosseln Pa"],
            [
                [
                    w.terminal,
                    w.unit,
                    ROLE_DE[w.role],
                    de(w.dp, 1),
                    de(w.throttle, 1) if w.throttle >= 0.5 else "–",
                ]
                for w in res.ways
            ],
            right=(3, 4),
        ),
        "",
        "## Ventilatoren",
        "",
    ]
    for f in res.fans:
        side = "Zuluft (Außenluft + Zuluft)" if f.side == "sup" else "Abluft (Abluft + Fortluft)"
        has = (
            f", Gerät {de(f.has, 0)} Pa: "
            + ("reicht" if f.need <= f.has + 1e-9 else "**reicht nicht**")
            if f.has is not None
            else ", externe Pressung des Geräts nicht angegeben"
        )
        out.append(
            f"- **{f.unit} {side}:** {de(f.q, 0)} m³/h, erforderlich {de(f.need, 1)} Pa"
            f" (ungünstigster Durchlass {f.index}){has}."
        )
    out += [
        "",
        "## Verfahren",
        "",
        "- Luftleitungen aus dem Modell: je Gerät und Luftart der kürzeste Baum über die"
        " rechtwinkligen Abstände; Längen sind Untergrenzen.",
        "- Durchmesser: der kleinste des Kanalsystems mit v ≤ v_max. Druckverlust nach"
        " Darcy-Weisbach mit λ nach Colebrook-White; Einzelwiderstände ζ je Bogen und T-Stück.",
        "- Ventilator: ungünstigster Weg der Außen- bzw. Fortluft plus der Zu- bzw. Abluft.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Ohne Druckverlust der Luftdurchlässe, Schalldämpfer, Filter und Brandschutzklappen;"
        " die externe Pressung des Geräts ist gegen das Kanalnetz allein gestellt.",
        "- Nur runde Kanäle; keine Kanalführung entlang von Schächten und Installationszonen.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


DUCTS = Calculator(
    "ducts",
    "Luftleitungen",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    airflow.AIRFLOW.tables,
)

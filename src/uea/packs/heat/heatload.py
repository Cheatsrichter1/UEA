"""Heizlast room by room (DIN EN 12831-1 with DIN/TS 12831-1), decision 0033.

A `norm` calculator, not yet reviewed. For each heated room i:

    Φ_HL,i = Φ_T,i + Φ_V,i
    Φ_T,i  = Σ_k A_k · U_k,c · f_k · (θ_int,i − θ_e)
    U_k,c  = U_k + ΔU_TB          (against outside air, the ground and unheated rooms)
    f_k    = 1                                        outside air
           = f_g1 · (θ_int,i − θ_m,e) / (θ_int,i − θ_e) · G_w   the ground
           = (θ_int,i − θ_j) / (θ_int,i − θ_e)         a room at θ_j
    Φ_V,i  = V̇_i · ρc_p · (θ_int,i − θ_e),  V̇_i = max(V̇_inf,i, n_min · V_i)
    V̇_inf,i = 2 · V_i · n_50 · e_i · ε_i

The surfaces and their areas come from the envelope (`envelope.py`), U from DIN EN ISO 6946
(`thermal.py`). Every number of the standards comes from the office's tables or the settings:
θ_e and θ_m,e by postcode, θ_int and n_min by room use, e by exposed openings and shielding,
ε by height, f_g1, G_w and ρc_p; ΔU_TB and n_50 are the planner's.

Deviations, to be settled in the review (`docs/validation/heatload.md`): the ground with the
component's U instead of U_equiv; infiltration by the room formula above instead of the
building's air flow through q_env50; no reheat, no mechanical ventilation. The building's load
is the sum over the heated rooms without the flows between them, with no reduction of the
infiltration.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.packs.arch.kinds import Room, RoomUse
from uea.packs.heat import emitters
from uea.packs.heat.envelope import PART_DE, Surface, envelope, terrain
from uea.packs.heat.geometry import generator_kw
from uea.packs.heat.thermal import MATERIAL, SURFACE, Thermal
from uea.packs.project import Project

VERSION = "0.3.0"
NORM = "DIN EN 12831-1:2017-09 mit DIN/TS 12831-1:2020-04"
USES: tuple[str, ...] = RoomUse.__args__  # type: ignore[attr-defined]

OUTDOOR = Spec(
    "outdoor",
    "Design outdoor temperature by postcode",
    "DIN/TS 12831-1",
    (
        Col("postcode", "text", "postcode, as in postcode= of the project"),
        Col("te", "num", "design outdoor temperature θ_e, °C", sign="any"),
        Col("tme", "num", "annual mean outdoor temperature θ_m,e, °C", sign="any"),
    ),
    ("postcode",),
    "One row for each postcode the office plans in, or only the project's.",
)
ROOM_TEMP = Spec(
    "room-temp",
    "Internal temperature and minimum air change by room use",
    "DIN/TS 12831-1",
    (
        Col("use", "text", "room use, as UEA names it", USES),
        Col("heated", "text", "whether rooms of this use are heated", ("yes", "no")),
        Col(
            "ti",
            "num",
            "internal design temperature θ_int, or of the unheated space, °C",
            sign="any",
        ),
        Col("nmin", "num", "minimum air change rate n_min, 1/h", sign="zero"),
    ),
    ("use",),
    "One row for each use the rooms of the project have.",
)
INFILTRATION = Spec(
    "infiltration",
    "Shielding coefficient e",
    "DIN EN 12831-1, DIN/TS 12831-1",
    (
        Col(
            "openings", "text", "outside walls with windows or doors the room has", ("0", "1", "2+")
        ),
        Col("shielding", "text", "shielding of the building", ("none", "moderate", "heavy")),
        Col("e", "num", "shielding coefficient e", sign="zero"),
    ),
    ("openings", "shielding"),
)
HEIGHT = Spec(
    "height-factor",
    "Height correction factor ε",
    "DIN EN 12831-1, DIN/TS 12831-1",
    (
        Col("upto", "num", "height of the room's middle above the terrain up to which it holds, m"),
        Col("eps", "num", "height correction factor ε"),
    ),
    ("upto",),
)
FACTORS = Spec(
    "heatload-factors",
    "Factors of the Heizlast",
    "DIN EN 12831-1, DIN/TS 12831-1",
    (
        Col("name", "text", "which factor", ("fg1", "gw-deep", "gw-shallow", "rho-cp")),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "fg1: annual variation of the outdoor temperature for the ground; gw-deep, gw-shallow: G_w"
    " with the groundwater deeper or less deep than the standard's limit; rho-cp: heat capacity"
    " of air per volume, Wh/(m³·K).",
)

PARAMS = (
    Param("tb", float, None, "thermal bridge surcharge ΔU_TB, W/(m²K), on the outer surfaces"),
    Param("n50", float, None, "air change rate at 50 Pa the building is to meet, 1/h"),
    Param("shielding", str, None, "shielding of the building", ("none", "moderate", "heavy")),
    Param("groundwater", str, "deep", "groundwater under the building", ("deep", "shallow")),
    Param("te", float, None, "θ_e in °C instead of the table outdoor", optional=True),
    Param("tme", float, None, "θ_m,e in °C instead of the table outdoor", optional=True),
    Param(
        "flow",
        float,
        None,
        "the system's design flow temperature, °C; with spread=, emitters of DIN EN 442 or 1264"
        " values give their output at it",
        optional=True,
    ),
    Param("spread", float, None, "the system's design spread, K", optional=True),
    Param(
        "floor",
        float,
        None,
        "the highest mean floor surface temperature, °C; underfloor heating above it fails",
        optional=True,
    ),
    Param(
        "bathfloor",
        float,
        None,
        "the same in baths and WCs, °C; floor= if left out",
        optional=True,
    ),
    Param(
        "insulation",
        str,
        None,
        "with a ventilation system: the building's insulation for its flows (DIN 1946-6, as"
        " airflow); the supply air then comes in warmed by the units' heat recovery",
        ("high", "low"),
        optional=True,
    ),
)


@dataclass
class Line:
    """One surface of a room in the calculation."""

    s: Surface
    u: float
    uc: float
    f: float
    h: float
    phi: float
    tj: float | None = None


@dataclass
class RoomLoad:
    id: str
    name: str
    use: str
    ti: float
    area: float
    volume: float
    lines: list[Line] = field(default_factory=list[Line])
    openings: str = "0"
    e: float = 0.0
    eps: float = 1.0
    v_inf: float = 0.0
    v_min: float = 0.0
    phi_v: float = 0.0
    mech: bool = False
    """The ventilation system supplies or extracts its air (setting insulation=)."""
    v_su: float = 0.0
    """Supply air from the system, m³/h."""
    t_su: float = 0.0
    """Its temperature as it comes in, °C."""
    f_su: float = 0.0
    """(θ_int − θ_su) / (θ_int − θ_e)."""
    v_tr: float = 0.0
    """Air that comes over from other rooms (an extract room), m³/h."""

    @property
    def phi_t(self) -> float:
        return sum(x.phi for x in self.lines)

    @property
    def phi(self) -> float:
        return self.phi_t + self.phi_v

    @property
    def v(self) -> float:
        """The outdoor-air equivalent flow, m³/h."""
        if not self.mech:
            return max(self.v_inf, self.v_min)
        rest = max(self.v_min - self.v_inf - self.v_su - self.v_tr, 0.0)
        return self.v_inf + self.v_su * self.f_su + rest


@dataclass
class Climate:
    te: float
    tme: float
    where: str


class Tables:
    """The office's tables and the settings, read once."""

    def __init__(self, env: Env, d: Derived, uses: Iterable[str]) -> None:
        self.env = env
        self.tb: float = env.param("tb")
        self.n50: float = env.param("n50")
        if self.tb < 0:
            raise ValueError("tb must be 0 or more")
        if self.n50 <= 0:
            raise ValueError("n50 must be more than 0")
        self.climate = self._climate(d)
        temps = env.table(ROOM_TEMP)
        missing = sorted({u for u in uses if temps.find(use=u) is None})
        if missing:
            raise ValueError(
                f"the table room-temp has no row for the use {', '.join(missing)}: add it"
            )
        self.temps = temps
        self.inf = env.table(INFILTRATION)
        self.height = env.table(HEIGHT)
        factors = env.table(FACTORS)
        self.factor: dict[str, float] = {}
        wanted = {"fg1": "fg1", "gw": f"gw-{env.param('groundwater')}", "rho-cp": "rho-cp"}
        for key, name in wanted.items():
            row = factors.find(name=name)
            if row is None:
                raise ValueError(f"the table heatload-factors has no row for {name}")
            self.factor[key] = float(row["value"])

    def _climate(self, d: Derived) -> Climate:
        te, tme = self.env.param("te"), self.env.param("tme")
        if te is not None and tme is not None:
            return Climate(te, tme, "Vorgabe des Aufrufs")
        proj = next((p for p in d.model.of_kind("project") if isinstance(p, Project)), None)
        code = proj.postcode if proj else None
        if code is None:
            raise ValueError("the project has no postcode=; give te= and tme=")
        row = self.env.table(OUTDOOR).find(postcode=code)
        if row is None:
            raise ValueError(f"the table outdoor has no row for the postcode {code}")
        return Climate(
            te if te is not None else float(row["te"]),
            tme if tme is not None else float(row["tme"]),
            f"Postleitzahl {code}",
        )

    def ti(self, use: str) -> float:
        row = self.temps.find(use=use)
        assert row is not None
        return float(row["ti"])

    def heated(self, use: str) -> bool:
        row = self.temps.find(use=use)
        assert row is not None
        return row["heated"] == "yes"

    def nmin(self, use: str) -> float:
        row = self.temps.find(use=use)
        assert row is not None
        return float(row["nmin"])

    def e(self, openings: str) -> float:
        row = self.inf.find(openings=openings, shielding=self.env.param("shielding"))
        if row is None:
            raise ValueError(
                f"the table infiltration has no row for openings {openings},"
                f" shielding {self.env.param('shielding')}"
            )
        return float(row["e"])

    def eps(self, above: float) -> float:
        rows = sorted(self.height.rows, key=lambda r: float(r["upto"]))
        for row in rows:
            if above <= float(row["upto"]) + 1e-9:
                return float(row["eps"])
        raise ValueError(f"the table height-factor reaches {rows[-1]['upto']} m, not {above:.1f}")


def rooms_in(d: Derived, scope: str | None) -> list[str]:
    rooms = list(d.arch.rooms)
    if scope is None:
        return rooms
    if scope in d.arch.levels:
        return [k for k in rooms if d.arch.rooms[k].level == scope]
    if scope in d.arch.rooms:
        return [scope]
    raise ValueError(f"unknown scope {scope}: give a storey or a room")


def calculate(d: Derived, env: Env) -> tuple[list[RoomLoad], Tables, Thermal]:
    if not d.arch.rooms:
        raise ValueError("there are no rooms")
    uses = {k: _use(d, k) for k in d.arch.rooms}
    tab = Tables(env, d, uses.values())
    ev = envelope(d)
    th = Thermal(env, (x.material for ss in ev.rooms.values() for s in ss for x in s.layers))
    clim = tab.climate
    out: list[RoomLoad] = []
    errors: list[str] = []
    ground = terrain(d) or 0.0
    for rid, surfaces in ev.rooms.items():
        use = uses[rid]
        if not tab.heated(use):
            continue
        ti = tab.ti(use)
        dt = ti - clim.te
        if dt <= 0:
            raise ValueError(f"{rid}: θ_int {ti:g} °C is not above θ_e {clim.te:g} °C")
        rg = d.arch.rooms[rid]
        el = d.model[rid]
        rl = RoomLoad(rid, el.label or "", use, ti, rg.area_fin, rg.volume or 0.0)
        for s in surfaces:
            if s.layers:
                u = th.u(s.layers, s.flow, s.far).u
            elif s.u_given is not None:
                u = s.u_given
            else:
                errors.append(f"{s.el} ({PART_DE[s.part]}) has no U-value in its type {s.build}")
                continue
            tj: float | None = None
            unheated = False
            if s.beyond == "room":
                assert s.other is not None
                ouse = uses[s.other]
                tj, unheated = tab.ti(ouse), not tab.heated(ouse)
                f = (ti - tj) / dt
            elif s.beyond == "ground":
                f = tab.factor["fg1"] * (ti - clim.tme) / dt * tab.factor["gw"]
            else:
                f = 1.0
            uc = u + (tab.tb if s.beyond != "room" or unheated else 0.0)
            h = s.area * uc * f
            rl.lines.append(Line(s, u, uc, f, h, h * dt, tj))
        facing = {
            (round(s.facing[0], 3), round(s.facing[1], 3))
            for s in surfaces
            if s.part in ("window", "door") and s.beyond == "outside" and s.facing
        }
        rl.openings = "0" if not facing else "1" if len(facing) == 1 else "2+"
        lv = d.arch.levels[rg.level]
        hr = rg.height_range()
        mid = lv.z + ((hr[0] + hr[1]) / 4 if hr else 0.0) - ground
        rl.e, rl.eps = tab.e(rl.openings), tab.eps(max(mid, 0.0))
        rl.v_inf = 2 * rl.volume * tab.n50 * rl.e * rl.eps
        rl.v_min = tab.nmin(use) * rl.volume
        rl.phi_v = rl.v * tab.factor["rho-cp"] * dt
        out.append(rl)
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    if env.param("insulation") is not None:
        _mechanical(d, out, env, tab)
    return out, tab, th


def _mechanical(d: Derived, out: list[RoomLoad], env: Env, tab: "Tables") -> None:
    """The ventilation system in the rooms' Φ_V (DIN EN 12831-1, 6.3.3): supply air comes in at
    θ_su = θ_e + η · (θ_ex − θ_e), the air an extract room draws comes over from other rooms at
    their temperature, and outdoor air makes up what falls short of V̇_min. θ_ex is the extract
    rooms' θ_int, weighted by their flows; η the heat recovery of the unit's type."""
    # imported here: the ventilation pack builds on the heating pack's geometry
    from uea.packs.vent import airflow
    from uea.packs.vent.geometry import ahu_type, fan_flow, inlet_flow, vent_type
    from uea.packs.vent.kinds import Fan, FanType

    air = airflow.calculate(d, env)
    te = tab.climate.te
    ti = {r.id: r.ti for r in out}
    ext = [(r.got, ti[r.id]) for r in air.rooms if r.role == "extract" and r.id in ti]
    flow = sum(q for q, _ in ext)
    t_ex = sum(q * t for q, t in ext) / flow if flow > 0 else None
    by = {r.id: r for r in air.rooms}
    m, v = d.model, d.vent
    for rl in out:
        a = by.get(rl.id)
        if a is None or not a.by:
            continue
        rl.mech = True
        if a.role == "extract":
            rl.v_tr = a.got
        elif a.role == "supply":
            heat = 0.0
            for k in a.by:
                el = m[k]
                eta = 0.0
                if el.kind == "air":
                    q = air.terminal.get(k, 0.0)
                    unit = m.get(v.unit_of.get(k, ""))
                    t = ahu_type(d, unit) if unit is not None else None
                    eta = (t.hr or 0.0) if t is not None else 0.0
                elif el.kind == "fan" and isinstance(el, Fan):
                    q = (fan_flow(d, el) or 0.0) / (2 if el.mode == "alt" else 1)
                    ft = vent_type(d, el, FanType, "fan")
                    eta = (ft.hr or 0.0) if ft is not None else 0.0
                else:
                    q = inlet_flow(d, el) or 0.0
                back = t_ex if t_ex is not None else rl.ti
                heat += q * (te + eta * (back - te))
                rl.v_su += q
            rl.t_su = heat / rl.v_su if rl.v_su > 0 else te
            rl.f_su = max((rl.ti - rl.t_su) / (rl.ti - te), 0.0)
        rl.phi_v = rl.v * tab.factor["rho-cp"] * (rl.ti - te)


def _use(d: Derived, rid: str) -> str:
    el = d.model[rid]
    assert isinstance(el, Room)
    return el.use


def building(loads: list[RoomLoad]) -> tuple[float, float]:
    """Transmission and ventilation of the building: the flows between heated rooms cancel."""
    heated = {r.id for r in loads}
    t = sum(x.phi for r in loads for x in r.lines if x.s.other not in heated)
    return t, sum(r.phi_v for r in loads)


def outputs(d: Derived, r: RoomLoad, env: Env) -> dict[str, emitters.Out]:
    """The output of each emitter of a room at its circuit's temperatures (`emitters.py`)."""
    flow, spread = env.param("flow"), env.param("spread")
    return {k: emitters.output(d, k, r.ti, flow, spread) for k in d.heat.emitters.get(r.id, [])}


def cover(d: Derived, r: RoomLoad, env: Env) -> tuple[dict[str, float], float]:
    """The emitters of a room with their output, and how far they fall short of its load."""
    em = {k: o.w for k, o in outputs(d, r, env).items()}
    return em, max(r.phi - sum(em.values()), 0.0)


def too_warm(d: Derived, r: RoomLoad, env: Env) -> dict[str, tuple[float, float]]:
    """The underfloor heatings of a room whose floor is warmer than the limit: (θ_F,m, limit)."""
    limit = env.param("floor")
    if r.use in ("bath", "wc") and env.param("bathfloor") is not None:
        limit = env.param("bathfloor")
    if limit is None:
        return {}
    return {
        k: (o.floor, limit)
        for k, o in outputs(d, r, env).items()
        if o.floor is not None and o.floor > limit + 1e-9
    }


def run(d: Derived, scope: str | None, env: Env) -> Output:
    wanted = set(rooms_in(d, scope))
    loads, tab, _ = calculate(d, env)
    shown = [r for r in loads if r.id in wanted]
    clim = tab.climate
    # once the heating has emitters, each room is checked against them (decision 0034)
    covering = any(d.heat.emitters.values())
    lines = [
        f"θe {clim.te:g} °C, θme {clim.tme:g} °C ({clim.where.replace('Postleitzahl', 'postcode')})"
        f" · {len(shown)} heated rooms"
    ]
    short = False
    rooms: dict[str, dict[str, object]] = {}
    for r in shown:
        name = f" {r.name}" if r.name else ""
        line = f"{r.id}{name} {r.ti:g} °C: {r.phi:.0f} W (T {r.phi_t:.0f}, V {r.phi_v:.0f})"
        rooms[r.id] = _data(r)
        if covering:
            em, gap = cover(d, r, env)
            got = ", ".join(f"{k} {w:.0f} W" for k, w in em.items()) or "no emitter"
            line += f" · {got}" + (f", short {gap:.0f} W" if gap > 0.5 else "")
            warm = too_warm(d, r, env)
            for k, (tf, lim) in warm.items():
                line += f", {k} floor {tf:.1f} °C > {lim:g}"
            short = short or gap > 0.5 or bool(warm)
            rooms[r.id]["emitters"] = {k: round(w, 1) for k, w in em.items()}
            rooms[r.id]["short"] = round(gap, 1)
            floors = {k: round(o.floor, 2) for k, o in outputs(d, r, env).items() if o.floor}
            if floors:
                rooms[r.id]["floor"] = floors
        lines.append(line)
    data: dict[str, object] = {"te": clim.te, "tme": clim.tme, "rooms": rooms}
    if scope is None:
        t, v = building(loads)
        area = sum(r.area for r in loads)
        line = (
            f"building: {(t + v) / 1000:.2f} kW (T {t / 1000:.2f}, V {v / 1000:.2f}),"
            f" {(t + v) / area:.0f} W/m² over {area:.1f} m²"
        )
        gens = generator_kw(d)
        if gens:
            kw = sum(gens.values())
            line += f" · {', '.join(f'{k} {v:g} kW' for k, v in gens.items())}"
            if kw * 1000 < t + v - 0.5:
                line += f", short {(t + v) / 1000 - kw:.2f} kW"
                short = True
        lines.append(line)
        data["building"] = {
            "phi_t": round(t, 1),
            "phi_v": round(v, 1),
            "area": round(area, 3),
            "generators": gens,
        }
    return Output(
        lines=lines,
        report=report(d, shown, loads, tab, scope, env),
        data=data,
        inputs={"rooms": [r.id for r in shown], "climate": clim.where},
        ok=not short,
    )


def _data(r: RoomLoad) -> dict[str, object]:
    return {
        "use": r.use,
        "ti": r.ti,
        "phi": round(r.phi, 1),
        "phi_t": round(r.phi_t, 1),
        "phi_v": round(r.phi_v, 1),
        "volume": round(r.volume, 3),
        "v_inf": round(r.v_inf, 4),
        "v_min": round(r.v_min, 4),
        "v_su": round(r.v_su, 4),
        "t_su": round(r.t_su, 3),
        "v_tr": round(r.v_tr, 4),
        "e": r.e,
        "eps": r.eps,
        "surfaces": [
            {
                "part": x.s.part,
                "el": x.s.el,
                "build": x.s.build,
                "beyond": x.s.other or x.s.beyond,
                "area": round(x.s.area, 4),
                "u": round(x.u, 5),
                "uc": round(x.uc, 5),
                "f": round(x.f, 5),
                "phi": round(x.phi, 2),
            }
            for x in r.lines
        ],
    }


BEYOND_DE = {"outside": "außen", "ground": "Erdreich", "none": "außen (kein Raum)"}


def report(
    d: Derived,
    shown: list[RoomLoad],
    loads: list[RoomLoad],
    tab: Tables,
    scope: str | None,
    env: Env,
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    clim = tab.climate
    covering = any(d.heat.emitters.values())
    head = ["Raum", "", "θ_int °C", "Fläche m²", "Φ_T W", "Φ_V W", "Φ_HL W", "W/m²"]
    if covering:
        head += ["Heizflächen W", "fehlt W"]
    body: list[list[str]] = []
    for r in shown:
        row = [
            r.id,
            r.name,
            de(r.ti, 0),
            de(r.area),
            de(r.phi_t, 0),
            de(r.phi_v, 0),
            de(r.phi, 0),
            de(r.phi / r.area, 0) if r.area else "–",
        ]
        if covering:
            em, gap = cover(d, r, env)
            row += [de(sum(em.values()), 0), f"**{de(gap, 0)}**" if gap > 0.5 else "–"]
        body.append(row)
    out = [
        f"# Heizlast: {title}",
        "",
        f"θ_e = {de(clim.te, 1)} °C, θ_m,e = {de(clim.tme, 1)} °C ({clim.where});"
        f" ΔU_WB = {de(tab.tb, 3)} W/(m²K); n_50 = {de(tab.n50, 1)} 1/h;"
        f" Abschirmung {SHIELD_DE[tab.env.param('shielding')]};"
        f" Grundwasser {'tief' if tab.env.param('groundwater') == 'deep' else 'hoch'}.",
        "",
        md_table(head, body, right=tuple(range(2, len(head)))),
        "",
    ]
    if scope is None:
        t, v = building(loads)
        out += [
            f"**Gebäude:** Φ_T = {de(t, 0)} W, Φ_V = {de(v, 0)} W, Φ_HL = **{de(t + v, 0)} W**"
            " (Summe der Räume ohne die Wärmeströme zwischen beheizten Räumen).",
            "",
        ]
        gens = generator_kw(d)
        if gens:
            kw = sum(gens.values())
            verdict = "deckt" if kw * 1000 >= t + v - 0.5 else "**deckt nicht**"
            names = ", ".join(f"{k} {de(x, 1)} kW" for k, x in gens.items())
            out += [
                f"Wärmeerzeuger: {names} (Herstellerangabe im Typ) {verdict} die Gebäudeheizlast.",
                "",
            ]
    for r in shown:
        body = [
            [
                PART_DE[x.s.part],
                x.s.el,
                x.s.build,
                x.s.other or BEYOND_DE[x.s.beyond],
                de(x.s.area),
                de(x.u, 3),
                de(x.uc, 3),
                de(x.f, 3),
                de(x.phi, 0),
            ]
            for x in r.lines
            if abs(x.f) > 1e-9
        ]
        out += [
            f"## {r.id} {r.name}",
            "",
            md_table(
                ["Bauteil", "", "Aufbau", "angrenzend", "A m²", "U", "U_c", "f", "Φ W"],
                body,
                right=(4, 5, 6, 7, 8),
            ),
            "",
            f"Lüftung: V = {de(r.volume)} m³, Fassaden mit Öffnungen {r.openings},"
            f" e = {de(r.e, 3)}, ε = {de(r.eps)}: V̇_inf = {de(r.v_inf)} m³/h,"
            f" V̇_min = {de(r.v_min)} m³/h"
            + (
                f", Zuluft der Anlage V̇_su = {de(r.v_su)} m³/h mit θ_su = {de(r.t_su, 1)} °C"
                f" (f_V,su = {de(r.f_su, 3)})"
                if r.v_su
                else ""
            )
            + (f", überströmende Luft V̇_tr = {de(r.v_tr)} m³/h" if r.v_tr else "")
            + f", Φ_V = {de(r.phi_v, 0)} W.",
            "",
        ]
    out += [
        "## Verfahren",
        "",
        "- Raumweise Heizlast Φ_HL = Φ_T + Φ_V. Φ_T = Σ A · U_c · f · (θ_int − θ_e) mit"
        " U_c = U + ΔU_WB gegen Außenluft, Erdreich und unbeheizte Räume; f = 1 gegen Außenluft,"
        " f = f_g1 · (θ_int − θ_m,e) / (θ_int − θ_e) · G_w gegen Erdreich,"
        " f = (θ_int − θ_j) / (θ_int − θ_e) gegen einen Raum mit θ_j.",
        "- Φ_V = V̇ · ρc_p · (θ_int − θ_e), V̇ = max(V̇_inf, n_min · V),"
        " V̇_inf = 2 · V · n_50 · e · ε. Mit Lüftungsanlage (Einstellung insulation=):"
        " V̇ = V̇_inf + V̇_su · f_V,su + max(0, V̇_min − V̇_inf − V̇_su − V̇_tr), Zuluft mit"
        " θ_su = θ_e + η · (θ_ex − θ_e) nach der Wärmerückgewinnung des Geräts, θ_ex die"
        " Raumtemperatur der Ablufträume nach ihren Volumenströmen; die Volumenströme nach"
        " DIN 1946-6 (Rechenverfahren `airflow`).",
        "- U nach DIN EN ISO 6946 aus den Schichten (Tabellen `material`, `surface`); Fenster und"
        " Türen mit dem U-Wert ihres Typs. Maße: Längen entlang der Rohbaukontur des Raums, Höhen"
        " von OKFF zu OKFF des Geschosses darüber, Böden und Decken mit der Fläche der"
        " Rohbaukontur, Dächer mit ihrer geneigten Fläche.",
        "- θ_e und θ_m,e aus der Tabelle `outdoor`, θ_int und n_min aus `room-temp`, e aus"
        " `infiltration`, ε aus `height-factor`, f_g1, G_w und ρc_p aus `heatload-factors`.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Erdreich mit dem U-Wert des Bauteils statt U_equiv (liegt auf der sicheren Seite).",
        "- Infiltration raumweise mit V̇_inf = 2 · V · n_50 · e · ε, nicht über q_env50 und den"
        " Luftvolumenstrom des Gebäudes; Gebäudeheizlast ohne Abminderung der Infiltration.",
        "- Keine Wiederaufheizleistung, keine Nachbargebäude. Mit Lüftungsanlage bleibt die"
        " Infiltration die freie (ohne Ungleichgewicht der Anlage), überströmende Luft hat die"
        " Temperatur des Raums, in den sie strömt.",
        "- Heizflächen: Leistung nach Herstellerangabe im Typ (Fußbodenheizung q mal Fläche,"
        " Heizkörper w) bei den Auslegungstemperaturen des Systems, oder aus den Prüfwerten des"
        " Herstellers bei den Temperaturen des Heizkreises: Heizkörper Φ = Φ_n · (Δθ/Δθ_n)^n"
        " nach DIN EN 442-2, Fußbodenheizung q = K_H · Δθ_H nach DIN EN 1264-2, jeweils mit der"
        " logarithmischen Übertemperatur; die mittlere Oberflächentemperatur des Fußbodens aus"
        " der Basiskennlinie. Randzonen und die Wärmeabgabe nach unten sind nicht abgebildet.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


SHIELD_DE = {"none": "keine", "moderate": "mittel", "heavy": "gut"}

HEATLOAD = Calculator(
    "heatload",
    "Heizlast raumweise",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (MATERIAL, SURFACE, OUTDOOR, ROOM_TEMP, INFILTRATION, HEIGHT, FACTORS),
)

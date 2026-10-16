"""Air flows of the dwelling and its rooms (DIN 1946-6), decision 0038.

A `norm` calculator. The dwelling (Nutzungseinheit) is every room whose use the
office's table `vent-room` does not mark `none`; A_NE its finished floor area, V_NE its volume.

    q_v,ges   = f · (a · A_NE² + b · A_NE + c)      for each level: FL (by insulation), RL, NL, IL
    q_v,inf   = komp · V_NE · n_50 · (lage · Δp / 50)^n
    measure   needed if q_v,inf < q_v,ges,FL       (lüftungstechnische Maßnahme)
    q_design  = max(q_v,ges,NL, Σ q_extract,R)
    extract   each extract room its q_extract,R, raised in proportion to reach q_design
    supply    each supply room q_design · f_R / Σ f_R

Against the system in `vent.uea`: a room with a terminal of its central unit gets its flow (the
terminals are designed for it); a decentral unit gives its room its type's flow, half each way
for a push-pull unit (it alternates), all of it for an exhaust fan or a unit that does both.
A room short of its flow fails the result, as does a central unit smaller than what its rooms
need, or a dwelling that needs a measure and has no system. a, b, c, f, the infiltration factors
and the flows by room use come from the office's tables; n_50 and the insulation are the
planner's.
"""

from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec, Table
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.arch.kinds import Room, RoomUse
from uea.packs.vent.geometry import ahu_type, fan_flow, inlet_flow
from uea.packs.vent.kinds import Fan

VERSION = "0.2.0"
NORM = "DIN 1946-6:2019-12"
USES: tuple[str, ...] = RoomUse.__args__  # type: ignore[attr-defined]
LEVELS = ("fl", "rl", "nl", "il")
LEVEL_DE = {"fl": "Feuchteschutz", "rl": "reduziert", "nl": "Nennlüftung", "il": "intensiv"}

VENT_TOTAL = Spec(
    "vent-total",
    "Total air flow of the dwelling by ventilation level",
    "DIN 1946-6",
    (
        Col(
            "level",
            "text",
            "fl-high, fl-low (by insulation), rl, nl or il",
            ("fl-high", "fl-low", "rl", "nl", "il"),
        ),
        Col("a", "num", "a, m³/h per m⁴", sign="any"),
        Col("b", "num", "b, m³/h per m²", sign="any"),
        Col("c", "num", "c, m³/h", sign="any"),
        Col("f", "num", "factor f"),
    ),
    ("level",),
    "q_v,ges = f · (a · A_NE² + b · A_NE + c), m³/h, with A_NE in m².",
)
VENT_ROOM = Spec(
    "vent-room",
    "Air flows by room use",
    "DIN 1946-6",
    (
        Col("use", "text", "room use, as UEA names it", USES),
        Col(
            "role",
            "text",
            "supply, extract, overflow, or none (not in the dwelling)",
            ("supply", "extract", "overflow", "none"),
        ),
        Col(
            "extract",
            "num",
            "extract flow of an extract room at the nominal level, m³/h",
            sign="zero",
        ),
        Col("fr", "num", "factor of a supply room for its share of the supply air", sign="zero"),
    ),
    ("use",),
    "One row for each use the rooms of the project have.",
)
VENT_INF = Spec(
    "vent-infiltration",
    "Infiltration of the dwelling",
    "DIN 1946-6",
    (
        Col("name", "text", "which factor", ("komp", "lage", "dp", "n")),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "q_v,inf = komp · V_NE · n_50 · (lage · dp / 50)^n, m³/h; dp in Pa.",
)
VENT_OVERFLOW = Spec(
    "vent-overflow",
    "Free area of the overflow openings by air flow",
    "DIN 1946-6",
    (
        Col("upto", "num", "air flow through the room's doors up to, m³/h"),
        Col("area", "num", "free area the overflow openings need, cm²"),
    ),
    ("upto",),
    "Needed once vent.uea has overflow openings (over).",
)
PARAMS = (
    Param("n50", float, None, "air change rate at 50 Pa the building is to meet, 1/h"),
    Param("insulation", str, None, "thermal insulation of the building", ("high", "low")),
)


@dataclass
class RoomAir:
    id: str
    name: str
    use: str
    role: str
    area: float
    volume: float
    need: float = 0.0
    """Its flow at the nominal level, m³/h: supply or extract by its role."""
    got: float = 0.0
    by: list[str] = field(default_factory=list[str])

    @property
    def short(self) -> float:
        return max(self.need - self.got, 0.0)


@dataclass
class Result:
    area: float
    volume: float
    q: dict[str, float]
    inf: float
    design: float
    rooms: list[RoomAir]
    measure: bool
    terminal: dict[str, float] = field(default_factory=dict[str, float])
    """The design flow of each air terminal of a central unit, m³/h; outdoor and exhaust air
    terminals share what their unit supplies and extracts."""
    units: dict[str, tuple[float, float, float | None]] = field(
        default_factory=dict[str, tuple[float, float, float | None]]
    )
    """Each central unit: supply, extract, and the largest flow of its type."""
    fans: float = 0.0
    """What the decentral units supply, m³/h."""
    overflow: dict[str, tuple[float, float, list[str]]] = field(
        default_factory=dict[str, tuple[float, float, list[str]]]
    )
    """Each supply and extract room, once vent.uea has overflow openings: the area it needs and
    the area its doors have, cm², and the openings."""

    @property
    def system(self) -> bool:
        return bool(self.units) or self.fans > 0 or any(r.by for r in self.rooms)


def calculate(d: Derived, env: Env) -> Result:
    m = d.model
    n50 = float(env.param("n50"))
    if n50 <= 0:
        raise ValueError("n50 must be more than 0")
    rooms_t = env.table(VENT_ROOM)
    uses = {k: _use(d, k) for k in d.arch.rooms}
    missing = sorted({u for u in uses.values() if rooms_t.find(use=u) is None})
    if missing:
        raise ValueError(f"the table vent-room has no row for the use {', '.join(missing)}: add it")
    rooms: list[RoomAir] = []
    for k in sorted(d.arch.rooms, key=natural):
        row = rooms_t.find(use=uses[k])
        assert row is not None
        if row["role"] == "none":
            continue
        rg = d.arch.rooms[k]
        rooms.append(
            RoomAir(k, m[k].label or "", uses[k], str(row["role"]), rg.area_fin, rg.volume or 0.0)
        )
    if not rooms:
        raise ValueError("no room belongs to the dwelling (vent-room marks every use none)")
    area = sum(r.area for r in rooms)
    volume = sum(r.volume for r in rooms)
    total = env.table(VENT_TOTAL)
    q: dict[str, float] = {}
    for lv in LEVELS:
        key = f"fl-{env.param('insulation')}" if lv == "fl" else lv
        row = total.find(level=key)
        if row is None:
            raise ValueError(f"the table vent-total has no row for {key}")
        a, b, c, f = (float(row[x]) for x in ("a", "b", "c", "f"))
        q[lv] = f * (a * area * area + b * area + c)
    fac: dict[str, float] = {}
    inf_t = env.table(VENT_INF)
    for name in ("komp", "lage", "dp", "n"):
        row = inf_t.find(name=name)
        if row is None:
            raise ValueError(f"the table vent-infiltration has no row for {name}")
        fac[name] = float(row["value"])
    inf = fac["komp"] * volume * n50 * (fac["lage"] * fac["dp"] / 50) ** fac["n"]
    extract = {r.id: float(_row(rooms_t, r.use)["extract"]) for r in rooms if r.role == "extract"}
    design = max(q["nl"], sum(extract.values()))
    scale = design / sum(extract.values()) if sum(extract.values()) > 0 else 0.0
    fr = {r.id: float(_row(rooms_t, r.use)["fr"]) for r in rooms if r.role == "supply"}
    for r in rooms:
        if r.role == "extract":
            r.need = extract[r.id] * scale
        elif r.role == "supply" and sum(fr.values()) > 0:
            r.need = design * fr[r.id] / sum(fr.values())
    res = Result(area, volume, q, inf, design, rooms, inf < q["fl"])
    _against(d, res)
    if d.vent.overflow:
        _overflow(d, res, env.table(VENT_OVERFLOW))
    return res


def _overflow(d: Derived, res: Result, table: Table) -> None:
    """The overflow openings of each supply and extract room against the area its flow needs:
    the air a supply room gets leaves through its doors, the air an extract room loses comes in
    through them."""
    rows = sorted(table.rows, key=lambda r: float(r["upto"]))
    v = d.vent
    for r in res.rooms:
        if r.role not in ("supply", "extract") or r.need <= 0:
            continue
        hit = next((x for x in rows if r.need <= float(x["upto"]) + 1e-9), None)
        need = float(hit["area"]) if hit is not None else float("inf")
        mine = sorted((k for k, sides in v.over_rooms.items() if r.id in sides), key=natural)
        res.overflow[r.id] = (need, sum(v.overflow[k] for k in mine), mine)


def _against(d: Derived, res: Result) -> None:
    """What the system in vent.uea gives each room."""
    m, v = d.model, d.vent
    for r in res.rooms:
        role = {"supply": "sup", "extract": "ext"}.get(r.role)
        if role is None:
            continue
        inlets = [k for k in v.terminals.get(r.id, {}).get(role, []) if m[k].kind == "inlet"]
        for k in inlets:
            r.got += inlet_flow(d, m[k]) or 0.0
            r.by.append(k)
        fans = [k for k in v.terminals.get(r.id, {}).get(role, []) if m[k].kind == "fan"]
        for k in fans:
            el = m[k]
            assert isinstance(el, Fan)
            flow = fan_flow(d, el) or 0.0
            r.got += flow / 2 if el.mode == "alt" else flow
            r.by.append(k)
        terms = [k for k in v.terminals.get(r.id, {}).get(role, []) if m[k].kind == "air"]
        if terms:
            rest = max(r.need - r.got, 0.0)
            for k in terms:
                res.terminal[k] = rest / len(terms)
            r.got += rest
            r.by += terms
    for el in m.of_kind("fan"):
        assert isinstance(el, Fan)
        if el.id in v.at and el.mode != "ext":
            flow = fan_flow(d, el) or 0.0
            res.fans += flow / 2 if el.mode == "alt" else flow
    for el in m.of_kind("ahu"):
        if el.id not in v.at:
            continue
        mine = [k for k, u in v.unit_of.items() if u == el.id]
        sup = sum(res.terminal.get(k, 0.0) for k in mine if getattr(m[k], "role") == "sup")  # noqa: B009
        ext = sum(res.terminal.get(k, 0.0) for k in mine if getattr(m[k], "role") == "ext")  # noqa: B009
        for k in mine:
            role = getattr(m[k], "role")  # noqa: B009
            same = [x for x in mine if getattr(m[x], "role") == role]  # noqa: B009
            if role == "oda":
                res.terminal[k] = sup / len(same)
            elif role == "eha":
                res.terminal[k] = ext / len(same)
        t = ahu_type(d, el)
        res.units[el.id] = (sup, ext, t.flow if t is not None else None)


def _row(table: Table, use: str) -> dict[str, str | float]:
    row = table.find(use=use)
    assert row is not None
    return row


def _use(d: Derived, rid: str) -> str:
    el = d.model[rid]
    assert isinstance(el, Room)
    return el.use


def verdict(res: Result) -> tuple[bool, list[str]]:
    """Whether the system gives what is needed, and what falls short."""
    short: list[str] = []
    if res.measure and not res.system:
        short.append("the dwelling needs a ventilation measure, and vent.uea has no system")
    if res.system:
        short += [f"{r.id} short {r.short:.0f} m³/h" for r in res.rooms if r.short > 0.5]
        for u, (sup, ext, flow) in res.units.items():
            if flow is not None and max(sup, ext) > flow + 0.5:
                short.append(f"{u} {max(sup, ext):.0f} m³/h over its {flow:g}")
    for k, (need, has, _) in res.overflow.items():
        if has < need - 1e-6:
            what = f"{need:.0f} cm²" if need != float("inf") else "more than the table's last row"
            short.append(f"{k} overflow {has:.0f} of {what}")
    return not short, short


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("airflow takes the whole dwelling: leave out the scope")
    res = calculate(d, env)
    ok, short = verdict(res)
    lines = [
        f"A_NE {res.area:.1f} m², V_NE {res.volume:.1f} m³ · "
        + ", ".join(f"{lv.upper()} {res.q[lv]:.0f}" for lv in LEVELS)
        + " m³/h",
        f"infiltration {res.inf:.0f} m³/h "
        + ("< FL: a ventilation measure is needed" if res.measure else "≥ FL: no measure needed"),
        f"design {res.design:.0f} m³/h"
        + (f" · decentral units supply {res.fans:.0f}" if res.fans else ""),
    ]
    for r in res.rooms:
        if r.role not in ("supply", "extract"):
            continue
        what = "supply" if r.role == "supply" else "extract"
        got = f" · {', '.join(r.by)} {r.got:.0f}" if r.by else " · nothing"
        flag = f", short {r.short:.0f}" if res.system and r.short > 0.5 else ""
        lines.append(f"{r.id} {r.name or r.use} {what} {r.need:.0f} m³/h{got}{flag}")
    for u, (sup, ext, flow) in res.units.items():
        cap = f" of {flow:g}" if flow is not None else ""
        lines.append(f"{u}: supply {sup:.0f}, extract {ext:.0f} m³/h{cap}")
    for k, (need, has, by) in res.overflow.items():
        if has < need - 1e-6:
            what = f"{need:.0f}" if need != float("inf") else "?"
            lines.append(f"{k} overflow {has:.0f} of {what} cm² ({', '.join(by) or 'none'})")
    data: dict[str, object] = {
        "area": round(res.area, 3),
        "volume": round(res.volume, 3),
        "q": {k: round(x, 2) for k, x in res.q.items()},
        "infiltration": round(res.inf, 2),
        "measure": res.measure,
        "design": round(res.design, 2),
        "rooms": {
            r.id: {"role": r.role, "need": round(r.need, 2), "got": round(r.got, 2), "by": r.by}
            for r in res.rooms
        },
        "terminals": {k: round(x, 2) for k, x in res.terminal.items()},
        "units": {
            u: {"supply": round(s, 2), "extract": round(e, 2), "flow": f}
            for u, (s, e, f) in res.units.items()
        },
        "overflow": {
            k: {"need": None if n == float("inf") else round(n, 1), "has": round(h, 1), "by": b}
            for k, (n, h, b) in res.overflow.items()
        },
        "short": short,
    }
    return Output(
        lines=lines,
        report=report(d, res, env, short),
        data=data,
        inputs={"rooms": [r.id for r in res.rooms]},
        ok=ok,
    )


ROLE_DE = {"supply": "Zuluft", "extract": "Abluft", "overflow": "Überström"}


def report(d: Derived, res: Result, env: Env, short: list[str]) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    ins = "hoch" if env.param("insulation") == "high" else "niedrig"
    out = [
        f"# Lüftungskonzept: {title}",
        "",
        f"Nutzungseinheit A_NE = {de(res.area, 1)} m², V_NE = {de(res.volume, 1)} m³;"
        f" n_50 = {de(env.param('n50'), 1)} 1/h; Wärmeschutz {ins}.",
        "",
        md_table(
            ["Lüftungsstufe", "q_v,ges m³/h"],
            [[f"{lv.upper()} ({LEVEL_DE[lv]})", de(res.q[lv], 0)] for lv in LEVELS],
            right=(1,),
        ),
        "",
        f"Infiltration q_v,inf = {de(res.inf, 0)} m³/h "
        + (
            f"< q_v,ges,FL = {de(res.q['fl'], 0)} m³/h: **lüftungstechnische Maßnahme"
            " erforderlich.**"
            if res.measure
            else f"≥ q_v,ges,FL = {de(res.q['fl'], 0)} m³/h: keine lüftungstechnische Maßnahme"
            " erforderlich."
        ),
        "",
        f"Auslegungsvolumenstrom {de(res.design, 0)} m³/h (Nennlüftung, mindestens die Summe"
        " der Abluftvolumenströme).",
        "",
        "## Räume",
        "",
    ]
    rows = [
        [
            r.id,
            r.name or r.use,
            ROLE_DE[r.role],
            de(r.area, 2),
            de(r.need, 0) if r.role != "overflow" else "–",
            ", ".join(r.by) or "–",
            de(r.got, 0) if r.by else "–",
            f"**{de(r.short, 0)}**" if res.system and r.short > 0.5 else "–",
        ]
        for r in res.rooms
        if r.role != "none"
    ]
    out += [
        md_table(
            ["Raum", "", "Art", "A m²", "q NL m³/h", "durch", "erhält m³/h", "fehlt m³/h"],
            rows,
            right=(3, 4, 6, 7),
        ),
        "",
    ]
    if res.units:
        out += [
            md_table(
                ["Gerät", "Zuluft m³/h", "Abluft m³/h", "Gerät max. m³/h"],
                [
                    [u, de(s, 0), de(e, 0), de(f, 0) if f is not None else "–"]
                    for u, (s, e, f) in res.units.items()
                ],
                right=(1, 2, 3),
            ),
            "",
        ]
    if res.overflow:
        out += [
            md_table(
                ["Raum", "Überströmöffnungen", "vorhanden cm²", "erforderlich cm²"],
                [
                    [
                        k,
                        ", ".join(b) or "–",
                        de(h, 0),
                        de(n, 0) if n != float("inf") else "über der Tabelle",
                    ]
                    for k, (n, h, b) in res.overflow.items()
                ],
                right=(2, 3),
            ),
            "",
        ]
    if res.fans:
        out += [
            f"Dezentrale Geräte: Zuluft im Mittel {de(res.fans, 0)} m³/h (Pendellüfter je zur"
            " Hälfte Zu- und Abluft).",
            "",
        ]
    out += [
        "**Ergebnis:** "
        + ("die Anlage deckt den Nennvolumenstrom jedes Raums." if not short else "; ".join(short))
        + "",
        "",
        "## Verfahren",
        "",
        "- Nutzungseinheit: alle Räume, deren Nutzung die Tabelle `vent-room` nicht mit none"
        " ausnimmt; Fläche und Volumen aus den Fertigmaßen.",
        "- q_v,ges = f · (a · A_NE² + b · A_NE + c) je Lüftungsstufe (Tabelle `vent-total`;"
        " Feuchteschutz nach Wärmeschutz).",
        "- q_v,inf = komp · V_NE · n_50 · (lage · Δp / 50)^n (Tabelle `vent-infiltration`);"
        " Maßnahme erforderlich, wenn q_v,inf < q_v,ges,FL.",
        "- Abluft: je Abluftraum q_Abluft der Tabelle, verhältnisgleich erhöht bis zum"
        " Auslegungsvolumenstrom; Zuluft: Auslegungsvolumenstrom nach den Faktoren f_R.",
        "- Anlage: Luftdurchlässe eines Zentralgeräts erhalten den Volumenstrom ihres Raums;"
        " dezentrale Geräte den Volumenstrom ihres Typs, Pendellüfter je zur Hälfte Zu- und"
        " Abluft.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Eine Nutzungseinheit je Projekt, keine Feuerstätten. Überströmöffnungen je Raum über"
        " seine Türen (Tabelle `vent-overflow`), sobald das Modell welche hat; der Weg der Luft"
        " durch die Überströmzone wird nicht verfolgt. Außenluftdurchlässe zählen mit dem"
        " Volumenstrom ihres Typs zur Zuluft ihres Raums.",
        "- Die Infiltration nach der Formel oben mit den Faktoren der Tabelle, ohne"
        " Unterscheidung nach Anlagenart und Gebäudelage über die Tabelle hinaus.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


AIRFLOW = Calculator(
    "airflow",
    "Lüftungskonzept und Luftvolumenströme",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (VENT_TOTAL, VENT_ROOM, VENT_INF, VENT_OVERFLOW),
)

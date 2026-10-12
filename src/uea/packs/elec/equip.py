"""The minimum electrical equipment of each room (DIN 18015-2): sockets, lighting outlets,
communication outlets and dedicated connections against the office's table (decision 0041).

A `norm` calculator. DIN 18015-2 sets the number of each by the room's use and, for most rooms, its
area, at the equipment grade the client chose. The numbers are the office's table
(`elec-minimum`); the code counts what the model has in each room and compares.

A room's devices are those mounted in it: a wall device belongs to the room in front of its face
(`mount.py`), a luminaire to the room it hangs in or faces. A waiver of `W-ELEC-010` on a room
(`waive _ W-ELEC-010 r5 "..."`) accepts what it lacks, and the report lists the reason.
"""

from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.core.registry import natural
from uea.derive import Derived
from uea.export.tables import USE_DE
from uea.packs.issues import Waive

VERSION = "0.1.0"
NORM = "DIN 18015-2"
CODE = "W-ELEC-010"
EPS = 1e-6
WHAT = ("sock", "light", "data", "conn")
WHAT_DE = {
    "sock": "Steckdosen",
    "light": "Beleuchtungsanschlüsse",
    "data": "Kommunikationsanschlüsse",
    "conn": "Geräteanschlüsse",
}

MINIMUM = Spec(
    "elec-minimum",
    "Minimum electrical equipment of a room",
    "DIN 18015-2",
    (
        Col("use", "text", "room use as UEA names it: living, kitchen, bedroom, ..."),
        Col("grade", "text", "equipment grade as the office's table names it, e.g. 1, 2, 3"),
        Col("upto", "num", "finished floor area up to, m²; the last row of a use covers any area"),
        Col("sock", "num", "socket outlets", sign="zero"),
        Col("light", "num", "lighting outlets", sign="zero"),
        Col("data", "num", "communication outlets (telephone, data, TV)", sign="zero"),
        Col("conn", "num", "dedicated connections (cooker, washing machine, ...)", sign="zero"),
    ),
    ("use", "grade", "upto"),
    "One row per use, grade and area range. A use with no rows is not checked.",
)

PARAMS = (
    Param("grade", str, None, "the equipment grade the client chose, as your table names it"),
    Param(
        "combos",
        str,
        "one",
        "a socket or data frame with several outlets counts as one, or each outlet counts",
        ("one", "each"),
    ),
)


@dataclass
class Row:
    id: str
    name: str
    use: str
    area: float
    status: str = "ok"
    """ok, short, waived, nodata (no row for the use) or large (larger than the last row)."""
    have: dict[str, int] = field(default_factory=dict[str, int])
    need: dict[str, int] = field(default_factory=dict[str, int])
    upto: float | None = None
    waiver: str | None = None

    @property
    def missing(self) -> dict[str, int]:
        return {
            k: self.need[k] - self.have.get(k, 0)
            for k in self.need
            if self.have.get(k, 0) < self.need[k]
        }


def counts(d: Derived, combos: str) -> dict[str, dict[str, int]]:
    """Per room: how many of each it has."""
    out: dict[str, dict[str, int]] = {}
    for mt in d.mounts.values():
        if mt.room is None:
            continue
        key = {"sock": "sock", "lum": "light", "data": "data", "conn": "conn"}.get(mt.kind)
        if key is None:
            continue
        n = 1
        if key in ("sock", "data") and combos == "each":
            n = int(getattr(d.model[mt.id], "n", 1))
        c = out.setdefault(mt.room, dict.fromkeys(WHAT, 0))
        c[key] += n
    return out


def waivers(d: Derived) -> dict[str, str]:
    """The rooms whose shortfall is accepted, with the reason."""
    out: dict[str, str] = {}
    for el in d.model.of_kind("waive"):
        if isinstance(el, Waive) and el.code == CODE:
            out[el.target.id] = (el.label or "") + (f" ({el.by})" if el.by else "")
    return out


def rooms_in(d: Derived, scope: str | None) -> list[str]:
    g = d.arch
    if scope is None:
        found = list(g.rooms)
    elif scope in g.rooms:
        found = [scope]
    elif scope in g.levels:
        found = [r.id for r in g.rooms.values() if r.level == scope]
    else:
        raise ValueError(f"{scope!r} is not a room or a storey")
    if not found:
        raise ValueError("there are no rooms")
    return sorted(found, key=natural)


def check(d: Derived, rid: str, have: dict[str, int], env: Env, waived: dict[str, str]) -> Row:
    rg = d.arch.rooms[rid]
    el = d.model[rid]
    use = str(getattr(el, "use", "other"))
    row = Row(rid, el.label or rid, use, rg.area_fin, have=have)
    grade = env.param("grade")
    rows = sorted(
        (
            r
            for r in env.table(MINIMUM).rows
            if str(r["use"]).casefold() == use.casefold()
            and str(r["grade"]).casefold() == str(grade).casefold()
        ),
        key=lambda r: float(r["upto"]),
    )
    if not rows:
        row.status = "nodata"
        return row
    hit = next((r for r in rows if row.area <= float(r["upto"]) + EPS), None)
    if hit is None:
        # larger than the last range: the last row, and the report says so
        hit = rows[-1]
        row.status = "large"
    row.upto = float(hit["upto"])
    row.need = {k: round(float(hit[k])) for k in WHAT}
    if row.missing:
        if rid in waived:
            row.status, row.waiver = "waived", waived[rid]
        else:
            row.status = "short"
    return row


def run(d: Derived, scope: str | None, env: Env) -> Output:
    env.table(MINIMUM)
    have = counts(d, env.param("combos"))
    waived = waivers(d)
    rows = [
        check(d, rid, have.get(rid, dict.fromkeys(WHAT, 0)), env, waived)
        for rid in rooms_in(d, scope)
    ]
    count = {
        s: sum(1 for r in rows if r.status == s)
        for s in ("ok", "short", "waived", "nodata", "large")
    }
    lines = [
        f"{len(rows)} rooms: {count['ok'] + count['large']} ok, {count['short']} short"
        + (f", {count['waived']} waived" if count["waived"] else "")
        + (f", {count['nodata']} not in table" if count["nodata"] else "")
    ]
    for r in rows:
        if r.status in ("short", "waived"):
            lack = ", ".join(f"{k} {r.have.get(k, 0)}/{r.need[k]}" for k in r.missing)
            tail = f" (waived: {r.waiver})" if r.status == "waived" else f" {CODE}"
            lines.append(f"{r.id} {r.use} {r.area:.1f} m²: {lack}{tail}")
        elif r.status == "nodata":
            lines.append(f"{r.id} {r.use}: no row in elec-minimum for grade {env.param('grade')}")
        elif r.status == "large" and r.missing:
            lines.append(f"{r.id}: larger than the table's last row ({r.upto:g} m²)")
    return Output(
        lines=lines,
        report=report(d, rows, env),
        data={"rooms": {r.id: _data(r) for r in rows}},
        inputs={"rooms": [r.id for r in rows]},
        ok=count["short"] == 0 and count["nodata"] == 0,
    )


def _data(r: Row) -> dict[str, object]:
    return {
        "use": r.use,
        "area": round(r.area, 4),
        "status": r.status,
        "upto": r.upto,
        "have": r.have,
        "need": r.need,
        "missing": r.missing,
        "waiver": r.waiver,
    }


STATUS_DE = {
    "ok": "erfüllt",
    "large": "erfüllt (Fläche über der letzten Tabellenzeile)",
    "short": "**nicht erfüllt**",
    "waived": "nicht erfüllt, akzeptiert",
    "nodata": "keine Tabellenzeile",
}


def report(d: Derived, rows: list[Row], env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    head = ["Raum", "Nutzung", "Fläche m²", *(WHAT_DE[k] for k in WHAT), "Ergebnis"]

    def cell(r: Row, k: str) -> str:
        if not r.need:
            return str(r.have.get(k, 0))
        return f"{r.have.get(k, 0)} / {r.need[k]}"

    body = [
        [
            r.id if r.name == r.id else f"{r.id} {r.name}",
            USE_DE.get(r.use, r.use),
            de(r.area),
            *(cell(r, k) for k in WHAT),
            STATUS_DE[r.status],
        ]
        for r in rows
    ]
    accepted = [f"- {r.id}: {r.waiver}" for r in rows if r.status == "waived"]
    out = [
        f"# Mindestausstattung der elektrischen Anlage: {title}",
        "",
        f"Ausstattungswert {env.param('grade')}. Je Spalte: vorhanden / gefordert.",
        "",
        md_table(head, body, right=(2, 3, 4, 5, 6)),
        "",
        "## Verfahren",
        "",
        "- Anzahl der Steckdosen, Beleuchtungs-, Kommunikations- und Geräteanschlüsse je Raum"
        " nach DIN 18015-2, nach Nutzung und Fertigfläche des Raums aus der Tabelle des Büros"
        " (siehe Normtabellen oben).",
        "- Gezählt wird, was im Modell im Raum liegt: Wandgeräte gehören zu dem Raum vor ihrer"
        " Wandseite, Leuchten zu dem Raum, in dem sie hängen.",
        "- Mehrfachsteckdosen und Mehrfach-Datendosen zählen "
        + ("als eine." if env.param("combos") == "one" else "je Anschluss."),
        "",
        *(["## Akzeptierte Abweichungen", "", *accepted, ""] if accepted else []),
        "## Nicht geprüft",
        "",
        "- Die Zahl der Stromkreise je Wohnung und die Anordnung der Anschlüsse im Raum.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


EQUIP = Calculator(
    "equip",
    "Mindestausstattung (DIN 18015-2)",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (MINIMUM,),
)

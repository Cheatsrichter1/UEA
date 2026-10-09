"""Cable sizing against overload: is the cable big enough for its breaker? (decision 0028)

A `norm` calculator. Clauses implemented (cited, the texts are not reproduced):

- DIN VDE 0100-430 (IEC 60364-4-43), 433.1: a circuit is protected against overload when
  Ib <= In <= Iz and I2 <= 1.45 * Iz. For a miniature circuit-breaker of characteristic B, C or
  D (EN 60898) the conventional tripping current is I2 = 1.45 * In, so the second condition
  follows from In <= Iz.
- DIN VDE 0100-520 (IEC 60364-5-52) and DIN VDE 0298-4: the current-carrying capacity Iz of a
  cable is the value of the table for its installation method, insulation and loaded conductors,
  multiplied by the correction factors for the ambient temperature and for grouping.

The tables are the office's (`uea data`): the formulas are here, the numbers are not.
Not covered: short-circuit protection, the fault loop, the minimum cross-section of a use.
"""

from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.packs.elec.geometry import CircGeo, circuits_in, declared_amps
from uea.packs.elec.kinds import Circ

VERSION = "0.1.0"
NORM = "DIN VDE 0100-430 (433.1), DIN VDE 0100-520, DIN VDE 0298-4"
EPS = 1e-9
OVERLOAD = frozenset("BCD")
"""Characteristics with I2 = 1.45 * In (EN 60898)."""

AMPACITY = Spec(
    "ampacity",
    "Current-carrying capacity Iz",
    "DIN VDE 0298-4",
    (
        Col(
            "method", "text", "reference installation method as the table names it: A1, B2, C, ..."
        ),
        Col("insulation", "text", "insulation of the cable", ("PVC", "XLPE")),
        Col("loaded", "num", "loaded conductors: 2 (single-phase) or 3 (three-phase)"),
        Col("mm2", "num", "conductor cross-section, mm²"),
        Col("amps", "num", "current-carrying capacity at reference conditions, A"),
    ),
    ("method", "insulation", "loaded", "mm2"),
    "Copper conductors. One row for each installation method, insulation, number of loaded"
    " conductors and cross-section the office uses.",
)
TEMPERATURE = Spec(
    "temp-factor",
    "Correction factor for the ambient temperature",
    "DIN VDE 0298-4",
    (
        Col("insulation", "text", "insulation of the cable", ("PVC", "XLPE")),
        Col("celsius", "num", "ambient temperature, °C"),
        Col("factor", "num", "factor for Iz"),
    ),
    ("insulation", "celsius"),
    "Needed only when the calculation is run with temp=<°C>.",
)
GROUPING = Spec(
    "group-factor",
    "Correction factor for grouped circuits",
    "DIN VDE 0298-4",
    (
        Col("arrangement", "text", "how they are grouped, as the table names it"),
        Col("circuits", "num", "number of circuits in the group"),
        Col("factor", "num", "factor for Iz"),
    ),
    ("arrangement", "circuits"),
    "Needed only when the calculation is run with group=<n> above 1.",
)

PARAMS = (
    Param("method", str, None, "installation method as your ampacity table names it, e.g. B2"),
    Param("insulation", str, "PVC", "insulation of the cables", ("PVC", "XLPE")),
    Param(
        "temp",
        float,
        None,
        "ambient temperature in °C; left out: the table's reference",
        optional=True,
    ),
    Param("group", int, 1, "circuits grouped together; 1: no grouping factor"),
    Param("arrangement", str, "", "how they are grouped, as your group-factor table names it"),
)


@dataclass
class Row:
    id: str
    cable: str
    breaker: str
    loaded: int
    status: str = "ok"
    """ok, fail, nodata (a table has no row for it) or open (the check does not apply)."""
    iz_table: float | None = None
    kt: float = 1.0
    kg: float = 1.0
    iz: float | None = None
    amps: float = 0.0
    """The rated current of the breaker, In."""
    ib: float | None = None
    """The current of the declared load, if any."""
    smallest: float | None = None
    """The smallest cross-section of the table that carries In."""
    notes: list[str] = field(default_factory=list[str])


def check(cg: CircGeo, el: Circ, env: Env) -> Row:
    method, ins = env.param("method"), env.param("insulation")
    temp, group = env.param("temp"), env.param("group")
    loaded = 2 if cg.phases == 1 else 3
    row = Row(cg.id, el.cable.fmt(), el.breaker.fmt(), loaded, amps=el.breaker.amps)
    row.ib = declared_amps(cg)
    amp = env.table(AMPACITY)
    hit = amp.find(method=method, insulation=ins, loaded=loaded, mm2=el.cable.mm2)
    if hit is None:
        row.status = "nodata"
        row.notes.append(f"no row for {method} {ins} {loaded} loaded {el.cable.mm2:g} mm²")
        return row
    row.iz_table = float(hit["amps"])
    if temp is not None:
        t = env.table(TEMPERATURE).find(insulation=ins, celsius=temp)
        if t is None:
            row.status = "nodata"
            row.notes.append(f"no row for {ins} at {temp:g} °C in temp-factor")
            return row
        row.kt = float(t["factor"])
    if group > 1:
        g = env.table(GROUPING).find(arrangement=env.param("arrangement"), circuits=group)
        if g is None:
            row.status = "nodata"
            row.notes.append(
                f"no row for {env.param('arrangement')!r} with {group} in group-factor"
            )
            return row
        row.kg = float(g["factor"])
    row.iz = row.iz_table * row.kt * row.kg
    same = [
        r
        for r in amp.rows
        if r["loaded"] == loaded
        and str(r["method"]).casefold() == method.casefold()
        and str(r["insulation"]).casefold() == ins.casefold()
    ]
    carrying = [float(r["mm2"]) for r in same if float(r["amps"]) * row.kt * row.kg >= row.amps]
    row.smallest = min(carrying) if carrying else None
    overdrawn = row.ib is not None and row.ib > row.amps + EPS
    if overdrawn:
        row.notes.append(f"the declared load needs {row.ib:.1f} A, more than In")
    if el.breaker.char not in OVERLOAD:
        row.status = "open"
        row.notes.append(f"I2 of characteristic {el.breaker.char} is not known: not checked")
    elif row.amps > row.iz + EPS or overdrawn:
        row.status = "fail"
    return row


def run(d: Derived, scope: str | None, env: Env) -> Output:
    env.table(AMPACITY)
    if env.param("temp") is not None:
        env.table(TEMPERATURE)
    if env.param("group") > 1:
        env.table(GROUPING)
    circuits = circuits_in(d, scope)
    if not circuits:
        raise ValueError("there are no circuits")
    rows: list[Row] = []
    for cg in circuits:
        el = d.model[cg.id]
        assert isinstance(el, Circ)
        rows.append(check(cg, el, env))
    count = {s: sum(1 for r in rows if r.status == s) for s in ("ok", "fail", "nodata", "open")}
    lines = [
        f"{len(rows)} circuits: {count['ok']} ok, {count['fail']} fail"
        + (f", {count['nodata']} without table data" if count["nodata"] else "")
        + (f", {count['open']} not checked" if count["open"] else "")
    ]
    for r in rows:
        if r.status == "ok":
            continue
        if r.status == "fail":
            why = f"In {r.amps:g} A > Iz {r.iz:.1f} A" if r.iz is not None and r.amps > r.iz else ""
            hint = f"; smallest in table {r.smallest:g} mm²" if r.smallest else "; none in table"
            lines.append(f"{r.id} {r.cable} {r.breaker}: {why or '; '.join(r.notes)}{hint}")
        else:
            lines.append(f"{r.id} {r.cable} {r.breaker}: {'; '.join(r.notes)}")
    return Output(
        lines=lines,
        report=report(d, rows, env),
        data={"circuits": {r.id: _data(r) for r in rows}},
        inputs={"circuits": [r.id for r in rows]},
        ok=count["fail"] == 0 and count["nodata"] == 0 and count["open"] == 0,
    )


def _data(r: Row) -> dict[str, object]:
    return {
        "cable": r.cable,
        "breaker": r.breaker,
        "loaded": r.loaded,
        "status": r.status,
        "iz_table": r.iz_table,
        "k_temp": r.kt,
        "k_group": r.kg,
        "iz": None if r.iz is None else round(r.iz, 4),
        "in": r.amps,
        "ib_declared": None if r.ib is None else round(r.ib, 4),
        "smallest_mm2": r.smallest,
        "notes": r.notes,
    }


STATUS_DE = {
    "ok": "erfüllt",
    "fail": "**nicht erfüllt**",
    "nodata": "keine Tabellenwerte",
    "open": "nicht geprüft",
}


def report(d: Derived, rows: list[Row], env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    temp = env.param("temp")
    head = [
        "Stromkreis",
        "Leitung",
        "Sicherung",
        "Iz Tabelle A",
        "k Temp.",
        "k Gruppe",
        "Iz A",
        "In A",
        "Ib A",
        "Ergebnis",
    ]
    body = [
        [
            r.id,
            r.cable,
            r.breaker,
            "–" if r.iz_table is None else de(r.iz_table, 1),
            de(r.kt),
            de(r.kg),
            "–" if r.iz is None else de(r.iz, 1),
            de(r.amps, 1),
            "–" if r.ib is None else de(r.ib, 1),
            STATUS_DE[r.status]
            + (
                f" (kleinster Querschnitt der Tabelle: {de(r.smallest, 1)} mm²)"
                if r.status == "fail" and r.smallest
                else ""
            ),
        ]
        for r in rows
    ]
    out = [
        f"# Leitungsquerschnitt und Überlastschutz: {title}",
        "",
        md_table(head, body, right=(3, 4, 5, 6, 7, 8)),
        "",
        "## Verfahren",
        "",
        "- Bedingung nach DIN VDE 0100-430, 433.1: Ib ≤ In ≤ Iz. Bei Leitungsschutzschaltern der"
        " Charakteristik B, C und D ist der große Prüfstrom I2 = 1,45 · In, die Bedingung"
        " I2 ≤ 1,45 · Iz folgt dann aus In ≤ Iz.",
        "- Iz = Tabellenwert für Verlegeart, Isolierung, Zahl der belasteten Adern und Querschnitt,"
        " mal Korrekturfaktoren für Umgebungstemperatur und Häufung. Die Tabellen stammen aus der"
        " lizenzierten Normfassung des Büros (siehe Normtabellen oben).",
        f"- Verlegeart {env.param('method')}, Isolierung {env.param('insulation')}"
        + (f", Umgebungstemperatur {de(temp, 0)} °C" if temp is not None else ", Bezugsbedingungen")
        + (f", {env.param('group')} gehäufte Stromkreise" if env.param("group") > 1 else "")
        + ".",
        "- Ib: nur der Strom aus der angegebenen Anschlussleistung (Leuchten, Anschlüsse,"
        " Einspeisungen); Steckdosen haben keine angegebene Leistung. Ohne Angabe bleibt Ib offen.",
        "",
        "## Nicht geprüft",
        "",
        "- Kurzschlussschutz, Fehlerschleifenimpedanz und Abschaltzeit, Spannungsfall"
        " (Rechenverfahren `vdrop`), Mindestquerschnitte nach Verwendung, Zuleitung.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


CABLE = Calculator(
    "cable",
    "Leitungsquerschnitt (Überlastschutz)",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (AMPACITY, TEMPERATURE, GROUPING),
)

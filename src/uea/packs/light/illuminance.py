"""The average maintained illuminance of a room by the utilisation factor method, against the
room's illuminance targets (decision 0050).

A `norm` calculator. For each target of a whole room (`illum il1 r2 em=150 h=0.75`):

    Ē = MF · Σ Φ_i · UF_i / A        k_i = 2 A / (h_i · U)

A is the room's finished floor area and U its perimeter (for a rectangle a · b / (h (a + b))),
h_i the height of luminaire i above the working plane, Φ_i the flux of its type and UF_i the
utilisation factor of its distribution at the room index k_i and the reflectances `refl=`, from
the office's table `light-uf` (the luminaire maker's data or the LiTG tables). Between two rows of
k the factor is interpolated linearly, as the method does; outside the table it is not guessed.
MF is the maintenance factor, the planner's statement (DIN EN 12464-1 asks for it).

A task area (`at=` and `area=`) needs a point calculation; it is listed, not checked.
"""

import math
from dataclasses import dataclass, field
from itertools import pairwise

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec, Table
from uea.core.registry import natural
from uea.derive import Derived
from uea.export.tables import USE_DE
from uea.packs.light.geometry import lum_type
from uea.packs.light.kinds import Illum, LumType

VERSION = "0.1.0"
NORM = "Wirkungsgradverfahren (LiTG-Publikation 3.5, CIE 40); Wartungswert nach DIN EN 12464-1"
EPS = 1e-6

UF = Spec(
    "light-uf",
    "Utilisation factor by distribution, reflectances and room index",
    "luminaire maker's data or LiTG-Publikation 3.5",
    (
        Col("dist", "text", "light distribution as the luminaire types name it: cos1, cos3, ..."),
        Col("refl", "text", "reflectances of ceiling, walls and floor as you name them, e.g. 753"),
        Col("k", "num", "room index"),
        Col("uf", "num", "utilisation factor for the type's flux= (LED: the room utilance)"),
    ),
    ("dist", "refl", "k"),
    "One row per distribution, reflectances and room index; k in between is interpolated.",
)

PARAMS = (
    Param("refl", str, None, "reflectances of ceiling, walls and floor as light-uf names them"),
    Param("mf", float, None, "maintenance factor of the installation, more than 0 and at most 1"),
)


@dataclass
class Lit:
    """One luminaire's share of a room's illuminance."""

    id: str
    type: str | None
    flux: float | None
    w: float | None
    dist: str | None
    h: float
    """Height above the working plane."""
    k: float | None = None
    uf: float | None = None
    note: str | None = None
    """Why it adds nothing: no data, or not above the plane."""

    @property
    def lumens(self) -> float:
        """The flux it brings to the working plane before maintenance."""
        return (self.flux or 0.0) * (self.uf or 0.0)


@dataclass
class Row:
    id: str
    room: str
    name: str
    use: str
    em: float
    plane: float
    area: float
    perimeter: float
    lits: list[Lit] = field(default_factory=list[Lit])
    e: float = 0.0
    status: str = "ok"
    """ok, low, or nodata (a luminaire lacks flux=, dist= or a row of light-uf)."""
    add: tuple[str, int] | None = None
    """For a low room: how many more of which type reach the target at the same height."""

    @property
    def watts(self) -> float | None:
        if any(x.w is None for x in self.lits):
            return None
        return sum(x.w or 0.0 for x in self.lits)

    @property
    def density(self) -> float | None:
        w = self.watts
        return None if w is None or not self.lits else w / self.area


def room_index(area: float, perimeter: float, h: float) -> float:
    """k = 2 A / (h U); for a rectangle a b / (h (a + b))."""
    return 2 * area / (h * perimeter)


def factor(table: Table, dist: str, refl: str, k: float) -> float | None:
    """The utilisation factor at k: a row, or linear between the two rows around it."""
    rows = sorted(
        (
            (float(r["k"]), float(r["uf"]))
            for r in table.rows
            if str(r["dist"]).casefold() == dist.casefold()
            and str(r["refl"]).casefold() == refl.casefold()
        ),
        key=lambda r: r[0],
    )
    for (k0, u0), (k1, u1) in pairwise(rows):
        if k0 - EPS <= k <= k1 + EPS:
            return u0 + (u1 - u0) * (min(max(k, k0), k1) - k0) / (k1 - k0)
    if len(rows) == 1 and abs(rows[0][0] - k) <= EPS:
        return rows[0][1]
    return None


def targets_in(d: Derived, scope: str | None) -> list[Illum]:
    g = d.arch
    found = [el for el in d.model.of_kind("illum") if isinstance(el, Illum)]
    if scope is None:
        pass
    elif scope in g.rooms:
        found = [t for t in found if t.room.id == scope]
    elif scope in g.levels:
        found = [t for t in found if t.room.id in g.rooms and g.rooms[t.room.id].level == scope]
    elif any(t.id == scope for t in found):
        found = [t for t in found if t.id == scope]
    else:
        raise ValueError(f"{scope!r} is not a room, a storey or an illuminance target")
    found = [t for t in found if t.room.id in g.rooms]
    if not found:
        raise ValueError(
            "there are no illuminance targets; add one per room: illum _ r1 em=<lx> h=<m>"
        )
    return sorted(found, key=lambda t: (natural(t.room.id), natural(t.id)))


def lits_in(d: Derived, room: str, plane: float, table: Table, refl: str, row: Row) -> None:
    """The luminaires in the room, each with its room index and utilisation factor."""
    ffl = d.arch.levels[d.arch.rooms[room].level].z
    for mt in sorted(d.mounts.values(), key=lambda m: natural(m.id)):
        if mt.kind != "lum" or mt.room != room:
            continue
        t = lum_type(d.model, d.model[mt.id])
        x = Lit(
            mt.id,
            t.id if t else None,
            t.flux if t else None,
            t.w if t else None,
            t.dist if t else None,
            mt.z - ffl - plane,
        )
        row.lits.append(x)
        if t is None:
            x.note = "no type and no default type"
        elif t.flux is None or t.dist is None:
            x.note = f"type {t.id} has no " + " or ".join(
                n for n, v in (("flux=", t.flux), ("dist=", t.dist)) if v is None
            )
        elif x.h <= EPS:
            x.note = "not above the working plane"
            continue
        if x.note:
            row.status = "nodata"
            continue
        assert t is not None and t.dist is not None
        x.k = room_index(row.area, row.perimeter, x.h)
        x.uf = factor(table, t.dist, refl, x.k)
        if x.uf is None:
            x.note = f"no row of light-uf for {t.dist} {refl} around k {x.k:.2f}"
            row.status = "nodata"


def addition(d: Derived, row: Row, table: Table, refl: str, mf: float) -> tuple[str, int] | None:
    """The luminaires of the room's main type (the most flux on the plane) to add at its height;
    in a room without any, of the default type at the ceiling."""
    best = max(row.lits, key=lambda x: x.lumens, default=None)
    if best is not None and best.lumens > 0 and best.type:
        typ, each = best.type, best.lumens
    else:
        defaults = [
            t for t in d.model.of_kind("type", "lum") if isinstance(t, LumType) and t.default
        ]
        rg = d.arch.rooms[row.room]
        if not defaults or rg.height is None or defaults[0].flux is None:
            return None
        t = defaults[0]
        h = rg.height - row.plane
        if h <= EPS or t.dist is None:
            return None
        uf = factor(table, t.dist, refl, room_index(row.area, row.perimeter, h))
        if uf is None:
            return None
        typ, each = t.id, (t.flux or 0.0) * uf
    n = math.ceil((row.em - row.e) * row.area / (mf * each) - EPS)
    return (typ, max(n, 1))


def calc_row(d: Derived, t: Illum, env: Env) -> Row:
    table = env.table(UF)
    refl, mf = str(env.param("refl")), float(env.param("mf"))
    rg = d.arch.rooms[t.room.id]
    el = d.model[t.room.id]
    row = Row(
        t.id,
        t.room.id,
        el.label or el.id,
        str(getattr(el, "use", "other")),
        t.em,
        t.h,
        rg.area_fin,
        rg.fin.length,
    )
    lits_in(d, t.room.id, t.h, table, refl, row)
    row.e = mf * sum(x.lumens for x in row.lits) / row.area
    if row.status == "nodata":
        return row
    if row.e < row.em - EPS:
        row.status = "low"
        row.add = addition(d, row, table, refl, mf)
    return row


def run(d: Derived, scope: str | None, env: Env) -> Output:
    env.table(UF)
    mf = env.param("mf")
    if not 0 < mf <= 1:
        raise ValueError("mf must be more than 0 and at most 1")
    targets = targets_in(d, scope)
    rows = [calc_row(d, t, env) for t in targets if t.area is None]
    tasks = [t for t in targets if t.area is not None]
    count = {s: sum(1 for r in rows if r.status == s) for s in ("ok", "low", "nodata")}
    head = f"{len(rows)} rooms: {count['ok']} ok, {count['low']} low"
    if count["nodata"]:
        head += f", {count['nodata']} without data"
    if tasks:
        head += f"; {len(tasks)} task areas not checked (point calculation)"
    lines = [head]
    for r in rows:
        line = f"{r.id} {r.room}: {r.e:.0f} lx"
        if r.status == "nodata":
            gaps = "; ".join(f"{x.id} {x.note}" for x in r.lits if x.note)
            lines.append(f"{line} of {r.em:g}, without data: {gaps}")
            continue
        line += f" {'≥' if r.status == 'ok' else '<'} {r.em:g} on {r.plane:g} m"
        line += f", {len(r.lits)} lum"
        if r.density is not None:
            line += f", {r.density:.1f} W/m²"
        if r.status == "low":
            line += f"; add {r.add[1]} {r.add[0]}" if r.add else "; no type to add"
        skipped = [x.id for x in r.lits if x.note]
        if skipped:
            line += f" ({' '.join(skipped)} below the plane)"
        lines.append(line)
    return Output(
        lines=lines,
        report=report(d, rows, tasks, env),
        data={"targets": {r.id: _data(r) for r in rows}, "tasks": [t.id for t in tasks]},
        inputs={"targets": [r.id for r in rows]},
        ok=count["low"] == 0 and count["nodata"] == 0,
    )


def _data(r: Row) -> dict[str, object]:
    return {
        "room": r.room,
        "use": r.use,
        "em": r.em,
        "plane": r.plane,
        "area": round(r.area, 4),
        "perimeter": round(r.perimeter, 4),
        "e": round(r.e, 2),
        "status": r.status,
        "watts": r.watts,
        "w_m2": None if r.density is None else round(r.density, 3),
        "add": None if r.add is None else {"type": r.add[0], "n": r.add[1]},
        "lums": [
            {
                "id": x.id,
                "type": x.type,
                "flux": x.flux,
                "dist": x.dist,
                "h": round(x.h, 4),
                "k": None if x.k is None else round(x.k, 4),
                "uf": None if x.uf is None else round(x.uf, 4),
                "note": x.note,
            }
            for x in r.lits
        ],
    }


STATUS_DE = {"ok": "erfüllt", "low": "**nicht erfüllt**", "nodata": "Daten fehlen"}


def report(d: Derived, rows: list[Row], tasks: list[Illum], env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    mf = float(env.param("mf"))
    summary = md_table(
        [
            *("Ziel", "Raum", "Nutzung", "Fläche m²", "Nutzebene m", "Leuchten"),
            *("Ē lx", "Ēm lx", "W/m²", "Ergebnis"),
        ],
        [
            [
                r.id,
                r.room if r.name == r.room else f"{r.room} {r.name}",
                USE_DE.get(r.use, r.use),
                de(r.area),
                de(r.plane),
                str(len(r.lits)),
                de(r.e, 0),
                de(r.em, 0),
                "–" if r.density is None else de(r.density, 1),
                STATUS_DE[r.status] + (f"; {r.add[1]} × {r.add[0]} ergänzen" if r.add else ""),
            ]
            for r in rows
        ],
        right=(3, 4, 5, 6, 7, 8),
    )
    detail = md_table(
        ["Ziel", "Leuchte", "Typ", "Φ lm", "Verteilung", "h m", "k", "η (UF)", "Hinweis"],
        [
            [
                r.id,
                x.id,
                x.type or "–",
                "–" if x.flux is None else de(x.flux, 0),
                x.dist or "–",
                de(x.h),
                "–" if x.k is None else de(x.k),
                "–" if x.uf is None else de(x.uf, 3),
                NOTE_DE.get(x.note or "", x.note or ""),
            ]
            for r in rows
            for x in r.lits
        ],
        right=(3, 5, 6, 7),
    )
    task_lines = [
        f"- {t.id} in {t.room.id}: {t.em:g} lx auf {de(t.h)} m, Sehaufgabenbereich"
        f" {de(t.area.w)} × {de(t.area.h)} m ({t.label or 'ohne Bezeichnung'})"
        for t in tasks
        if t.area is not None
    ]
    out = [
        f"# Beleuchtung, mittlere Beleuchtungsstärke: {title}",
        "",
        f"Wartungsfaktor MF = {de(mf)}, Reflexionsgrade {env.param('refl')} (Decke, Wände,"
        " Boden, wie in der Tabelle des Büros benannt).",
        "",
        summary,
        "",
        "## Leuchten",
        "",
        detail if any(r.lits for r in rows) else "Keine Leuchten in den Räumen.",
        "",
        "## Verfahren",
        "",
        "- Wirkungsgradverfahren: Ē = MF · Σ Φ · η / A, je Leuchte mit ihrem Raumindex"
        " k = 2 · A / (h · U), bei Rechteckräumen k = a · b / (h · (a + b)).",
        "- A und U: Fertigfläche und Umfang des Raums aus dem Modell; h: Höhe der Leuchte"
        " über der Nutzebene des Ziels.",
        "- η (Raumwirkungsgrad bzw. Beleuchtungswirkungsgrad) aus der Tabelle des Büros nach"
        " Lichtverteilung, Reflexionsgraden und k (siehe Normtabellen oben), zwischen zwei"
        " Raumindizes linear interpoliert, außerhalb der Tabelle nicht berechnet.",
        "- Ergänzung bei Unterschreitung: Anzahl der Leuchten des im Raum maßgebenden Typs"
        " auf gleicher Höhe, ohne Leuchten im Raum des Standardtyps an der Decke.",
        "",
        *(["## Sehaufgabenbereiche, nicht geprüft", "", *task_lines, ""] if task_lines else []),
        "## Nicht geprüft",
        "",
        "- Gleichmäßigkeit U0, Blendung (UGR), Farbwiedergabe, Beleuchtungsstärken an Wänden"
        " und Decke, Sehaufgabenbereiche (Punktberechnung), Tageslicht, Notbeleuchtung.",
        "- Ob die Leuchten gleichmäßig verteilt sind, wie das Verfahren voraussetzt; Wandleuchten"
        " und Pendelleuchten zählen wie Deckenleuchten auf ihrer Höhe.",
        "- Ob der Raum für das Verfahren hinreichend rechteckig ist (L-förmige Räume teilen).",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


NOTE_DE = {
    "not above the working plane": "nicht über der Nutzebene, nicht gerechnet",
    "no type and no default type": "kein Typ",
}


LIGHT = Calculator(
    "light",
    "Mittlere Beleuchtungsstärke (Wirkungsgradverfahren)",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (UF,),
)

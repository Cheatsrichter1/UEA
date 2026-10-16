"""Areas and volumes per DIN 277 (Grundflächen und Rauminhalte im Hochbau).

A `norm` calculator. DIN 277 is licensed: its text and its table of uses are not in this
repository. This module implements the method with the standard's defined terms; the office
assigns UEA's room uses to the standard's usage groups in the table `din277-uses`, from its own
copy (decision 0008). What is implemented, per storey (Grundrissebene):

- BGF (Brutto-Grundfläche): the outline of the storey at its outer faces, finishes included
  (render, cladding), filled; the storey's slabs widen it. Lufträume (voids in the storey's own
  slab) are no floor and do not count.
- NRF (Netto-Raumfläche): each room's finished outline (between the finished surfaces), minus
  the voids in it. A stair's footprint on the storey it starts from is VF; the rest of the room
  goes to the group of its use: NUF 1 to 7, TF 8, VF 9.
- KGF (Konstruktions-Grundfläche): BGF − NRF: walls and their finishes, door reveals, niches,
  installation shafts.
- BRI (Brutto-Rauminhalt): each storey's BGF outline from its finished floor to the finished
  floor of the storey above; the lowest storey from the underside of its floor construction
  (all layers of its slab, foundations excluded); the top storey up to the top of the roof
  covering.

Not covered: areas that are not enclosed on all sides or not covered (Sonderfall der
Raumumschließung: balconies, loggias, terraces; not in the model yet), courtyards inside a
storey's outline (filled as if enclosed), roofs over a storey below the top one (split levels:
their slice ends at the floor above), the split of areas by clear height.
"""

from dataclasses import dataclass, field
from typing import get_args

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from uea.calc import Calculator, Env, Output, data, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.fmt import ar
from uea.geom import Ceil, Lin, Part, clean, filled, union
from uea.packs.arch.geometry import ArchGeo, LevelGeo
from uea.packs.arch.kinds import Room, RoomUse

VERSION = "0.1.0"
NORM = "DIN 277:2021-08"

USES = Spec(
    "din277-uses",
    "Room uses in the usage groups of DIN 277",
    "DIN 277",
    (
        Col("use", "text", "room use as UEA names it", choices=get_args(RoomUse)),
        Col("group", "num", "usage group: 1 to 7 NUF, 8 TF, 9 VF"),
    ),
    ("use",),
    "One row per room use. A use with no row stops the split of the NRF and is named.",
)


def group_name(g: int) -> str:
    return f"NUF {g}" if g <= 7 else ("TF" if g == 8 else "VF")


@dataclass
class RoomPart:
    id: str
    name: str
    use: str
    area: float
    """NRF of the room, stairs excluded."""
    stair: float = 0.0
    """Stair footprint in the room: VF."""
    group: int | None = None


@dataclass
class LevelAreas:
    id: str
    bgf: float
    nrf: float
    rooms: list[RoomPart]
    void: float
    """Lufträume cut from the BGF."""
    unassigned: float
    """Floor regions with no room: they end up in the KGF."""
    bri: float | None
    heights: str
    """How the BRI slice is bounded, for the report."""
    groups: dict[str, float] = field(default_factory=dict[str, float])

    @property
    def kgf(self) -> float:
        return self.bgf - self.nrf


def outline(g: ArchGeo, level: str) -> BaseGeometry:
    """The storey at its outer faces with the finishes, filled; its slabs widen it.

    The outline of the cores grows by the thinnest exterior finish, mitred, so the finish runs
    round the corners and over the ends of walls; an exterior wall with a thicker finish adds
    its own band.
    """
    walls = g.walls_on(level)
    parts: list[BaseGeometry] = [w.poly for w in walls]
    parts += [s.outline for s in g.slabs.values() if s.level == level and s.status != "demolish"]
    out = filled(union(parts))
    ext = [(w, w.finish(w.ext)) for w in walls if w.ext is not None]
    f = ext_finish(g, level)
    if f > 0 and not out.is_empty:
        out = clean(out.buffer(f, join_style="mitre"))
    bands = [
        w.box(w.lo - x, w.lo) if w.ext == "lo" else w.box(w.hi, w.hi + x)
        for w, x in ext
        if x > f + 1e-9
    ]
    return filled(union([out, *bands])) if bands else out


def ext_finish(g: ArchGeo, level: str) -> float:
    """The thinnest exterior finish of the storey's exterior walls: what the outline grows by."""
    return min((w.finish(w.ext) for w in g.walls_on(level) if w.ext is not None), default=0.0)


def _voids(g: ArchGeo, level: str) -> BaseGeometry:
    slab = g.slab_on(level)
    if slab is None:
        return union([])
    return union(v.poly for v in g.voids.values() if v.slab == slab.id)


def _top(g: ArchGeo, lv: LevelGeo) -> Ceil:
    """The top of the roof covering above the storey's FFL, as a height field. A roof without
    an overhang covers the cores; it grows as the outline does, so it covers the finish too."""
    grow = ext_finish(g, lv.id)
    parts: list[Part] = []
    for roof in g.roofs.values():
        if g.levels[roof.level].z <= lv.z + 1e-9 and roof.status != "demolish":
            planes = tuple(Lin(p.a, p.b, p.c + roof.skin_of(p) - lv.z) for p in roof.planes)
            foot = roof.foot
            if grow > 0:
                grown = clean(foot.buffer(grow, join_style="mitre"))
                assert isinstance(grown, Polygon)
                foot = grown
            parts.append(Part(foot, planes))
    return Ceil((), tuple(parts))


def level_areas(d: Derived, lv: LevelGeo, groups: dict[str, int] | None) -> LevelAreas:
    g = d.arch
    out = outline(g, lv.id)
    voids = clean(_voids(g, lv.id).intersection(out))
    rooms: list[RoomPart] = []
    covered: list[BaseGeometry] = []
    for rg in g.rooms.values():
        if rg.level != lv.id:
            continue
        el = d.model[rg.id]
        assert isinstance(el, Room)
        fin = clean(rg.fin.difference(voids)) if not voids.is_empty else rg.fin
        stair = sum(
            s.poly.intersection(fin).area
            for s in g.stairs.values()
            if s.level == lv.id and s.status != "demolish"
        )
        part = RoomPart(rg.id, el.label or el.use, el.use, fin.area - stair, stair)
        if groups is not None:
            part.group = groups.get(el.use)
        rooms.append(part)
        covered.append(rg.poly)
    taken = union(covered)
    unassigned = sum(r.area for r in g.regions.get(lv.id, []) if r.difference(taken).area > 0.5)
    nrf = sum(r.area + r.stair for r in rooms)
    bri: float | None
    if lv.above is not None:
        h = g.levels[lv.above].z - lv.z
        bri = out.area * h
        heights = f"FFL {ar(lv.z)} bis FFL {lv.above} {ar(g.levels[lv.above].z)}"
    else:
        top = _top(g, lv)
        bri = top.volume(out) if top else None
        heights = f"FFL {ar(lv.z)} bis Oberkante Dachdeckung"
    if lv.below is None and bri is not None:
        slab = g.slab_on(lv.id)
        bottom = slab.ceiling if slab is not None else lv.ssl
        bri += out.area * (lv.z - bottom)
        heights = f"Unterkante Bodenkonstruktion {ar(bottom)}, " + heights
    la = LevelAreas(lv.id, out.area - voids.area, nrf, rooms, voids.area, unassigned, bri, heights)
    if groups is not None:
        for r in rooms:
            if r.group is not None:
                k = group_name(r.group)
                la.groups[k] = la.groups.get(k, 0.0) + r.area
        if any(r.stair for r in rooms):
            la.groups["VF"] = la.groups.get("VF", 0.0) + sum(r.stair for r in rooms)
    return la


def _groups(env: Env, d: Derived) -> dict[str, int] | None:
    """Room use to usage group from the office's table, or None when it is not installed."""
    if data.load(USES) is None:
        return None
    table = env.table(USES)
    out: dict[str, int] = {}
    for row in table.rows:
        n = row["group"]
        assert isinstance(n, float)
        if not n.is_integer() or not 1 <= n <= 9:
            raise ValueError(f"din277-uses: group {n:g} for {row['use']} is not 1 to 9")
        out[str(row["use"])] = int(n)
    used = {getattr(r, "use", "") for r in d.model.of_kind("room")}
    missing = sorted(used - set(out))
    if missing:
        raise ValueError(
            f"din277-uses has no group for the room uses {', '.join(missing)}; add a row each"
        )
    return out


def din277(d: Derived, scope: str | None, env: Env) -> Output:
    g = d.arch
    if scope is None:
        levels = g.level_order()
    elif scope in g.levels:
        levels = [scope]
    else:
        raise ValueError(f"scope {scope!r}: give a level or nothing for the whole project")
    groups = _groups(env, d)
    result = [level_areas(d, g.levels[k], groups) for k in levels]
    lines: list[str] = []
    ok = True
    for la in result:
        split = " · ".join(f"{k} {ar(v)}" for k, v in sorted(la.groups.items(), key=_order))
        s = f"{la.id} BGF {ar(la.bgf)} · NRF {ar(la.nrf)}"
        s += f" ({split})" if split else ""
        s += f" · KGF {ar(la.kgf)} · BRI {ar(la.bri) if la.bri is not None else '?'}"
        lines.append(s)
        if la.unassigned > 0:
            lines.append(f"  {la.id}: {ar(la.unassigned)} m² of floor has no room; counted as KGF")
        if la.bri is None:
            ok = False
            lines.append(f"  {la.id}: no roof over the top storey, so its BRI is unknown")
    total = {
        "bgf": sum(la.bgf for la in result),
        "nrf": sum(la.nrf for la in result),
        "kgf": sum(la.kgf for la in result),
    }
    bri = sum(la.bri for la in result if la.bri is not None)
    lines.append(
        f"BGF {ar(total['bgf'])} · NRF {ar(total['nrf'])} · KGF {ar(total['kgf'])} m²"
        f" · BRI {ar(bri)} m³" + ("" if ok else " (incomplete)")
    )
    if groups is None:
        lines.append(
            "NUF, TF and VF need the office's table din277-uses: uea data show din277-uses"
        )
    return Output(
        lines=lines,
        report=_report(d, result, total, bri, groups is not None),
        data={
            "total": {**{k: round(v, 4) for k, v in total.items()}, "bri": round(bri, 4)},
            "levels": [
                {
                    "id": la.id,
                    "bgf": round(la.bgf, 4),
                    "nrf": round(la.nrf, 4),
                    "kgf": round(la.kgf, 4),
                    "bri": round(la.bri, 4) if la.bri is not None else None,
                    "void": round(la.void, 4),
                    "unassigned": round(la.unassigned, 4),
                    "groups": {k: round(v, 4) for k, v in la.groups.items()},
                    "rooms": [
                        {
                            "id": r.id,
                            "use": r.use,
                            "group": r.group,
                            "nrf": round(r.area, 4),
                            "stair": round(r.stair, 4),
                        }
                        for r in la.rooms
                    ],
                }
                for la in result
            ],
        },
        inputs={"levels": levels},
        ok=ok,
    )


def _order(item: tuple[str, float]) -> tuple[int, str]:
    k = item[0]
    return ({"TF": 8, "VF": 9}.get(k, int(k[-1]) if k[-1].isdigit() else 10), k)


def _report(
    d: Derived, levels: list[LevelAreas], total: dict[str, float], bri: float, split: bool
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    out = [f"# Grundflächen und Rauminhalte nach DIN 277: {title}", ""]
    for la in levels:
        out += [f"## {la.id}", ""]
        rows: list[list[str]] = []
        for r in la.rooms:
            grp = group_name(r.group) if r.group is not None else "–"
            rows.append([f"{r.id} {r.name}", r.use, grp, de(r.area)])
            if r.stair:
                rows.append([f"{r.id} Treppe", "Treppe", "VF", de(r.stair)])
        out += [md_table(["Raum", "Nutzung", "Gruppe", "NRF m²"], rows, (3,)), ""]
        out.append(
            f"- BGF: {de(la.bgf)} m²" + (f" (ohne Luftraum {de(la.void)} m²)" if la.void else "")
        )
        out.append(f"- NRF: {de(la.nrf)} m²")
        for k, v in sorted(la.groups.items(), key=_order):
            out.append(f"  - {k}: {de(v)} m²")
        out.append(f"- KGF (BGF − NRF): {de(la.kgf)} m²")
        if la.unassigned:
            out.append(f"  - darin {de(la.unassigned)} m² Grundfläche ohne Raum im Modell")
        bri_s = f"{de(la.bri)} m³" if la.bri is not None else "nicht ermittelbar (kein Dach)"
        out += [f"- BRI: {bri_s} ({la.heights})", ""]
    out += [
        "## Summe",
        "",
        f"- BGF: {de(total['bgf'])} m²",
        f"- NRF: {de(total['nrf'])} m²",
        f"- KGF: {de(total['kgf'])} m²",
        f"- BRI: {de(bri)} m³",
        "",
        "## Verfahren",
        "",
        "- BGF je Grundrissebene: Umriss in den äußeren Maßen einschließlich Putz und Bekleidung;"
        " Lufträume (Deckenöffnungen der Ebene) zählen nicht.",
        "- NRF: Raumflächen zwischen den fertigen Oberflächen. Treppen zählen in der Ebene, in der"
        " sie beginnen, als Verkehrsfläche.",
        "- KGF = BGF − NRF: Wände mit Putz, Türöffnungen, Nischen, Installationsschächte.",
        "- BRI: BGF-Umriss je Ebene mal Höhe von Fußbodenoberfläche zu Fußbodenoberfläche; unterste"
        " Ebene ab Unterseite der Bodenkonstruktion (ohne Gründung), oberste bis Oberkante"
        " Dachdeckung.",
        "- Zuordnung der Nutzungen zu den Nutzungsgruppen: Tabelle din277-uses des Büros."
        if split
        else "- Die Aufteilung der NRF in NUF, TF und VF fehlt: die Tabelle din277-uses ist nicht"
        " installiert.",
        "",
        "## Nicht abgedeckt",
        "",
        "- Sonderfall der Raumumschließung (Balkone, Loggien, Terrassen): nicht im Modell.",
        "- Innenhöfe innerhalb eines Geschossumrisses werden wie umschlossen gerechnet.",
        "- Aufteilung nach lichter Raumhöhe.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


DIN277 = Calculator(
    name="din277",
    title="Areas and volumes per DIN 277 (BGF, NRF, KGF, BRI)",
    kind="norm",
    version=VERSION,
    fn=din277,
    norm=NORM,
    tables=(USES,),
)

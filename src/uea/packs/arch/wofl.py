"""Wohnfläche per Wohnflächenverordnung (WoFlV) of 25 November 2003.

A `norm` calculator. The WoFlV is a federal ordinance (an amtliches Werk), so its rules can be
implemented and cited freely. Clauses implemented here:

- §2 Abs. 3 Nr. 1: Zubehörräume (Keller, Waschküche, Bodenraum, Heizungsraum, Garage) do not
  count; taken from the room's use.
- §3 Abs. 1: Grundfläche between the finished surfaces (Vorderkante der Bekleidung): the
  room's Fertig outline.
- §3 Abs. 3 Nr. 2: stairs with more than three risers and their landings do not count.
- §3 Abs. 3 Nr. 3: Türnischen do not count (rooms end at the wall face).
- §3 Abs. 3 Nr. 4: niches count only if they reach the floor and are deeper than 0.13 m.
- §4 Nr. 1 and 2: parts with a clear height of 2 m or more count fully, from 1 m to under
  2 m half, under 1 m not at all.
- A void in the floor (stair hole) is no floor area (§3 Abs. 1).

Not covered yet: §3 Abs. 3 Nr. 1 (chimneys, pillars, Vormauerungen), §4 Nr. 3 and 4
(Wintergärten, balconies, terraces). Rooms of those kinds are not in the model yet.
"""

from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

from uea.calc import Calculator, Output
from uea.derive import Derived
from uea.fmt import ar
from uea.geom import clean, union
from uea.packs.arch.geometry import RoomGeo
from uea.packs.arch.kinds import Niche, Room

VERSION = "0.1.0"
NORM = "WoFlV vom 25.11.2003"

EXCLUDED: dict[str, str] = {
    "cellar": "Kellerraum, §2 Abs. 3 Nr. 1 a",
    "laundry": "Waschküche, §2 Abs. 3 Nr. 1 c",
    "attic": "Bodenraum, §2 Abs. 3 Nr. 1 d",
    "technical": "Heizungsraum, §2 Abs. 3 Nr. 1 f",
    "garage": "Garage, §2 Abs. 3 Nr. 1 g",
}
NICHE_MIN_DEPTH = 0.13


@dataclass
class RoomArea:
    id: str
    name: str
    level: str
    use: str
    grund: float = 0.0
    """Fertig outline area, §3 Abs. 1."""
    minus: list[tuple[str, float, str]] = field(default_factory=list[tuple[str, float, str]])
    plus: list[tuple[str, float, str]] = field(default_factory=list[tuple[str, float, str]])
    full: float = 0.0
    half: float = 0.0
    low: float = 0.0
    excluded: str | None = None
    no_ceiling: bool = False

    @property
    def net(self) -> float:
        return self.grund - sum(a for _, a, _ in self.minus) + sum(a for _, a, _ in self.plus)

    @property
    def wofl(self) -> float:
        if self.excluded:
            return 0.0
        return self.full + 0.5 * self.half


def room_area(d: Derived, rg: RoomGeo) -> RoomArea:
    g = d.arch
    el = d.model[rg.id]
    assert isinstance(el, Room)
    ra = RoomArea(rg.id, el.label or el.use, rg.level, el.use)
    ra.grund = rg.area_fin
    if el.use in EXCLUDED:
        ra.excluded = EXCLUDED[el.use]
        return ra
    cut: list[BaseGeometry] = []
    for s in g.stairs.values():
        if s.level != rg.level or s.n <= 3 or s.status == "demolish":
            continue
        a = s.poly.intersection(rg.fin).area
        if a > 1e-6:
            ra.minus.append((f"Treppe {s.id}", a, "§3 Abs. 3 Nr. 2"))
            cut.append(s.poly)
    slab = g.slab_on(rg.level)
    for v in g.voids.values():
        if slab is None or v.slab != slab.id:
            continue
        rest = v.poly.difference(union(cut)) if cut else v.poly
        a = rest.intersection(rg.fin).area
        if a > 1e-6:
            ra.minus.append((f"Deckenöffnung {v.id}", a, "§3 Abs. 1"))
            cut.append(v.poly)
    net = clean(rg.fin.difference(union(cut))) if cut else rg.fin
    if not rg.ceiling:
        ra.no_ceiling = True
        return ra
    a2 = rg.ceiling.at_least(net, 2.0).area
    a1 = rg.ceiling.at_least(net, 1.0).area
    ra.full, ra.half, ra.low = a2, a1 - a2, net.area - a1
    for o in g.openings.values():
        if o.kind != "niche" or rg.id not in o.sides or o.status == "demolish":
            continue
        side_room = o.sides[1] if o.face == "hi" else o.sides[0]
        if side_room != rg.id:
            continue
        ni = d.model[o.id]
        assert isinstance(ni, Niche)
        if o.sill <= 1e-6 and o.depth > NICHE_MIN_DEPTH:
            a = o.width * o.depth
            ra.plus.append((f"Nische {o.id}", a, "§3 Abs. 3 Nr. 4"))
            h = o.top
            if h >= 2.0:
                ra.full += a
            elif h >= 1.0:
                ra.half += a
            else:
                ra.low += a
    return ra


def _scope_rooms(d: Derived, scope: str | None) -> list[RoomGeo]:
    g = d.arch
    m = d.model
    if scope is None:
        ids = [r.id for r in m.of_kind("room")]
    elif scope in g.levels:
        ids = [r.id for r in m.of_kind("room") if isinstance(r, Room) and r.level.id == scope]
    elif scope in m and m[scope].kind == "room":
        ids = [scope]
    else:
        raise ValueError(f"scope {scope!r}: give a level, a room or nothing for the whole project")
    missing = [i for i in ids if i not in g.rooms]
    if missing:
        raise ValueError(
            f"rooms {' '.join(missing)} have no outline; fix them first (uea check arch)"
        )
    return [g.rooms[i] for i in ids]


def wofl(d: Derived, scope: str | None) -> Output:
    rooms = [room_area(d, rg) for rg in _scope_rooms(d, scope)]
    problems = [r.id for r in rooms if r.no_ceiling and not r.excluded]
    if problems:
        raise ValueError(
            f"{' '.join(problems)}: no ceiling (no storey or roof above), so the clear height"
            " per §4 is unknown"
        )
    lines: list[str] = []
    for r in rooms:
        if r.excluded:
            lines.append(f"{r.id} {r.name}: not counted ({r.use}: {r.excluded})")
            continue
        s = f"{r.id} {r.name} {ar(r.grund)}"
        for what, a, _ in r.minus:
            s += f" -{what.split()[-1]} {ar(a)}"
        for what, a, _ in r.plus:
            s += f" +{what.split()[-1]} {ar(a)}"
        if r.half > 1e-6 or r.low > 1e-6:
            s += f" | {ar(r.full)} full + {ar(r.half)}/2 (1-2 m)"
            if r.low > 1e-6:
                s += f", {ar(r.low)} under 1 m"
        if r.minus or r.plus or r.half > 1e-6 or r.low > 1e-6:
            s += f" = {ar(r.wofl)}"
        lines.append(s)
    levels: dict[str, float] = {}
    for r in rooms:
        levels[r.level] = levels.get(r.level, 0.0) + r.wofl
    total = sum(levels.values())
    lines.append(
        " · ".join(f"{k} {ar(v)}" for k, v in levels.items()) + f" · Wohnfläche {ar(total)} m²"
    )
    return Output(
        lines=lines,
        report=_report(d, rooms, levels, total),
        data={
            "total": round(total, 4),
            "levels": {k: round(v, 4) for k, v in levels.items()},
            "rooms": [
                {
                    "id": r.id,
                    "name": r.name,
                    "level": r.level,
                    "use": r.use,
                    "grund": round(r.grund, 4),
                    "minus": [{"what": w, "area": round(a, 4), "rule": c} for w, a, c in r.minus],
                    "plus": [{"what": w, "area": round(a, 4), "rule": c} for w, a, c in r.plus],
                    "full": round(r.full, 4),
                    "half": round(r.half, 4),
                    "low": round(r.low, 4),
                    "excluded": r.excluded,
                    "wofl": round(r.wofl, 4),
                }
                for r in rooms
            ],
        },
        inputs={"rooms": [r.id for r in rooms]},
    )


def _report(d: Derived, rooms: list[RoomArea], levels: dict[str, float], total: float) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    out = [f"# Wohnflächenberechnung nach WoFlV: {title}", ""]
    out += [
        "| Raum | Geschoss | Grundfläche (Fertigmaß) | Abzüge und Zuschläge"
        " | lichte Höhe ≥ 2 m | 1–2 m (½) | < 1 m | Wohnfläche |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]

    def de(v: float) -> str:
        return f"{v:.2f}".replace(".", ",")

    for r in rooms:
        if r.excluded:
            out.append(
                f"| {r.id} {r.name} | {r.level} | {de(r.grund)}"
                f" | nicht angerechnet: {r.excluded} | | | | 0,00 |"
            )
            continue
        adj = "; ".join(
            [f"− {w} {de(a)} ({c})" for w, a, c in r.minus]
            + [f"+ {w} {de(a)} ({c})" for w, a, c in r.plus]
        )
        out.append(
            f"| {r.id} {r.name} | {r.level} | {de(r.grund)} | {adj} | {de(r.full)} | {de(r.half)} |"
            f" {de(r.low)} | {de(r.wofl)} |"
        )
    out.append("")
    for k, v in levels.items():
        out.append(f"- {k}: {de(v)} m²")
    out.append(f"- **Wohnfläche gesamt: {de(total)} m²**")
    out += [
        "",
        "## Angewandte Regeln",
        "",
        "- §3 Abs. 1: Grundfläche nach den lichten Maßen ab Vorderkante der Bekleidung"
        " (Fertigmaß: Rohbaumaß abzüglich der Putz- und Bekleidungsschichten der Wandtypen).",
        "- §3 Abs. 3 Nr. 2: Treppen mit über drei Steigungen und deren Podeste werden abgezogen;"
        " Deckenöffnungen über Treppen sind keine Grundfläche.",
        "- §3 Abs. 3 Nr. 3: Türnischen bleiben außer Betracht (Raumgrenze ist die Wandoberfläche).",
        "- §3 Abs. 3 Nr. 4: Nischen werden nur angerechnet, wenn sie bis zum Fußboden reichen und"
        " tiefer als 0,13 m sind.",
        "- §4 Nr. 1 und 2: lichte Höhe ≥ 2 m voll, 1 m bis unter 2 m zur Hälfte, unter 1 m nicht.",
        "- §2 Abs. 3 Nr. 1: Zubehörräume (Keller, Waschküche, Bodenraum, Heizungsraum, Garage)"
        " gehören nicht zur Wohnfläche; maßgeblich ist die Nutzung des Raums im Modell.",
        "",
        "## Nicht abgedeckt",
        "",
        "- §3 Abs. 3 Nr. 1 (Schornsteine, Vormauerungen, freistehende Pfeiler und Säulen) und"
        " §4 Nr. 3 und 4 (Wintergärten, Schwimmbäder, Balkone, Loggien, Dachgärten, Terrassen):"
        " solche Bauteile und Räume enthält das Modell noch nicht.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


WOFL = Calculator(
    name="wofl",
    title="Wohnfläche per WoFlV",
    kind="norm",
    version=VERSION,
    fn=wofl,
    norm=NORM,
)

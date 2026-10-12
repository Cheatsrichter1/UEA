"""The positions of the structure (decision 0040): every member that the Statische Berechnung
proves, numbered as the Positionsplan shows them. Derived from the model alone, so the plan and
the calculation always agree.

Groups by storey from the top: group k holds the roofs on the k-th storey from the top with
their rafters, the slab above it and the beams under that slab, its load-bearing walls and the
lintels over their openings, its columns and its bracing; the last group holds the strip
footings under the lowest storey's walls and the pad footings under its columns. Each position
is drawn on the floor plan of the storey it is in (a slab and its beams on the plan of the
storey below it).
"""

from dataclasses import dataclass

from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.arch.geometry import ArchGeo, OpeningGeo
from uea.packs.struct.model import beams_of, bearing, columns_of, lowest

TITLE = {
    "roof": "Dach",
    "rafter": "Sparren",
    "slab": "Decke",
    "beam": "Unterzug",
    "wall": "Wand",
    "lintel": "Sturz",
    "footing": "Streifenfundament",
    "column": "Stütze",
    "pad": "Einzelfundament",
    "bracing": "Aussteifung",
}


@dataclass(frozen=True)
class Pos:
    no: str
    """1.01"""
    kind: str
    id: str
    """The element: rf1, sl2, bm1, w8, f7 (a lintel by its opening), w1 (a footing by its wall)."""
    sheet: str
    """The storey whose plan shows it."""

    @property
    def title(self) -> str:
        return f"{TITLE[self.kind]} {self.id}"


def lintel_openings(g: ArchGeo, wall: str) -> list[OpeningGeo]:
    """The openings of a wall that need a lintel: doors, windows, and holes through it that are
    not round (a core drilling needs none)."""
    out = [o for o in g.openings.values() if o.host == wall and o.kind in ("door", "win")]
    for h in g.holes.values():
        if h.wall is not None and h.host == wall and h.wall.face is None and not h.round:
            out.append(h.wall)
    return sorted(out, key=lambda o: (o.lo, natural(o.id)))


def rafters_of(d: Derived, roof: str) -> list[str]:
    return sorted(
        (el.id for el in d.model.of_kind("rafter") if getattr(el, "roof").id == roof),  # noqa: B009
        key=natural,
    )


def positions(d: Derived) -> list[Pos]:
    g = d.arch
    sg = getattr(d, "struct", None)
    order = g.level_order()
    first = lowest(g)
    out: list[Pos] = []
    for k, lv in enumerate(reversed(order), start=1):
        items: list[tuple[str, str]] = []
        for r in sorted(g.roofs_on(lv), key=lambda r: natural(r.id)):
            items.append(("roof", r.id))
            items += [("rafter", k) for k in rafters_of(d, r.id)]
        above = g.levels[lv].above
        if above is not None:
            sl = g.slab_on(above)
            if sl is not None:
                items.append(("slab", sl.id))
            items += [("beam", b.id) for b in beams_of(sg, above)]
        walls = bearing(g, lv)
        items += [("wall", w.id) for w in walls]
        for w in walls:
            items += [("lintel", o.id) for o in lintel_openings(g, w.id)]
        items += [("column", c.id) for c in columns_of(sg, lv)]
        if walls:
            items.append(("bracing", lv))
        out += [Pos(f"{k}.{j:02d}", kind, key, lv) for j, (kind, key) in enumerate(items, 1)]
    if first is not None:
        k = len(order) + 1
        last: list[tuple[str, str]] = [("footing", w.id) for w in bearing(g, first)]
        last += [("pad", c.id) for c in columns_of(sg, first)]
        out += [Pos(f"{k}.{j:02d}", kind, key, first) for j, (kind, key) in enumerate(last, 1)]
    return out

"""The structural model as the architecture gives it (decision 0040): which load-bearing walls
carry each slab and each wall above them. Load-bearing is the wall's lb flag; a slab rests on the
load-bearing walls of the storey below it that its outline covers; a wall stands on the
load-bearing walls of the storey below whose cores its own core overlaps."""

from shapely.geometry.base import BaseGeometry

from uea.core.registry import natural
from uea.packs.arch.geometry import ArchGeo, SlabGeo, WallGeo

TOUCH = 1e-3
"""A slab rests on a wall whose core comes this close to its outline (m)."""
MIN_OVERLAP = 1e-4
"""Cores that overlap by less than this (m²) only touch at a corner."""


def lowest(g: ArchGeo) -> str | None:
    order = g.level_order()
    return order[0] if order else None


def bearing(g: ArchGeo, level: str) -> list[WallGeo]:
    """The active load-bearing walls of a storey, by id."""
    return sorted((w for w in g.walls_on(level) if w.lb), key=lambda w: natural(w.id))


def slab_supports(g: ArchGeo, sl: SlabGeo) -> list[WallGeo]:
    """The load-bearing walls under a slab: on the storey below the one it carries."""
    below = g.levels[sl.level].below
    if below is None:
        return []
    area: BaseGeometry = sl.net.buffer(TOUCH)
    return [w for w in bearing(g, below) if w.core.intersects(area)]


def stands_on(g: ArchGeo, w: WallGeo) -> list[tuple[WallGeo, float]]:
    """The load-bearing walls of the storey below that a wall stands on, each with its share of
    the overlap of the cores."""
    below = g.levels[w.level].below
    if below is None:
        return []
    hits = [(o, w.core.intersection(o.core).area) for o in bearing(g, below)]
    hits = [(o, a) for o, a in hits if a > MIN_OVERLAP]
    total = sum(a for _, a in hits)
    return [(o, a / total) for o, a in hits]

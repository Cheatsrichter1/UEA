"""The structural model (decision 0040): which supports carry each slab, each wall and each beam.

Load-bearing is the wall's lb flag. A slab rests on the load-bearing walls of the storey below
it that its outline covers, and on the beams under it (`beam`, struct.uea). A wall stands on the
load-bearing walls of the storey below whose cores its own core overlaps, and on the beams of its
storey that run inside its core. A beam rests on the load-bearing walls of the storey below that
it crosses.
"""

from dataclasses import dataclass

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from uea.core.registry import natural
from uea.packs.arch.geometry import ArchGeo, SlabGeo, WallGeo
from uea.packs.struct.geometry import BeamGeo, StructGeo

TOUCH = 1e-3
"""A slab rests on a wall whose core comes this close to its outline (m)."""
MIN_OVERLAP = 1e-4
"""Cores that overlap by less than this (m²) only touch at a corner."""
MIN_BEARING = 0.05
"""A beam crossing a wall over less than this (m) does not rest on it."""


@dataclass(frozen=True)
class Support:
    """What carries a slab or a wall: a load-bearing wall below, or a beam."""

    id: str
    kind: str
    """wall or beam."""
    shape: BaseGeometry
    """The wall's core, or the beam's axis."""


def lowest(g: ArchGeo) -> str | None:
    order = g.level_order()
    return order[0] if order else None


def bearing(g: ArchGeo, level: str) -> list[WallGeo]:
    """The active load-bearing walls of a storey, by id."""
    return sorted((w for w in g.walls_on(level) if w.lb), key=lambda w: natural(w.id))


def beams_of(sg: StructGeo | None, level: str) -> list[BeamGeo]:
    if sg is None:
        return []
    return sorted((b for b in sg.beams.values() if b.level == level), key=lambda b: natural(b.id))


def slab_supports(g: ArchGeo, sl: SlabGeo, sg: StructGeo | None = None) -> list[Support]:
    """The load-bearing walls under a slab, on the storey below the one it carries, and the
    beams under it."""
    below = g.levels[sl.level].below
    if below is None:
        return []
    area: BaseGeometry = sl.net.buffer(TOUCH)
    out = [Support(w.id, "wall", w.core) for w in bearing(g, below) if w.core.intersects(area)]
    out += [
        Support(b.id, "beam", b.line) for b in beams_of(sg, sl.level) if b.line.intersects(area)
    ]
    return out


def stands_on(g: ArchGeo, w: WallGeo, sg: StructGeo | None = None) -> list[tuple[str, float]]:
    """The supports a wall stands on, each with its share: the length of the wall's axis over it
    (a wall below: the overlap of the cores across the wall's thickness; a beam: its axis inside
    the wall's core)."""
    below = g.levels[w.level].below
    if below is None:
        return []
    hits: list[tuple[str, float]] = []
    for o in bearing(g, below):
        a = w.core.intersection(o.core).area
        if a > MIN_OVERLAP:
            hits.append((o.id, a / w.t))
    core = w.core.buffer(TOUCH)
    for b in beams_of(sg, w.level):
        length = free_span(g, b).intersection(core).length
        if length > MIN_BEARING:
            hits.append((b.id, length))
    total = sum(x for _, x in hits)
    return [(k, x / total) for k, x in hits]


def free_span(g: ArchGeo, b: BeamGeo) -> BaseGeometry:
    """The beam's axis between its bearings: the part not inside a wall it rests on (a wall
    over its bearing stands on that wall, not on the beam)."""
    below = g.levels[b.level].below
    if below is None:
        return b.line
    cores = [w.core for w in bearing(g, below)]
    out: BaseGeometry = b.line
    for c in cores:
        out = out.difference(c)
    return out


def on_beam(g: ArchGeo, w: WallGeo, b: BeamGeo) -> tuple[float, float]:
    """Where along the beam a wall standing on it lies: from s0 to s1."""
    seg = free_span(g, b).intersection(w.core.buffer(TOUCH))
    pts = [b.s_of(x, y) for x, y in _coords(seg)]
    return (min(pts), max(pts))


def beam_bearings(g: ArchGeo, b: BeamGeo) -> list[tuple[str, float]]:
    """The load-bearing walls of the storey below the beam's that it rests on, each with the
    point along the beam where it bears (the middle of its bearing), from a to b."""
    below = g.levels[b.level].below
    if below is None:
        return []
    out: list[tuple[str, float]] = []
    for w in bearing(g, below):
        seg = b.line.intersection(w.core.buffer(TOUCH))
        if seg.is_empty or seg.length < MIN_BEARING:
            continue
        pts = [b.s_of(x, y) for x, y in _coords(seg)]
        out.append((w.id, (min(pts) + max(pts)) / 2))
    return sorted(out, key=lambda x: x[1])


def _coords(geom: BaseGeometry) -> list[tuple[float, float]]:
    if isinstance(geom, LineString):
        return [(float(x), float(y)) for x, y in geom.coords]
    out: list[tuple[float, float]] = []
    for part in getattr(geom, "geoms", []):
        out += _coords(part)
    return out

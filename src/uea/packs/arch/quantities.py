"""Quantities of architectural elements: what the tables and the LV count.

A wall's net elevation area and core volume, the sloped area of a roof.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from uea.packs.arch.geometry import ArchGeo, WallGeo, roof_pieces


def wall_profile(w: WallGeo) -> list[tuple[float, float]] | None:
    """Height of the wall above its bottom along its run, at every break of the top."""
    if not w.top:
        return None
    ss = sorted({w.s0, w.s1, *(s for s, _ in w.top if w.s0 < s < w.s1)})
    out: list[tuple[float, float]] = []
    for s in ss:
        z = w.top_at(s)
        assert z is not None
        out.append((s, z - w.bottom))
    return out


@dataclass
class WallQty:
    gross: float | None
    """Elevation area between the wall ends, under the top profile."""
    openings: float
    """Doors and windows, in structural sizes."""
    net: float | None
    volume: float | None
    """Core volume: net area times core thickness."""
    h_min: float | None
    h_max: float | None


def wall_qty(g: ArchGeo, w: WallGeo) -> WallQty:
    holes = sum(
        (o.hi - o.lo) * (o.top - o.sill)
        for o in g.openings.values()
        if o.host == w.id and o.kind != "niche"
    )
    prof = wall_profile(w)
    if prof is None:
        return WallQty(None, holes, None, None, None, None)
    gross = sum((b - a) * (ha + hb) / 2 for (a, ha), (b, hb) in pairwise(prof))
    net = gross - holes
    return WallQty(
        gross,
        holes,
        net,
        net * (w.hi - w.lo),
        min(h for _, h in prof),
        max(h for _, h in prof),
    )


def roof_areas(g: ArchGeo, levels: Iterable[str] | None = None) -> dict[str, float]:
    """Sloped area of each roof of the given storeys (all if None), including its overhangs."""
    out: dict[str, float] = defaultdict(float)
    for lv in g.level_order() if levels is None else levels:
        ids = [rf.id for rf in g.roofs_on(lv)]
        if not ids:
            continue
        for i, plane, poly in roof_pieces(g, lv):
            out[ids[i]] += poly.area * (1 + plane.a**2 + plane.b**2) ** 0.5
    return dict(out)

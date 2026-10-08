"""Stair layouts: the flights, the landing or the winders of a stair in the stair's own frame.

The frame has p along the first flight and q across it. The first flight covers q = 0..w and
the stair turns toward +q. Treads are numbered from the lower floor: tread i lies i risers up.
A stair of n risers has n-1 treads (the upper floor is the last one). A landing is one tread
and m winders are m treads in the turn (`docs/decisions/0019-stair-shapes.md`).
"""

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

Pt = tuple[float, float]


@dataclass(frozen=True, slots=True)
class LFlight:
    poly: Polygon
    start: Pt
    """Middle of the edge the flight starts on."""
    climb: Pt
    risers: int
    tread0: int
    """The flight starts on this tread (0: the lower floor)."""


@dataclass(frozen=True, slots=True)
class Layout:
    poly: Polygon
    flights: list[LFlight]
    turn: list[tuple[Polygon, int]]
    """The treads of the landing or winders: polygon and tread number."""
    lines: list[LineString]
    """Edges between treads, for the plan."""
    walk: list[Pt]
    """Walking line, up the middle."""


def _one(parts: list[Polygon]) -> Polygon:
    g = unary_union(parts)
    assert isinstance(g, Polygon)
    return g


def layout(
    shape: str, n: int, tread: float, w: float, n1: int | None, winders: int | None, gap: float
) -> Layout:
    t = tread
    if shape == "straight":
        run = (n - 1) * t
        poly = box(0.0, 0.0, run, w)
        return Layout(
            poly,
            [LFlight(poly, (0.0, w / 2), (1.0, 0.0), n, 0)],
            [],
            [LineString([(i * t, 0.0), (i * t, w)]) for i in range(1, n - 1)],
            [(0.0, w / 2), (run, w / 2)],
        )
    m = winders or 1
    first = n1 if n1 is not None else (n - m + 1) // 2
    a1 = (first - 1) * t
    count2 = n - first - m
    a2 = count2 * t
    f1 = box(0.0, 0.0, a1, w)
    lines = [LineString([(i * t, 0.0), (i * t, w)]) for i in range(1, first)]
    flight1 = LFlight(f1, (0.0, w / 2), (1.0, 0.0), first, 0)
    if shape == "l":
        square = box(a1, 0.0, a1 + w, w)
        f2 = box(a1, w, a1 + w, w + a2)
        flight2 = LFlight(f2, (a1 + w / 2, w), (0.0, 1.0), count2 + 1, first + m - 1)
        lines += [LineString([(a1, w + j * t), (a1 + w, w + j * t)]) for j in range(count2)]
        turn, rays = _turn(square, (a1, w), w, first, m)
        walk = [(0.0, w / 2), (a1 + w / 2, w / 2), (a1 + w / 2, w + a2)]
        return Layout(_one([f1, square, f2]), [flight1, flight2], turn, lines + rays, walk)
    square = box(a1, 0.0, a1 + w, 2 * w + gap)
    f2 = box(a1 - a2, w + gap, a1, 2 * w + gap)
    flight2 = LFlight(f2, (a1, w + gap + w / 2), (-1.0, 0.0), count2 + 1, first)
    lines += [LineString([(a1 - j * t, w + gap), (a1 - j * t, 2 * w + gap)]) for j in range(count2)]
    well = box(max(0.0, a1 - a2), w, a1, w + gap)
    walk = [(0.0, w / 2), (a1 + w / 2, w / 2), (a1 + w / 2, w + gap + w / 2)]
    walk.append((a1 - a2, w + gap + w / 2))
    return Layout(_one([f1, square, f2, well]), [flight1, flight2], [(square, first)], lines, walk)


def _turn(
    square: Polygon, apex: Pt, w: float, first: int, m: int
) -> tuple[list[tuple[Polygon, int]], list[LineString]]:
    """The treads of the quarter turn: a landing, or m winders fanned out from the inner corner."""
    if m == 1:
        return [(square, first)], []
    dirs = [
        (math.sin(math.radians(90.0 * j / m)), -math.cos(math.radians(90.0 * j / m)))
        for j in range(m + 1)
    ]
    reach = 3 * w
    treads: list[tuple[Polygon, int]] = []
    for j in range(1, m + 1):
        (ax, ay), (bx, by) = dirs[j - 1], dirs[j]
        wedge = Polygon(
            [
                apex,
                (apex[0] + reach * ax, apex[1] + reach * ay),
                (apex[0] + reach * bx, apex[1] + reach * by),
            ]
        )
        piece = square.intersection(wedge)
        assert isinstance(piece, Polygon)
        treads.append((piece, first + j - 1))
    rays: list[LineString] = []
    for dx, dy in dirs[1:-1]:
        dist = min(w / dx if dx > 1e-9 else math.inf, w / -dy if -dy > 1e-9 else math.inf)
        rays.append(LineString([apex, (apex[0] + dist * dx, apex[1] + dist * dy)]))
    return treads, rays

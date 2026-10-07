"""Small 2D helpers on top of Shapely: rectangles, half-planes and linear height fields."""

from collections.abc import Iterable
from dataclasses import dataclass

import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import split, unary_union

GRID = 1e-6
"""Coordinates are snapped to a micrometre so faces computed twice coincide."""
MIN_AREA = 1e-4
"""Regions smaller than 1 cm² are slivers, not rooms."""


def r(v: float) -> float:
    return round(v, 6) + 0.0


def rect(x0: float, x1: float, y0: float, y1: float) -> Polygon:
    return box(r(min(x0, x1)), r(min(y0, y1)), r(max(x0, x1)), r(max(y0, y1)))


def polys(g: BaseGeometry | None, min_area: float = MIN_AREA) -> list[Polygon]:
    """The polygons in a geometry, without slivers."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area >= min_area else []
    out: list[Polygon] = []
    for part in getattr(g, "geoms", []):
        out.extend(polys(part, min_area))
    return out


def union(gs: Iterable[BaseGeometry]) -> BaseGeometry:
    items = [g for g in gs if not g.is_empty]
    if not items:
        return Polygon()
    return clean(unary_union(items))


def clean(g: BaseGeometry) -> BaseGeometry:
    out: BaseGeometry = shapely.set_precision(g, GRID)  # pyright: ignore[reportUnknownMemberType]
    return out


def filled(g: BaseGeometry) -> BaseGeometry:
    """Each polygon without its holes: the outline a set of walls encloses."""
    return union(Polygon(p.exterior) for p in polys(g, 0.0))


def split_by(regions: list[Polygon], line: LineString) -> list[Polygon]:
    out: list[Polygon] = []
    for p in regions:
        if p.intersects(line):
            out.extend(polys(split(p, line)))
        else:
            out.append(p)
    return out


def extend(line: LineString, d: float) -> LineString:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    length = line.length or 1.0
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    return LineString([(x0 - ux * d, y0 - uy * d), (x1 + ux * d, y1 + uy * d)])


@dataclass(frozen=True, slots=True)
class Lin:
    """A linear function of plan position: a*x + b*y + c."""

    a: float
    b: float
    c: float

    def __call__(self, x: float, y: float) -> float:
        return self.a * x + self.b * y + self.c

    def __sub__(self, o: "Lin") -> "Lin":
        return Lin(self.a - o.a, self.b - o.b, self.c - o.c)

    def minus(self, h: float) -> "Lin":
        return Lin(self.a, self.b, self.c - h)

    @property
    def flat(self) -> bool:
        return abs(self.a) < 1e-12 and abs(self.b) < 1e-12


def halfplane(g: BaseGeometry, f: Lin) -> BaseGeometry:
    """The part of g where f >= 0."""
    if g.is_empty:
        return g
    if f.flat:
        return g if f.c >= -1e-9 else Polygon()
    x0, y0, x1, y1 = g.bounds
    m = 1.0
    pts = [(x0 - m, y0 - m), (x1 + m, y0 - m), (x1 + m, y1 + m), (x0 - m, y1 + m)]
    clipped: list[tuple[float, float]] = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        fp, fq = f(*p), f(*q)
        if fp >= 0:
            clipped.append(p)
        if (fp >= 0) != (fq >= 0):
            t = fp / (fp - fq)
            clipped.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    if len(clipped) < 3:
        return Polygon()
    return clean(g.intersection(Polygon(clipped)))


def lower_envelope_regions(g: BaseGeometry, fs: list[Lin]) -> list[tuple[Lin, BaseGeometry]]:
    """Split g into the regions where each f is the smallest of fs."""
    out: list[tuple[Lin, BaseGeometry]] = []
    for i, f in enumerate(fs):
        part = g
        for j, o in enumerate(fs):
            if i == j:
                continue
            # f <= o, ties go to the lower index
            diff = o - f if j > i else (o - f).minus(1e-9)
            part = halfplane(part, diff)
            if part.is_empty:
                break
        if not part.is_empty and part.area > 0:
            out.append((f, part))
    return out


def min_field_at_least(g: BaseGeometry, fs: list[Lin], h: float) -> BaseGeometry:
    """The part of g where min(fs) >= h."""
    part = g
    for f in fs:
        part = halfplane(part, f.minus(h))
    return part


def integrate_min(g: BaseGeometry, fs: list[Lin]) -> float:
    """Integral of max(0, min(fs)) over g (exact for linear pieces)."""
    pos = min_field_at_least(g, fs, 0.0)
    total = 0.0
    for f, part in lower_envelope_regions(pos, fs):
        c = part.centroid
        total += part.area * f(c.x, c.y)
    return total


__all__ = [
    "LineString",
    "MultiPolygon",
    "Polygon",
    "box",
]

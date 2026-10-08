"""Small 2D helpers on top of Shapely: rectangles, half-planes and linear height fields."""

import math
from collections.abc import Iterable, Sequence
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
    # a corner exactly on the line is added twice: drop repeats, or the clip polygon is invalid
    pts = [c for i, c in enumerate(clipped) if math.dist(c, clipped[i - 1]) > 1e-9]
    if len(pts) < 3:
        return Polygon()
    return clean(g.intersection(Polygon(pts)))


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


@dataclass(frozen=True, slots=True)
class Part:
    """A height field that exists over `foot` and is the lowest of its planes."""

    foot: Polygon
    planes: tuple[Lin, ...]

    def at(self, x: float, y: float) -> float:
        return min(p(x, y) for p in self.planes)


Piece = tuple[Lin, Polygon]
"""A polygon over which a height field is the plane `Lin`."""


def part_pieces(part: Part, g: BaseGeometry) -> list[Piece]:
    region = clean(g.intersection(part.foot))
    if region.is_empty:
        return []
    return [
        (f, p) for f, geo in lower_envelope_regions(region, list(part.planes)) for p in polys(geo)
    ]


def union_pieces(parts: Sequence[Part], g: BaseGeometry) -> list[tuple[int, Lin, Polygon]]:
    """Pieces of the highest of the parts over g, each part only where it exists.

    Each piece comes with the index of its part. Where two planes are equal, the part listed
    first wins.
    """
    per = [part_pieces(p, g) for p in parts]
    out: list[tuple[int, Lin, Polygon]] = []
    for i, mine in enumerate(per):
        for f, poly in mine:
            rest: BaseGeometry = poly
            for j, theirs in enumerate(per):
                if i == j:
                    continue
                margin = -1e-7 if j < i else 1e-7
                for f2, poly2 in theirs:
                    if rest.is_empty:
                        break
                    beaten = halfplane(clean(rest.intersection(poly2)), (f2 - f).minus(margin))
                    if not beaten.is_empty and beaten.area > 0:
                        rest = clean(rest.difference(beaten))
            out.extend((i, f, p) for p in polys(rest))
    return out


@dataclass(frozen=True, slots=True)
class Ceil:
    """Clear height above the FFL: the lowest of the caps and of the highest roof part.

    A cap is a plane that holds everywhere (the slab above). Roof parts hold where they exist;
    where several overlap, the highest counts (valleys and hips of a roof with wings).
    """

    caps: tuple[Lin, ...] = ()
    parts: tuple[Part, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.caps or self.parts)

    def pieces(self, g: BaseGeometry) -> list[Piece]:
        if g.is_empty or not self:
            return []
        out: list[Piece] = []
        outside = g
        if self.parts:
            cover = union(p.foot for p in self.parts)
            for _, f, poly in union_pieces(self.parts, clean(g.intersection(cover))):
                fs = [f, *self.caps]
                out.extend(
                    (h, p) for h, geo in lower_envelope_regions(poly, fs) for p in polys(geo)
                )
            outside = clean(g.difference(cover))
        if self.caps and not outside.is_empty:
            fs = list(self.caps)
            out.extend((h, p) for h, geo in lower_envelope_regions(outside, fs) for p in polys(geo))
        return out

    def flat(self, g: BaseGeometry) -> bool:
        return all(f.flat for f, _ in self.pieces(g))

    def at_least(self, g: BaseGeometry, h: float) -> BaseGeometry:
        """The part of g where the clear height is h or more."""
        return union(halfplane(p, f.minus(h)) for f, p in self.pieces(g))

    def height_range(self, g: BaseGeometry) -> tuple[float, float] | None:
        vals: list[float] = []
        for f, p in self.pieces(g):
            vals.extend(f(x, y) for x, y in p.exterior.coords)
        if not vals:
            return None
        return (max(min(vals), 0.0), max(vals))

    def volume(self, g: BaseGeometry) -> float:
        total = 0.0
        for f, p in self.pieces(g):
            for q in polys(halfplane(p, f), 0.0):
                c = q.centroid
                total += q.area * f(c.x, c.y)
        return total


__all__ = [
    "LineString",
    "MultiPolygon",
    "Polygon",
    "box",
]

"""Architecture geometry derived from intent.

Walls, openings, stairs and separators are resolved from their positions (anchor±distance,
spans). Slabs take their outline from the walls below, roofs from their storey's outline.
Rooms are the regions around their seed points, bounded by walls and separators; finished
sizes subtract the finish layers of the walls. Heights come from the slab or roof above.

Coordinates are global plan metres; heights (`z`, `bottom`, `top` of walls, roof planes) are
absolute metres relative to ±0.00. Opening sills and tops are relative to the storey's FFL.
"""

import math
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as SPoint
from shapely.geometry.base import BaseGeometry

from uea.core.model import Model
from uea.core.registry import natural
from uea.core.schema import Element
from uea.core.values import Anchor, Layers, Span
from uea.derive import Derived, GeoError, Unresolved
from uea.fmt import ar, ln
from uea.geom import (
    Ceil,
    Lin,
    Part,
    clean,
    extend,
    filled,
    polys,
    r,
    rect,
    split_by,
    union,
)
from uea.packs.arch.kinds import (
    Door,
    Niche,
    Roof,
    RoofType,
    Room,
    Sep,
    Slab,
    SlabType,
    Stair,
    Void,
    Wall,
    WallType,
    Win,
)
from uea.packs.arch.stairs import layout
from uea.packs.project import Grid, Level

Axis = Literal["x", "y", "s"]
"""x and y: absolute plan axes. s: along a wall that runs at an angle, from its start a."""
Side = Literal["lo", "hi"]
OPENING_KINDS = ("door", "win", "niche")
JOIN_TOL = 2e-3
"""A wall end within 2 mm of another wall touches it."""
JOIN_MIN_SIN = 0.2
"""Walls closer than about 12° to parallel are not joined."""
JOIN_MAX = 2.0


def other_axis(a: Axis) -> Axis:
    return "y" if a == "x" else "x"


@dataclass
class LevelGeo:
    id: str
    z: float
    fb: float
    head: float | None
    below: str | None = None
    above: str | None = None

    @property
    def ssl(self) -> float:
        """Structural slab level, the top of the slab core (absolute)."""
        return self.z - self.fb


@dataclass
class WallGeo:
    id: str
    level: str
    o: Literal["h", "v", "d"]
    """h: runs along x (its position is a y interval); v: runs along y; d: any other direction."""
    lo: float
    hi: float
    s0: float
    s1: float
    layers: Layers
    flip: bool
    status: str
    lb: bool
    bottom: float = 0.0
    top: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])
    """Top profile along the wall: (s, absolute z). Empty if unknown."""
    ext: Side | None = None
    """Outside face of an exterior wall."""
    org: tuple[float, float] = (0.0, 0.0)
    """Plan point of s=0, c=0: the origin for h and v walls, the start a of a d wall."""
    udir: tuple[float, float] = (1.0, 0.0)
    """Unit direction of s for a d wall (a to b)."""
    raw: bool = False
    """Given by a= and b=: its ends are joined to the walls they touch."""
    ea: tuple[float, float] = (0.0, 0.0)
    eb: tuple[float, float] = (0.0, 0.0)
    """How far the lo and hi face reach beyond s0 and s1 where the ends join other walls."""

    @property
    def u(self) -> tuple[float, float]:
        """Plan direction of s."""
        return (1.0, 0.0) if self.o == "h" else (0.0, 1.0) if self.o == "v" else self.udir

    @property
    def n(self) -> tuple[float, float]:
        """Plan direction of c, from the lo face to the hi face."""
        if self.o == "h":
            return (0.0, 1.0)
        if self.o == "v":
            return (1.0, 0.0)
        return (-self.udir[1], self.udir[0])

    @property
    def along(self) -> Axis:
        return "x" if self.o == "h" else "y" if self.o == "v" else "s"

    @property
    def across(self) -> Literal["x", "y"]:
        """The axis a position across the wall is on; walls at an angle have none."""
        assert self.o != "d"
        return "y" if self.o == "h" else "x"

    @property
    def t(self) -> float:
        return self.hi - self.lo

    @property
    def length(self) -> float:
        return self.s1 - self.s0

    @property
    def mid(self) -> float:
        return (self.lo + self.hi) / 2

    @property
    def active(self) -> bool:
        return self.status != "demolish"

    @property
    def faces(self) -> tuple[str, str]:
        """Names of the lo and hi face."""
        return {"h": ("s", "n"), "v": ("w", "e"), "d": ("r", "l")}[self.o]

    def box(self, a: float, b: float, grown: bool = True) -> Polygon:
        """The wall between across-coordinates a and b over its span (and its joins)."""
        if not grown or not (any(self.ea) or any(self.eb)):
            if self.o == "h":
                return rect(self.s0, self.s1, a, b)
            if self.o == "v":
                return rect(a, b, self.s0, self.s1)
        # an end cut along the far face of the wall it joins is a straight line across the faces
        pts = [self._at(-1, a, grown), self._at(1, a, grown), self._at(1, b, grown)]
        pts.append(self._at(-1, b, grown))
        return Polygon([(r(x), r(y)) for x, y in pts])

    def _at(self, end: int, c: float, grown: bool) -> tuple[float, float]:
        """The corner of the wall's end (-1: at s0, 1: at s1) at across-coordinate c."""
        if not grown:
            return self.plan_point(self.s0 if end < 0 else self.s1, c)
        k = (c - self.lo) / self.t
        if end < 0:
            return self.plan_point(self.s0 - self.ea[0] - (self.ea[1] - self.ea[0]) * k, c)
        return self.plan_point(self.s1 + self.eb[0] + (self.eb[1] - self.eb[0]) * k, c)

    @property
    def poly(self) -> Polygon:
        return self.box(self.lo, self.hi)

    @property
    def core(self) -> Polygon:
        """The wall between its ends a and b, without the joins."""
        return self.box(self.lo, self.hi, grown=False)

    def face_line(self, side: Side) -> LineString:
        c = self.lo if side == "lo" else self.hi
        (ax, ay), (bx, by) = self.plan_point(self.s0, c), self.plan_point(self.s1, c)
        return LineString([(r(ax), r(ay)), (r(bx), r(by))])

    def inner(self) -> Side:
        """The side the first-listed layers are on."""
        side: Side = "lo"
        if self.ext is not None:
            side = "hi" if self.ext == "lo" else "lo"
        if self.flip:
            side = "hi" if side == "lo" else "lo"
        return side

    def finish(self, side: Side) -> float:
        return self.layers.before_core() if side == self.inner() else self.layers.after_core()

    def plan_point(self, s: float, c: float) -> tuple[float, float]:
        (ux, uy), (nx, ny), (ox, oy) = self.u, self.n, self.org
        return (ox + s * ux + c * nx, oy + s * uy + c * ny)

    def c_of(self, x: float, y: float) -> float:
        """The across-coordinate of a plan point."""
        return self.n[0] * (x - self.org[0]) + self.n[1] * (y - self.org[1])

    def s_of(self, x: float, y: float) -> float:
        return self.u[0] * (x - self.org[0]) + self.u[1] * (y - self.org[1])

    def end_points(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return self.plan_point(self.s0, self.mid), self.plan_point(self.s1, self.mid)

    def top_at(self, s: float) -> float | None:
        if not self.top:
            return None
        pts = self.top
        if s <= pts[0][0]:
            return pts[0][1]
        for (sa, za), (sb, zb) in pairwise(pts):
            if sa <= s <= sb:
                return za if sb == sa else za + (zb - za) * (s - sa) / (sb - sa)
        return pts[-1][1]

    def top_min(self, a: float, b: float) -> float | None:
        if not self.top:
            return None
        vals = [z for s, z in self.top if a < s < b]
        ends = [self.top_at(a), self.top_at(b)]
        return min([v for v in ends if v is not None] + vals)


@dataclass
class OpeningGeo:
    id: str
    kind: str
    host: str
    level: str
    axis: Axis
    lo: float
    hi: float
    sill: float
    """Bottom above the FFL."""
    top: float
    """Top above the FFL."""
    depth: float
    face: Side | None
    status: str
    sides: tuple[str | None, str | None] = (None, None)
    """Rooms on the host wall's lo and hi side (None: outside)."""

    @property
    def width(self) -> float:
        return self.hi - self.lo

    @property
    def mid(self) -> float:
        return (self.lo + self.hi) / 2


@dataclass
class StairPartGeo:
    """A flight, the landing or one winder of a stair."""

    kind: Literal["flight", "landing", "winder"]
    poly: Polygon
    tread: int
    """Flight: the tread it starts on (0 is the lower floor). Landing, winder: its own number."""
    risers: int = 0
    start: tuple[float, float] = (0.0, 0.0)
    """Flight: the middle of the edge it starts on."""
    climb: tuple[float, float] = (0.0, 0.0)
    """Flight: the unit direction it climbs."""


@dataclass
class StairGeo:
    id: str
    level: str
    to: str
    x0: float
    x1: float
    y0: float
    y1: float
    poly: Polygon
    """Footprint of all flights, the landing and the well."""
    up: str
    n: int
    riser: float
    tread: float
    w: float
    status: str
    shape: str = "straight"
    turn: str | None = None
    n1: int = 0
    """Risers of the first flight (shapes l and u)."""
    winders: int = 0
    parts: list[StairPartGeo] = field(default_factory=list[StairPartGeo])
    lines: list[LineString] = field(default_factory=list[LineString])
    """Edges between treads."""
    walk: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])
    """Walking line, up the middle."""

    @property
    def run(self) -> float:
        """Length of the treads of a straight stair."""
        return (self.n - 1) * self.tread

    @property
    def step(self) -> float:
        """Step length 2h + a (Schrittmaß)."""
        return 2 * self.riser + self.tread


@dataclass
class SepGeo:
    id: str
    level: str
    o: Literal["h", "v"]
    pos: float
    s0: float
    s1: float

    @property
    def line(self) -> LineString:
        if self.o == "h":
            return LineString([(r(self.s0), r(self.pos)), (r(self.s1), r(self.pos))])
        return LineString([(r(self.pos), r(self.s0)), (r(self.pos), r(self.s1))])


@dataclass
class SlabGeo:
    id: str
    level: str
    outline: BaseGeometry
    layers: Layers
    top: float
    """Absolute height of the core's top (the storey's SSL)."""
    status: str
    net: BaseGeometry = field(default_factory=Polygon)
    """Outline minus voids."""

    @property
    def underside(self) -> float:
        """Underside of the core."""
        return self.top - self.layers.core

    @property
    def ceiling(self) -> float:
        """Underside of everything (the finished ceiling below)."""
        return self.top - self.layers.core - self.layers.after_core()


@dataclass
class VoidGeo:
    id: str
    slab: str
    poly: Polygon


@dataclass
class RoofGeo:
    id: str
    level: str
    shape: str
    pitch: float
    x0: float
    x1: float
    y0: float
    y1: float
    foot: Polygon
    """The rectangle it covers."""
    base: float
    """Absolute height of the rafter underside at the eaves line."""
    planes: list[Lin]
    """Rafter underside (absolute z) as planes; the roof is their minimum."""
    eave_edges: list[str]
    over: Polygon
    skin: float
    """Vertical thickness above the rafter underside."""
    lining: float
    """Vertical thickness below the rafter underside."""
    d_max: float
    status: str

    @property
    def slope(self) -> float:
        return math.tan(math.radians(self.pitch))

    def underside(self, x: float, y: float) -> float:
        return min(p(x, y) for p in self.planes)

    @property
    def eaves_z(self) -> float:
        """Eaves height: top of the roof skin above the outer face of the eaves wall."""
        return self.base + self.skin

    @property
    def ridge_z(self) -> float:
        """Ridge height: top of the roof skin at the ridge (highest point)."""
        return self.base + self.slope * self.d_max + self.skin


@dataclass
class RoomGeo:
    id: str
    level: str
    seed: tuple[float, float]
    poly: Polygon
    """Shell outline, between core faces."""
    fin: BaseGeometry
    """Finished outline (finish layers of the walls removed)."""
    bounds: list[str]
    ceiling: Ceil
    """Clear height above the FFL: the slab above and the roofs. Empty: no ceiling."""

    @property
    def area(self) -> float:
        return self.poly.area

    @property
    def area_fin(self) -> float:
        return self.fin.area

    @property
    def flat(self) -> bool:
        return self.ceiling.flat(self.fin)

    @property
    def height(self) -> float | None:
        """Clear height (finished) if it is the same everywhere."""
        hr = self.height_range()
        if hr is None or hr[1] - hr[0] > 1e-6:
            return None
        return hr[0]

    def height_range(self) -> tuple[float, float] | None:
        return self.ceiling.height_range(self.fin)

    @property
    def volume(self) -> float | None:
        if not self.ceiling:
            return None
        return self.ceiling.volume(self.fin)

    def dims(self, which: Literal["shell", "fin"]) -> tuple[float, float] | None:
        """Width and depth if the outline is a rectangle."""
        g = self.poly if which == "shell" else self.fin
        x0, y0, x1, y1 = g.bounds
        if abs((x1 - x0) * (y1 - y0) - g.area) > 1e-6:
            return None
        return (x1 - x0, y1 - y0)


@dataclass
class ArchGeo:
    levels: dict[str, LevelGeo] = field(default_factory=dict[str, LevelGeo])
    walls: dict[str, WallGeo] = field(default_factory=dict[str, WallGeo])
    openings: dict[str, OpeningGeo] = field(default_factory=dict[str, OpeningGeo])
    stairs: dict[str, StairGeo] = field(default_factory=dict[str, StairGeo])
    seps: dict[str, SepGeo] = field(default_factory=dict[str, SepGeo])
    slabs: dict[str, SlabGeo] = field(default_factory=dict[str, SlabGeo])
    voids: dict[str, VoidGeo] = field(default_factory=dict[str, VoidGeo])
    roofs: dict[str, RoofGeo] = field(default_factory=dict[str, RoofGeo])
    rooms: dict[str, RoomGeo] = field(default_factory=dict[str, RoomGeo])
    seeds: dict[str, tuple[float, float]] = field(default_factory=dict[str, tuple[float, float]])
    domains: dict[str, BaseGeometry] = field(default_factory=dict[str, BaseGeometry])
    regions: dict[str, list[Polygon]] = field(default_factory=dict[str, list[Polygon]])

    def level_order(self) -> list[str]:
        return sorted(self.levels, key=lambda k: self.levels[k].z)

    def room_at(self, level: str, x: float, y: float) -> str | None:
        p = SPoint(x, y)
        for rid, g in self.rooms.items():
            if g.level == level and g.poly.covers(p):
                return rid
        return None

    def walls_on(self, level: str, active: bool = True) -> list[WallGeo]:
        return [w for w in self.walls.values() if w.level == level and (w.active or not active)]

    def roofs_on(self, level: str) -> list[RoofGeo]:
        return [r for r in self.roofs.values() if r.level == level and r.status != "demolish"]

    def roof_parts(self, level: str) -> list[RoofGeo]:
        """The roofs of a storey; together they are one roof (0020-roof-parts)."""
        return self.roofs_on(level)

    def slab_on(self, level: str) -> SlabGeo | None:
        for s in self.slabs.values():
            if s.level == level and s.status != "demolish":
                return s
        return None


class Resolver:
    def __init__(self, d: Derived) -> None:
        self.d = d
        self.m: Model = d.model
        self.g = ArchGeo()
        d.arch = self.g

    # ---------- lookups ----------

    def need(self, key: str, *kinds: str) -> Element:
        """The element, or Unresolved (the reference check reports the problem)."""
        el = self.m.get(key)
        if el is None or (kinds and el.kind not in kinds):
            raise Unresolved(key, missing=True)
        return el

    def level(self, key: str) -> LevelGeo:
        self.need(key, "level")
        if key not in self.g.levels:
            raise Unresolved(key, missing=True)
        return self.g.levels[key]

    def wall_type(self, key: str) -> WallType:
        el = self.need(key, "type")
        if not isinstance(el, WallType):
            raise Unresolved(key, missing=True)
        return el

    # ---------- anchors ----------

    def base(self, a: Anchor, axis: Axis) -> float:
        if a.coord is not None:
            return a.coord
        assert a.ref is not None
        el = self.m.get(a.ref)
        if el is None:
            raise Unresolved(a.ref, missing=True)
        side = self._side(a)
        if isinstance(el, Grid):
            if a.face is not None:
                raise GeoError(f"{a.fmt()}: a grid has no faces", f"write {a.ref}{a.sign or ''}")
            if axis == "s":
                raise self._no_s(a)
            if el.axis != axis:
                raise GeoError(
                    f"{axis}={a.fmt()}: grid {a.ref} is an {el.axis} line",
                    f"use an {axis} grid for {axis}=",
                )
            return el.coord
        if isinstance(el, Wall):
            w = self.axis_wall(a, axis)
            if w.across != axis:
                raise GeoError(
                    f"{axis}={a.fmt()}: {a.ref} runs along {axis} and has no {axis} face",
                    f"anchor {axis}= on a grid or on a wall that runs along {other_axis(axis)}",
                )
            if a.face is not None:
                ok = "ns" if w.o == "h" else "ew"
                if a.face != "c" and a.face not in ok:
                    raise GeoError(
                        f"{a.fmt()}: {a.ref} runs along {w.along}; its faces are"
                        f" .{ok[0]} and .{ok[1]}",
                    )
            if side == "c":
                return w.mid
            if side is None:
                raise GeoError(
                    f"{axis}={a.fmt()}: say which face of {a.ref}",
                    f"{a.ref}+ (its +{axis} face), {a.ref}- or a face like"
                    f" {a.ref}.{'n' if w.o == 'h' else 'e'}",
                )
            return w.hi if side == "hi" else w.lo
        if el.kind in OPENING_KINDS:
            o = self.opening(a.ref)
            if o.axis != axis:
                if o.axis == "s":
                    raise GeoError(
                        f"{axis}={a.fmt()}: {a.ref} is in a wall that runs at an angle and has no"
                        f" {axis} position",
                        f"anchor {axis}= on a grid or on a wall along x or y",
                    )
                raise GeoError(
                    f"{axis}={a.fmt()}: {a.ref} lies along {o.axis}",
                    f"use {o.axis}= or anchor on something along {axis}",
                )
            if side == "c":
                return o.mid
            if side is None:
                raise GeoError(
                    f"{axis}={a.fmt()}: say which edge of {a.ref}",
                    f"{a.ref}+, {a.ref}- or {a.ref}.c",
                )
            return o.hi if side == "hi" else o.lo
        if isinstance(el, Stair):
            if axis == "s":
                raise self._no_s(a)
            s = self.stair(a.ref)
            lo, hi = (s.x0, s.x1) if axis == "x" else (s.y0, s.y1)
            if side == "c":
                return (lo + hi) / 2
            if side is None:
                raise GeoError(
                    f"{axis}={a.fmt()}: say which side of {a.ref}", f"{a.ref}+ or {a.ref}-"
                )
            return hi if side == "hi" else lo
        if isinstance(el, Sep):
            if axis == "s":
                raise self._no_s(a)
            s = self.sep(a.ref)
            if (s.o == "h") != (axis == "y"):
                raise GeoError(
                    f"{axis}={a.fmt()}: {a.ref} runs along {axis} and has no {axis} position"
                )
            return s.pos
        raise GeoError(
            f"{a.fmt()}: {a.ref} is a {el.kind}; positions anchor on grids, walls, openings,"
            " stairs and separators"
        )

    def axis_wall(self, a: Anchor, axis: Axis) -> WallGeo:
        """The wall an anchor points at, if it can give a position on an axis."""
        assert a.ref is not None
        if axis == "s":
            raise self._no_s(a)
        w = self.wall(a.ref)
        if w.o == "d":
            raise GeoError(
                f"{axis}={a.fmt()}: {a.ref} runs at an angle and has no {axis} position",
                f"anchor {axis}= on a grid or on a wall along x or y",
            )
        return w

    @staticmethod
    def _no_s(a: Anchor) -> GeoError:
        return GeoError(
            f"s={a.fmt()}: s counts along one wall from its start a; {a.ref} cannot give it",
            "use a number (s=1.2+) or an opening of the same wall (s=f1+0.5)",
        )

    @staticmethod
    def _side(a: Anchor) -> Literal["lo", "hi", "c"] | None:
        if a.face == "c":
            return "c"
        if a.face in ("n", "e"):
            return "hi"
        if a.face in ("s", "w"):
            return "lo"
        if a.sign == "+":
            return "hi"
        if a.sign == "-":
            return "lo"
        return None

    def point(self, a: Anchor, axis: Axis) -> float:
        b = self.base(a, axis)
        if a.sign == "+":
            return b + a.dist
        if a.sign == "-":
            return b - a.dist
        return b

    def interval(self, a: Anchor, axis: Axis, length: float) -> tuple[float, float]:
        if a.face == "c":
            c = self.point(a, axis)
            return (c - length / 2, c + length / 2)
        if a.sign is None:
            raise GeoError(
                f"{axis}={a.fmt()}: say which side it lies on",
                f"{a.fmt()}+ (extends in +{axis}) or {a.fmt()}- (extends in -{axis})",
            )
        b = self.base(a, axis)
        if a.sign == "+":
            return (b + a.dist, b + a.dist + length)
        return (b - a.dist - length, b - a.dist)

    def span(self, s: Span, axis: Axis) -> tuple[float, float]:
        va = self._end(s.a, s.b, axis)
        vb = self._end(s.b, s.a, axis)
        lo, hi = min(va, vb), max(va, vb)
        if hi - lo < 1e-6:
            raise GeoError(f"{axis}={s.fmt()} is empty ({ln(lo)})")
        return lo, hi

    def _end(self, a: Anchor, other: Anchor, axis: Axis) -> float:
        if a.sign is not None or a.face is not None or a.coord is not None:
            return self.point(a, axis)
        el = self.m.get(a.ref or "")
        if el is None:
            raise Unresolved(a.ref or "?", missing=True)
        if isinstance(el, Grid):
            return self.point(a, axis)
        toward = self._rough(other, axis)
        if isinstance(el, Wall):
            w = self.axis_wall(a, axis)
            if w.across != axis:
                raise GeoError(
                    f"{axis} span end {a.fmt()}: {el.id} runs along {axis}",
                    f"end the span on a wall that runs along {other_axis(axis)}",
                )
            return w.hi if toward > w.mid else w.lo
        lo = self.point(Anchor(a.ref, None, "-"), axis)
        hi = self.point(Anchor(a.ref, None, "+"), axis)
        return hi if toward > (lo + hi) / 2 else lo

    def _rough(self, a: Anchor, axis: Axis) -> float:
        if a.sign is not None or a.face is not None or a.coord is not None:
            return self.point(a, axis)
        el = self.m.get(a.ref or "")
        if el is None:
            raise Unresolved(a.ref or "?", missing=True)
        if isinstance(el, Wall):
            w = self.axis_wall(a, axis)
            return w.mid if w.across == axis else (w.s0 + w.s1) / 2
        if isinstance(el, Grid):
            return el.coord
        return self.point(Anchor(a.ref, "c"), axis)

    # ---------- elements ----------

    def wall(self, key: str) -> WallGeo:
        return self.d.resolve(key, self.g.walls, lambda: self._wall(key))

    def _wall(self, key: str) -> WallGeo:
        el = self.need(key, "wall")
        assert isinstance(el, Wall)
        self.level(el.level.id)
        wt = self.wall_type(el.type.id)
        t = wt.layers.core
        if el.on is not None:
            self.need(el.on.id, "wall")
            src = self.wall(el.on.id)
            if abs(src.t - t) > 1e-6:
                raise GeoError(
                    f"on={src.id}: {key} has a core of {ln(t)}, {src.id} of {ln(src.t)}",
                    "use x=/y= to place it, or a type with the same core",
                    others=(src.id,),
                )
            return WallGeo(
                key, el.level.id, src.o, src.lo, src.hi, src.s0, src.s1, wt.layers, el.flip,
                el.status, el.lb, org=src.org, udir=src.udir, raw=src.raw,
            )  # fmt: skip
        if el.a is not None:
            assert el.b is not None
            return self._raw_wall(el, wt)
        if isinstance(el.y, Anchor):
            assert isinstance(el.x, Span)
            o = "h"
            lo, hi = self.interval(el.y, "y", t)
            s0, s1 = self.span(el.x, "x")
        else:
            assert isinstance(el.x, Anchor) and isinstance(el.y, Span)
            o = "v"
            lo, hi = self.interval(el.x, "x", t)
            s0, s1 = self.span(el.y, "y")
        return WallGeo(key, el.level.id, o, lo, hi, s0, s1, wt.layers, el.flip, el.status, el.lb)

    def _raw_wall(self, el: Wall, wt: WallType) -> WallGeo:
        """A wall from the point a to the point b: its axis, with the core centred on it."""
        assert el.a is not None and el.b is not None
        ax, ay = self.point(el.a.x, "x"), self.point(el.a.y, "y")
        bx, by = self.point(el.b.x, "x"), self.point(el.b.y, "y")
        t = wt.layers.core
        length = math.hypot(bx - ax, by - ay)
        if length < 1e-6:
            raise GeoError(
                f"a and b are the same point ({ln(ax)},{ln(ay)})", "give two different points"
            )

        def wall(
            o: Literal["h", "v", "d"],
            lo: float,
            hi: float,
            s0: float,
            s1: float,
            org: tuple[float, float] = (0.0, 0.0),
            udir: tuple[float, float] = (1.0, 0.0),
        ) -> WallGeo:
            return WallGeo(
                el.id, el.level.id, o, lo, hi, s0, s1, wt.layers, el.flip, el.status, el.lb,
                org=org, udir=udir, raw=True,
            )  # fmt: skip

        if abs(by - ay) <= 1e-6:
            y = (ay + by) / 2
            return wall("h", y - t / 2, y + t / 2, min(ax, bx), max(ax, bx))
        if abs(bx - ax) <= 1e-6:
            x = (ax + bx) / 2
            return wall("v", x - t / 2, x + t / 2, min(ay, by), max(ay, by))
        u = ((bx - ax) / length, (by - ay) / length)
        return wall("d", -t / 2, t / 2, 0.0, length, (ax, ay), u)

    def opening(self, key: str) -> OpeningGeo:
        return self.d.resolve(key, self.g.openings, lambda: self._opening(key))

    def _opening(self, key: str) -> OpeningGeo:
        el = self.need(key, *OPENING_KINDS)
        assert isinstance(el, Door | Win | Niche)
        self.need(el.host.id, "wall")
        w = self.wall(el.host.id)
        axis = w.along
        given: Axis = "x" if el.x is not None else "y" if el.y is not None else "s"
        if given != axis:
            if axis == "s":
                raise GeoError(
                    f"{key} is in {w.id}, which runs at an angle: give s=, the distance from its"
                    f" start a, not {given}=",
                    f"~ {key} {given}= s={el.along.fmt()}",
                )
            raise GeoError(
                f"{key} is in {w.id}, which runs along {axis}: give {axis}=, not {given}=",
                f"~ {key} {given}= {axis}={el.along.fmt()}",
            )
        if axis == "s":
            for ref in el.along.refs():
                other = self.m.get(ref)
                if isinstance(other, Door | Win | Niche) and other.host.id != w.id:
                    raise GeoError(
                        f"s={el.along.fmt()}: {ref} is in {other.host.id}, and s counts along"
                        f" one wall ({w.id})",
                        "anchor on an opening of the same wall, or use a number",
                    )
        lo, hi = self.interval(el.along, axis, el.size.w)
        lvl = self.level(w.level)
        face: Side | None = None
        depth = w.t
        if isinstance(el, Win):
            if el.sill is not None:
                sill = el.sill
            elif lvl.head is not None:
                sill = lvl.head - el.size.h
            else:
                raise GeoError(
                    f"{lvl.id} has no head height (head=) and {key} no sill=",
                    f"~ {lvl.id} head=2.26 or ~ {key} sill=0.9",
                )
        elif isinstance(el, Niche):
            sill = el.sill
            assert el.host.face is not None
            lo_face, hi_face = w.faces
            if el.host.face not in (lo_face, hi_face):
                where = "runs at an angle" if w.o == "d" else f"runs along {w.along}"
                raise GeoError(
                    f"host {el.host.fmt()}: {w.id} {where}; its faces are .{hi_face} and .{lo_face}"
                )
            face = "hi" if el.host.face == hi_face else "lo"
            depth = el.d
        else:
            sill = el.sill if el.sill is not None else 0.0
        return OpeningGeo(
            key,
            el.kind,
            w.id,
            w.level,
            axis,
            lo,
            hi,
            sill,
            sill + el.size.h,
            depth,
            face,
            el.status,
        )

    def stair(self, key: str) -> StairGeo:
        return self.d.resolve(key, self.g.stairs, lambda: self._stair(key))

    def _stair(self, key: str) -> StairGeo:
        el = self.need(key, "stair")
        assert isinstance(el, Stair)
        a = self.level(el.level.id)
        b = self.level(el.to.id)
        rise = b.z - a.z
        if rise <= 0:
            raise GeoError(
                f"{el.to.id} (z={ln(b.z)}) is not above {el.level.id} (z={ln(a.z)})",
                "swap the storeys: stair <id> <from> <to>",
            )
        lay = layout(el.shape, el.n, el.tread, el.w, el.n1, el.winders, el.gap or 0.1)
        climb = {"n": (0.0, 1.0), "s": (0.0, -1.0), "e": (1.0, 0.0), "w": (-1.0, 0.0)}[el.up]
        left = (-climb[1], climb[0])
        q = left if el.turn != "r" else (-left[0], -left[1])
        # local (p, q) to plan: p along the first flight, q toward the turn
        to_plan = [climb[0], q[0], climb[1], q[1], 0.0, 0.0]
        bx0, by0, bx1, by1 = affine_transform(lay.poly, to_plan).bounds
        x0, x1 = self.interval(el.x, "x", bx1 - bx0)
        y0, y1 = self.interval(el.y, "y", by1 - by0)
        to_plan[4], to_plan[5] = x0 - bx0, y0 - by0

        def put(g: Polygon) -> Polygon:
            moved = affine_transform(g, to_plan)
            assert isinstance(moved, Polygon)
            return Polygon([(r(x), r(y)) for x, y in moved.exterior.coords])

        def at(p: tuple[float, float]) -> tuple[float, float]:
            return (
                to_plan[0] * p[0] + to_plan[1] * p[1] + to_plan[4],
                to_plan[2] * p[0] + to_plan[3] * p[1] + to_plan[5],
            )

        def turn_dir(v: tuple[float, float]) -> tuple[float, float]:
            return (to_plan[0] * v[0] + to_plan[1] * v[1], to_plan[2] * v[0] + to_plan[3] * v[1])

        parts: list[StairPartGeo] = []
        for fl in lay.flights:
            parts.append(
                StairPartGeo(
                    "flight", put(fl.poly), fl.tread0, fl.risers, at(fl.start), turn_dir(fl.climb)
                )
            )
        landing = el.winders is None
        for poly, number in lay.turn:
            parts.append(StairPartGeo("landing" if landing else "winder", put(poly), number))
        lines = [LineString([at((c[0], c[1])) for c in ln_.coords]) for ln_ in lay.lines]
        n1 = lay.flights[0].risers
        return StairGeo(
            key,
            a.id,
            b.id,
            r(x0),
            r(x1),
            r(y0),
            r(y1),
            put(lay.poly),
            el.up,
            el.n,
            rise / el.n,
            el.tread,
            el.w,
            el.status,
            el.shape,
            el.turn,
            n1 if el.shape != "straight" else 0,
            el.winders or 0,
            parts,
            lines,
            [at(pt) for pt in lay.walk],
        )

    def sep(self, key: str) -> SepGeo:
        return self.d.resolve(key, self.g.seps, lambda: self._sep(key))

    def _sep(self, key: str) -> SepGeo:
        el = self.need(key, "sep")
        assert isinstance(el, Sep)
        self.level(el.level.id)
        if isinstance(el.y, Anchor):
            assert isinstance(el.x, Span)
            pos = self.point(el.y, "y")
            s0, s1 = self.span(el.x, "x")
            return SepGeo(key, el.level.id, "h", pos, s0, s1)
        assert isinstance(el.x, Anchor) and isinstance(el.y, Span)
        pos = self.point(el.x, "x")
        s0, s1 = self.span(el.y, "y")
        return SepGeo(key, el.level.id, "v", pos, s0, s1)

    def seed(self, key: str) -> tuple[float, float]:
        return self.d.resolve(key, self.g.seeds, lambda: self._seed(key))

    def _seed(self, key: str) -> tuple[float, float]:
        el = self.need(key, "room")
        assert isinstance(el, Room)
        self.level(el.level.id)
        return (self.point(el.at.x, "x"), self.point(el.at.y, "y"))

    # ---------- whole model ----------

    def run(self) -> None:
        self._levels()
        for kind, fn in (
            ("wall", self.wall),
            ("door", self.opening),
            ("win", self.opening),
            ("niche", self.opening),
            ("stair", self.stair),
            ("sep", self.sep),
            ("room", self.seed),
        ):
            for el in self.m.of_kind(kind):
                with suppress(Unresolved):
                    fn(el.id)
        self._joins()
        self._slabs()
        self._voids()
        self._domains()
        self._exterior()
        self._roofs()
        self._wall_tops()
        self._rooms()
        self._opening_sides()

    def _levels(self) -> None:
        levels = sorted(
            (e for e in self.m.of_kind("level") if isinstance(e, Level)), key=lambda e: e.z
        )
        for i, lv in enumerate(levels):
            self.g.levels[lv.id] = LevelGeo(
                lv.id,
                lv.z,
                lv.fb,
                lv.head,
                levels[i - 1].id if i > 0 else None,
                levels[i + 1].id if i + 1 < len(levels) else None,
            )

    def _joins(self) -> None:
        """Grow the ends of raw walls to the far face of the wall they touch (0018-raw-walls)."""
        for w in self.g.walls.values():
            if not (w.raw and w.active):
                continue
            others = [o for o in self.g.walls_on(w.level) if o is not w]
            for end, s_end, sign in (("a", w.s0, -1.0), ("b", w.s1, 1.0)):
                p = w.plan_point(s_end, w.mid)
                out = (sign * w.u[0], sign * w.u[1])
                reach = (0.0, 0.0)
                for o in others:
                    if o.core.distance(SPoint(p)) <= JOIN_TOL:
                        lo, hi = _reach(w, p, out, o)
                        reach = (max(reach[0], lo), max(reach[1], hi))
                if end == "a":
                    w.ea = reach
                else:
                    w.eb = reach

    def _walls_union(self, level: str) -> BaseGeometry:
        return union(w.poly for w in self.g.walls_on(level))

    def _slabs(self) -> None:
        for el in self.m.of_kind("slab"):
            assert isinstance(el, Slab)
            lv = self.g.levels.get(el.level.id)
            st = self.m.get(el.type.id)
            if lv is None or not isinstance(st, SlabType):
                continue
            outline = Polygon()
            if lv.below is not None:
                outline = filled(self._walls_union(lv.below))
            if outline.is_empty:
                outline = filled(self._walls_union(lv.id))
            if outline.is_empty:
                self.d.add(
                    "E-ARCH-030",
                    el.id,
                    f"has no outline: no walls on {lv.id} or below it",
                    "add the walls it rests on",
                )
                continue
            self.g.slabs[el.id] = SlabGeo(
                el.id, lv.id, outline, st.layers, lv.ssl, el.status, outline
            )

    def _voids(self) -> None:
        for el in self.m.of_kind("void"):
            assert isinstance(el, Void)
            slab = self.g.slabs.get(el.slab.id)
            if slab is None:
                continue
            try:
                if el.over is not None:
                    self.need(el.over.id, "stair")
                    poly = self.stair(el.over.id).poly
                else:
                    assert el.x is not None and el.y is not None
                    x0, x1 = self.span(el.x, "x")
                    y0, y1 = self.span(el.y, "y")
                    poly = rect(x0, x1, y0, y1)
            except Unresolved:
                continue
            except GeoError as e:
                self.d.add(e.code, el.id, e.msg, e.fix)
                continue
            self.g.voids[el.id] = VoidGeo(el.id, slab.id, poly)
            if el.status != "demolish":
                slab.net = clean(slab.net.difference(poly))

    def _domains(self) -> None:
        for lv in self.g.levels.values():
            parts: list[BaseGeometry] = [filled(self._walls_union(lv.id))]
            parts.extend(s.outline for s in self.g.slabs.values() if s.level == lv.id)
            self.g.domains[lv.id] = union(parts)

    def _exterior(self) -> None:
        for w in self.g.walls.values():
            dom = self.g.domains.get(w.level)
            if dom is None or dom.is_empty:
                continue
            edge = dom.boundary
            on = [
                side
                for side in ("lo", "hi")
                if w.face_line(side).intersection(edge.buffer(1e-5)).length > 0.01
            ]
            if len(on) == 1:
                w.ext = "lo" if on[0] == "lo" else "hi"

    def _roofs(self) -> None:
        for el in self.m.of_kind("roof"):
            assert isinstance(el, Roof)
            lv = self.g.levels.get(el.level.id)
            rt = self.m.get(el.type.id)
            if lv is None or not isinstance(rt, RoofType):
                continue
            dom = self.g.domains.get(lv.id)
            if dom is None or dom.is_empty:
                self.d.add(
                    "E-ARCH-040",
                    el.id,
                    f"{lv.id} has no outline to put the roof on (no walls or slab)",
                    f"add the slab of {lv.id} or its walls",
                )
                continue
            if el.x is not None and el.y is not None:
                try:
                    x0, x1 = self.span(el.x, "x")
                    y0, y1 = self.span(el.y, "y")
                except Unresolved:
                    continue
                except GeoError as e:
                    self.d.add(e.code, el.id, e.msg, e.fix)
                    continue
            else:
                x0, y0, x1, y1 = dom.bounds
                if abs((x1 - x0) * (y1 - y0) - dom.area) > 1e-3:
                    self.d.add(
                        "W-ARCH-041",
                        el.id,
                        f"the outline of {lv.id} is not a rectangle; the roof covers its bounding"
                        f" box {ar(x1 - x0)} x {ar(y1 - y0)}",
                        f"one roof per wing: ~ {el.id} x=<a>..<b> y=<c>..<d>, + roof for the rest",
                    )
            self.g.roofs[el.id] = make_roof(el, rt, lv, x0, x1, y0, y1)
        for lv in self.g.levels.values():
            parts = self.g.roofs_on(lv.id)
            dom = self.g.domains.get(lv.id)
            if not parts or dom is None:
                continue
            bare = dom.difference(union(p.foot for p in parts))
            if bare.area > 0.05:
                c = max(polys(bare), key=lambda q: q.area).representative_point()
                self.d.add(
                    "W-ARCH-042",
                    parts[0].id,
                    f"{ar(bare.area)} m² of the outline of {lv.id} lie under no roof, e.g. at"
                    f" ({ar(c.x)},{ar(c.y)})",
                    "add a roof for that part, or extend the roofs' x=/y=",
                )

    def _wall_tops(self) -> None:
        for w in self.g.walls.values():
            el = self.m[w.id]
            assert isinstance(el, Wall)
            lv = self.g.levels[w.level]
            w.bottom = lv.ssl
            if el.h is not None:
                w.top = [(w.s0, lv.ssl + el.h), (w.s1, lv.ssl + el.h)]
            elif el.top is not None:
                roof = self.g.roofs.get(el.top.id)
                if roof is not None:
                    w.top = roof_profile(w, self.g.roof_parts(roof.level))
            elif lv.above is not None:
                above = self.g.levels[lv.above]
                slab = self.g.slab_on(above.id)
                z = slab.underside if slab is not None else above.ssl
                w.top = [(w.s0, z), (w.s1, z)]
            else:
                self.d.add(
                    "W-ARCH-010",
                    w.id,
                    f"has no height yet: no storey above {lv.id} and no roof",
                    f"~ {w.id} top=<roof> or ~ {w.id} h=2.5",
                )

    def _rooms(self) -> None:
        for lv in self.g.levels.values():
            walls = self.g.walls_on(lv.id)
            wall_u = union(w.poly for w in walls)
            dom = self.g.domains.get(lv.id, Polygon())
            regions = polys(clean(dom.difference(wall_u)))
            for s in self.g.seps.values():
                if s.level == lv.id:
                    regions = split_by(regions, extend(s.line, 0.05))
            self.g.regions[lv.id] = regions
            bands: list[Polygon] = []
            for w in walls:
                for side in ("lo", "hi"):
                    f = w.finish(side)
                    if f > 0:
                        bands.append(
                            w.box(w.lo - f, w.lo) if side == "lo" else w.box(w.hi, w.hi + f)
                        )
            band_u = union(bands)
            ceiling = self._ceiling(lv)
            taken: dict[int, str] = {}
            for el in self.m.of_kind("room"):
                assert isinstance(el, Room)
                if el.level.id != lv.id or el.id not in self.g.seeds:
                    continue
                x, y = self.g.seeds[el.id]
                p = SPoint(x, y)
                idx = next((i for i, reg in enumerate(regions) if reg.covers(p)), None)
                if idx is None:
                    inside = [w.id for w in walls if w.poly.covers(p)]
                    if inside:
                        self.d.add(
                            "E-ARCH-020",
                            el.id,
                            f"seed at=({ln(x)},{ln(y)}) lies inside wall {inside[0]}",
                            "move the seed into the room",
                            inside[0],
                        )
                    else:
                        self.d.add(
                            "E-ARCH-020",
                            el.id,
                            f"seed at=({ln(x)},{ln(y)}) lies outside the outline of {lv.id}",
                            "move the seed into the room, or add the walls around it",
                        )
                    continue
                if idx in taken:
                    self.d.add(
                        "E-ARCH-021",
                        el.id,
                        f"lies in the same region as {taken[idx]}",
                        f"separate them with a wall or a sep, or remove {el.id}",
                        taken[idx],
                    )
                    continue
                taken[idx] = el.id
                poly = regions[idx]
                fin = clean(poly.difference(band_u))
                edge = poly.exterior.buffer(1e-5)
                bounds = [
                    w.id
                    for w in walls
                    if w.poly.intersection(edge).area > 1e-6
                    and w.poly.boundary.intersection(edge).length > 0.01
                ]
                bounds += [
                    s.id
                    for s in self.g.seps.values()
                    if s.level == lv.id and s.line.intersection(edge).length > 0.01
                ]
                bounds = sorted(bounds, key=natural)
                self.g.rooms[el.id] = RoomGeo(el.id, lv.id, (x, y), poly, fin, bounds, ceiling)
            for i, reg in enumerate(regions):
                if taken and i not in taken and reg.area >= 0.5:
                    c = reg.representative_point()
                    self.d.add(
                        "W-ARCH-022",
                        lv.id,
                        f"region of {ar(reg.area)} m² at ({ar(c.x)},{ar(c.y)}) has no room",
                        f"+ room _ {lv.id} <use> at={ar(c.x)},{ar(c.y)}",
                    )

    def _ceiling(self, lv: LevelGeo) -> Ceil:
        caps: list[Lin] = []
        if lv.above is not None:
            above = self.g.levels[lv.above]
            slab = self.g.slab_on(above.id)
            z = slab.ceiling if slab is not None else above.ssl
            caps.append(Lin(0.0, 0.0, z - lv.z))
        parts: list[Part] = []
        for roof in self.g.roofs.values():
            rl = self.g.levels[roof.level]
            if rl.z <= lv.z + 1e-9 and roof.status != "demolish":
                planes = tuple(Lin(p.a, p.b, p.c - roof.lining - lv.z) for p in roof.planes)
                parts.append(Part(roof.foot, planes))
        return Ceil(tuple(caps), tuple(parts))

    def _opening_sides(self) -> None:
        for o in self.g.openings.values():
            w = self.g.walls.get(o.host)
            if w is None:
                continue
            lo = w.plan_point(o.mid, w.lo - 0.05)
            hi = w.plan_point(o.mid, w.hi + 0.05)
            o.sides = (self.g.room_at(w.level, *lo), self.g.room_at(w.level, *hi))


def _reach(
    w: WallGeo, p: tuple[float, float], out: tuple[float, float], o: WallGeo
) -> tuple[float, float]:
    """How far the lo and hi face of w at its end p must grow along `out` to the far face of o."""
    nx, ny = o.n
    slope = nx * out[0] + ny * out[1]
    if abs(slope) < JOIN_MIN_SIN:
        return (0.0, 0.0)
    inside = (p[0] - 0.1 * out[0], p[1] - 0.1 * out[1])
    far = o.lo if o.c_of(*inside) > o.mid else o.hi
    reach: list[float] = []
    for offset in (w.lo - w.mid, w.hi - w.mid):
        q = (p[0] + offset * w.n[0], p[1] + offset * w.n[1])
        reach.append(min(max((far - o.c_of(*q)) / slope, 0.0), JOIN_MAX))
    return (reach[0], reach[1])


def make_roof(
    el: Roof, rt: RoofType, lv: LevelGeo, x0: float, x1: float, y0: float, y1: float
) -> RoofGeo:
    t = math.tan(math.radians(el.pitch))
    cos = math.cos(math.radians(el.pitch))
    base = lv.ssl + el.knee
    # eave edges: (name, inward normal, a point on the edge)
    edges: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
        "s": ((0.0, 1.0), (x0, y0)),
        "n": ((0.0, -1.0), (x0, y1)),
        "w": ((1.0, 0.0), (x0, y0)),
        "e": ((-1.0, 0.0), (x1, y0)),
    }
    if el.shape == "gable":
        eaves = ["s", "n"] if el.ridge == "x" else ["w", "e"]
        d_max = (y1 - y0) / 2 if el.ridge == "x" else (x1 - x0) / 2
    elif el.shape == "shed":
        low = {"n": "s", "s": "n", "e": "w", "w": "e"}[el.up or "n"]
        eaves = [low]
        d_max = (y1 - y0) if low in "ns" else (x1 - x0)
    else:
        eaves = ["s", "n", "w", "e"]
        d_max = min(x1 - x0, y1 - y0) / 2
    planes: list[Lin] = []
    for name in eaves:
        (nx, ny), (px, py) = edges[name]
        planes.append(Lin(t * nx, t * ny, base - t * (px * nx + py * ny)))
    ov = {k: (el.eave if k in eaves else el.verge) for k in "snwe"}
    over = rect(x0 - ov["w"], x1 + ov["e"], y0 - ov["s"], y1 + ov["n"])
    skin = (rt.layers.core + rt.layers.before_core()) / cos
    lining = rt.layers.after_core() / cos
    return RoofGeo(
        el.id,
        lv.id,
        el.shape,
        el.pitch,
        x0,
        x1,
        y0,
        y1,
        rect(x0, x1, y0, y1),
        base,
        planes,
        eaves,
        over,
        skin,
        lining,
        d_max,
        el.status,
    )


def roof_profile(w: WallGeo, parts: Sequence[RoofGeo]) -> list[tuple[float, float]]:
    """Top of a wall cut by the roofs of a storey: the rafter underside along its centre line."""
    c = w.mid
    p0, p1 = w.plan_point(w.s0, c), w.plan_point(w.s1, c)
    seg = LineString([p0, p1])

    def z(s: float) -> float:
        x, y = w.plan_point(s, c)
        at = SPoint(x, y)
        covering = [rf for rf in parts if rf.foot.distance(at) < 1e-6]
        if not covering:
            covering = [min(parts, key=lambda rf: rf.foot.distance(at))]
        return max(rf.underside(x, y) for rf in covering)

    ss = {w.s0, w.s1}
    planes = [f for rf in parts for f in rf.planes]
    for i, a in enumerate(planes):
        for b in planes[i + 1 :]:
            # where a == b along the line: (a-b)(s) = 0, linear in s
            diff = a - b
            f0, f1 = diff(*p0), diff(*p1)
            if (f0 > 0) != (f1 > 0) and f0 != f1:
                ss.add(w.s0 + (w.s1 - w.s0) * f0 / (f0 - f1))
    for rf in parts:
        cut = seg.intersection(rf.foot.boundary)
        pts = [cut] if isinstance(cut, SPoint) else list(getattr(cut, "geoms", []))
        for g in pts:
            if isinstance(g, SPoint) and w.s0 < w.s_of(g.x, g.y) < w.s1:
                ss.add(w.s_of(g.x, g.y))
    prof = [(s, z(s)) for s in sorted(ss)]
    keep = prof[:1]
    for (s, h), (s_next, h_next) in pairwise(prof[1:]):
        s_last, h_last = keep[-1]
        if abs((h - h_last) * (s_next - s_last) - (h_next - h_last) * (s - s_last)) > 1e-9:
            keep.append((s, h))
    return [*keep, prof[-1]]


def derive_arch(d: Derived) -> None:
    Resolver(d).run()


def arch_signatures(d: Derived) -> dict[str, tuple[float | str, ...]]:
    """Derived placement per element, to report what follows a change."""
    g = d.arch

    def q(v: float) -> float:
        return round(v, 4)

    out: dict[str, tuple[float | str, ...]] = {}
    for w in g.walls.values():
        out[w.id] = (w.o, q(w.lo), q(w.hi), q(w.s0), q(w.s1))
        if w.o == "d":
            out[w.id] += (q(w.org[0]), q(w.org[1]), q(w.udir[0]), q(w.udir[1]))
    for o in g.openings.values():
        out[o.id] = (q(o.lo), q(o.hi), q(o.sill), q(o.top))
    for s in g.stairs.values():
        out[s.id] = (q(s.x0), q(s.x1), q(s.y0), q(s.y1), round(s.poly.area, 3))
    for p in g.seps.values():
        out[p.id] = (q(p.pos), q(p.s0), q(p.s1))
    for rm in g.rooms.values():
        out[rm.id] = (round(rm.area_fin, 2),)
    for sl in g.slabs.values():
        out[sl.id] = (round(sl.net.area, 2),)
    for rf in g.roofs.values():
        out[rf.id] = (q(rf.x0), q(rf.x1), q(rf.y0), q(rf.y1), q(rf.base))
    return out

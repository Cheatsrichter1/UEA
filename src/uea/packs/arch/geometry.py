"""Architecture geometry derived from intent.

Walls, openings, stairs and separators are resolved from their positions (anchor±distance,
spans). Slabs take their outline from the walls below, roofs from their storey's outline.
Rooms are the regions around their seed points, bounded by walls and separators; finished
sizes subtract the finish layers of the walls. Heights come from the slab or roof above.

Coordinates are global plan metres; heights (`z`, `bottom`, `top` of walls, roof planes) are
absolute metres relative to ±0.00. Opening sills and tops are relative to the storey's FFL.
"""

import math
from contextlib import suppress
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

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
    Lin,
    clean,
    extend,
    filled,
    integrate_min,
    lower_envelope_regions,
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
from uea.packs.project import Grid, Level

Axis = Literal["x", "y"]
Side = Literal["lo", "hi"]
OPENING_KINDS = ("door", "win", "niche")


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
    o: Literal["h", "v"]
    """h: runs along x (its position is a y interval); v: runs along y."""
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

    @property
    def along(self) -> Axis:
        return "x" if self.o == "h" else "y"

    @property
    def across(self) -> Axis:
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

    def box(self, a: float, b: float) -> Polygon:
        """Rectangle between across-coordinates a and b over the wall's span."""
        if self.o == "h":
            return rect(self.s0, self.s1, a, b)
        return rect(a, b, self.s0, self.s1)

    @property
    def poly(self) -> Polygon:
        return self.box(self.lo, self.hi)

    def face_line(self, side: Side) -> LineString:
        c = self.lo if side == "lo" else self.hi
        if self.o == "h":
            return LineString([(r(self.s0), r(c)), (r(self.s1), r(c))])
        return LineString([(r(c), r(self.s0)), (r(c), r(self.s1))])

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
        return (s, c) if self.o == "h" else (c, s)

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
class StairGeo:
    id: str
    level: str
    to: str
    x0: float
    x1: float
    y0: float
    y1: float
    up: str
    n: int
    riser: float
    tread: float
    w: float
    status: str

    @property
    def run(self) -> float:
        return (self.n - 1) * self.tread

    @property
    def poly(self) -> Polygon:
        return rect(self.x0, self.x1, self.y0, self.y1)

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
    ceiling: list[Lin]
    """Clear height above the FFL as planes; the height is their minimum. Empty: no ceiling."""

    @property
    def area(self) -> float:
        return self.poly.area

    @property
    def area_fin(self) -> float:
        return self.fin.area

    @property
    def flat(self) -> bool:
        return all(p.flat for p in self.ceiling)

    @property
    def height(self) -> float | None:
        """Clear height (finished) if it is the same everywhere."""
        if not self.ceiling or not self.flat:
            return None
        return min(p.c for p in self.ceiling)

    def height_range(self) -> tuple[float, float] | None:
        if not self.ceiling:
            return None
        if self.flat:
            h = min(p.c for p in self.ceiling)
            return (h, h)
        vals: list[float] = []
        for _, part in lower_envelope_regions(self.fin, self.ceiling):
            for p in polys(part, 0.0):
                vals.extend(min(f(x, y) for f in self.ceiling) for x, y in p.exterior.coords)
        if not vals:
            return None
        return (max(min(vals), 0.0), max(vals))

    @property
    def volume(self) -> float | None:
        if not self.ceiling:
            return None
        return integrate_min(self.fin, self.ceiling)

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
            if el.axis != axis:
                raise GeoError(
                    f"{axis}={a.fmt()}: grid {a.ref} is an {el.axis} line",
                    f"use an {axis} grid for {axis}=",
                )
            return el.coord
        if isinstance(el, Wall):
            w = self.wall(a.ref)
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
            w = self.wall(el.id)
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
            w = self.wall(el.id)
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
            o, lo, hi, s0, s1 = src.o, src.lo, src.hi, src.s0, src.s1
        elif isinstance(el.y, Anchor):
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

    def opening(self, key: str) -> OpeningGeo:
        return self.d.resolve(key, self.g.openings, lambda: self._opening(key))

    def _opening(self, key: str) -> OpeningGeo:
        el = self.need(key, *OPENING_KINDS)
        assert isinstance(el, Door | Win | Niche)
        self.need(el.host.id, "wall")
        w = self.wall(el.host.id)
        axis = w.along
        given: Axis = "x" if el.x is not None else "y"
        if given != axis:
            raise GeoError(
                f"{key} is in {w.id}, which runs along {axis}: give {axis}=, not {given}=",
                f"~ {key} {given}= {axis}={el.along.fmt()}",
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
            ok = "ns" if w.o == "h" else "ew"
            if el.host.face not in ok:
                raise GeoError(
                    f"host {el.host.fmt()}: {w.id} runs along {w.along}; its faces are"
                    f" .{ok[0]} and .{ok[1]}"
                )
            face = "hi" if el.host.face in "ne" else "lo"
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
        run = (el.n - 1) * el.tread
        if el.up in ("w", "e"):
            x0, x1 = self.interval(el.x, "x", run)
            y0, y1 = self.interval(el.y, "y", el.w)
        else:
            x0, x1 = self.interval(el.x, "x", el.w)
            y0, y1 = self.interval(el.y, "y", run)
        return StairGeo(
            key, a.id, b.id, x0, x1, y0, y1, el.up, el.n, rise / el.n, el.tread, el.w, el.status
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
            x0, y0, x1, y1 = dom.bounds
            if abs((x1 - x0) * (y1 - y0) - dom.area) > 1e-3:
                self.d.add(
                    "W-ARCH-041",
                    el.id,
                    f"the outline of {lv.id} is not a rectangle; the roof covers its bounding box"
                    f" {ar(x1 - x0)} x {ar(y1 - y0)}",
                )
            self.g.roofs[el.id] = make_roof(el, rt, lv, x0, x1, y0, y1)

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
                    w.top = roof_profile(w, roof)
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

    def _ceiling(self, lv: LevelGeo) -> list[Lin]:
        planes: list[Lin] = []
        if lv.above is not None:
            above = self.g.levels[lv.above]
            slab = self.g.slab_on(above.id)
            z = slab.ceiling if slab is not None else above.ssl
            planes.append(Lin(0.0, 0.0, z - lv.z))
        for roof in self.g.roofs.values():
            rl = self.g.levels[roof.level]
            if rl.z <= lv.z + 1e-9 and roof.status != "demolish":
                planes.extend(Lin(p.a, p.b, p.c - roof.lining - lv.z) for p in roof.planes)
        return planes

    def _opening_sides(self) -> None:
        for o in self.g.openings.values():
            w = self.g.walls.get(o.host)
            if w is None:
                continue
            lo = w.plan_point(o.mid, w.lo - 0.05)
            hi = w.plan_point(o.mid, w.hi + 0.05)
            o.sides = (self.g.room_at(w.level, *lo), self.g.room_at(w.level, *hi))


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
        base,
        planes,
        eaves,
        over,
        skin,
        lining,
        d_max,
        el.status,
    )


def roof_profile(w: WallGeo, roof: RoofGeo) -> list[tuple[float, float]]:
    """Top of a wall cut by a roof: the rafter underside along the wall's centre line."""
    c = w.mid

    def z(s: float) -> float:
        return roof.underside(*w.plan_point(s, c))

    ss = {w.s0, w.s1}
    fs = roof.planes
    for i, a in enumerate(fs):
        for b in fs[i + 1 :]:
            # where a == b along the line: (a-b)(s) = 0, linear in s
            diff = a - b
            f0 = diff(*w.plan_point(w.s0, c))
            f1 = diff(*w.plan_point(w.s1, c))
            if (f0 > 0) != (f1 > 0) and f0 != f1:
                ss.add(w.s0 + (w.s1 - w.s0) * f0 / (f0 - f1))
    return [(s, z(s)) for s in sorted(ss)]


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
    for o in g.openings.values():
        out[o.id] = (q(o.lo), q(o.hi), q(o.sill), q(o.top))
    for s in g.stairs.values():
        out[s.id] = (q(s.x0), q(s.x1), q(s.y0), q(s.y1))
    for p in g.seps.values():
        out[p.id] = (q(p.pos), q(p.s0), q(p.s1))
    for rm in g.rooms.values():
        out[rm.id] = (round(rm.area_fin, 2),)
    for sl in g.slabs.values():
        out[sl.id] = (round(sl.net.area, 2),)
    for rf in g.roofs.values():
        out[rf.id] = (q(rf.x0), q(rf.x1), q(rf.y0), q(rf.y1), q(rf.base))
    return out

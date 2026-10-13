"""The surfaces around each room and what lies beyond them (decision 0033).

For the U-values and the Heizlast, every room is taken apart into surfaces: the pieces of the
walls on its outline, the windows and doors in them, its floor and its ceiling or roof. Each
surface knows its build-up, the direction of the heat flow and what lies beyond: outside air,
the ground, another room, or nothing UEA knows (no room there).

Dimensions: lengths along the room's shell outline (the core faces of its walls); a wall's
height from the storey's FFL to the FFL of the storey above, or to the wall's top where no storey
is above; floors and ceilings with the area of the shell outline; roofs with their sloped area
over it. The part of an exterior wall below the terrain (`ground=` of the project) borders the
ground. An interior door without a U-value counts as part of its wall.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from uea.core.values import Layer, Ref
from uea.derive import Derived
from uea.geom import polys, union
from uea.packs.arch.geometry import (
    LevelGeo,
    OpeningGeo,
    RoomGeo,
    Side,
    WallGeo,
    opening_type,
)
from uea.packs.arch.kinds import DoorType, FloorType, RoofType, Room
from uea.packs.heat.thermal import Far, Flow
from uea.packs.project import Project

TOL = 1e-3
STRIP = 0.3
"""How far beyond a wall's far core face a neighbouring room is looked for, m."""
MIN_AREA = 1e-4

Part = Literal["wall", "window", "door", "floor", "ceiling", "roof"]
Beyond = Literal["outside", "ground", "room", "none"]

PART_DE = {
    "wall": "Wand",
    "window": "Fenster",
    "door": "Tür",
    "floor": "Boden",
    "ceiling": "Decke",
    "roof": "Dach",
}


@dataclass
class Surface:
    room: str
    part: Part
    el: str
    """The wall, opening, slab or roof."""
    build: str
    """The build-up: its type or types (slab + floor), or the opening's type."""
    layers: tuple[Layer, ...]
    """Empty for windows and doors."""
    u_given: float | None
    """The U-value of a window's or door's type."""
    flow: Flow
    beyond: Beyond
    other: str | None
    """The room beyond."""
    area: float
    facing: tuple[float, float] | None = None
    """Outward plan direction of a wall or an opening in it."""

    @property
    def far(self) -> Far:
        """For R_se: nothing known beyond counts as outside air (the safe side)."""
        if self.beyond == "ground":
            return "ground"
        return "inside" if self.beyond == "room" else "outside"


@dataclass
class Envelope:
    rooms: dict[str, list[Surface]] = field(default_factory=dict[str, list[Surface]])
    notes: list[str] = field(default_factory=list[str])


def envelope(d: Derived) -> Envelope:
    env = Envelope()
    by_host: dict[str, list[OpeningGeo]] = defaultdict(list)
    for o in d.arch.openings.values():
        if o.kind in ("door", "win") and o.status != "demolish":
            by_host[o.host].append(o)
    for rid, rg in d.arch.rooms.items():
        out: list[Surface] = []
        _walls(d, rg, by_host, out, env.notes)
        _floor(d, rg, out, env.notes)
        _ceiling(d, rg, out, env.notes)
        env.rooms[rid] = out
    return env


def terrain(d: Derived) -> float | None:
    for p in d.model.of_kind("project"):
        if isinstance(p, Project):
            return p.ground
    return None


def _type(d: Derived, key: str) -> str:
    """The type a wall, slab or roof refers to."""
    t = getattr(d.model[key], "type", None)
    return t.id if isinstance(t, Ref) else ""


def _edges(poly: Polygon) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for ring in [poly.exterior, *poly.interiors]:
        pts = [(float(x), float(y)) for x, y in ring.coords]
        out.extend(pairwise(pts))
    return out


def _on_face(w: WallGeo, a: tuple[float, float], b: tuple[float, float]) -> Side | None:
    """The core face of w the edge a-b lies on, if any."""
    ca, cb = w.c_of(*a), w.c_of(*b)
    if abs(ca - cb) > TOL:
        return None
    if abs(ca - w.lo) < TOL:
        return "lo"
    if abs(ca - w.hi) < TOL:
        return "hi"
    return None


def _walls(
    d: Derived,
    rg: RoomGeo,
    by_host: dict[str, list[OpeningGeo]],
    out: list[Surface],
    notes: list[str],
) -> None:
    g = d.arch
    lv = g.levels[rg.level]
    walls = g.walls_on(rg.level)
    others: list[tuple[str, BaseGeometry]] = [
        (k, o.poly) for k, o in g.rooms.items() if o.level == rg.level and k != rg.id
    ]
    others += _reaching(d, lv)
    for a, b in _edges(rg.poly):
        for w in walls:
            side = _on_face(w, a, b)
            if side is None:
                continue
            i = 0 if side == "lo" else 1
            sa, sb = sorted((w.s_of(*a), w.s_of(*b)))
            s0, s1 = max(sa, w.s0 - w.ea[i]), min(sb, w.s1 + w.eb[i])
            if s1 - s0 > TOL:
                _wall_piece(d, rg, lv, w, side, s0, s1, others, walls, by_host, out, notes)


def _reaching(d: Derived, lv: LevelGeo) -> list[tuple[str, BaseGeometry]]:
    """Rooms of lower storeys that reach up into this one (split level: a hall under its own
    roof beside a storeyed wing), with the part of their outline that does."""
    g = d.arch
    out: list[tuple[str, BaseGeometry]] = []
    for k, o in g.rooms.items():
        low = g.levels[o.level]
        hr = o.height_range()
        if low.z >= lv.z - TOL or hr is None or low.z + hr[1] <= lv.z + TOL:
            continue
        up = o.poly.intersection(o.ceiling.uncapped)
        if up.area > MIN_AREA:
            out.append((k, up))
    return out


def _wall_piece(
    d: Derived,
    rg: RoomGeo,
    lv: LevelGeo,
    w: WallGeo,
    side: Side,
    s0: float,
    s1: float,
    others: list[tuple[str, BaseGeometry]],
    walls: list[WallGeo],
    by_host: dict[str, list[OpeningGeo]],
    out: list[Surface],
    notes: list[str],
) -> None:
    """The stretch s0..s1 of wall w on the room's outline, split by what lies beyond it."""
    c0, c1 = (w.hi, w.hi + STRIP) if side == "lo" else (w.lo - STRIP, w.lo)
    strip = Polygon(
        [w.plan_point(s0, c0), w.plan_point(s1, c0), w.plan_point(s1, c1), w.plan_point(s0, c1)]
    )
    spans: list[tuple[float, float, str | None]] = []
    for k, poly in others:
        for p in polys(strip.intersection(poly)):
            ss = [w.s_of(x, y) for x, y in p.exterior.coords]
            lo, hi = max(min(ss), s0), min(max(ss), s1)
            if hi - lo > TOL:
                spans.append((lo, hi, k))
    spans.sort()
    rest: list[tuple[float, float, str | None]] = []
    at = s0
    for lo, hi, _ in spans:
        if lo - at > TOL:
            rest.append((at, lo, None))
        at = max(at, hi)
    if s1 - at > TOL:
        rest.append((at, s1, None))
    # where another wall meets this one from the far side, its end is beyond: the stretch goes
    # with the room next to it
    walled = [
        (min(ss), max(ss))
        for x in walls
        if x.id != w.id
        for p in polys(strip.intersection(x.poly))
        for ss in [[w.s_of(px, py) for px, py in p.exterior.coords]]
    ]
    kept: list[tuple[float, float, str | None]] = []
    for lo, hi, _ in rest:
        inside = any(a - TOL <= lo and hi <= b + TOL for a, b in walled)
        near = [k for a, b, k in spans if abs(b - lo) < TOL or abs(a - hi) < TOL]
        if inside and near:
            spans.append((lo, hi, near[0]))
        else:
            kept.append((lo, hi, None))
    rest = kept
    exterior = w.ext is not None and w.ext != side
    n = w.n if side == "lo" else (-w.n[0], -w.n[1])
    build = _type(d, w.id)
    ground = terrain(d)
    near = w.lo - STRIP / 2 if side == "lo" else w.hi + STRIP / 2
    for lo, hi, other in sorted(spans + rest):
        beyond: Beyond = "room" if other else "outside" if exterior else "none"
        if beyond == "none":
            notes.append(f"{rg.id}: no room beyond {w.id} over {hi - lo:.2f} m, counted as outside")
        # split level: where the room reaches up to its own roof, the wall counts up to its top,
        # no higher than the room's ceiling
        reach = None
        hr = rg.height_range()
        if hr is not None and rg.ceiling.uncapped.covers(SPoint(w.plan_point((lo + hi) / 2, near))):
            reach = lv.z + hr[1]
        area, below = _wall_area(d, lv, w, lo, hi, ground if beyond == "outside" else None, reach)
        for o in by_host.get(w.id, []):
            if not lo - TOL <= o.mid <= hi + TOL:
                continue
            surf = _opening(d, rg, o, beyond, other, n)
            if surf is not None:
                out.append(surf)
                area -= surf.area
        if below > TOL:
            out.append(
                Surface(
                    rg.id,
                    "wall",
                    w.id,
                    build,
                    w.layers.items,
                    None,
                    "horizontal",
                    "ground",
                    None,
                    below,
                    n,
                )
            )
        if area > MIN_AREA:
            out.append(
                Surface(
                    rg.id,
                    "wall",
                    w.id,
                    build,
                    w.layers.items,
                    None,
                    "horizontal",
                    beyond,
                    other,
                    area,
                    n,
                )
            )


def _wall_area(
    d: Derived,
    lv: LevelGeo,
    w: WallGeo,
    lo: float,
    hi: float,
    ground: float | None,
    reach: float | None = None,
) -> tuple[float, float]:
    """The area of the wall from lo to hi above the terrain, and below it. reach: the room
    reaches up past the storey above to this height (split level)."""
    if lv.above is not None and reach is None:
        h = d.arch.levels[lv.above].z - lv.z
        under = min(max(ground - lv.z, 0.0), h) if ground is not None else 0.0
        return (hi - lo) * (h - under), (hi - lo) * under
    if not w.top:
        return 0.0, 0.0
    pts = [lo, *(s for s, _ in w.top if lo < s < hi), hi]
    total = 0.0
    for sa, sb in pairwise(pts):
        za, zb = w.top_at(sa), w.top_at(sb)
        assert za is not None and zb is not None
        if reach is not None:
            za, zb = min(za, reach), min(zb, reach)
        total += (sb - sa) * ((za + zb) / 2 - lv.z)
    under = 0.0
    if ground is not None and reach is not None:
        under = (hi - lo) * min(max(ground - lv.z, 0.0), reach - lv.z)
    return max(total - under, 0.0), under


def _opening(
    d: Derived,
    rg: RoomGeo,
    o: OpeningGeo,
    beyond: Beyond,
    other: str | None,
    n: tuple[float, float],
) -> Surface | None:
    el = d.model[o.id]
    t = opening_type(d.model, el)
    u = (t.ud or t.uw) if isinstance(t, DoorType) else t.uw if t is not None else None
    if beyond == "room" and u is None:
        return None  # an interior door without a U-value: part of the wall
    part: Part = "door" if o.kind == "door" else "window"
    area = o.width * (o.top - o.sill)
    build = t.id if t is not None else ""
    return Surface(rg.id, part, o.id, build, (), u, "horizontal", beyond, other, area, n)


def _floor_of(d: Derived, room: str) -> FloorType | None:
    el = d.model[room]
    if isinstance(el, Room) and el.floor is not None:
        t = d.model.get(el.floor.id)
        return t if isinstance(t, FloorType) else None
    return None


def _build(d: Derived, slab: str, floor_room: str) -> tuple[str, tuple[Layer, ...]]:
    """A slab with the floor of the room on it."""
    sg = d.arch.slabs[slab]
    name = _type(d, slab)
    layers = sg.layers.items
    ft = _floor_of(d, floor_room)
    if ft is not None:
        name, layers = f"{name} + {ft.id}", (*ft.layers.items, *layers)
    return name, layers


def _overlaps(
    d: Derived, level: str, region: BaseGeometry
) -> tuple[list[tuple[str, float]], float]:
    """The rooms of a storey over or under a region, with their share of its area; the part
    over or under that storey's walls is shared out in proportion. And what is left."""
    out: list[tuple[str, float]] = []
    for k, o in d.arch.rooms.items():
        if o.level == level:
            a = region.intersection(o.poly).area
            if a > MIN_AREA:
                out.append((k, a))
    rooms = union(d.arch.rooms[k].poly for k, _ in out)
    walls = union(w.poly for w in d.arch.walls_on(level)).difference(rooms)
    walled = region.intersection(walls).area
    got = sum(a for _, a in out)
    if got > 0:
        out = [(k, a * (got + walled) / got) for k, a in out]
        return out, max(region.area - got - walled, 0.0)
    return out, region.area


def _floor(d: Derived, rg: RoomGeo, out: list[Surface], notes: list[str]) -> None:
    g = d.arch
    lv = g.levels[rg.level]
    slab = g.slab_on(rg.level)
    if slab is None:
        notes.append(f"{rg.id}: no slab under it, so no floor")
        return
    name, layers = _build(d, slab.id, rg.id)
    rest = rg.poly.area
    if lv.below is not None:
        under, rest = _overlaps(d, lv.below, rg.poly)
        for k, a in under:
            out.append(Surface(rg.id, "floor", slab.id, name, layers, None, "down", "room", k, a))
    if rest > MIN_AREA:
        beyond: Beyond = "ground" if lv.below is None else "none"
        if beyond == "none":
            notes.append(f"{rg.id}: no room under {rest:.2f} m² of its floor, counted as outside")
        out.append(Surface(rg.id, "floor", slab.id, name, layers, None, "down", beyond, None, rest))


def _ceiling(d: Derived, rg: RoomGeo, out: list[Surface], notes: list[str]) -> None:
    g = d.arch
    lv = g.levels[rg.level]
    slab = g.slab_on(lv.above) if lv.above is not None else None
    # split level: the part of the room that reaches up to its own roof has no slab above
    uncapped = rg.ceiling.uncapped
    roofed: BaseGeometry = rg.poly
    if slab is not None and not uncapped.is_empty:
        roofed = rg.poly.intersection(uncapped)
        if roofed.area > MIN_AREA:
            _roofs(d, rg, roofed, out)
    if slab is not None:
        assert lv.above is not None
        capped = rg.poly.difference(uncapped) if not uncapped.is_empty else rg.poly
        if capped.area <= MIN_AREA:
            return
        over, rest = _overlaps(d, lv.above, capped)
        for k, a in over:
            name, layers = _build(d, slab.id, k)
            out.append(Surface(rg.id, "ceiling", slab.id, name, layers, None, "up", "room", k, a))
        if rest > MIN_AREA:
            name = _type(d, slab.id)
            out.append(
                Surface(
                    rg.id,
                    "ceiling",
                    slab.id,
                    name,
                    slab.layers.items,
                    None,
                    "up",
                    "outside",
                    None,
                    rest,
                )
            )
        return
    _roofs(d, rg, roofed, out)
    if not any(s.part == "roof" for s in out):
        notes.append(f"{rg.id}: neither a slab nor a roof above it, so no ceiling")


def _roofs(d: Derived, rg: RoomGeo, region: BaseGeometry, out: list[Surface]) -> None:
    """The roofs over a region of the room, with their sloped area."""
    roofs = d.arch.roofs_on(rg.level)
    for f, poly in rg.ceiling.pieces(region):
        c = poly.centroid
        roof = next((r for r in roofs if r.foot.buffer(TOL).covers(c)), None)
        if roof is None:
            continue
        t = d.model.get(_type(d, roof.id))
        if not isinstance(t, RoofType):
            continue
        area = poly.area * math.sqrt(1 + f.a * f.a + f.b * f.b)
        out.append(
            Surface(rg.id, "roof", roof.id, t.id, t.layers.items, None, "up", "outside", None, area)
        )

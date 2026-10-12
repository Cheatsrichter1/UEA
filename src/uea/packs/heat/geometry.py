"""What the heating elements add up to (decision 0034): where they are, what supplies what, the
loops of the underfloor heating, and the heat output of every emitter.

Underfloor heating: the pipe in the room is its area over the pipe spacing; each loop also runs
to the manifold and back, the rectilinear distance from the manifold to the room's finished
outline plus the height between them. The loops are as few as keep each within the type's
longest loop, all of the same length.

Heating pipes (decision 0037), derived like the plumbing: from each generator or tank, the
shortest rectilinear tree over what it supplies directly (tanks, manifolds, radiators), a flow
and a return pipe side by side; from each manifold, a home run (Anbindeleitung) to each radiator
on it. The underfloor loops are the manifold's own circuits.
"""

import math
from contextlib import suppress
from dataclasses import dataclass, field

from shapely.geometry import Point as SPoint
from shapely.ops import nearest_points

from uea.core.model import Model
from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived, GeoError, Unresolved
from uea.packs.arch.geometry import Resolver
from uea.packs.heat.kinds import (
    Gen,
    GenType,
    Man,
    ManType,
    Rad,
    RadType,
    Tank,
    TankType,
    Ufh,
    UfhType,
)
from uea.packs.mount import Mounted, Mounts
from uea.packs.net import Crossing, Net, Section, finish, gap, grow, node_of, routed, through

PLACED = ("gen", "tank", "man", "rad")


@dataclass
class Loops:
    """The loops of one underfloor heating."""

    area: float
    spacing: float
    reach: float
    """From the manifold to the room and up or down to its floor, one way, m."""
    n: int
    each: float
    """Length of each loop, connection lines included, m."""

    @property
    def pipe(self) -> float:
        return self.n * self.each


@dataclass
class HeatGeo:
    at: dict[str, Mounted] = field(default_factory=dict[str, Mounted])
    """Where the generators, tanks, manifolds and radiators are."""
    supplies: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """What each generator, tank and manifold supplies, in id order."""
    loops: dict[str, Loops] = field(default_factory=dict[str, Loops])
    output: dict[str, float] = field(default_factory=dict[str, float])
    """Heat output of each emitter at the design temperatures, W, where its type gives it (w=,
    q=); a type with DIN EN 442 or 1264 values gets its output from the calculators."""
    emitters: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """The emitters of each room."""
    too_far: list[str] = field(default_factory=list[str])
    """Underfloor heatings whose manifold is farther than half a loop."""
    nets: dict[str, Net] = field(default_factory=dict[str, Net])
    """The pipes from each generator, tank or manifold to what it supplies directly; a section
    stands for its flow and its return pipe."""
    crossings: list[Crossing] = field(default_factory=list[Crossing])
    """Where the pipes pass the slabs (decision 0039)."""

    def pipe_from(self, end: str) -> tuple[str, float] | None:
        """The net an element hangs from and the length of pipe to it, one way."""
        for root, net in self.nets.items():
            if end in net.nodes and end != root:
                return root, net.reach(end)
        return None


def heat_type[T: Element](m: Model, el: Element, cls: type[T], category: str) -> T | None:
    """The type of a heating element: its own, else the type of its kind marked default."""
    ref = getattr(el, "type", None)
    if ref is not None:
        t = m.get(ref.id)
        return t if isinstance(t, cls) else None
    for t in m.of_kind("type", category):
        if isinstance(t, cls) and getattr(t, "default", False):
            return t
    return None


def derive_heat(d: Derived) -> None:
    m = d.model
    h = d.heat = HeatGeo()
    place = Placer(d)
    for kind in PLACED:
        for el in m.of_kind(kind):
            with suppress(Unresolved):
                d.resolve(el.id, h.at, lambda el=el: place.place(el))
    for kind in ("tank", "man", "ufh", "rad"):
        for el in m.of_kind(kind):
            src = getattr(el, "src", None)
            if src is not None and src.id in m:
                h.supplies.setdefault(src.id, []).append(el.id)
    for lst in h.supplies.values():
        lst.sort(key=natural)
    for el in m.of_kind("ufh"):
        assert isinstance(el, Ufh)
        with suppress(Unresolved):
            d.resolve(el.id, h.loops, lambda el=el: _loops(d, el))
    for el in m.of_kind("rad"):
        assert isinstance(el, Rad)
        t = heat_type(m, el, RadType, "rad")
        mt = h.at.get(el.id)
        if t is not None:
            if t.w is not None:
                h.output[el.id] = t.w
            if mt is not None and t.length:
                mt.width = t.length
        if mt is not None and mt.room is not None:
            h.emitters.setdefault(mt.room, []).append(el.id)
    for el in m.of_kind("ufh"):
        assert isinstance(el, Ufh)
        lp = h.loops.get(el.id)
        t = heat_type(m, el, UfhType, "ufh")
        if lp is not None and t is not None and t.q is not None:
            h.output[el.id] = t.q * lp.area
        h.emitters.setdefault(el.room.id, []).append(el.id)
    for lst in h.emitters.values():
        lst.sort(key=natural)
    _pipes(d)


def _pipes(d: Derived) -> None:
    m, h = d.model, d.heat
    rank = {"gen": 0, "tank": 1, "man": 2}
    roots = [k for k in h.supplies if k in h.at and m[k].kind in rank]
    for root in sorted(roots, key=lambda k: (rank[m[k].kind], natural(k))):
        ends = [k for k in h.supplies[root] if k in h.at]  # an underfloor heating has no point
        if not ends:
            continue
        el = m[root]
        assert isinstance(el, Gen | Tank | Man)
        via = el.via.refs() if el.via else ()
        net = Net(root, {root: node_of(h.at[root])})
        for k in ends:
            net.nodes[k] = node_of(h.at[k])
        if el.kind == "man":
            for k in ends:
                length, legs = gap(net.nodes[root], net.nodes[k])
                net.sections.append(Section(root, k, length, legs, "home", [k]))
        else:
            grow(net, {root}, [root], ends, "pipe", routed(d, via))
            finish(net, set(ends))
        h.crossings += through(d, net, via)
        h.nets[root] = net


class Placer:
    def __init__(self, d: Derived) -> None:
        self.d = d
        self.mounts = Mounts(d)
        self.arch: Resolver = self.mounts.arch

    def place(self, el: Element) -> Mounted:
        g = self.d.arch
        if isinstance(el, Gen):
            lv = g.levels.get(el.level.id)
            if lv is None:
                raise Unresolved(el.level.id, missing=True)
            x, y = self.arch.point(el.at.x, "x"), self.arch.point(el.at.y, "y")
            return Mounted(el.id, el.kind, lv.id, (x, y), lv.z + el.z, g.room_at(lv.id, x, y))
        if isinstance(el, Tank):
            rg = g.rooms.get(el.host.id)
            if rg is None:
                raise Unresolved(el.host.id, missing=True)
            if el.at is not None:
                x, y = self.arch.point(el.at.x, "x"), self.arch.point(el.at.y, "y")
            else:
                c = rg.fin.centroid
                p = c if rg.fin.contains(c) else rg.fin.representative_point()
                x, y = p.x, p.y
            lv = g.levels[rg.level]
            return Mounted(el.id, el.kind, rg.level, (x, y), lv.z, rg.id, width=0.6)
        if isinstance(el, Man) and self.d.model.get(el.host.id) is not None:
            host = self.d.model[el.host.id]
            if host.kind == "niche":
                return self._in_niche(el)
        return self.mounts._on_wall(el.id, el)  # pyright: ignore[reportPrivateUsage]

    def _in_niche(self, el: Man) -> Mounted:
        if any(v is not None for v in (el.x, el.y, el.s, el.z)):
            raise GeoError(
                f"{el.id} is in the niche {el.host.id}, which places it: leave out x=, y=, s=, z=",
                f"~ {el.id} x= y= s= z=",
                "E-HEAT-002",
            )
        o = self.d.arch.openings.get(el.host.id)
        if o is None:
            raise Unresolved(el.host.id, missing=True)
        w = self.d.arch.walls[o.host]
        side = o.face or ("hi" if w.ext == "lo" else "lo")
        c = w.hi if side == "hi" else w.lo
        x, y = w.plan_point(o.mid, c)
        lv = self.d.arch.levels[o.level]
        sign = 1.0 if side == "hi" else -1.0
        room = self.d.arch.room_at(o.level, x + sign * w.n[0] * 0.05, y + sign * w.n[1] * 0.05)
        letter = w.faces[1] if side == "hi" else w.faces[0]
        z = lv.z + (o.sill + o.top) / 2
        return Mounted(
            el.id, el.kind, o.level, (x, y), z, room, w.id, side, letter, w.along, o.mid, o.width
        )


def _loops(d: Derived, el: Ufh) -> Loops:
    m, h = d.model, d.heat
    rg = d.arch.rooms.get(el.room.id)
    man = h.at.get(el.src.id)
    if rg is None:
        raise Unresolved(el.room.id, missing=True)
    if man is None:
        raise Unresolved(el.src.id, missing=el.src.id not in m)
    t = heat_type(m, el, UfhType, "ufh")
    if t is None:
        raise Unresolved(el.id, missing=True)  # W-HEAT-001 says so
    area = el.area if el.area is not None else rg.area_fin
    lv = d.arch.levels[rg.level]
    p = SPoint(man.point)
    near = p if rg.fin.covers(p) else nearest_points(rg.fin, p)[0]
    reach = abs(near.x - p.x) + abs(near.y - p.y) + abs(man.z - lv.z)
    pipe = area / t.spacing
    room_for = t.max - 2 * reach
    if room_for <= 0:
        h.too_far.append(el.id)
        return Loops(area, t.spacing, reach, 0, 0.0)
    n = max(1, math.ceil(pipe / room_for - 1e-9))
    return Loops(area, t.spacing, reach, n, pipe / n + 2 * reach)


def heat_signatures(d: Derived) -> dict[str, tuple[float | str, ...]]:
    h = d.heat
    out: dict[str, tuple[float | str, ...]] = {
        k: (round(v.point[0], 4), round(v.point[1], 4), round(v.z, 4)) for k, v in h.at.items()
    }
    for k, lp in h.loops.items():
        out[k] = (lp.n, round(lp.each, 3))
    for net in h.nets.values():
        for sec in net.sections:
            out[sec.name] = (round(sec.length, 3),)
    return out


def generator_kw(d: Derived) -> dict[str, float]:
    """The heat output of every generator with a type, kW."""
    out: dict[str, float] = {}
    for el in d.model.of_kind("gen"):
        t = heat_type(d.model, el, GenType, "gen")
        if t is not None:
            out[el.id] = t.kw
    return out


def tank_type(d: Derived, el: Element) -> TankType | None:
    return heat_type(d.model, el, TankType, "tank")


def man_type(d: Derived, el: Element) -> ManType | None:
    return heat_type(d.model, el, ManType, "man")

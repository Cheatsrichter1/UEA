"""Where the plumbing is and the pipes between (decision 0035).

The pipes are derived like the cables (decision 0027): each network is the shortest tree over
the rectilinear distances, so a pipe runs along x, y and z, and its length is a lower bound.

- Cold water: from the meter to every fixture that takes water and to every storage tank that
  heats drinking water. On the meter's storey the tree grows from the meter; a riser carries the
  water to the storeys above (or below), where the tree grows from the riser. What no riser
  reaches joins the nearest pipe directly.
- Hot water: from each tank that heats drinking water to the fixtures that take hot water and
  have it as their nearest such tank, the same way.
- Waste water: each fixture runs to its stack (Fallleitung) on its storey or to the sewer
  connection: to=, else the nearest in plan. The fixtures on one stack and storey form a tree to
  it (the branches, Anschlussleitungen); the stack runs down to its foot; the feet run to the
  sewer connection under the floor (Grundleitungen). Waste pipes lie at the storey's FFL.
"""

from contextlib import suppress
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

from uea.core.model import Model
from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived, Unresolved
from uea.packs.arch.geometry import Resolver
from uea.packs.heat.geometry import heat_type
from uea.packs.heat.kinds import TankType
from uea.packs.mount import Mounted, Mounts
from uea.packs.plumb.kinds import OUTLET_Z, Meter, Riser, San, Sewer, Stack

PLACED = ("meter", "riser", "stack", "sewer", "san")
SectionKind = Literal["pipe", "riser", "branch", "stack", "ground"]
EPS = 1e-6


@dataclass(frozen=True)
class Node:
    id: str
    """An element id, or a riser or stack on a storey: sr1:OG."""
    level: str
    point: tuple[float, float]
    z: float


@dataclass
class Section:
    """A pipe between two nodes of a network (a Teilstrecke)."""

    a: str
    """The end toward the meter, the tank or the sewer."""
    b: str
    length: float
    legs: int
    """How many of x, y and z it runs along; a bend between each two."""
    kind: SectionKind
    serves: list[str] = field(default_factory=list[str])
    """The fixtures and tanks beyond b: those it supplies, or whose waste water it carries."""

    @property
    def bends(self) -> int:
        return max(self.legs - 1, 0)

    @property
    def name(self) -> str:
        return f"{self.a}>{self.b}"


@dataclass
class Net:
    root: str
    nodes: dict[str, Node] = field(default_factory=dict[str, Node])
    sections: list[Section] = field(default_factory=list[Section])
    """Each after the section it hangs from."""

    def up(self) -> dict[str, Section]:
        return {s.b: s for s in self.sections}

    def path(self, end: str) -> list[Section]:
        """The sections from the root to end, in order."""
        up = self.up()
        out: list[Section] = []
        k = end
        while k in up:
            out.append(up[k])
            k = up[k].a
        return out[::-1]

    def reach(self, end: str) -> float:
        return sum(s.length for s in self.path(end))

    def has(self, end: str) -> bool:
        return end == self.root or end in self.up()

    @property
    def total(self) -> float:
        return sum(s.length for s in self.sections)


@dataclass
class PlumbGeo:
    at: dict[str, Mounted] = field(default_factory=dict[str, Mounted])
    """Where the fixtures, the meter, the risers and stacks (on their lowest storey) and the
    sewer connection are."""
    cold: Net | None = None
    hot: dict[str, Net] = field(default_factory=dict[str, Net])
    """By the tank they come from."""
    drain: Net | None = None
    tanks: list[str] = field(default_factory=list[str])
    """The storage tanks that heat drinking water."""
    hot_from: dict[str, str] = field(default_factory=dict[str, str])
    drains_to: dict[str, str] = field(default_factory=dict[str, str])
    """The stack or sewer each fixture's waste water runs to."""
    stray: dict[str, str] = field(default_factory=dict[str, str])
    """Fixtures whose waste water has nowhere to go, and why."""


def gap(a: Node, b: Node) -> tuple[float, int]:
    """Rectilinear distance and how many axes it runs along."""
    legs = [abs(a.point[0] - b.point[0]), abs(a.point[1] - b.point[1]), abs(a.z - b.z)]
    return sum(legs), sum(x > EPS for x in legs)


def derive_plumb(d: Derived) -> None:
    m = d.model
    p = d.plumb = PlumbGeo()
    place = Placer(d)
    for kind in PLACED:
        for el in m.of_kind(kind):
            with suppress(Unresolved):
                d.resolve(el.id, p.at, lambda el=el: place.place(el))
    fixtures = [el for el in m.of_kind("san") if isinstance(el, San) and el.id in p.at]
    p.tanks = sorted(
        (
            el.id
            for el in m.of_kind("tank")
            if el.id in d.heat.at and getattr(heat_type(m, el, TankType, "tank"), "dhw", False)
        ),
        key=natural,
    )
    node = {k: _node(v) for k, v in p.at.items()}
    for t in p.tanks:
        node[t] = _node(d.heat.at[t])
    risers = [node[el.id] for el in m.of_kind("riser") if el.id in node]
    # hot water from the nearest tank that heats drinking water
    for el in fixtures:
        if el.supply == "both" and p.tanks:
            p.hot_from[el.id] = min(
                p.tanks, key=lambda t: (gap(node[el.id], node[t])[0], natural(t))
            )
    meters = [el.id for el in m.of_kind("meter") if el.id in node]
    if meters:
        ends = [node[el.id] for el in fixtures if el.supply != "none"]
        ends += [node[t] for t in p.tanks]
        p.cold = supply(d, node[meters[0]], ends, risers)
    for t in p.tanks:
        ends = [node[k] for k, v in p.hot_from.items() if v == t]
        if ends:
            p.hot[t] = supply(d, node[t], ends, risers)
    p.drain = drainage(d, [el for el in fixtures if el.drains], node)


class Placer:
    def __init__(self, d: Derived) -> None:
        self.d = d
        self.mounts = Mounts(d)
        self.arch: Resolver = self.mounts.arch

    def place(self, el: Element) -> Mounted:
        g = self.d.arch
        if isinstance(el, Sewer):
            lv = g.levels.get(el.level.id)
            if lv is None:
                raise Unresolved(el.level.id, missing=True)
            x, y = self.arch.point(el.at.x, "x"), self.arch.point(el.at.y, "y")
            return Mounted(el.id, el.kind, lv.id, (x, y), lv.z, g.room_at(lv.id, x, y))
        if isinstance(el, San):
            host = self.d.model.get(el.host.id)
            z = el.z if el.z is not None else OUTLET_Z[el.fixture]
            if host is not None and host.kind == "wall":
                return self.mounts._on_wall(el.id, el.model_copy(update={"z": z}))  # pyright: ignore[reportPrivateUsage]
            return self._in_room(el, el.host.id, el.at, z)
        if isinstance(el, Meter):
            return self._in_room(el, el.host.id, el.at, el.z)
        assert isinstance(el, Riser | Stack)
        return self._in_room(el, el.host.id, el.at, 0.0)

    def _in_room(self, el: Element, room: str, at: object, z: float) -> Mounted:
        g = self.d.arch
        rg = g.rooms.get(room)
        if rg is None:
            raise Unresolved(room, missing=True)
        point = getattr(at, "x", None), getattr(at, "y", None)
        if point[0] is not None and point[1] is not None:
            x, y = self.arch.point(point[0], "x"), self.arch.point(point[1], "y")
        else:
            c = rg.fin.centroid
            q = c if rg.fin.contains(c) else rg.fin.representative_point()
            x, y = q.x, q.y
        lv = g.levels[rg.level]
        return Mounted(el.id, el.kind, rg.level, (x, y), lv.z + z, rg.id, width=0.3)


def _node(mt: Mounted) -> Node:
    return Node(mt.id, mt.level, mt.point, mt.z)


def _grow(net: Net, done: set[str], inside: list[str], left: list[str], kind: SectionKind) -> None:
    """Prim's algorithm: join each of left to the nearest node inside, ties to the lower id."""
    inside = sorted(inside, key=natural)
    left = sorted(set(left) - done, key=natural)
    while left:
        best = min(
            (gap(net.nodes[u], net.nodes[v]), natural(v), natural(u), u, v)
            for u in inside
            for v in left
        )
        (length, legs), _, _, u, v = best
        net.sections.append(Section(u, v, length, legs, kind))
        inside.append(v)
        left.remove(v)
        done.add(v)


def _vertical(net: Net, done: set[str], a: str, b: str, kind: SectionKind) -> None:
    length, legs = gap(net.nodes[a], net.nodes[b])
    net.sections.append(Section(a, b, length, legs, kind))
    done.add(b)


def _finish(net: Net, ends: set[str]) -> None:
    """Drop the pipes that lead to no fixture, then say what each section serves."""
    while True:
        heads = {s.a for s in net.sections}
        dead = [s for s in net.sections if s.b not in heads and s.b not in ends]
        if not dead:
            break
        net.sections = [s for s in net.sections if s not in dead]
    used = {net.root} | {s.b for s in net.sections}
    net.nodes = {k: v for k, v in net.nodes.items() if k in used}
    below: dict[str, list[Section]] = {}
    for s in net.sections:
        below.setdefault(s.a, []).append(s)

    def serves(k: str) -> list[str]:
        out = [k] if k in ends else []
        for s in below.get(k, []):
            s.serves = sorted(serves(s.b), key=natural)
            out += s.serves
        return out

    serves(net.root)


def supply(d: Derived, root: Node, ends: list[Node], risers: list[Node]) -> Net:
    """The tree of a drinking-water network from its root over the ends (see the module)."""
    order = d.arch.level_order()
    idx = {k: i for i, k in enumerate(order)}
    net = Net(root.id, {root.id: root})
    for e in ends:
        net.nodes[e.id] = e
    top = max([idx[root.level], *(idx[e.level] for e in ends)])
    on: dict[str, list[str]] = {}
    for r in sorted(risers, key=lambda r: natural(r.id)):
        for lv in order[idx[r.level] : top + 1]:
            k = f"{r.id}:{lv}"
            net.nodes[k] = Node(k, lv, r.point, d.arch.levels[lv].z)
            on.setdefault(lv, []).append(k)
    done = {root.id}
    base = idx[root.level]
    for lv in sorted(order, key=lambda k: (abs(idx[k] - base), idx[k])):
        if idx[lv] != base:
            near = order[idx[lv] + (1 if idx[lv] < base else -1)]
            for k in on.get(lv, []):
                rid = k.partition(":")[0]
                if f"{rid}:{near}" in done:
                    _vertical(net, done, f"{rid}:{near}", k, "riser")
        inside = [k for k in done if net.nodes[k].level == lv]
        if inside:
            left = [e.id for e in ends if e.level == lv] + on.get(lv, [])
            _grow(net, done, inside, left, "pipe")
    _grow(net, done, list(done), [e.id for e in ends], "pipe")
    _finish(net, {e.id for e in ends})
    return net


def drainage(d: Derived, fixtures: list[San], node: dict[str, Node]) -> Net | None:
    """The tree of the waste water from the fixtures to the sewer connection (see the module)."""
    p = d.plumb
    m = d.model
    sewers = [el for el in m.of_kind("sewer") if el.id in node]
    stacks = {el.id: node[el.id] for el in m.of_kind("stack") if el.id in node}
    order = d.arch.level_order()
    idx = {k: i for i, k in enumerate(order)}
    sewer = node[sewers[0].id] if sewers else None

    def reaches(k: str, lv: str) -> bool:
        if k in stacks:
            return idx[stacks[k].level] <= idx[lv]
        return sewer is not None and k == sewer.id and sewer.level == lv

    takers: list[str] = sorted(stacks, key=natural) + ([sewer.id] if sewer else [])
    for el in fixtures:
        f = node[el.id]
        if el.to is not None:
            if el.to.id not in node:
                continue
            if not reaches(el.to.id, f.level):
                p.stray[el.id] = f"{el.to.id} does not reach {f.level}"
                continue
            p.drains_to[el.id] = el.to.id
            continue
        ok = [k for k in takers if reaches(k, f.level)]
        if not ok:
            p.stray[el.id] = "no stack reaches its storey and no sewer connection is on it"
            continue
        p.drains_to[el.id] = min(ok, key=lambda k: (_plan(f, node[k]), natural(k)))
    if sewer is None:
        for k in p.drains_to:
            p.stray[k] = "there is no sewer connection"
        p.drains_to = {}
        return None
    net = Net(sewer.id, {sewer.id: sewer})
    done = {sewer.id}
    feet: list[str] = []
    for sid, st in stacks.items():
        mine = [node[k].level for k, v in p.drains_to.items() if v == sid]
        if not mine:
            continue
        levels = order[idx[st.level] : max(idx[x] for x in mine) + 1]
        for lv in levels:
            k = f"{sid}:{lv}"
            net.nodes[k] = Node(k, lv, st.point, d.arch.levels[lv].z)
        feet.append(f"{sid}:{levels[0]}")
    _grow(net, done, [sewer.id], feet, "ground")
    for sid in sorted(stacks, key=natural):
        levels = [k for k in net.nodes if k.startswith(f"{sid}:")]
        levels.sort(key=lambda k: idx[k.partition(":")[2]])
        for a, b in pairwise(levels):
            _vertical(net, done, a, b, "stack")
    for k in sorted(p.drains_to, key=natural):
        f = node[k]
        net.nodes[k] = Node(k, f.level, f.point, d.arch.levels[f.level].z)
    for taker in takers:
        by_level: dict[str, list[str]] = {}
        for k, v in p.drains_to.items():
            if v == taker:
                by_level.setdefault(net.nodes[k].level, []).append(k)
        for lv, ks in by_level.items():
            start = taker if taker == sewer.id else f"{taker}:{lv}"
            _grow(net, done, [start], ks, "branch")
    _finish(net, set(p.drains_to))
    return net


def _plan(a: Node, b: Node) -> float:
    return abs(a.point[0] - b.point[0]) + abs(a.point[1] - b.point[1])


def plumb_signatures(d: Derived) -> dict[str, tuple[float | str, ...]]:
    p = d.plumb
    out: dict[str, tuple[float | str, ...]] = {
        k: (round(v.point[0], 4), round(v.point[1], 4), round(v.z, 4)) for k, v in p.at.items()
    }
    for net in nets(d):
        for s in net.sections:
            out[s.name] = (round(s.length, 3),)
    return out


def nets(d: Derived) -> list[Net]:
    p = d.plumb
    return [n for n in (p.cold, *p.hot.values(), p.drain) if n is not None]


def plumb_type[T: Element](m: Model, el: Element | None, cls: type[T], category: str) -> T | None:
    """The type of a pipe network: its element's own, else the type of its kind marked default."""
    return heat_type(m, el, cls, category) if el is not None else _default(m, cls, category)


def _default[T: Element](m: Model, cls: type[T], category: str) -> T | None:
    for t in m.of_kind("type", category):
        if isinstance(t, cls) and getattr(t, "default", False):
            return t
    return None

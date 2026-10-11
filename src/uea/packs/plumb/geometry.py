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

from uea.core.model import Model
from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived, Unresolved
from uea.packs.arch.geometry import Resolver
from uea.packs.heat.geometry import heat_type
from uea.packs.heat.kinds import TankType
from uea.packs.mount import Mounted, Mounts
from uea.packs.net import Net, Node, finish, gap, grow, node_of, vertical
from uea.packs.plumb.kinds import OUTLET_Z, Meter, Riser, San, Sewer, Stack

PLACED = ("meter", "riser", "stack", "sewer", "san")


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
    node = {k: node_of(v) for k, v in p.at.items()}
    for t in p.tanks:
        node[t] = node_of(d.heat.at[t])
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
                    vertical(net, done, f"{rid}:{near}", k, "riser")
        inside = [k for k in done if net.nodes[k].level == lv]
        if inside:
            left = [e.id for e in ends if e.level == lv] + on.get(lv, [])
            grow(net, done, inside, left, "pipe")
    grow(net, done, list(done), [e.id for e in ends], "pipe")
    finish(net, {e.id for e in ends})
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
    grow(net, done, [sewer.id], feet, "ground")
    for sid in sorted(stacks, key=natural):
        levels = [k for k in net.nodes if k.startswith(f"{sid}:")]
        levels.sort(key=lambda k: idx[k.partition(":")[2]])
        for a, b in pairwise(levels):
            vertical(net, done, a, b, "stack")
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
            grow(net, done, [start], ks, "branch")
    finish(net, set(p.drains_to))
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

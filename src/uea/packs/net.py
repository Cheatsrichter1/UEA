"""Derived networks of pipes, cables and ducts: trees of sections over the rectilinear distances
between nodes (decisions 0027, 0035, 0037). A section runs along x, y and z, so its length is a
lower bound, and it knows how many of the axes it runs along (a bend between each two).

A section that changes storey passes the slabs between (decision 0039): a vertical one (a riser,
a stack) where it stands, any other through the nearest of the holes or voids its network names
(`via=`), which lengthens it by the detour.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon

from uea.core.issues import Issue
from uea.core.registry import natural
from uea.derive import Derived
from uea.fmt import ln
from uea.packs.mount import Mounted

SectionKind = Literal["pipe", "riser", "branch", "stack", "ground", "home", "duct"]
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
    via: list[str] = field(default_factory=list[str])
    """The slab holes it changes storey through."""

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


def gap(a: Node, b: Node) -> tuple[float, int]:
    """Rectilinear distance and how many axes it runs along."""
    legs = [abs(a.point[0] - b.point[0]), abs(a.point[1] - b.point[1]), abs(a.z - b.z)]
    return sum(legs), sum(x > EPS for x in legs)


def node_of(mt: Mounted) -> Node:
    return Node(mt.id, mt.level, mt.point, mt.z)


def grow(
    net: Net,
    done: set[str],
    inside: list[str],
    left: list[str],
    kind: SectionKind,
    dist: Callable[[Node, Node], tuple[float, int]] = gap,
) -> None:
    """Prim's algorithm: join each of left to the nearest node inside, ties to the lower id."""
    inside = sorted(inside, key=natural)
    left = sorted(set(left) - done, key=natural)
    while left:
        best = min(
            (dist(net.nodes[u], net.nodes[v]), natural(v), natural(u), u, v)
            for u in inside
            for v in left
        )
        (length, legs), _, _, u, v = best
        net.sections.append(Section(u, v, length, legs, kind))
        inside.append(v)
        left.remove(v)
        done.add(v)


def vertical(net: Net, done: set[str], a: str, b: str, kind: SectionKind) -> None:
    length, legs = gap(net.nodes[a], net.nodes[b])
    net.sections.append(Section(a, b, length, legs, kind))
    done.add(b)


def finish(net: Net, ends: set[str]) -> None:
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


@dataclass
class Crossing:
    """A section passing a slab (decision 0039)."""

    root: str
    by: str
    """What passes: a riser or stack where the section is vertical, else the network's root."""
    section: Section
    slab: str
    point: tuple[float, float] | None
    """Where it passes, if known: a vertical section's point, or its hole's centre."""
    hole: str | None


def through(d: Derived, net: Net, via: Sequence[str] = ()) -> list[Crossing]:
    """Every slab the sections of net pass, each with its hole. A section that is not vertical
    goes through the nearest hole of via= in each slab, and grows by the detour."""
    out: list[Crossing] = []
    for s in net.sections:
        a, b = net.nodes[s.a], net.nodes[s.b]
        passes = _passes(d, a, b, via)
        if not passes:
            continue
        by = s.b.partition(":")[0] if gap(a, b)[1] <= 1 else net.root
        for slab, point, hole in passes:
            out.append(Crossing(net.root, by, s, slab, point, hole))
        s.via = [h for _, _, h in passes if h is not None]
        s.length, s.legs = _detour(a, b, passes)
    return out


def routed(d: Derived, via: Sequence[str]) -> Callable[[Node, Node], tuple[float, int]]:
    """The distance of two nodes through the holes of via=, for grow()."""
    if not via:
        return gap
    return lambda a, b: _detour(a, b, _passes(d, a, b, via))


Pass = tuple[str, tuple[float, float] | None, str | None]
"""A slab a section passes: its id, where (if known) and the hole (if any)."""


def _passes(d: Derived, a: Node, b: Node, via: Sequence[str]) -> list[Pass]:
    g = d.arch
    order = g.level_order()
    if a.level == b.level or a.level not in order or b.level not in order:
        return []
    ia, ib = order.index(a.level), order.index(b.level)
    slabs = [g.slab_on(lv) for lv in order[min(ia, ib) + 1 : max(ia, ib) + 1]]
    if ia > ib:
        slabs.reverse()
    upright = gap(a, b)[1] <= 1
    out: list[Pass] = []
    prev = a.point
    for sl in slabs:
        if sl is None:
            continue
        here = [
            (h.id, h.poly) for h in g.holes.values() if h.host == sl.id and h.status != "demolish"
        ]
        here += [(v.id, v.poly) for v in g.voids.values() if v.slab == sl.id]
        if upright:
            p = SPoint(a.point)
            hole = next((k for k, poly in here if poly.buffer(1e-6).covers(p)), None)
            out.append((sl.id, a.point, hole))
            continue
        mine = [(k, _mid(poly)) for k, poly in here if k in via]
        if not mine:
            out.append((sl.id, None, None))
            continue
        k, c = min(mine, key=lambda x: (_plan(prev, x[1]) + _plan(x[1], b.point), natural(x[0])))
        prev = c
        out.append((sl.id, c, k))
    return out


def _detour(a: Node, b: Node, passes: list[Pass]) -> tuple[float, int]:
    pts = [a.point, *(p for _, p, _ in passes if p is not None), b.point]
    legs = [abs(p[i] - q[i]) for p, q in pairwise(pts) for i in (0, 1)]
    legs.append(abs(a.z - b.z))
    return sum(legs), sum(x > EPS for x in legs)


def _mid(poly: Polygon) -> tuple[float, float]:
    c = poly.centroid
    return (c.x, c.y)


def _plan(p: tuple[float, float], q: tuple[float, float]) -> float:
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def missing_holes(cs: list[Crossing], code: str, disc: str, via: bool = True) -> list[Issue]:
    """An issue for each slab a section passes with no hole: the handoff to arch (0039)."""
    out: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for c in cs:
        key = (c.section.name, c.slab)
        if c.hole is not None or key in seen:
            continue
        seen.add(key)
        if c.point is not None:
            el = c.by
            x, y = ln(c.point[0]), ln(c.point[1])
            msg = f"{c.section.name} passes {c.slab} at {x},{y}, and no hole is there"
            fix = f'ask arch for one: + req _ {disc} {c.slab} "Durchbruch für {el} bei {x}/{y}"'
        elif via:
            el = c.root
            msg = (
                f"{c.section.name} changes storey through {c.slab}, and no hole in it is in"
                f" via= of {el}"
            )
            fix = f'+ req _ {disc} {c.slab} "Durchbruch für ...", then ~ {el} via=<hole>'
        else:
            el = c.section.b
            msg = f"{c.section.name} changes storey through {c.slab} away from a riser"
            fix = "run it up a riser: + riser <room> at=<x,y>"
        out.append(Issue(code, el, msg, fix, (c.slab,)))
    return out


def hole_users(d: Derived) -> dict[str, list[str]]:
    """What passes each hole or void: risers, stacks, the roots of networks, facade units."""
    out: dict[str, set[str]] = {}
    for c in (*d.heat.crossings, *d.plumb.crossings, *d.vent.crossings):
        if c.hole is not None:
            out.setdefault(c.hole, set()).add(c.by)
    for k, h in d.vent.holes.items():
        if h is not None:
            out.setdefault(h, set()).add(k)
    return {k: sorted(v, key=natural) for k, v in out.items()}

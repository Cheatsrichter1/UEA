"""Derived networks of pipes, cables and ducts: trees of sections over the rectilinear distances
between nodes (decisions 0027, 0035, 0037). A section runs along x, y and z, so its length is a
lower bound, and it knows how many of the axes it runs along (a bend between each two).

A section that changes storey passes the slabs between (decision 0039): a vertical one (a riser,
a stack) where it stands, any other through the nearest of the holes or voids its network names
(`via=`), which lengthens it by the detour.
"""

import heapq
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Literal

from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as SPoint

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
    path: list[tuple[float, float]] | None = None
    """Its way on plan along the installation zones, when it follows them (decision 0045)."""

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
    """Prim's algorithm: join each of left to the nearest node inside, ties to the lower id. A
    distance that follows the installation zones also gives the way (`Zoned.path`)."""
    keys = {k: natural(k) for k in (*inside, *left)}
    waiting = set(left) - done
    # for each node still waiting, its nearest node inside: (distance, its key, its id)
    near: dict[str, tuple[tuple[float, int], tuple[Any, ...], str]] = {}

    def offer(u: str) -> None:
        for v in waiting:
            cand = (dist(net.nodes[u], net.nodes[v]), keys[u], u)
            if v not in near or cand < near[v]:
                near[v] = cand

    for u in inside:
        offer(u)
    while waiting:
        v = min(waiting, key=lambda k: (near[k][0], keys[k], near[k][1]))
        (length, legs), _, u = near.pop(v)
        sec = Section(u, v, length, legs, kind)
        if isinstance(dist, Zoned):
            sec.path = dist.path(net.nodes[u], net.nodes[v])
        net.sections.append(sec)
        waiting.remove(v)
        done.add(v)
        offer(v)


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
        here += [
            (sh.id, sh.poly)
            for sh in g.shafts.values()
            if sl.id in sh.slabs and sh.status != "demolish"
        ]
        if upright:
            p = SPoint(a.point)
            hole = next((k for k, poly in here if poly.buffer(1e-6).covers(p)), None)
            out.append((sl.id, a.point, hole))
            continue
        # the holes the network names, and every shaft (decision 0045)
        mine = [(k, _mid(poly)) for k, poly in here if k in via or k in g.shafts]
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


# ---------- installation zones (decision 0045) ----------

Pt = tuple[float, float]
Key = tuple[float, float, float]


@dataclass
class _Seg:
    a: Pt
    b: Pt
    z: float


class Zoned:
    """The distance between two nodes along the installation zones of their storey: straight
    (rectilinear) to the nearest point of a zone, along the zones, and straight on to the other
    node. Zones that cross or touch join; a zone at another height joins by the difference.
    Nodes on different storeys, or on a storey without zones, keep the rectilinear distance of
    `base`. The pre-wall installations are zones too, along their middle at half their height.
    """

    def __init__(self, d: Derived, base: Callable[[Node, Node], tuple[float, int]] = gap) -> None:
        self.base = base
        self.segs: dict[str, list[_Seg]] = {}
        for zg in d.arch.zones.values():
            self.segs.setdefault(zg.level, []).append(_Seg(zg.a, zg.b, zg.z))
        for pw in d.arch.prewalls.values():
            if pw.status == "demolish":
                continue
            w = d.arch.walls[pw.wall]
            mid = pw.front - (pw.depth / 2 if pw.side == "hi" else -pw.depth / 2)
            a, b = w.plan_point(pw.lo, mid), w.plan_point(pw.hi, mid)
            self.segs.setdefault(pw.level, []).append(_Seg(a, b, (pw.z0 + pw.z1) / 2))
        self.graphs = {lv: _graph(segs) for lv, segs in self.segs.items()}
        """Per storey: the graph's edges, and each segment's nodes in order along it."""
        self._memo: dict[tuple[str, str], tuple[float, int, list[Pt]] | None] = {}

    def __call__(self, a: Node, b: Node) -> tuple[float, int]:
        got = self._route(a, b)
        if got is None:
            return self.base(a, b)
        return got[0], got[1]

    def path(self, a: Node, b: Node) -> list[Pt] | None:
        got = self._route(a, b)
        return got[2] if got is not None else None

    def _route(self, a: Node, b: Node) -> tuple[float, int, list[Pt]] | None:
        if a.level != b.level or a.level not in self.segs:
            return None
        key = (a.id, b.id)
        if key not in self._memo:
            self._memo[key] = self._solve(a, b)
        return self._memo[key]

    def _solve(self, a: Node, b: Node) -> tuple[float, int, list[Pt]] | None:
        segs = self.segs[a.level]
        edges, along = self.graphs[a.level]
        ea, eb = _enter(segs, a), _enter(segs, b)
        # each entry joins the graph at the nodes of its segment on either side of it
        extra: dict[Key, list[tuple[Key, float]]] = {}
        for _, p, i in (ea, eb):
            sg = segs[i]
            line = LineString([sg.a, sg.b])
            at = line.project(SPoint(p))
            k = (p[0], p[1], sg.z)
            keys = along[i]
            before = [q for q in keys if line.project(SPoint(q[0], q[1])) <= at + EPS]
            after = [q for q in keys if line.project(SPoint(q[0], q[1])) >= at - EPS]
            for q in before[-1:] + after[:1]:
                length = abs(p[0] - q[0]) + abs(p[1] - q[1])
                extra.setdefault(k, []).append((q, length))
                extra.setdefault(q, []).append((k, length))
        pa, sa = ea[1], ea[2]
        pb, sb = eb[1], eb[2]
        ka, kb = (pa[0], pa[1], segs[sa].z), (pb[0], pb[1], segs[sb].z)
        if sa == sb:
            direct = abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])
            extra.setdefault(ka, []).append((kb, direct))
            extra.setdefault(kb, []).append((ka, direct))
        way = _dijkstra(edges, extra, ka, kb)
        if way is None:
            return None
        length, keys = way
        total = ea[0] + length + eb[0]
        pts = [a.point, *[(k[0], k[1]) for k in keys], b.point]
        clean: list[Pt] = []
        for p in pts:
            if not clean or abs(clean[-1][0] - p[0]) + abs(clean[-1][1] - p[1]) > EPS:
                clean.append(p)
        return total, len(clean) + 1, clean


def _enter(segs: list[_Seg], n: Node) -> tuple[float, Pt, int]:
    """The nearest point of the zones to a node, rectilinear in plan and in height, with the
    index of its segment."""
    best: tuple[float, Pt, int] | None = None
    for i, sg in enumerate(segs):
        line = LineString([sg.a, sg.b])
        q = line.interpolate(line.project(SPoint(n.point)))
        p = (float(q.x), float(q.y))
        cost = abs(n.point[0] - p[0]) + abs(n.point[1] - p[1]) + abs(n.z - sg.z)
        if best is None or cost < best[0] - EPS:
            best = (cost, p, i)
    assert best is not None
    return best


def _graph(
    segs: list[_Seg],
) -> tuple[dict[Key, list[tuple[Key, float]]], list[list[Key]]]:
    """The zones as a graph: each split where another zone meets it, a zone at another height
    joined by the difference."""
    cuts: list[list[Pt]] = [[s.a, s.b] for s in segs]
    joins: list[tuple[Key, Key]] = []
    for i, si in enumerate(segs):
        li = LineString([si.a, si.b])
        for j in range(i + 1, len(segs)):
            sj = segs[j]
            hit = li.intersection(LineString([sj.a, sj.b]))
            for c in _points(hit):
                cuts[i].append(c)
                cuts[j].append(c)
                if abs(si.z - sj.z) > EPS:
                    joins.append(((c[0], c[1], si.z), (c[0], c[1], sj.z)))
    edges: dict[Key, list[tuple[Key, float]]] = {}
    along: list[list[Key]] = []
    for sg, pts in zip(segs, cuts, strict=True):
        line = LineString([sg.a, sg.b])
        ordered = sorted(
            {(round(p[0], 6), round(p[1], 6)) for p in pts}, key=lambda p: line.project(SPoint(p))
        )
        along.append([(p[0], p[1], sg.z) for p in ordered])
        for p, q in pairwise(ordered):
            u, v = (p[0], p[1], sg.z), (q[0], q[1], sg.z)
            length = abs(p[0] - q[0]) + abs(p[1] - q[1])
            edges.setdefault(u, []).append((v, length))
            edges.setdefault(v, []).append((u, length))
    for u, v in joins:
        u = (round(u[0], 6), round(u[1], 6), u[2])
        v = (round(v[0], 6), round(v[1], 6), v[2])
        edges.setdefault(u, []).append((v, abs(u[2] - v[2])))
        edges.setdefault(v, []).append((u, abs(u[2] - v[2])))
    return edges, along


def _points(geom: object) -> list[Pt]:
    if isinstance(geom, SPoint):
        return [(float(geom.x), float(geom.y))]
    if isinstance(geom, LineString):
        return [(float(x), float(y)) for x, y in geom.coords]
    out: list[Pt] = []
    for part in getattr(geom, "geoms", []):
        out += _points(part)
    return out


def _dijkstra(
    edges: dict[Key, list[tuple[Key, float]]],
    extra: dict[Key, list[tuple[Key, float]]],
    start: Key,
    goal: Key,
) -> tuple[float, list[Key]] | None:
    dist: dict[Key, float] = {start: 0.0}
    prev: dict[Key, Key] = {}
    heap: list[tuple[float, Key]] = [(0.0, start)]
    while heap:
        du, u = heapq.heappop(heap)
        if u == goal:
            way = [u]
            while way[-1] in prev:
                way.append(prev[way[-1]])
            return du, way[::-1]
        if du > dist.get(u, float("inf")) + EPS:
            continue
        for v, w in [*edges.get(u, []), *extra.get(u, [])]:
            nd = du + w
            if nd < dist.get(v, float("inf")) - EPS:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return None

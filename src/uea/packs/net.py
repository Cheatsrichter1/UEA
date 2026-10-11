"""Derived networks of pipes, cables and ducts: trees of sections over the rectilinear distances
between nodes (decisions 0027, 0035, 0037). A section runs along x, y and z, so its length is a
lower bound, and it knows how many of the axes it runs along (a bend between each two).
"""

from dataclasses import dataclass, field
from typing import Literal

from uea.core.registry import natural
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


def grow(net: Net, done: set[str], inside: list[str], left: list[str], kind: SectionKind) -> None:
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

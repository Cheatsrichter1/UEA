"""Cable routes: how long each circuit's cable is (decision 0027).

The cable of a circuit is a tree that starts at its board and reaches every device and luminaire
on it. The tree is the shortest one over the rectilinear distances (Prim's algorithm): a cable
runs horizontally along the walls and vertically beside them, so a run is the sum of its legs in
x, y and z, not the straight line. Each run gets a fixed allowance for the ends at both devices.
Nothing here is stored; the lengths follow when a device, a wall or a storey moves.
"""

from dataclasses import dataclass, field

from uea.core.registry import natural
from uea.packs.mount import Mounted

ALLOW = 0.3
"""Added to every run for the stripped ends and the loop at both devices, in m."""


def gap(a: Mounted, b: Mounted) -> float:
    """The rectilinear distance between two mounted things, in m."""
    return abs(a.point[0] - b.point[0]) + abs(a.point[1] - b.point[1]) + abs(a.z - b.z)


@dataclass(frozen=True)
class Run:
    """One cable between a thing and the one it is fed from."""

    a: str
    b: str
    length: float
    """Including the allowance."""


@dataclass
class Route:
    """The cable tree of one circuit."""

    board: str
    runs: list[Run] = field(default_factory=list[Run])
    reach: dict[str, float] = field(default_factory=dict[str, float])
    """Length of the cable from the board to each thing on the way, in m."""
    skipped: list[str] = field(default_factory=list[str])
    """Things on the circuit with no place (a feed to another discipline)."""

    @property
    def total(self) -> float:
        return sum(r.length for r in self.runs)

    @property
    def far(self) -> tuple[str, float] | None:
        """The thing farthest from the board along the cable, and how far."""
        if not self.runs:
            return None
        return max(((k, v) for k, v in self.reach.items()), key=lambda kv: (kv[1], kv[0]))


def tree(board: str, at: dict[str, Mounted], things: list[str]) -> Route:
    """The shortest cable tree from the board over the things that have a place.

    Ties go to the lower id, so the same model always gives the same tree.
    """
    route = Route(board, reach={board: 0.0})
    left = sorted({k for k in things if k in at and k != board}, key=natural)
    route.skipped = sorted({k for k in things if k not in at}, key=natural)
    inside = [board]
    while left:
        best = min(
            ((gap(at[u], at[v]), natural(v), natural(u), u, v) for u in inside for v in left),
        )
        d, _, _, u, v = best
        length = d + ALLOW
        route.runs.append(Run(u, v, length))
        route.reach[v] = route.reach[u] + length
        inside.append(v)
        left.remove(v)
    return route

"""Structural validators (decision 0040): the load path the architecture gives. Whether the
members carry their loads is not a check; the loads need the office's tables (`uea calc
loads`), and the design of the members is the Tragwerksplaner's."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.packs.struct.model import lowest, slab_supports, stands_on

CODES: dict[str, str] = {
    "W-STRUCT-001": "load-bearing wall that stands on no load-bearing wall of the storey below",
    "W-STRUCT-002": "slab with no load-bearing wall under it",
}


def struct_checks(d: Derived) -> Iterable[Issue]:
    g = d.arch
    out: list[Issue] = []
    first = lowest(g)
    for w in sorted(g.walls.values(), key=lambda w: w.id):
        if not (w.lb and w.active) or w.level == first:
            continue
        if not stands_on(g, w):
            below = g.levels[w.level].below
            out.append(
                Issue(
                    "W-STRUCT-001",
                    w.id,
                    f"is load-bearing, but no load-bearing wall of {below} is under it: its load"
                    " goes into the slab",
                    "put a load-bearing wall under it (on=), or ask struct for a beam",
                    (),
                )
            )
    for sl in sorted(g.slabs.values(), key=lambda s: s.id):
        if sl.level == first or sl.status == "demolish":
            continue
        if not slab_supports(g, sl):
            out.append(
                Issue(
                    "W-STRUCT-002",
                    sl.id,
                    f"rests on no load-bearing wall of {g.levels[sl.level].below}",
                    "mark the walls under it load-bearing (lb)",
                    (),
                )
            )
    return out

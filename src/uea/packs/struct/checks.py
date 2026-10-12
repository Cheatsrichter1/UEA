"""Structural validators (decision 0040): the load path the architecture gives. Whether the
members carry their loads is not a check; the loads need the office's tables (`uea calc
loads`), and the design of the members is the Tragwerksplaner's."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.packs.struct.model import (
    MIN_OVERLAP,
    beam_bearings,
    bearing,
    lowest,
    slab_supports,
    stands_on,
)

CODES: dict[str, str] = {
    "W-STRUCT-001": "load-bearing wall that stands on no load-bearing wall of the storey below",
    "W-STRUCT-002": "slab with no load-bearing wall under it",
    "W-STRUCT-003": "beam that rests on fewer than two load-bearing walls",
    "W-STRUCT-004": "hole in a slab over the wall that carries the slab",
}


def struct_checks(d: Derived) -> Iterable[Issue]:
    g = d.arch
    sg = getattr(d, "struct", None)
    out: list[Issue] = []
    first = lowest(g)
    for w in sorted(g.walls.values(), key=lambda w: w.id):
        if not (w.lb and w.active) or w.level == first:
            continue
        if not stands_on(g, w, sg):
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
        if not slab_supports(g, sl, sg):
            out.append(
                Issue(
                    "W-STRUCT-002",
                    sl.id,
                    f"rests on no load-bearing wall of {g.levels[sl.level].below}",
                    "mark the walls under it load-bearing (lb)",
                    (),
                )
            )
    for b in sorted(sg.beams.values() if sg else [], key=lambda b: b.id):
        on = beam_bearings(g, b)
        if len(on) < 2:
            below = g.levels[b.level].below
            got = ", ".join(k for k, _ in on) or "none"
            out.append(
                Issue(
                    "W-STRUCT-003",
                    b.id,
                    f"rests on {got} of the load-bearing walls of {below}: a beam needs two",
                    "run a= and b= into load-bearing walls of the storey below",
                    tuple(k for k, _ in on),
                )
            )
    for h in sorted(g.holes.values(), key=lambda h: h.id):
        sl = g.slabs.get(h.host)
        if sl is None or h.status == "demolish":
            continue
        below = g.levels[sl.level].below
        if below is None:
            continue
        for w in bearing(g, below):
            if h.poly.intersection(w.core).area > MIN_OVERLAP:
                out.append(
                    Issue(
                        "W-STRUCT-004",
                        h.id,
                        f"lies over {w.id}, which carries {sl.id}: the slab has no bearing there",
                        f"move it off {w.id}, or ask struct for a trimmer (Auswechslung)",
                        (w.id,),
                    )
                )
    return out

"""Electrical validators: placement on the walls, switches, circuits and luminaires.

The clearances are our own planning rules, not a norm's: a norm clause is only cited where a check
really implements it (decision 0025).
"""

import math
from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.fmt import iv, ln
from uea.packs.arch.geometry import door_hinge
from uea.packs.arch.kinds import Door
from uea.packs.elec.kinds import Board, Rcd, Switch

CODES: dict[str, str] = {
    "E-ELEC-001": "device outside its host wall",
    "E-ELEC-002": "device on a wall without a usable face",
    "E-ELEC-003": "device in an opening of its wall",
    "W-ELEC-004": "device closer than 0.1 m to an opening",
    "E-ELEC-005": "device below the floor or above the top of its wall",
    "E-ELEC-006": "device on a demolished wall",
    "E-ELEC-011": "switch controls something that is not a luminaire",
    "W-ELEC-012": "switch on the hinge side of a door, where the open leaf covers it",
    "W-ELEC-020": "connected load larger than the circuit breaker carries",
    "W-ELEC-022": "circuit that feeds nothing",
    "W-ELEC-030": "luminaire that no switch controls",
    "W-ELEC-031": "luminaire switched from more than one circuit",
    "W-ELEC-040": "distribution board without an RCD",
}

CLEAR = 0.10
"""Free space around a device next to an opening, in m."""
HALF_HEIGHT = 0.0355
"""Half the height of a device frame, in m."""
OFFSET = 0.15
"""Where a device moves to next to an opening, in m."""
HINGE_REACH = 0.5
"""A switch this close to the hinge edge of a door is behind the open leaf, in m."""


def elec_checks(d: Derived) -> Iterable[Issue]:
    g = d.arch
    m = d.model
    e = d.elec
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, others))

    for mt in d.mounts.values():
        if mt.kind == "lum" or mt.wall is None:
            continue
        el = m[mt.id]
        w = g.walls[mt.wall]
        lv = g.levels[w.level]
        a = mt.axis
        if mt.s < w.s0 - 1e-6 or mt.s > w.s1 + 1e-6:
            add(
                "E-ELEC-001",
                mt.id,
                f"{a} {ln(mt.s)} lies outside {w.id} ({a} {ln(w.s0)}..{ln(w.s1)})",
                f"move it along {w.id}",
                w.id,
            )
        if w.status == "demolish":
            add(
                "E-ELEC-006",
                mt.id,
                f"is on {w.id}, which is demolished",
                "move it to a wall that stays, or demolish it too",
                w.id,
            )
        z_rel = mt.z - lv.z
        top = w.top_at(mt.s)
        if z_rel - HALF_HEIGHT < -1e-6:
            add("E-ELEC-005", mt.id, f"z={ln(z_rel)} is below the FFL", "raise it")
        elif top is not None and mt.z + HALF_HEIGHT > top + 1e-6:
            add(
                "E-ELEC-005",
                mt.id,
                f"z={ln(z_rel)} is above the top of {w.id} (+{ln(top - lv.z)})",
                "lower it",
                w.id,
            )
        s0, s1 = mt.s - mt.width / 2, mt.s + mt.width / 2
        z0, z1 = z_rel - HALF_HEIGHT, z_rel + HALF_HEIGHT
        for o in g.openings.values():
            if o.host != w.id or o.kind == "niche" or o.status == "demolish":
                continue
            # the frame overlaps the opening, or its centre is closer than CLEAR to it
            inside = s0 < o.hi and s1 > o.lo and z0 < o.top and z1 > o.sill
            gap = math.hypot(
                max(o.lo - mt.s, mt.s - o.hi, 0.0), max(o.sill - z_rel, z_rel - o.top, 0.0)
            )
            if not inside and gap >= CLEAR - 1e-9:
                continue
            side = "+" if mt.s >= o.mid else "-"
            need = max(OFFSET, math.ceil((mt.width / 2 + 0.05) / 0.005) * 0.005)
            fix = f"move {mt.id}, e.g. {a}={o.id}{side}{ln(need)}"
            if inside:
                add(
                    "E-ELEC-003",
                    mt.id,
                    f"on {w.id} at {a} {ln(mt.s)} lies in opening {o.id} ({a} {iv(o.lo, o.hi)})",
                    fix,
                    o.id,
                )
            else:
                add(
                    "W-ELEC-004",
                    mt.id,
                    f"is {gap * 100:.0f} cm from opening {o.id} (at least {CLEAR * 100:.0f} cm)",
                    fix,
                    o.id,
                )
        if isinstance(el, Switch):
            for o in g.openings.values():
                if o.host != w.id or o.kind != "door" or o.status == "demolish":
                    continue
                hinge = door_hinge(d, g.openings[o.id])
                if hinge is None or hinge[0] != mt.face:
                    continue
                hs = o.hi if hinge[1] else o.lo
                beyond = (mt.s - hs) if hinge[1] else (hs - mt.s)
                if 0 <= beyond < min(o.width, HINGE_REACH):
                    door = m[o.id]
                    assert isinstance(door, Door)
                    add(
                        "W-ELEC-012",
                        mt.id,
                        f"is on the hinge side of {o.id} (hand={door.hand}), which opens into"
                        f" {door.into.id if door.into else '?'}",
                        f"move {mt.id} past the other edge, or ask arch to turn {o.id}",
                        o.id,
                    )
    for cg in e.circuits.values():
        if cg.load_w > cg.capacity_w + 1e-6:
            add(
                "W-ELEC-020",
                cg.id,
                f"connected load {cg.load_w:.0f} W is more than {cg.breaker.fmt()} carries"
                f" ({cg.capacity_w:.0f} W)",
                "split the circuit or choose a larger breaker and cable",
            )
        if not cg.devices and not cg.lums:
            add("W-ELEC-022", cg.id, "feeds nothing", "remove it or put devices on it")
    for lum in m.of_kind("lum"):
        sws = e.controls.get(lum.id, [])
        if not sws:
            add(
                "W-ELEC-030", lum.id, "is not controlled by any switch", "add it to a switch's ctl="
            )
        elif len(e.lum_circuits[lum.id]) > 1:
            add(
                "W-ELEC-031",
                lum.id,
                f"is switched from circuits {' '.join(e.lum_circuits[lum.id])}",
                "put its switches on one circuit",
                *sws,
            )
    for sw in m.of_kind("switch"):
        assert isinstance(sw, Switch)
        for ref in sw.ctl.refs():
            t = m.get(ref)
            if t is not None and t.kind != "lum":
                add(
                    "E-ELEC-011",
                    sw.id,
                    f"ctl={ref}: {ref} is a {t.kind}, not a luminaire",
                    "control luminaires (lum) only",
                    ref,
                )
    boards = {r.board.id for r in m.of_kind("rcd") if isinstance(r, Rcd)}
    for bd in m.of_kind("board"):
        assert isinstance(bd, Board)
        if not bd.media and bd.id not in boards:
            add("W-ELEC-040", bd.id, "has no RCD", f"+ rcd _ {bd.id} 40/0.03 A")
    return out

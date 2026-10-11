"""Ventilation validators (decision 0038). Whether the system delivers the air the rooms need is
not a check: the flows need the office's tables (DIN 1946-6), so `uea calc airflow` says it, and
`uea check` reads the same on every machine."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.fmt import ln
from uea.packs.net import missing_holes
from uea.packs.vent.geometry import vent_type
from uea.packs.vent.kinds import AhuType, Air, Fan, FanType

CODES: dict[str, str] = {
    "E-VENT-002": "unit or terminal on a wall without a usable face, or outdoor or exhaust air in"
    " a room",
    "W-VENT-001": "ventilation unit without a type, and none of its kind is marked default",
    "W-VENT-002": "push-pull unit without a matching pair",
    "W-VENT-003": "decentral unit, or outdoor or exhaust air terminal, not on an exterior wall",
    "W-VENT-004": "air terminal with no central unit",
    "W-VENT-005": "central unit without outdoor air, exhaust air, supply or extract terminals",
    "W-VENT-006": "decentral unit, or outdoor or exhaust air terminal, with no hole through its"
    " wall",
    "W-VENT-007": "ducts that change storey through a slab with no hole for them",
}
TYPES = {"ahu": AhuType, "fan": FanType}


def vent_checks(d: Derived) -> Iterable[Issue]:
    m, v = d.model, d.vent
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, others))

    for kind, cls in TYPES.items():
        for el in m.of_kind(kind):
            if vent_type(d, el, cls, kind) is None:
                add(
                    "W-VENT-001",
                    el.id,
                    f"has no type, and no {kind} type is marked default",
                    f"~ {el.id} type=<{kind} type>, or mark one default",
                )
    for k, why in v.bad_pairs:
        add("W-VENT-002", k, why, "pair the two units with each other")
    for el in m.of_kind("fan"):
        assert isinstance(el, Fan)
        if (
            el.mode == "alt"
            and el.id not in v.pairs
            and not any(k == el.id for k, _ in v.bad_pairs)
        ):
            add(
                "W-VENT-002",
                el.id,
                "is a push-pull unit without a pair: it works only in pairs",
                f"~ {el.id} pair=<the other unit>, or mode=both",
            )
    for kind in ("fan", "air"):
        for el in m.of_kind(kind):
            mt = v.at.get(el.id)
            if mt is None or mt.wall is None:
                continue
            if isinstance(el, Air) and el.role not in ("oda", "eha"):
                continue
            if d.arch.walls[mt.wall].ext is None:
                add(
                    "W-VENT-003",
                    el.id,
                    f"is on {mt.wall}, which is not an exterior wall: its air must reach outside",
                    "put it on an exterior wall",
                    mt.wall,
                )
                continue
            if el.id in v.holes and v.holes[el.id] is None:
                add(
                    "W-VENT-006",
                    el.id,
                    f"is on {mt.wall} at {mt.axis} {ln(mt.s)} z {ln(mt.z)}, and no hole goes"
                    " through the wall there",
                    f'ask arch for a core drilling: + req _ vent {mt.wall} "Kernbohrung für'
                    f' {el.id}"',
                    mt.wall,
                )
    units = {el.id for el in m.of_kind("ahu")}
    for el in m.of_kind("air"):
        if el.id in v.at and el.id not in v.unit_of:
            why = "there is no central unit" if not units else f"{el.src.id} has no place"  # type: ignore[union-attr]
            add("W-VENT-004", el.id, f"has no unit: {why}", "add an ahu, or src= one")
    for u in sorted(units):
        if u not in v.at:
            continue
        missing = [r for r in ("oda", "eha", "sup", "ext") if (u, r) not in v.ducts]
        if missing:
            add(
                "W-VENT-005",
                u,
                f"has no {', '.join(missing)} terminal",
                f"add air terminals: air <host> {missing[0]} src={u}",
            )
    out += missing_holes(v.crossings, "W-VENT-007", "vent")
    return out

"""Plumbing validators (decision 0035). Whether the pipes are large enough is not a check: the
sizing needs the office's tables, so it is part of `uea calc water` and `uea calc drain`, and
`uea check` reads the same on every machine."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.packs.net import missing_holes
from uea.packs.plumb.geometry import nets
from uea.packs.plumb.kinds import San

CODES: dict[str, str] = {
    "E-PLUMB-002": "fixture on a wall without a usable face",
    "W-PLUMB-001": "fixture that takes water, and there is no meter",
    "W-PLUMB-002": "fixture that takes hot water, and no storage tank heats drinking water",
    "W-PLUMB-003": "fixture whose waste water has nowhere to go",
    "W-PLUMB-004": "riser or stack that nothing runs through",
    "W-PLUMB-005": "a second meter or sewer connection; the first one serves",
    "W-PLUMB-006": "pipe that passes a slab with no hole for it",
}


def plumb_checks(d: Derived) -> Iterable[Issue]:
    m, p = d.model, d.plumb
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, others))

    meters = m.of_kind("meter")
    for el in m.of_kind("san"):
        assert isinstance(el, San)
        if el.id not in p.at:
            continue
        if el.supply != "none" and not meters:
            add("W-PLUMB-001", el.id, "takes water, and there is no meter", "+ meter <room>")
        if el.supply == "both" and not p.tanks:
            add(
                "W-PLUMB-002",
                el.id,
                "takes hot water, and no storage tank heats drinking water",
                "a tank in heat.uea whose type is dhw, or water=cold",
            )
        if el.id in p.stray:
            add(
                "W-PLUMB-003",
                el.id,
                f"its waste water has nowhere to go: {p.stray[el.id]}",
                "a stack from its storey or below (+ stack <room>), a sewer connection, or to=",
            )
    used = {k.partition(":")[0] for n in nets(d) for s in n.sections for k in (s.a, s.b)}
    for kind in ("riser", "stack"):
        for el in m.of_kind(kind):
            if el.id in p.at and el.id not in used:
                what = "water" if kind == "riser" else "waste water"
                add("W-PLUMB-004", el.id, f"no {what} runs through it", f"- {el.id}, or move it")
    for kind, what in (("meter", "meter"), ("sewer", "sewer connection")):
        first, *more = [el.id for el in m.of_kind(kind)] or [""]
        for k in more:
            add("W-PLUMB-005", k, f"a second {what}: {first} serves", f"- {k}", first)
    out += missing_holes(p.crossings, "W-PLUMB-006", "plumb", via=False)
    return out

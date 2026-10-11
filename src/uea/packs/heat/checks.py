"""Heating validators (decision 0034). Whether an emitter covers its room's Heizlast is not a
check: the Heizlast needs the office's tables, so it is part of `uea calc heatload`, and
`uea check` reads the same on every machine."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.packs.heat.geometry import heat_type, man_type, tank_type
from uea.packs.heat.kinds import GenType, ManType, RadType, TankType, UfhType

CODES: dict[str, str] = {
    "E-HEAT-002": "manifold or radiator on a wall without a usable face",
    "W-HEAT-001": "heating element without a type, and none of its kind is marked default",
    "W-HEAT-002": "manifold with more loops than outlets",
    "W-HEAT-003": "underfloor heating too far from its manifold for a loop",
    "W-HEAT-004": "generator, tank or manifold that supplies nothing (a tank that heats drinking"
    " water supplies the hot water)",
}

TYPES = {"gen": GenType, "tank": TankType, "man": ManType, "ufh": UfhType, "rad": RadType}


def heat_checks(d: Derived) -> Iterable[Issue]:
    m, h = d.model, d.heat
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, others))

    for kind, cls in TYPES.items():
        for el in m.of_kind(kind):
            if heat_type(m, el, cls, kind) is None:
                add(
                    "W-HEAT-001",
                    el.id,
                    f"has no type, and no {kind} type is marked default",
                    f"~ {el.id} type=<{kind} type>, or mark one default",
                )
    for el in m.of_kind("man"):
        loops = [k for k in h.supplies.get(el.id, []) if k in h.loops]
        n = sum(h.loops[k].n for k in loops)
        t = man_type(d, el)
        if t is not None and n > t.outlets:
            add(
                "W-HEAT-002",
                el.id,
                f"connects {n} loops ({', '.join(loops)}), its type {t.id} has {t.outlets} outlets",
                "a manifold type with more outlets, or a second manifold",
                *loops,
            )
    for k in h.too_far:
        el = m[k]
        lp_max = getattr(heat_type(m, el, UfhType, "ufh"), "max", 0.0)
        src = getattr(el, "src").id  # noqa: B009
        add(
            "W-HEAT-003",
            k,
            f"{src} is too far away: a loop of {lp_max:g} m does not reach the room and back",
            "a manifold closer to the room",
            src,
        )
    for kind in ("gen", "tank", "man"):
        for el in m.of_kind(kind):
            if kind == "tank" and getattr(tank_type(d, el), "dhw", False):
                continue  # it supplies the hot water (plumb.uea)
            if not h.supplies.get(el.id):
                add("W-HEAT-004", el.id, "supplies nothing", f"connect something with src={el.id}")
    return out

"""Derived values of plumbing elements, for `uea get`."""

from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ids
from uea.packs.light.views import where
from uea.packs.net import Net
from uea.packs.plumb.kinds import San

WATER_EN = {"cold": "cold", "both": "cold+hot", "none": "no water"}


def describe(d: Derived, el: Element) -> list[str]:
    p = d.plumb
    if el.kind == "tank":
        net = p.hot.get(el.id)
        if net is None:
            return []
        ends = [k for k in net.nodes if k in d.model and d.model[k].kind == "san"]
        return [f"hot water to {ids(sorted(ends, key=natural))} | {_m(net.total)} of pipe"]
    out: list[str] = []
    mt = p.at.get(el.id)
    if mt is not None:
        out.append(where(mt))
    if isinstance(el, San):
        parts = [f"{el.fixture} {WATER_EN[el.supply]}"]
        if p.cold is not None and p.cold.has(el.id):
            parts.append(f"water {_m(p.cold.reach(el.id))} from {p.cold.root}")
        t = p.hot_from.get(el.id)
        if t is not None and t in p.hot:
            parts.append(f"hot {_m(p.hot[t].reach(el.id))} from {t}")
        to = p.drains_to.get(el.id)
        if to is not None and p.drain is not None:
            parts.append(f"waste to {to}, {_m(p.drain.reach(el.id))} to {p.drain.root}")
        out.append(" | ".join(parts))
    elif el.kind == "meter" and p.cold is not None and p.cold.root == el.id:
        ends = _ends(p.cold)
        out.append(f"supplies {ids(ends) or 'nothing'} | {_m(p.cold.total)} of pipe")
    elif el.kind == "riser":
        levels = _levels(d, el.id, [n for n in (p.cold, *p.hot.values()) if n is not None])
        out.append(f"{'–'.join(levels)}" if levels else "carries nothing")
    elif el.kind == "stack" and p.drain is not None:
        levels = _levels(d, el.id, [p.drain])
        takes = sorted((k for k, v in p.drains_to.items() if v == el.id), key=natural)
        if levels:
            foot = p.drain.reach(f"{el.id}:{levels[0]}")
            out.append(
                f"{'–'.join(levels)} | takes {ids(takes)} | foot {_m(foot)} to {p.drain.root}"
            )
    elif el.kind == "sewer" and p.drain is not None and p.drain.root == el.id:
        out.append(f"takes {len(p.drains_to)} fixtures | {_m(p.drain.total)} of pipe")
    return out


def _m(v: float) -> str:
    return f"{v:.1f} m"


def _ends(net: Net) -> list[str]:
    return sorted({k for s in net.sections if s.a == net.root for k in s.serves}, key=natural)


def _levels(d: Derived, key: str, nets: list[Net]) -> list[str]:
    on = {k.partition(":")[2] for n in nets for k in n.nodes if k.startswith(f"{key}:")}
    return [lv for lv in d.arch.level_order() if lv in on]

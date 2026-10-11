"""Derived values of ventilation elements, for `uea get`."""

from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ids, ln
from uea.packs.light.views import where
from uea.packs.vent.geometry import ahu_type, fan_flow


def describe(d: Derived, el: Element) -> list[str]:
    v = d.vent
    out: list[str] = []
    mt = v.at.get(el.id)
    if mt is not None:
        out.append(where(mt))
    if el.kind == "fan":
        flow = fan_flow(d, el)
        mode = getattr(el, "mode")  # noqa: B009
        parts = [f"{ln(flow)} m³/h" if flow is not None else "", mode]
        if el.id in v.pairs:
            parts.append(f"pair {v.pairs[el.id]}")
        out.append(" | ".join(x for x in parts if x))
    elif el.kind == "ahu":
        t = ahu_type(d, el)
        parts = [f"up to {ln(t.flow)} m³/h" if t is not None else ""]
        for (u, role), net in v.ducts.items():
            if u == el.id:
                ends = [k for k in net.nodes if k != u]
                parts.append(f"{role} {ids(ends)} {net.total:.1f} m")
        out.append(" | ".join(x for x in parts if x) or "no terminals")
    elif el.kind == "air":
        up = v.duct_from(el.id)
        if up is not None:
            out.append(f"{getattr(el, 'role')} from {up[0]} | duct {up[1]:.1f} m")  # noqa: B009
    return out

"""Derived values of heating elements, for `uea get`."""

from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ids, ln
from uea.packs.heat.geometry import generator_kw, man_type, tank_type
from uea.packs.light.views import where


def describe(d: Derived, el: Element) -> list[str]:
    h = d.heat
    out: list[str] = []
    mt = h.at.get(el.id)
    if mt is not None:
        out.append(where(mt))
    src = getattr(el, "src", None)
    tail = f"from {src.id}" if src is not None else ""
    supplies = h.supplies.get(el.id, [])
    if el.kind == "gen":
        kw = generator_kw(d).get(el.id)
        out.append(
            (f"{ln(kw)} kW | " if kw is not None else "") + f"supplies {ids(supplies) or 'nothing'}"
        )
    elif el.kind == "tank":
        t = tank_type(d, el)
        size = f"{ln(t.vol)} l{' dhw' if t.dhw else ''}" if t is not None else ""
        parts = (size, tail, f"supplies {ids(supplies) or 'nothing'}")
        out.append(" | ".join(x for x in parts if x))
    elif el.kind == "man":
        loops = sum(h.loops[k].n for k in supplies if k in h.loops)
        t = man_type(d, el)
        of = f" of {t.outlets} outlets" if t is not None else ""
        out.append(f"{tail} | {loops} loops{of} | supplies {ids(supplies) or 'nothing'}")
    elif el.kind == "ufh":
        lp = h.loops.get(el.id)
        w = h.output.get(el.id)
        if lp is not None:
            if lp.n == 0:
                out.append(f"{ln(lp.area)} m² | {tail} {ln(lp.reach)} m away: too far for a loop")
            else:
                out.append(
                    f"{ln(lp.area)} m² | {lp.n} loop{'s' if lp.n > 1 else ''} of {lp.each:.1f} m"
                    f" (spacing {ln(lp.spacing)}, {tail} {lp.reach:.1f} m)"
                    + (f" | {w:.0f} W" if w is not None else "")
                )
    elif el.kind == "rad":
        w = h.output.get(el.id)
        out.append(tail + (f" | {w:.0f} W" if w is not None else ""))
    return out

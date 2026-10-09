"""Derived values of a luminaire, for `uea get`."""

from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ln
from uea.packs.light.geometry import lum_type
from uea.packs.mount import Mounted


def where(m: Mounted) -> str:
    x, y = m.point
    on = f"{m.wall}.{m.letter} {m.axis} {ln(m.s)}" if m.wall else f"at {ln(x)},{ln(y)}"
    return f"{on} z {ln(m.z)} | {m.room or 'no room'} {m.level}"


def describe(d: Derived, el: Element) -> list[str]:
    if el.kind != "lum" or el.id not in d.mounts:
        return []
    t = lum_type(d.model, el)
    kind = ""
    if t is not None:
        kind = f" | {t.id}" + (f" {ln(t.w)} W" if t.w else "")
    return [where(d.mounts[el.id]) + kind]

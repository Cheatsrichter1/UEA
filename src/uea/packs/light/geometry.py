"""Where the luminaires are, and what they draw."""

from contextlib import suppress

from uea.core.model import Model
from uea.core.schema import Element
from uea.derive import Derived, Unresolved
from uea.packs.light.kinds import Lum, LumType
from uea.packs.mount import Mounts


def lum_type(m: Model, el: Element) -> LumType | None:
    """The type of a luminaire: its own, else the type marked default."""
    if not isinstance(el, Lum):
        return None
    if el.type is not None:
        t = m.get(el.type.id)
        return t if isinstance(t, LumType) else None
    defaults = [t for t in m.of_kind("type", "lum") if isinstance(t, LumType) and t.default]
    return defaults[0] if defaults else None


def derive_light(d: Derived) -> None:
    mounts = Mounts(d)
    for el in d.model.of_kind("lum"):
        with suppress(Unresolved):
            mounts.place(el.id)


def light_signatures(d: Derived) -> dict[str, tuple[float, ...]]:
    """Where each luminaire is, to report what follows a change."""
    return {
        k: (round(v.point[0], 4), round(v.point[1], 4), round(v.z, 4))
        for k, v in d.mounts.items()
        if v.kind == "lum"
    }

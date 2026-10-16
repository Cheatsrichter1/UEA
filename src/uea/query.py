"""What `uea find` selects: a kind and filters, shared with the positions of the LV."""

from uea.core.schema import Element, fmt_value, spec
from uea.core.values import Ref, RefList
from uea.derive import Derived
from uea.packs.arch.views import in_room, level_of


def matches(d: Derived, el: Element, flt: list[str]) -> bool:
    """Whether el passes every filter: k=v on a field, level=, room=, a flag or a category."""
    sp = spec(type(el))
    for f in flt:
        if "=" in f:
            k, v = f.split("=", 1)
            if k == "level":
                if level_of(d, el) != v:
                    return False
                continue
            if k == "room":
                if not in_room(d, el, v):
                    return False
                continue
            if k not in sp.fields:
                return False
            val = getattr(el, k)
            if isinstance(val, Ref):
                if v not in (val.id, val.fmt()):
                    return False
            elif isinstance(val, RefList):
                if v not in val.refs():
                    return False
            elif val is None or fmt_value(val).strip('"') != v:
                return False
        else:
            if f in ("ext", "int") and el.kind == "wall":
                w = d.arch.walls.get(el.id)
                if w is None or (w.ext is not None) != (f == "ext"):
                    return False
                continue
            if f == "open" and el.kind == "req":
                if not getattr(el, "open", False):
                    return False
                continue
            if f in sp.flags:
                if not getattr(el, f):
                    return False
                continue
            hit = any(getattr(el, n) == f for n in sp.flag_enums)
            if not hit and el.category != f:
                return False
    return True

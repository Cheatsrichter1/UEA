"""Domain packs and the registry of element kinds.

The core knows the disciplines and the direction references may point between them. A pack
registers its kinds; the registry maps a line to its kind and gives the canonical order.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from uea.core.schema import Element
from uea.core.syntax import LineError, RawLine

if TYPE_CHECKING:
    from uea.core.issues import Issue
    from uea.derive import Derived

DISCIPLINES: tuple[str, ...] = (
    "project",
    "arch",
    "struct",
    "light",
    "elec",
    "heat",
    "plumb",
    "vent",
    "issues",
)
"""Every planned discipline, in file order. Packs that are not built yet are still named here,
so requests from them can be recorded."""

UPSTREAM: dict[str, frozenset[str]] = {
    "project": frozenset(),
    "arch": frozenset({"project"}),
    "struct": frozenset({"project", "arch"}),
    "light": frozenset({"project", "arch"}),
    "heat": frozenset({"project", "arch"}),
    "plumb": frozenset({"project", "arch"}),
    "vent": frozenset({"project", "arch"}),
    "elec": frozenset({"project", "arch", "light", "heat", "plumb", "vent"}),
    "issues": frozenset(DISCIPLINES),
}
"""Which disciplines each discipline may reference (references only point upstream)."""

Check = Callable[["Derived"], Iterable["Issue"]]
Deriver = Callable[["Derived"], None]
Signatures = Callable[["Derived"], dict[str, tuple[Any, ...]]]
Describe = Callable[["Derived", Element], list[str]]


@dataclass(frozen=True)
class Pack:
    name: str
    title: str
    kinds: tuple[type[Element], ...]
    """Kinds in canonical file order; `type` categories first."""
    derive: Deriver | None = None
    checks: tuple[Check, ...] = ()
    codes: dict[str, str] = field(default_factory=dict[str, str])
    """Issue codes this pack raises, with a one-line meaning."""
    signatures: Signatures | None = None
    """Derived geometry per element, compared before and after a batch to report what moved."""
    describe: Describe | None = None
    """Derived values of one element, as short lines for `uea get`."""
    also: tuple[str, ...] = ()
    """Kinds of other disciplines this pack adds lines to in `uea get`."""

    @property
    def file(self) -> str:
        return f"{self.name}.uea"


_NAT = re.compile(r"(\d+)")


def natural(s: str) -> tuple[Any, ...]:
    """Natural order: w2 before w10."""
    return tuple(int(p) if p.isdigit() else p for p in _NAT.split(s))


class Registry:
    def __init__(self, packs: Iterable[Pack]) -> None:
        self.packs: dict[str, Pack] = {}
        self.kinds: dict[str, type[Element]] = {}
        self.types: dict[str, type[Element]] = {}
        self.prefixes: dict[str, type[Element]] = {}
        self._order: dict[type[Element], int] = {}
        for pack in sorted(packs, key=lambda p: DISCIPLINES.index(p.name)):
            if pack.name not in DISCIPLINES:
                raise ValueError(f"unknown discipline {pack.name}")
            self.packs[pack.name] = pack
            for i, cls in enumerate(pack.kinds):
                if cls.pack != pack.name:
                    raise ValueError(f"{cls.__name__} declares pack {cls.pack}, not {pack.name}")
                self._order[cls] = i
                if cls.kind == "type":
                    assert cls.category is not None
                    if cls.category in self.types:
                        raise ValueError(f"type category {cls.category} registered twice")
                    self.types[cls.category] = cls
                    continue
                if cls.kind in self.kinds:
                    raise ValueError(f"kind {cls.kind} registered twice")
                self.kinds[cls.kind] = cls
                if cls.prefix is not None:
                    if cls.prefix in self.prefixes:
                        other = self.prefixes[cls.prefix].kind
                        raise ValueError(f"prefix {cls.prefix} used by {other} and {cls.kind}")
                    self.prefixes[cls.prefix] = cls

    def cls_for(self, raw: RawLine) -> type[Element]:
        if raw.kind == "type":
            if not raw.bare:
                cats = " ".join(self.types)
                raise LineError(f"type {raw.key}: missing category. Categories: {cats}")
            cat = raw.bare[0]
            if cat not in self.types:
                cats = " ".join(self.types)
                raise LineError(f"type {raw.key}: unknown category {cat!r}. Categories: {cats}")
            return self.types[cat]
        if raw.kind not in self.kinds:
            raise LineError(f"unknown kind {raw.kind!r}. Kinds: {' '.join(self.kind_names())}")
        return self.kinds[raw.kind]

    def kind_names(self) -> list[str]:
        names = list(self.kinds)
        if self.types:
            names.insert(0, "type")
        return names

    def sort_key(self, el: Element) -> tuple[Any, ...]:
        cls = type(el)
        within: tuple[Any, ...]
        if el.kind == "level":
            within = (getattr(el, "z", 0.0), natural(el.id))
        elif el.kind == "grid":
            x = getattr(el, "x", None)
            y = getattr(el, "y", None)
            within = (0, x, natural(el.id)) if x is not None else (1, y, natural(el.id))
        else:
            within = natural(el.id)
        return (DISCIPLINES.index(cls.pack), self._order[cls], within)

    def type_class(self, category: str) -> type[Element] | None:
        return self.types.get(category)

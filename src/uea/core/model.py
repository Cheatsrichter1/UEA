"""The in-memory model: every element of a project, keyed by id."""

from collections.abc import Iterable, Iterator
from typing import Any

from uea.core.registry import Registry
from uea.core.schema import Element, build, check_key, raw_to_data, spec
from uea.core.syntax import RawLine
from uea.core.values import Value


def element_from_raw(reg: Registry, raw: RawLine, *, check_id: bool = True) -> Element:
    cls = reg.cls_for(raw)
    if check_id:
        check_key(cls, raw.key)
    return build(cls, raw_to_data(cls, raw))


def refs_of(el: Element) -> list[tuple[str, str]]:
    """(field, id) for every element reference in an element."""
    out: list[tuple[str, str]] = []
    for name in spec(type(el)).fields:
        v = getattr(el, name)
        if isinstance(v, Value):
            out.extend((name, r) for r in v.refs())
    return out


def map_refs(el: Element, f: Any) -> Element:
    """A copy of el with every reference renamed by f (id -> id)."""
    changes: dict[str, Any] = {}
    for name in spec(type(el)).fields:
        v = getattr(el, name)
        if isinstance(v, Value):
            nv = v.map_refs(f)
            if nv != v:
                changes[name] = nv
    new_id = f(el.id) if el.id.startswith("@") else el.id
    if not changes and new_id == el.id:
        return el
    return type(el).model_validate({**dict(el), **changes, "id": new_id})


class Model:
    def __init__(self, reg: Registry, elements: Iterable[Element] = ()) -> None:
        self.reg = reg
        self.els: dict[str, Element] = {}
        self._referrers: dict[str, list[str]] | None = None
        for el in elements:
            self.els[el.id] = el

    def __contains__(self, key: object) -> bool:
        return key in self.els

    def __getitem__(self, key: str) -> Element:
        return self.els[key]

    def __iter__(self) -> Iterator[Element]:
        return iter(self.els.values())

    def __len__(self) -> int:
        return len(self.els)

    def get(self, key: str) -> Element | None:
        return self.els.get(key)

    def copy(self) -> "Model":
        return Model(self.reg, self.els.values())

    def put(self, el: Element) -> None:
        self.els[el.id] = el
        self._referrers = None

    def remove(self, key: str) -> Element:
        self._referrers = None
        return self.els.pop(key)

    def sorted(self, els: Iterable[Element] | None = None) -> list[Element]:
        return sorted(self.els.values() if els is None else els, key=self.reg.sort_key)

    def of_kind(self, kind: str, category: str | None = None) -> list[Element]:
        return self.sorted(
            e
            for e in self.els.values()
            if e.kind == kind and (category is None or e.category == category)
        )

    def pack_of(self, key: str) -> str:
        return type(self.els[key]).pack

    def in_pack(self, pack: str) -> list[Element]:
        return self.sorted(e for e in self.els.values() if type(e).pack == pack)

    def pack_text(self, pack: str) -> str:
        lines = [e.line() for e in self.in_pack(pack)]
        return "".join(line + "\n" for line in lines)

    def packs(self) -> set[str]:
        return {type(e).pack for e in self.els.values()}

    def referrers(self, key: str) -> list[str]:
        """Ids of the elements that reference key."""
        if self._referrers is None:
            idx: dict[str, list[str]] = {}
            for el in self.els.values():
                for _, r in refs_of(el):
                    idx.setdefault(r, []).append(el.id)
            self._referrers = idx
        return list(dict.fromkeys(self._referrers.get(key, [])))

    def project_name(self) -> str | None:
        ps = self.of_kind("project")
        return ps[0].id if ps else None

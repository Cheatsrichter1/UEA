"""Derived values: geometry and everything computed from the model, never stored.

Each pack fills its part of `Derived`; `check` then collects the issues of all packs.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from uea.core.issues import Issue
from uea.core.model import Model, refs_of
from uea.core.registry import UPSTREAM
from uea.core.schema import F, spec
from uea.core.values import Ref, RefList

if TYPE_CHECKING:
    from uea.packs.arch.geometry import ArchGeo
    from uea.packs.issues import Req, Waive

T = TypeVar("T")


class GeoError(Exception):
    """An element cannot be placed. The message has the numbers; fix says what to do."""

    def __init__(
        self,
        msg: str,
        fix: str | None = None,
        code: str = "E-GEO-001",
        others: tuple[str, ...] = (),
    ) -> None:
        super().__init__(msg)
        self.msg = msg
        self.fix = fix
        self.code = code
        self.others = others


class Unresolved(Exception):
    """A dependency cannot be placed (its own issue says why)."""

    def __init__(self, dep: str, missing: bool = False) -> None:
        super().__init__(dep)
        self.dep = dep
        self.missing = missing


class Derived:
    def __init__(self, model: Model) -> None:
        self.model = model
        self.issues: list[Issue] = []
        self._failed: dict[str, bool] = {}
        self._stack: list[str] = []
        self.arch: ArchGeo

    def resolve(self, key: str, store: dict[str, T], fn: Callable[[], T]) -> T:
        """Memoized resolution with cycle detection. Failures become issues on key."""
        if key in store:
            return store[key]
        if key in self._failed:
            raise Unresolved(key)
        if key in self._stack:
            cycle = [*self._stack[self._stack.index(key) :], key]
            raise GeoError(
                f"positions refer to each other in a cycle: {' -> '.join(cycle)}",
                "anchor one of them on a grid or on a wall outside the cycle",
                code="E-GEO-003",
            )
        self._stack.append(key)
        try:
            value = fn()
        except GeoError as e:
            self._failed[key] = True
            self.issues.append(Issue(e.code, key, e.msg, e.fix, e.others))
            raise Unresolved(key) from None
        except Unresolved as e:
            self._failed[key] = True
            if not e.missing:
                self.issues.append(
                    Issue(
                        "E-GEO-002",
                        key,
                        f"depends on {e.dep}, which cannot be placed",
                        f"fix {e.dep} first",
                        (e.dep,),
                    )
                )
            raise Unresolved(key) from None
        finally:
            self._stack.pop()
        store[key] = value
        return value

    def attempt(self, key: str, store: dict[str, T], fn: Callable[[], T]) -> T | None:
        try:
            return self.resolve(key, store, fn)
        except Unresolved:
            return None

    def add(self, code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        self.issues.append(Issue(code, el, msg, fix, tuple(others)))


def derive(model: Model) -> Derived:
    d = Derived(model)
    for pack in model.reg.packs.values():
        if pack.derive is not None:
            pack.derive(d)
    return d


def ref_issues(model: Model) -> list[Issue]:
    """Reference checks: targets exist, have the right kind, and point upstream."""
    out: list[Issue] = []
    for el in model:
        pack = type(el).pack
        fields = spec(type(el)).fields
        for name, target in refs_of(el):
            t = model.get(target)
            if t is None:
                out.append(
                    Issue(
                        "E-REF-001",
                        el.id,
                        f"{name}={target}: {target} does not exist",
                        "point it at an existing element or add the element",
                        (target,),
                    )
                )
                continue
            tpack = type(t).pack
            if tpack != pack and tpack not in UPSTREAM[pack]:
                out.append(
                    Issue(
                        "E-REF-002",
                        el.id,
                        f"{pack} must not reference {tpack} ({name}={target})",
                        f"{pack} may reference {', '.join(sorted(UPSTREAM[pack]))};"
                        f" ask {tpack} with a request instead",
                        (target,),
                    )
                )
                continue
            meta: F = fields[name].meta
            value: Any = getattr(el, name)
            if meta.targets and isinstance(value, Ref | RefList):
                tkind = f"type:{t.category}" if t.kind == "type" else t.kind
                if tkind not in meta.targets:
                    want = " or ".join(
                        x.replace("type:", "") + (" type" if "type:" in x else "")
                        for x in meta.targets
                    )
                    have = f"{t.category} type" if t.kind == "type" else t.kind
                    out.append(
                        Issue(
                            "E-REF-003",
                            el.id,
                            f"{name}={target} is a {have}, not a {want}",
                            None,
                            (target,),
                        )
                    )
    return out


@dataclass
class Report:
    """The state of a model: open issues, waived issues, open requests."""

    model: Model
    issues: list[Issue]
    waived: list[tuple[Issue, "Waive"]] = field(default_factory=list[tuple[Issue, "Waive"]])
    requests: list["Req"] = field(default_factory=list["Req"])

    def owner(self, issue: Issue) -> str:
        el = self.model.get(issue.el)
        return type(el).pack if el is not None else "project"

    def request_owner(self, req: "Req") -> str:
        for t in req.targets.refs():
            el = self.model.get(t)
            if el is not None:
                return type(el).pack
        return "arch"

    def errors(self, disc: str | None = None) -> list[Issue]:
        return [
            i
            for i in self.issues
            if i.severity == "error" and (disc is None or self.owner(i) == disc)
        ]

    def warnings(self, disc: str | None = None) -> list[Issue]:
        return [
            i
            for i in self.issues
            if i.severity == "warning" and (disc is None or self.owner(i) == disc)
        ]

    def of(self, disc: str | None) -> list[Issue]:
        return [i for i in self.issues if disc is None or self.owner(i) == disc]


def check(d: Derived) -> Report:
    from uea.packs.issues import Req, Waive

    model = d.model
    found: list[Issue] = [*ref_issues(model), *d.issues]
    for pack in model.reg.packs.values():
        for fn in pack.checks:
            found.extend(fn(d))
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    unique: list[Issue] = []
    for i in found:
        if i.key not in seen:
            seen.add(i.key)
            unique.append(i)
    waivers = [e for e in model.of_kind("waive") if isinstance(e, Waive)]
    by_key = {(w.code, w.target.id): w for w in waivers}
    used: set[str] = set()
    open_: list[Issue] = []
    waived: list[tuple[Issue, Waive]] = []
    for i in unique:
        w = by_key.get((i.code, i.el))
        if w is not None:
            waived.append((i, w))
            used.add(w.id)
        else:
            open_.append(i)
    for w in waivers:
        if w.id not in used:
            open_.append(
                Issue(
                    "W-ISSUE-001",
                    w.id,
                    f"waives {w.code} on {w.target.id}, but there is no such issue",
                    f"remove it: - {w.id}",
                )
            )
    reqs = [e for e in model.of_kind("req") if isinstance(e, Req) and e.open]
    return Report(model, open_, waived, reqs)


def report(model: Model) -> tuple[Derived, Report]:
    d = derive(model)
    return d, check(d)

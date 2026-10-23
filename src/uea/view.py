"""Partial views: read a slice of the model at a base batch, write back only to that slice.

See docs/decisions/foundations.md#0046-partial-views.
"""

from dataclasses import dataclass

from uea.core.model import Model, refs_of
from uea.derive import Derived
from uea.packs.arch.views import in_room, level_of
from uea.project import History

SYNTAX = (
    "a discipline (heat), discipline:level (heat:OG), discipline:room (elec:r3), a level or an id"
)


class ViewError(Exception):
    pass


def select(d: Derived, selector: str) -> set[str]:
    """The ids a selector names; terms joined by commas are added up."""
    m = d.model
    out: set[str] = set()
    for term in selector.split(","):
        term = term.strip()
        if not term:
            raise ViewError(f"empty term in {selector!r}: use {SYNTAX}, joined by commas")
        out |= _term(d, m, term)
    return out


def _term(d: Derived, m: Model, term: str) -> set[str]:
    pack, _, rest = term.partition(":")
    if rest:
        if pack not in m.reg.packs:
            raise ViewError(f"unknown discipline {pack!r} in {term}: {' '.join(m.reg.packs)}")
        els = m.in_pack(pack)
        if rest in d.arch.levels:
            return {e.id for e in els if level_of(d, e) == rest}
        if rest in d.arch.rooms:
            return {e.id for e in els if in_room(d, e, rest)}
        raise ViewError(f"{rest!r} in {term} is not a level or a room")
    if term in m.reg.packs:
        return {e.id for e in m.in_pack(term)}
    if term in d.arch.levels:
        return {e.id for e in m if level_of(d, e) == term}
    if term in m:
        return _hanging(m, term)
    raise ViewError(f"unknown selector {term!r}: use {SYNTAX}")


def _hanging(m: Model, key: str) -> set[str]:
    """The element and everything that references it, transitively."""
    out = {key}
    todo = [key]
    while todo:
        for r in m.referrers(todo.pop()):
            if r not in out:
                out.add(r)
                todo.append(r)
    return out


def context(m: Model, ids: set[str]) -> set[str]:
    """What the slice references outside itself, transitively upstream, so every reference
    in a view resolves."""
    out: set[str] = set()
    todo = list(ids)
    while todo:
        el = m.get(todo.pop())
        if el is None:
            continue
        for _, r in refs_of(el):
            if r not in ids and r not in out and r in m:
                out.add(r)
                todo.append(r)
    return out


@dataclass
class View:
    selector: str
    base: int
    elements: list[str]
    """The slice's lines, in canonical order."""
    context: list[str]
    """The lines it references outside itself, read-only."""


def view(d: Derived, selector: str, base: int) -> View:
    m = d.model
    ids = select(d, selector)
    ctx = context(m, ids)
    return View(
        selector,
        base,
        [e.line() for e in m.sorted(m[i] for i in ids)],
        [e.line() for e in m.sorted(m[i] for i in ctx)],
    )


def check_base(history: History, base: int, edited: set[str], selector: str | None) -> list[str]:
    """Errors for elements a batch after the base touched that this batch edits as well."""
    last = history.last()
    if base > last:
        return [f"base {base} is ahead of the history: the last batch is {last}"]
    again = f"uea view {selector}" if selector else "uea get"
    for e in history.entries():
        if e.batch <= base:
            continue
        clash = sorted(edited & e.touched())
        if clash:
            return [
                f"batch {e.batch} changed {' '.join(clash)} after base {base}."
                f" Read them again ({again}) and write the batch on the new base"
            ]
    return []


def check_scope(
    before: Derived, after: Derived, selector: str, edited: set[str], added: set[str]
) -> list[str]:
    """Errors for what a batch writes outside the view: elements it changes or removes must be
    in the slice as read, elements it adds must fall in it."""
    outside = sorted(edited - select(before, selector)) + sorted(added - select(after, selector))
    if not outside:
        return []
    return [
        f"{' '.join(outside)} {'is' if len(outside) == 1 else 'are'} outside {selector}."
        f" Write them with a view that holds them, or without --view"
    ]

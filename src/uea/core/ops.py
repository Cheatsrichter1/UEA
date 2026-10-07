"""Operations: the line syntax with a prefix.

    + wall @a EG IW-115 x=w6+1.385 y=w5..w3     add; UEA assigns the id
    ~ w9 type=IW-175                             set fields
    - w9                                         remove
    > grid E x=10.74                             replace a whole element

See ARCHITECTURE.md §5.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from uea.core.model import Model, element_from_raw, map_refs, refs_of
from uea.core.registry import Registry
from uea.core.schema import (
    Element,
    build,
    check_key,
    flag_tokens,
    fmt_value,
    spec,
    usage,
)
from uea.core.syntax import LineError, RawLine, parse_tokens, strip_comment, tokenize
from uea.core.values import Value

Sign = Literal["+", "~", "-", ">"]
PLACEHOLDER = re.compile(r"^@[A-Za-z0-9_]+$")


class OpsError(Exception):
    """A batch that cannot be applied. Nothing changed."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Op:
    sign: Sign
    n: int
    text: str
    raw: RawLine
    """For + and >: the element line. For ~: key is the target, bare/kv/label the changes.
    For -: key is the first id, bare the others."""

    @property
    def where(self) -> str:
        return f"line {self.n}: {self.text}"


def parse_ops(text: str) -> list[Op]:
    ops: list[Op] = []
    errors: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        body = strip_comment(line).strip()
        if not body:
            continue
        sign = body[0]
        if sign not in "+~->":
            errors.append(
                f"line {n}: {body}: start with + (add), ~ (set), - (remove) or > (replace)"
            )
            continue
        rest = body[1:].strip()
        try:
            tokens = tokenize(rest)
            if sign in "+>":
                raw = parse_tokens(tokens)
            else:
                if not tokens:
                    raise LineError(f"{sign} needs an id")
                raw = parse_tokens([sign, *tokens])
        except LineError as e:
            errors.append(f"line {n}: {body}: {e}")
            continue
        ops.append(Op(sign, n, body, raw))  # type: ignore[arg-type]
    if errors:
        raise OpsError(errors)
    if not ops:
        raise OpsError(
            ["no operations. Write one per line: + kind @a ..., ~ id k=v, - id, > kind id ..."]
        )
    return ops


@dataclass
class Applied:
    model: Model
    ops: list[str] = field(default_factory=list[str])
    inverse: list[str] = field(default_factory=list[str])
    added: list[tuple[str | None, str]] = field(default_factory=list[tuple[str | None, str]])
    changed: list[str] = field(default_factory=list[str])
    removed: list[str] = field(default_factory=list[str])
    packs: set[str] = field(default_factory=set[str])
    closed: list[str] = field(default_factory=list[str])

    @property
    def touched(self) -> set[str]:
        return {i for _, i in self.added} | set(self.changed) | set(self.removed)


class _Ids:
    def __init__(self, model: Model, history_max: dict[str, int]) -> None:
        self.next: dict[str, int] = dict(history_max)
        for el in model:
            if el.prefix is not None:
                num = el.id[len(el.prefix) :]
                if num.isdigit():
                    self.next[el.prefix] = max(self.next.get(el.prefix, 0), int(num))

    def take(self, prefix: str) -> str:
        n = self.next.get(prefix, 0) + 1
        self.next[prefix] = n
        return f"{prefix}{n}"


def _diff_fields(old: Element, new: Element) -> list[str]:
    out: list[str] = []
    for name, fs in spec(type(new)).fields.items():
        a, b = getattr(old, name), getattr(new, name)
        if a == b:
            continue
        if b is None or b is False or (fs.meta.flag_enum and b == fs.default):
            out.append(f"{name}=")
        elif b is True:
            out.append(name)
        elif name == "label":
            out.append(f'label="{b}"')
        else:
            out.append(f"{name}={fmt_value(b)}")
    return out


def _try_value(cls: type[Element], name: str, tok: str) -> bool:
    ann = spec(cls).fields[name].annotation
    for t in getattr(ann, "__args__", (ann,)):
        if isinstance(t, type) and issubclass(t, Value):
            try:
                t.parse(tok)
                return True
            except ValueError:
                return False
    return False


def apply_ops(
    model: Model,
    ops: list[Op],
    *,
    batch: int,
    history_max: dict[str, int] | None = None,
    internal: bool = False,
) -> Applied:
    """Apply ops to model in place. Raises OpsError; the caller works on a copy."""
    reg = model.reg
    res = Applied(model)
    errors: list[str] = []
    ids = _Ids(model, history_max or {})
    pmap: dict[str, str] = {}
    assigned: list[str] = []

    # pass 1: assign ids, so placeholders may be used before they are defined
    for op in ops:
        if op.sign != "+":
            continue
        raw = op.raw
        try:
            cls = reg.cls_for(raw)
        except LineError as e:
            errors.append(f"{op.where}: {e}")
            continue
        key = raw.key
        if key == "_" or PLACEHOLDER.match(key):
            if cls.prefix is None:
                errors.append(f"{op.where}: a {cls.kind} is named by you: {usage(cls)}")
                continue
            new_id = ids.take(cls.prefix)
            assigned.append(new_id)
            if key != "_":
                if key in pmap:
                    errors.append(f"{op.where}: placeholder {key} defined twice")
                    continue
                pmap[key] = new_id
            res.added.append((None if key == "_" else key, new_id))
        elif cls.prefix is not None and not internal:
            errors.append(
                f"{op.where}: UEA assigns ids. Write + {cls.kind} @name ... (or _ if nothing"
                " refers to it)"
            )
    if errors:
        raise OpsError(errors)

    def mapper(where: str) -> Callable[[str], str]:
        def f(ref: str) -> str:
            if ref.startswith("@"):
                if ref not in pmap:
                    raise LineError(
                        f"placeholder {ref} is not defined in this batch (+ kind {ref} ...)"
                    )
                return pmap[ref]
            return ref

        return f

    added_iter = iter(assigned)
    for op in ops:
        try:
            if op.sign == "+":
                _add(model, res, op, mapper(op.where), added_iter, internal)
            elif op.sign == "-":
                for key in (op.raw.key, *op.raw.bare):
                    key = mapper(op.where)(key)
                    if key not in model:
                        raise LineError(f"{key} does not exist")
                    old = model.remove(key)
                    res.removed.append(key)
                    res.packs.add(type(old).pack)
                    res.ops.append(f"- {key}")
                    res.inverse.append(f"+ {old.line()}")
            elif op.sign == "~":
                _set(reg, model, res, op, mapper(op.where), batch)
            else:
                _replace(reg, model, res, op, mapper(op.where))
        except LineError as e:
            errors.append(f"{op.where}: {e}")
    if errors:
        raise OpsError(errors)
    res.inverse.reverse()
    # an element added and removed in one batch leaves no trace
    gone = set(res.removed)
    res.added = [(p, i) for p, i in res.added if i not in gone]
    res.changed = [
        i for i in dict.fromkeys(res.changed) if i in model and i not in {x for _, x in res.added}
    ]
    return res


def _check_placeholders(el: Element) -> None:
    for name, ref in refs_of(el):
        if ref.startswith("@"):
            raise LineError(f"{name}={ref}: placeholder not defined in this batch")


def _add(
    model: Model,
    res: Applied,
    op: Op,
    f: Callable[[str], str],
    added_iter: Iterator[str],
    internal: bool,
) -> None:
    raw = op.raw
    cls = model.reg.cls_for(raw)
    key = raw.key
    if key == "_" or PLACEHOLDER.match(key):
        key = next(added_iter)
    elif cls.prefix is None:
        check_key(cls, key)
    if key in model:
        el = model[key]
        if cls.prefix is None:
            raise LineError(
                f"{key} exists ({el.kind}); change it with ~ {key} k=v or > {el.kind} {key} ..."
            )
        raise LineError(f"{key} exists")
    el = element_from_raw(model.reg, RawLine(raw.kind, key, raw.bare, raw.label, raw.kv))
    el = map_refs(el, f)
    _check_placeholders(el)
    model.put(el)
    res.packs.add(type(el).pack)
    res.ops.append(f"+ {el.line()}")
    res.inverse.append(f"- {key}")
    if (cls.prefix is None or internal) and all(i != key for _, i in res.added):
        res.added.append((None, key))


def _set(
    reg: Registry, model: Model, res: Applied, op: Op, f: Callable[[str], str], batch: int
) -> None:
    key = f(op.raw.key)
    if key not in model:
        raise LineError(f"{key} does not exist")
    old = model[key]
    cls = type(old)
    sp = spec(cls)
    data: dict[str, Any] = {"id": key, **{n: getattr(old, n) for n in sp.fields}}
    for k, v in op.raw.kv:
        if k not in sp.fields:
            raise LineError(f"{cls.kind} has no field {k!r}. Fields: {' '.join(sp.fields)}")
        fs = sp.fields[k]
        if v == "":
            if fs.required:
                raise LineError(f"{k} is required and cannot be removed")
            data[k] = fs.default
        else:
            data[k] = v
    tokens = flag_tokens(cls)
    for tok in op.raw.bare:
        if tok == "done" and cls.kind == "req":
            data["done"] = batch
            data["rejected"] = None
            continue
        if tok in tokens:
            name, value = tokens[tok]
            data[name] = value
            continue
        cands = _positional_candidates(model, cls, tok)
        if len(cands) != 1:
            hint = " ".join(f"{p}={tok}" for p in (cands or sp.positional))
            raise LineError(
                f"what is {tok!r}? Flags: {' '.join(tokens) or 'none'}."
                f" Write field=value, e.g. {hint}"
            )
        data[cands[0]] = tok
    if op.raw.label is not None:
        data["label"] = op.raw.label or None
    new = map_refs(build(cls, data), f)
    _check_placeholders(new)
    if new == old:
        return
    model.put(new)
    res.packs.add(cls.pack)
    res.changed.append(key)
    res.ops.append(" ".join(["~", key, *_diff_fields(old, new)]))
    res.inverse.append(f"> {old.line()}")
    if cls.kind == "req" and getattr(new, "open", True) is False and getattr(old, "open", True):
        res.closed.append(key)


def _positional_candidates(model: Model, cls: type[Element], tok: str) -> list[str]:
    out: list[str] = []
    sp = spec(cls)
    for name in sp.positional:
        fs = sp.fields[name]
        if fs.meta.targets:
            target = model.get(tok)
            if target is not None:
                tkind = f"type:{target.category}" if target.kind == "type" else target.kind
                if tkind in fs.meta.targets:
                    out.append(name)
        elif fs.choices:
            if tok in fs.choices:
                out.append(name)
        elif _try_value(cls, name, tok):
            out.append(name)
    return out


def _replace(reg: Registry, model: Model, res: Applied, op: Op, f: Callable[[str], str]) -> None:
    raw = op.raw
    key = f(raw.key)
    if key not in model:
        raise LineError(f"{key} does not exist; add it with +")
    old = model[key]
    new = element_from_raw(reg, RawLine(raw.kind, key, raw.bare, raw.label, raw.kv))
    if type(new) is not type(old):
        raise LineError(
            f"{key} is a {old.kind}{' ' + old.category if old.category else ''}; > keeps the kind"
        )
    new = map_refs(new, f)
    _check_placeholders(new)
    if new == old:
        return
    model.put(new)
    res.packs.add(type(new).pack)
    res.changed.append(key)
    res.ops.append(f"> {new.line()}")
    res.inverse.append(f"> {old.line()}")

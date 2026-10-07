"""Element schemas and the conversion between elements and lines.

Every element kind is a frozen Pydantic model. Field metadata (`F`) says how a field is
written (positional, `key=value`, flag), its unit, and which kinds a reference may target.
"""

import re
import types
import typing
from dataclasses import dataclass
from functools import cache
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.fields import FieldInfo

from uea.core.syntax import LineError, RawLine, fmt_num, needs_quotes, quote
from uea.core.values import Value

ID_RE = re.compile(r"^([a-z]+)(\d+)$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
TYPE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class F:
    """Field metadata.

    doc: one line for `uea help <kind>`. unit: fixed unit of the value. targets: kinds a
    reference may point to (`type:wall` for a wall type). flag: a bool written as a bare
    token. flag_enum: a Literal whose non-default value is written as a bare token.
    """

    doc: str = ""
    unit: str | None = None
    targets: tuple[str, ...] = ()
    flag: bool = False
    flag_enum: bool = False


Status = Annotated[
    Literal["new", "existing", "demolish", "temp"],
    F("status; new unless flagged existing (Bestand), demolish or temp", flag_enum=True),
]


class Element(BaseModel):
    """Base of every element kind."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ClassVar[str] = ""
    pack: ClassVar[str] = ""
    prefix: ClassVar[str | None] = None
    """Id prefix for kinds whose ids UEA assigns; None for kinds the agent names."""
    positional: ClassVar[tuple[str, ...]] = ()
    doc: ClassVar[str] = ""
    category: ClassVar[str | None] = None
    """For `type` elements: the category written after the name (`type AW-365 wall`)."""

    id: str
    label: Annotated[str | None, F("free text")] = None

    @property
    def is_named(self) -> bool:
        return self.prefix is None

    def line(self) -> str:
        return to_line(self)

    def kv_order(self) -> tuple[str, ...]:
        """Order of the key=value fields in the line; the schema order by default."""
        return spec(type(self)).kv


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    meta: F
    required: bool
    default: Any
    annotation: Any

    @property
    def choices(self) -> tuple[str, ...]:
        return literal_values(self.annotation)


@dataclass(frozen=True, slots=True)
class KindSpec:
    fields: dict[str, FieldSpec]
    positional: tuple[str, ...]
    kv: tuple[str, ...]
    flags: tuple[str, ...]
    flag_enums: tuple[str, ...]


def literal_values(annotation: Any) -> tuple[str, ...]:
    """The allowed strings of a Literal annotation (also inside Optional/Annotated)."""
    origin = typing.get_origin(annotation)
    if origin is Literal:
        return tuple(str(a) for a in typing.get_args(annotation))
    if origin in (typing.Union, types.UnionType, Annotated):
        out: list[str] = []
        for a in typing.get_args(annotation):
            out.extend(literal_values(a))
        return tuple(out)
    return ()


def _meta(info: FieldInfo) -> F:
    for m in info.metadata:
        if isinstance(m, F):
            return m
    return F()


@cache
def spec(cls: type[Element]) -> KindSpec:
    fields: dict[str, FieldSpec] = {}
    for name, info in cls.model_fields.items():
        if name == "id":
            continue
        fields[name] = FieldSpec(
            name, _meta(info), info.is_required(), info.default, info.annotation
        )
    flags = tuple(n for n, f in fields.items() if f.meta.flag)
    flag_enums = tuple(n for n, f in fields.items() if f.meta.flag_enum)
    kv = tuple(
        n
        for n in fields
        if n not in cls.positional and n not in flags and n not in flag_enums and n != "label"
    )
    return KindSpec(fields, cls.positional, kv, flags, flag_enums)


def fmt_value(v: Any) -> str:
    if isinstance(v, Value):
        return v.fmt()
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return fmt_num(v)
    if isinstance(v, int):
        return str(v)
    s = str(v)
    return quote(s) if needs_quotes(s) else s


def to_line(el: Element) -> str:
    """The canonical line of an element."""
    sp = spec(type(el))
    parts = [el.kind, el.id]
    if el.category is not None:
        parts.append(el.category)
    parts.extend(fmt_value(getattr(el, n)) for n in sp.positional)
    if el.label is not None:
        parts.append(quote(el.label))
    for n in el.kv_order():
        v = getattr(el, n)
        if v is not None and v != sp.fields[n].default:
            parts.append(f"{n}={fmt_value(v)}")
    parts.extend(n for n in sp.flags if getattr(el, n))
    for n in sp.flag_enums:
        v = getattr(el, n)
        if v != sp.fields[n].default:
            parts.append(str(v))
    return " ".join(parts)


def usage(cls: type[Element]) -> str:
    """Short form of a kind's line, for error messages: `wall <id> <level> <type> ...`."""
    head = f"{cls.kind} <{'name' if cls.prefix is None else 'id'}>"
    if cls.category:
        head += f" {cls.category}"
    return " ".join([head, *(f"<{p}>" for p in cls.positional)])


def flag_tokens(cls: type[Element]) -> dict[str, tuple[str, str | bool]]:
    """Bare tokens a kind accepts after its positional fields: token -> (field, value)."""
    sp = spec(cls)
    out: dict[str, tuple[str, str | bool]] = {n: (n, True) for n in sp.flags}
    for n in sp.flag_enums:
        for v in sp.fields[n].choices:
            if v != sp.fields[n].default:
                out[v] = (n, v)
    return out


def validation_message(e: ValidationError) -> str:
    msgs: list[str] = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        if err["type"] == "missing":
            msg = "missing"
        elif err["type"] == "extra_forbidden":
            msg = "unknown field"
        elif err["type"] == "literal_error":
            msg = f"{err.get('input')!r}: {msg.lower()}"
        msgs.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(msgs)


def build(cls: type[Element], data: dict[str, Any]) -> Element:
    try:
        return cls.model_validate(data)
    except ValidationError as e:
        raise LineError(f"{cls.kind} {data.get('id', '?')}: {validation_message(e)}") from None


def raw_to_data(cls: type[Element], raw: RawLine) -> dict[str, Any]:
    """Field values of a line, as strings, checked against the kind's fields."""
    sp = spec(cls)
    data: dict[str, Any] = {"id": raw.key}
    bare = list(raw.bare)
    if cls.category is not None:
        bare = bare[1:]
    if len(bare) < len(sp.positional):
        missing = " ".join(f"<{p}>" for p in sp.positional[len(bare) :])
        raise LineError(f"{cls.kind} {raw.key}: missing {missing}. Usage: {usage(cls)} ...")
    data.update(zip(sp.positional, bare, strict=False))
    tokens = flag_tokens(cls)
    for tok in bare[len(sp.positional) :]:
        if tok not in tokens:
            known = " ".join(tokens) or "none"
            raise LineError(
                f"{cls.kind} {raw.key}: unknown flag {tok!r}. Flags: {known}. Usage: {usage(cls)}"
            )
        field, value = tokens[tok]
        if field in data:
            raise LineError(f"{cls.kind} {raw.key}: {field} given twice")
        data[field] = value
    if raw.label is not None:
        data["label"] = raw.label
    for k, v in raw.kv:
        if k == "label" and "label" not in data:
            data["label"] = v
            continue
        if k not in sp.kv:
            if k in sp.positional:
                raise LineError(
                    f"{cls.kind} {raw.key}: {k} is positional, write it without {k}=. "
                    f"Usage: {usage(cls)}"
                )
            raise LineError(f"{cls.kind} {raw.key}: unknown field {k!r}. Fields: {' '.join(sp.kv)}")
        data[k] = v
    return data


def check_key(cls: type[Element], key: str) -> None:
    if cls.prefix is None:
        pattern = TYPE_NAME_RE if cls.kind in {"type", "project"} else NAME_RE
        if cls.kind == "project":
            pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
        if not pattern.match(key):
            rule = (
                "letters, digits, _ and -"
                if cls.kind in {"type", "project"}
                else "a letter, then letters, digits or _ (no -: W-1.2 means grid W minus 1.2)"
            )
            raise LineError(f"{cls.kind} name {key!r}: use {rule}")
        if ID_RE.match(key):
            raise LineError(
                f"{cls.kind} name {key!r} looks like an element id; start names with a capital"
                " letter (EG, AW-365, A1)"
            )
    else:
        m = ID_RE.match(key)
        if not m or m.group(1) != cls.prefix:
            raise LineError(f"{cls.kind} id {key!r}: ids of this kind are {cls.prefix}<number>")

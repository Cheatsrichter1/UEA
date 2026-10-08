"""Structured field values: references, positions, spans, points, sizes and layers.

Each value parses from and formats to its line form, lists the element ids it references,
and can rename them (placeholders become ids when a batch is applied).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from uea.core.syntax import fmt_num

NAME = r"@?[A-Za-z][A-Za-z0-9_]*"
REFNAME = r"@?[A-Za-z][A-Za-z0-9_.-]*?"
NUM = r"\d+(?:\.\d+)?"
FACES = "nsewc"

_ANCHOR = re.compile(
    rf"^(?:(?P<ref>{NAME})(?:\.(?P<face>[{FACES}]))?|(?P<coord>-?{NUM}))"
    rf"(?:(?P<sign>[+-])(?P<dist>{NUM})?)?$"
)
_REF = re.compile(rf"^(?P<id>{REFNAME})(?:\.(?P<face>[{FACES}]))?$")
_SIZE = re.compile(rf"^(?P<w>{NUM})x(?P<h>{NUM})$")
_LAYER = re.compile(rf"^(?P<core>\*)?(?P<mat>[A-Za-z0-9_.-]+):(?P<t>{NUM})$")


class Value:
    """Base of all structured values. Subclasses are frozen dataclasses."""

    __slots__ = ()

    def fmt(self) -> str:
        raise NotImplementedError

    def refs(self) -> tuple[str, ...]:
        return ()

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return self

    @classmethod
    def parse(cls, s: str) -> Self:
        raise NotImplementedError

    def __str__(self) -> str:
        return self.fmt()

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        def coerce(v: Any) -> Any:
            if isinstance(v, cls):
                return v
            if isinstance(v, str):
                return cls.parse(v)
            raise ValueError(f"expected {cls.__name__}, got {v!r}")

        def ser(v: Any) -> str:
            assert isinstance(v, Value)
            return v.fmt()

        return core_schema.no_info_plain_validator_function(
            coerce, serialization=core_schema.plain_serializer_function_ser_schema(ser)
        )


@dataclass(frozen=True, slots=True)
class Ref(Value):
    """A reference to another element, optionally to one of its faces: `w5`, `w5.n`."""

    id: str
    face: str | None = None

    def fmt(self) -> str:
        return self.id if self.face is None else f"{self.id}.{self.face}"

    def refs(self) -> tuple[str, ...]:
        return (self.id,)

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return type(self)(f(self.id), self.face)

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _REF.match(s)
        if not m:
            raise ValueError(
                f"{s!r} is not a reference (an id or name, optionally with .n/.s/.e/.w)"
            )
        return cls(m["id"], m["face"])


@dataclass(frozen=True, slots=True)
class RefList(Value):
    """Comma-separated references: `d1,d4,d6`."""

    items: tuple[Ref, ...]

    def fmt(self) -> str:
        return ",".join(r.fmt() for r in self.items)

    def refs(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.items)

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return type(self)(tuple(r.map_refs(f) for r in self.items))

    @classmethod
    def parse(cls, s: str) -> Self:
        parts = s.split(",")
        if not s or any(not p for p in parts):
            raise ValueError(f"{s!r} is not a list of references like d1,d4")
        return cls(tuple(Ref.parse(p) for p in parts))


@dataclass(frozen=True, slots=True)
class Anchor(Value):
    """One coordinate relative to something: `w4+2.26`, `E-`, `w5.n-`, `f2.c`, `S`, `3.2`.

    `ref` names a grid, wall, opening or other element; `coord` is a raw coordinate instead.
    `sign` says from which side of the anchor and in which direction; `dist` is the distance.
    """

    ref: str | None
    face: str | None = None
    sign: str | None = None
    dist: float = 0.0
    coord: float | None = None

    def fmt(self) -> str:
        head = fmt_num(self.coord) if self.coord is not None else str(self.ref)
        if self.face:
            head += f".{self.face}"
        if self.sign:
            head += self.sign + (fmt_num(self.dist) if self.dist else "")
        return head

    def refs(self) -> tuple[str, ...]:
        return () if self.ref is None else (self.ref,)

    def map_refs(self, f: Callable[[str], str]) -> Self:
        if self.ref is None:
            return self
        return type(self)(f(self.ref), self.face, self.sign, self.dist, self.coord)

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _ANCHOR.match(s)
        if not m:
            raise ValueError(
                f"{s!r} is not a position; write anchor±distance, e.g. w4+2.26, E-, f2.c, S+1"
            )
        dist = float(m["dist"]) if m["dist"] else 0.0
        if m["coord"] is not None:
            return cls(None, None, m["sign"], dist, float(m["coord"]))
        return cls(m["ref"], m["face"], m["sign"], dist)


@dataclass(frozen=True, slots=True)
class Span(Value):
    """An extent between two anchors: `W..E`, `w1..w3` (the faces that face each other)."""

    a: Anchor
    b: Anchor

    def fmt(self) -> str:
        return f"{self.a.fmt()}..{self.b.fmt()}"

    def refs(self) -> tuple[str, ...]:
        return self.a.refs() + self.b.refs()

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return type(self)(self.a.map_refs(f), self.b.map_refs(f))

    @classmethod
    def parse(cls, s: str) -> Self:
        parts = s.split("..")
        if len(parts) != 2:
            raise ValueError(f"{s!r} is not a span; write a..b, e.g. W..E or w1..w3")
        return cls(Anchor.parse(parts[0]), Anchor.parse(parts[1]))


def parse_place(s: str) -> Anchor | Span:
    """A wall's x= or y=: a position (`w1+4.51`) or a span (`w4..w2`)."""
    return Span.parse(s) if ".." in s else Anchor.parse(s)


@dataclass(frozen=True, slots=True)
class Point(Value):
    """A plan point: `at=w4+1,w1+1` (x anchor, y anchor)."""

    x: Anchor
    y: Anchor

    def fmt(self) -> str:
        return f"{self.x.fmt()},{self.y.fmt()}"

    def refs(self) -> tuple[str, ...]:
        return self.x.refs() + self.y.refs()

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return type(self)(self.x.map_refs(f), self.y.map_refs(f))

    @classmethod
    def parse(cls, s: str) -> Self:
        parts = s.split(",")
        if len(parts) != 2:
            raise ValueError(f"{s!r} is not a point; write x,y, e.g. w4+1,w1+1")
        return cls(Anchor.parse(parts[0]), Anchor.parse(parts[1]))


@dataclass(frozen=True, slots=True)
class Size(Value):
    """Width x height in metres: `0.885x2.01`."""

    w: float
    h: float

    def fmt(self) -> str:
        return f"{fmt_num(self.w)}x{fmt_num(self.h)}"

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _SIZE.match(s)
        if not m:
            raise ValueError(f"{s!r} is not a size; write WxH in metres, e.g. 0.885x2.01")
        w, h = float(m["w"]), float(m["h"])
        if w <= 0 or h <= 0:
            raise ValueError(f"size {s} must be larger than 0")
        return cls(w, h)


@dataclass(frozen=True, slots=True)
class Layer:
    material: str
    t: float
    core: bool


@dataclass(frozen=True, slots=True)
class Layers(Value):
    """A build-up: `plaster:0.015,*brick:0.365,render:0.02`. `*` marks the core layer(s)."""

    items: tuple[Layer, ...]

    def fmt(self) -> str:
        return ",".join(f"{'*' if x.core else ''}{x.material}:{fmt_num(x.t)}" for x in self.items)

    @classmethod
    def parse(cls, s: str) -> Self:
        items: list[Layer] = []
        for part in s.split(","):
            m = _LAYER.match(part)
            if not m:
                raise ValueError(
                    f"layer {part!r}: write material:thickness, core with *, e.g. *brick:0.365"
                )
            t = float(m["t"])
            if t <= 0:
                raise ValueError(f"layer {part!r}: thickness must be larger than 0")
            items.append(Layer(m["mat"], t, bool(m["core"])))
        return cls(tuple(items))

    @property
    def total(self) -> float:
        return sum(x.t for x in self.items)

    @property
    def core(self) -> float:
        return sum(x.t for x in self.items if x.core)

    def before_core(self) -> float:
        """Thickness of the layers listed before the first core layer."""
        out = 0.0
        for x in self.items:
            if x.core:
                break
            out += x.t
        return out

    def after_core(self) -> float:
        """Thickness of the layers listed after the last core layer."""
        out = 0.0
        for x in reversed(self.items):
            if x.core:
                break
            out += x.t
        return out

"""Plumbing kinds (`plumb.uea`): sanitary fixtures, the water meter, risers, stacks and the sewer
connection (decision 0035).

A fixture stands on a wall face or in a room. The drinking water comes from the meter, the hot
water from a storage tank of the heating that heats drinking water; risers carry both up through
the storeys. The waste water runs to a stack (Fallleitung) or straight to the sewer connection.
The pipes between them are derived, not written. The types carry the pipe systems' sizes and
values from the manufacturer; the catalogue values in examples are placeholders, not design data.
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Anchor, Point, Ref
from uea.packs.pipes import Bores

Fixture = Literal[
    "basin", "sink", "wc", "urinal", "bidet", "shower", "bath", "wm", "dw", "tap", "floor"
]
FIXTURES: tuple[str, ...] = Fixture.__args__  # type: ignore[attr-defined]
Water = Literal["cold", "both", "none"]

WATER: dict[str, Water] = {
    "basin": "both",
    "sink": "both",
    "bidet": "both",
    "shower": "both",
    "bath": "both",
    "wc": "cold",
    "urinal": "cold",
    "wm": "cold",
    "dw": "cold",
    "tap": "cold",
    "floor": "none",
}
"""The water a fixture takes unless water= says otherwise."""
OUTLET_Z: dict[str, float] = {
    "basin": 1.0,
    "sink": 1.0,
    "bidet": 0.5,
    "shower": 2.1,
    "bath": 0.7,
    "wc": 1.0,
    "urinal": 1.2,
    "wm": 1.0,
    "dw": 0.5,
    "tap": 0.6,
    "floor": 0.0,
}
"""The height of a fixture's outlet above the FFL unless z= says otherwise, m. Planning
defaults, not norm values; what counts is the height difference to the meter."""
DRAINS = frozenset(FIXTURES) - {"tap"}
"""Fixtures with a waste pipe; an outside tap has none."""


# ---------- types ----------


class _PlumbType(Element):
    kind: ClassVar[str] = "type"
    pack: ClassVar[str] = "plumb"
    default: Annotated[bool, F("used by elements of its kind without type=", flag=True)] = False


class PipeType(_PlumbType):
    category: ClassVar[str | None] = "pipe"
    doc: ClassVar[str] = (
        "Drinking-water pipe system: type MV pipe sizes=16x2,20x2.25,26x3 k=0.007 bend=1.4"
        " tee=1.7. k: roughness; bend, tee: loss coefficients ζ of a bend and of a tee (the"
        " branch), from the manufacturer."
    )
    sizes: Annotated[Bores, F("sizes from small to large, outer diameter x wall", unit="mm")]
    k: Annotated[float, F("roughness of the pipe wall", unit="mm")]
    bend: Annotated[float, F("loss coefficient ζ of a bend")]
    tee: Annotated[float, F("loss coefficient ζ of a tee")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(b.dn is not None for b in self.sizes.items):
            raise ValueError("a drinking-water pipe has no DN: write outer diameter x wall")
        if self.k <= 0 or self.bend < 0 or self.tee < 0:
            raise ValueError("k must be more than 0, bend and tee 0 or more")
        return self


class DrainType(_PlumbType):
    category: ClassVar[str | None] = "drain"
    doc: ClassVar[str] = (
        "Drain pipe system: type HT drain sizes=50:50x1.8,70:75x1.9,100:110x2.7 (DN, then outer"
        " diameter x wall). The stack's type serves its branches too, the sewer's the pipes"
        " under the building."
    )
    sizes: Annotated[Bores, F("sizes from small to large, DN:outer diameter x wall", unit="mm")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(b.dn is None for b in self.sizes.items):
            raise ValueError("give each drain size its DN: 100:110x2.7")
        return self


# ---------- elements ----------


class San(Element):
    kind: ClassVar[str] = "san"
    pack: ClassVar[str] = "plumb"
    prefix: ClassVar[str | None] = "sa"
    positional: ClassVar[tuple[str, ...]] = ("host", "fixture")
    doc: ClassVar[str] = (
        "A sanitary fixture on a wall face (san sa1 w4 sink y=f2.c) or in a room (san sa7 r9"
        " shower at=w15-0.45,w10-0.45). Fixtures: basin, sink, wc, urinal, bidet, shower, bath,"
        " wm (washing machine), dw (dishwasher), tap (outside tap), floor (floor drain). z= its"
        " outlet; to= the stack or sewer its waste runs to, else the nearest on its storey."
    )
    host: Annotated[Ref, F("wall face, or room", targets=("wall", "room"))]
    fixture: Annotated[Fixture, F("what it is")]
    at: Annotated[Point | None, F("point in the room, x,y", unit="m")] = None
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[Anchor | None, F("centre along a wall in any direction", unit="m")] = None
    z: Annotated[float | None, F("height of its water outlet above the FFL", unit="m")] = None
    water: Annotated[
        Water | None, F("cold, both (cold and hot) or none; by fixture if left out")
    ] = None
    to: Annotated[
        Ref | None, F("stack or sewer its waste water runs to", targets=("stack", "sewer"))
    ] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        axes = sum(v is not None for v in (self.x, self.y, self.s))
        if axes > 1:
            raise ValueError("give one of x=, y= or s=, for a fixture on a wall")
        if axes and self.at is not None:
            raise ValueError("at= is for a fixture in a room, x=/y=/s= for one on a wall")
        return self

    @property
    def supply(self) -> Water:
        return self.water or WATER[self.fixture]

    @property
    def drains(self) -> bool:
        return self.fixture in DRAINS

    @property
    def width(self) -> float:
        return 0.5


class Meter(Element):
    kind: ClassVar[str] = "meter"
    pack: ClassVar[str] = "plumb"
    prefix: ClassVar[str | None] = "wz"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "Where the drinking water enters, with its meter (Wasserzähler): meter wz1 r3"
        " at=w4+0.3,w3-0.3 p=4 dp=450. p: the lowest supply pressure the water supplier states;"
        " dp: the loss of the meter, filter and the other apparatus at the design flow."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    at: Annotated[
        Point | None, F("plan point x,y; the middle of the room if left out", unit="m")
    ] = None
    z: Annotated[float, F("height above the FFL", unit="m")] = 0.5
    p: Annotated[float | None, F("lowest supply pressure", unit="bar")] = None
    dp: Annotated[float | None, F("pressure loss of the meter and apparatus", unit="hPa")] = None
    type: Annotated[
        Ref | None, F("pipe system; the default pipe type if left out", targets=("type:pipe",))
    ] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.p is not None and self.p <= 0:
            raise ValueError("p must be more than 0")
        if self.dp is not None and self.dp < 0:
            raise ValueError("dp must be 0 or more")
        return self


class Riser(Element):
    kind: ClassVar[str] = "riser"
    pack: ClassVar[str] = "plumb"
    prefix: ClassVar[str | None] = "sr"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A riser (Steigleitung) for cold and hot water, from a room up through the storeys"
        " above: riser sr1 r3 at=w4+0.2,w3-1. Fixtures on other storeys than the meter get"
        " their water through it."
    )
    host: Annotated[Ref, F("room on its lowest storey", targets=("room",))]
    at: Annotated[
        Point | None, F("plan point x,y; the middle of the room if left out", unit="m")
    ] = None


class Stack(Element):
    kind: ClassVar[str] = "stack"
    pack: ClassVar[str] = "plumb"
    prefix: ClassVar[str | None] = "fl"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A stack (Fallleitung) with its vent through the roof, from a room up through the"
        " storeys above: stack fl1 r3 at=w4+0.15,w3-1.6. Its foot runs to the sewer."
    )
    host: Annotated[Ref, F("room on its lowest storey", targets=("room",))]
    at: Annotated[
        Point | None, F("plan point x,y; the middle of the room if left out", unit="m")
    ] = None
    type: Annotated[
        Ref | None,
        F("drain pipe system; the default drain type if left out", targets=("type:drain",)),
    ] = None


class Sewer(Element):
    kind: ClassVar[str] = "sewer"
    pack: ClassVar[str] = "plumb"
    prefix: ClassVar[str | None] = "kn"
    positional: ClassVar[tuple[str, ...]] = ("level",)
    doc: ClassVar[str] = (
        "Where the waste water leaves the building for the public sewer (an inspection chamber"
        " or the wall it passes): sewer kn1 EG at=W-2,N-2. The pipes to it run under the"
        " storey's floor."
    )
    level: Annotated[Ref, F("storey whose floor the pipes run under", targets=("level",))]
    at: Annotated[Point, F("plan point x,y", unit="m")]
    type: Annotated[
        Ref | None,
        F("drain pipe system; the default drain type if left out", targets=("type:drain",)),
    ] = None


KINDS: tuple[type[Element], ...] = (
    PipeType,
    DrainType,
    San,
    Meter,
    Riser,
    Stack,
    Sewer,
)

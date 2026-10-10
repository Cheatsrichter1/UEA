"""Heating element kinds (`heat.uea`): generators, storage tanks, manifolds and emitters.

A heat generator stands at a point of a storey (`gen g1 EG at=W-1.2,N-1`), a tank in a room, a
manifold in a niche or on a wall face; underfloor heating covers a room, a radiator hangs on a
wall. `src=` says where each gets its heat from: a manifold from a tank or a generator, an emitter
from a manifold (or, a radiator, from a tank or generator). The types carry the product data
(decision 0034); the catalogue values in examples are placeholders, not design data.
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Anchor, Point, Ref
from uea.packs.mount import WallMounted

# ---------- types ----------


class _HeatType(Element):
    kind: ClassVar[str] = "type"
    pack: ClassVar[str] = "heat"
    default: Annotated[bool, F("used by elements of its kind without type=", flag=True)] = False

    def _positive(self, *names: str) -> None:
        for n in names:
            v = getattr(self, n)
            if v is not None and v <= 0:
                raise ValueError(f"{n} must be larger than 0")


class GenType(_HeatType):
    category: ClassVar[str | None] = "gen"
    doc: ClassVar[str] = (
        "Heat generator type: type WP-8 gen kw=8 source=air. kw: heat output at the design"
        " outdoor temperature and flow temperature, from the manufacturer."
    )
    kw: Annotated[float, F("heat output at the design point", unit="kW")]
    source: Annotated[
        Literal["air", "ground", "water", "gas", "oil", "wood", "district", "electric"] | None,
        F("heat source: air, ground, water (heat pumps), gas, oil, wood, district, electric"),
    ] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("kw")
        return self


class TankType(_HeatType):
    category: ClassVar[str | None] = "tank"
    doc: ClassVar[str] = (
        "Storage tank type: type HM-200 tank vol=200 dhw (dhw: heats drinking water)."
    )
    vol: Annotated[float, F("volume", unit="l")]
    dhw: Annotated[bool, F("heats drinking water", flag=True)] = False

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("vol")
        return self


class ManType(_HeatType):
    category: ClassVar[str | None] = "man"
    doc: ClassVar[str] = "Manifold type (Heizkreisverteiler): type HKV-10 man outlets=10 w=0.55."
    outlets: Annotated[int, F("heating circuits it can connect")]
    w: Annotated[float | None, F("width of its cabinet", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("outlets", "w")
        return self


class UfhType(_HeatType):
    category: ClassVar[str | None] = "ufh"
    doc: ClassVar[str] = (
        "Underfloor heating type (Fußbodenheizung): type FBH-15 ufh spacing=0.15 q=60 max=100."
        " q: heat output per m² at the system's design temperatures and the floor covering,"
        " from the manufacturer; max: the longest loop, connection lines included."
    )
    spacing: Annotated[float, F("pipe spacing", unit="m")]
    q: Annotated[float, F("heat output per floor area", unit="W/m²")]
    max: Annotated[float, F("longest loop, with its connection lines", unit="m")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("spacing", "q", "max")
        return self


class RadType(_HeatType):
    category: ClassVar[str | None] = "rad"
    doc: ClassVar[str] = (
        "Radiator type: type HK-22 rad w=1100 length=1 height=0.6. w: heat output at the system's"
        " design temperatures, from the manufacturer."
    )
    w: Annotated[float, F("heat output at the design temperatures", unit="W")]
    length: Annotated[float | None, F("length", unit="m")] = None
    height: Annotated[float | None, F("height", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("w", "length", "height")
        return self


# ---------- elements ----------


class Gen(Element):
    kind: ClassVar[str] = "gen"
    pack: ClassVar[str] = "heat"
    prefix: ClassVar[str | None] = "g"
    positional: ClassVar[tuple[str, ...]] = ("level",)
    doc: ClassVar[str] = (
        "A heat generator (heat pump, boiler) on a storey, inside or outside:"
        ' gen g1 EG at=W-1.2,N-1 type=WP-8 "Wärmepumpe außen".'
    )
    level: Annotated[Ref, F("storey", targets=("level",))]
    at: Annotated[Point, F("plan point x,y", unit="m")]
    z: Annotated[float, F("height above the FFL", unit="m")] = 0.0
    type: Annotated[Ref | None, F("generator type; default if left out", targets=("type:gen",))] = (
        None
    )


class Tank(Element):
    kind: ClassVar[str] = "tank"
    pack: ClassVar[str] = "heat"
    prefix: ClassVar[str | None] = "t"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A storage tank (or a heat pump's indoor unit with one) in a room:"
        " tank t1 r3 at=w4+0.4,w5+0.4 src=g1. at= default the middle of the room."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    at: Annotated[Point | None, F("plan point x,y", unit="m")] = None
    src: Annotated[Ref | None, F("generator that heats it", targets=("gen",))] = None
    type: Annotated[Ref | None, F("tank type; default if left out", targets=("type:tank",))] = None


class Man(Element):
    kind: ClassVar[str] = "man"
    pack: ClassVar[str] = "heat"
    prefix: ClassVar[str | None] = "hv"
    positional: ClassVar[tuple[str, ...]] = ("host", "src")
    doc: ClassVar[str] = (
        "A manifold (Heizkreisverteiler) in a niche, or on a wall face like a device:"
        " man hv1 ni1 t1, man hv2 w12.n g1 x=w15+0.5 z=0.6."
    )
    host: Annotated[Ref, F("niche, or wall face", targets=("niche", "wall"))]
    src: Annotated[Ref, F("tank or generator it gets its heat from", targets=("tank", "gen"))]
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[Anchor | None, F("centre along a wall in any direction", unit="m")] = None
    z: Annotated[float | None, F("height of its centre above the FFL", unit="m")] = None
    type: Annotated[Ref | None, F("manifold type; default if left out", targets=("type:man",))] = (
        None
    )
    default_z: ClassVar[float | None] = 0.6

    @property
    def width(self) -> float:
        return 0.5


class Ufh(Element):
    kind: ClassVar[str] = "ufh"
    pack: ClassVar[str] = "heat"
    prefix: ClassVar[str | None] = "uh"
    positional: ClassVar[tuple[str, ...]] = ("room", "src")
    doc: ClassVar[str] = (
        "Underfloor heating over a room's floor, from a manifold: ufh uh1 r1 hv1. area= the"
        " heated part, if not the whole finished floor."
    )
    room: Annotated[Ref, F("room", targets=("room",))]
    src: Annotated[Ref, F("manifold", targets=("man",))]
    area: Annotated[float | None, F("heated floor area", unit="m²")] = None
    type: Annotated[Ref | None, F("type; default if left out", targets=("type:ufh",))] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.area is not None and self.area <= 0:
            raise ValueError("area must be larger than 0")
        return self


class Rad(WallMounted):
    kind: ClassVar[str] = "rad"
    pack: ClassVar[str] = "heat"
    prefix: ClassVar[str | None] = "hk"
    positional: ClassVar[tuple[str, ...]] = ("host", "src")
    default_z: ClassVar[float | None] = 0.45
    doc: ClassVar[str] = (
        "A radiator (Heizkörper) on a wall face: rad hk1 w1 hv1 x=f1. z= its centre, 0.45 if"
        " left out."
    )
    src: Annotated[Ref, F("manifold, tank or generator", targets=("man", "tank", "gen"))]
    type: Annotated[Ref | None, F("type; default if left out", targets=("type:rad",))] = None

    @property
    def width(self) -> float:
        return 1.0


KINDS: tuple[type[Element], ...] = (
    GenType,
    TankType,
    ManType,
    UfhType,
    RadType,
    Gen,
    Tank,
    Man,
    Ufh,
    Rad,
)

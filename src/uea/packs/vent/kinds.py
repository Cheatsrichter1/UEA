"""Ventilation kinds (`vent.uea`): central units, decentral units and air terminals
(decision 0038).

A central unit with heat recovery (Lüftungsgerät, `ahu`) stands in a room; its air terminals
(`air`) sit in the rooms it supplies and extracts, and on the facade or roof where the outdoor air
comes in and the exhaust air leaves. The ducts between them are derived, not written. A
decentral unit (`fan`) goes through an exterior wall: a push-pull pair with heat recovery
(`pair=`, the second half derived), an exhaust fan, or a unit that supplies and extracts at once.
The types carry the product data; the catalogue values in examples are placeholders, not design
data.
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Anchor, Point, Ref
from uea.packs.mount import WallMounted
from uea.packs.pipes import Diameters

Role = Literal["sup", "ext", "oda", "eha"]
ROLES: tuple[str, ...] = Role.__args__  # type: ignore[attr-defined]
FanMode = Literal["alt", "ext", "both"]

# ---------- types ----------


class _VentType(Element):
    kind: ClassVar[str] = "type"
    pack: ClassVar[str] = "vent"
    default: Annotated[bool, F("used by elements of its kind without type=", flag=True)] = False

    def _positive(self, *names: str) -> None:
        for n in names:
            v = getattr(self, n)
            if v is not None and v <= 0:
                raise ValueError(f"{n} must be larger than 0")


class AhuType(_VentType):
    category: ClassVar[str | None] = "ahu"
    doc: ClassVar[str] = (
        "Central ventilation unit type (Lüftungsgerät mit Wärmerückgewinnung): type KWL-250 ahu"
        " flow=250 dp=150 hr=0.85. flow: the largest air flow; dp: the external pressure it"
        " delivers at that flow, for each side; hr: heat recovery; from the manufacturer."
    )
    flow: Annotated[float, F("largest air flow", unit="m³/h")]
    dp: Annotated[float | None, F("external pressure at that flow", unit="Pa")] = None
    hr: Annotated[float | None, F("heat recovery efficiency, 0 to 1")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("flow", "dp", "hr")
        if self.hr is not None and self.hr > 1:
            raise ValueError("hr is a share: at most 1")
        return self


class FanType(_VentType):
    category: ClassVar[str | None] = "fan"
    doc: ClassVar[str] = (
        "Decentral unit type (dezentrales Lüftungsgerät, Abluftventilator): type DZ-160 fan"
        " flow=30 hr=0.8. flow: its air flow at the nominal level, through the unit; from the"
        " manufacturer."
    )
    flow: Annotated[float, F("air flow at the nominal level", unit="m³/h")]
    hr: Annotated[float | None, F("heat recovery efficiency, 0 to 1")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._positive("flow", "hr")
        if self.hr is not None and self.hr > 1:
            raise ValueError("hr is a share: at most 1")
        return self


class DuctType(_VentType):
    category: ClassVar[str | None] = "duct"
    doc: ClassVar[str] = (
        "Round duct system: type R duct sizes=80,100,125,160 k=0.15 bend=0.3 tee=0.6 default"
        " (inner diameters, mm). k: roughness; bend, tee: loss coefficients ζ, from the"
        " manufacturer."
    )
    sizes: Annotated[Diameters, F("inner diameters from small to large", unit="mm")]
    k: Annotated[float, F("roughness of the duct wall", unit="mm")]
    bend: Annotated[float, F("loss coefficient ζ of a bend")]
    tee: Annotated[float, F("loss coefficient ζ of a tee")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.k <= 0 or self.bend < 0 or self.tee < 0:
            raise ValueError("k must be more than 0, bend and tee 0 or more")
        return self


# ---------- elements ----------


class Ahu(Element):
    kind: ClassVar[str] = "ahu"
    pack: ClassVar[str] = "vent"
    prefix: ClassVar[str | None] = "lg"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A central ventilation unit with heat recovery in a room: ahu lg1 r3 at=w4+0.5,w3-0.4."
        " at= default the middle of the room; z= its duct connections above the FFL."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    at: Annotated[Point | None, F("plan point x,y", unit="m")] = None
    z: Annotated[float, F("height of its duct connections above the FFL", unit="m")] = 1.8
    type: Annotated[Ref | None, F("unit type; default if left out", targets=("type:ahu",))] = None


class Fan(WallMounted):
    kind: ClassVar[str] = "fan"
    pack: ClassVar[str] = "vent"
    prefix: ClassVar[str | None] = "vl"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    default_z: ClassVar[float | None] = 2.2
    doc: ClassVar[str] = (
        "A decentral unit through an exterior wall: fan vl1 w11 y=w12-0.5 pair=vl2. mode: alt"
        " (push-pull, in pairs; the default), ext (exhaust fan), both (supplies and extracts at"
        " once). pair= the other unit of a push-pull pair; the other side is derived. z= 2.2 if"
        " left out."
    )
    mode: Annotated[FanMode, F("alt (push-pull pair), ext (exhaust) or both")] = "alt"
    pair: Annotated[Ref | None, F("the other unit of its push-pull pair", targets=("fan",))] = None
    type: Annotated[Ref | None, F("unit type; default if left out", targets=("type:fan",))] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.pair is not None and self.mode != "alt":
            raise ValueError("pair= is for push-pull units (mode alt)")
        if self.pair is not None and self.pair.id == self.id:
            raise ValueError("a unit is not its own pair")
        return self

    @property
    def width(self) -> float:
        return 0.25


class Air(Element):
    kind: ClassVar[str] = "air"
    pack: ClassVar[str] = "vent"
    prefix: ClassVar[str | None] = "ld"
    positional: ClassVar[tuple[str, ...]] = ("host", "role")
    doc: ClassVar[str] = (
        "An air terminal of a central unit (Luftdurchlass): in a room for supply or extract air"
        " (air ld1 r2 sup at=w2-1.5,w1+2; at= default the middle, z= default the ceiling), or on"
        " an exterior wall for outdoor or exhaust air (air ld9 w4 oda y=w3-1 z=2.4). role: sup,"
        " ext, oda (outdoor air in), eha (exhaust air out). src= its unit; the only or nearest"
        " if left out."
    )
    host: Annotated[Ref, F("room, or wall for oda and eha", targets=("room", "wall"))]
    role: Annotated[Role, F("sup, ext, oda or eha")]
    at: Annotated[Point | None, F("plan point in the room, x,y", unit="m")] = None
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[Anchor | None, F("centre along a wall in any direction", unit="m")] = None
    z: Annotated[float | None, F("height of its centre above the FFL", unit="m")] = None
    src: Annotated[Ref | None, F("its central unit", targets=("ahu",))] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        axes = sum(v is not None for v in (self.x, self.y, self.s))
        if axes > 1:
            raise ValueError("give one of x=, y= or s=, for a terminal on a wall")
        if axes and self.at is not None:
            raise ValueError("at= is for a terminal in a room, x=/y=/s= for one on a wall")
        return self

    @property
    def width(self) -> float:
        return 0.2


KINDS: tuple[type[Element], ...] = (AhuType, FanType, DuctType, Ahu, Fan, Air)

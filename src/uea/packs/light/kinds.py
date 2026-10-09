"""Lighting kinds (`light.uea`): luminaire types and luminaires.

In v1 the light pack only holds the luminaires, which the electrical design places in rooms and
wires through the switches that control them (decision 0025). Lighting design and photometric
calculation come later (decision 0006).
"""

from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Anchor, Point, Ref


class LumType(Element):
    kind: ClassVar[str] = "type"
    pack: ClassVar[str] = "light"
    category: ClassVar[str | None] = "lum"
    doc: ClassVar[str] = "Luminaire type. A luminaire without type= uses the type marked default."
    flux: Annotated[float | None, F("luminous flux", unit="lm")] = None
    w: Annotated[float | None, F("power", unit="W")] = None
    dist: Annotated[
        str | None, F("light distribution for the photometric calculation, e.g. cos1, cos3")
    ] = None
    default: Annotated[bool, F("used by luminaires without type=", flag=True)] = False

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.w is not None and self.w <= 0:
            raise ValueError("w must be larger than 0")
        if self.flux is not None and self.flux <= 0:
            raise ValueError("flux must be larger than 0")
        return self


class Lum(Element):
    kind: ClassVar[str] = "lum"
    pack: ClassVar[str] = "light"
    prefix: ClassVar[str | None] = "l"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A luminaire. In a room (host r2): at= a point, z= its height; by default the middle of"
        " the room at the ceiling. On a wall (host w1.s): x=/y= along it, z= its height."
    )
    host: Annotated[Ref, F("room, or wall face", targets=("room", "wall"))]
    at: Annotated[Point | None, F("point in the room, x,y", unit="m")] = None
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[Anchor | None, F("centre along a wall in any direction", unit="m")] = None
    z: Annotated[float | None, F("height of its centre above the FFL", unit="m")] = None
    type: Annotated[
        Ref | None, F("luminaire type; default type if left out", targets=("type:lum",))
    ] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        axes = sum(v is not None for v in (self.x, self.y, self.s))
        if axes > 1:
            raise ValueError("give one of x=, y= or s=, for a luminaire on a wall")
        if axes and self.at is not None:
            raise ValueError("at= is for a luminaire in a room, x=/y=/s= for one on a wall")
        return self

    @property
    def width(self) -> float:
        return 0.2


KINDS: tuple[type[Element], ...] = (LumType, Lum)

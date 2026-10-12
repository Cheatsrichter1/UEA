"""Structural kinds (`struct.uea`, decision 0040): what the architecture does not give.

The load-bearing walls and the slabs are the architect's (`lb`). A beam (Unterzug) carries a
slab and the walls on it where no wall is under them; a load is a point or line load the rooms'
uses do not cover (a buffer tank, a heavy partition the agent writes as a load); the rafters
give the timber of a gable roof. Sections and
materials are rows of the office's tables, not types in the model: their values are catalogue
and norm data.
"""

from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.schema import TYPE_NAME_RE, Element, F
from uea.core.values import Point, Ref


class Beam(Element):
    kind: ClassVar[str] = "beam"
    pack: ClassVar[str] = "struct"
    prefix: ClassVar[str | None] = "bm"
    positional: ClassVar[tuple[str, ...]] = ("level", "section")
    doc: ClassVar[str] = (
        "A beam (Unterzug) under the slab of a storey: beam bm1 OG HEB-160 a=w6,w1+1 b=w6,w5."
        " It carries that slab and the walls of the storey that stand on it, and rests on the"
        " load-bearing walls of the storey below that it crosses. section: a row of the"
        " office's beam-section table."
    )
    level: Annotated[Ref, F("storey whose slab it carries", targets=("level",))]
    section: Annotated[str, F("section, a name in the office's beam-section table")]
    a: Annotated[Point, F("start of its axis, a point x,y")]
    b: Annotated[Point, F("end of its axis, a point x,y")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not TYPE_NAME_RE.match(self.section):
            raise ValueError(f"section {self.section!r}: a name like HEB-160 or GL24h-12x24")
        return self


class Load(Element):
    kind: ClassVar[str] = "load"
    pack: ClassVar[str] = "struct"
    prefix: ClassVar[str | None] = "lo"
    positional: ClassVar[tuple[str, ...]] = ("level",)
    doc: ClassVar[str] = (
        'A load on the slab of a storey: load lo1 OG g=3 at=w4+0.5,w5+0.5 "Pufferspeicher 300 l"'
        " (a point load, kN), or a=/b= for a line load (kN/m). g permanent, q imposed,"
        " characteristic."
    )
    level: Annotated[Ref, F("storey whose slab carries it", targets=("level",))]
    g: Annotated[float, F("permanent part, characteristic", unit="kN or kN/m")] = 0.0
    q: Annotated[float, F("imposed part, characteristic", unit="kN or kN/m")] = 0.0
    at: Annotated[Point | None, F("a point load: where it stands")] = None
    a: Annotated[Point | None, F("a line load: the start of its line")] = None
    b: Annotated[Point | None, F("a line load: the end of its line")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.g < 0 or self.q < 0 or self.g + self.q <= 0:
            raise ValueError("give g= and/or q=, 0 or more, not both 0")
        line = self.a is not None or self.b is not None
        if line == (self.at is not None) or (line and (self.a is None or self.b is None)):
            raise ValueError("give at= (a point load) or a= and b= (a line load)")
        return self


class Rafter(Element):
    kind: ClassVar[str] = "rafter"
    pack: ClassVar[str] = "struct"
    prefix: ClassVar[str | None] = "sp"
    positional: ClassVar[tuple[str, ...]] = ("roof", "material")
    doc: ClassVar[str] = (
        "The rafters of a gable roof (Sparren of a Sparren- or Kehlbalkendach): rafter sp1 rf1"
        " C24 b=0.08 h=0.2 e=0.8. b, h: the section; e: the spacing. collar= the height of a"
        " collar beam (Kehlbalken) above the rafters' feet, cb= ch= its section if not the"
        " rafter's. material: a strength class of the office's timber table."
    )
    roof: Annotated[Ref, F("the roof", targets=("roof",))]
    material: Annotated[str, F("strength class, a row of the office's timber table: C24")]
    b: Annotated[float, F("width of a rafter", unit="m")]
    h: Annotated[float, F("depth of a rafter", unit="m")]
    e: Annotated[float, F("spacing of the rafters", unit="m")]
    collar: Annotated[
        float | None, F("height of the collar beam's axis above the rafters' feet", unit="m")
    ] = None
    cb: Annotated[float | None, F("width of the collar beam", unit="m")] = None
    ch: Annotated[float | None, F("depth of the collar beam", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not TYPE_NAME_RE.match(self.material):
            raise ValueError(f"material {self.material!r}: a strength class like C24 or GL24h")
        for n in ("b", "h", "e", "collar", "cb", "ch"):
            v = getattr(self, n)
            if v is not None and v <= 0:
                raise ValueError(f"{n} must be more than 0")
        if (self.cb is not None or self.ch is not None) and self.collar is None:
            raise ValueError("cb= and ch= are the collar beam's: give collar= too")
        return self


KINDS: tuple[type[Element], ...] = (Beam, Load, Rafter)

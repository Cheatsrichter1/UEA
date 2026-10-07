"""The project pack: project data, levels and grids, shared by every discipline (`project.uea`)."""

from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.registry import Pack
from uea.core.schema import Element, F


class Project(Element):
    kind: ClassVar[str] = "project"
    pack: ClassVar[str] = "project"
    doc: ClassVar[str] = "The project: name, site, terrain height. One per project."
    site: Annotated[str | None, F("country and Land, e.g. DE-HE")] = None
    plz: Annotated[str | None, F("postcode")] = None
    ground: Annotated[float | None, F("terrain height relative to ±0.00 (OKFF EG)", unit="m")] = (
        None
    )


class Level(Element):
    kind: ClassVar[str] = "level"
    pack: ClassVar[str] = "project"
    doc: ClassVar[str] = (
        "A storey. z is its OKFF; OK Rohdecke is z - fb. Windows hang from head (Sturzhöhe)."
    )
    z: Annotated[float, F("OKFF; ±0.00 is OKFF of the ground storey", unit="m")]
    fb: Annotated[float, F("Fußbodenaufbau: OKFF minus OK Rohdecke", unit="m")] = 0.0
    head: Annotated[float | None, F("Sturzhöhe: window heads above OKFF", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.fb < 0:
            raise ValueError("fb must not be negative")
        if self.head is not None and self.head <= 0:
            raise ValueError("head must be above OKFF")
        return self


class Grid(Element):
    kind: ClassVar[str] = "grid"
    pack: ClassVar[str] = "project"
    doc: ClassVar[str] = "A grid line: x= for a line along y, y= for a line along x."
    x: Annotated[float | None, F("x of a grid line running along y", unit="m")] = None
    y: Annotated[float | None, F("y of a grid line running along x", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.x is None) == (self.y is None):
            raise ValueError("give exactly one of x= or y=")
        return self

    @property
    def axis(self) -> str:
        return "x" if self.x is not None else "y"

    @property
    def coord(self) -> float:
        v = self.x if self.x is not None else self.y
        assert v is not None
        return v


PACK = Pack(
    name="project",
    title="Project, levels and grids",
    kinds=(Project, Level, Grid),
)

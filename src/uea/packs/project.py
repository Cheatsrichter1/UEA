"""The project pack: project data, levels and grids, shared by every discipline (`project.uea`)."""

from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.registry import Pack
from uea.core.schema import Element, F


class Project(Element):
    kind: ClassVar[str] = "project"
    pack: ClassVar[str] = "project"
    doc: ClassVar[str] = (
        'The project, one per project: project <name> "title" site=DE-HE postcode=64283 ground=-0.3'
    )
    site: Annotated[str | None, F("country and state as ISO 3166-2, e.g. DE-HE")] = None
    postcode: Annotated[str | None, F("postcode")] = None
    ground: Annotated[
        float | None, F("terrain height relative to ±0.00, the ground storey's FFL", unit="m")
    ] = None


class Level(Element):
    kind: ClassVar[str] = "level"
    pack: ClassVar[str] = "project"
    doc: ClassVar[str] = (
        "A storey. z is its FFL (finished floor level, OKFF); its SSL (structural slab level, OK"
        " Rohdecke) is z - fb. Windows hang from head (Sturzhöhe)."
    )
    z: Annotated[float, F("FFL; ±0.00 is the FFL of the ground storey", unit="m")]
    fb: Annotated[float, F("floor build-up: FFL minus SSL", unit="m")] = 0.0
    head: Annotated[float | None, F("head height: window heads above the FFL", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.fb < 0:
            raise ValueError("fb must not be negative")
        if self.head is not None and self.head <= 0:
            raise ValueError("head must be above the FFL")
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

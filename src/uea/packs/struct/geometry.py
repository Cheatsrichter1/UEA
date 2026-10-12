"""Where the structural elements are (decision 0040): beams and loads in plan."""

from dataclasses import dataclass, field

from shapely.geometry import LineString
from shapely.geometry import Point as SPoint

from uea.core.values import Point
from uea.derive import Derived, GeoError
from uea.packs.arch.geometry import Resolver
from uea.packs.struct.kinds import Beam, Load

SAMPLE = 0.05
"""A line load is shared out as point loads this far apart (m)."""


@dataclass
class BeamGeo:
    id: str
    level: str
    """The storey whose slab it carries; it lies in the storey below."""
    section: str
    a: tuple[float, float]
    b: tuple[float, float]

    @property
    def line(self) -> LineString:
        return LineString([self.a, self.b])

    @property
    def length(self) -> float:
        return self.line.length

    def s_of(self, x: float, y: float) -> float:
        return float(self.line.project(SPoint(x, y)))


@dataclass
class LoadGeo:
    id: str
    level: str
    g: float
    q: float
    pts: list[tuple[float, float]]
    """A point load: its point. A line load: points SAMPLE apart, each carrying its stretch."""
    length: float = 0.0
    """A line load: the length of its line; 0 for a point load."""

    def share(self) -> tuple[float, float]:
        """g and q of each point, kN."""
        if not self.length:
            return self.g, self.q
        n = len(self.pts)
        return self.g * self.length / n, self.q * self.length / n


@dataclass
class StructGeo:
    beams: dict[str, BeamGeo] = field(default_factory=dict[str, BeamGeo])
    loads: dict[str, LoadGeo] = field(default_factory=dict[str, LoadGeo])


def derive_struct(d: Derived) -> None:
    sg = d.struct = StructGeo()
    arch = Resolver(d, reuse=True)

    def pt(p: Point) -> tuple[float, float]:
        return (arch.point(p.x, "x"), arch.point(p.y, "y"))

    for el in d.model.of_kind("beam"):
        assert isinstance(el, Beam)

        def beam(el: Beam = el) -> BeamGeo:
            arch.level(el.level.id)
            a, b = pt(el.a), pt(el.b)
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6:
                raise GeoError("a= and b= are the same point", "give the beam a length")
            return BeamGeo(el.id, el.level.id, el.section, a, b)

        d.attempt(el.id, sg.beams, beam)
    for el in d.model.of_kind("load"):
        assert isinstance(el, Load)

        def load(el: Load = el) -> LoadGeo:
            arch.level(el.level.id)
            if el.at is not None:
                return LoadGeo(el.id, el.level.id, el.g, el.q, [pt(el.at)])
            assert el.a is not None and el.b is not None
            line = LineString([pt(el.a), pt(el.b)])
            if line.length < 1e-6:
                raise GeoError("a= and b= are the same point", "give the line a length")
            n = max(1, round(line.length / SAMPLE))
            pts = [line.interpolate((i + 0.5) / n, normalized=True) for i in range(n)]
            return LoadGeo(el.id, el.level.id, el.g, el.q, [(p.x, p.y) for p in pts], line.length)

        d.attempt(el.id, sg.loads, load)

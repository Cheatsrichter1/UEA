"""The plot derived from the model: its polygon and area, and whether the building stands on it
(decision 0055).

The outline's points are resolved like any plan point (grids, walls, numbers), in the order
given. The building's footprint is the outline of each storey at its outer faces, as for the BGF
(`din277.outline`).
"""

from dataclasses import dataclass, field

from shapely.geometry import Polygon

from uea.core.issues import Issue
from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ar
from uea.geom import clean
from uea.packs.arch.geometry import Resolver
from uea.packs.site.kinds import Plot

OUTSIDE = 0.01
"""m² of a storey beyond the plot that count as outside, above rounding."""


@dataclass
class PlotGeo:
    id: str
    poly: Polygon

    @property
    def area(self) -> float:
        return self.poly.area


@dataclass
class SiteGeo:
    plots: dict[str, PlotGeo] = field(default_factory=dict[str, PlotGeo])
    issues: list[Issue] = field(default_factory=list[Issue])

    @property
    def plot(self) -> PlotGeo | None:
        """The plot, if there is exactly one."""
        return next(iter(self.plots.values())) if len(self.plots) == 1 else None


def derive_site(d: Derived) -> None:
    sg = SiteGeo()
    d.site = sg
    plots = [p for p in d.model.of_kind("plot") if isinstance(p, Plot)]
    if len(plots) > 1:
        sg.issues.append(
            Issue(
                "E-SITE-002",
                plots[1].id,
                f"a project has one plot; {plots[0].id} is one already",
                "give the plot the outline of the whole Baugrundstück and remove the others",
                tuple(p.id for p in plots[:1]),
            )
        )
    arch = Resolver(d, reuse=True)
    store: dict[str, Polygon] = {}
    for el in plots:

        def make(el: Plot = el) -> Polygon:
            pts = [(arch.point(p.x, "x"), arch.point(p.y, "y")) for p in el.outline.items]
            return Polygon(pts)

        poly = d.attempt(el.id, store, make)
        if poly is None:
            continue
        if not poly.is_valid or poly.area < 1e-6:
            sg.issues.append(
                Issue(
                    "E-SITE-001",
                    el.id,
                    "its outline crosses itself or encloses no area",
                    "give the points in order round the plot, each corner once",
                )
            )
            continue
        sg.plots[el.id] = PlotGeo(el.id, poly)


def site_checks(d: Derived) -> list[Issue]:
    out = list(d.site.issues)
    pg = d.site.plot
    if pg is None:
        return out
    from uea.packs.arch.din277 import outline

    parts: list[str] = []
    at = ""
    for lv in d.arch.level_order():
        beyond = clean(outline(d.arch, lv).difference(pg.poly))
        if beyond.area > OUTSIDE:
            parts.append(f"{ar(beyond.area)} m² of {lv}")
            if not at:
                x, y = beyond.representative_point().coords[0]
                at = f"({ar(x)},{ar(y)})"
    if parts:
        out.append(
            Issue(
                "W-SITE-003",
                pg.id,
                f"{', '.join(parts)} lie outside the plot, e.g. at {at}",
                "move the building, or check the plot's outline",
            )
        )
    return out


def describe(d: Derived, el: Element) -> list[str]:
    pg = d.site.plots.get(el.id)
    return [f"area {ar(pg.area)} m²"] if pg is not None else []

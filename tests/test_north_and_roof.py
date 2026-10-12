"""The north arrow on the plans and the elevations' names (`north=`), and the roof over a storey
drawn dashed on its plan."""

import math

import pytest

from tests.conftest import BOX, derive_text
from uea.export.drawing import Circle, Line, Poly, Text
from uea.export.elevation import sheet_elevation
from uea.export.paper import L_NORTH, L_ROOF, compass_de
from uea.export.sheet import roof_outline, sheet_plan

ROOFED = (
    BOX
    + "wall w5 OG AW y=S+ x=W..E lb\n"
    + "wall w6 OG AW x=E- y=w5..w7 lb\n"
    + "wall w7 OG AW y=N- x=W..E lb\n"
    + "wall w8 OG AW x=W+ y=w5..w7 lb\n"
    + "type DA roof layers=ziegel:0.05,*sparren:0.2\n"
    + "roof rf1 OG DA gable ridge=x pitch=30 knee=0.5 eave=0.5 verge=0.3\n"
)


def test_compass() -> None:
    assert [compass_de(a) for a in (0, 22, 23, 90, 180, 225, 270, 315, 359, -90)] == [
        "Nord",
        "Nord",
        "Nordost",
        "Ost",
        "Süd",
        "Südwest",
        "West",
        "Nordwest",
        "Nord",
        "West",
    ]


def test_no_arrow_without_north() -> None:
    d, _ = derive_text(BOX)
    dw = sheet_plan(d, "EG")
    assert dw is not None
    assert [it for it in dw.items if getattr(it, "layer", "") == L_NORTH] == []


def test_the_arrow_points_north() -> None:
    d, _ = derive_text(BOX.replace('project box "Box"', 'project box "Box" north=90'))
    dw = sheet_plan(d, "EG")
    assert dw is not None and dw.sheet is not None
    items = [it for it in dw.items if getattr(it, "layer", "") == L_NORTH]
    circle = next(it for it in items if isinstance(it, Circle))
    tip = next(it for it in items if isinstance(it, Poly)).pts[0]
    # north 90° clockwise from +y is +x on plan: the tip lies east of the middle by the radius
    assert tip[0] - circle.c[0] == pytest.approx(circle.r)
    assert tip[1] == pytest.approx(circle.c[1])
    assert any(isinstance(it, Text) and it.text == "N" for it in items)


def test_elevations_are_named_by_the_compass() -> None:
    d, _ = derive_text(BOX.replace('project box "Box"', 'project box "Box" north=90'))
    # the plan's south side faces 180° - 90° = 90°, east
    dw = sheet_elevation(d, "south")
    assert dw is not None
    assert dw.title.endswith("Ansicht Ost")
    d, _ = derive_text(BOX)
    dw = sheet_elevation(d, "south")
    assert dw is not None and dw.title.endswith("Ansicht Süd")


def test_roof_outline() -> None:
    d, _ = derive_text(ROOFED)
    segs = roof_outline(d.arch, "OG")
    # the outline with 0.3 at the verges and 0.5 at the eaves, and the ridge at y = 4
    pts = {p for s in segs for p in s}
    xs = sorted({round(p[0], 6) for p in pts})
    ys = sorted({round(p[1], 6) for p in pts})
    assert xs == [-0.3, 10.3]
    assert ys == [-0.5, 4.0, 8.5]
    ridge = [s for s in segs if s[0][1] == pytest.approx(4.0) and s[1][1] == pytest.approx(4.0)]
    assert len(ridge) == 1
    assert math.dist(*ridge[0]) == pytest.approx(10.6)
    total = sum(math.dist(*s) for s in segs)
    assert total == pytest.approx(2 * 10.6 + 2 * 9.0 + 10.6)


def test_the_roof_is_drawn_on_its_storey_only() -> None:
    d, _ = derive_text(ROOFED)
    og, eg = sheet_plan(d, "OG"), sheet_plan(d, "EG")
    assert og is not None and eg is not None
    assert len([it for it in og.items if isinstance(it, Line) and it.layer == L_ROOF]) == 7
    assert [it for it in eg.items if getattr(it, "layer", "") == L_ROOF] == []

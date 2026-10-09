"""The elevation: a facade seen from outside, with its openings, the roof, the ground and the
dimensions. Hand-computed values on the 10 x 8 box house of the other sheet tests."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false, reportPrivateImportUsage=false

from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon

from tests.conftest import BOX, derive_text
from tests.test_geometry import ROOF
from tests.test_sheet import HOUSE, area, house, texts
from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Poly, Text
from uea.export.dxf import to_dxf
from uea.export.elevation import sheet_elevation
from uea.export.paper import (
    L_BLOCK,
    L_DIM,
    L_DOOR,
    L_GRID,
    L_ROOF,
    L_TERRAIN,
    L_VIEW,
    L_WIN,
    LAYER_COLORS,
    Stand,
)

STAND = Stand(3, "2026-10-09")


def seen(d: Derived, side: str) -> Drawing:
    dw = sheet_elevation(d, side, STAND)
    assert dw is not None and dw.sheet is not None
    return dw


def frames(dw: Drawing, layer: str) -> list[Poly]:
    """The outlines of windows or doors, big one first (the glass lies inside it)."""
    found = [it for it in dw.items if isinstance(it, Poly) and it.layer == layer and it.pen]
    return sorted(found, key=area, reverse=True)


def box_of(p: Poly) -> tuple[float, float, float, float]:
    xs, zs = [q[0] for q in p.pts], [q[1] for q in p.pts]
    return (min(xs), min(zs), max(xs), max(zs))


def test_the_door_is_on_the_south_facade_and_the_window_on_the_north() -> None:
    d = house()
    # the door d1 is in w1, x 2..3, on the FFL, 2.01 high
    (door, *_) = frames(seen(d, "south"), L_DOOR)
    assert box_of(door) == pytest.approx((2.0, 0.0, 3.0, 2.01))
    assert frames(seen(d, "south"), L_WIN) == []
    # the window f1 is in w3, x 3..4.2; seen from the north, x runs to the left: u = -x. Its
    # sill is the head 2.26 less its height 1.2
    (win, *_) = frames(seen(d, "north"), L_WIN)
    assert box_of(win) == pytest.approx((-4.2, 1.06, -3.0, 2.26))
    assert frames(seen(d, "north"), L_DOOR) == []


def test_the_interior_is_not_seen_through_a_window() -> None:
    # a wall inside, with a door, behind the south wall's door
    d = house("wall w5 EG IW y=w1+3 x=w4..w2 lb\ndoor d2 w5 1x2.01 x=W+2\n")
    dw = seen(d, "south")
    doors = frames(dw, L_DOOR)
    assert len(doors) == 2  # the outline and the frame inside it of d1 alone
    assert box_of(doors[0]) == pytest.approx((2.0, 0.0, 3.0, 2.01))


def test_a_corner_has_no_line_in_the_facade() -> None:
    dw = seen(house(), "east")
    # the east wall w2 and the ends of w1 and w3 are one plane; u = y runs 0..8
    verticals = [
        it
        for it in dw.items
        if isinstance(it, Line)
        and it.layer == L_VIEW
        and it.a[0] == pytest.approx(it.b[0])
        and 0.0 < it.a[0] < 8.0
    ]
    assert verticals == []


def test_the_ground_hides_the_foot_and_runs_across() -> None:
    ground = HOUSE.replace('project box "Box"', 'project box "Box" ground=-0.3')
    dw = seen(house("", ground), "south")
    lines = [it for it in dw.items if isinstance(it, Line) and it.layer == L_VIEW]
    assert min(min(ln.a[1], ln.b[1]) for ln in lines) == pytest.approx(-0.3, abs=1e-3)
    terrain = [
        it
        for it in dw.items
        if isinstance(it, Line) and it.layer == L_TERRAIN and it.a[1] == it.b[1]
    ]
    (line,) = terrain
    assert (line.a[0], line.b[0]) == pytest.approx((-0.8, 10.8))  # 8 mm beyond the walls
    marks = texts(dw, L_DIM)
    assert "Gelände -0,30" in marks and "EG ±0,00" in marks


def test_dimensions_by_hand() -> None:
    dims = texts(seen(house(), "south"), L_DIM)
    # along the bottom: the door 2 + 1 and the pier 7, and the width 10;
    # on the right: the door 2.01 and the whole 2.75 (the edge of the slab above reaches 2.75)
    for t in ("2,00", "1,00", "7,00", "10,00", "2,01", "2,75"):
        assert t in dims


def test_the_gable_end_shows_the_thickness_of_the_roof() -> None:
    d, _ = derive_text(ROOF)
    dw = seen(d, "east")
    rf = d.arch.roofs["rf1"]
    skin = 0.2 * 2**0.5
    roof = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_ROOF and it.fill]
    # two slopes of 4 m along the plane, each a band of 0.2 * sqrt(2) vertically
    assert sum(area(r) for r in roof) == pytest.approx(2 * 4 * skin, abs=1e-3)
    assert max(box_of(r)[3] for r in roof) == pytest.approx(rf.ridge_z, abs=1e-3)
    marks = texts(dw, L_DIM)
    assert "First +4,783" in marks and "Traufe +0,783" in marks


def test_the_eaves_side_shows_the_slope() -> None:
    d, _ = derive_text(ROOF)
    dw = seen(d, "south")
    skin = 0.2 * 2**0.5
    roof = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_ROOF and it.fill]
    # the south slope seen square: 10 m wide, from the eaves to the ridge, 4 m of rise; and the
    # strip of its edge at the eaves. The north slope behind it is hidden.
    assert sum(area(r) for r in roof) == pytest.approx(10 * (4 + skin))


def test_the_sheet() -> None:
    d = house()
    dw = seen(d, "south")
    block = texts(dw, L_BLOCK)
    assert "Ansicht Süd" in block and "A-05" in block  # after two plans, the sections: none
    assert "ENTWURF – nicht unterzeichnet" in block
    assert "Ansicht Süd   M 1:100" in texts(dw)
    assert [
        texts(seen(d, s), L_BLOCK).count("Ansicht " + de)
        for s, de in (("north", "Nord"), ("east", "Ost"), ("west", "West"))
    ] == [1, 1, 1]
    grids = sorted(t.text for t in dw.items if isinstance(t, Text) and t.layer == L_GRID)
    assert grids == ["E", "W"]  # the grids that cross the facade


def test_no_walls_no_elevation() -> None:
    d, _ = derive_text("\n".join(x for x in BOX.splitlines() if not x.startswith("wall")))
    assert sheet_elevation(d, "south") is None


def test_dxf(tmp_path: Path) -> None:
    d, _ = derive_text(ROOF)
    dw = seen(d, "south")
    path = tmp_path / "e.dxf"
    to_dxf(dw, path, LAYER_COLORS)
    doc = ezdxf.readfile(path)
    assert doc.audit().errors == []
    assert {"A-DACH", "A-ANSICHT", "A-BEMASSUNG"} <= {ly.dxf.name for ly in doc.layers}


def test_polygons_are_valid_shapes() -> None:
    d, _ = derive_text(ROOF)
    for side in ("north", "east", "south", "west"):
        for it in seen(d, side).items:
            if isinstance(it, Poly) and len(it.pts) >= 3:
                assert Polygon(it.pts, it.holes).is_valid

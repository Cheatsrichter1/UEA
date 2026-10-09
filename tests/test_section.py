"""The section: the `section` kind, the cut through walls, slabs, roof and stairs, what is behind
the cut, dimensions and marks, the cut lines in the plans, DXF and PDF. Hand-computed values on
a 10 x 8 box house (walls 0.3 core, storeys at 0 and 2.9, slabs 0.2 + 0.01 plaster below)."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false, reportPrivateImportUsage=false

import re
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon

from tests.conftest import BOX, codes, derive_text, model_from
from tests.test_geometry import ROOF, SLABS
from tests.test_sheet import HOUSE, area, house, texts
from uea.core.syntax import LineError
from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Poly, Text
from uea.export.dxf import to_dxf
from uea.export.paper import (
    L_BLOCK,
    L_CUT,
    L_DEMOLISH,
    L_DIM,
    L_GRID,
    L_LB,
    L_NLB,
    L_ROOF,
    L_SLAB,
    L_STAIR,
    L_TERRAIN,
    L_WIN,
    LAYER_COLORS,
    Stand,
)
from uea.export.pdf import to_pdf
from uea.export.section import sheet_section
from uea.export.sheet import sheet_plan
from uea.packs.arch.kinds import Section

STAND = Stand(3, "2026-10-09")


def cut(d: Derived, key: str = "A") -> Drawing:
    dw = sheet_section(d, key, STAND)
    assert dw is not None and dw.sheet is not None
    return dw


def of_layer(dw: Drawing, layer: str) -> list[Poly]:
    return [it for it in dw.items if isinstance(it, Poly) and it.layer == layer]


def top(it: Poly) -> float:
    return max(p[1] for p in it.pts)


# ---------- the kind ----------


def test_the_line_of_a_section() -> None:
    el = model_from(BOX + "section A x=W+2.5 look=w\nsection B y=N-1\n")["A"]
    assert isinstance(el, Section)
    assert el.line() == "section A x=W+2.5 look=w"
    assert model_from(BOX + "section B y=N-1\n")["B"].line() == "section B y=N-1"


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("section A", "exactly one of x= or y="),
        ("section A x=2 y=3", "exactly one of x= or y="),
        ("section A x=W..E", "one position, not a span"),
        ("section A x=2 look=n", "looks e or w"),
        ("section A y=2 look=e", "looks n or s"),
        ("section A x=2 look=up", "look"),
    ],
)
def test_a_section_needs_one_position_and_a_fitting_direction(line: str, message: str) -> None:
    with pytest.raises(LineError, match=message):
        model_from(BOX + line + "\n")


def test_the_cut_is_placed_on_the_plan() -> None:
    d, rep = derive_text(BOX + SLABS + "section A x=W+2.5\nsection B y=N-1 look=s\n")
    a, b = d.arch.sections["A"], d.arch.sections["B"]
    assert (a.axis, a.coord, a.look) == ("x", 2.5, "e")  # looks east unless told
    assert (b.axis, b.coord, b.look) == ("y", 7.0, "s")
    assert [c for c in codes(rep) if c[1] in "AB"] == []


@pytest.mark.parametrize(
    ("look", "right", "u_of_x2_y3", "depth_of_x4_y1"),
    [
        # a cut across x at x = 3, or across y at y = 3: the drawing's right-hand side, the
        # position of (2, 3) across the drawing, the distance of (4, 1) behind the plane
        ("e", (0.0, -1.0), -3.0, 1.0),
        ("w", (0.0, 1.0), 3.0, -1.0),
    ],
)
def test_looking_east_or_west(
    look: str, right: tuple[float, float], u_of_x2_y3: float, depth_of_x4_y1: float
) -> None:
    d, _ = derive_text(BOX + f"section A x=3 look={look}\n")
    sc = d.arch.sections["A"]
    assert sc.right == right
    assert sc.u(2.0, 3.0) == u_of_x2_y3
    assert sc.depth(4.0, 1.0) == depth_of_x4_y1


@pytest.mark.parametrize(
    ("look", "right", "u_of_x2_y3", "depth_of_x1_y5"),
    [("n", (1.0, 0.0), 2.0, 2.0), ("s", (-1.0, 0.0), -2.0, -2.0)],
)
def test_looking_north_or_south(
    look: str, right: tuple[float, float], u_of_x2_y3: float, depth_of_x1_y5: float
) -> None:
    d, _ = derive_text(BOX + f"section A y=3 look={look}\n")
    sc = d.arch.sections["A"]
    assert sc.right == right
    assert sc.u(2.0, 3.0) == u_of_x2_y3
    assert sc.depth(1.0, 5.0) == depth_of_x1_y5


def test_a_cut_outside_the_building_says_so() -> None:
    d, rep = derive_text(HOUSE + "section Z x=50\n")
    assert ("W-ARCH-060", "Z") in codes(rep)
    assert sheet_section(d, "Z") is None


# ---------- the cut ----------

# a cut across x at 2.5, looking east: the door d1 in w1 (south wall) is x 2..3. Drawn to the
# right is -y: w1 core y 0..0.3 is u -0.3..0, w3 core y 7.7..8 is u -8..-7.7.
CUT = "section A x=W+2.5\n"


def test_the_cut_walls_have_their_openings() -> None:
    dw = cut(house(CUT))
    walls = of_layer(dw, L_LB)
    # EG walls stand on the SSL -0.15 and reach the underside of the slab above, 2.55: 2.7 high.
    # w3: 0.3 x 2.7. w1: the same, less the door 0.3 x 2.01 (it stands on the FFL, 0)
    assert sum(area(w) for w in walls) == pytest.approx(0.81 + 0.81 - 0.3 * 2.01)
    x0 = min(p[0] for w in walls for p in w.pts)
    x1 = max(p[0] for w in walls for p in w.pts)
    assert (x0, x1) == pytest.approx((-8.0, 0.0))
    assert min(p[1] for w in walls for p in w.pts) == pytest.approx(-0.15)
    assert max(p[1] for w in walls for p in w.pts) == pytest.approx(2.55)


def test_the_slabs_are_cut_with_their_layers() -> None:
    dw = cut(house(CUT))
    cores = sorted(of_layer(dw, L_SLAB), key=top)
    # the core of each slab is 0.2 thick under its SSL (-0.15 and 2.75) across the 8 m depth
    assert [round(top(c), 3) for c in cores] == [-0.15, 2.75]
    assert [area(c) for c in cores] == pytest.approx([1.6, 1.6])


def test_the_door_stands_in_the_cut_as_a_gap() -> None:
    dw = cut(house(CUT))
    # no window in the cut; the door leaves no line behind it
    assert [it for it in dw.items if isinstance(it, Line) and it.layer == L_WIN] == []
    south = [w for w in of_layer(dw, L_LB) if max(p[0] for p in w.pts) == pytest.approx(0.0)]
    assert sum(area(w) for w in south) == pytest.approx(0.3 * 2.7 - 0.3 * 2.01)


def test_a_window_in_the_cut_is_drawn_as_glass() -> None:
    # a window f2 in w3, x 5..6.2, is cut at x = 5.5; its sill is head 2.26 - 1.2 = 1.06
    d = house("win f2 w3 1.2x1.2 x=W+5\nsection A x=W+5.5\n")
    dw = cut(d)
    glass = [it for it in dw.items if isinstance(it, Line) and it.layer == L_WIN]
    verticals = [ln for ln in glass if ln.a[0] == ln.b[0]]
    assert len(verticals) == 1
    (v,) = verticals
    assert (v.a[0], v.a[1], v.b[1]) == pytest.approx((-7.855, 1.06, 2.26))


def test_the_clear_height_is_written_in_the_room() -> None:
    dw = cut(house(CUT))
    # the room's ceiling is the slab's plaster: 2.75 - 0.2 - 0.01 = 2.54
    assert "Wohnen" in texts(dw)
    assert "lichte Höhe 2,54 m" in texts(dw)


def test_dimensions_by_hand() -> None:
    dims = texts(dw := cut(house(CUT)), L_DIM)
    # wall faces: 0.3 + 7.4 + 0.3 = 8; heights: door 2.01 and the rest of the storey 0.89
    for t in ("0,30", "7,40", "8,00", "2,01", "0,89", "2,90"):
        assert t in dims
    assert dims.count("0,30") == 2
    assert "Schnitt A-A   M 1:100" in texts(dw)


def test_the_sheet() -> None:
    dw = cut(house(CUT))
    block = texts(dw, L_BLOCK)
    assert "Schnitt A-A" in block
    assert "ENTWURF – nicht unterzeichnet" in block
    assert "A-03" in block  # after the plans of the two storeys
    assert "Höhen in m, ±0,00 = OKFF Erdgeschoss" in block
    assert "Stand 09.10.2026 · Batch 3 · UEA " in " ".join(block)
    assert dw.sheet is not None and (dw.sheet.size, dw.sheet.scale) == ("A3", 100)


def test_height_marks_and_the_ground() -> None:
    d = house(CUT)
    assert not [t for t in texts(cut(d)) if t.startswith("Gelände")]
    ground = HOUSE.replace('project box "Box"', 'project box "Box" ground=-0.3')
    dw = cut(house(CUT, ground))
    marks = texts(dw, L_DIM)
    assert "EG ±0,00" in marks and "OG +2,90" in marks and "Gelände -0,30" in marks
    # the ground line runs outside the walls only, 8 mm of paper beyond their plaster
    line = [it for it in dw.items if isinstance(it, Line) and it.layer == L_TERRAIN]
    long = [ln for ln in line if ln.a[1] == ln.b[1] and ln.a[0] != ln.b[0]]
    assert len(long) == 2 and all(ln.a[1] == pytest.approx(-0.3) for ln in long)
    assert min(ln.a[0] for ln in long) == pytest.approx(-8.02 - 0.8)
    assert max(ln.b[0] for ln in long) == pytest.approx(0.02 + 0.8)


# ---------- roof, stairs, behind the cut ----------


def test_a_gable_roof_in_the_cut() -> None:
    d, _ = derive_text(ROOF + "section A x=W+5\n")
    dw = cut(d)
    rf = d.arch.roofs["rf1"]
    band = of_layer(dw, L_ROOF)
    # the cut across the ridge: its top is the ridge, 0.5 + 4 + 0.2 * sqrt(2) = 4.783
    assert max(top(b) for b in band) == pytest.approx(4.5 + 0.2 * 2**0.5)
    assert rf.ridge_z == pytest.approx(4.5 + 0.2 * 2**0.5)
    marks = texts(dw, L_DIM)
    assert "First +4,783" in marks and "Traufe +0,783" in marks
    # a wall under the roof follows the rafter: w1's core stands to the underside at its middle
    south = [w for w in of_layer(dw, L_NLB) if max(p[0] for p in w.pts) == pytest.approx(0.0)]
    assert sum(area(w) for w in south) == pytest.approx(0.3 * (0.5 + 0.15))


STAIR = (
    "stair st1 EG OG x=w2-1 y=w3- up=w w=1 n=12 tread=0.2\n"
    "void v1 sl2 over=st1\n"
    "section T y=w3-0.5 look=n\n"
)


def test_a_stair_in_the_cut() -> None:
    d, rep = derive_text(HOUSE + STAIR)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    dw = cut(d, "T")
    (steps,) = of_layer(dw, L_STAIR)
    # the stair climbs west from x = 8.7, one past w2's face, over 11 treads of 0.2, each
    # 2.9 / 12 higher
    xs = [p[0] for p in steps.pts]
    assert (min(xs), max(xs)) == pytest.approx((6.5, 8.7))
    assert top(steps) == pytest.approx(11 * 2.9 / 12)
    # the slab of the upper storey has the void: it is cut in two pieces
    upper = [c for c in of_layer(dw, L_SLAB) if top(c) == pytest.approx(2.75)]
    assert sorted((min(p[0] for p in c.pts), max(p[0] for p in c.pts)) for c in upper) == [
        pytest.approx((0.0, 6.5)),
        pytest.approx((8.7, 10.0)),
    ]


def test_a_window_behind_the_cut_is_seen_through_its_wall() -> None:
    # w2 is the east wall, 7.5 m behind a cut at x = 2.5 looking east; y 4..5 is u -5..-4
    d = house("win f2 w2 1x1 y=S+4\n" + CUT)
    dw = cut(d)
    frames = [it for it in of_layer(dw, L_WIN) if it.pen is not None]
    outer = max(frames, key=area)
    assert area(outer) == pytest.approx(1.0)
    assert (min(p[0] for p in outer.pts), max(p[0] for p in outer.pts)) == pytest.approx(
        (-5.0, -4.0)
    )
    assert (min(p[1] for p in outer.pts), max(p[1] for p in outer.pts)) == pytest.approx(
        (1.26, 2.26)
    )
    # a window behind a nearer wall stays hidden: looking west instead, w4 is the far wall and
    # has no window
    west = cut(house("win f2 w2 1x1 y=S+4\nsection A x=W+2.5 look=w\n"))
    assert [it for it in of_layer(west, L_WIN) if it.pen is not None] == []


def test_status_colours_in_an_umbau() -> None:
    d, _ = derive_text(
        HOUSE.replace("wall w3 EG AW y=N- x=W..E lb", "wall w3 EG AW y=N- x=W..E lb demolish") + CUT
    )
    dw = cut(d)
    assert [round(area(p), 3) for p in of_layer(dw, L_DEMOLISH)] == [0.81]
    assert {p.fill for p in of_layer(dw, L_LB)} == {"#b02020"}  # new walls are red in an Umbau


# ---------- grids, plans, files ----------


def test_grids_across_the_cut_have_bubbles() -> None:
    dw = cut(house(CUT))
    # the cut runs across x: it meets the grids along x, S and N, at u = 0 and -8
    bubbles = [it for it in dw.items if isinstance(it, Text) and it.layer == L_GRID]
    assert sorted((t.text, round(t.at[0], 3)) for t in bubbles) == [("N", -8.0), ("S", 0.0)]


def test_the_plan_shows_the_cut_line() -> None:
    d = house(CUT + "section B y=S+3 look=s\n")
    dw = sheet_plan(d, "EG", STAND)
    assert dw is not None
    letters = [it for it in dw.items if isinstance(it, Text) and it.layer == L_CUT]
    assert sorted(t.text for t in letters) == ["A", "A", "B", "B"]
    lines = [it for it in dw.items if isinstance(it, Line) and it.layer == L_CUT]
    # the line across the building: A runs along y from -0.025 m... on paper 2.5 mm beyond the walls
    long = [ln for ln in lines if ln.a[0] == ln.b[0] == pytest.approx(2.5)]
    assert any(abs(ln.b[1] - ln.a[1]) == pytest.approx(8.0 + 2 * 0.25, abs=0.01) for ln in long)
    # the arrows point the way the section looks: A east, B south
    heads = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_CUT]
    assert len(heads) == 4


def test_a_cut_that_misses_the_storey_is_not_drawn_in_its_plan() -> None:
    d = house("section A x=W+50\n")
    dw = sheet_plan(d, "EG", STAND)
    assert dw is not None
    assert [it for it in dw.items if getattr(it, "layer", "") == L_CUT] == []


def test_dxf_and_pdf(tmp_path: Path) -> None:
    dw = cut(house(CUT))
    path = tmp_path / "s.dxf"
    to_dxf(dw, path, LAYER_COLORS)
    doc = ezdxf.readfile(path)
    assert doc.audit().errors == []
    names = {layer.dxf.name for layer in doc.layers}
    assert {"A-WAND-TRAG", "A-DECKE", "A-BEMASSUNG", "A-RASTER", "A-RAUM-TEXT"} <= names
    box = ezdxf.bbox.extents(doc.modelspace())
    assert box.size.x == pytest.approx(39000.0, abs=1.0)  # A3 at 1:100
    to_pdf(dw, tmp_path / "s.pdf")
    data = (tmp_path / "s.pdf").read_bytes()
    match = re.search(rb"/MediaBox \[ ?0 0 ([\d.]+) ([\d.]+) ?\]", data)
    assert match is not None and float(match[1]) == pytest.approx(420 / 25.4 * 72, abs=0.1)


def test_polygons_are_valid_shapes() -> None:
    dw = cut(house(CUT + STAIR))
    for it in dw.items:
        if isinstance(it, Poly) and len(it.pts) >= 3:
            assert Polygon(it.pts, it.holes).is_valid

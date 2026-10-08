"""The floor plan sheet: dimension chains, cut walls, fitting on paper, DXF and PDF."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false, reportPrivateImportUsage=false

import re
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon

from tests.conftest import BOX, derive_text
from tests.test_geometry import SLABS
from uea.derive import Derived
from uea.export.drawing import Drawing, Poly, Sheet, Text, to_png, to_svg
from uea.export.dxf import to_dxf
from uea.export.pdf import to_pdf
from uea.export.sheet import (
    BLOCK_H,
    BLOCK_W,
    L_BLOCK,
    L_DEMOLISH,
    L_DIM,
    L_FRAME,
    L_LB,
    LAYER_COLORS,
    Stand,
    dim_text,
    frame,
    height_text,
    place,
    sheet_plan,
    side_chains,
)

# a 10 x 8 box: walls with a 0.3 core, so the ends of w2 and w4 are 0.3 and 7.7
HOUSE = (
    BOX
    + SLABS
    + "door d1 w1 1x2.01 x=W+2 into=r1 hand=l\n"
    + "win f1 w3 1.2x1.2 x=W+3\n"
    + "niche ni1 w2.w 1x2.1 y=w1+2 d=0.1\n"
    + "room r1 EG living at=W+1,S+1 floor=FB\n"
)


def house(extra: str = "", text: str = HOUSE) -> Derived:
    d, rep = derive_text(text + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d


def drawn(d: Derived, level: str = "EG") -> Drawing:
    dw = sheet_plan(d, level, Stand(3, "2026-10-08"))
    assert dw is not None and dw.sheet is not None
    return dw


def texts(dw: Drawing, layer: str | None = None) -> list[str]:
    return [it.text for it in dw.items if isinstance(it, Text) and layer in (None, it.layer)]


def area(it: Poly) -> float:
    return Polygon(it.pts, it.holes).area


def test_numbers_the_german_way() -> None:
    assert [dim_text(v) for v in (10.49, 1.135, 0.365, 2.26, 2.0, 0.24)] == [
        "10,49",
        "1,135",
        "0,365",
        "2,26",
        "2,00",
        "0,24",
    ]
    assert [height_text(v) for v in (0.0, 2.875, -0.15)] == ["±0,00", "+2,875", "-0,15"]


def test_sheet_maps_paper_to_plan() -> None:
    sh = Sheet("A3", (420.0, 297.0), 100, (-5.0, 3.0))
    assert sh.pt(10, 20) == pytest.approx((-4.0, 5.0))  # 10 mm at 1:100 is 1 m
    assert sh.m(0.35) == pytest.approx(0.035)
    assert sh.mm(0.35) == pytest.approx(3.5)
    assert sh.bounds() == pytest.approx((-5.0, 3.0, 37.0, 32.7))


def test_chains_of_the_box() -> None:
    d = house()
    walls = d.arch.walls_on("EG")
    bbox = (0.0, 0.0, 10.0, 8.0)
    south = side_chains(d, walls, "S", bbox)
    # openings and piers: the door 2..3 in the south wall; the wall faces between the ends; total
    assert [(c.kind, c.pts) for c in south] == [
        ("open", [0.0, 2.0, 3.0, 10.0]),
        ("walls", [0.0, 0.3, 9.7, 10.0]),
        ("total", [0.0, 10.0]),
    ]
    north = side_chains(d, walls, "N", bbox)
    assert north[0].pts == pytest.approx([0.0, 3.0, 4.2, 10.0])  # the window 3..4.2
    west = side_chains(d, walls, "W", bbox)
    # no openings in the west wall: wall faces (w1 and w3 reach it), then the total
    assert [(c.kind, c.pts) for c in west] == [
        ("walls", [0.0, 0.3, 7.7, 8.0]),
        ("total", [0.0, 8.0]),
    ]


def test_dimension_texts() -> None:
    dw = drawn(house())
    dims = texts(dw, L_DIM)
    # south chains 2+1+7, 0.3+9.4+0.3, 10; north 3+1.2+5.8; west 0.3+7.4+0.3 and 8; east alike
    for t in ("2,00", "1,00", "7,00", "9,40", "10,00", "1,20", "5,80", "7,40", "8,00"):
        assert t in dims
    assert dims.count("0,30") >= 6


def test_cut_walls_have_real_openings() -> None:
    dw = drawn(house())
    fills = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_LB]
    # cores 3 + 3 + 2.22 + 2.22, less the door 1 x 0.3, the window 1.2 x 0.3 and the niche 1 x 0.1
    assert sum(area(p) for p in fills) == pytest.approx(10.44 - 0.3 - 0.36 - 0.1)


def test_room_stamp_and_caption() -> None:
    dw = drawn(house())
    assert "Wohnen" in texts(dw)
    assert f"{9.38 * 7.38:.2f}".replace(".", ",") + " m²" in texts(dw)
    assert "Grundriss Erdgeschoss   M 1:100" in texts(dw)


def test_title_block_stays_unsigned() -> None:
    dw = drawn(house())
    block = texts(dw, L_BLOCK)
    assert "ENTWURF – nicht unterzeichnet" in block
    for label in ("Bauherr", "Planverfasser", "Unterschrift"):
        assert label in block
    assert "Stand 08.10.2026 · Batch 3 · UEA " in " ".join(block)
    assert "A3" in block and "1:100" in block and "A-01" in block
    assert "OKFF ±0,00 m" in block


def test_everything_fits_on_the_sheet_clear_of_the_title_block() -> None:
    for text in (HOUSE, HOUSE.replace("x=10", "x=40").replace("y=8", "y=30")):
        dw = drawn(house(text=text))
        sh = dw.sheet
        assert sh is not None
        fx0, fy0, fx1, fy1 = frame(sh.paper)
        tb = (fx1 - BLOCK_W, fy0, fx1, fy0 + BLOCK_H)
        content = Drawing("")
        content.items = [
            it for it in dw.items if getattr(it, "layer", "") not in (L_FRAME, L_BLOCK)
        ]
        x0, y0, x1, y1 = (
            sh.mm(v - o) for v, o in zip(content.bounds(), sh.origin * 2, strict=True)
        )
        assert fx0 <= x0 and x1 <= fx1 and fy0 <= y0 and y1 <= fy1
        assert x1 <= tb[0] or y0 >= tb[3]
    assert dw.sheet is not None
    assert (dw.sheet.size, dw.sheet.scale) != ("A3", 100)  # the large house needs more


def test_place_prefers_the_middle_then_above_then_left_of_the_title_block() -> None:
    # frame 20..410 x 10..287, title block 225..410 x 10..65
    paper = (420.0, 297.0)
    assert place(paper, 200.0, 150.0) == pytest.approx((115.0, 73.5))  # the middle
    assert place(paper, 380.0, 100.0) == pytest.approx((25.0, 98.5))  # the middle, wide
    # too low in the middle, so above the block: y 70..287 holds 210 mm with 3.5 to spare
    assert place(paper, 380.0, 210.0) == pytest.approx((25.0, 73.5))
    # too tall for that, so left of the block: x 20..220 holds 190 mm with 5 to spare
    assert place(paper, 190.0, 270.0) == pytest.approx((25.0, 13.5))
    assert place(paper, 380.0, 250.0) is None


def test_status_colours_in_an_umbau() -> None:
    dw = drawn(house("wall w5 EG IW x=w4+4 y=w1..w3 demolish\n"))
    demolished = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_DEMOLISH]
    assert [it.fill for it in demolished] == ["#ffd800"]
    new = [it for it in dw.items if isinstance(it, Poly) and it.layer == L_LB]
    assert {it.fill for it in new} == {"#b02020"}


def test_no_walls_no_sheet() -> None:
    d, _ = derive_text(BOX)
    assert sheet_plan(d, "OG") is None


def test_dxf(tmp_path: Path) -> None:
    dw = drawn(house())
    path = tmp_path / "p.dxf"
    counts = to_dxf(dw, path, LAYER_COLORS)
    assert counts["Text"] == len(texts(dw))
    doc = ezdxf.readfile(path)
    assert doc.audit().errors == []
    assert doc.units == 4  # millimetres
    names = {layer.dxf.name for layer in doc.layers}
    assert {"A-WAND-TRAG", "A-BEMASSUNG", "A-TUER", "A-FENSTER", "A-RAHMEN"} <= names
    msp = doc.modelspace()
    assert len(msp.query("HATCH")) >= 1
    # text in mm: the caption sits below the middle of the box, 10 m wide
    caption = next(t for t in msp.query("TEXT") if t.dxf.text.startswith("Grundriss"))
    assert caption.dxf.insert.x == pytest.approx(5000.0)
    assert caption.dxf.height == pytest.approx(350.0)  # 3.5 mm at 1:100
    # the frame is 0.7 mm wide on paper, whatever the scale
    frame_lines = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "A-RAHMEN"]
    assert frame_lines and frame_lines[0].dxf.lineweight == 70
    # the header knows how big the drawing is, so viewers do not collapse it
    assert doc.header["$EXTMAX"][0] < 1e10
    # the sheet is 420 x 297 mm at 1:100: its frame spans 390 x 277 mm, 39 x 27.7 m
    box = ezdxf.bbox.extents(msp)
    assert box.size.x == pytest.approx(39000.0, abs=1.0)
    assert box.size.y == pytest.approx(27700.0, abs=1.0)


def test_pdf(tmp_path: Path) -> None:
    dw = drawn(house())
    path = tmp_path / "p.pdf"
    to_pdf(dw, path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    box = re.search(rb"/MediaBox \[ ?0 0 ([\d.]+) ([\d.]+) ?\]", data)
    assert box is not None
    # A3 landscape: 420 x 297 mm in points
    assert float(box[1]) == pytest.approx(420 / 25.4 * 72, abs=0.1)
    assert float(box[2]) == pytest.approx(297 / 25.4 * 72, abs=0.1)
    with pytest.raises(ValueError, match="sheet"):
        to_pdf(Drawing("no sheet"), tmp_path / "x.pdf")


def test_svg_and_png(tmp_path: Path) -> None:
    dw = drawn(house())
    svg = to_svg(dw)
    width = re.match(r'<svg [^>]*width="(\d+)"', svg)
    assert width is not None and int(width[1]) == round(420 / 25.4 * 96)
    assert 'transform="rotate(-90.0' in svg  # the dimensions on the sides are turned
    w, h = to_png(dw, tmp_path / "p.png", max_px=1200)
    assert (w, h) == (1200, round(1200 * 297 / 420))

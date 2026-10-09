"""The electrical sheets: the installation plan of a storey and the board diagram, with the
derived phases and the occupation of the field. Hand-computed values on the 10 x 8 box house of
`test_elec.py`."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false, reportPrivateImportUsage=false

from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon

from tests.conftest import derive_text
from tests.test_elec import BOARD, HOUSE, elec
from tests.test_sheet import texts
from uea.derive import Derived
from uea.export import install as ins
from uea.export.board import ROW_TE, Group, field_rows, sheet_board
from uea.export.drawing import Arc, Drawing, Line, Poly, Text
from uea.export.dxf import to_dxf
from uea.export.install import ELEC_LAYER_COLORS, PALETTE, sheet_install
from uea.export.paper import L_BLOCK, LAYER_COLORS, Stand
from uea.export.pdf import to_pdf

STAND = Stand(3, "2026-10-09")
SOCKETS = "sock s1 w4 c2 y=w1+0.3 z=1.15 n=2\n"
LIGHT = "lum l1 r1\nswitch sw1 w4 c1 y=w1+2 ctl=l1\n"


def install(extra: str, level: str = "EG") -> Drawing:
    d, _ = elec(extra)
    dw = sheet_install(d, level, STAND)
    assert dw is not None and dw.sheet is not None
    return dw


def arcs(dw: Drawing, layer: str) -> list[Arc]:
    return [it for it in dw.items if isinstance(it, Arc) and it.layer == layer]


# ---------- the installation plan ----------


def test_a_socket_is_a_half_circle_on_the_wall_face() -> None:
    dw = install(SOCKETS)
    assert dw.sheet is not None and (dw.sheet.size, dw.sheet.scale) == ("A3", 50)
    found = sorted(arcs(dw, ins.E_SOCK), key=lambda a: a.c[1])
    # two outlets, 3.4 mm apart on paper = 0.17 m at 1:50, either side of the socket at
    # (0.3, 0.6) on the room side of w4 (which runs along y); radius 1.5 mm = 0.075 m
    assert [a.c for a in found] == [pytest.approx((0.3, 0.515)), pytest.approx((0.3, 0.685))]
    assert all(a.r == pytest.approx(0.075) for a in found)
    # the half circle bulges into the room, to the east: from -90 to +90 degrees
    assert all((a.a0, a.a1) == (pytest.approx(-90.0), pytest.approx(90.0)) for a in found)


def test_symbols_take_the_colour_of_their_circuit() -> None:
    dw = install(SOCKETS + LIGHT)
    # c1 is the first circuit and c2 the second
    assert {a.pen.color for a in arcs(dw, ins.E_SOCK)} == {PALETTE[1]}
    switch = [it for it in dw.items if getattr(it, "layer", "") == ins.E_SWITCH]
    assert {it.pen.color for it in switch if isinstance(it, Line | Arc)} <= {PALETTE[0]}
    assert "c2" in texts(dw, ins.E_LABEL) and "c1" in texts(dw, ins.E_LABEL)


def test_a_dashed_line_joins_a_switch_to_its_luminaire() -> None:
    d, _ = elec(LIGHT)
    dw = sheet_install(d, "EG", STAND)
    assert dw is not None
    lines = [it for it in dw.items if isinstance(it, Line) and it.layer == ins.E_LINE]
    (line,) = lines
    lum = d.mounts["l1"].point
    assert line.b == pytest.approx(lum)  # ends at the luminaire, in the middle of the room
    assert line.pen.dash  # and is dashed
    assert line.pen.color == PALETTE[0]


def test_the_floor_plan_is_the_grey_background() -> None:
    dw = install(SOCKETS)
    fills = {it.fill for it in dw.items if isinstance(it, Poly) and it.fill}
    walls = [it for it in dw.items if isinstance(it, Poly) and it.layer == ins.E_WALL]
    assert walls and {w.fill for w in walls if w.fill} == {ins.WALL_FILL}
    assert fills >= {ins.WALL_FILL}
    # no dimension chain, no section line: only the plan and the devices
    layers = {getattr(it, "layer", "") for it in dw.items}
    assert "A-BEMASSUNG" not in layers and "A-WAND-TRAG" not in layers


def test_the_legend_and_the_title_block() -> None:
    dw = install(SOCKETS + LIGHT + "smoke rm1 r1\n")
    t = texts(dw, ins.E_LEGEND)
    assert "Legende" in t
    assert "Steckdose (ein Halbkreis je Auslass)" in t
    assert "Schaltverbindung Schalter → Leuchte" in t
    assert "Rauchwarnmelder" in t
    # the circuits on this sheet, as the model gives them
    assert "c1 B10 NYM-J3x1.5 Licht" in t and "c2 B16 NYM-J3x2.5 Steckdosen" in t
    block = texts(dw, L_BLOCK)
    assert "Elektroinstallation Erdgeschoss" in block and "E-01" in block and "1:50" in block
    assert "ENTWURF – nicht unterzeichnet" in block
    assert "Symbole vereinfacht, in Anlehnung an DIN EN 60617" in block
    assert "Elektroinstallation Erdgeschoss   M 1:50" in texts(dw)


def test_a_two_way_switch_has_a_stroke_on_each_side() -> None:
    one = install(LIGHT)
    two = install(LIGHT + "switch sw2 w4 c1 y=w1+3 ctl=l1\n")

    def strokes(dw: Drawing) -> int:
        return len([it for it in dw.items if isinstance(it, Line) and it.layer == ins.E_SWITCH])

    # a single switch is a circle with one stroke; two switches on l1 are both two-way, each with
    # a stroke on both sides
    assert strokes(one) == 1
    assert strokes(two) == 4


def test_a_storey_without_devices_has_no_sheet() -> None:
    d, _ = elec(SOCKETS)
    assert sheet_install(d, "OG", STAND) is None


def test_a_crowd_of_circuits_goes_in_columns() -> None:
    many = "".join(
        f'circ c{i} fi1 NYM-J3x2.5 B16 "K{i}"\nsock s{i} w4 c{i} y=w1+{i * 0.2}\n'
        for i in range(3, 30)
    )
    dw = install(many)
    t = texts(dw, ins.E_LEGEND)
    assert "c29 B16 NYM-J3x2.5 K29" in t


def test_dxf_and_pdf(tmp_path: Path) -> None:
    dw = install(SOCKETS + LIGHT)
    path = tmp_path / "e.dxf"
    to_dxf(dw, path, {**LAYER_COLORS, **ELEC_LAYER_COLORS})
    doc = ezdxf.readfile(path)
    assert doc.audit().errors == []
    names = {layer.dxf.name for layer in doc.layers}
    assert {"E-STECKDOSE", "E-SCHALTER", "E-LEUCHTE", "E-SCHALTLINIE", "E-GRUND-WAND"} <= names
    to_pdf(dw, tmp_path / "e.pdf")
    assert (tmp_path / "e.pdf").read_bytes().startswith(b"%PDF")


# ---------- phases and the field ----------

CIRCUITS = (
    "rcd fi2 b1 40/0.03 A\n"
    'circ c3 fi1 NYM-J5x2.5 B16 p=3 "Herd"\n'
    'circ c4 fi2 NYM-J3x2.5 B16 "Bad"\n'
)


def test_the_phases_are_shared_out() -> None:
    d, _ = elec(CIRCUITS)
    # in the order fi1 (c1, c2, c3), fi2 (c4); each load counts at least 1000 W. c1 takes L1,
    # c2 the least loaded of L2 and L3 (L2), the three-phase c3 a third on each, c4 then L3
    got = {c: d.elec.circuits[c].phase for c in ("c1", "c2", "c3", "c4")}
    assert got == {"c1": "L1", "c2": "L2", "c3": "L1-L3", "c4": "L3"}


def test_a_declared_load_weighs_more() -> None:
    # c1 carries 5000 W: c2 and c3 go to L2 and L3, a third circuit finds L2 and L3 lighter
    d, _ = elec(
        "conn a1 w4 c1 y=w1+3 w=5000\ncirc c3 fi1 NYM-J3x2.5 B16\ncirc c4 fi1 NYM-J3x2.5 B16\n"
    )
    got = {c: d.elec.circuits[c].phase for c in ("c1", "c2", "c3", "c4")}
    assert got == {"c1": "L1", "c2": "L2", "c3": "L3", "c4": "L2"}


def groups_of(d: Derived) -> list[Group]:
    from uea.packs.elec.kinds import Rcd

    out: list[Group] = []
    for r in d.model.of_kind("rcd"):
        assert isinstance(r, Rcd)
        out.append(Group(r, [c for c in d.elec.circuits.values() if c.rcd == r.id]))
    return out


def test_the_field_is_filled_in_rows_of_12_te() -> None:
    d, _ = elec(CIRCUITS)
    rows = field_rows(True, groups_of(d))
    # SPD 4 TE; fi1: RCD 4 + c1 1 + c2 1 + c3 3 = 9; fi2: RCD 4 + c4 1 = 5
    assert [(r.used, [i[1] for i in r.items]) for r in rows] == [
        (4, ["SPD"]),
        (9, ["fi1", "c1", "c2", "c3"]),
        (5, ["fi2", "c4"]),
    ]


def test_a_full_row_goes_on_in_the_next() -> None:
    many = "".join(f"circ c{i} fi1 NYM-J3x2.5 B16\n" for i in range(3, 11))
    d, _ = elec(many)
    rows = field_rows(False, groups_of(d))
    # fi1 has c1..c10, ten breakers: 4 + 8 fill 12 TE, the last two go on in the next row
    assert [(r.used, r.items[0][0], len(r.items)) for r in rows] == [(12, "rcd", 9), (6, "cont", 3)]
    assert all(r.used <= ROW_TE for r in rows)


# ---------- the board diagram ----------


def board(extra: str = "") -> Drawing:
    d, _ = derive_text(
        HOUSE + BOARD.replace("main=SLS-E35", "main=SLS-E35 spd=T1+T2") + CIRCUITS + extra
    )
    dw = sheet_board(d, "b1", STAND)
    assert dw is not None and dw.sheet is not None
    return dw


def test_the_diagram() -> None:
    dw = board(SOCKETS + LIGHT)
    assert dw.sheet is not None and (dw.sheet.size, dw.sheet.scale) == ("A3", 1)
    t = texts(dw, "E-SCHALTPLAN")
    assert "Netz / HAK" in t and "Zähler (1)" in t and "SLS" in t and "E35" in t
    assert "SPD" in t and "T1+T2" in t
    assert "fi1 RCD" in t and "fi2 RCD" in t and "40 A / 0,03 A" in t and "Typ A, 4-polig" in t
    # the circuits in order, with phase and cable
    for cid in ("c1", "c2", "c3", "c4"):
        assert cid in t
    assert "L1–L3" in t and "NYM-J5x2.5" in t and "3-polig" in t
    # what hangs on c2: one socket box with two outlets
    assert "1 Dosen / 2 Steckpl." in t
    block = texts(dw, L_BLOCK)
    assert "Verteilungsplan b1 UV" in block and "o. M." in block and "E-03" in block


def test_the_diagram_names_the_derived_field() -> None:
    dw = board()
    t = texts(dw, "E-SCHALTPLAN")
    assert "Belegung Verteilerfeld b1 (abgeleitet), 12 TE je Reihe" in t
    assert "Reihe 1: 4 TE" in t and "Reihe 2: 9 TE" in t and "Reihe 3: 5 TE" in t


def test_a_media_board_has_no_diagram() -> None:
    d, _ = elec("board b2 w4 y=w1+5 z=1.4 media\n")
    assert sheet_board(d, "b2", STAND) is None
    assert sheet_board(d, "s1", STAND) is None


def test_the_texts_of_the_diagram_stay_inside_the_sheet() -> None:
    dw = board()
    x0, y0, x1, y1 = dw.sheet.bounds()  # type: ignore[union-attr]
    for it in dw.items:
        if isinstance(it, Text):
            assert x0 <= it.at[0] <= x1 and y0 <= it.at[1] <= y1
        if isinstance(it, Poly) and len(it.pts) >= 3:
            assert Polygon(it.pts).is_valid


def test_the_diagram_in_files(tmp_path: Path) -> None:
    dw = board(SOCKETS)
    to_dxf(dw, tmp_path / "b.dxf", {**LAYER_COLORS, **ELEC_LAYER_COLORS})
    doc = ezdxf.readfile(tmp_path / "b.dxf")
    assert doc.audit().errors == []
    to_pdf(dw, tmp_path / "b.pdf")
    assert (tmp_path / "b.pdf").read_bytes().startswith(b"%PDF")

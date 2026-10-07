"""Geometry from intent, against hand-computed values.

The box: grids W=0 E=10 S=0 N=8, exterior walls with 0.01 Gips inside, a 0.30 core and 0.02
Putz outside, placed on the outer grids. So the inside Rohbau runs x 0.3..9.7, y 0.3..7.7
(9.4 x 7.4 = 69.56 m²) and Fertig x 0.31..9.69, y 0.31..7.69 (9.38 x 7.38 = 69.2244 m²).
"""

import pytest

from tests.conftest import BOX, codes, derive_text

SLABS = "slab sl1 EG DE\nslab sl2 OG DE\n"


def test_box_room() -> None:
    d, rep = derive_text(BOX + SLABS + "room r1 EG living at=W+1,S+1\n")
    g = d.arch
    w4 = g.walls["w4"]
    assert (w4.o, w4.lo, w4.hi, w4.s0, w4.s1) == pytest.approx(("v", 0.0, 0.3, 0.3, 7.7))
    w1 = g.walls["w1"]
    assert (w1.o, w1.lo, w1.hi, w1.s0, w1.s1) == pytest.approx(("h", 0.0, 0.3, 0.0, 10.0))
    assert {k: w.ext for k, w in g.walls.items()} == {
        "w1": "lo",
        "w2": "hi",
        "w3": "hi",
        "w4": "lo",
    }
    r = g.rooms["r1"]
    assert r.area == pytest.approx(9.4 * 7.4)
    assert r.area_fin == pytest.approx(9.38 * 7.38)
    # OG: OK Rohdecke 2.9 - 0.15 = 2.75; slab core 0.2 and Gips 0.01 below: ceiling at 2.54
    assert r.height == pytest.approx(2.54)
    assert r.volume == pytest.approx(9.38 * 7.38 * 2.54)
    assert r.bounds == ["w1", "w2", "w3", "w4"]
    # walls stand on OK Rohdecke EG (-0.15) and end under the OG slab core (2.75 - 0.2)
    assert w1.bottom == pytest.approx(-0.15)
    assert w1.top == [(0.0, pytest.approx(2.55)), (10.0, pytest.approx(2.55))]
    assert codes(rep) == []


def test_interior_wall_splits_rooms() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + "wall w5 EG IW x=w4+4 y=w1..w3\n"
        + "room r1 EG living at=W+1,S+1\nroom r2 EG bedroom at=E-1,S+1\n"
    )
    g = d.arch
    assert (g.walls["w5"].lo, g.walls["w5"].hi) == pytest.approx((4.3, 4.415))
    assert g.walls["w5"].ext is None
    # r1: x 0.3..4.3; Fertig minus 0.01 on each side
    assert g.rooms["r1"].area_fin == pytest.approx(3.98 * 7.38)
    # r2: x 4.415..9.7 = 5.285
    assert g.rooms["r2"].area == pytest.approx(5.285 * 7.4)
    assert g.rooms["r2"].area_fin == pytest.approx(5.265 * 7.38)
    assert codes(rep) == []


def test_openings() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + "wall w5 EG IW x=w4+4 y=w1..w3\n"
        + "door d1 w5 0.885x2.01 y=w1+1 into=r2 din=l\n"
        + "win f1 w1 1.26x1.26 x=W+1.51\n"
        + "win f2 w1 1x1 x=f1+0.5\n"
        + "win f3 w3 1x1 x=f1.c\n"
        + "win f4 w3 1x1 x=E-1 sill=0.9\n"
        + "room r1 EG living at=W+1,S+1\nroom r2 EG bedroom at=E-1,S+1\n"
    )
    g = d.arch
    d1 = g.openings["d1"]
    assert (d1.axis, d1.lo, d1.hi, d1.sill, d1.top) == pytest.approx(("y", 1.3, 2.185, 0.0, 2.01))
    assert d1.sides == ("r1", "r2")
    f1 = g.openings["f1"]
    # windows hang from the Sturzhöhe 2.26: sill 2.26 - 1.26 = 1.0
    assert (f1.lo, f1.hi, f1.sill, f1.top) == pytest.approx((1.51, 2.77, 1.0, 2.26))
    assert f1.sides == (None, "r1")
    assert (g.openings["f2"].lo, g.openings["f2"].hi) == pytest.approx((3.27, 4.27))
    # centred on f1 (2.14)
    assert (g.openings["f3"].lo, g.openings["f3"].hi) == pytest.approx((1.64, 2.64))
    assert (g.openings["f4"].lo, g.openings["f4"].hi, g.openings["f4"].sill) == pytest.approx(
        (8.0, 9.0, 0.9)
    )
    assert codes(rep) == []


def test_explicit_face_and_raw_coordinate() -> None:
    d, _ = derive_text(BOX + "wall w5 EG IW y=w1.n+2 x=w4..w2\nwall w6 EG IW x=5+ y=w1..w5\n")
    g = d.arch
    assert (g.walls["w5"].lo, g.walls["w5"].hi) == pytest.approx((2.3, 2.415))
    assert (g.walls["w5"].s0, g.walls["w5"].s1) == pytest.approx((0.3, 9.7))
    assert (g.walls["w6"].lo, g.walls["w6"].s0, g.walls["w6"].s1) == pytest.approx((5.0, 0.3, 2.3))


def test_stacked_wall_and_core_mismatch() -> None:
    d, rep = derive_text(BOX + "wall w5 OG AW on=w1\nwall w6 OG IW on=w2\n")
    g = d.arch
    assert (g.walls["w5"].lo, g.walls["w5"].hi, g.walls["w5"].s0) == pytest.approx((0.0, 0.3, 0.0))
    assert ("E-GEO-001", "w6") in codes(rep)


def test_stair() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + "stair st1 EG OG x=w2-1 y=w3- up=w w=1 n=16 tread=0.26\nvoid v1 sl2 over=st1\n"
    )
    s = d.arch.stairs["st1"]
    assert s.riser == pytest.approx(2.9 / 16)
    assert s.run == pytest.approx(3.9)
    assert (s.x0, s.x1, s.y0, s.y1) == pytest.approx((4.8, 8.7, 6.7, 7.7))
    assert s.step == pytest.approx(2 * 2.9 / 16 + 0.26)
    assert d.arch.slabs["sl2"].net.area == pytest.approx(10 * 8 - 3.9)
    assert [c for c, _ in codes(rep) if c.startswith("W-ARCH-03")] == ["W-ARCH-035"]


def test_stair_warnings() -> None:
    _, rep = derive_text(BOX + SLABS + "stair st1 EG OG x=w2-1 y=w3- up=w w=1 n=12 tread=0.2\n")
    found = codes(rep)
    assert ("W-ARCH-034", "st1") in found  # 2 x 0.2417 + 0.2 = 0.683
    assert ("W-ARCH-033", "st1") in found  # no void in sl2


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (
            "wall w5 EG IW x=w6+1 y=w1..w3\nwall w6 EG IW x=w5+1 y=w1..w3\n",
            [("E-GEO-002", "w5"), ("E-GEO-003", "w6")],
        ),
        ("wall w5 EG IW x=w1+1 y=w1..w3\n", [("E-GEO-001", "w5")]),
        ("win f9 w1 1x1 x=E+0.5\n", [("E-ARCH-001", "f9")]),
        ("win f8 w1 1.26x1.26 x=W+1.51\nwin f9 w1 1x1 x=W+2\n", [("E-ARCH-002", "f9")]),
        (
            "wall w9 EG AW x=W+ y=S..N\n",
            [("E-ARCH-011", "w9"), ("E-ARCH-011", "w9"), ("E-ARCH-011", "w9")],
        ),
        ("room r1 EG living at=W+0.1,S+4\n", [("E-ARCH-020", "r1")]),
        ("room r1 EG living at=W+1,S+1\nroom r2 EG living at=E-1,N-1\n", [("E-ARCH-021", "r2")]),
        ("door d9 w99 1x2 x=W+1\n", [("E-REF-001", "d9")]),
        ("wall w5 EG FE y=S+1 x=w4..w2\n", [("E-REF-003", "w5")]),
        ("wall w5 OG AW on=w1\n", [("W-ARCH-010", "w5")]),
        ("win f9 w1 1x1 y=S+1\n", [("E-GEO-001", "f9")]),
        ("niche ni1 w2.w 1x1 y=w1+1 d=0.3\n", [("E-ARCH-007", "ni1")]),
        ("win f9 w1 1x2.5 x=W+1 sill=0.5\n", [("E-ARCH-003", "f9")]),
        ('waive wv1 W-ARCH-099 w1 "x"\n', [("W-ISSUE-001", "wv1")]),
    ],
)
def test_issues(extra: str, expected: list[tuple[str, str]]) -> None:
    _, rep = derive_text(BOX + SLABS + extra)
    assert [c for c in codes(rep) if c[0] != "W-ARCH-022"] == sorted(expected)


def test_dependency_issue_names_the_cause() -> None:
    _, rep = derive_text(BOX + "wall w5 EG IW x=w1+1 y=w1..w3\nwall w6 EG IW x=w5+1 y=w1..w3\n")
    by = {i.el: i for i in rep.issues}
    assert by["w6"].code == "E-GEO-002"
    assert "w5" in by["w6"].msg


def test_door_into_must_be_next_to_it() -> None:
    _, rep = derive_text(
        BOX
        + SLABS
        + "wall w5 EG IW x=w4+4 y=w1..w3\nwall w6 EG IW y=w1+3 x=w5..w2\n"
        + "door d1 w5 0.885x2.01 y=w1+1 into=r3 din=l\n"
        + "room r1 EG living at=W+1,S+1\nroom r2 EG bedroom at=E-1,S+1\n"
        + "room r3 EG bath at=E-1,N-1\n"
    )
    assert ("E-ARCH-004", "d1") in codes(rep)


def test_demolished_wall_does_not_bound_rooms() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + "wall w5 EG IW x=w4+4 y=w1..w3 demolish\n"
        + "win f9 w5 1x1 y=w1+1\n"
        + "room r1 EG living at=W+1,S+1\n"
    )
    assert d.arch.rooms["r1"].area == pytest.approx(9.4 * 7.4)
    assert ("E-ARCH-008", "f9") in codes(rep)


ROOF = """\
project r
level EG z=0 fb=0
grid W x=0
grid E x=10
grid S y=0
grid N y=8
type AW wall layers=gips:0.01,*mw:0.3,putz:0.02
type DA roof layers=ziegel:0.05,*sparren:0.15
wall w1 EG AW y=S+ x=W..E top=rf1
wall w2 EG AW x=E- y=w1..w3 top=rf1
wall w3 EG AW y=N- x=W..E top=rf1
wall w4 EG AW x=W+ y=w1..w3 top=rf1
roof rf1 EG DA gable ridge=x pitch=45 kn=0.5
room r1 EG living at=W+1,S+1
"""


def test_gable_roof() -> None:
    d, rep = derive_text(ROOF)
    rf = d.arch.roofs["rf1"]
    # rafter underside at the eaves: OK Rohdecke 0 + kn 0.5; tan 45° = 1; half width 4
    assert rf.base == pytest.approx(0.5)
    skin = 0.2 / (2**0.5 / 2)
    assert rf.eaves_z == pytest.approx(0.5 + skin)
    assert rf.ridge_z == pytest.approx(0.5 + 4 + skin)
    assert rf.underside(3, 2) == pytest.approx(2.5)
    assert rf.underside(3, 7) == pytest.approx(1.5)
    # the gable wall w4 follows the rafter underside along its centre line
    assert d.arch.walls["w4"].top == [
        (pytest.approx(0.3), pytest.approx(0.8)),
        (pytest.approx(4.0), pytest.approx(4.5)),
        (pytest.approx(7.7), pytest.approx(0.8)),
    ]
    r = d.arch.rooms["r1"]
    # clear height h(y) = min(0.5 + y, 8.5 - y) over y 0.31..7.69 (Fertig)
    assert r.height is None
    assert r.height_range() == (pytest.approx(0.81), pytest.approx(4.5))
    integral = 2 * ((0.5 * 4 + 4**2 / 2) - (0.5 * 0.31 + 0.31**2 / 2))
    assert r.volume == pytest.approx(9.38 * integral)
    assert codes(rep) == []


def test_shed_and_hip_roofs() -> None:
    d, _ = derive_text(ROOF.replace("gable ridge=x pitch=45", "shed up=n pitch=45"))
    rf = d.arch.roofs["rf1"]
    assert rf.ridge_z == pytest.approx(0.5 + 8 + 0.2 / (2**0.5 / 2))
    assert rf.underside(5, 6) == pytest.approx(6.5)
    d, _ = derive_text(ROOF.replace("gable ridge=x pitch=45", "hip pitch=45"))
    rf = d.arch.roofs["rf1"]
    assert rf.underside(1, 4) == pytest.approx(1.5)
    assert rf.underside(5, 4) == pytest.approx(4.5)

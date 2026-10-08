"""Walls in any direction (docs/decisions/0018-raw-walls.md), against hand-computed values.

BOX has grids W=0 E=10 S=0 N=8 and four 0.30 core walls on them. TK is a bare 0.20 wall.
"""

import math

import pytest
from shapely.geometry import Polygon

from tests.conftest import BOX, codes, derive_text, model_from
from uea.core.syntax import LineError

SLABS = "slab sl1 EG DE\nslab sl2 OG DE\n"
TK = "type TK wall layers=*mw:0.2\n"
HEAD = "".join(f"{x}\n" for x in BOX.splitlines() if not x.startswith("wall")) + TK


def corners(poly: Polygon) -> set[tuple[float, float]]:
    return {(round(c[0], 4), round(c[1], 4)) for c in poly.exterior.coords}


def test_three_four_five_wall() -> None:
    d, rep = derive_text(BOX + SLABS + TK + "wall w5 EG TK a=1,1 b=4,5\n")
    w = d.arch.walls["w5"]
    assert (w.o, w.s0, w.s1, w.lo, w.hi) == ("d", 0.0, pytest.approx(5.0), -0.1, 0.1)
    assert w.udir == pytest.approx((0.6, 0.8))
    assert (w.ea, w.eb) == ((0.0, 0.0), (0.0, 0.0))  # free ends stay as given
    # 0.1 either side of the axis, along the normal (-0.8, 0.6)
    assert corners(w.poly) == {(0.92, 1.06), (1.08, 0.94), (3.92, 5.06), (4.08, 4.94)}
    assert w.poly.area == pytest.approx(1.0)
    assert w.plan_point(2.5, 0.0) == pytest.approx((2.5, 3.0))
    assert codes(rep) == []


def test_points_can_be_anchored_on_walls_and_grids() -> None:
    d, _ = derive_text(BOX + TK + "wall w5 EG TK a=w4.c,w1.c b=E-1,N+0\n")
    w = d.arch.walls["w5"]
    # the axes of w4 and w1 cross at (0.15, 0.15); E-1 is x=9, N is y=8
    assert w.org == pytest.approx((0.15, 0.15))
    assert w.plan_point(w.s1, 0.0) == pytest.approx((9.0, 8.0))


def test_axis_parallel_raw_wall_is_an_ordinary_wall() -> None:
    d, rep = derive_text(
        BOX + SLABS + TK + "wall w5 EG TK a=5,7.7 b=5,0.3\nwall w6 EG TK y=w1+2 x=w4..w5\n"
    )
    w5 = d.arch.walls["w5"]
    assert (w5.o, w5.lo, w5.hi, w5.s0, w5.s1) == pytest.approx(("v", 4.9, 5.1, 0.3, 7.7))
    # other walls anchor on it and span to its face
    w6 = d.arch.walls["w6"]
    assert (w6.lo, w6.hi, w6.s0, w6.s1) == pytest.approx((2.3, 2.5, 0.3, 4.9))
    assert codes(rep) == []


def test_two_raw_walls_meeting_on_their_axes_make_a_full_corner() -> None:
    d, rep = derive_text(HEAD + "wall w1 EG TK a=0,0 b=5,0\nwall w2 EG TK a=5,0 b=5,4\n")
    w1, w2 = d.arch.walls["w1"], d.arch.walls["w2"]
    # each runs through to the far face of the other: 0.1 beyond the axis
    assert (w1.ea, w1.eb) == ((0.0, 0.0), pytest.approx((0.1, 0.1)))
    assert (w2.ea, w2.eb) == (pytest.approx((0.1, 0.1)), (0.0, 0.0))
    # an L: 5.1 x 0.2 along x, then 0.2 x 3.9 up
    assert w1.poly.union(w2.poly).area == pytest.approx(5.1 * 0.2 + 0.2 * 3.9)
    assert "E-ARCH-011" not in [c for c, _ in codes(rep)]


def test_a_corner_at_45_degrees_is_a_mitre() -> None:
    d, rep = derive_text(HEAD + "wall w1 EG TK a=0,0 b=4,0\nwall w2 EG TK a=4,0 b=7,3\n")
    w1, w2 = d.arch.walls["w1"], d.arch.walls["w2"]
    # a mitred polyline is as large as its strips: (4 + 3 sqrt 2) x 0.2, nothing missing at
    # the outer corner and nothing sticking out at the inner one
    assert w1.poly.union(w2.poly).area == pytest.approx(0.2 * (4 + 3 * math.sqrt(2)), abs=1e-4)
    # outer (south) corner where y=-0.1 meets the south face of w2: x = 4 + 0.1 (sqrt 2 - 1)
    xs = sorted(x for x, y in corners(w1.poly) if y == -0.1)
    assert xs[-1] == pytest.approx(4 + 0.1 * (math.sqrt(2) - 1), abs=1e-4)
    assert "E-ARCH-011" not in [c for c, _ in codes(rep)]


def test_chamfered_corner() -> None:
    """A 45° wall across the SW corner, from the axis of w4 to the axis of w1."""
    d, rep = derive_text(
        BOX
        + SLABS
        + TK
        + "wall w5 EG TK a=0.15,3.15 b=3.15,0.15\n"
        + "room r1 EG living at=5,4\nroom r2 EG storage at=0.6,0.6\n"
    )
    w5 = d.arch.walls["w5"]
    # the faces of the 0.2 wall are x+y = 3.3 +- 0.1 sqrt 2; both ends run to x=0 and y=0, the
    # outer faces of w4 and w1, so the body is a trapezoid with no gap and no wedge
    c = 0.1 * math.sqrt(2)
    assert corners(w5.poly) == {
        (0.0, round(3.3 - c, 4)),
        (round(3.3 - c, 4), 0.0),
        (round(3.3 + c, 4), 0.0),
        (0.0, round(3.3 + c, 4)),
    }
    # the room: the inner rectangle without the triangle behind the NE face x+y = 3.3 + c
    leg = 3.3 + c - 0.6
    assert d.arch.rooms["r1"].area == pytest.approx(9.4 * 7.4 - leg**2 / 2, abs=1e-4)
    assert d.arch.rooms["r1"].area_fin == pytest.approx(
        9.38 * 7.38 - (leg - 0.02) ** 2 / 2, abs=1e-4
    )
    assert d.arch.rooms["r1"].bounds == ["w1", "w2", "w3", "w4", "w5"]
    # the closet behind the wall: legs 3.3 - c - 0.6 on the SW side
    assert d.arch.rooms["r2"].area == pytest.approx((3.3 - c - 0.6) ** 2 / 2, abs=1e-4)
    assert codes(rep) == []


def test_openings_in_a_skew_wall_count_from_its_start() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + TK
        + "wall w5 EG TK a=1,1 b=4,5\n"
        + "door d1 w5 0.9x2.01 s=1+\n"
        + "win f1 w5 1x1 s=d1+0.5\n"
        + "win f2 w5 0.5x0.5 s=f1.c sill=0.3\n"
    )
    g = d.arch
    d1, f1, f2 = g.openings["d1"], g.openings["f1"], g.openings["f2"]
    assert d1.axis == "s"
    assert (d1.lo, d1.hi) == pytest.approx((1.0, 1.9))
    assert (f1.lo, f1.hi) == pytest.approx((2.4, 3.4))  # 0.5 past the + edge of d1
    assert (f2.lo, f2.hi) == pytest.approx((2.65, 3.15))  # centred on f1 at 2.9
    # the middle of d1 is 1.45 along the wall, 0.6 and 0.8 of that in x and y
    assert g.walls["w5"].plan_point(d1.mid, 0.0) == pytest.approx((1 + 1.45 * 0.6, 1 + 1.45 * 0.8))
    assert codes(rep) == []


def test_openings_in_a_chamfer_know_the_rooms_on_both_sides() -> None:
    d, rep = derive_text(
        BOX
        + SLABS
        + TK
        + "wall w5 EG TK a=0.15,3.15 b=3.15,0.15\n"
        + "door d1 w5 0.9x2.01 s=2+ into=r1 hand=l\n"
        + "room r1 EG living at=5,4\nroom r2 EG storage at=0.6,0.6\n"
    )
    # seen from a to b, the left side (the hi side, NE) is the living room
    assert d.arch.openings["d1"].sides == ("r2", "r1")
    assert codes(rep) == []


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ("win f9 w5 1x1 x=W+1\n", [("E-GEO-001", "f9")]),
        ("win f9 w1 1x1 s=1+\n", [("E-GEO-001", "f9")]),
        ("wall w6 EG TK y=w5+1 x=w4..w2\n", [("E-GEO-001", "w6")]),
        ("win f9 w5 1x1 s=f8+1\nwin f8 w4 1x1 y=S+2\n", [("E-GEO-001", "f9")]),
        ("niche ni1 w5.n 1x1 s=1+ d=0.1\n", [("E-GEO-001", "ni1")]),
    ],
)
def test_skew_wall_errors(extra: str, expected: list[tuple[str, str]]) -> None:
    _, rep = derive_text(BOX + SLABS + TK + "wall w5 EG TK a=1,1 b=4,5\n" + extra)
    got = [c for c in codes(rep) if c[0] in {"E-GEO-001", "E-GEO-002", "E-ARCH-001"}]
    assert got == sorted(expected)


def test_niche_in_a_skew_wall_uses_l_and_r() -> None:
    d, rep = derive_text(
        BOX + SLABS + TK + "wall w5 EG TK a=1,1 b=4,5\nniche ni1 w5.l 1x1 s=1+ d=0.1\n"
    )
    assert d.arch.openings["ni1"].face == "hi"  # the left of a to b
    assert codes(rep) == []


def test_the_overlap_check_still_sees_real_overlaps() -> None:
    _, rep = derive_text(HEAD + "wall w1 EG TK a=0,0 b=5,0\nwall w2 EG TK a=1,0 b=6,0\n")
    assert ("E-ARCH-011", "w2") in codes(rep)


def test_a_wall_needs_two_different_points() -> None:
    _, rep = derive_text(BOX + TK + "wall w5 EG TK a=1,1 b=1,1\n")
    assert ("E-GEO-001", "w5") in codes(rep)


def test_stacked_wall_follows_a_skew_wall() -> None:
    d, _ = derive_text(BOX + TK + "wall w5 EG TK a=1,1 b=4,5\nwall w6 OG TK on=w5\n")
    w5, w6 = d.arch.walls["w5"], d.arch.walls["w6"]
    assert (w6.o, w6.org, w6.udir) == (w5.o, w5.org, w5.udir)
    assert w6.poly.equals(w5.poly)


def test_nonsense_forms_are_rejected_when_parsed() -> None:
    with pytest.raises(LineError):
        model_from("wall w9 EG TK a=1,1\n")

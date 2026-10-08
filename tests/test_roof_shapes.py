"""Half-hip, mansard, flat and tent roofs (docs/decisions/0021-roof-shapes.md).

HOUSE is a box of 0.30 core walls, outside 0..10 x 0..8, so a roof covers 10 x 8 and the
finished room is 9.38 x 7.38 (x 0.31..9.69, y 0.31..7.69). Roofs have a knee of 0.5 and layers
of 0.20 above the rafters, none below.
"""

import math

import pytest
from shapely.geometry import Point

from tests.conftest import codes, derive_text
from uea.derive import Derived, Report

HOUSE = """\
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
room r1 EG living at=W+1,S+1
"""
T60, T20 = math.tan(math.radians(60)), math.tan(math.radians(20))
RUN = 2 / T60  # the steep part of the mansard rises 2 over this run


def roofed(line: str) -> tuple[Derived, Report]:
    d, rep = derive_text(HOUSE + line + "\n")
    return d, rep


def under(d: Derived, x: float, y: float) -> float:
    return d.arch.roofs["rf1"].underside(x, y)


def test_half_hip_cuts_the_ridge_short() -> None:
    d, rep = roofed("roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 halfhip=2")
    # 45°: the gable planes are 0.5 + y and 8.5 - y, the ridge 4.5 high. The hips run 2 in from
    # each end, so the hip plane is 2 lower at the end wall (2.5 at x=0) and rises as 2.5 + x
    assert under(d, 0, 4) == pytest.approx(2.5)
    assert under(d, 1, 4) == pytest.approx(3.5)
    assert under(d, 2, 4) == pytest.approx(4.5)  # the ridge begins
    assert under(d, 10, 4) == pytest.approx(2.5)
    assert under(d, 1, 1) == pytest.approx(1.5)  # still on the gable plane, which is lower
    assert d.arch.roofs["rf1"].peak == pytest.approx(4.0)
    assert codes(rep) == []


def test_half_hip_gable_wall_has_a_flat_top() -> None:
    d, _ = roofed("roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 halfhip=2")
    # the west wall's axis is at x=0.15, where the hip plane is 2.65: the gable planes reach it at
    # y = 2.15 and y = 5.85
    assert d.arch.walls["w4"].top == [
        (pytest.approx(0.3), pytest.approx(0.8)),
        (pytest.approx(2.15), pytest.approx(2.65)),
        (pytest.approx(5.85), pytest.approx(2.65)),
        (pytest.approx(7.7), pytest.approx(0.8)),
    ]


def test_half_hip_volume() -> None:
    d, _ = roofed("roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 halfhip=2")
    # the gable room: 9.38 x the integral of min(0.5 + y, 8.5 - y) over y 0.31..7.69; each hip
    # takes off the part of the gable above 2.5 + x, which at x is a triangle (2 - x)^2 in cross
    # section for x 0.31..2
    gable = 9.38 * 2 * ((0.5 * 4 + 4**2 / 2) - (0.5 * 0.31 + 0.31**2 / 2))
    assert d.arch.rooms["r1"].volume == pytest.approx(gable - 2 * (2 - 0.31) ** 3 / 3)


def test_half_hip_as_long_as_the_hip_is_a_hip_roof() -> None:
    d, _ = roofed("roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 halfhip=3.999")
    h, _ = roofed("roof rf1 EG DA hip pitch=45 knee=0.5")
    for x, y in [(0.5, 4), (2, 3), (3.5, 4), (6, 2), (9, 6)]:
        assert under(d, x, y) == pytest.approx(under(h, x, y), abs=0.01)


def test_gabled_mansard() -> None:
    d, rep = roofed("roof rf1 EG DA mansard ridge=x pitch=60 upper=20 rise=2 knee=0.5")
    rf = d.arch.roofs["rf1"]
    # steep part: 0.5 + tan 60° x d up to 2.5 at d = 2 / tan 60° = 1.155, then tan 20° x more
    assert under(d, 5, 0.5) == pytest.approx(0.5 + T60 * 0.5)
    assert under(d, 5, 2) == pytest.approx(2.5 + T20 * (2 - RUN))
    assert under(d, 5, 6.5) == pytest.approx(2.5 + T20 * (1.5 - RUN))  # 1.5 from the north edge
    assert under(d, 5, 7) == pytest.approx(0.5 + T60)  # 1 from it: still steep
    ridge = 2.0 + T20 * (4 - RUN)
    assert rf.peak == pytest.approx(ridge)
    assert under(d, 5, 4) == pytest.approx(0.5 + ridge)
    # the layers above (0.2 square to the roof) are thicker, measured upright, on the steep part
    assert rf.eaves_z == pytest.approx(0.5 + 0.2 / math.cos(math.radians(60)))
    assert rf.ridge_z == pytest.approx(0.5 + ridge + 0.2 / math.cos(math.radians(20)))
    assert rf.skin_of(rf.planes[0]) == pytest.approx(0.2 / math.cos(math.radians(60)))
    assert rf.skin_of(rf.planes[1]) == pytest.approx(0.2 / math.cos(math.radians(20)))
    assert rf.eave_edges == ["s", "n"]
    # the gable wall shows the break on both sides, at its axis x = 0.15
    assert d.arch.walls["w4"].top == [
        (pytest.approx(0.3), pytest.approx(0.5 + T60 * 0.3)),
        (pytest.approx(RUN), pytest.approx(2.5)),
        (pytest.approx(4.0), pytest.approx(0.5 + ridge)),
        (pytest.approx(8 - RUN), pytest.approx(2.5)),
        (pytest.approx(7.7), pytest.approx(0.5 + T60 * 0.3)),
    ]
    assert codes(rep) == []


def test_gabled_mansard_volume() -> None:
    d, _ = roofed("roof rf1 EG DA mansard ridge=x pitch=60 upper=20 rise=2 knee=0.5")
    # the height over y 0.31..4 (mirrored for the north half), times 9.38 along x
    steep = 0.5 * (RUN - 0.31) + T60 / 2 * (RUN**2 - 0.31**2)
    flat = 2.5 * (4 - RUN) + T20 * (4 - RUN) ** 2 / 2
    assert d.arch.rooms["r1"].volume == pytest.approx(9.38 * 2 * (steep + flat))


def test_hipped_mansard() -> None:
    d, rep = roofed("roof rf1 EG DA mansard pitch=60 upper=20 rise=2 knee=0.5")
    rf = d.arch.roofs["rf1"]
    assert rf.eave_edges == ["s", "n", "w", "e"]
    assert under(d, 1, 4) == pytest.approx(0.5 + T60)  # 1 in from the west edge, still steep
    assert under(d, 3, 4) == pytest.approx(2.5 + T20 * (3 - RUN))
    assert under(d, 5, 4) == pytest.approx(
        0.5 + 2.0 + T20 * (4 - RUN)
    )  # the ridge, 4 in from s and n
    # the west wall (axis x = 0.15) is under the steep west plane all along
    assert d.arch.walls["w4"].top == [
        (pytest.approx(0.3), pytest.approx(0.5 + T60 * 0.15)),
        (pytest.approx(7.7), pytest.approx(0.5 + T60 * 0.15)),
    ]
    assert codes(rep) == []


def test_flat_roof() -> None:
    d, rep = roofed("roof rf1 EG DA flat knee=2.7 eave=0.4 verge=1")
    rf = d.arch.roofs["rf1"]
    # the underside is at 2.7 everywhere, the skin 0.2 on top; the overhang is all eave
    assert all(under(d, x, y) == pytest.approx(2.7) for x, y in [(0, 0), (5, 4), (10, 8)])
    assert (rf.eaves_z, rf.ridge_z) == (pytest.approx(2.9), pytest.approx(2.9))
    assert rf.over.bounds == pytest.approx((-0.4, -0.4, 10.4, 8.4))
    r1 = d.arch.rooms["r1"]
    assert r1.height == pytest.approx(2.7)
    assert r1.volume == pytest.approx(9.38 * 7.38 * 2.7)
    assert d.arch.walls["w4"].top == [(pytest.approx(0.3), 2.7), (pytest.approx(7.7), 2.7)]
    assert codes(rep) == []


def test_flat_roof_over_a_wing() -> None:
    # a flat roof on a rectangle of the outline covers only that
    d, rep = roofed("roof rf1 EG DA flat knee=2.7 x=W..E y=S..S+4")
    assert d.arch.roofs["rf1"].foot.contains(Point(5, 2))
    assert not d.arch.roofs["rf1"].foot.contains(Point(5, 6))
    assert ("W-ARCH-042", "rf1") in codes(rep)


def test_tent_roof_is_a_hip_roof_on_a_square() -> None:
    d, rep = roofed("roof rf1 EG DA hip pitch=45 knee=0.5 x=W..W+8 y=S..N")
    rf = d.arch.roofs["rf1"]
    # four planes meeting in one point 4 above the eaves line
    assert under(d, 4, 4) == pytest.approx(4.5)
    assert (rf.peak, rf.eave_edges) == (pytest.approx(4.0), ["s", "n", "w", "e"])
    assert under(d, 4, 1) == pytest.approx(1.5) and under(d, 1, 4) == pytest.approx(1.5)
    assert ("W-ARCH-042", "rf1") in codes(rep)  # the box is 10 wide: 2 left over


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("roof rf1 EG DA gable ridge=x pitch=45 halfhip=4", "less than 4"),
        ("roof rf1 EG DA gable ridge=y pitch=45 halfhip=4.5", "leaves no ridge"),
        ("roof rf1 EG DA mansard pitch=60 upper=20 rise=7", "less than 6.928"),
    ],
)
def test_shapes_that_do_not_fit_their_rectangle(line: str, expected: str) -> None:
    d, rep = roofed(line)
    assert ("E-ARCH-043", "rf1") in codes(rep)
    msg = next(i.msg + " " + (i.fix or "") for i in rep.issues if i.code == "E-ARCH-043")
    assert expected in msg
    assert "rf1" not in d.arch.roofs


def test_two_shed_roofs_rising_outward_are_a_butterfly_roof() -> None:
    d, rep = roofed(
        "roof rf1 EG DA shed up=w pitch=45 knee=0.5 x=W..W+5 y=S..N\n"
        "roof rf2 EG DA shed up=e pitch=45 knee=0.5 x=W+5..E y=S..N"
    )
    r1 = d.arch.rooms["r1"]
    # lowest in the valley at x = 5 (the knee), highest at the finished west and east faces
    assert r1.height_range() == (pytest.approx(0.5), pytest.approx(0.5 + 5 - 0.31))
    assert d.arch.rooms["r1"].volume == pytest.approx(7.38 * 2 * (0.5 * 4.69 + 4.69**2 / 2))
    assert codes(rep) == []

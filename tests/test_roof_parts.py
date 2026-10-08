"""Several roofs on one storey are one roof (docs/decisions/0020-roof-parts.md).

An L-shaped house: wing A is x 0..10, y 0..4; wing B is x 0..4, y 0..10; 0.30 walls on the
outline, interior 0.3..9.7 by 0.3..3.7 and 0.3..3.7 by 3.7..9.7, 52.36 m². Roofs rise 45° from
a knee of 0.5 at the outer faces, so a roof plane is 0.5 + the distance from its eaves line.
"""

import pytest
from shapely.geometry import Point

from tests.conftest import codes, derive_text
from uea.packs.arch.geometry import RoomGeo

L_HOUSE = """\
project l
level EG z=0 fb=0
grid W x=0
grid E x=10
grid E2 x=4
grid S y=0
grid N y=10
grid N2 y=4
type TK wall layers=*mw:0.3
type DA roof layers=ziegel:0.05,*sparren:0.15
wall w1 EG TK y=S+ x=W..E top=rf1
wall w2 EG TK x=E- y=w1..w3 top=rf1
wall w3 EG TK y=N2- x=E2..E top=rf1
wall w4 EG TK x=E2- y=w3.s..w5 top=rf1
wall w5 EG TK y=N- x=W..E2 top=rf1
wall w6 EG TK x=W+ y=w1..w5 top=rf1
room r1 EG living at=1,1
"""
GABLES = (
    "roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 x=W..E y=S..N2\n"
    "roof rf2 EG DA gable ridge=y pitch=45 knee=0.5 x=W..E2 y=S..N\n"
)
HIPS = (
    "roof rf1 EG DA hip pitch=45 knee=0.5 x=W..E y=S..N2\n"
    "roof rf2 EG DA hip pitch=45 knee=0.5 x=W..E2 y=S..N\n"
)


def height_at(rg: RoomGeo, x: float, y: float) -> float:
    for plane, poly in rg.ceiling.pieces(rg.fin):
        if poly.distance(Point(x, y)) < 1e-9:
            return plane(x, y)
    raise AssertionError(f"({x}, {y}) is under no roof")


def pairs(*xs: tuple[float, float]) -> list[tuple[object, object]]:
    return [(pytest.approx(a), pytest.approx(b)) for a, b in xs]


def test_cross_gable_heights() -> None:
    d, rep = derive_text(L_HOUSE + GABLES)
    r1 = d.arch.rooms["r1"]
    assert r1.area == pytest.approx(52.36)
    # B's gable runs through A's roof (2, 1) and A's through B's (1, 2): the higher one counts
    for x, y, h in [
        (2, 1, 2.5),
        (1, 2, 2.5),
        (8, 2, 2.5),
        (2, 8, 2.5),
        (1, 1, 1.5),  # both planes cross here
        (6, 1, 1.5),
        (1, 6, 1.5),
        (3.85, 3.5, 1.0),  # the strip of A that is also under B: A is higher
        (3.5, 3.85, 1.0),
    ]:
        assert height_at(r1, x, y) == pytest.approx(h), (x, y)
    assert r1.height is None
    assert r1.height_range() == (pytest.approx(0.8), pytest.approx(2.5))
    assert codes(rep) == []


def test_cross_gable_volume() -> None:
    d, _ = derive_text(L_HOUSE + GABLES)
    # corner square 0.3..3.7: 0.5 x 3.4² + the integral of max(f(x), f(y)) with f(t) = min(t, 4-t),
    # which is 2 x 3.4 x 3.91 - (0.3 x 3.4² + 4 x 1.7³ / 3) by the measure of {f >= h};
    # each arm, 6 long: 6 x (0.5 x 3.4 + 3.91)
    corner = 0.5 * 3.4**2 + 2 * 3.4 * 3.91 - (0.3 * 3.4**2 + 4 * 1.7**3 / 3)
    arms = 2 * 6 * (0.5 * 3.4 + 3.91)
    assert d.arch.rooms["r1"].volume == pytest.approx(corner + arms)


def test_hip_roofs_on_both_wings_are_the_roof_of_the_l() -> None:
    d, rep = derive_text(L_HOUSE + HIPS)
    r1 = d.arch.rooms["r1"]
    for x, y, h in [
        (2, 2, 2.5),  # where the two ridges meet
        (2, 3, 2.5),  # on the ridge of B
        (3, 2, 2.5),  # on the ridge of A
        (3, 3, 1.5),
        (3.5, 3.5, 1.0),  # on the valley from the inner corner (4, 4)
        (7, 2, 2.5),
        (2, 7, 2.5),
    ]:
        assert height_at(r1, x, y) == pytest.approx(h), (x, y)
    assert codes(rep) == []


def test_walls_follow_the_combined_roof() -> None:
    d, _ = derive_text(L_HOUSE + GABLES)
    top = {k: w.top for k, w in d.arch.walls.items()}
    # the gable wall of B (north): 0.5 at the corners, 2.5 at its ridge
    assert top["w5"] == pairs((0.0, 0.5), (2.0, 2.5), (4.0, 0.5))
    # the south wall is the eaves wall of A (0.65 at the wall's centre line) except where it is
    # the gable wall of B: its plane is higher than 0.65 from x = 0.15 to 3.85
    assert top["w1"] == pairs((0.0, 0.65), (0.15, 0.65), (2.0, 2.5), (3.85, 0.65), (10.0, 0.65))
    # the west wall likewise is the gable wall of A, down to B's eaves (0.65) from y = 3.85
    assert top["w6"] == pairs((0.3, 0.8), (2.0, 2.5), (3.85, 0.65), (9.7, 0.65))
    assert top["w2"] == pairs((0.3, 0.8), (2.0, 2.5), (3.7, 0.8))
    assert top["w3"] == pairs((4.0, 0.65), (10.0, 0.65))
    assert top["w4"] == pairs((3.7, 0.8), (3.85, 0.65), (9.7, 0.65))


def test_one_roof_per_wing_warns_for_what_is_left_out() -> None:
    _, rep = derive_text(L_HOUSE + GABLES.splitlines(keepends=True)[0])
    found = [i for i in rep.issues if i.code == "W-ARCH-042"]
    assert [i.el for i in found] == ["rf1"]
    assert "24.00 m²" in found[0].msg  # wing B, 4 x 6 outside A
    assert "W-ARCH-041" not in [i.code for i in rep.issues]


def test_an_l_outline_without_footprints_gets_one_bounding_box() -> None:
    d, rep = derive_text(L_HOUSE + "roof rf1 EG DA gable ridge=x pitch=45 knee=0.5\n")
    assert [i.code for i in rep.issues if i.code.startswith("W-ARCH-04")] == ["W-ARCH-041"]
    assert "x=<a>..<b>" in next(i.fix or "" for i in rep.issues if i.code == "W-ARCH-041")
    rf = d.arch.roofs["rf1"]
    assert (rf.x0, rf.x1, rf.y0, rf.y1) == (0.0, 10.0, 0.0, 10.0)


def test_footprint_spans_must_resolve() -> None:
    _, rep = derive_text(L_HOUSE + "roof rf1 EG DA hip pitch=45 x=W..E y=S..S\n")
    assert ("E-GEO-001", "rf1") in codes(rep)


def test_equal_roofs_are_one_roof() -> None:
    d, rep = derive_text(
        L_HOUSE.replace("top=rf1", "")
        + "roof rf1 EG DA gable ridge=x pitch=45 knee=0.5 x=W..E y=S..N2\n"
        + "roof rf2 EG DA gable ridge=x pitch=45 knee=0.5 x=W..E y=S..N2\n"
    )
    r1 = d.arch.rooms["r1"]
    # the same planes twice: no second surface, and the lower index wins every tie
    assert height_at(r1, 6, 2) == pytest.approx(2.5)
    assert r1.volume is not None and r1.volume > 0
    assert [c for c in codes(rep) if c[0] == "W-ARCH-042"] == [("W-ARCH-042", "rf1")]

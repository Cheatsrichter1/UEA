"""Stairs with a landing, winders or a half turn (docs/decisions/0019-stair-shapes.md).

BOX: EG at 0, OG at 2.9, so 16 risers are 0.18125 high. All stairs are 1 m wide with a tread of
0.26 m unless said otherwise; a flight of k risers has k-1 treads.
"""

import math

import pytest
from shapely.geometry import Point

from tests.conftest import BOX, codes, derive_text

SLABS = "slab sl1 EG DE\nslab sl2 OG DE\n"
L16 = "stair st1 EG OG x=1+ y=1+ up=n w=1 n=16 tread=0.26 shape=l"


def stair(text: str):  # type: ignore[no-untyped-def]
    d, rep = derive_text(BOX + SLABS + text)
    return d.arch.stairs["st1"], rep


def test_l_stair_with_landing() -> None:
    s, _ = stair(L16 + " turn=l\n")
    # n1 = 8: seven treads (1.82 m) up the first flight, the 1 m landing, seven more
    assert (s.n1, s.riser) == (8, pytest.approx(2.9 / 16))
    assert (s.x0, s.x1, s.y0, s.y1) == pytest.approx((1.0, 3.82, 1.0, 3.82))
    assert s.poly.area == pytest.approx(1.82 + 1 + 1.82)
    # up=n, turn=l: first flight on the right (x 2.82..3.82), landing above it, then toward -x
    assert s.poly.contains(Point(3.3, 2.0)) and s.poly.contains(Point(3.3, 3.3))
    assert s.poly.contains(Point(1.5, 3.3)) and not s.poly.contains(Point(1.5, 1.5))
    kinds = [(p.kind, p.risers, p.tread) for p in s.parts]
    assert kinds == [("flight", 8, 0), ("flight", 8, 8), ("landing", 0, 8)]
    # 16 risers in all: 8 + 8, none in the turn
    assert sum(p.risers for p in s.parts) == 16
    assert s.walk[0] == pytest.approx((3.32, 1.0)) and s.walk[-1] == pytest.approx((1.0, 3.32))


def test_turning_the_other_way_mirrors_the_stair() -> None:
    s, _ = stair(L16 + " turn=r\n")
    assert s.poly.area == pytest.approx(4.64)
    assert s.poly.contains(Point(1.3, 2.0)) and s.poly.contains(Point(3.3, 3.3))
    assert not s.poly.contains(Point(3.3, 1.5))
    assert s.walk[-1] == pytest.approx((3.82, 3.32))


def test_the_first_flight_can_be_longer() -> None:
    s, _ = stair(L16 + " turn=l n1=10\n")
    # 9 treads (2.34 m) then the landing; 16 - 10 - 1 = 5 treads after it
    assert (s.x0, s.x1, s.y0, s.y1) == pytest.approx((1.0, 3.3, 1.0, 4.34))
    assert [p.risers for p in s.parts if p.kind == "flight"] == [10, 6]
    assert s.poly.area == pytest.approx(2.34 + 1 + 1.3)


def test_winders_replace_the_landing() -> None:
    s, _ = stair(L16 + " turn=r winders=3\n")
    # n1 = (16 - 3 + 1) // 2 = 7: six treads, three winders in the 1 m square, six treads
    assert s.n1 == 7
    assert s.poly.area == pytest.approx(1.56 + 1 + 1.56)
    assert (s.x1 - s.x0, s.y1 - s.y0) == pytest.approx((2.56, 2.56))
    winders = [p for p in s.parts if p.kind == "winder"]
    assert [p.tread for p in winders] == [7, 8, 9]
    # three equal 30° wedges from the inner corner: tan 30° / 2, 1 - tan 30°, tan 30° / 2
    t30 = math.tan(math.radians(30))
    assert [p.poly.area for p in winders] == pytest.approx([t30 / 2, 1 - t30, t30 / 2])
    flights = [(p.risers, p.tread) for p in s.parts if p.kind == "flight"]
    assert flights == [(7, 0), (7, 9)]
    # 7 + 7 risers in the flights and the 2 between the three winder treads
    assert sum(r for r, _ in flights) + len(winders) - 1 == 16
    assert len(s.lines) == 6 + 2 + 6  # tread edges of both flights and the two rays


def test_u_stair_has_a_well() -> None:
    s, _ = stair("stair st1 EG OG x=1+ y=1+ up=n w=1 n=16 tread=0.26 shape=u turn=l\n")
    # both flights 1.82 m, landing 1 x 2.1, the 0.1 well between them
    assert (s.x1 - s.x0, s.y1 - s.y0) == pytest.approx((2.1, 2.82))
    assert s.poly.area == pytest.approx(1.82 + 2.1 + 1.82 + 1.82 * 0.1)
    assert s.poly.contains(Point(1.0 + 1.05, 2.0))  # in the well
    assert [p.risers for p in s.parts if p.kind == "flight"] == [8, 8]
    # up the right side, back down the left
    assert s.walk[0] == pytest.approx((2.6, 1.0)) and s.walk[-1] == pytest.approx((1.5, 1.0))


def test_u_stair_with_a_longer_second_flight_reaches_back() -> None:
    s, _ = stair("stair st1 EG OG x=1+ y=1+ up=n w=1 n=17 tread=0.26 shape=u turn=l gap=0.2 n1=6\n")
    # first flight 5 treads (1.3 m), landing, second flight 17 - 6 - 1 = 10 treads (2.6 m) that
    # reaches back past the start of the first: along the climb it runs from -1.3 to 1.3 + 1
    assert (s.x1 - s.x0) == pytest.approx(2 * 1 + 0.2)
    assert (s.y1 - s.y0) == pytest.approx(2.6 + 1)


def test_void_over_a_shaped_stair_is_its_footprint() -> None:
    d, rep = derive_text(BOX + SLABS + L16 + " turn=l\nvoid v1 sl2 over=st1\n")
    assert d.arch.slabs["sl2"].net.area == pytest.approx(80 - 4.64)
    assert [c for c, _ in codes(rep) if c.startswith("W-ARCH-03")] == ["W-ARCH-035"]


def test_describe_a_shaped_stair() -> None:
    from uea.packs.arch.views import describe

    d, _ = derive_text(BOX + SLABS + L16 + " turn=r winders=3\n")
    line = describe(d, d.model["st1"])[0]
    assert "16 risers 0.181" in line and "l turn r, 7+7 risers, 3 winders" in line
    assert "= 4.12 m²" in line

"""The 2D helpers: half-planes and the highest of several roof parts."""

import pytest
from shapely.geometry import Point

from uea.geom import Ceil, Lin, Part, halfplane, rect, union_pieces


def test_halfplane_with_a_corner_of_the_clip_box_on_the_line() -> None:
    # the box around the square is 1 larger on every side, so its corner (-1, 3) lies on x + y = 2
    tri = halfplane(rect(0, 2, 0, 2), Lin(-1, -1, 2))
    assert tri.area == pytest.approx(2.0)
    assert tri.covers(Point(0.5, 0.5)) and not tri.covers(Point(1.5, 1.5))


def test_the_highest_part_wins_and_ties_go_to_the_first() -> None:
    a = Part(rect(0, 4, 0, 4), (Lin(0, 0.5, 0), Lin(0, -0.5, 4)))  # ridge along x at y = 2, 1 high
    b = Part(rect(0, 4, 0, 4), (Lin(0.5, 0, 0), Lin(-0.5, 0, 4)))  # ridge along y at x = 2
    pieces = union_pieces([a, b], rect(0, 4, 0, 4))
    assert sum(p.area for _, _, p in pieces) == pytest.approx(16.0)
    # at (1, 2) a is 1.0 and b is 0.5; at (2, 1) it is the other way round
    for x, y, part, h in [(1, 2, 0, 1.0), (2, 1, 1, 1.0), (1, 1, 0, 0.5)]:
        hit = [(i, f(x, y)) for i, f, p in pieces if p.distance(Point(x, y)) < 1e-9]
        assert (part, h) in [(i, pytest.approx(v)) for i, v in hit], (x, y)
    twice = union_pieces([a, a], rect(0, 4, 0, 4))
    assert {i for i, _, _ in twice} == {0}


def test_ceiling_is_the_lower_of_the_slab_and_the_roofs() -> None:
    # a gable roof 0.5 + the distance to y = 0 or y = 4 (ridge 2.5 at y = 2) under a slab at 1.5
    roof = Part(rect(0, 4, 0, 4), (Lin(0, 1, 0.5), Lin(0, -1, 4.5)))
    ceil = Ceil((Lin(0, 0, 1.5),), (roof,))
    g = rect(0, 4, 0, 4)
    # the roof is lower than the slab for y < 1 and y > 3: 0.5 + y, then 1.5, then 4.5 - y
    assert ceil.height_range(g) == (pytest.approx(0.5), pytest.approx(1.5))
    assert ceil.volume(g) == pytest.approx(4 * (1.0 + 2 * 1.5 + 1.0))
    assert ceil.at_least(g, 1.0).area == pytest.approx(4 * 3)  # y from 0.5 to 3.5
    assert not Ceil()
    assert Ceil((Lin(0, 0, 2.5),)).flat(g)


def test_no_roof_over_a_point_means_only_the_slab_counts() -> None:
    roof = Part(rect(0, 2, 0, 4), (Lin(0, 0, 0.5),))
    ceil = Ceil((Lin(0, 0, 2.5),), (roof,))
    g = rect(0, 4, 0, 4)
    assert ceil.volume(g) == pytest.approx(2 * 4 * 0.5 + 2 * 4 * 2.5)
    assert Ceil(parts=(roof,)).volume(g) == pytest.approx(2 * 4 * 0.5)  # nothing over x > 2

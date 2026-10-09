"""Cable routes: the shortest tree from the board over a circuit's devices, rectilinear, with the
allowance per run. Hand-computed on the 10 x 8 box house of test_elec (the inside face of the west
wall at x = 0.3, `y=w1+1` is y = 1.3, a board at 1.4 m, a socket at 0.3 m, a switch at 1.05 m)."""

import pytest

from tests.conftest import derive_text
from tests.test_elec import BOARD, HOUSE, elec, prototype_text
from uea.derive import Derived
from uea.packs.elec.routes import ALLOW, gap
from uea.packs.elec.views import describe


def routed(extra: str) -> Derived:
    d, rep = elec(extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d


def test_sockets_are_chained_in_order_of_distance() -> None:
    d = routed("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3\n")
    r = d.elec.routes["c2"]
    # board (0.3, 1.3, 1.4), s1 (0.3, 2.3, 0.3), s2 (0.3, 3.3, 0.3)
    # board to s1: 1.0 along y and 1.1 up/down = 2.1; s1 to s2: 1.0
    assert [(x.a, x.b) for x in r.runs] == [("b1", "s1"), ("s1", "s2")]
    assert [x.length for x in r.runs] == pytest.approx([2.4, 1.3])
    assert r.total == pytest.approx(3.7)
    assert r.reach == {"b1": 0.0, "s1": pytest.approx(2.4), "s2": pytest.approx(3.7)}
    assert r.far == ("s2", pytest.approx(3.7))
    assert r.skipped == []


def test_a_tie_goes_to_the_lower_id() -> None:
    # the board at y 4.3; the sockets 1.5 each side along y and 1.1 lower: both 2.6 away from it,
    # and 3.0 from each other
    text = (HOUSE + BOARD).replace("y=w1+1 z=1.4", "y=w1+4 z=1.4")
    d, _ = derive_text(text + "sock s2 w4 c2 y=w1+2.5\nsock s1 w4 c2 y=w1+5.5\n")
    r = d.elec.routes["c2"]
    assert [(x.a, x.b) for x in r.runs] == [("b1", "s1"), ("b1", "s2")]
    assert [x.length for x in r.runs] == pytest.approx([2.9, 2.9])
    assert r.far == ("s2", pytest.approx(2.9))
    assert r.total == pytest.approx(5.8)


def test_a_luminaire_hangs_from_the_ceiling() -> None:
    d = routed("lum l1 r1 at=5,4 z=2.5\nswitch sw1 w4 c1 y=w1+1 ctl=l1\n")
    r = d.elec.routes["c1"]
    # board (0.3, 1.3, 1.4); sw1 (0.3, 1.3, 1.05) is 0.35 away; l1 (5, 4, 2.5) is 4.7 + 2.7 + 1.1 =
    # 8.5 from the board and 4.7 + 2.7 + 1.45 = 8.85 from the switch: the board feeds both
    assert [(x.a, x.b) for x in r.runs] == [("b1", "sw1"), ("b1", "l1")]
    assert [x.length for x in r.runs] == pytest.approx([0.35 + 0.3, 8.5 + 0.3])
    assert r.far == ("l1", pytest.approx(8.8))


def test_a_circuit_branches_where_that_is_shorter() -> None:
    # s3 is nearer to s1 than to the board, but s2 is too: it is fed from the nearest one
    d = routed("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+4\nsock s3 w4 c2 y=w1+3\n")
    r = d.elec.routes["c2"]
    # chain b1 - s1 - s3 - s2, each step along y 1.0
    assert [(x.a, x.b) for x in r.runs] == [("b1", "s1"), ("s1", "s3"), ("s3", "s2")]
    assert r.far == ("s2", pytest.approx(2.4 + 1.3 + 1.3))


def test_a_connection_with_no_place_is_skipped() -> None:
    d = routed("sock s1 w4 c2 y=w1+2\nfeed fd1 r1 c2 w=1000\n")
    r = d.elec.routes["c2"]
    assert r.skipped == ["fd1"]
    assert [x.b for x in r.runs] == ["s1"]


def test_a_circuit_with_nothing_placed_has_no_cable() -> None:
    d = routed("")
    assert d.elec.routes["c1"].runs == []
    assert d.elec.routes["c1"].far is None
    assert describe(d, d.model["c1"])[1:] == []


def test_the_route_follows_a_moved_board() -> None:
    near = routed("sock s1 w4 c2 y=w1+2\n")
    assert near.elec.routes["c2"].total == pytest.approx(2.4)
    text = (HOUSE + BOARD).replace("y=w1+1 z=1.4", "y=w1+4 z=1.4") + "sock s1 w4 c2 y=w1+2\n"
    d, _ = derive_text(text)
    # board now at y 4.3: 2.0 along y, 1.1 in height
    assert d.elec.routes["c2"].total == pytest.approx(2.0 + 1.1 + 0.3)


def test_data_outlets_are_cabled_one_run_from_the_board() -> None:
    d = routed("board b2 w4 y=w1+5 z=1.4 media\ndata dt1 w4 b2 y=w1+3 n=2\n")
    run = d.elec.homeruns["dt1"]
    # b2 (0.3, 5.3, 1.4), dt1 (0.3, 3.3, 0.3): 2.0 + 1.1
    assert (run.a, run.b, run.length) == ("b2", "dt1", pytest.approx(3.1 + 0.3))
    assert describe(d, d.model["dt1"])[0].endswith("| 3.4 m of cable from b2")


def test_the_circuit_view_says_how_long_and_how_far() -> None:
    d = routed("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3\n")
    assert describe(d, d.model["c2"])[1] == "cable 3.7 m in 2 runs | farthest s2 at 3.7 m"
    d = routed("sock s1 w4 c2 y=w1+2\nfeed fd1 r1 c2\n")
    assert (
        describe(d, d.model["c2"])[1]
        == "cable 2.4 m in 1 runs | farthest s1 at 2.4 m | not placed: fd1"
    )


def test_the_gap_is_rectilinear() -> None:
    d = routed("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3 z=1.3\n")
    assert gap(d.mounts["s1"], d.mounts["s2"]) == pytest.approx(1.0 + 1.0)


def test_the_tables_list_runs_and_quantities() -> None:
    from uea.export.tables import tables

    d = routed(
        "sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3\n"
        "lum l1 r1 at=5,4 z=2.5\nswitch sw1 w4 c1 y=w1+1 ctl=l1\n"
        "board b2 w4 y=w1+5 z=1.4 media\ndata dt1 w4 b2 y=w1+3 n=2\n"
    )
    ts = {t.name: t for t in tables(d)}
    heads = [c.head for c in ts["Stromkreise"].cols]
    c1, c2 = (dict(zip(heads, r, strict=True)) for r in ts["Stromkreise"].rows)
    assert (c2["Leitungslänge m"], c2["Längster Weg m"]) == (3.7, 3.7)
    assert (c1["Leitungslänge m"], c1["Längster Weg m"]) == (9.45, 8.8)
    runs = ts["Leitungen"]
    assert [r[:3] for r in runs.rows] == [
        ["c1", "b1", "sw1"],
        ["c1", "b1", "l1"],
        ["c2", "b1", "s1"],
        ["c2", "s1", "s2"],
        ["Daten b2", "b2", "dt1"],
    ]
    assert [r[4] for r in runs.rows] == [0.65, 8.8, 2.4, 1.3, 6.8]
    assert runs.total is not None and runs.total[4] == pytest.approx(19.95)
    q = ts["Kabelmengen"]
    assert q.rows == [
        ["NYM-J3x1.5", 1, 9.45],
        ["NYM-J3x2.5", 1, 3.7],
        ["Datenleitung (2 Ports)", 1, 6.8],
    ]
    # one storey: the OG has no run
    assert not {"Leitungen"} & {t.name for t in tables(d, "OG")}


def test_haus_mueller_routes() -> None:
    d, _ = derive_text(prototype_text())
    e = d.elec
    placed = {k: [x for x in cg.devices if x in d.mounts] + cg.lums for k, cg in e.circuits.items()}
    for cid, route in e.routes.items():
        assert len(route.runs) == len(placed[cid])
        assert all(r.length >= ALLOW for r in route.runs)
        far = route.far
        if far:
            assert route.total >= far[1] > 0
    assert sorted(e.homeruns) == ["dt1", "dt2", "dt3"]

"""Shafts, pre-wall installations and installation zones (decision 0045), by hand on the 10 x 8
box of conftest with an OG on top."""

import pytest

from tests.conftest import BOX, derive_text
from tests.test_elec import found
from uea.export.drawing import Line, Text
from uea.export.sheet import sheet_plan
from uea.packs.arch.views import describe
from uea.packs.arch.wofl import WOFL
from uea.packs.net import Net, Node, Section, Zoned, through

HOUSE = (
    BOX
    + "wall w5 OG AW on=w1 lb h=2.5\nwall w6 OG AW on=w2 lb h=2.5\n"
    + "wall w7 OG AW on=w3 lb h=2.5\nwall w8 OG AW on=w4 lb h=2.5\n"
    + "slab sl1 EG DE\nslab sl2 OG DE\n"
    + "room r1 EG living at=W+1,S+1\nroom r2 OG living at=W+1,S+1\n"
)
SHAFT = "shaft sh1 EG 0.4x0.6 at=W+8,S+2 to=OG\n"


def test_a_shaft_opens_the_slabs_and_the_rooms() -> None:
    d, rep = derive_text(HOUSE)
    before = {k: r.area_fin for k, r in d.arch.rooms.items()}
    net = d.arch.slabs["sl2"].net.area
    d, rep = derive_text(HOUSE + SHAFT)
    assert [i.code for i in rep.issues if i.code.startswith("E-")] == []
    sh = d.arch.shafts["sh1"]
    assert (sh.levels, sh.slabs) == (["EG", "OG"], ["sl2"])
    # 0.4 x 0.6 out of the slab it passes and out of the rooms on both storeys
    assert d.arch.slabs["sl2"].net.area == pytest.approx(net - 0.24)
    assert d.arch.rooms["r1"].area_fin == pytest.approx(before["r1"] - 0.24)
    assert d.arch.rooms["r2"].area_fin == pytest.approx(before["r2"] - 0.24)
    assert describe(d, d.model["sh1"]) == ["x 7.8..8.2 y 1.7..2.3 = 0.24 m² | EG..OG | opens sl2"]
    for level in ("EG", "OG"):
        dw = sheet_plan(d, level)
        assert dw is not None
        assert any(isinstance(it, Text) and it.text == "Schacht sh1" for it in dw.items)
    _, rep = derive_text(HOUSE + "shaft sh1 EG 0.4x0.6 at=W+8,S+2 to=EG\n")
    assert found(rep, "E-ARCH-070") == ["sh1"]


def test_networks_pass_through_a_shaft() -> None:
    d, _ = derive_text(HOUSE + SHAFT)
    # a pipe from the EG at (5, 5) to the OG at (6, 6), with no hole named: through the shaft's
    # middle (8, 2), the detour 3 + 3 and 2 + 4 in plan and 3 up
    a, b = Node("a", "EG", (5.0, 5.0), 0.5), Node("b", "OG", (6.0, 6.0), 3.5)
    net = Net("a", {"a": a, "b": b}, [Section("a", "b", 5.0, 3, "pipe", ["b"])])
    cs = through(d, net)
    assert [(c.slab, c.hole) for c in cs] == [("sl2", "sh1")]
    assert net.sections[0].length == pytest.approx(3 + 3 + 2 + 4 + 3)
    # a riser standing in the shaft passes the slab in it
    up = Net("r", {"r": Node("r", "EG", (8.0, 2.0), 0.0), "s": Node("s", "OG", (8.0, 2.0), 3.0)})
    up.sections = [Section("r", "s", 3.0, 1, "riser", ["s"])]
    assert [c.hole for c in through(d, up)] == ["sh1"]


PREWALL = "prewall vw1 w4.e 1.6x1.2 y=S+1 d=0.2\n"


def test_a_prewall_carries_its_fixtures() -> None:
    text = HOUSE + PREWALL + "type MV pipe sizes=16x2 k=0.007 bend=1 tee=1 default\n"
    text += "san sa1 w4.e basin y=S+1.5\nsan sa2 w4.e basin y=S+5\n"
    d, rep = derive_text(text)
    assert [i.code for i in rep.issues if i.code.startswith("E-")] == []
    pw = d.arch.prewalls["vw1"]
    # w4's core ends at x 0.3, its plaster at 0.31: the pre-wall from 0.31 to 0.51
    x0, y0, x1, y1 = pw.poly.bounds
    assert (x0, y0, x1, y1) == (
        pytest.approx(0.31),
        pytest.approx(1.0),
        pytest.approx(0.51),
        pytest.approx(2.6),
    )
    assert d.plumb.at["sa1"].point == (pytest.approx(0.51), pytest.approx(1.5))
    assert d.plumb.at["sa2"].point == (pytest.approx(0.3), pytest.approx(5.0))
    assert describe(d, d.model["vw1"])[0].endswith("| carries sa1")
    # 1.2 m high: still floor area; 1.6 m high, more than 0.1 m²: not (WoFlV §3 Abs. 3 Nr. 1)
    o = WOFL.fn(d, "r1")
    assert o.data["rooms"][0]["minus"] == []
    d, _ = derive_text(HOUSE + PREWALL.replace("1.6x1.2", "1.6x1.6"))
    o = WOFL.fn(d, "r1")
    room = o.data["rooms"][0]
    assert room["minus"] == [
        {"what": "Vormauerung vw1", "area": pytest.approx(0.32), "rule": "§3 Abs. 3 Nr. 1"}
    ]
    assert room["wofl"] == pytest.approx(room["grund"] - 0.32)


def test_zones() -> None:
    d, _ = derive_text(HOUSE + "zone iz1 EG a=W+1,N-0.5 b=E-1,N-0.5 z=2.3\n")
    zoned = Zoned(d)
    a, b = Node("a", "EG", (1.0, 1.0), 0.3), Node("b", "EG", (9.0, 1.0), 0.3)
    # up to the zone at y 7.5, 2.3 high: 6.5 + 2.0; along it 8; and down again 6.5 + 2.0
    assert zoned(a, b) == (pytest.approx(25.0), 5)
    assert zoned.path(a, b) == [(1.0, 1.0), (1.0, 7.5), (9.0, 7.5), (9.0, 1.0)]
    # another storey has no zones: the rectilinear distance
    c, e = Node("c", "OG", (1.0, 1.0), 3.3), Node("e", "OG", (9.0, 1.0), 3.3)
    assert zoned(c, e) == (pytest.approx(8.0), 1)
    # two zones crossing at different heights join by the difference
    d, _ = derive_text(
        HOUSE
        + "zone iz1 EG a=W+1,N-0.5 b=E-1,N-0.5 z=2.3\n"
        + "zone iz2 EG a=W+5,S+0.5 b=W+5,N-0.5 z=2.5\n"
    )
    zoned = Zoned(d)
    f = Node("f", "EG", (5.0, 1.0), 2.5)
    g = Node("g", "EG", (8.0, 7.5), 2.3)
    # f onto iz2 at (5, 1) (0), along it to (5, 7.5) 6.5, over to iz1 0.2, along to (8, 7.5) 3
    assert zoned(f, g)[0] == pytest.approx(6.5 + 0.2 + 3)


def test_zones_on_the_plans_and_in_the_pipes() -> None:
    from uea.export.install import E_ZONE
    from uea.export.tga import sheet_tga

    text = HOUSE + "zone iz1 EG a=W+1,N-0.5 b=E-1,N-0.5 z=0.3\n"
    text += "type MV pipe sizes=16x2 k=0.007 bend=1 tee=1 default\n"
    text += "meter wz1 r1 at=W+1,S+1\nsan sa1 w2.w sink y=S+2\n"
    d, _ = derive_text(text)
    cold = d.plumb.cold
    assert cold is not None
    s = cold.sections[0]
    # from the meter (1, 1) to the zone at (1, 7.5), along it to (9, 7.5), down to the sink
    assert s.path is not None and s.path[1] == (1.0, 7.5)
    dw = sheet_tga(d, "EG", "plumb")
    assert dw is not None
    assert [it for it in dw.items if isinstance(it, Line) and it.layer == E_ZONE]

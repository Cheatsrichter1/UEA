"""Wohnfläche per WoFlV, against hand-computed values (own data, not the ordinance's examples)."""

import pytest

from tests.conftest import BOX, derive_text
from tests.test_geometry import ROOF
from uea.packs.arch.wofl import wofl

HOUSE = (
    BOX
    + """\
level DB z=5.8 fb=0.2
slab sl1 EG DE
slab sl2 OG DE
slab sl3 DB DE
wall w5 OG AW on=w1
wall w6 OG AW on=w2
wall w7 OG AW on=w3
wall w8 OG AW on=w4
stair st1 EG OG x=w2-1 y=w3- up=w w=1 n=16 tread=0.26
void v1 sl2 over=st1
room r1 EG living at=W+1,S+1
room r2 OG bedroom at=W+1,S+1
room r3 DB attic at=W+1,S+1
"""
)
FIN = 9.38 * 7.38  # Fertig area of the box room
STAIR = 3.9 * (7.69 - 6.7)  # stair x 4.8..8.7, y 6.7..7.7, cut at the Fertig face y = 7.69


def test_stair_and_hole_are_deducted() -> None:
    d, _ = derive_text(HOUSE)
    o = wofl(d, None)
    rooms = {r["id"]: r for r in o.data["rooms"]}
    assert rooms["r1"]["grund"] == pytest.approx(FIN, abs=1e-4)
    assert rooms["r1"]["minus"] == [
        {"what": "Treppe st1", "area": pytest.approx(STAIR, abs=1e-4), "rule": "§3 Abs. 3 Nr. 2"}
    ]
    assert rooms["r1"]["wofl"] == pytest.approx(FIN - STAIR, abs=1e-4)
    assert rooms["r2"]["minus"][0]["what"] == "Deckenöffnung v1"
    assert rooms["r2"]["wofl"] == pytest.approx(FIN - STAIR, abs=1e-4)
    assert rooms["r3"]["excluded"] == "Bodenraum, §2 Abs. 3 Nr. 1 d"
    assert o.data["total"] == pytest.approx(2 * (FIN - STAIR), abs=1e-4)


def test_niche_to_the_floor_counts() -> None:
    d, _ = derive_text(HOUSE + "niche ni1 w2.w 1x2.1 y=w1+2 d=0.2\n")
    rooms = {r["id"]: r for r in wofl(d, "EG").data["rooms"]}
    assert rooms["r1"]["plus"][0]["area"] == pytest.approx(0.2)
    assert rooms["r1"]["wofl"] == pytest.approx(FIN - STAIR + 0.2, abs=1e-4)


@pytest.mark.parametrize("niche", ["1x2.1 y=w1+2 d=0.1", "1x1.5 y=w1+2 sill=0.3 d=0.2"])
def test_shallow_or_raised_niches_do_not_count(niche: str) -> None:
    d, _ = derive_text(HOUSE + f"niche ni1 w2.w {niche}\n")
    rooms = {r["id"]: r for r in wofl(d, "EG").data["rooms"]}
    assert rooms["r1"]["plus"] == []


def test_heights_under_a_roof() -> None:
    # clear height min(0.5 + y, 8.5 - y): >= 2 m for y 1.5..6.5, 1..2 m for y 0.5..1.5 and
    # 6.5..7.5, under 1 m for y 0.31..0.5 and 7.5..7.69; room width 9.38
    d, _ = derive_text(ROOF)
    r = wofl(d, None).data["rooms"][0]
    assert r["full"] == pytest.approx(5.0 * 9.38, abs=1e-4)
    assert r["half"] == pytest.approx(2.0 * 9.38, abs=1e-4)
    assert r["low"] == pytest.approx(0.38 * 9.38, abs=1e-4)
    assert r["wofl"] == pytest.approx(5.0 * 9.38 + 9.38, abs=1e-4)


def test_scope() -> None:
    d, _ = derive_text(HOUSE)
    assert [r["id"] for r in wofl(d, "OG").data["rooms"]] == ["r2"]
    assert [r["id"] for r in wofl(d, "r1").data["rooms"]] == ["r1"]
    with pytest.raises(ValueError, match="scope"):
        wofl(d, "w1")


def test_room_without_ceiling_stops() -> None:
    d, _ = derive_text(HOUSE.replace("room r3 DB attic", "room r3 DB living"))
    with pytest.raises(ValueError, match="no ceiling"):
        wofl(d, None)

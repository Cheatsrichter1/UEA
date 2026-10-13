"""Split level: a tall single-storey hall beside a two-storey wing, on the same storeys.

A box of 0.30 core walls, outside 0..10 x 0..8, 6 m tall. Wall w5 (core x 4..4.3) parts the
two-storey wing in the west from the hall in the east. The OG slab (0.20) has a void over the
hall; a flat roof on EG covers the hall (x 4..10) with its underside 5.0 above the SSL, and a
flat roof on OG covers the wing.
"""

import pytest

from tests.conftest import codes, derive_text
from uea.derive import Derived, Report

BOX = """\
project p
level EG z=0 fb=0
level OG z=3 fb=0
grid W x=0
grid E x=10
grid S y=0
grid N y=8
type AW wall layers=gips:0.01,*mw:0.3,putz:0.02
type DE slab layers=*beton:0.2
type DA roof layers=kies:0.05,*holz:0.15
wall w1 EG AW y=S+ x=W..E h=6 lb
wall w2 EG AW x=E- y=w1..w3 h=6 lb
wall w3 EG AW y=N- x=W..E h=6 lb
wall w4 EG AW x=W+ y=w1..w3 h=6 lb
wall w5 EG AW x=W+4 y=w1..w3 h=6 lb
room r1 EG office at=W+1,S+1
room r2 EG storage at=E-1,S+1
slab sl1 OG DE
wall w6 OG AW y=S+ x=W..W+4.3 top=rf2
wall w7 OG AW y=N- x=W..W+4.3 top=rf2
wall w8 OG AW x=W+ y=w6..w7 top=rf2
wall w9 OG AW x=W+4 y=w6..w7 top=rf2
room r3 OG office at=W+1,S+1
roof rf2 OG DA flat knee=2.5 x=W..W+4.3 y=S..N
"""
HALL = "void v1 sl1 x=w5..E y=S..N\nroof rf1 EG DA flat knee=5 x=W+4..E y=S..N\n"


def split(extra: str = HALL) -> tuple[Derived, Report]:
    return derive_text(BOX + extra)


def test_the_hall_reaches_up_to_its_own_roof() -> None:
    d, rep = split()
    r1, r2 = d.arch.rooms["r1"], d.arch.rooms["r2"]
    # the hall has no slab above it: its ceiling is the roof underside, 5.0 above the FFL
    assert r2.height == pytest.approx(5.0)
    assert r2.volume == pytest.approx(r2.area_fin * 5.0)
    # the wing below the slab keeps the storey: 3.0 - 0.2
    assert r1.height == pytest.approx(2.8)
    # the airspace over the hall needs no room and no roof of OG; the wing of EG needs no roof
    # of EG, it lies under the slab of OG
    assert codes(rep) == []


def test_a_void_without_its_own_roof_keeps_the_storey() -> None:
    # a void with nothing of this storey above it (a stair well) is still under the storey above
    d, rep = split("void v1 sl1 x=w5..E y=S..N\n")
    assert d.arch.rooms["r2"].height == pytest.approx(2.8)
    assert ("W-ARCH-022", "OG") not in codes(rep)


def test_without_the_void_the_slab_still_caps_the_hall() -> None:
    # a roof on EG under the slab of OG: the slab is lower and caps the room
    d, rep = split("roof rf1 EG DA flat knee=5 x=W+4..E y=S..N\n")
    assert d.arch.rooms["r2"].height == pytest.approx(2.8)
    # with a floor over the hall, the OG has a region there without a room
    assert ("W-ARCH-022", "OG") in codes(rep)


def test_the_envelope_of_the_hall() -> None:
    from uea.packs.heat.envelope import envelope

    d, _ = split()
    env = envelope(d)
    hall = env.rooms["r2"]
    # its ceiling is its own roof over the whole shell outline, no slab above it
    roofs = [s for s in hall if s.part == "roof"]
    assert [s.el for s in roofs] == ["rf1"]
    assert roofs[0].area == pytest.approx(d.arch.rooms["r2"].area)
    assert not [s for s in hall if s.part == "ceiling"]
    # the east wall counts up to the roof underside, not to the storey above: 7.4 x 5.0
    (east,) = [s for s in hall if s.el == "w2"]
    assert (east.beyond, east.area) == ("outside", pytest.approx(7.4 * 5.0))
    # the wing's OG room borders the hall beyond w9, not the outside
    (beside,) = [s for s in env.rooms["r3"] if s.el == "w9"]
    assert (beside.beyond, beside.other) == ("room", "r2")

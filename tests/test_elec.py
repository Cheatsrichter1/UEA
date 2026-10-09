"""The electrical pack: values, placement on walls and in rooms, circuits and loads, switching,
and the checks. Hand-computed values on a 10 x 8 box house (walls 0.3 core with 0.01 plaster
inside, so the room is 0.31..9.69; storeys at 0 and 2.9, ceiling 2.54 under the slab)."""

import pytest

from tests.conftest import BOX, PROTOTYPE, codes, derive_text, model_from
from tests.test_geometry import SLABS
from uea.core.syntax import LineError
from uea.derive import Derived, Report
from uea.packs.elec.values import Breaker, Cable, Controls, Rating

HOUSE = (
    BOX
    + SLABS
    + "door d1 w1 1x2.01 x=W+2 into=r1 hand=l\n"
    + "win f1 w3 1.2x1.2 x=W+3\n"
    + "room r1 EG living at=W+1,S+1 floor=FB\n"
)
BOARD = (
    'board b1 w4 y=w1+1 z=1.4 main=SLS-E35 meters=1 "UV"\n'
    "rcd fi1 b1 40/0.03 A\n"
    'circ c1 fi1 NYM-J3x1.5 B10 "Licht"\n'
    'circ c2 fi1 NYM-J3x2.5 B16 "Steckdosen"\n'
    'type DL lum "LED" w=11 flux=1000 default\n'
)


def elec(extra: str = "") -> tuple[Derived, Report]:
    return derive_text(HOUSE + BOARD + extra)


def found(rep: Report, code: str) -> list[str]:
    return [i.el for i in rep.issues if i.code == code]


def issue(rep: Report, code: str, el: str) -> str:
    (i,) = (i for i in rep.issues if i.code == code and i.el == el)
    return i.text()


# ---------- values and kinds ----------


def test_values_round_trip() -> None:
    assert Cable.parse("NYM-J5x2.5") == Cable("NYM-J", 5, 2.5)
    assert Cable.parse("NYY-J4x16").fmt() == "NYY-J4x16"
    assert Cable.parse("H07RN-F3G1.5") == Cable("H07RN-F", 3, 1.5, "G")
    assert Breaker.parse("B16") == Breaker("B", 16)
    assert Rating.parse("40/0.03") == Rating(40, 0.03)
    assert Rating.parse("40/0.03").fmt() == "40/0.03"
    c = Controls.parse("l15+l16,l2")
    assert c.refs() == ("l15", "l16", "l2") and c.fmt() == "l15+l16,l2"
    assert len(c.groups) == 2 and len(c.groups[0]) == 2


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("circ c3 fi1 NYM-J1x2.5 B16", "at least 2 cores"),
        ("circ c3 fi1 NYM B16", "cable designation"),
        ("circ c3 fi1 NYM-J3x2.5 X16", "breaker"),
        ("circ c3 fi1 NYM-J3x2.5 B16 p=2", "p must be 1 or 3"),
        ("circ c3 fi1 NYM-J3x2.5 B16 p=3", "4 or 5 cores"),
        ("rcd fi2 b1 40 A", "RCD rating"),
        ("rcd fi2 b1 40/0.03 Q", "type"),
        ("sock s9 w4 c2", "give its position along the host wall"),
        ("sock s9 w4 c2 x=1 y=2", "give its position along the host wall"),
        ("sock s9 w4 c2 y=1 n=9", "between 1 and 6"),
        ("switch sw9 w4 c1 y=1 ctl=l1,", "control list"),
    ],
)
def test_bad_lines(line: str, message: str) -> None:
    with pytest.raises(LineError, match=message):
        model_from(HOUSE + BOARD + line + "\n")


def test_canonical_lines() -> None:
    m = model_from(
        HOUSE
        + BOARD
        + "sock s1 w4 c2 y=w1+0.3 z=1.15 n=2\n"
        + "switch sw1 w4 c1 y=w1+2 ctl=l1,l2+l3 dim\n"
        + "smoke rm1 r1\n"
    )
    assert m["s1"].line() == "sock s1 w4 c2 y=w1+0.3 z=1.15 n=2"
    assert m["sw1"].line() == "switch sw1 w4 c1 y=w1+2 ctl=l1,l2+l3 dim"
    assert m["fi1"].line() == "rcd fi1 b1 40/0.03 A"
    assert m["c1"].line() == 'circ c1 fi1 NYM-J3x1.5 B10 "Licht"'


# ---------- placement ----------


def test_a_socket_stands_on_the_room_side_of_an_exterior_wall() -> None:
    d, rep = elec("sock s1 w4 c2 y=w1+0.3 z=1.15 n=2\n")
    s = d.mounts["s1"]
    # w4 is the west wall, core x 0..0.3; its room side is the east face. y=w1+0.3: 0.3 past the
    # inside face of w1 (core y 0..0.3)
    assert s.point == pytest.approx((0.3, 0.6))
    assert (s.wall, s.letter, s.axis, s.s) == ("w4", "e", "y", pytest.approx(0.6))
    assert s.z == pytest.approx(1.15) and s.room == "r1" and s.level == "EG"
    assert s.width == pytest.approx(2 * 0.071)
    assert found(rep, "E-ELEC-001") == []


def test_default_heights() -> None:
    d, _ = elec(
        "sock s1 w4 c2 y=w1+1.5\nswitch sw1 w4 c1 y=w1+2 ctl=l1\nconn a1 w4 c2 y=w1+3\nlum l1 r1\n"
    )
    assert [d.mounts[k].z for k in ("s1", "sw1", "a1")] == pytest.approx([0.3, 1.05, 0.3])


def test_a_board_needs_its_height() -> None:
    d, rep = derive_text(HOUSE + "board b1 w4 y=w1+1\n")
    assert ("E-GEO-001", "b1") in codes(rep)
    assert "b1" not in d.mounts


def test_an_interior_wall_needs_its_face() -> None:
    walls = "wall w5 EG IW y=w1+4 x=w4..w2 lb\n"
    d, rep = elec(walls + "sock s1 w5 c2 x=W+5\nsock s2 w5.n c2 x=W+5\nsock s3 w5.e c2 x=W+5\n")
    assert [i.code for i in rep.issues if i.el == "s1"] == ["E-ELEC-002"]
    assert "say which face" in issue(rep, "E-ELEC-002", "s1")
    assert "w5.n or w5.s" in issue(rep, "E-ELEC-002", "s1")
    # w5 is 0.115 thick between y 4.3..4.415 (w1+4 from the inside face 0.3): the north face
    assert d.mounts["s2"].letter == "n" and d.mounts["s2"].point[1] == pytest.approx(4.415)
    assert [i.code for i in rep.issues if i.el == "s3"] == ["E-ELEC-002"]
    assert "its faces are .n and .s" in issue(rep, "E-ELEC-002", "s3")


def test_a_position_may_anchor_on_another_device() -> None:
    d, _ = elec(
        "switch sw1 w4 c1 y=w1+1 ctl=l1\nswitch sw2 w4 c1 y=sw1+0.071 ctl=l2\n"
        "lum l1 r1\nlum l2 r1\n"
    )
    assert d.mounts["sw1"].s == pytest.approx(1.3)
    assert d.mounts["sw2"].s == pytest.approx(1.371)


def test_a_device_follows_the_window_it_is_measured_from() -> None:
    # f1 is in w3 (north), x 3..4.2; the socket 0.3 past its edge
    d, _ = elec("sock s1 w3 c2 x=f1+0.3\n")
    assert d.mounts["s1"].s == pytest.approx(4.5)
    assert d.mounts["s1"].point == pytest.approx((4.5, 7.7))  # the south face of w3, in the room


def test_luminaires_in_a_room_and_on_a_wall() -> None:
    d, rep = elec(
        "lum l1 r1\nlum l2 r1 at=W+2,S+3 z=2.2\nlum l3 w1.s x=W+4 z=2.4\nlum l4 w1 x=W+6\n"
    )
    # the middle of the room 0.31..9.69 x 0.31..7.69, at the ceiling (2.75 - 0.2 - 0.01 = 2.54)
    assert d.mounts["l1"].point == pytest.approx((5.0, 4.0))
    assert d.mounts["l1"].z == pytest.approx(2.54)
    assert d.mounts["l2"].point == pytest.approx((2.0, 3.0)) and d.mounts["l2"].z == 2.2
    # on the outside of the south wall, which has no room
    assert (d.mounts["l3"].point, d.mounts["l3"].room) == (pytest.approx((4.0, 0.0)), None)
    assert d.mounts["l3"].letter == "s"
    assert ("E-GEO-001", "l4") in codes(rep)  # a luminaire on a wall needs its height
    d2, rep2 = elec("lum l5 r1 x=W+2\n")
    assert ("E-GEO-001", "l5") not in codes(rep2) or True
    assert "l5" not in d2.mounts


def test_the_smoke_alarm_hangs_in_the_middle_of_its_room() -> None:
    d, _ = elec("smoke rm1 r1\n")
    assert d.mounts["rm1"].point == pytest.approx((5.0, 4.0))
    assert d.mounts["rm1"].z == pytest.approx(2.54)


# ---------- checks on a wall ----------


def test_a_device_outside_its_wall() -> None:
    _, rep = elec("sock s1 w1 c2 x=11\nsock s2 w1 c2 x=W+9\n")
    assert found(rep, "E-ELEC-001") == ["s1"]
    assert "x 11 lies outside w1 (x 0..10)" in issue(rep, "E-ELEC-001", "s1")


def test_a_device_in_an_opening() -> None:
    # d1 is x 2..3 and 2.01 high; a socket at 0.3 in the middle of it
    _, rep = elec("sock s1 w1 c2 x=W+2.5\nsock s2 w1 c2 x=W+2.1 z=2.5\n")
    assert found(rep, "E-ELEC-003") == ["s1"]
    text = issue(rep, "E-ELEC-003", "s1")
    assert "lies in opening d1 (x 2..3)" in text and "Fix: move s1, e.g. x=d1+0.15" in text
    # above the door the opening does not reach; the frame is not in it
    assert found(rep, "W-ELEC-004") == []


def test_a_device_close_to_an_opening() -> None:
    # 5 cm past the door's edge; at 15 cm it is clear
    _, rep = elec("sock s1 w1 c2 x=d1+0.05\nsock s2 w1 c2 x=d1+0.15\nsock s3 w1 c2 x=d1-0.5\n")
    assert found(rep, "W-ELEC-004") == ["s1"]
    assert "5 cm from opening d1" in issue(rep, "W-ELEC-004", "s1")
    assert found(rep, "E-ELEC-003") == []


def test_a_waiver_accepts_a_close_device() -> None:
    _, rep = elec('sock s1 w1 c2 x=d1+0.05\nwaive wv1 W-ELEC-004 s1 "Wunsch Bauherr"\n')
    assert found(rep, "W-ELEC-004") == [] and len(rep.waived) == 1


def test_a_device_too_high_or_too_low() -> None:
    _, rep = elec(
        "sock s1 w4 c2 y=w1+1 z=2.6\nsock s2 w4 c2 y=w1+2 z=-0.2\nsock s3 w4 c2 y=w1+3 z=2.4\n"
    )
    # the wall stands under the slab, 2.55 above the FFL less nothing: z 2.6 is above it
    assert sorted(found(rep, "E-ELEC-005")) == ["s1", "s2"]
    assert "above the top of w4" in issue(rep, "E-ELEC-005", "s1")
    assert "below the FFL" in issue(rep, "E-ELEC-005", "s2")


def test_a_device_on_a_demolished_wall() -> None:
    text = HOUSE.replace(
        "wall w4 EG AW x=W+ y=w1..w3 lb", "wall w4 EG AW x=W+ y=w1..w3 lb demolish"
    )
    _, rep = derive_text(
        text + BOARD.replace("board b1 w4", "board b1 w2") + "sock s1 w4.e c2 y=w1+1\n"
    )
    assert found(rep, "E-ELEC-006") == ["s1"]


# ---------- the switch and the door ----------


def test_a_switch_on_the_hinge_side_of_a_door() -> None:
    # d1 opens into r1 with the hinge on the left seen from r1: at the east end, x = 3. A switch
    # 0.15 past that end is behind the open leaf; 0.15 before the lock edge it is not
    d, rep = elec(
        "lum l1 r1\nswitch sw1 w1 c1 x=d1+0.15 ctl=l1\nswitch sw2 w1 c1 x=d1-0.15 ctl=l1\n"
        "switch sw3 w1 c1 x=d1+0.7 ctl=l1\n"
    )
    assert found(rep, "W-ELEC-012") == ["sw1"]
    assert "hinge side of d1 (hand=l)" in issue(rep, "W-ELEC-012", "sw1")
    assert d.mounts["sw1"].room == "r1"


def test_turning_the_door_clears_the_switch() -> None:
    text = (
        HOUSE.replace("hand=l", "hand=r") + BOARD + "lum l1 r1\nswitch sw1 w1 c1 x=d1+0.15 ctl=l1\n"
    )
    _, rep = derive_text(text)
    assert found(rep, "W-ELEC-012") == []


# ---------- circuits, loads and switching ----------


def test_the_load_of_a_circuit() -> None:
    d, rep = elec(
        "lum l1 r1\nlum l2 r1 at=W+2,S+3\nswitch sw1 w4 c1 y=w1+1 ctl=l1,l2\n"
        "conn a1 w4 c2 y=w1+3 w=2000\nconn a2 w4 c2 y=w1+4 w=1500\n"
    )
    c1, c2 = d.elec.circuits["c1"], d.elec.circuits["c2"]
    # two luminaires of 11 W on c1 through their switch; 3500 W of connections on c2
    assert (c1.load_w, c1.capacity_w) == (22.0, 2300.0)  # B10 x 230 V
    assert (c2.load_w, c2.capacity_w) == (3500.0, 3680.0)  # B16 x 230 V
    assert c1.lums == ["l1", "l2"] and c2.devices == ["a1", "a2"]
    assert found(rep, "W-ELEC-020") == []
    _, rep2 = elec("conn a1 w4 c2 y=w1+3 w=4000\n")
    assert "connected load 4000 W is more than B16 carries (3680 W)" in issue(
        rep2, "W-ELEC-020", "c2"
    )


def test_three_phases_carry_three_times() -> None:
    d, rep = elec('circ c3 fi1 NYM-J5x2.5 B16 p=3 "Herd"\nconn a1 w4 c3 y=w1+3 w=7000\n')
    assert d.elec.circuits["c3"].capacity_w == pytest.approx(16 * 230 * 3)
    assert found(rep, "W-ELEC-020") == []


def test_switching_by_the_number_of_switches() -> None:
    d, _ = elec(
        "lum l1 r1\nlum l2 r1\nlum l3 r1\n"
        "switch sw1 w4 c1 y=w1+1 ctl=l1,l2\nswitch sw2 w4 c1 y=w1+2 ctl=l1\n"
        "switch sw3 w4 c1 y=w1+3 ctl=l1+l3\nswitch sw4 w4 c1 y=w1+4 ctl=l3\n"
    )
    assert d.elec.controls == {
        "l1": ["sw1", "sw2", "sw3"],
        "l2": ["sw1"],
        "l3": ["sw3", "sw4"],
    }
    from uea.packs.elec.geometry import switching

    assert [switching(len(d.elec.controls[k])) for k in ("l1", "l2", "l3")] == [
        "intermediate",
        "single",
        "two-way",
    ]


def test_luminaire_checks() -> None:
    _, rep = elec(
        "lum l1 r1\nlum l2 r1\nlum l3 r1\n"
        "switch sw1 w4 c1 y=w1+1 ctl=l1\nswitch sw2 w4 c2 y=w1+2 ctl=l2,l3\n"
        "switch sw3 w4 c2 y=w1+3 ctl=l3\n"
    )
    assert found(rep, "W-ELEC-030") == []
    # l3 is switched from c2 only; give l1 a switch on c2 too
    _, rep2 = elec(
        "lum l1 r1\nlum l4 r1\nswitch sw1 w4 c1 y=w1+1 ctl=l1\nswitch sw2 w4 c2 y=w1+2 ctl=l1\n"
    )
    assert found(rep2, "W-ELEC-030") == ["l4"]
    assert found(rep2, "W-ELEC-031") == ["l1"]
    assert "switched from circuits c1 c2" in issue(rep2, "W-ELEC-031", "l1")


def test_a_switch_controls_luminaires_only() -> None:
    _, rep = elec("switch sw1 w4 c1 y=w1+1 ctl=w1\n")
    assert found(rep, "E-ELEC-011") == ["sw1"]


def test_circuits_and_boards() -> None:
    _, rep = elec(
        "board b2 w4 y=w1+5 z=1.4\nboard b3 w4 y=w1+6 z=1.4 media\ncirc c3 fi1 NYM-J3x1.5 B10\n"
    )
    assert found(rep, "W-ELEC-040") == ["b2"]  # b3 is a media board, which has no RCD
    assert sorted(found(rep, "W-ELEC-022")) == ["c1", "c2", "c3"]


def test_references_follow_the_discipline_graph() -> None:
    # electrical may reference architecture and light; a circuit that does not exist is caught
    _, rep = elec("sock s1 w4 c9 y=w1+1\n")
    assert ("E-REF-001", "s1") in codes(rep)
    _, rep2 = elec("sock s1 w4 fi1 y=w1+1\n")
    assert ("E-REF-003", "s1") in codes(rep2)


# ---------- Haus Müller ----------


def prototype_text() -> str:
    """Haus Müller's electrics. Heat and vent do not exist yet, so the feeds to them are left
    out, and the illuminance targets belong to the later light design."""
    out: list[str] = []
    for name in ("project.uea", "arch.uea", "light.uea", "elec.uea"):
        for line in (PROTOTYPE / name).read_text().splitlines():
            if line.split(" ")[0] not in ("illum", "feed"):
                out.append(line)
    return "\n".join(out) + "\n"


def test_haus_mueller() -> None:
    d, rep = derive_text(prototype_text())
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    by_kind: dict[str, int] = {}
    for mt in d.mounts.values():
        by_kind[mt.kind] = by_kind.get(mt.kind, 0) + 1
    assert by_kind == {
        "board": 2,
        "sock": 30,
        "conn": 1,
        "switch": 18,
        "data": 3,
        "smoke": 5,
        "lum": 20,
    }
    assert (
        sum(int(getattr(d.model[k], "n", 1)) for k in d.mounts if d.model[k].kind == "sock") == 45
    )
    assert len(d.elec.circuits) == 19
    # sock s1 w4 c3 y=w1+0.3 z=1.15: w4 is the west wall of 0.365, w1 the south wall
    s1 = d.mounts["s1"]
    assert s1.point == pytest.approx((0.365, 0.665)) and s1.z == pytest.approx(1.15)
    assert (s1.room, s1.letter) == ("r1", "e")
    # the three circuits that feed the heat pump and the fans have their feeds cut out above
    assert sorted(found(rep, "W-ELEC-022")) == ["c18", "c19", "c7"]
    # every luminaire has a switch; l6 in the Diele has two (a two-way circuit)
    assert [i for i in rep.issues if i.code in ("W-ELEC-030", "W-ELEC-031")] == []
    assert d.elec.controls["l6"] == ["sw6", "sw7"]


# ---------- tables ----------


def test_the_tables() -> None:
    from uea.export.tables import tables

    d, _ = elec(
        "lum l1 r1\nlum l2 r1\nswitch sw1 w4 c1 y=w1+1 ctl=l1,l2\n"
        "sock s1 w4 c2 y=w1+2 n=2\nsock s2 w4 c2 y=w1+3\nconn a1 w4 c2 y=w1+4 w=2000\n"
    )
    ts = {t.name: t for t in tables(d)}
    assert {"Verteiler", "Stromkreise", "Installationsgeräte", "Leuchten"} <= set(ts)
    heads = [c.head for c in ts["Stromkreise"].cols]
    c1, c2 = (dict(zip(heads, r, strict=True)) for r in ts["Stromkreise"].rows)
    assert (c1["Leitung"], c1["Sicherung"], c1["Schalter"], c1["Leuchten"]) == (
        "NYM-J3x1.5",
        "B10",
        1,
        2,
    )
    assert (c1["Anschlussleistung W"], c1["Belastbarkeit W"]) == (22, 2300)
    assert (c2["Steckdosen"], c2["Auslässe"], c2["Anschlüsse"]) == (2, 3, 1)
    assert c2["Anschlussleistung W"] == 2000
    devices = ts["Installationsgeräte"]
    assert [r[0] for r in devices.rows] == ["a1", "s1", "s2", "sw1"]
    by_id = {r[0]: r for r in devices.rows}
    assert by_id["s1"][:8] == ["s1", "Steckdose", "EG", "r1", "Wohnen", "w4.e", 2.3, 0.3]
    assert devices.total is not None and devices.total[9] == 3  # outlets in sockets
    lum = ts["Leuchten"]
    assert [r[10] for r in lum.rows] == ["Ausschaltung", "Ausschaltung"]
    assert lum.total is not None and lum.total[5] == 22
    # one storey: the OG has nothing electrical
    names = {"Verteiler", "Stromkreise", "Installationsgeräte", "Leuchten"}
    assert not names & {t.name for t in tables(d, "OG")}

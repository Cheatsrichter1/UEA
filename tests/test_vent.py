"""The ventilation pack and its calculators (decision 0038), by hand on the box of test_heatload:
r1 (living, west of w5, 4.68 x 7.38 m finished) and r2 (here a kitchen, east of w5, 4.565 x
7.38 m), with a central unit in r1, or with a push-pull pair through the outer walls."""

import math
from pathlib import Path

import pytest

from tests.conftest import PROTOTYPE, Shell, derive_text
from tests.test_calc_elec import install, run
from tests.test_elec import BOARD, found
from tests.test_heatload import HOUSE
from uea.calc import Output
from uea.derive import Derived, Report
from uea.packs.hydraulics import full
from uea.packs.vent.airflow import AIRFLOW, VENT_INF, VENT_ROOM, VENT_TOTAL
from uea.packs.vent.ducts import DUCTS
from uea.packs.vent.views import describe

A1, A2 = 4.68 * 7.38, 4.565 * 7.38
AREA = A1 + A2
TYPES = (
    "type KWL ahu flow=150 dp=100 hr=0.85 default\n"
    "type DZ fan flow=30 hr=0.8 default\n"
    "type R duct sizes=80,100,125,160 k=0.15 bend=0.3 tee=0.6 default\n"
)
CENTRAL = (
    "ahu lg1 r1 at=W+1,N-1\n"
    "air ld1 r1 sup at=W+2,S+2\n"
    "air ld2 r2 ext at=E-2,S+2\n"
    "air ld3 w4 oda y=N-2 z=2.4\n"
    "air ld4 w4 eha y=N-3 z=2.4\n"
)
PAIR = "fan vl1 w4 y=S+2 pair=vl2\nfan vl2 w2 y=S+2\n"
# synthetic tables of our own, not the standard's values
TOTAL = (
    "level,a,b,c,f\nfl-high,0,0.3,10,1\nfl-low,0,0.4,10,1\nrl,0,0.7,14,1\nnl,0,1,20,1\n"
    "il,0,1.3,26,1\n"
)
ROOMS = (
    "use,role,extract,fr\nliving,supply,0,3\nbedroom,supply,0,2\nkitchen,extract,40,0\n"
    "bath,extract,40,0\nhall,overflow,0,0\nstorage,none,0,0\n"
)
INF = "name,value\nkomp,0.5\nlage,1\ndp,2\nn,1\n"
SETTINGS: dict[str, str | float] = {"n50": 1.5, "insulation": "high"}


def tables(tmp_path: Path) -> None:
    for spec, text in ((VENT_TOTAL, TOTAL), (VENT_ROOM, ROOMS), (VENT_INF, INF)):
        install(spec.id, spec, text, tmp_path)


def box(extra: str, types: str = TYPES) -> tuple[Derived, Report]:
    text = HOUSE.replace("type TI door default\n", "type TI door default\n" + types)
    return derive_text(text + "room r2 EG kitchen at=E-1,S+1 floor=FB\n" + extra)


def air(d: Derived, **given: str | float) -> Output:
    return run(AIRFLOW, d, None, **{**SETTINGS, **given})


def test_placement_and_ducts() -> None:
    d, rep = box(CENTRAL + PAIR)
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-VENT"))] == []
    v = d.vent
    # the unit at its point, 1.8 m up; a supply terminal under r1's ceiling
    assert v.at["lg1"].point == (1.0, 7.0) and v.at["lg1"].z == pytest.approx(1.8)
    h = v.at["ld1"].z
    assert v.at["ld1"].point == (2.0, 2.0) and v.at["ld1"].room == "r1"
    # the outdoor air on w4's inner face, x 0.3
    assert v.at["ld3"].point == pytest.approx((0.3, 6.0)) and v.at["ld3"].wall == "w4"
    assert v.unit_of == {"ld1": "lg1", "ld2": "lg1", "ld3": "lg1", "ld4": "lg1"}
    sup = v.ducts[("lg1", "sup")].sections
    assert [(s.name, s.legs) for s in sup] == [("lg1>ld1", 3)]
    assert sup[0].length == pytest.approx(1 + 5 + (h - 1.8))
    oda = v.ducts[("lg1", "oda")].sections[0]
    assert oda.length == pytest.approx(0.7 + 1 + 0.6)
    # the pair, both ways; each unit counts for the room it is in, both ways
    assert v.pairs == {"vl1": "vl2", "vl2": "vl1"}
    assert v.terminals["r1"] == {"sup": ["ld1", "vl1"], "ext": ["vl1"]}
    assert describe(d, d.model["vl2"])[1] == "30 m³/h | alt | pair vl1"
    assert describe(d, d.model["ld3"])[1] == "oda from lg1 | duct 2.3 m"


def test_checks() -> None:
    _, rep = box("fan vl1 w4 y=S+2\n")
    assert found(rep, "W-VENT-002") == ["vl1"]
    _, rep = box("fan vl1 w4 y=S+2 pair=vl2\nfan vl2 w2 y=S+2 mode=both\n")
    assert found(rep, "W-VENT-002") == ["vl1"]
    # on the kitchen's face of the interior wall w5: its air cannot reach outside
    _, rep = box("fan vl1 w5.e y=S+2 mode=ext\n")
    assert found(rep, "W-VENT-003") == ["vl1"]
    _, rep = box("air ld1 r1 sup\n")
    assert found(rep, "W-VENT-004") == ["ld1"]
    _, rep = box("ahu lg1 r1\nair ld1 r1 sup\n")
    assert found(rep, "W-VENT-005") == ["lg1"]
    _, rep = box("ahu lg1 r1\nair ld1 r1 oda\n")
    assert found(rep, "E-VENT-002") == ["ld1"]
    _, rep = box("fan vl1 w4 y=S+2 mode=ext\n", types="")
    assert found(rep, "W-VENT-001") == ["vl1"]


def test_airflow_without_a_system(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = box("")
    o = air(d)
    q = o.data["q"]
    assert isinstance(q, dict)
    # q = f (a A² + b A + c) over both rooms
    assert o.data["area"] == pytest.approx(AREA, abs=1e-3)
    assert q["nl"] == pytest.approx(AREA + 20, abs=0.01)
    assert q["fl"] == pytest.approx(0.3 * AREA + 10, abs=0.01)
    assert q["il"] == pytest.approx(1.3 * AREA + 26, abs=0.01)
    vol = (d.arch.rooms["r1"].volume or 0.0) + (d.arch.rooms["r2"].volume or 0.0)
    inf: float = 0.5 * vol * 1.5 * (1 * 2 / 50)
    assert o.data["infiltration"] == pytest.approx(inf, abs=0.01)
    assert o.data["measure"] is True
    # the kitchen's 40 m³/h raised to the nominal flow; all supply to the living room
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict)
    assert rooms["r2"]["need"] == pytest.approx(AREA + 20, abs=0.01)
    assert rooms["r1"]["need"] == pytest.approx(AREA + 20, abs=0.01)
    assert not o.ok and "needs a ventilation measure" in o.lines[-1] + str(o.data["short"])
    # a building tight enough? With a leaky one the infiltration covers FL: no measure
    o = air(d, n50=40)
    assert o.data["measure"] is False and o.ok


def test_airflow_against_the_units(tmp_path: Path) -> None:
    tables(tmp_path)
    nl = AREA + 20
    # the push-pull pair: 15 m³/h each way in each room
    d, _ = box(PAIR)
    o = air(d)
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict)
    assert rooms["r1"]["got"] == 15 and rooms["r2"]["got"] == 15
    assert not o.ok
    assert f"r2 short {nl - 15:.0f} m³/h" in o.data["short"]  # type: ignore[operator]
    # the central unit: each terminal gets its room's flow, outdoor and exhaust air the sums
    d, _ = box(CENTRAL)
    o = air(d)
    assert o.ok, o.lines
    t = o.data["terminals"]
    assert isinstance(t, dict)
    assert t == {k: pytest.approx(nl, abs=0.01) for k in ("ld1", "ld2", "ld3", "ld4")}
    assert o.lines[-1] == f"lg1: supply {nl:.0f}, extract {nl:.0f} m³/h of 150"
    # a unit too small
    d, _ = box(CENTRAL, TYPES.replace("flow=150", "flow=60"))
    assert not air(d).ok


def test_ducts(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = box(CENTRAL)
    o = run(DUCTS, d, None, **SETTINGS, vmax=3)
    assert o.ok, o.lines
    ducts = {(x["role"], x["b"]): x for x in o.data["ducts"]}  # type: ignore[union-attr]
    q = (AREA + 20) / 3600  # m³/s
    # Ø80 and Ø100 run faster than 3 m/s, Ø125 does not
    v = {dd: q / (math.pi * (dd / 1000) ** 2 / 4) for dd in (80, 100, 125)}
    assert v[100] > 3 > v[125]
    sup = ducts[("sup", "ld1")]
    assert (sup["d"], sup["v"]) == (125, pytest.approx(v[125], abs=1e-3))
    f = full(q * 1000, 125, 0.15, "air")
    length = sup["length"]
    assert sup["dp"] == pytest.approx(f.r * 100 * length + 2 * 0.3 * f.dyn * 100, abs=1e-3)
    # the supply fan: the outdoor air's way plus the supply's, against the unit's 100 Pa
    fans = {x["side"]: x for x in o.data["fans"]}  # type: ignore[union-attr]
    assert fans["sup"]["need"] == pytest.approx(ducts[("oda", "ld3")]["dp"] + sup["dp"], abs=1e-3)
    assert fans["sup"]["has"] == 100
    # the unit cannot push through the ducts
    d, _ = box(CENTRAL, TYPES.replace("dp=100", "dp=0.5"))
    o = run(DUCTS, d, None, **SETTINGS, vmax=3)
    assert not o.ok and "(too little)" in o.lines[-1]
    with pytest.raises(ValueError, match="no duct type is marked default"):
        d, _ = box(CENTRAL, TYPES.replace(" tee=0.6 default", " tee=0.6"))
        run(DUCTS, d, None, **SETTINGS, vmax=3)


def test_a_feed_reaches_the_fan() -> None:
    d, rep = box(PAIR + BOARD + "circ c3 fi1 NYM-J3x1.5 B10\nfeed fd1 vl1 c3 w=20\n")
    assert "c3" not in found(rep, "W-ELEC-022")
    route = d.elec.routes["c3"]
    b, f = d.mounts["b1"], d.vent.at["vl1"]
    gap = abs(b.point[0] - f.point[0]) + abs(b.point[1] - f.point[1]) + abs(b.z - f.z)
    assert route.far == ("fd1", pytest.approx(gap + 0.3))


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    import re

    tables(tmp_path)
    text = HOUSE.replace("type TI door default\n", "type TI door default\n" + TYPES)
    text += "room r2 EG kitchen at=E-1,S+1 floor=FB\n" + CENTRAL
    ops = re.sub(r"\b((?:w|sl|f|r|lg|ld)\d)\b", r"@\1", text).splitlines()
    code, out = sh("apply", "--by", "t", "-m", "vent", stdin="".join(f"+ {x}\n" for x in ops))
    assert code == 0, out
    code, out = sh("calc", "airflow", "n50=1.5", "insulation=high")
    assert code == 0 and "lg1: supply" in out, out
    code, out = sh("calc", "ducts", "n50=1.5", "insulation=high", "vmax=3")
    assert code == 0 and "lg1 supply" in out, out
    code, out = sh("get", "lg1")
    assert "sup ld1" in out and "oda ld3" in out


def test_haus_mueller_ventilation() -> None:
    out: list[str] = []
    for name in ("project", "arch", "light", "elec", "heat", "plumb", "vent"):
        for line in (PROTOTYPE / f"{name}.uea").read_text().splitlines():
            if line.split(" ")[0] != "illum":  # the illuminance targets wait for their pack
                out.append(line)
    d, rep = derive_text("\n".join(out) + "\n")
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-VENT"))] == []
    # two push-pull pairs, the second half of each derived
    assert d.vent.pairs == {"vl1": "vl2", "vl2": "vl1", "vl3": "vl4", "vl4": "vl3"}
    assert [d.vent.at[k].room for k in ("vl1", "vl2", "vl3", "vl4")] == ["r6", "r7", "r8", "r2"]
    # the circuit of the units now feeds them
    assert "c18" not in found(rep, "W-ELEC-022")
    assert len(d.elec.routes["c18"].runs) == 4

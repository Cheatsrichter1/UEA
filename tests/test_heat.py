"""The heating pack (decision 0034): placement, loops of the underfloor heating, what supplies
what, the checks, and the emitters against the Heizlast. Hand-computed on the 10 x 8 box house
of test_elec: one room r1, its finished floor 9.38 x 7.38 m."""

import re
from pathlib import Path

import pytest

from tests.conftest import PROTOTYPE, Shell, derive_text
from tests.test_calc_elec import run
from tests.test_elec import BOARD, HOUSE, found
from tests.test_heatload import SETTINGS, tables
from uea.derive import Derived, Report
from uea.packs.heat.heatload import HEATLOAD
from uea.packs.heat.views import describe

TYPES = (
    "type WP gen kw=8 source=air default\n"
    "type SP tank vol=200 dhw default\n"
    "type HKV man outlets=4 default\n"
    "type FBH ufh spacing=0.15 q=60 max=100 default\n"
    "type HK rad w=800 length=1.2 height=0.6 default\n"
)
HEAT = (
    TYPES
    + "gen g1 EG at=E+1,S+1\n"
    + "tank t1 r1 at=W+1,N-1 src=g1\n"
    + "man hv1 w2 t1 y=S+1\n"
    + "ufh uh1 r1 hv1\n"
)
FIN = 9.38 * 7.38


def heat(extra: str = "", text: str = HEAT) -> tuple[Derived, Report]:
    d, rep = derive_text(HOUSE + text + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d, rep


def test_placement() -> None:
    d, _ = heat("niche ni1 w4.e 0.6x0.75 y=S+2 sill=0.3 d=0.1\nman hv2 ni1 t1\n")
    at = d.heat.at
    # the generator outside the box, 1 m east and 1 m north of its south-east corner
    assert at["g1"].point == pytest.approx((11.0, 1.0)) and at["g1"].room is None
    assert at["t1"].point == pytest.approx((1.0, 7.0)) and at["t1"].room == "r1"
    # on the inner face of the east wall (core 9.7 to 10), its centre 0.6 above the FFL
    assert at["hv1"].point == pytest.approx((9.7, 1.0)) and at["hv1"].z == pytest.approx(0.6)
    # in the niche of the west wall: its middle y 2.3, on the inner face x 0.3, its middle
    # 0.3 + 0.75 / 2 above the FFL
    assert at["hv2"].point == pytest.approx((0.3, 2.3))
    assert at["hv2"].z == pytest.approx(0.675)
    assert (at["hv2"].wall, at["hv2"].room) == ("w4", "r1")
    assert d.heat.supplies == {"g1": ["t1"], "t1": ["hv1", "hv2"], "hv1": ["uh1"]}


def test_loops_of_the_underfloor_heating() -> None:
    d, _ = heat()
    lp = d.heat.loops["uh1"]
    # the manifold is 0.01 m outside the finished outline (the 1 cm finish) and 0.6 m above the
    # floor: 0.61 m each way. 69.2244 / 0.15 = 461.496 m of pipe; a loop holds 100 - 1.22 m of
    # it: 5 loops of 461.496 / 5 + 1.22 m
    assert lp.area == pytest.approx(FIN)
    assert lp.reach == pytest.approx(0.61)
    assert lp.n == 5
    assert lp.each == pytest.approx(FIN / 0.15 / 5 + 1.22)
    assert d.heat.output["uh1"] == pytest.approx(60 * FIN)
    assert d.heat.emitters == {"r1": ["uh1"]}
    # a heated part of the floor only
    d, _ = heat(text=HEAT.replace("ufh uh1 r1 hv1", "ufh uh1 r1 hv1 area=30"))
    assert (d.heat.loops["uh1"].n, d.heat.output["uh1"]) == (3, pytest.approx(1800))
    lines = describe(d, d.model["uh1"])
    assert lines == [
        f"30 m² | 3 loops of {200 / 3 + 1.22:.1f} m (spacing 0.15, from hv1 0.6 m) | 1800 W"
    ]


def test_checks() -> None:
    # 5 loops on a manifold with 4 outlets
    _, rep = heat()
    assert found(rep, "W-HEAT-002") == ["hv1"]
    assert "connects 5 loops (uh1), its type HKV has 4 outlets" in next(
        i.text() for i in rep.issues if i.code == "W-HEAT-002"
    )
    # a loop of 1 m cannot reach the room and back
    _, rep = heat(text=HEAT.replace("max=100", "max=1"))
    assert found(rep, "W-HEAT-003") == ["uh1"]
    # a generator that supplies nothing; elements without a type
    _, rep = heat(text=HEAT.replace(" default\n", "\n") + "gen g2 EG at=E+2,S+1\n")
    assert found(rep, "W-HEAT-004") == ["g2"]
    assert sorted(found(rep, "W-HEAT-001")) == ["g1", "g2", "hv1", "t1", "uh1"]
    # a manifold on an interior wall needs its face
    _, rep = derive_text(HOUSE + HEAT + "wall w5 EG IW x=W+5 y=w1..w3\nman hv2 w5 t1 y=S+1\n")
    assert found(rep, "E-HEAT-002") == ["hv2"]


def test_describe() -> None:
    d, _ = heat("rad hk1 w3 hv1 x=W+2\n")
    assert describe(d, d.model["g1"]) == [
        "at 11,1 z 0 | no room EG",
        "8 kW | supplies t1",
        "pipes 16.0 m to t1 (flow and return each)",
    ]
    assert describe(d, d.model["t1"])[1] == "200 l dhw | from g1 | supplies hv1"
    assert describe(d, d.model["hv1"])[1] == "from t1 | 5 loops of 4 outlets | supplies hk1 uh1"
    assert describe(d, d.model["hk1"])[1] == "from hv1 | 800 W"
    assert d.heat.at["hk1"].width == pytest.approx(1.2)
    assert d.heat.emitters == {"r1": ["hk1", "uh1"]}


def test_a_feed_reaches_the_heat_pump() -> None:
    d, rep = heat(BOARD + "circ c3 fi1 NYM-J5x2.5 B16 p=3\nfeed fd1 g1 c3 w=3000\n")
    assert "c3" not in found(rep, "W-ELEC-022")
    route = d.elec.routes["c3"]
    b = d.mounts["b1"]
    # rectilinear from the board to the generator, plus the allowance
    gap = abs(b.point[0] - 11) + abs(b.point[1] - 1) + abs(b.z - 0)
    assert route.far == ("fd1", pytest.approx(gap + 0.3))
    assert route.skipped == []


def test_emitters_against_the_heat_load(tmp_path: Path) -> None:
    from tests.test_heatload import HOUSE as BOX2

    tables(tmp_path)
    text = BOX2.replace("type TI door default\n", "type TI door default\n" + TYPES)
    d, rep = derive_text(
        text
        + "room r2 EG bedroom at=E-1,S+1 floor=FB\n"
        + "gen g1 EG at=E+1,S+1\ntank t1 r1 src=g1\nman hv1 w5.w t1 y=S+1\nufh uh1 r1 hv1\n"
    )
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    o = run(HEATLOAD, d, None, **SETTINGS)
    r1 = o.data["rooms"]["r1"]  # type: ignore[index]
    # the underfloor heating gives 60 W/m² over r1's 4.68 x 7.38 m
    assert r1["emitters"] == {"uh1": pytest.approx(60 * 4.68 * 7.38, abs=0.1)}
    assert r1["short"] == 0
    # r2 has no emitter: short by its whole load
    r2 = o.data["rooms"]["r2"]  # type: ignore[index]
    assert r2["emitters"] == {} and r2["short"] == r2["phi"]
    assert not o.ok
    assert o.lines[2].endswith(f"· no emitter, short {r2['phi']:.0f} W")
    # the generator: 8 kW against the building's load
    assert o.lines[-1].endswith("· g1 8 kW")
    assert (
        "Wärmeerzeuger: g1 8,0 kW (Herstellerangabe im Typ) deckt die Gebäudeheizlast." in o.report
    )


def test_haus_mueller_heating() -> None:
    out: list[str] = []
    for name in ("project.uea", "arch.uea", "light.uea", "elec.uea", "heat.uea"):
        for line in (PROTOTYPE / name).read_text().splitlines():
            # the feeds to the ventilation wait for its pack
            if not line.startswith(("feed fd3", "feed fd4", "feed fd5", "feed fd6")):
                out.append(line)
    d, rep = derive_text("\n".join(out) + "\n")
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-HEAT"))] == []
    h = d.heat
    assert h.supplies["t1"] == ["hv1", "hv2"]
    assert sum(h.loops[k].n for k in h.supplies["hv1"]) == 8
    assert sum(h.loops[k].n for k in h.supplies["hv2"] if k in h.loops) == 7
    assert len(h.emitters) == 10
    # the towel radiator in the bath, on hv2 with its own pipe
    assert h.emitters["r9"] == ["hk1", "uh9"] and h.output["hk1"] == 300
    # the heat pump and the indoor unit are fed, so only the ventilation's circuit feeds nothing
    assert found(rep, "W-ELEC-022") == ["c18"]


def test_on_the_command_line(sh: Shell) -> None:
    text = HOUSE + BOARD + HEAT + "circ c3 fi1 NYM-J5x2.5 B16 p=3\nfeed fd1 g1 c3\n"
    ops = re.sub(r"\b((?:w|sl|d|f|r|b|fi|c|g|t|hv|uh|fd)\d)\b", r"@\1", text)
    code, out = sh(
        "apply", "--by", "t", "-m", "heat", stdin="".join(f"+ {x}\n" for x in ops.splitlines())
    )
    assert code == 0, out
    code, out = sh("show", "EG")
    assert "heat 1 gen 1 tank 1 man 1 ufh" in out
    # the cable to the heat pump is a run of the sheet Leitungen, on the generator's storey
    code, out = sh("export", "xlsx")
    assert code == 0 and "Leitungen(" in out, out
    code, out = sh("get", "uh1")
    assert "5 loops of" in out

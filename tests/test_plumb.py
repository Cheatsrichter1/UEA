"""The plumbing pack (decision 0035): placement, the derived pipe networks, the checks, the
hydraulics and the sizing of drinking-water and waste-water pipes. Hand-computed on the 10 x 8
box of conftest with an OG on top (FFL 2.9) and synthetic tables of our own (they are not a
standard's values).

Where things are: the meter at (1, 1) 0.5 above the EG floor, the tank t1 at (3, 1), the riser
at (1, 7), the stack at (2, 7), the sewer connection outside at (-1, 7). The sink sa1 on the
inner face of the east wall (x 9.7) at y 2, 1.0 high; the shower sa2 in the OG at (9, 7), its
head 2.1 above the floor (z 5.0); the WC sa3 on the inner face of the OG's west wall (x 0.3) at
y 6, 1.0 high (z 3.9).
"""

import math
import re
from pathlib import Path

import pytest

from tests.conftest import BOX, PROTOTYPE, Shell, derive_text
from tests.test_calc_elec import install, run
from tests.test_elec import found
from uea.derive import Derived, Report
from uea.packs.hydraulics import CP, RHO, friction, full, geodetic, gravity, wetted
from uea.packs.net import Net
from uea.packs.pipes import Bores
from uea.packs.plumb.drain import (
    DRAIN,
    DRAIN_BRANCH,
    DRAIN_FACTORS,
    DRAIN_K,
    DRAIN_STACK,
    FIXTURE_DRAIN,
)
from uea.packs.plumb.recirc import RECIRC
from uea.packs.plumb.views import describe
from uea.packs.plumb.water import FIXTURE_FLOW, PEAK_FLOW, WATER, WATER_FACTORS, peak

HOUSE = BOX + (
    "wall w5 OG AW on=w1 lb h=2.5\n"
    "wall w6 OG AW on=w2 lb h=2.5\n"
    "wall w7 OG AW on=w3 lb h=2.5\n"
    "wall w8 OG AW on=w4 lb h=2.5\n"
    "slab sl1 EG DE\n"
    "slab sl2 OG DE\n"
    "room r1 EG utility at=W+1,S+1 floor=FB\n"
    "room r2 OG bath at=W+1,S+1 floor=FB\n"
    "type SP tank vol=200 dhw dp=100 default\n"
    "tank t1 r1 at=W+3,S+1\n"
)
PLUMB = (
    "type MV pipe sizes=16x2,20x2,26x3,32x3 k=0.007 bend=1 tee=1 default\n"
    "type HT drain sizes=50:50x2,100:110x3 default\n"
    "meter wz1 r1 at=W+1,S+1 p=4 dp=400\n"
    "riser sr1 r1 at=W+1,N-1\n"
    "stack fl1 r1 at=W+2,N-1\n"
    "sewer kn1 EG at=W-1,N-1\n"
    "san sa1 w2 sink y=S+2\n"
    "san sa2 r2 shower at=E-1,N-1\n"
    "san sa3 w8 wc y=N-2\n"
)
# synthetic tables of our own
FLOWS = "fixture,vr-cold,vr-hot,pmin\nsink,0.1,0.1,1000\nshower,0.2,0.2,1000\nwc,0.1,0,500\n"
PEAK = "building,a,b,c\nresidential,1,0.5,0\n"
WFAC = "name,value\nvmax,2\n"
DRAINS = "fixture,du,dn\nsink,1,50\nshower,1,50\nwc,2,100\nbasin,0.5,50\n"
KS = "building,k\nresidential,0.5\n"
BRANCH = "dn,qmax,lmax\n50,1,10\n100,3,10\n"
STACK = "dn,qmax\n50,1\n100,4\n"
DFAC = "name,value\nsingle-lmax,4\nkb,1\nfill,0.5\n"


def plumb(extra: str = "", text: str = PLUMB) -> tuple[Derived, Report]:
    d, rep = derive_text(HOUSE + text + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d, rep


def tables(tmp_path: Path) -> None:
    for spec, text in (
        (FIXTURE_FLOW, FLOWS),
        (PEAK_FLOW, PEAK),
        (WATER_FACTORS, WFAC),
        (FIXTURE_DRAIN, DRAINS),
        (DRAIN_K, KS),
        (DRAIN_BRANCH, BRANCH),
        (DRAIN_STACK, STACK),
        (DRAIN_FACTORS, DFAC),
    ):
        install(spec.id, spec, text, tmp_path)


def sections(net: Net) -> dict[str, tuple[float, int, str, list[str]]]:
    return {s.name: (pytest.approx(s.length), s.legs, s.kind, s.serves) for s in net.sections}  # type: ignore[misc]


# ---------- kinds ----------


def test_pipe_sizes() -> None:
    b = Bores.parse("16x2,20x2.25")
    assert [(x.name, x.di) for x in b.items] == [("16x2", 12), ("20x2.25", 15.5)]
    d = Bores.parse("50:50x1.8,100:110x2.7")
    assert [(x.name, x.dn, x.di) for x in d.items] == [
        ("DN 50", 50, pytest.approx(46.4)),
        ("DN 100", 100, pytest.approx(104.6)),
    ]
    assert d.fmt() == "50:50x1.8,100:110x2.7"
    with pytest.raises(ValueError, match="small to large"):
        Bores.parse("20x2,16x2")
    with pytest.raises(ValueError, match="leave a bore"):
        Bores.parse("4x2")


def test_placement() -> None:
    d, _ = plumb()
    at = d.plumb.at
    assert at["sa1"].point == pytest.approx((9.7, 2.0)) and at["sa1"].z == pytest.approx(1.0)
    assert at["sa2"].point == pytest.approx((9.0, 7.0)) and at["sa2"].z == pytest.approx(5.0)
    assert at["sa3"].point == pytest.approx((0.3, 6.0)) and at["sa3"].z == pytest.approx(3.9)
    assert at["wz1"].z == pytest.approx(0.5) and at["kn1"].room is None
    # z= gives the outlet
    d, _ = plumb("san sa4 w2 sink y=S+4 z=1.2\n")
    assert d.plumb.at["sa4"].z == pytest.approx(1.2)


# ---------- networks ----------


def test_cold_water() -> None:
    d, _ = plumb()
    cold = d.plumb.cold
    assert cold is not None
    # EG from the meter (1, 1, 0.5): the tank 2 + 0.5 away, the riser's foot 6 + 0.5; the sink
    # 8.7 m from the tank (6.7 + 1 + 1), nearer than from the meter (8.7 + 1 + 0.5 = 10.2).
    # OG from the riser (1, 7, 2.9): the WC 0.7 + 1 + 1 = 2.7, the shower 8 + 2.1 = 10.1.
    assert sections(cold) == {
        "wz1>t1": (2.5, 2, "pipe", ["sa1", "t1"]),
        "wz1>sr1:EG": (6.5, 2, "pipe", ["sa2", "sa3"]),
        "t1>sa1": (8.7, 3, "pipe", ["sa1"]),
        "sr1:EG>sr1:OG": (2.9, 1, "riser", ["sa2", "sa3"]),
        "sr1:OG>sa3": (2.7, 3, "pipe", ["sa3"]),
        "sr1:OG>sa2": (10.1, 2, "pipe", ["sa2"]),
    }
    assert cold.reach("sa2") == pytest.approx(6.5 + 2.9 + 10.1)


def test_hot_water() -> None:
    d, _ = plumb()
    assert d.plumb.tanks == ["t1"] and d.plumb.hot_from == {"sa1": "t1", "sa2": "t1"}
    hot = d.plumb.hot["t1"]
    # from the tank (3, 1, 0): the riser's foot 2 + 6 = 8, the sink 8.7; the WC takes cold only
    assert sections(hot) == {
        "t1>sr1:EG": (8.0, 2, "pipe", ["sa2"]),
        "t1>sa1": (8.7, 3, "pipe", ["sa1"]),
        "sr1:EG>sr1:OG": (2.9, 1, "riser", ["sa2"]),
        "sr1:OG>sa2": (10.1, 2, "pipe", ["sa2"]),
    }


def test_waste_water() -> None:
    d, _ = plumb()
    p = d.plumb
    # the sink: 7.7 + 5 = 12.7 to the stack in plan, 10.7 + 5 = 15.7 to the sewer connection
    assert p.drains_to == {"sa1": "fl1", "sa2": "fl1", "sa3": "fl1"}
    assert p.drain is not None
    # waste pipes lie at the storey's FFL
    assert sections(p.drain) == {
        "kn1>fl1:EG": (3.0, 1, "ground", ["sa1", "sa2", "sa3"]),
        "fl1:EG>fl1:OG": (2.9, 1, "stack", ["sa2", "sa3"]),
        "fl1:EG>sa1": (12.7, 2, "branch", ["sa1"]),
        "fl1:OG>sa3": (2.7, 2, "branch", ["sa3"]),
        "fl1:OG>sa2": (7.0, 1, "branch", ["sa2"]),
    }
    # to= the sewer connection, which is on the EG
    d, _ = plumb(text=PLUMB.replace("san sa1 w2 sink y=S+2", "san sa1 w2 sink y=S+2 to=kn1"))
    assert d.plumb.drain is not None and d.plumb.drain.path("sa1")[0].name == "kn1>sa1"


def test_without_a_riser_the_pipes_go_straight() -> None:
    d, rep = plumb(text=PLUMB.replace("riser sr1 r1 at=W+1,N-1\n", ""))
    cold = d.plumb.cold
    assert cold is not None and "riser" not in {s.kind for s in cold.sections}
    # the WC joins the nearest pipe: the meter, 0.7 + 5 + 3.4 = 9.1 away
    assert cold.path("sa3")[-1].name == "wz1>sa3"
    assert cold.path("sa3")[-1].length == pytest.approx(9.1)
    assert found(rep, "W-PLUMB-004") == []


# ---------- checks ----------


def test_checks() -> None:
    # no meter, no tank that heats drinking water, no sewer connection
    text = PLUMB.replace("meter wz1 r1 at=W+1,S+1 p=4 dp=400\n", "").replace(
        "sewer kn1 EG at=W-1,N-1\n", ""
    )
    _, rep = derive_text(HOUSE.replace(" dhw dp=100", "") + text)
    assert found(rep, "W-PLUMB-001") == ["sa1", "sa2", "sa3"]
    assert found(rep, "W-PLUMB-002") == ["sa1", "sa2"]
    assert found(rep, "W-PLUMB-003") == ["sa1", "sa2", "sa3"]
    assert "there is no sewer connection" in next(
        i.text() for i in rep.issues if i.code == "W-PLUMB-003"
    )
    # the tank heats no drinking water and supplies nothing in heat: a warning there
    assert found(rep, "W-HEAT-004") == ["t1"]
    # waste water to the sewer connection from the OG; a stack and a second meter in vain
    _, rep = plumb("san sa4 r2 basin at=W+1,S+1 to=kn1\nstack fl2 r2 at=W+1,S+1\nmeter wz2 r1\n")
    assert found(rep, "W-PLUMB-003") == ["sa4"]
    assert "kn1 does not reach OG" in next(i.text() for i in rep.issues if i.el == "sa4")
    assert found(rep, "W-PLUMB-004") == ["fl2"]
    assert found(rep, "W-PLUMB-005") == ["wz2"]
    # a dhw tank supplies the hot water: no W-HEAT-004
    assert found(rep, "W-HEAT-004") == []
    # a fixture on an interior wall needs its face
    _, rep = derive_text(HOUSE + PLUMB + "wall w9 EG IW x=W+5 y=w1..w3\nsan sa5 w9 basin y=S+1\n")
    assert found(rep, "E-PLUMB-002") == ["sa5"]


def test_describe() -> None:
    d, _ = plumb()
    m = d.model
    assert describe(d, m["sa2"]) == [
        "at 9,7 z 5 | r2 OG",
        "shower cold+hot | water 19.5 m from wz1 | hot 21.0 m from t1 | waste to fl1, 12.9 m"
        " to kn1",
    ]
    assert describe(d, m["wz1"])[1] == "supplies sa1-sa3 t1 | 33.4 m of pipe"
    assert describe(d, m["sr1"])[1] == "EG–OG"
    assert describe(d, m["fl1"])[1] == "EG–OG | takes sa1-sa3 | foot 3.0 m to kn1"
    assert describe(d, m["kn1"])[1] == "takes 3 fixtures | 28.3 m of pipe"
    assert describe(d, m["t1"]) == ["hot water to sa1 sa2 | 29.7 m of pipe"]


# ---------- hydraulics ----------


def test_hydraulics() -> None:
    # laminar 64/Re; a smooth pipe at Re 10^5: λ 0.0180 (Colebrook-White, the Moody chart)
    assert friction(1000, 0) == pytest.approx(0.064)
    assert friction(1e5, 0) == pytest.approx(0.0180, abs=1e-4)
    lam = friction(5e4, 0.001)
    assert 1 / math.sqrt(lam) == pytest.approx(
        -2 * math.log10(2.51 / (5e4 * math.sqrt(lam)) + 0.001 / 3.71)
    )
    # 0.1 l/s in a 12 mm bore: v = 0.0001 / (π 0.012² / 4) = 0.8842 m/s;
    # ρv²/2 = 999.7 · 0.8842² / 2 = 390.8 Pa = 3.908 hPa
    f = full(0.1, 12, 0.007, "cold")
    assert f.v == pytest.approx(0.88419, abs=1e-5)
    assert f.dyn == pytest.approx(3.9078, abs=1e-4)
    re = 0.88419 * 0.012 / 1.306e-6
    assert f.r == pytest.approx(friction(re, 0.007 / 12) / 0.012 * 3.9078, rel=1e-4)
    # 1 m of height: 999.7 · 9.81 = 9807 Pa
    assert geodetic(1) == pytest.approx(98.07, abs=0.01)
    # half full: half the circle, R_h = d/4; full: R_h = d/4 too
    assert wetted(0.5) == pytest.approx((math.pi / 8, 0.25))
    assert wetted(1) == pytest.approx((math.pi / 4, 0.25))
    # DN 100 (di 100 mm) at 1 %, k_b 1 mm: 4R = 0.1 m, √(2g · 0.1 · 0.01) = 0.14007;
    # 2.51 · 1.306e-6 / (0.1 · 0.14007) = 0.000234, 0.001 / 0.371 = 0.002695;
    # v = −2 lg(0.002929) · 0.14007 = 0.7097 m/s; full 0.7097 · π/4 · 0.01 = 5.574 l/s
    assert gravity(100, 0.01, 1, 1) == pytest.approx(5.574, abs=1e-3)
    assert gravity(100, 0.01, 1, 0.5) == pytest.approx(5.574 / 2, abs=1e-3)


def test_peak_flow() -> None:
    # V̇S = a ΣV̇R^b − c, at most ΣV̇R, at least the largest single flow
    assert peak(4, 0.2, (1, 0.5, 0)) == pytest.approx(2)
    assert peak(0.3, 0.2, (1, 0.5, 0)) == pytest.approx(0.3)
    assert peak(2, 0.5, (1, 0.5, 1.2)) == pytest.approx(0.5)


# ---------- sizing ----------


def test_water(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = plumb()
    o = run(WATER, d)
    assert o.ok, o.lines
    secs = {(x["temp"], x["a"], x["b"]): x for x in o.data["sections"]}  # type: ignore[union-attr]
    # wz1>t1 carries the sink's cold 0.1 and the tank's hot 0.1 + 0.2 = 0.4 l/s (V̇S = ΣV̇R
    # below 1 l/s with these constants); in 16x2 (12 mm) 3.54 m/s, so 20x2 (16 mm): 1.989 m/s
    s = secs[("cold", "wz1", "t1")]
    assert (s["sum_vr"], s["vs"], s["size"]) == (0.4, 0.4, "20x2")
    assert s["v"] == pytest.approx(0.0004 / (math.pi * 0.016**2 / 4), abs=1e-3)
    # t1>sa1: cold, 2 bends and a tee; hot from the tank itself, 2 bends
    for temp, zeta in (("cold", 3), ("hot", 2)):
        s = secs[(temp, "t1", "sa1")]
        f = full(0.1, 12, 0.007, temp)  # type: ignore[arg-type]
        assert (s["size"], s["zeta"]) == ("16x2", zeta)
        assert s["dp"] == pytest.approx(f.r * 8.7 + zeta * f.dyn, abs=0.01)
    # the WC: 4000 − 400 (apparatus) − 98.07 · 3.4 (from 0.5 up to 3.9) − its pipes − 500
    ways = {(w["fixture"], w["temp"]): w for w in o.data["fixtures"]}  # type: ignore[union-attr]
    wc = ways[("sa3", "cold")]
    pipes = sum(secs[("cold", *k)]["dp"] for k in (("wz1", "sr1:EG"), ("sr1:EG", "sr1:OG"),
                                                    ("sr1:OG", "sa3")))  # fmt: skip
    assert wc["height"] == pytest.approx(geodetic(3.4), abs=0.1)
    assert wc["reserve"] == pytest.approx(4000 - 400 - geodetic(3.4) - pipes - 500, abs=0.2)
    # hot water also loses the tank's 100 hPa and the cold way to the tank
    hot = ways[("sa2", "hot")]
    assert hot["tank"] == 100
    assert hot["pipes"] == pytest.approx(
        secs[("cold", "wz1", "t1")]["dp"]
        + sum(
            secs[("hot", *k)]["dp"]
            for k in (("t1", "sr1:EG"), ("sr1:EG", "sr1:OG"), ("sr1:OG", "sa2"))
        ),
        abs=0.2,
    )
    assert o.lines[0].startswith("wz1 4 bar, apparatus 400 hPa · pipe MV · V̇S = 1·ΣV̇R^0.5 − 0")
    assert "# Trinkwasser-Rohrbemessung: Box" in o.report
    assert any(c.startswith("fixture-flow (DIN 1988-300)") for c in o.tables)


def test_water_enlarges_the_worst_way(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = plumb(text=PLUMB.replace(" p=4 ", " p=2.6 "))
    o = run(WATER, d)
    ways = {(w["fixture"], w["temp"]): w["reserve"] for w in o.data["fixtures"]}  # type: ignore[union-attr]
    secs = {(x["temp"], x["b"]): x["size"] for x in o.data["sections"]}  # type: ignore[union-attr]
    # at 2.6 bar the shower's hot way falls short in 16x2; its pipes grow until it has its
    # pressure, the longest 10.1 m to the shower first
    assert o.ok and min(ways.values()) >= 0
    assert secs[("hot", "sa2")] == "20x2"
    # at 1.5 bar nothing is enough: the result fails
    d, _ = plumb(text=PLUMB.replace(" p=4 ", " p=1.5 "))
    o = run(WATER, d)
    assert not o.ok and any(x.endswith(" short") for x in o.lines)


def test_water_needs_its_data(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = plumb(text=PLUMB.replace(" p=4 dp=400", ""))
    with pytest.raises(ValueError, match="wz1 needs p="):
        run(WATER, d)
    d, _ = derive_text(HOUSE.replace(" dp=100", "") + PLUMB)
    with pytest.raises(ValueError, match="the type of t1 needs dp="):
        run(WATER, d)
    d, _ = plumb("san sa4 w2 bath y=S+4\n")
    with pytest.raises(ValueError, match="fixture-flow has no row for bath"):
        run(WATER, d)


def test_drain(tmp_path: Path) -> None:
    tables(tmp_path)
    # a basin behind the WC in the OG: 1 m from it, 1.7 + 2 = 3.7 from the stack
    d, _ = plumb("san sa4 w8 basin y=N-3\n")
    o = run(DRAIN, d, slope=1)
    secs = {(x["a"], x["b"]): x for x in o.data["sections"]}  # type: ignore[union-attr]
    # under the building: ΣDU 1 + 1 + 2 + 0.5 = 4.5, 0.5 √4.5 = 1.06 < the WC's 2: Q 2 l/s;
    # DN 100 (di 104) at 1 %, half full, carries more
    s = secs[("kn1", "fl1:EG")]
    assert (s["du"], s["q"], s["dn"]) == (4.5, 2, 100)
    assert s["holds"] == pytest.approx(gravity(104, 0.01, 1, 0.5), abs=1e-3)
    # the stack: the WC makes it DN 100 at least; 2 l/s within 4
    s = secs[("fl1:EG", "fl1:OG")]
    assert (s["du"], s["q"], s["dn"], s["holds"]) == (3.5, 2, 100, 4)
    # the collecting branch to the WC and the basin: no smaller than the WC's DN 100
    s = secs[("fl1:OG", "sa3")]
    assert (s["du"], s["dn"], s["holds"]) == (2.5, 100, 3)
    assert secs[("sa3", "sa4")]["dn"] == 50
    # the sink's branch is 12.7 m and the shower's 7, unvented at most 4 for one fixture; the
    # basin's 3.7 m on a collecting branch within its 10
    branches = {b["fixture"]: (b["length"], b["lmax"]) for b in o.data["branches"]}  # type: ignore[union-attr]
    assert branches == {
        "sa1": (12.7, 4),
        "sa2": (7.0, 4),
        "sa3": (2.7, 10),
        "sa4": (3.7, 10),
    }
    assert not o.ok
    assert "sa1 branch 12.7 m, unvented at most 4 m: too long" in o.lines
    assert "| sa1 | Einzel | 12,7 | 4,0 | **zu lang** |" in o.report
    # a stack too small for its flow: only DN 50 in the type and no WC
    d, _ = plumb(
        text=PLUMB.replace("50:50x2,100:110x3", "50:50x2").replace(
            "san sa3 w8 wc", "san sa3 w8 sink"
        )
    )
    o = run(DRAIN, d, slope=1)
    stack = next(x for x in o.data["sections"] if x["kind"] == "stack")  # type: ignore[union-attr]
    assert stack["dn"] == 50  # 0.5 √2 = 0.71 < 1 (sink 1, shower 1): Q 1, within DN 50's 1
    d, _ = plumb(text=PLUMB.replace("50:50x2,100:110x3", "50:50x2"))
    o = run(DRAIN, d, slope=1)
    assert any("HT has no size of DN 100 or more" in x for x in o.lines)


def test_haus_mueller_plumbing() -> None:
    out: list[str] = []
    for name in ("project.uea", "arch.uea", "light.uea", "elec.uea", "heat.uea", "plumb.uea"):
        for line in (PROTOTYPE / name).read_text().splitlines():
            if not line.startswith(("feed fd3", "feed fd4", "feed fd5", "feed fd6")):
                out.append(line)
    d, rep = derive_text("\n".join(out) + "\n")
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-PLUMB", "W-HEAT"))] == []
    p = d.plumb
    assert p.cold is not None and p.drain is not None
    assert sorted(p.hot_from) == ["sa1", "sa4", "sa6", "sa7"]
    # everything drains to the stack in the HWR under the WC of the bath (request q3)
    assert set(p.drains_to.values()) == {"fl1"}
    assert d.plumb.at["fl1"].room == "r3"


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    tables(tmp_path)
    ops = re.sub(r"\b((?:w|sl|r|t|wz|sr|fl|kn|sa)\d)\b", r"@\1", HOUSE + PLUMB)
    code, out = sh(
        "apply", "--by", "t", "-m", "plumb", stdin="".join(f"+ {x}\n" for x in ops.splitlines())
    )
    assert code == 0, out
    code, out = sh("show", "EG")
    assert "plumb 1 san 1 meter 1 riser 1 stack 1 sewer" in out
    code, out = sh("get", "sa2")
    assert "waste to fl1, 12.9 m to kn1" in out
    code, out = sh("calc", "water")
    assert code == 0 and "report: out/water.md" in out, out
    code, out = sh("calc", "drain", "slope=1")
    assert code == 1 and "too long" in out


# ---------- circulation ----------


def test_circulation(tmp_path: Path) -> None:
    tables(tmp_path)
    d, rep = plumb("recirc zk1 t1\n")
    assert [i.code for i in rep.issues if i.code == "W-PLUMB-007"] == []
    # the riser is circulated; the branches t1>sa1 and sr1:OG>sa2 end at one fixture each
    assert [s.name for s in d.plumb.recirc["t1"].sections] == ["t1>sr1:EG", "sr1:EG>sr1:OG"]
    o = run(RECIRC, d, None, loss=10, dt=5, dead=3)
    assert o.ok
    lp = o.data["loops"]["zk1"]  # type: ignore[index]
    rho_c = RHO["hot"] * CP
    legs = {x["b"]: x for x in lp["legs"]}
    # the riser loses 10 · 2.9 W; the pipe to it carries that and its own 10 · 8
    assert legs["sr1:OG"]["loss"] == pytest.approx(29)
    assert legs["sr1:EG"]["loss"] == pytest.approx(109)
    assert legs["sr1:OG"]["q"] == pytest.approx(29 / (rho_c * 5), rel=1e-4)
    assert lp["flow"] == pytest.approx(109 / (rho_c * 5), rel=1e-4)
    # the circulation pipe: the smallest within 2 m/s; one bend on t1>sr1:EG, a tee up the riser
    q1 = 109 / (rho_c * 5)
    assert legs["sr1:EG"]["circ"] == "16x2"
    f = full(q1, 12, 0.007, "hot")
    assert legs["sr1:EG"]["dp_circ"] == pytest.approx(f.r * 8.0 + 1 * f.dyn, abs=1e-3)
    # one end: its loss is the pump head
    total = sum(x["dp_hot"] + x["dp_circ"] for x in lp["legs"])
    assert lp["head"] == pytest.approx(total, abs=0.01) and lp["index"] == "sr1:OG"
    # the branches without circulation hold π · d_i² / 4 · l (16x2, d_i 12 mm)
    dead = lp["dead"]
    assert dead["sa1"]["length"] == pytest.approx(8.7)
    assert dead["sa2"]["length"] == pytest.approx(10.1)
    assert dead["sa2"]["litres"] == pytest.approx(math.pi * 0.012**2 / 4 * 10.1 * 1000, rel=1e-3)
    o = run(RECIRC, d, None, loss=10, dt=5, dead=1)
    assert not o.ok
    assert any(x.startswith("sa2: 1.14 l in 10.1 m without circulation > 1 l") for x in o.lines)


def test_circulation_needs_pipes_to_circulate() -> None:
    _, rep = plumb("recirc zk1 t1\n", PLUMB.replace("san sa2 r2 shower at=E-1,N-1\n", ""))
    assert ("W-PLUMB-007", "zk1") in [(i.code, i.el) for i in rep.issues]

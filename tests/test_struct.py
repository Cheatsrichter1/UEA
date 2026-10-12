"""The structure pack (decision 0040): the load path's checks, `uea calc loads` and `uea calc
struct`, by hand on the 10 x 8 box of conftest with an OG of the same walls on top (h 2.5), slabs
DE (0.2 concrete, 0.01 plaster) and floors FB (0.02 tiles, 0.13 screed), and synthetic tables of
our own: none of their values is a standard's."""

import math
from pathlib import Path

import pytest

from tests.conftest import BOX, PROTOTYPE, Shell, derive_text, model_from
from tests.test_calc_elec import install, run
from tests.test_elec import found
from uea.calc import Env
from uea.packs.struct.actions import Act, Factors
from uea.packs.struct.design import STRUCT, bending, slenderness
from uea.packs.struct.frame import Case, beam
from uea.packs.struct.loads import FACTORS, IMPOSED, LOADS, PARTITION, PSI, SNOW, UNIT_WEIGHT, WIND
from uea.packs.struct.model import slab_supports
from uea.packs.struct.plate import analyse
from uea.packs.struct.positions import positions
from uea.packs.struct.tables import (
    BEAM_MATERIAL,
    COLUMN_SECTION,
    CONCRETE,
    LIMITS,
    LINTEL,
    MASONRY,
    MASONRY_END,
    SECTION,
    TIMBER,
)

HOUSE = BOX + (
    "wall w5 OG AW on=w1 lb h=2.5\n"
    "wall w6 OG AW on=w2 lb h=2.5\n"
    "wall w7 OG AW on=w3 lb h=2.5\n"
    "wall w8 OG AW on=w4 lb h=2.5\n"
    "slab sl1 EG DE\n"
    "slab sl2 OG DE\n"
    "room r1 EG living at=W+1,S+1 floor=FB\n"
    "room r2 OG living at=W+1,S+1 floor=FB\n"
)
# γ in kN/m³: AW 0.01 · 10 + 0.3 · 8 + 0.02 · 15 = 2.8 kN/m², DE 0.2 · 25 + 0.01 · 10 = 5.1,
# FB 0.02 · 20 + 0.13 · 20 = 3.0, IW 0.01 · 10 + 0.115 · 15 + 0.01 · 10 = 1.925
WEIGHTS = (
    "material,gamma\ngips,10\nmw,8\nputz,15\nstb,25\nfliese,20\nestrich,20\nks,15\n"
    "putz-gips,10\nputz-kalkgips,14\nziegel-t9,7\nputz-leicht,10\nxps,0.4\nze,20\neps-tsd,0.3\n"
    "eps,0.3\nparkett,7\nosb,6\nziegel,20\nsparren,2\nlattung,5\nkonterlattung,5\n"
)
IMPOSED_T = (
    "use,qk\nliving,1.5\nkitchen,1.5\nbedroom,1.5\nutility,2\nwc,1.5\nhall,2\nbath,1.5\nattic,1\n"
)
PARTS = "upto,qk\n4,0.7\n6,1.1\n"
FAC = (
    "name,value\ngamma-g,1.3\ngamma-q,1.4\ngamma-g-inf,0.9\ngamma-m,1.6\nzeta,0.8\nrho2,0.7\n"
    "gamma-c,1.6\nalpha-cc,0.8\ngamma-s,1.2\nfyk,480\nd1,0.03\ncrdc,0.12\nvmin,0.04\n"
    "rho-min-ft,0.25\nrho-min,0.0012\n"
)
PSI_T = "action,psi0\nimposed,0.65\nsnow,0.45\nwind,0.55\n"
SNOW_T = "pitch,mu1\n0,0.7\n30,0.7\n60,0\n"
WIND_T = "pitch,pressure,suction\n0,0,-0.6\n30,0.4,-0.4\n45,0.6,-0.2\n"
LIMITS_T = (
    "name,value\nbuilding-height,18\nspan,8\nqk,4.5\nclear-height,2.8\nxi,0.4\ndeflection,250\n"
    "ld,33\nld-span,145\n"
)
MASONRY_T = "material,fk\nmw,4\nks,9.5\nziegel-t9,3.2\n"
END_T = "upto,phi\n5,0.75\n8,0.45\n"
CONCRETE_T = "material,fck,ecm\nstb,28,30000\n"
LINTEL_T = (
    "type,t,span,qrd\nL-A,0.3,1.25,20\nL-A,0.3,1.5,30\nL-B,0.3,1.5,90\nFS-365,0.365,1.5,40\n"
    "FS-365,0.365,2.5,25\nSB-365,0.365,2.5,90\nFS-240,0.24,1.25,30\nSB-240,0.24,1.25,90\n"
)
SECTION_T = "name,material,w,i,av,g\nS-160,steel-x,300,2400,18,0.42\n"
COLUMN_T = "name,material,a,imin,alpha,g\nC-140,steel-x,40,500,0.49,0.3\n"
STEEL_T = "material,fk,fvk,e,gamma,kmod\nsteel-x,230,130,200000,1.1,1\n"
ROOF = (
    "type DA roof layers=ziegel:0.05,*sparren:0.2\n"
    "roof rf1 OG DA gable ridge=x pitch=30 knee=2.5 eave=0.5\n"
)
"""On the OG: 1.4 kN/m² along the slope, two planes of 10 x 4.5 m on plan."""
SHARES = {"w1": 21.09 + 3, "w2": 13.69 + 2.22, "w3": 21.09 + 3, "w4": 13.69 + 2.22}
"""The 9.4 x 7.4 field inside the cores split at 45°: triangles of 7.4 · 3.7 / 2 = 13.69 m² at the
short sides, trapezoids of (69.56 - 2 · 13.69) / 2 = 21.09 m² at the long ones; each wall also
carries the slab over its own core: 10 x 0.3 = 3 and 7.4 x 0.3 = 2.22 m²."""


def near(v: float) -> object:
    """The data rounds to three decimals."""
    return pytest.approx(v, abs=2e-3)


TIMBER_T = (
    "material,fmk,ft0k,fc0k,fvk,e0mean,e005,kmod,gamma,kcr,betac\n"
    "C24,24,14,21,4,11000,7400,0.9,1.3,0.67,0.2\n"
)


@pytest.fixture
def tables(tmp_path: Path) -> None:
    for spec, text in (
        (UNIT_WEIGHT, WEIGHTS),
        (IMPOSED, IMPOSED_T),
        (PARTITION, PARTS),
        (FACTORS, FAC),
        (PSI, PSI_T),
        (SNOW, SNOW_T),
        (WIND, WIND_T),
        (LIMITS, LIMITS_T),
        (MASONRY, MASONRY_T),
        (MASONRY_END, END_T),
        (CONCRETE, CONCRETE_T),
        (LINTEL, LINTEL_T),
        (SECTION, SECTION_T),
        (BEAM_MATERIAL, STEEL_T),
        (TIMBER, TIMBER_T),
        (COLUMN_SECTION, COLUMN_T),
    ):
        install(spec.id, spec, text, tmp_path)


def test_checks() -> None:
    _, rep = derive_text(HOUSE)
    assert [i for i in rep.issues if i.code.startswith("W-STRUCT")] == []
    # an OG wall marked load-bearing over the open EG; the EG walls not load-bearing
    _, rep = derive_text(HOUSE + "wall w9 OG AW x=W+5 y=w5..w7 lb h=2.5\n")
    assert found(rep, "W-STRUCT-001") == ["w9"]
    _, rep = derive_text(HOUSE.replace("W..E lb\n", "W..E\n").replace("w1..w3 lb\n", "w1..w3\n"))
    assert found(rep, "W-STRUCT-002") == ["sl2"]
    assert sorted(found(rep, "W-STRUCT-001")) == ["w5", "w6", "w7", "w8"]


def test_loads(tables: None) -> None:
    d, _ = derive_text(HOUSE)
    o = run(LOADS, d, None, soil=150)
    assert o.ok
    sl2 = o.data["slabs"]["sl2"]
    # 80 m² of slab, the room 9.38 x 7.38 = 69.2244 m² of floor and imposed load
    g = 80 * 5.1 + 69.2244 * 3.0
    q = 69.2244 * 1.5
    assert (sl2["G"], sl2["Q"]) == (near(g), near(q))
    for k, a in SHARES.items():
        assert sl2["shares"][k] == pytest.approx(a, abs=0.2), k
    w = o.data["walls"]
    # own weights: EG 2.7 high (from the SSL -0.15 to the slab's underside 2.55), OG 2.5
    assert w["w1"]["own"] == near(10 * 2.7 * 2.8)
    assert w["w5"]["own"] == near(10 * 2.5 * 2.8)
    assert w["w5"]["on"] == ["w1"]
    # w1 at its base: itself, its share of sl2, w5
    share = sl2["shares"]["w1"] / 80
    assert w["w1"]["G"] == near(75.6 + g * share + 70)
    assert w["w1"]["Q"] == near(q * share)
    nd = (1.3 * w["w1"]["G"] + 1.4 * w["w1"]["Q"]) / 10
    assert f"n_d {nd:.1f} kN/m, b ≥ {nd / 150:.2f} m" in "\n".join(o.lines)
    # the ground slab goes to the soil
    assert "(on the ground)" in next(x for x in o.lines if x.startswith("sl1"))


def test_partitions(tables: None, tmp_path: Path) -> None:
    text = HOUSE + "wall w9 OG IW x=W+5 y=w5..w7 h=2.5\nroom r3 OG living at=E-1,S+1 floor=FB\n"
    d, _ = derive_text(text)
    o = run(LOADS, d, None)
    # 1.925 kN/m² x 2.5 m = 4.8125 kN/m: the row up to 6, 1.1 kN/m² on the OG's
    # 4.68 x 7.38 + 4.565 x 7.38 = 68.2281 m² of rooms
    assert o.data["partitions"]["w9"] == near(4.8125)
    rooms = 4.68 * 7.38 + 4.565 * 7.38
    assert o.data["slabs"]["sl2"]["Q"] == near(rooms * (1.5 + 1.1))
    assert o.ok
    # heavier than the table: a line load on sl2, 4.8125 kN/m over its 7.4 m between w5 and w7,
    # half of it nearest to w1, half to w3; no surcharge on the OG any more
    before = o.data["walls"]
    install(PARTITION.id, PARTITION, "upto,qk\n4,0.7\n", tmp_path)
    o = run(LOADS, d, None)
    assert o.ok and o.data["heavy"] == ["w9"]
    assert o.data["slabs"]["sl2"]["Q"] == near(rooms * 1.5)
    line = 4.8125 * 7.4
    assert "w9 OG: G 35.6 kN, Q 0.0 kN on w1, w3" in o.lines
    for k in ("w1", "w3"):
        top = o.data["walls"][k]["top"]["G"] - before[k]["top"]["G"]
        assert top == pytest.approx(line / 2, abs=0.2), k


def test_missing_data(tables: None) -> None:
    d, _ = derive_text(
        HOUSE.replace("type DE slab layers=*stb:0.2", "type DE slab layers=*bims:0.2")
    )
    with pytest.raises(ValueError, match="unit-weight has no row for bims"):
        run(LOADS, d, None)


def test_haus_mueller(tables: None) -> None:
    out: list[str] = []
    for name in ("project", "arch"):
        out += (PROTOTYPE / f"{name}.uea").read_text().splitlines()
    d, rep = derive_text("\n".join(out) + "\n")
    assert [i for i in rep.issues if i.code.startswith("W-STRUCT")] == []
    o = run(LOADS, d, None, sk=0.85, qp=0.5)
    assert o.ok, o.lines
    w = o.data["walls"]
    # nothing is lost on the way down: the footings carry every load-bearing wall, every slab
    # but the ground slab and the roof
    base = sum(x["G"] for x in w.values() if x["level"] == "EG")
    own = sum(x["own"] for x in w.values())
    slabs = sum(s["G"] for k, s in o.data["slabs"].items() if k != "sl1")
    roof = sum(e["G"] for e in o.data["roofs"]["rf1"]["edges"].values())
    assert base == pytest.approx(own + slabs + roof, abs=0.05)
    # the gable roof rests on the OG's eaves walls under the slab of the Spitzboden; the gable
    # walls stand on the OG's west and east walls and corners
    assert {k: e["to"] for k, e in o.data["roofs"]["rf1"]["edges"].items()} == {
        "s": {"w8": 1.0},
        "n": {"w10": 1.0},
    }
    assert set(w["w16"]["on"]) <= {"w8", "w10", "w11"} and "w11" in w["w16"]["on"]
    # every position proved
    o = run(STRUCT, d, None, sk=0.85, qp=0.5, soil=200)
    assert o.ok, [x for x in o.lines if "NOT OK" in x]
    kinds = [p["kind"] for p in o.data["positions"].values()]
    assert kinds.count("slab") == 2 and kinds.count("lintel") == 20 and kinds.count("footing") == 5
    # the holes of the services in the slab and the outer walls are listed for the engineer
    assert o.data["holes"] == ["ho1", "ho2", "ho3", "ho4", "ho5", "ho6"]


def test_on_the_command_line(sh: Shell, tables: None) -> None:
    import re

    ops = re.sub(r"\b((?:w|sl|r)\d)\b", r"@\1", HOUSE).splitlines()
    code, out = sh("apply", "--by", "t", "-m", "box", stdin="".join(f"+ {x}\n" for x in ops))
    assert code == 0, out
    code, out = sh("calc", "loads", "soil=150")
    assert code == 0 and "w1 EG base:" in out, out
    code, out = sh("export", "pdf", "loads")
    assert code == 0 and "loads.pdf A4" in out, out
    code, out = sh("help", "struct")
    assert "calc struct: the Statische Berechnung" in out and "beam " in out
    code, out = sh("calc", "struct", "soil=150")
    # the box's slab spans 7.7 m with 0.2 m: too slender (test_slab_checks), so the result fails
    assert code == 1 and "2.01 sl2 slab h 0.20" in out and "3.01 w1 EG base" in out, out
    assert "l/d 45.3 ≤ 18.8 NOT OK" in out
    code, out = sh("export", "pdf", "struct")
    assert code == 0 and "struct.pdf A4" in out, out
    code, out = sh("export", "svg", "struct:EG")
    assert code == 0 and "struct-EG.svg A3 1:50" in out, out
    svg = (sh.root / "out" / "struct-EG.svg").read_text()
    assert "2.01 Decke sl2" in svg and "2.02 · 3.01" in svg
    code, out = sh("export", "svg", "struct:XX")
    assert code == 1 and "unknown level" in out


# ---------- 8b: roof, snow, wind, combination ----------


def test_roof(tables: None) -> None:
    d, rep = derive_text(HOUSE + ROOF)
    assert [i for i in rep.issues if i.code.startswith("W-STRUCT")] == []
    with pytest.raises(ValueError, match="give sk= and qp="):
        run(LOADS, d, None)
    o = run(LOADS, d, None, sk=0.85, qp=0.5)
    assert o.ok, o.lines
    # each plane 10 x 4.5 = 45 m² on plan: g 1.4 / cos 30° = 1.61658, s 0.7 · 0.85 = 0.595,
    # w 0.4 · 0.5 = 0.2 and the suction -0.4 · 0.5 = -0.2 kN/m²
    g = 1.4 / math.cos(math.radians(30))
    edges = o.data["roofs"]["rf1"]["edges"]
    assert set(edges) == {"s", "n"}
    s = edges["s"]
    assert (s["G"], s["S"], s["W"], s["up"]) == (
        near(45 * g),
        near(45 * 0.595),
        near(45 * 0.2),
        near(-45 * 0.2),
    )
    # the eaves rest on the OG's walls along them
    assert s["to"] == {"w5": 1.0} and edges["n"]["to"] == {"w7": 1.0}
    assert o.data["walls"]["w5"]["top"]["S"] == near(45 * 0.595)
    # uplift with the roof's weight favourable: (0.9 · G + 1.4 · W_suction) / 10 m
    up = (0.9 * 45 * g - 1.4 * 9.0) / 10
    assert (
        f"rf1 eaves s: G {45 * g:.1f}, S 26.8, W 9.0 kN on w5 100%; uplift n_d {up:.2f} kN/m"
        in (o.lines)
    )
    # and down to the footing of w1, the snow leading or the imposed load
    base = o.data["walls"]["w1"]
    lead = max(
        base["Q"] + 0.45 * base["S"] + 0.55 * base["W"],
        base["S"] + 0.65 * base["Q"] + 0.55 * base["W"],
        base["W"] + 0.65 * base["Q"] + 0.45 * base["S"],
    )
    nd = (1.3 * base["G"] + 1.4 * lead) / 10
    assert any(x.startswith("w1 EG base:") and f"n_d {nd:.1f} kN/m" in x for x in o.lines)


def test_combination(tables: None) -> None:
    f = Factors(Env(LOADS, {}))
    # leading Q: 4 + 0.45 · 2 + 0.55 · 1 = 5.45 beats S (5.15) and W (4.5)
    assert f.design(Act(10, 4, 2, 1)) == pytest.approx(1.3 * 10 + 1.4 * 5.45)
    # one variable action needs no ψ; uplift does not count
    assert f.design(Act(10, 4, 0, -3)) == pytest.approx(13 + 5.6)


def test_point_load(tables: None) -> None:
    d, _ = derive_text(HOUSE)
    before = run(LOADS, d, None).data["walls"]["w2"]["top"]
    d, _ = derive_text(HOUSE + "load lo1 OG g=3 q=1 at=9.5,4\n")
    o = run(LOADS, d, None)
    # 0.2 m from the core of w2, far from the others
    top = o.data["walls"]["w2"]["top"]
    assert (top["G"] - before["G"], top["Q"] - before["Q"]) == (near(3), near(1))
    assert "lo1 OG: G 3.0 kN, Q 1.0 kN on w2" in o.lines


def test_beam(tables: None) -> None:
    # an OG wall over the open EG: on a beam that spans from w1 to w3 under it
    wall = "wall w9 OG IW x=W+5 y=w5..w7 lb h=2.5\n"
    d, rep = derive_text(HOUSE + wall + "beam bm1 OG S-160 a=5.0575,0.15 b=5.0575,7.85\n")
    assert [i for i in rep.issues if i.code.startswith("W-STRUCT")] == []
    o = run(LOADS, d, None)
    assert o.ok, o.lines
    assert o.data["walls"]["w9"]["on"] == ["bm1"]
    r = o.data["beams"]["bm1"]
    # symmetric: half to each wall; together the beam's own weight over 7.7 m, its part of sl2
    # and the wall on it
    sl2 = o.data["slabs"]["sl2"]
    part = sl2["shares"]["bm1"] / sum(sl2["shares"].values())
    total = 0.42 * 7.7 + sl2["G"] * part + o.data["walls"]["w9"]["G"]
    assert r["w1"]["G"] == pytest.approx(r["w3"]["G"], abs=1e-3)
    assert r["w1"]["G"] + r["w3"]["G"] == pytest.approx(total, abs=0.01)
    assert r["w1"]["Q"] + r["w3"]["Q"] == pytest.approx(sl2["Q"] * part, abs=0.01)
    # its design: about q_d · L² / 8 over the 7.55 m between the middles of its bearings
    o = run(STRUCT, d, None)
    line = next(x for x in o.lines if " bm1 beam" in x)
    qd = (1.3 * total + 1.4 * sl2["Q"] * part) / 7.7
    m_ed = float(line.split("M_Ed ")[1].split("/")[0])
    assert m_ed == pytest.approx(qd * 7.55**2 / 8, rel=0.02)
    # M_Rd = 300 cm³ · 230 / 1.1 = 62.7 kNm
    assert "M_Rd 62.7 kNm" in line


def test_beam_solver() -> None:
    # a single span: M = qL²/8, w = 5qL⁴/(384EI); two spans: M_support = qL²/8, R_mid = 1.25 qL
    one = beam(4, [0, 4], 1e4, {"g": Case([(0, 4, 10)])}, {"c": {"g": 1}})["c"]
    assert (one.sag, one.shear, one.reactions) == (pytest.approx(20), pytest.approx(20), [20, 20])
    assert one.deflection == pytest.approx(5 * 10 * 4**4 / (384 * 1e4), rel=1e-3)
    two = beam(8, [0, 4, 8], 1e4, {"g": Case([(0, 8, 10)])}, {"c": {"g": 1}})["c"]
    assert two.hog == pytest.approx(20) and two.reactions[1] == pytest.approx(50)
    assert two.sag == pytest.approx(9 * 10 * 16 / 128)


# ---------- 8c: members ----------


def navier(q: float, a: float, b: float, nu: float = 0.2) -> tuple[float, float]:
    """m_x and m_y in the middle of a simply supported rectangle a x b under q (series)."""
    mx = my = 0.0
    for m in range(1, 80, 2):
        for n in range(1, 80, 2):
            s = (-1) ** ((m + n) // 2 - 1)
            k = 16 * q / (math.pi**6 * m * n * ((m / a) ** 2 + (n / b) ** 2) ** 2)
            mx += s * k * math.pi**2 * ((m / a) ** 2 + nu * (n / b) ** 2)
            my += s * k * math.pi**2 * ((n / b) ** 2 + nu * (m / a) ** 2)
    return mx, my


def edge_shear(q: float, a: float, b: float, nu: float = 0.2) -> float:
    """The support's line reaction (Kirchhoff's effective shear V_y = Q_y + ∂M_xy/∂x) in the
    middle of the edge y = b of a simply supported rectangle a x b under q (series)."""
    out = 0.0
    for m in range(1, 201, 2):
        for n in range(1, 201, 2):
            am, bn = m * math.pi / a, n * math.pi / b
            w = 16 * q / (math.pi**2 * m * n) / (am**2 + bn**2) ** 2
            out += w * math.sin(am * a / 2) * (bn**3 + (2 - nu) * am**2 * bn)
    return out


def test_plate() -> None:
    # sl2 on the axes of w1..w4: a 9.7 x 7.7 rectangle, under 12 kN/m² everywhere
    d, _ = derive_text(HOUSE)
    sl = d.arch.slabs["sl2"]
    m = analyse(d.arch, sl.net, slab_supports(d.arch, sl), 0.2, 30e6, lambda x, y: 12.0, [])
    mx, my = navier(12.0, 9.7, 7.7)
    # the shear: the line reaction in the middle of the long edge, within 1 % of the series
    assert m.shear == pytest.approx(edge_shear(12.0, 9.7, 7.7), rel=0.01)
    assert m.at_shear == pytest.approx((5.0, 7.85))
    # the plate ends at the exterior walls' axes; at the elements' middles: within 1 %, and
    # m_x + |m_xy| peaks off the middle, toward the corners
    assert m.bottom_y == pytest.approx(my, rel=0.01)
    assert mx < m.bottom_x < 1.1 * mx


def test_bending_and_slenderness() -> None:
    # m 20 kNm/m, d 0.17 m, f_cd 14 and f_yd 400 N/mm²: μ = 20 / (0.17² · 14000) = 0.049432,
    # ω = 1 - √(1 - 2μ) = 0.050718, a_s = ω · 0.17 · 14000 / 400000 = 3.018 cm²/m, x/d = ω / 0.8
    mu, got = bending(20, 0.17, 14000, 400000)
    assert got is not None
    assert mu == pytest.approx(0.049432, abs=1e-6)
    assert got == (pytest.approx(0.050718 / 0.8, abs=1e-5), pytest.approx(3.018, abs=1e-3))
    assert bending(300, 0.17, 14000, 400000)[1] is None
    # h_ef / t = 6.3: 0.85 - 0.0011 · 39.69 = 0.806341
    assert slenderness(6.3) == pytest.approx(0.806341)


def test_slab_checks(tables: None) -> None:
    d, _ = derive_text(HOUSE)
    o = run(STRUCT, d, None)
    line = next(x for x in o.lines if " sl2 slab" in x)
    # d = 0.2 - 0.03; f_ctm = 0.3 · 28^(2/3); a_s,min = max(0.25 · f_ctm / 480, 0.0012) · d
    dd = 0.17
    fctm = 0.3 * 28 ** (2 / 3)
    as_min = max(0.25 * fctm / 480, 0.0012) * dd * 1e4
    assert as_min == pytest.approx(2.449, abs=1e-3)
    # shear: k = min(1 + √(200/170), 2) = 2, ρ_l = a_s,min / (b d); v_Rd,c the larger of
    # 0.12 · k · (100 ρ_l f_ck)^(1/3) and v_min = 0.04 · k^1.5 · √28, times d
    rho = as_min / (dd * 1e4)
    v_c = 0.12 * 2 * (100 * rho * 28) ** (1 / 3)
    v_min = 0.04 * 2**1.5 * math.sqrt(28)
    assert v_min > v_c
    assert f"/v_Rd,c {v_min * dd * 1000:.1f} kN/m" in line
    # slenderness: the field 9.7 x 7.7 between the axes, l = 7.7; l/d = 45.3 against
    # min(33, 145 / 7.7) = 18.8: too slender
    assert f"l/d {7.7 / dd:.1f} ≤ {145 / 7.7:.1f} NOT OK" in line
    # the plate is loaded in three cases: every room, and alternate rooms (r1 alone here: the
    # pattern needs two groups, so one case)
    assert "Lastfälle: Nutzlast überall;" in o.report


def test_load_patterns() -> None:
    from uea.packs.struct.design import _patterns  # pyright: ignore[reportPrivateUsage]
    from uea.packs.struct.loads import RoomLoad, SlabLoad

    box = __import__("shapely").box
    rooms = [
        RoomLoad("r1", box(0, 0, 4, 4), 1, 2),
        RoomLoad("r2", box(4.2, 0, 8, 4), 1, 2),
        RoomLoad("r3", box(0, 4.2, 4, 8), 1, 2),
        RoomLoad("r4", box(4.2, 4.2, 8, 8), 1, 2),
    ]
    s = SlabLoad("sl", "OG", 64, 5, 0, 0, 0, 0, room_loads=rooms)
    # a checkerboard: r1 and r4 against r2 and r3
    assert _patterns(s) == {"all": None, "odd": {"r1", "r4"}, "even": {"r2", "r3"}}


def test_walls_and_lintels(tables: None) -> None:
    d, _ = derive_text(HOUSE + "win f1 w1 1.26x1.26 x=W+2\n")
    loads = run(LOADS, d, None).data["walls"]
    o = run(STRUCT, d, None)
    pos = {p["id"]: (k, p) for k, p in o.data["positions"].items() if p["kind"] == "wall"}
    # w2: h 2.7 (SSL -0.15 to the slab's underside 2.55), h_ef = 0.7 · 2.7, t 0.3, so Φ1 = 0.806;
    # the slab ends on it with l_f = min(9.7 across, 7.7 along) = 7.7: Φ2 = 0.45 governs;
    # f_d = 0.8 · 4 / 1.6 = 2 N/mm²: n_Rd = 0.45 · 2000 · 0.3 = 270 kN/m
    # w2 runs 7.4 m between the cores of w1 and w3
    b = loads["w2"]
    n_ed = (1.3 * b["G"] + 1.4 * b["Q"]) / 7.4
    line = next(x for x in o.lines if " w2 wall" in x)
    assert f"n_Ed {n_ed:.1f}/n_Rd 270.0 kN/m, Φ 0.45" in line and "ok" in line
    assert pos["w2"][1]["eta"] == pytest.approx(n_ed / 270, abs=1e-3)
    # the lintel over f1 in w1: what w1 carries at its top per metre, and the masonry over the
    # window (2.55 - 2.26 = 0.29 m of 2.8 kN/m²); too much for L-A (30 kN/m), so L-B
    t = loads["w1"]["top"]
    qd = 1.3 * (t["G"] / 10 + 2.8 * 0.29) + 1.4 * t["Q"] / 10
    line = next(x for x in o.lines if " f1 lintel" in x)
    assert f"q_d {qd:.1f} kN/m → L-B (q_Rd 90.0) η {qd / 90:.2f} ok" in line
    # the wall without the window: 10 - 1.26 m of masonry
    w1 = loads["w1"]
    assert f"n_Ed {(1.3 * w1['G'] + 1.4 * w1['Q']) / 8.74:.1f}" in next(
        x for x in o.lines if " w1 wall" in x
    )


def test_positions(tables: None) -> None:
    d, _ = derive_text(HOUSE)
    got = [(p.no, p.kind, p.id, p.sheet) for p in positions(d)]
    assert got == [
        ("1.01", "wall", "w5", "OG"),
        ("1.02", "wall", "w6", "OG"),
        ("1.03", "wall", "w7", "OG"),
        ("1.04", "wall", "w8", "OG"),
        ("2.01", "slab", "sl2", "EG"),
        ("2.02", "wall", "w1", "EG"),
        ("2.03", "wall", "w2", "EG"),
        ("2.04", "wall", "w3", "EG"),
        ("2.05", "wall", "w4", "EG"),
        ("3.01", "footing", "w1", "EG"),
        ("3.02", "footing", "w2", "EG"),
        ("3.03", "footing", "w3", "EG"),
        ("3.04", "footing", "w4", "EG"),
    ]


def test_more_checks() -> None:
    # a beam on one wall only; a hole in the slab over the wall that carries it
    _, rep = derive_text(
        HOUSE + "beam bm1 OG S-160 a=2,0.15 b=2,4\nhole ho1 sl2 0.2x0.2 at=0.15,4\n"
    )
    assert found(rep, "W-STRUCT-003") == ["bm1"]
    assert found(rep, "W-STRUCT-004") == ["ho1"]


def test_wall_hole(tables: None) -> None:
    # a rectangular hole through w2 gets a lintel and shortens the wall; a core drilling neither
    # gets a lintel nor is missed in the list of holes
    d, _ = derive_text(
        HOUSE + "hole ho1 w2 0.3x0.2 y=S+2 sill=1.5\nhole ho2 w4 0.15x0.15 y=S+2 sill=1.5 round\n"
    )
    o = run(STRUCT, d, None)
    assert [
        (p["kind"], p["id"]) for p in o.data["positions"].values() if p["kind"] == "lintel"
    ] == [("lintel", "ho1")]
    assert any(" ho1 lintel 0.30 m in w2" in x for x in o.lines)
    assert o.data["holes"] == ["ho1", "ho2"]


# ---------- 8e: rafters ----------


def test_rafter_frames() -> None:
    from uea.packs.struct.design import _rafter_bars  # pyright: ignore[reportPrivateUsage]
    from uea.packs.struct.frame import plane_frame
    from uea.packs.struct.kinds import Rafter

    # a couple roof 8 m wide at 35°: a three-hinged frame. Under q along the slope, w = q / cos α
    # on plan: M = w (L/2)² / 8 in each rafter, H = w L² / (8 f), N at the foot H cos α + V sin α
    span, rise = 8.0, 4.0 * math.tan(math.radians(35))
    nodes = {"TL": (0.0, 0.0), "FL": (0.0, 0.0), "R": (4.0, rise), "FR": (8.0, 0.0)}
    nodes["TR"] = (8.0, 0.0)
    el = model_from("rafter sp1 rf1 C24 b=0.08 h=0.2 e=0.8\n")["sp1"]
    assert isinstance(el, Rafter)
    fr = _rafter_bars(dict(nodes), el, rise / 4, ["w1", "w2"], span, 1.1e7)
    assert not isinstance(fr, str) and set(fr.nodes) == {"FL", "R", "FR"}
    a = math.atan(rise / 4)
    w = 2.0 / math.cos(a)
    eff, rx = plane_frame(
        fr.nodes, fr.bars, ["FL", "FR"], {"g": [(n, 0.0, -2.0) for n in fr.sides]}, {"c": {"g": 1}}
    )
    h = w * span**2 / (8 * rise)
    assert eff["c"]["Rl"].moment == pytest.approx(w * 4.0**2 / 8, rel=1e-6)
    assert rx["c"]["FL"] == (pytest.approx(h, rel=1e-6), pytest.approx(w * 4.0, rel=1e-6))
    assert eff["c"]["Rl"].compression == pytest.approx(
        h * math.cos(a) + w * 4.0 * math.sin(a), rel=1e-6
    )
    # a collar at half the rise: the rafter is nearly a beam over two spans of L/4 on plan,
    # w (L/4)² / 8 over the collar; the collar in compression
    el = model_from(f"rafter sp1 rf1 C24 b=0.08 h=0.2 e=0.8 collar={rise / 2}\n")["sp1"]
    assert isinstance(el, Rafter)
    fr = _rafter_bars(dict(nodes), el, rise / 4, ["w1", "w2"], span, 1.1e7)
    assert not isinstance(fr, str)
    eff, _ = plane_frame(
        fr.nodes, fr.bars, ["FL", "FR"], {"g": [(n, 0.0, -2.0) for n in fr.sides]}, {"c": {"g": 1}}
    )
    two = w * 2.0**2 / 8
    assert 0.9 * two < eff["c"]["Fl"].moment <= two
    assert eff["c"]["K"].compression > 0 and eff["c"]["K"].moment == pytest.approx(0, abs=1e-6)
    with pytest.raises(ValueError, match="give collar= too"):
        model_from("rafter sp1 rf1 C24 b=0.08 h=0.2 e=0.8 cb=0.06\n")


def test_rafters(tables: None) -> None:
    from uea.packs.struct.design import buckling

    text = HOUSE + ROOF + "rafter sp1 rf1 C24 b=0.08 h=0.2 e=0.8\n"
    text += "rafter sp2 rf1 C24 b=0.08 h=0.2 e=0.8 collar=1.5\n"
    d, _ = derive_text(text)
    o = run(STRUCT, d, None, sk=0.85, qp=0.5)
    pos = {p["id"]: k for k, p in o.data["positions"].items()}
    assert (pos["rf1"], pos["sp1"], pos["sp2"]) == ("1.01", "1.02", "1.03")
    sp1 = next(x for x in o.lines if " sp1 rafters" in x)
    assert sp1.startswith("1.02 sp1 rafters C24 8/20 e 0.8: η ") and sp1.endswith(" ok")
    assert "Sparren sp1" in o.report and "Horizontalschub am Fußpunkt" in o.report
    # k_c: λ_rel = λ / π · √(f_c,0,k / E_0,05), k = 0.5 (1 + β_c (λ_rel − 0.3) + λ_rel²)
    rel = 100 / math.pi * math.sqrt(21 / 7400)
    k = 0.5 * (1 + 0.2 * (rel - 0.3) + rel**2)
    assert buckling(100, 21, 7400, 0.2) == pytest.approx(1 / (k + math.sqrt(k * k - rel * rel)))
    assert buckling(10, 21, 7400, 0.2) == 1.0
    # a hip roof: its rafters are not proved
    d, _ = derive_text(
        HOUSE + ROOF.replace("gable ridge=x", "hip") + "rafter sp1 rf1 C24 b=0.08 h=0.2 e=0.8\n"
    )
    o = run(STRUCT, d, None, sk=0.85, qp=0.5)
    assert any("sp1 rafters: only the rafters of a gable roof" in x for x in o.lines)


# ---------- 8e: columns ----------

COLUMN = "beam bm1 OG S-160 a=W,S+4 b=E,S+4\ncolumn co1 EG C-140 at=W+5,S+4\n"


def test_columns(tables: None) -> None:
    from uea.packs.struct.design import buckling_chi

    d, rep = derive_text(HOUSE + COLUMN)
    assert [i.code for i in rep.issues if i.code.startswith("W-STRUCT")] == []
    # the beam rests on w4, the column and w2
    from uea.packs.struct.model import beam_bearings

    on = beam_bearings(d.arch, d.struct.beams["bm1"], d.struct)
    assert [k for k, _ in on] == ["w4", "co1", "w2"]
    o = run(LOADS, d, None, soil=200)
    assert o.ok, o.lines
    col = o.data["columns"]["co1"]
    reaction = o.data["beams"]["bm1"]["co1"]
    # from the EG's SSL -0.15 to sl2's underside 2.9 - 0.15 - 0.2 = 2.55: 2.70 m of 0.3 kN/m
    assert col["height"] == pytest.approx(2.7) and col["own"] == pytest.approx(0.81)
    assert col["G"] == pytest.approx(reaction["G"] + 0.81, abs=2e-3)
    assert col["Q"] == pytest.approx(reaction["Q"], abs=2e-3)
    assert col["to"] == "Einzelfundament"
    o = run(STRUCT, d, None, soil=200)
    pos = {(p["kind"], p["id"]): k for k, p in o.data["positions"].items()}
    # sl2, bm1, w1..w4, then the column; the pad after the four strip footings
    assert pos[("column", "co1")] == "2.07" and pos[("pad", "co1")] == "3.05"
    # i = √(500 / 40) cm, λ = 2.7 / i; λ̄ = λ / π · √(230 / 200000); χ by α = 0.49
    lam = 2.7 / math.sqrt(500e-8 / 40e-4)
    rel = lam / math.pi * math.sqrt(230 / 200000)
    phi = 0.5 * (1 + 0.49 * (rel - 0.2) + rel**2)
    chi = 1 / (phi + math.sqrt(phi**2 - rel**2))
    assert buckling_chi(lam, 230, 200000, 0.49) == (pytest.approx(chi), pytest.approx(rel))
    n_rd = chi * 40e-4 * 230 / 1.1 * 1000
    n_ed = 1.3 * col["G"] + 1.4 * col["Q"]
    line = next(x for x in o.lines if " co1 column" in x)
    assert f"N_Ed {n_ed:.1f}/N_b,Rd {n_rd:.1f} kN" in line and line.endswith(" ok")
    pad = next(x for x in o.lines if " co1 pad" in x)
    assert f"a ≥ {math.sqrt(n_ed / 200):.2f} m" in pad


def test_column_checks() -> None:
    _, rep = derive_text(HOUSE + "column co1 EG C-140 at=W+5,S+4\n")
    assert found(rep, "W-STRUCT-005") == ["co1"]
    # a beam from w4 that ends on a column: two supports
    _, rep = derive_text(
        HOUSE + "beam bm1 OG S-160 a=W,S+4 b=W+5,S+4\ncolumn co1 EG C-140 at=W+5,S+4\n"
    )
    assert found(rep, "W-STRUCT-003") == [] and found(rep, "W-STRUCT-005") == []

"""The structure pack (decision 0040): the load path's checks and `uea calc loads`, by hand on the
10 x 8 box of conftest with an OG of the same walls on top (h 2.5), slabs DE (0.2 concrete, 0.01
plaster) and floors FB (0.02 tiles, 0.13 screed), and synthetic tables of our own (not the
standard's values)."""

from pathlib import Path

import pytest

from tests.conftest import BOX, PROTOTYPE, Shell, derive_text
from tests.test_calc_elec import install, run
from tests.test_elec import found
from uea.packs.struct.loads import FACTORS, IMPOSED, LOADS, PARTITION, UNIT_WEIGHT

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
    "eps,0.3\nparkett,7\nosb,6\n"
)
IMPOSED_T = (
    "use,qk\nliving,1.5\nkitchen,1.5\nbedroom,1.5\nutility,2\nwc,1.5\nhall,2\nbath,1.5\nattic,1\n"
)
PARTS = "upto,qk\n4,0.7\n6,1.1\n"
FAC = "name,value\ngamma-g,1.3\ngamma-q,1.4\n"
SHARES = {"w1": 21.09 + 3, "w2": 13.69 + 2.22, "w3": 21.09 + 3, "w4": 13.69 + 2.22}
"""The 9.4 x 7.4 field inside the cores split at 45°: triangles of 7.4 · 3.7 / 2 = 13.69 m² at the
short sides, trapezoids of (69.56 - 2 · 13.69) / 2 = 21.09 m² at the long ones; each wall also
carries the slab over its own core: 10 x 0.3 = 3 and 7.4 x 0.3 = 2.22 m²."""


def near(v: float) -> object:
    """The data rounds to three decimals."""
    return pytest.approx(v, abs=2e-3)


@pytest.fixture
def tables(tmp_path: Path) -> None:
    for spec, text in (
        (UNIT_WEIGHT, WEIGHTS),
        (IMPOSED, IMPOSED_T),
        (PARTITION, PARTS),
        (FACTORS, FAC),
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
    install(PARTITION.id, PARTITION, "upto,qk\n4,0.7\n", tmp_path)
    o = run(LOADS, d, None)
    assert not o.ok and "w9: 4.81 kN/m, heavier than partition-load" in "\n".join(o.lines)


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
    o = run(LOADS, d, None)
    assert o.ok, o.lines
    w = o.data["walls"]
    # nothing is lost on the way down: the footings carry every load-bearing wall and every
    # slab but the ground slab
    base = sum(x["G"] for x in w.values() if x["level"] == "EG")
    own = sum(x["own"] for x in w.values())
    slabs = sum(s["G"] for k, s in o.data["slabs"].items() if k != "sl1")
    assert base == pytest.approx(own + slabs, abs=0.05)
    # the gable walls of the Spitzboden stand on the OG's west and east walls and corners
    assert set(w["w16"]["on"]) <= {"w8", "w10", "w11"} and "w11" in w["w16"]["on"]


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
    assert "uea calc loads" in out and "Details" not in out

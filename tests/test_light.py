"""Illuminance targets and the calculator `light` (decision 0050), hand-computed on the 10 x 8 box
house of test_elec with our own synthetic utilisation factors (they are not any maker's or the
LiTG's values)."""

import json
from pathlib import Path

import pytest

from tests.conftest import PROTOTYPE, Shell, derive_text, model_from
from tests.test_calc_elec import install, run
from tests.test_cli import build
from tests.test_elec import HOUSE
from uea.calc import data as norm_data
from uea.derive import Derived
from uea.packs.light.illuminance import LIGHT, UF, factor, room_index

TYPES = (
    'type DK lum "Deckenleuchte" flux=2000 w=20 dist=cos1 default\n'
    'type DX lum "ohne Verteilung" flux=1000 w=10\n'
)
# cos1 at 753: 0.60 at k 2, 0.65 at 2.5, 0.70 at 3, 0.75 at 4
UFS = """\
# synthetic test values, not any maker's or the LiTG's
dist,refl,k,uf
cos1,753,2,0.60
cos1,753,2.5,0.65
cos1,753,3,0.70
cos1,753,4,0.75
cos1,551,2,0.5
"""
TWO = "lum l1 r1\nlum l2 r1 at=W+3,S+2 z=2\n"


def house(extra: str) -> Derived:
    d, rep = derive_text(HOUSE + TYPES + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d


def test_room_index_and_factor(tmp_path: Path) -> None:
    # a rectangle: 2 a b / (h 2 (a + b)) = a b / (h (a + b)); 4 x 3 at 2 m: 12 / 14
    assert room_index(12, 14, 2) == pytest.approx(12 / 14)
    table, errors = norm_data.add(UF, _csv(tmp_path, UFS), "synthetic")
    assert table is not None, errors
    assert factor(table, "cos1", "753", 3) == pytest.approx(0.70)
    assert factor(table, "COS1", "753", 2.5) == pytest.approx(0.65)
    assert factor(table, "cos1", "753", 3.5) == pytest.approx(0.725)
    # outside the table, or a single row away from k: no value
    assert factor(table, "cos1", "753", 1.9) is None
    assert factor(table, "cos1", "753", 4.1) is None
    assert factor(table, "cos1", "551", 2) == pytest.approx(0.5)
    assert factor(table, "cos1", "551", 2.2) is None
    assert factor(table, "cos3", "753", 3) is None


def _csv(tmp_path: Path, text: str) -> Path:
    f = tmp_path / "uf.csv"
    f.write_text(text)
    return f


def test_average_illuminance_of_a_room(tmp_path: Path) -> None:
    install("uf", UF, UFS, tmp_path)
    d = house(TWO + "illum il1 r1 em=100 h=0.75\n")
    o = run(LIGHT, d, refl=753, mf=0.8)
    r = o.data["targets"]["il1"]
    # r1 finished: 9.38 x 7.38 = 69.2244 m², perimeter 33.52 m, ceiling at 2.54 m
    assert (r["area"], r["perimeter"]) == (pytest.approx(69.2244), pytest.approx(33.52))
    l1, l2 = r["lums"]
    # l1 at the ceiling: h = 2.54 - 0.75 = 1.79; k = 69.2244 / (1.79 * 16.76) = 2.307449;
    # uf = 0.60 + 0.05 * 0.307449 / 0.5 = 0.630745
    assert (l1["h"], l1["k"], l1["uf"]) == (1.79, 2.3074, 0.6307)
    # l2 at 2 m: h = 1.25, k = 69.2244 / (1.25 * 16.76) = 3.30427; uf = 0.70 + 0.05 * 0.30427
    assert (l2["h"], l2["k"], l2["uf"]) == (1.25, pytest.approx(3.3043, abs=1e-4), 0.7152)
    # E = 0.8 * (2000 * 0.630745 + 2000 * 0.7152135) / 69.2244 = 31.1095 lx
    assert r["e"] == pytest.approx(31.11, abs=0.01)
    assert r["status"] == "low" and not o.ok
    # l2 brings the most to the plane, 1430.43 lm: (100 - 31.1095) * 69.2244 / (0.8 * 1430.43)
    # = 4.17, so 5 more DK at its height
    assert r["add"] == {"type": "DK", "n": 5}
    # 40 W on 69.2244 m²
    assert r["w_m2"] == pytest.approx(0.578, abs=1e-3)
    assert o.lines == [
        "1 rooms: 0 ok, 1 low",
        "il1 r1: 31 lx < 100 on 0.75 m, 2 lum, 0.6 W/m²; add 5 DK",
    ]
    assert "| il1 | r1 | Wohnen | 69,22 | 0,75 | 2 | 31 | 100 | 0,6 |" in o.report
    assert "**nicht erfüllt**; 5 × DK ergänzen |" in o.report
    assert o.tables[0].startswith("light-uf (luminaire maker's data or LiTG-Publikation 3.5)")
    # a lower target is met; a lower maintenance factor halves the result
    o = run(LIGHT, house(TWO + "illum il1 r1 em=30 h=0.75\n"), refl=753, mf=0.8)
    assert o.ok and o.lines[1] == "il1 r1: 31 lx ≥ 30 on 0.75 m, 2 lum, 0.6 W/m²"
    o = run(LIGHT, house(TWO + "illum il1 r1 em=30 h=0.75\n"), refl=753, mf=0.4)
    assert o.data["targets"]["il1"]["e"] == pytest.approx(31.11 / 2, abs=0.01)


def test_a_room_without_luminaires_takes_the_default_type(tmp_path: Path) -> None:
    install("uf", UF, UFS, tmp_path)
    o = run(LIGHT, house("illum il1 r1 em=100 h=0.75\n"), refl=753, mf=0.8)
    r = o.data["targets"]["il1"]
    # the default DK at the ceiling, uf 0.630745: 100 * 69.2244 / (0.8 * 1261.49) = 6.86, so 7
    assert (r["e"], r["status"], r["add"]) == (0, "low", {"type": "DK", "n": 7})
    assert r["w_m2"] is None


def test_what_the_calculator_cannot_compute(tmp_path: Path) -> None:
    install("uf", UF, UFS, tmp_path)
    # a type without dist=, and reflectances the table does not have
    d = house(TWO + "lum l3 r1 at=W+5,S+5 type=DX\nillum il1 r1 em=100 h=0.75\n")
    o = run(LIGHT, d, refl=753, mf=0.8)
    r = o.data["targets"]["il1"]
    assert r["status"] == "nodata" and not o.ok and r["add"] is None
    assert o.lines[1].endswith("without data: l3 type DX has no dist=")
    o = run(LIGHT, house(TWO + "illum il1 r1 em=100 h=0.75\n"), refl=551, mf=0.8)
    assert o.lines[1] == (
        "il1 r1: 0 lx of 100, without data: l1 no row of light-uf for cos1 551 around k 2.31;"
        " l2 no row of light-uf for cos1 551 around k 3.30"
    )
    # a pendant at or below the working plane adds nothing and is named
    d = house(TWO + "lum l3 r1 at=W+5,S+5 z=0.7\nillum il1 r1 em=30 h=0.75\n")
    o = run(LIGHT, d, refl=753, mf=0.8)
    assert o.data["targets"]["il1"]["lums"][2]["note"] == "not above the working plane"
    assert o.ok and o.lines[1].endswith("(l3 below the plane)")
    assert "nicht über der Nutzebene, nicht gerechnet" in o.report


def test_task_areas_scopes_and_settings(tmp_path: Path) -> None:
    d = house(
        TWO
        + 'illum il1 r1 em=30 h=0.75\nillum il2 r1 em=500 h=0.75 at=W+3,S+2 area=1.8x0.9 "Tisch"\n'
    )
    with pytest.raises(norm_data.MissingTable, match="uea data add light-uf"):
        run(LIGHT, d, refl=753, mf=0.8)
    install("uf", UF, UFS, tmp_path)
    o = run(LIGHT, d, refl=753, mf=0.8)
    assert o.lines[0] == "1 rooms: 1 ok, 0 low; 1 task areas not checked (point calculation)"
    assert o.data["tasks"] == ["il2"] and o.ok
    assert "- il2 in r1: 500 lx auf 0,75 m, Sehaufgabenbereich 1,80 × 0,90 m (Tisch)" in o.report
    for scope in ("r1", "EG", "il1"):
        assert list(run(LIGHT, d, scope, refl=753, mf=0.8).data["targets"]) == ["il1"]
    with pytest.raises(ValueError, match="'zz' is not a room, a storey or an illuminance"):
        run(LIGHT, d, "zz", refl=753, mf=0.8)
    with pytest.raises(ValueError, match="there are no illuminance targets"):
        run(LIGHT, house(TWO), refl=753, mf=0.8)
    with pytest.raises(ValueError, match="mf must be more than 0 and at most 1"):
        run(LIGHT, d, refl=753, mf=1.2)
    with pytest.raises(ValueError, match="light needs refl=<value>"):
        run(LIGHT, d, mf=0.8)


def test_targets_are_checked() -> None:
    for line, message in (
        ("illum il1 r1 em=0 h=0.75", "em must be larger than 0"),
        ("illum il1 r1 em=100 h=0.75 at=W+1,S+1", "a task area needs both at= and area="),
        ("illum il1 r1 em=100 h=0.75 area=1x1", "a task area needs both at= and area="),
    ):
        with pytest.raises(ValueError, match=message):
            model_from(HOUSE + line + "\n")


def test_haus_mueller_dining_room(tmp_path: Path) -> None:
    install("uf", UF, UFS + "cos1,753,1,0.45\ncos3,753,1,0.55\ncos3,753,2,0.7\n", tmp_path)
    lines: list[str] = []
    for name in ("project", "arch", "light", "elec"):
        for line in (PROTOTYPE / f"{name}.uea").read_text().splitlines():
            if line.split(" ")[0] != "feed":
                lines.append(line)
    d, rep = derive_text("\n".join(lines) + "\n")
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    o = run(LIGHT, d, refl=753, mf=0.8)
    # the general target of r2 is computed, the dining table is a task area
    assert list(o.data["targets"]) == ["il1"] and o.data["tasks"] == ["il2"]
    r = o.data["targets"]["il1"]
    # r2: 6.235 x 4.48 = 27.9328 m², perimeter 21.43 m, six luminaires
    assert r["area"] == pytest.approx(27.9328) and len(r["lums"]) == 6
    # the pendant l2 PL-12 at 1.6 m: h 0.85, k = 27.9328 / (0.85 * 10.715) = 3.066948, cos1:
    # uf 0.70 + 0.05 * 0.066948 = 0.703347, 844.02 lm
    pendant = r["lums"][0]
    assert (pendant["id"], pendant["k"], pendant["uf"]) == ("l2", 3.0669, 0.7033)
    # at the ceiling, 2.515 m: h 1.765, k 1.476991. l3 DK-18 1800 lm cos1: uf 0.45 + 0.15 *
    # 0.476991 = 0.521549, 938.79 lm; four DL-11 1050 lm cos3: uf 0.621549, 4 * 652.63 lm.
    # E = 0.8 * (844.02 + 938.79 + 2610.50) / 27.9328 = 125.83 lx < 150
    assert r["e"] == pytest.approx(125.83, abs=0.01) and r["status"] == "low"
    # l3 brings the most: (150 - 125.83) * 27.9328 / (0.8 * 938.79) = 0.9, one more DK-18
    assert r["add"] == {"type": "DK-18", "n": 1}


def test_the_command(sh: Shell, tmp_path: Path) -> None:
    build(sh)
    batch = "".join(f"+ {x}\n" for x in TYPES.splitlines()) + (
        "+ lum _ r1\n+ illum _ r1 em=10 h=0.75\n"
    )
    code, out = sh("apply", "--by", "t", "-m", "Licht", stdin=batch)
    assert code == 0, out
    code, out = sh("calc", "light", "refl=753", "mf=0.8")
    assert code == 1 and out.startswith("light: the table 'light-uf'")
    f = tmp_path / "uf.csv"
    f.write_text(UFS)
    assert sh("data", "add", "light-uf", str(f), "--edition", "synthetic")[0] == 0
    code, out = sh("calc", "light", "refl=753", "mf=0.8")
    assert code == 0, out
    head, summary = out.splitlines()[:2]
    assert head.startswith("norm light 0.1.0 · Mittlere Beleuchtungsstärke")
    assert summary == "1 rooms: 1 ok, 0 low"
    rec = json.loads((sh.root / "out" / "light.json").read_text())
    assert rec["inputs"]["settings"] == {"refl": "753", "mf": 0.8}
    assert rec["tables"][0].startswith("light-uf (luminaire maker's data")

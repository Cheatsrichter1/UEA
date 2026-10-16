"""The LV: numbers, quantities, prices, checks and the exports (decision 0048).

On the box of test_tables: four exterior walls 2.7 m high, w1 and w3 10 m long, w2 and w4 7.4 m
between them; a door of 1 x 2.01 in w1, a window of 1.2 x 1.2 in w3; one room, 9.38 x 7.38
between the finished faces, with the floor type FB. Prices and texts are made up.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tests.conftest import Shell, derive_text, model_from
from tests.test_calc_elec import install
from tests.test_tables import HOUSE, H
from uea.batch import run, sync
from uea.derive import Derived, Report
from uea.export.gaeb import NS, gaeb_xml
from uea.export.lv import TEXTS, build, lv_tables
from uea.project import Project

LV = """\
title T01 "Rohbau"
title T02 "Ausbau"
pos p1 T01 area sel="wall ext" "Außenwand" kg=331 ep=100
pos p2 T01 vol sel="wall" "Mauerwerk Kernvolumen" kg=331
pos p3 T02 n sel="win" "Fenster" ep=500 kg=334 text=FE-01
pos p4 T02 area sel="room floor=FB" "Bodenbelag" kg=352
pos p5 T01 fix=1 unit=psch "Baustelleneinrichtung" ep=2000 kg=391
"""
NET = 34.8 * H - 2.01 - 1.44
"""The exterior walls: (10 + 7.4 + 10 + 7.4) x 2.7 less the door and the window: 90.51 m²."""
FLOOR = 9.38 * 7.38
"""The room between the finished faces: 69.2244 m²."""


def lv(extra: str = "") -> tuple[Derived, Report]:
    return derive_text(HOUSE + LV + extra)


def codes(rep: Report) -> list[tuple[str, str]]:
    return sorted((i.code, i.el) for i in rep.issues if "LV" in i.code)


def test_numbers_and_quantities() -> None:
    d, rep = lv()
    assert codes(rep) == []
    g = d.lv
    # titles by their names, positions by their ids within each title
    assert g.oz == {
        "T01": "01",
        "T02": "02",
        "p1": "01.0010",
        "p2": "01.0020",
        "p5": "01.0030",
        "p3": "02.0010",
        "p4": "02.0020",
    }
    assert g.qty["p1"].value == pytest.approx(NET)
    assert g.qty["p1"].unit == "m2"
    assert g.qty["p1"].counted == ["w1", "w2", "w3", "w4"]
    assert g.qty["p2"].value == pytest.approx(NET * 0.3)  # 27.153 m³ of 0.3 m cores
    assert (g.qty["p3"].value, g.qty["p3"].unit) == (1, "St")
    assert g.qty["p4"].value == pytest.approx(FLOOR)
    assert (g.qty["p5"].value, g.qty["p5"].unit) == (1, "psch")


def test_get_shows_number_quantity_and_price() -> None:
    from uea.cli import describe

    d, _ = lv()
    assert describe(d, d.model["p1"]) == ["01.0010 · 90.510 m2 · 9051.00 €", "counts 4: w1-w4"]
    assert describe(d, d.model["p5"]) == ["01.0030 · 1 psch · 2000.00 €"]
    # T01: p1 9051 and p5 2000; p2 has no price
    assert describe(d, d.model["T01"]) == ["01 · 3 positions · 11051.00 € for 2 priced"]


def test_pinned_numbers() -> None:
    d, rep = lv('title T03 "Technik" oz=07\npos p6 T03 n sel="door" "Türen" oz=0100\n')
    assert d.lv.oz["T03"] == "07"
    assert d.lv.oz["p6"] == "07.0100"
    assert codes(rep) == []
    _, rep = lv('pos p6 T01 n sel="door" "Türen" oz=0010\n')
    assert codes(rep) == [("E-LV-004", "p6")]


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('pos p6 T01 vol sel="win" "x"', "a win has no measure vol; it has n area"),
        ('pos p6 T01 n sel="pipe" "x"', "unknown kind 'pipe'"),
        ('pos p6 T01 n sel="wall \'ext" "x"', "cannot be read"),
    ],
)
def test_selectors_and_measures_that_cannot_be_used(line: str, message: str) -> None:
    _, rep = lv(line + "\n")
    bad = [i for i in rep.issues if i.code == "E-LV-001"]
    assert len(bad) == 1 and bad[0].el == "p6" and message in bad[0].msg


def test_nothing_twice_and_missing() -> None:
    _, rep = lv(
        'pos p6 T01 n sel="sock" "Steckdosen" kg=444\n'  # there are none
        'pos p7 T01 area sel="wall type=AW" "Doppelt"\n'  # the same walls as p1
        'pos p8 T01 area sel="wall level=OG" "Oben"\n'
        "wall w9 OG AW y=S+ x=W..E\n"  # no storey and no roof above: no height yet
    )
    assert ("W-LV-002", "p6") in codes(rep)
    assert ("W-LV-003", "p7") in codes(rep)
    assert ("W-LV-005", "p8") in codes(rep)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('pos p6 T01 n sel="win"', "needs its short text"),
        ('pos p6 T01 fix=1 "x"', "fix= needs unit"),
        ('pos p6 T01 n sel="win" fix=1 unit=St "x"', "either fix= or a measure"),
        ('pos p6 T01 "x"', "give a measure"),
        ('pos p6 T01 n sel="win" kg=42 "x"', "not a DIN 276 cost group"),
        ('pos p6 T01 n sel="win" unit=St "x"', "unit= is for fix="),
        ('title T09 "x" oz=A1', "1 to 4 digits"),
    ],
)
def test_bad_lines(line: str, message: str) -> None:
    with pytest.raises(Exception, match=message):
        model_from(line)


def test_a_batch_says_which_positions_follow(empty: Project) -> None:
    m = model_from(HOUSE + LV)
    empty.write(m, m.packs())
    with empty.lock():
        sync(empty)
    res = run(empty, "~ f1 1.5x1.2", "arch", "größeres Fenster")
    assert res.ok
    assert "p1" in res.follows and "p2" in res.follows
    assert "p3" not in res.follows


def test_gaeb(tmp_path: Path) -> None:
    install("texts", TEXTS, 'key,text\nFE-01,"Fenster liefern.|Einbau nach RAL."\n', tmp_path)
    d, rep = lv()
    xml = gaeb_xml(build(d, rep), "box", "Box")
    root = ET.fromstring(xml)
    n = {"g": NS}
    assert root.tag == f"{{{NS}}}GAEB"
    assert root.findtext("g:Award/g:DP", namespaces=n) == "83"
    ctgy = root.findall(".//g:BoQCtgy", n)
    assert [c.get("RNoPart") for c in ctgy] == ["01", "02"]
    items = {i.get("ID"): i for i in root.iterfind(".//g:Item", n)}
    assert list(items) == ["UEA_p1", "UEA_p2", "UEA_p5", "UEA_p3", "UEA_p4"]
    p1 = items["UEA_p1"]
    assert (p1.get("RNoPart"), p1.findtext("g:Qty", namespaces=n)) == ("0010", "90.510")
    assert p1.findtext("g:QU", namespaces=n) == "m2"
    short = p1.find(".//g:TextOutlTxt/g:p/g:span", n)
    assert short is not None and short.text == "Außenwand"
    long = [s.text for s in items["UEA_p3"].iterfind(".//g:DetailTxt//g:span", n)]
    assert long == ["Fenster liefern.", "Einbau nach RAL."]
    # bidders get no prices
    assert root.find(".//g:UP", n) is None and root.find(".//g:IT", n) is None


def test_xlsx_sheets() -> None:
    d, _ = lv()
    sheet, costs = lv_tables(d)
    assert [r[0] for r in sheet.rows] == [
        "01",
        "01.0010",
        "01.0020",
        "01.0030",
        "02",
        "02.0010",
        "02.0020",
    ]
    assert sheet.rows[0][6] == pytest.approx(11051)  # title T01
    assert sheet.total is not None and sheet.total[6] == pytest.approx(11551)
    assert costs.rows == [[331, 1, pytest.approx(9051)], [334, 1, 500], [391, 1, 2000]]


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    m = model_from(HOUSE)
    Project(sh.root).write(m, m.packs())
    sh("log")  # records the files written by hand as batch 1
    assert (
        sh("export", "gaeb")[1]
        == "no LV positions yet: add titles and positions to lv (uea help lv)\n"
    )
    ops = "\n".join("+ " + x for x in LV.replace("p1", "_").splitlines() if x.startswith("title"))
    ops += '\n+ pos _ T01 area sel="wall ext" "Außenwand" text=AW-01\n'
    code, text = sh("apply", "--by", "lv", "-m", "LV", stdin=ops)
    assert code == 0, text
    code, text = sh("export", "gaeb")
    assert code == 0
    assert text.splitlines() == [
        "p/out/box.x83 GAEB DA XML 3.3 (83): 2 titles, 1 position, no prices",
        "no long text (table lv-texts not installed): p1",
    ]
    assert (sh.root / "out" / "box.x83").read_bytes().startswith(b"<?xml")
    code, text = sh("get", "p1")
    assert " 01.0010 · 90.510 m2" in text

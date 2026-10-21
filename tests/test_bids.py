"""Bids: reading GAEB 84, the arithmetic check, the comparison and the Kostenanschlag (0051).

On the LV of test_lv: p1 90.51 m² exterior wall, p2 27.153 m³ masonry, p5 1 psch site setup
(title T01), p3 1 window, p4 69.2244 m² floor (T02); the bidders price the quantities of the
phase 83 file, with three decimals (p4: 69.224). The bids are made up:

    bd1 Muster Bau GmbH, 2 % off   bd2 Beispiel AG
    p1  110 → 9956.10              100 → 9051.00 (states 9100.00)
    p2  300 → 8145.90              280 → 7602.84
    p5 2500 → 2500.00             3000 → 3000.00
    p3  450 →  450.00              900 →  900.00
    p4   40 → 2768.96               38 → 2630.51 (69.224 × 38 = 2630.512)
    sum      23820.96                    23184.35 (states 23233.35)
    net      23344.5408                  23184.35
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tests.conftest import Shell, derive_text, model_from
from tests.test_calc_elec import run
from tests.test_lv import HOUSE, LV, lv
from uea.calc.bids import BIDS
from uea.calc.din276 import COSTS
from uea.derive import Derived, Report
from uea.export.gaeb import NS, gaeb_xml
from uea.export.lv import build
from uea.importer.gaeb import NotImportable, plan, read
from uea.project import Project

BD1: dict[str, float] = {"p1": 110, "p2": 300, "p5": 2500, "p3": 450, "p4": 40}
BD2: dict[str, float] = {"p1": 100, "p2": 280, "p5": 3000, "p3": 900, "p4": 38}
SUM1 = 9956.10 + 8145.90 + 2500 + 450 + 2768.96
SUM2 = 9051.00 + 7602.84 + 3000 + 900 + 2630.51

PRICES = """\
bid bd1 "Muster Bau GmbH" date=2026-11-02 total=23820.96 disc=2
bid bd2 "Beispiel AG" total=23233.35
price pr1 bd1 p1 ep=110 qty=90.51
price pr2 bd1 p2 ep=300 qty=27.153
price pr3 bd1 p5 ep=2500 qty=1
price pr4 bd1 p3 ep=450 qty=1
price pr5 bd1 p4 ep=40 qty=69.224
price pr6 bd2 p1 ep=100 qty=90.51 gp=9100
price pr7 bd2 p2 ep=280 qty=27.153
price pr8 bd2 p5 ep=3000 qty=1
price pr9 bd2 p3 ep=900 qty=1
price pr10 bd2 p4 ep=38 qty=69.224
"""


def bids(extra: str = "") -> tuple[Derived, Report]:
    return derive_text(HOUSE + LV + PRICES + extra)


def x84(
    prices: dict[str, float],
    bidder: str | None = "Muster Bau GmbH",
    *,
    ids: bool = True,
    it: dict[str, float] | None = None,
    total: float | None = None,
    disc: float | None = None,
) -> bytes:
    """The phase 83 file of the box as a bidder returns it: phase 84 with unit prices."""
    d, rep = lv()
    root = ET.fromstring(gaeb_xml(build(d, rep), "box", "Box"))
    n = {"g": NS}
    dp = root.find("g:Award/g:DP", n)
    assert dp is not None
    dp.text = "84"
    award = root.find("g:Award", n)
    assert award is not None
    if bidder is not None:
        ctr = ET.SubElement(ET.SubElement(award, f"{{{NS}}}CTR"), f"{{{NS}}}Address")
        ET.SubElement(ctr, f"{{{NS}}}Name1").text = bidder
    info = root.find(".//g:BoQInfo", n)
    assert info is not None
    totals = ET.SubElement(info, f"{{{NS}}}Totals")
    if total is not None:
        ET.SubElement(totals, f"{{{NS}}}Total").text = f"{total:.2f}"
    if disc is not None:
        ET.SubElement(totals, f"{{{NS}}}DiscountPcnt").text = f"{disc:g}"
    for item in root.iterfind(".//g:Item", n):
        pid = str(item.get("ID"))[4:]
        if not ids:
            del item.attrib["ID"]
        if pid in prices:
            qty = float(str(item.findtext("g:Qty", namespaces=n)))
            up = ET.Element(f"{{{NS}}}UP")
            up.text = f"{prices[pid]:.2f}"
            item.insert(2, up)
            gp = (it or {}).get(pid, round(qty * prices[pid], 2))
            el = ET.Element(f"{{{NS}}}IT")
            el.text = f"{gp:.2f}"
            item.insert(3, el)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def codes(rep: Report) -> list[tuple[str, str]]:
    return sorted((i.code, i.el) for i in rep.issues if "BID" in i.code or "REF" in i.code)


# ---------- the model ----------


def test_checked_sums_and_checks() -> None:
    d, rep = bids()
    s1, s2 = d.bid.bids["bd1"], d.bid.bids["bd2"]
    assert s1.checked == pytest.approx(SUM1)
    assert s1.net == pytest.approx(SUM1 * 0.98)  # 23344.5408
    assert s2.checked == pytest.approx(SUM2)
    assert s1.titles == s2.titles == ["T01", "T02"]
    assert s1.by_title["T01"] == pytest.approx(9956.10 + 8145.90 + 2500)
    # bd2 states 9100 for p1 and a total with it; the unit price counts
    assert codes(rep) == [("W-BID-004", "pr6"), ("W-BID-005", "bd2")]
    w4 = next(i for i in rep.issues if i.code == "W-BID-004")
    assert (
        w4.msg
        == "bd2 states 9100.00 € for p1, but 90.510 × 100.00 = 9051.00 €; the unit price counts"
    )
    assert w4.rule == "VOB/A § 16c Abs. 2 Nr. 1"


def test_incomplete_and_changed_quantities() -> None:
    # bd3 bids on T02 only and leaves p4 out; a second window makes p3 two
    d, rep = bids(
        'bid bd3 "Elektro Klein"\nprice pr11 bd3 p3 ep=480 qty=1\nwin f2 w3 1.2x1.2 x=W+6\n'
    )
    assert d.bid.bids["bd3"].titles == ["T02"]
    assert d.bid.bids["bd3"].unpriced == ["p4"]
    assert ("W-BID-002", "bd3") in codes(rep)
    changed = [i for i in rep.issues if i.code == "W-BID-003"]
    assert {i.el for i in changed} == {"bd1", "bd2", "bd3"}
    assert all("p3" in i.others for i in changed)


def test_get_shows_the_bids() -> None:
    from uea.cli import describe

    d, _ = bids()
    assert describe(d, d.model["bd1"]) == [
        "5 prices · 23820.96 € · 2 % off 23344.54 €",
        "titles: T01 T02",
    ]
    assert describe(d, d.model["pr10"]) == ["02.0020 · 69.224 × 38.00 = 2630.51 €"]
    assert describe(d, d.model["p1"])[-1] == "bids: bd1 110.00 · bd2 100.00"


def test_a_removed_position_leaves_its_prices_dangling() -> None:
    """Removing a priced position is an error on its prices, not on the LV's batch."""
    gone = LV.replace('pos p4 T02 area sel="room floor=FB" "Bodenbelag" kg=352\n', "")
    d, rep = derive_text(HOUSE + gone + PRICES)
    assert ("E-REF-001", "pr5") in codes(rep) and ("E-REF-001", "pr10") in codes(rep)
    # the checked sum keeps the bidder's own quantity and price
    assert d.bid.bids["bd1"].checked == pytest.approx(SUM1)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("bid bd1", "needs its bidder"),
        ('bid bd1 "x" disc=100', "percentage"),
        ('bid bd1 "x" date=2.11.2026', "YYYY-MM-DD"),
        ("price pr1 bd1 p1 ep=-1", "ep must be 0 or more"),
    ],
)
def test_bad_lines(line: str, message: str) -> None:
    with pytest.raises(Exception, match=message):
        model_from(line)


# ---------- reading GAEB 84 ----------


def test_read_and_plan(tmp_path: Path) -> None:
    f = tmp_path / "muster.x84"
    f.write_bytes(x84(BD1, total=SUM1, disc=2))
    offer = read(f)
    assert (offer.phase, offer.bidder, offer.total, offer.disc) == (
        "84",
        "Muster Bau GmbH",
        pytest.approx(SUM1),
        2,
    )
    assert [i.oz for i in offer.items] == ["01.0010", "01.0020", "01.0030", "02.0010", "02.0020"]
    d, _ = lv()
    pl = plan(offer, d, None)
    assert pl.text.splitlines() == [
        f'+ bid @b "Muster Bau GmbH" date={offer.date} total=23820.96 disc=2 file=muster.x84',
        "+ price _ @b p1 ep=110 qty=90.51",
        "+ price _ @b p2 ep=300 qty=27.153",
        "+ price _ @b p5 ep=2500 qty=1",
        "+ price _ @b p3 ep=450 qty=1",
        "+ price _ @b p4 ep=40 qty=69.224",
    ]


def test_by_number_and_what_is_left_out(tmp_path: Path) -> None:
    """Without UEA's item ids the numbers match; an item the LV lacks is skipped, a missing
    unit price noted, a total price that is not qty × ep kept as gp=."""
    xml = x84({"p1": 100.0, "p3": 900.0}, ids=False, it={"p1": 9100})
    root = ET.fromstring(xml)
    items = root.find(f".//{{{NS}}}Itemlist")
    assert items is not None
    extra = ET.SubElement(items, f"{{{NS}}}Item", RNoPart="0040")
    ET.SubElement(extra, f"{{{NS}}}Qty").text = "3"
    f = tmp_path / "b.x84"
    f.write_bytes(ET.tostring(root))
    d, _ = lv()
    pl = plan(read(f), d, None)
    assert "+ price _ @b p1 ep=100 qty=90.51 gp=9100" in pl.text
    assert "+ price _ @b p3 ep=900 qty=1" in pl.text
    assert pl.prices == 2
    assert pl.skipped == ["01.0040"]
    assert pl.notes == ["no unit price in the file: p2 p5 p4"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("83", "phase 83, the request for bids"),
        ("nobody", "names no bidder"),
        ("noprice", "prices no position"),
        ("junk", "is not XML"),
    ],
)
def test_files_that_cannot_be_read(tmp_path: Path, change: str, message: str) -> None:
    f = tmp_path / "b.x84"
    if change == "83":
        d, rep = lv()
        f.write_bytes(gaeb_xml(build(d, rep), "box", "Box"))
    elif change == "nobody":
        f.write_bytes(x84(BD1, bidder=None))
    elif change == "noprice":
        f.write_bytes(x84({}))
    else:
        f.write_text("not xml")
    d, _ = lv()
    with pytest.raises(NotImportable, match=message):
        plan(read(f), d, None)


# ---------- the comparison ----------


def test_comparison() -> None:
    d, _ = bids()
    o = run(BIDS, d)
    assert o.lines == [
        "bd1 Muster Bau GmbH: 23820.96 € · 2 % off 23344.54 € · rank 2 of 2",
        "bd2 Beispiel AG: 23184.35 € · rank 1 of 2",
        "bd2: total price of p1 is not qty × ep; the ep counts",
        "bd2: states 23233.35 €, checked 23184.35 €",
        # the office's own prices: p1 9051 + p5 2000; p3 500
        "T01 Rohbau: bd2 19653.84 · bd1 20602.00 · LV 11051.00",
        "T02 Ausbau: bd1 3218.96 · bd2 3530.51 · LV 500.00",
        # p3: 450 and 900 around the median 675, a third off each way
        "p3: bd1 450.00 is -33 % on the median 675.00",
        "p3: bd2 900.00 is +33 % on the median 675.00",
    ]
    assert [b["rank"] for b in o.data["bids"]] == [2, 1]
    assert "Preisspiegel" in o.report and "der Einheitspreis ist maßgebend" in o.report
    # a looser threshold flags nothing
    assert not run(BIDS, d, dev=40).data["flags"]


def test_an_incomplete_bid_is_not_ranked() -> None:
    d, _ = bids('bid bd3 "Elektro Klein"\nprice pr11 bd3 p3 ep=480 qty=1\n')
    lines = run(BIDS, d).lines
    assert lines[0].endswith("rank 2 of 2 · on T01 T02")
    assert "bd3 Elektro Klein: 480.00 € · incomplete, not ranked: no price for p4 · on T02" in lines
    # one title: only its line, and the bids on it
    o = run(BIDS, d, "T02")
    assert "T02 Ausbau: bd3 480.00 · bd1 3218.96 · bd2 3530.51 · LV 500.00" in o.lines
    assert not any(x.startswith("T01") for x in o.lines)
    with pytest.raises(ValueError, match="unknown title"):
        run(BIDS, d, "T9")


# ---------- the Kostenanschlag ----------


def test_kostenanschlag() -> None:
    d, _ = bids()
    rows = run(COSTS, d, stage="offer", bid="bd2").data["rows"]
    # the model's quantities times bd2's prices: p4 69.2244 × 38 = 2630.5272
    assert [(r["kg"], r["source"], r["cost"]) for r in rows] == [
        (331, "bd2", pytest.approx(9051 + 27.153 * 280)),
        (334, "bd2", 900),
        (352, "bd2", pytest.approx(2630.53)),
        (391, "bd2", 3000),
    ]
    # bd1 less its 2 %
    rows = run(COSTS, d, stage="offer", bid="bd1").data["rows"]
    assert rows[0]["cost"] == pytest.approx((9956.1 + 8145.9) * 0.98)
    o = run(COSTS, d, stage="offer", bid="bd2")
    assert "# Kostenanschlag nach DIN 276" in o.report
    assert "Angebot bd2 (Beispiel AG)" in o.report


def test_kostenanschlag_from_part_of_the_lv() -> None:
    """A bid on one position; the office's own prices for the rest, where it has them."""
    d, _ = bids('bid bd3 "Elektro Klein"\nprice pr11 bd3 p3 ep=480 qty=1\n')
    o = run(COSTS, d, stage="offer", bid="bd3")
    assert [(r["kg"], r["source"], r["cost"]) for r in o.data["rows"]] == [
        (331, "lv", pytest.approx(9051)),
        (334, "bd3", 480),
        (391, "lv", 2000),
    ]
    assert o.data["notes"] == ["no price (ep= or a bid awarded), not in it: p2 p4"]


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({"stage": "offer"}, "needs bid="),
        ({"stage": "offer", "bid": "bd7"}, "no such bid"),
        ({"stage": "offer", "bid": "bd1,bd2"}, "bd1 and bd2 both price p1"),
        ({"stage": "estimate", "bid": "bd1"}, "bid= is for stage=offer"),
    ],
)
def test_kostenanschlag_needs_the_bids(given: dict[str, str], message: str) -> None:
    d, _ = bids()
    with pytest.raises(ValueError, match=message):
        run(COSTS, d, **given)


# ---------- on the command line ----------


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    m = model_from(HOUSE + LV)
    Project(sh.root).write(m, m.packs())
    sh("log")
    f = tmp_path / "beispiel.x84"
    f.write_bytes(x84(BD2, "Beispiel AG", it={"p1": 9100}, total=23233.35))
    code, text = sh("import", "gaeb", str(f), "--by", "lv")
    assert code == 0, text
    assert text.splitlines() == [
        "beispiel.x84: GAEB DA XML (84): ok (batch 2): bd1, 5 prices, 23184.35 € checked",
        "W-BID-004 pr1 bd1 states 9100.00 € for p1, but 90.510 × 100.00 = 9051.00 €; the unit"
        " price counts [VOB/A § 16c Abs. 2 Nr. 1]. Fix: uea calc bids uses the unit price;"
        " tell the bidder",
        "W-BID-005 bd1 states a total of 23233.35 €, its prices give 23184.35 €"
        " [VOB/A § 16c Abs. 2 Nr. 1]. Fix: uea calc bids uses the checked sum; tell the bidder",
    ]
    assert (sh.root / "bid.uea").read_text().startswith('bid bd1 "Beispiel AG"')
    code, text = sh("import", "gaeb", str(f), "--by", "lv")
    assert code == 1 and "is in the model as bd1" in text
    code, text = sh("calc", "bids")
    assert code == 0, text
    assert "bd1 Beispiel AG: 23184.35 € · rank 1 of 1" in text
    code, text = sh("calc", "costs", "stage=offer", "bid=bd1")
    assert code == 0, text
    assert "331: bd1 p1 p2 = 16653.84 €" in text.splitlines()
    _, text = sh("get", "p1")
    assert "bids: bd1 100.00" in text

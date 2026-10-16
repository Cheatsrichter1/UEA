"""Cost estimate per DIN 276 and fee per HOAI 2021, by hand on the box of test_din277.

The box has a BGF of 2 x 80.7216 = 161.4432 m² and a BRI of 263.152416 + 218.755536 =
481.907952 m³. Prices and fee tables are synthetic test data of our own: round numbers, not the
office's prices and not the HOAI's Honorartafeln.
"""

from pathlib import Path

import pytest

from tests.conftest import Shell, derive_text, model_from
from tests.test_calc_elec import install, run
from tests.test_din277 import SHELL
from uea.calc.din276 import COSTS, REF, span
from uea.calc.hoai import FEES, HOAI, chargeable_building, phases
from uea.derive import Derived
from uea.project import Project

BGF = 2 * 10.04 * 8.04
BRI = 10.04 * 8.04 * (3.26 + 2.71)
PRICES = "kg,name,basis,price\n300,Baukonstruktionen,bgf,1000\n400,Technische Anlagen,bri,100\n"
KG300 = BGF * 1000  # 161443.20
KG400 = BRI * 100  # 48190.7952
FEE_TABLE = """\
service,cost,zone,base,top
building,100000,III,20000,25000
building,200000,III,35000,43000
building,300000,III,50000,62000
services,40000,II,10000,12000
services,60000,II,14000,17000
"""


def box(extra: str = "") -> Derived:
    d, rep = derive_text(SHELL + extra)
    assert [i for i in rep.issues if i.code.startswith("E")] == []
    return d


def tables(tmp_path: Path, prices: str = PRICES) -> None:
    install("prices", REF, prices, tmp_path)
    install("fees", FEES, FEE_TABLE, tmp_path)


# ---------- the estimate ----------


def test_estimate(tmp_path: Path) -> None:
    tables(tmp_path)
    o = run(COSTS, box(), stand="2026-Q3")
    assert [(r["kg"], r["cost"]) for r in o.data["rows"]] == [
        (300, pytest.approx(KG300, abs=0.005)),
        (400, pytest.approx(KG400, abs=0.005)),
    ]
    net = KG300 + KG400  # 209633.9952
    assert o.data["net"] == pytest.approx(net, abs=0.005)
    assert o.data["vat"] == pytest.approx(net * 0.19, abs=0.005)
    assert o.data["gross"] == pytest.approx(net * 1.19, abs=0.005)
    assert o.lines[0] == "300 Baukonstruktionen: 161.44 m² BGF × 1000.00 = 161443.20 €"
    assert o.lines[-1] == "net 209634.00 € · VAT 19 % 39830.46 € · gross 249464.45 €"
    assert "Kostenstand: 2026-Q3" in o.report
    assert any("cost-ref" in t for t in o.tables)


def test_the_priced_lv_beside_the_estimate(tmp_path: Path) -> None:
    tables(tmp_path)
    lv = (
        'title T01 "Rohbau"\n'
        'pos p1 T01 area sel="wall ext" "Außenwand" kg=331 ep=100\n'
        'pos p2 T01 fix=1 unit=psch "Heizung" kg=420 ep=5000\n'
    )
    rows = run(COSTS, box(lv)).data["rows"]
    # the exterior walls, 34.8 m round, no openings: EG 2.7 high (-0.15 to the slab's underside
    # at 2.55), OG 2.6 (2.75 to the roof's underside at 5.35); 184.44 m² at 100 €
    assert rows[0]["lv"] == pytest.approx(34.8 * (2.7 + 2.6) * 100)
    assert rows[1]["lv"] == 5000
    # the LV is only shown, never added
    assert rows[0]["cost"] == pytest.approx(KG300, abs=0.005)


@pytest.mark.parametrize(
    ("prices", "message"),
    [
        ("kg,name,basis,price\n300,a,bgf,1\n330,b,bgf,1\n", "330 and 300 overlap"),
        ("kg,name,basis,price\n1000,a,bgf,1\n", "is not a cost group"),
        ("kg,name,basis,price\n300,a,nuf,1\n", "din277-uses is not installed"),
    ],
)
def test_bad_prices(tmp_path: Path, prices: str, message: str) -> None:
    install("prices", REF, prices, tmp_path)
    with pytest.raises(ValueError, match=message):
        run(COSTS, box())


def test_span() -> None:
    assert span(300) == (300, 399)
    assert span(330) == (330, 339)
    assert span(334) == (334, 334)


# ---------- the fee ----------


def test_chargeable_costs_of_a_building() -> None:
    # KG 400 up to a quarter of KG 300 in full, the rest by half
    assert chargeable_building(400_000, 80_000) == (480_000, 80_000, 0)
    assert chargeable_building(400_000, 140_000) == (400_000 + 100_000 + 20_000, 100_000, 20_000)


def test_phases() -> None:
    assert phases(None, 9) == list(range(1, 10))
    assert phases("1-4", 9) == [1, 2, 3, 4]
    assert phases("1-3,5,8", 9) == [1, 2, 3, 5, 8]
    with pytest.raises(ValueError, match="phases 1 to 6"):
        phases("1-9", 6)
    with pytest.raises(ValueError, match="give phases like"):
        phases("a", 9)


def test_fee_of_the_building_from_the_estimate(tmp_path: Path) -> None:
    tables(tmp_path)
    o = run(HOAI, box(), zone="III")
    # 25 % of KG 300 is 40360.80; KG 400 exceeds it by 7829.9952, of which half counts
    quarter = 0.25 * KG300
    cost = KG300 + quarter + (KG400 - quarter) / 2  # 205718.9976
    assert o.data["chargeable"] == pytest.approx(cost, abs=0.005)
    # between the rows 200000 and 300000: k = 5718.9976 / 100000
    k = (cost - 200_000) / 100_000
    base = 35_000 + k * 15_000  # 35857.85
    assert o.data["table"]["base"] == pytest.approx(base, abs=0.005)
    assert o.data["table"]["top"] == pytest.approx(43_000 + k * 19_000, abs=0.005)
    assert o.data["share"] == 100  # 2 + 7 + 15 + 3 + 25 + 10 + 4 + 32 + 2
    assert o.data["fee"] == pytest.approx(base, abs=0.005)
    assert o.data["gross"] == pytest.approx(base * 1.19, abs=0.01)


def test_phases_rate_conversion_and_incidental_costs(tmp_path: Path) -> None:
    tables(tmp_path)
    o = run(HOAI, box(), zone="III", kosten=250_000, rate=50, lph="1-4", umbau=20, nk=5)
    full = (42_500 + 52_500) / 2  # halfway between the rows, then halfway to the upper rate
    fee = full * 0.27  # phases 1 to 4: 2 + 7 + 15 + 3 %
    assert o.data["full"] == pytest.approx(full)
    assert o.data["fee"] == pytest.approx(fee)
    assert o.data["conversion"] == pytest.approx(fee * 0.2)
    assert o.data["incidental"] == pytest.approx(fee * 1.2 * 0.05)
    assert o.data["net"] == pytest.approx(fee * 1.2 * 1.05)
    assert o.lines[2].startswith("phases 1-4 = 27 % (§ 34 Abs. 3)")


def test_technical_equipment_takes_kg_400(tmp_path: Path) -> None:
    tables(tmp_path)
    o = run(HOAI, box(), service="services", zone="II", lph="1-3,5")
    assert o.data["chargeable"] == pytest.approx(KG400, abs=0.005)
    k = (KG400 - 40_000) / 20_000
    assert o.data["full"] == pytest.approx(10_000 + k * 4_000, abs=0.005)
    assert o.data["share"] == 2 + 9 + 17 + 22


def test_fee_stops_outside_the_table_and_without_what_it_needs(tmp_path: Path) -> None:
    tables(tmp_path)
    with pytest.raises(ValueError, match="free to agree"):
        run(HOAI, box(), zone="III", kosten=50_000)
    with pytest.raises(ValueError, match="needs zone="):
        run(HOAI, box())
    with pytest.raises(ValueError, match="need kosten="):
        run(HOAI, box(), service="structure", zone="III")
    with pytest.raises(ValueError, match="no rows for building"):
        run(HOAI, box(), zone="V", kosten=150_000)


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    m = model_from(SHELL)
    Project(sh.root).write(m, m.packs())
    sh("log")
    code, text = sh("calc", "costs")
    assert code == 1 and "uea data add cost-ref" in text
    tables(tmp_path)
    code, text = sh("calc", "costs", "stand=2026-Q3")
    assert code == 0 and "norm costs 0.2.0" in text and "DIN 276:2018-12" in text
    code, text = sh("calc", "hoai", "zone=III", "lph=1-4")
    assert code == 0 and "norm hoai 0.2.0" in text and "HOAI 2021" in text
    report = (sh.root / "out" / "hoai.md").read_text()
    assert "# Honorarermittlung nach HOAI 2021: Box" in report
    assert "| LPH 3 | 15 % |" in report


def test_phase_shares_sum_to_the_whole_fee() -> None:
    from uea.calc.hoai import SERVICES

    assert {k: (len(v[1]), sum(v[1])) for k, v in SERVICES.items()} == {
        "building": (9, 100),
        "services": (9, 100),
        "structure": (6, 100),
    }


# ---------- the calculation from the priced LV, and the fee on it ----------

PRICED = """\
title T01 "Rohbau"
pos p1 T01 area sel="wall ext" "Außenwand" kg=331 ep=100
pos p2 T01 fix=1 unit=psch "Heizung" kg=420 ep=5000
pos p3 T01 fix=2 unit=St "Lüftungsgeräte" kg=430 ep=1500
pos p4 T01 fix=3 unit=St "Fenster" kg=334
pos p5 T01 fix=1 unit=psch "Gerüst" ep=800
"""
WALLS = 34.8 * (2.7 + 2.6) * 100  # 184.44 m² of exterior wall at 100 €: 18444
SMALL_FEES = """\
service,cost,zone,base,top
building,20000,III,5000,6000
building,30000,III,7000,8400
services,4000,II,1000,1200
services,6000,II,1400,1700
"""


def test_calculation_takes_the_lv_where_it_is_priced(tmp_path: Path) -> None:
    install("prices", REF, PRICES, tmp_path)
    o = run(COSTS, box(PRICED), stage="calculation")
    assert [(r["kg"], r["source"], r["cost"]) for r in o.data["rows"]] == [
        (331, "lv", pytest.approx(WALLS)),
        (420, "lv", 5000),
        (430, "lv", 3000),
    ]
    assert o.data["net"] == pytest.approx(WALLS + 8000)  # 26444
    assert o.data["notes"] == [
        "300: priced in the LV; its estimate of 161443.20 € is not used",
        "400: priced in the LV; its estimate of 48190.80 € is not used",
        "no price (ep=), not in it: p4",
        "no cost group (kg=), not in it: p5",
    ]
    assert "# Kostenberechnung nach DIN 276: Box" in o.report


def test_calculation_keeps_the_estimate_of_groups_the_lv_does_not_price(tmp_path: Path) -> None:
    prices = "kg,name,basis,price\n330,Außenwände,bgf,600\n340,Innenwände,bgf,400\n"
    install("prices", REF, prices, tmp_path)
    rows = run(COSTS, box(PRICED), stage="calculation").data["rows"]
    assert [(r["kg"], r["source"]) for r in rows] == [
        (331, "lv"),
        (340, "estimate"),
        (420, "lv"),
        (430, "lv"),
    ]
    assert rows[1]["cost"] == pytest.approx(BGF * 400)  # 64577.28
    assert rows[0]["name"] == "Außenwände"


def test_calculation_needs_a_priced_lv(tmp_path: Path) -> None:
    install("prices", REF, PRICES, tmp_path)
    with pytest.raises(ValueError, match="no calculation yet"):
        run(COSTS, box(), stage="calculation")


def test_fee_on_the_calculation(tmp_path: Path) -> None:
    install("prices", REF, PRICES, tmp_path)
    install("fees", FEES, SMALL_FEES, tmp_path)
    o = run(HOAI, box(PRICED), zone="III")
    # § 6 Abs. 1: the LV is priced, so the calculation: KG 300 18444, KG 400 8000; a quarter of
    # KG 300 is 4611 in full, the 3389 above it by half
    cost = WALLS + 4611 + (8000 - 4611) / 2  # 24749.5
    assert o.data["chargeable"] == pytest.approx(cost)
    assert "from the cost calculation" in o.lines[0]
    assert o.data["fee"] == pytest.approx(5000 + (cost - 20_000) / 10_000 * 2000)  # 5949.90
    # the estimate is far above this table
    with pytest.raises(ValueError, match="free to agree"):
        run(HOAI, box(PRICED), zone="III", costs="estimate")


def test_fee_per_group_of_technical_systems(tmp_path: Path) -> None:
    install("prices", REF, PRICES, tmp_path)
    install("fees", FEES, SMALL_FEES, tmp_path)
    o = run(HOAI, box(PRICED), service="services", zone="II", groups="420")
    assert o.data["chargeable"] == 5000
    assert o.data["full"] == pytest.approx(1200)  # halfway between 4000 and 6000
    assert "KG 420 5000.00 (§ 54)" in o.lines[0]
    with pytest.raises(ValueError, match="free to agree"):
        run(HOAI, box(PRICED), service="services", zone="II", groups="420,430")  # 8000
    with pytest.raises(ValueError, match="chargeable costs are 0"):
        run(HOAI, box(PRICED), service="services", zone="II", groups="410")
    with pytest.raises(ValueError, match="is for service=services"):
        run(HOAI, box(PRICED), zone="III", groups="420")
    with pytest.raises(ValueError, match="510 is not a cost group of KG 400"):
        run(HOAI, box(PRICED), service="services", zone="II", groups="510")

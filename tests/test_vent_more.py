"""Outdoor air inlets, overflow openings, terminal and silencer losses, and the ventilation in
the Heizlast (decision 0043), by hand on the box of test_vent: r1 living and r2 kitchen."""

from pathlib import Path
from typing import Any, cast

import pytest

from tests.test_calc_elec import install, run
from tests.test_elec import found
from tests.test_heatload import SETTINGS as HEAT
from tests.test_heatload import tables as heat_tables
from tests.test_vent import AREA, CENTRAL, SETTINGS, air, box, tables
from uea.packs.heat.heatload import HEATLOAD
from uea.packs.vent.airflow import VENT_OVERFLOW
from uea.packs.vent.ducts import DUCTS

NL = AREA + 20
EXHAUST = (
    "type ALD inlet flow=30 default\n"
    "fan vl1 w2 y=S+2 mode=ext\n"
    "inlet al1 w4 y=S+2\n"
    "inlet al2 w4 y=S+4\n"
)
DOOR = "door d2 w5 0.885x2.01 y=S+4\n"
OVER = "upto,area\n50,50\n150,150\n"


def test_inlets_supply_their_room(tmp_path: Path) -> None:
    tables(tmp_path)
    d, rep = box(EXHAUST)
    # through the exterior wall with no hole yet, like a fan
    assert sorted(found(rep, "W-VENT-006")) == ["al1", "al2", "vl1"]
    assert d.vent.terminals["r1"] == {"sup": ["al1", "al2"]}
    o = air(d)
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict)
    # two inlets of 30 m³/h each: the living room's supply; the kitchen's exhaust fan 30
    assert rooms["r1"]["got"] == 60 and rooms["r1"]["by"] == ["al1", "al2"]
    assert rooms["r2"]["got"] == 30
    _, rep = box("type ALD inlet flow=30 default\ninlet al1 w5.w y=S+2\n")
    assert found(rep, "W-VENT-003") == ["al1"]


def test_overflow_openings(tmp_path: Path) -> None:
    tables(tmp_path)
    install("o", VENT_OVERFLOW, OVER, tmp_path)
    # no overflow opening in the model: not checked
    d, _ = box(CENTRAL + DOOR)
    assert air(d).ok and air(d).data["overflow"] == {}
    # the undercut of d2: 0.885 m x 0.01 m = 88.5 cm²; both rooms pass NL = 88.2 m³/h: 150 cm²
    d, _ = box(CENTRAL + DOOR + "over ue1 d2 cut=0.01\n")
    assert d.vent.overflow["ue1"] == pytest.approx(88.5)
    assert d.vent.over_rooms["ue1"] == ("r1", "r2")
    o = air(d)
    assert round(NL, 1) == 88.2
    assert o.data["overflow"] == {
        "r1": {"need": 150, "has": 88.5, "by": ["ue1"]},
        "r2": {"need": 150, "has": 88.5, "by": ["ue1"]},
    }
    assert not o.ok and "r1 overflow 88 of 150 cm² (ue1)" in o.lines
    # an overflow element of 100 cm² in the door as well
    d, _ = box(CENTRAL + DOOR + "over ue1 d2 cut=0.01\nover ue2 d2 area=100\n")
    assert air(d).ok
    with pytest.raises(ValueError, match=r"give cut= \(the undercut\) or area="):
        box(CENTRAL + DOOR + "over ue1 d2\n")


def test_terminal_and_silencer_losses(tmp_path: Path) -> None:
    tables(tmp_path)
    d, _ = box(CENTRAL)
    plain = run(DUCTS, d, None, **SETTINGS, vmax=3)
    sides = {x["side"]: x["need"] for x in plain.data["fans"]}  # type: ignore[union-attr]
    text = CENTRAL.replace("air ld1 r1 sup at=W+2,S+2", "air ld1 r1 sup at=W+2,S+2 dp=20")
    text = text.replace("ahu lg1 r1 at=W+1,N-1", "ahu lg1 r1 at=W+1,N-1 sil=15")
    d, _ = box(text)
    o = run(DUCTS, d, None, **SETTINGS, vmax=3)
    got = {x["side"]: x["need"] for x in o.data["fans"]}  # type: ignore[union-attr]
    assert got["sup"] == pytest.approx(sides["sup"] + 20 + 15, abs=1e-3)
    assert got["ext"] == pytest.approx(sides["ext"] + 15, abs=1e-3)
    assert o.data["terminals"]["ld1"]["dp"] == pytest.approx(  # type: ignore[index]
        plain.data["terminals"]["ld1"]["dp"] + 20,
        abs=1e-3,  # type: ignore[index]
    )


def test_heat_recovery_in_the_heat_load(tmp_path: Path) -> None:
    heat_tables(tmp_path)
    tables(tmp_path)
    d, _ = box(CENTRAL)
    before = run(HEATLOAD, d, None, **HEAT).data["rooms"]
    o = run(HEATLOAD, d, None, **HEAT, insulation="high")
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict) and isinstance(before, dict)
    r1 = cast(dict[str, float], rooms["r1"])
    r2 = cast(dict[str, float], rooms["r2"])
    # the supply air: θ_e −10 °C, recovered by 0.85 of the way to the kitchen's 20 °C
    assert r1["v_su"] == pytest.approx(NL, abs=0.01)
    assert r1["t_su"] == pytest.approx(-10 + 0.85 * 30, abs=1e-3)
    f_su = (20 - 15.5) / 30
    rest = max(r1["v_min"] - r1["v_inf"] - NL, 0.0)
    v1 = r1["v_inf"] + NL * f_su + rest
    assert r1["phi_v"] == pytest.approx(v1 * 0.34 * 30, abs=0.1)
    # the kitchen draws its air over from the living room: infiltration and what V̇_min lacks
    assert r2["v_tr"] == pytest.approx(NL, abs=0.01)
    v2 = r2["v_inf"] + max(r2["v_min"] - r2["v_inf"] - NL, 0.0)
    assert r2["phi_v"] == pytest.approx(v2 * 0.34 * 30, abs=0.1)
    assert r1["phi_v"] < before["r1"]["phi_v"]
    assert "θ_su = 15,5 °C" in o.report


def test_ventilation_in_the_ifc(tmp_path: Path) -> None:
    import ifcopenshell

    from tests.test_ifc import check_valid_and_buildable
    from tests.test_vent import PAIR
    from uea.export.ifc import export_ifc

    d, _ = box(CENTRAL + PAIR + "type ALD inlet flow=30 default\ninlet al1 w1 x=W+3\n")
    path = tmp_path / "v.ifc"
    counts = export_ifc(d, path)
    f: Any = ifcopenshell.open(str(path))  # pyright: ignore[reportUnknownMemberType]
    check_valid_and_buildable(f)
    # the unit and the pair; four terminals and the inlet; one duct per terminal of lg1
    assert counts["IfcUnitaryEquipment"] == 3
    assert counts["IfcAirTerminal"] == 5
    assert counts["IfcDuctSegment"] == 4
    terms = {e.Tag: e.PredefinedType for e in f.by_type("IfcAirTerminal")}
    assert terms == {
        "ld1": "DIFFUSER",
        "ld2": "GRILLE",
        "ld3": "LOUVRE",
        "ld4": "LOUVRE",
        "al1": "LOUVRE",
    }
    systems = sorted(s.Name for s in f.by_type("IfcDistributionSystem"))
    assert systems == ["lg1 Abluft", "lg1 Außenluft", "lg1 Fortluft", "lg1 Zuluft"]
    sup = next(s for s in f.by_type("IfcDistributionSystem") if s.Name == "lg1 Zuluft")
    members = {p.Tag or p.Name for r in sup.IsGroupedBy for p in r.RelatedObjects}
    assert members == {"lg1", "ld1", "lg1>ld1"}


def test_inlets_on_the_ventilation_plan() -> None:
    # an exhaust system: one fan and two inlets, no central unit; the plan drew no inlet and
    # failed on it ('Inlet' has no role)
    from uea.export.drawing import Text
    from uea.export.tga import sheet_tga

    d, _ = box(EXHAUST)
    dw = sheet_tga(d, "EG", "vent")
    assert dw is not None
    texts = [it.text for it in dw.items if isinstance(it, Text)]
    assert texts.count("ALD") == 2 and {"al1", "al2", "vl1 Abluft"} <= set(texts)
    assert "Außenluftdurchlass (ALD)" in texts

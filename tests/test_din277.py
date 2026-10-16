"""Areas and volumes per DIN 277, hand-computed on the 10 x 8 box of two storeys.

The cores of the exterior walls run on the grids (10 x 8 m outside), 0.3 m thick, with 0.01 m
of plaster inside and 0.02 m of render outside. The slabs are 0.2 m of concrete with 0.01 m of
plaster below; the flat roof's underside is 2.6 m above the OG's SSL (2.75), and it is 0.26 m
thick up to the top of its covering (the layers from the core up). The use table is synthetic
test data of our own, not the standard's.
"""

from pathlib import Path

import pytest

from tests.conftest import BOX, Shell, derive_text, model_from
from tests.test_calc_elec import install, run
from uea.derive import Derived
from uea.packs.arch.din277 import DIN277, USES
from uea.project import Project

SHELL = (
    BOX
    + """\
type DA roof layers=kies:0.05,abd:0.01,*holz:0.2,gips:0.0125
wall w5 OG AW on=w1 lb top=rf1
wall w6 OG AW on=w2 lb top=rf1
wall w7 OG AW on=w3 lb top=rf1
wall w8 OG AW on=w4 lb top=rf1
slab sl1 EG DE
slab sl2 OG DE
roof rf1 OG DA flat knee=2.6
room r1 EG living at=W+5,S+5
room r2 OG bedroom at=W+5,S+5
"""
)
STAIR = """\
stair st1 EG OG x=w4+0.5 y=w1+1 up=n w=1 n=16 tread=0.26
void v1 sl2 over=st1
"""
TABLE = "use,group\nliving,1\nbedroom,1\nhall,9\ntechnical,8\n"

BGF = 10.04 * 8.04
"""Cores 10 x 8 and 0.02 m of render all round: 80.7216."""
NRF = 9.38 * 7.38
"""Inside the 0.3 m cores (9.4 x 7.4), less 0.01 m of plaster each side: 69.2244."""
STAIR_AREA = 1 * 15 * 0.26
"""1 m wide, 15 treads of 0.26 m: 3.9."""


def box(extra: str = "") -> Derived:
    d, rep = derive_text(SHELL + extra)
    assert rep.issues == []
    return d


def test_areas_and_volume_of_the_box() -> None:
    o = run(DIN277, box())
    eg, og = o.data["levels"]
    assert eg["bgf"] == pytest.approx(BGF)
    assert eg["nrf"] == pytest.approx(NRF)
    assert eg["kgf"] == pytest.approx(BGF - NRF)  # 11.4972
    # from the underside of the floor slab (SSL -0.15, 0.2 concrete, 0.01 plaster: -0.36)
    # to the OG's FFL 2.9
    assert eg["bri"] == pytest.approx(BGF * (2.9 + 0.36))  # 263.152416
    # from the OG's FFL up to the top of the roof: 2.75 + 2.6 + 0.26 = 5.61
    assert og["bri"] == pytest.approx(BGF * (5.61 - 2.9))  # 218.755536
    assert o.data["total"]["bgf"] == pytest.approx(2 * BGF)
    assert o.data["total"]["bri"] == pytest.approx(BGF * 3.26 + BGF * 2.71)
    assert o.lines[-2] == "BGF 161.44 · NRF 138.45 · KGF 22.99 m² · BRI 481.91 m³"
    assert "uea data show din277-uses" in o.lines[-1]


def test_a_stair_is_vf_and_its_void_no_floor(tmp_path: Path) -> None:
    install("uses", USES, TABLE, tmp_path)
    o = run(DIN277, box(STAIR))
    eg, og = o.data["levels"]
    # the stair stays in the EG's NRF, as VF; the room keeps the rest
    assert eg["nrf"] == pytest.approx(NRF)
    assert eg["groups"] == pytest.approx({"NUF 1": NRF - STAIR_AREA, "VF": STAIR_AREA})
    assert eg["rooms"][0]["stair"] == pytest.approx(STAIR_AREA)
    # over it, the OG has a void: no floor, so neither BGF nor NRF
    assert og["bgf"] == pytest.approx(BGF - STAIR_AREA)
    assert og["nrf"] == pytest.approx(NRF - STAIR_AREA)
    assert og["kgf"] == pytest.approx(BGF - NRF)
    assert og["groups"] == pytest.approx({"NUF 1": NRF - STAIR_AREA})
    # the space of the void is still inside the building
    assert og["bri"] == pytest.approx(BGF * 2.71)
    assert o.lines[0] == "EG BGF 80.72 · NRF 69.22 (NUF 1 65.32 · VF 3.90) · KGF 11.50 · BRI 263.15"
    assert any("din277-uses (DIN 277), Ausgabe synthetic test values" in t for t in o.tables)


def test_a_level(tmp_path: Path) -> None:
    o = run(DIN277, box(), "OG")
    assert [lv["id"] for lv in o.data["levels"]] == ["OG"]
    with pytest.raises(ValueError, match="give a level or nothing"):
        run(DIN277, box(), "r1")


def test_a_use_without_a_group(tmp_path: Path) -> None:
    install("uses", USES, "use,group\nliving,1\n", tmp_path)
    with pytest.raises(ValueError, match="no group for the room uses bedroom"):
        run(DIN277, box())


def test_a_group_out_of_range(tmp_path: Path) -> None:
    install("uses", USES, "use,group\nliving,1\nbedroom,10\n", tmp_path)
    with pytest.raises(ValueError, match="group 10 for bedroom is not 1 to 9"):
        run(DIN277, box())


def test_no_roof_over_the_top_storey() -> None:
    text = SHELL.replace("roof rf1 OG DA flat knee=2.6\n", "").replace(" top=rf1", " h=2.5")
    d, _ = derive_text(text)
    o = run(DIN277, d)
    assert not o.ok
    assert o.data["levels"][1]["bri"] is None
    assert "  OG: no roof over the top storey, so its BRI is unknown" in o.lines
    assert o.lines[-2].endswith("(incomplete)")


def test_floor_without_a_room_goes_to_kgf() -> None:
    d, _ = derive_text(SHELL.replace("room r2 OG bedroom at=W+5,S+5\n", ""))
    og = run(DIN277, d).data["levels"][1]
    assert og["nrf"] == 0
    assert og["unassigned"] == pytest.approx(9.4 * 7.4)  # the shell area of the empty storey


def test_on_the_command_line(sh: Shell) -> None:
    m = model_from(SHELL)
    Project(sh.root).write(m, m.packs())
    code, text = sh("calc", "din277")
    assert code == 0
    assert "norm din277 0.1.0" in text and "DIN 277:2021-08" in text
    report = (sh.root / "out" / "din277.md").read_text()
    assert "# Grundflächen und Rauminhalte nach DIN 277: Box" in report
    assert "- BGF: 80,72 m²" in report


def test_haus_mueller(prototype: Project) -> None:
    from uea.derive import report

    d, _ = report(prototype.load())
    eg, og, db = run(DIN277, d).data["levels"]
    outside = 10.53 * 8.53  # cores 10.49 x 8.49 and 0.02 m of render: 89.8209
    assert eg["bgf"] == pytest.approx(outside)
    # from the underside of the floor slab (SSL -0.15, 0.25 concrete, 0.14 XPS: -0.54) to the
    # OG's FFL 2.875
    assert eg["bri"] == pytest.approx(outside * 3.415)
    # the stair hole of 1 x 15 x 0.26 in the OG's slab
    assert og["bgf"] == pytest.approx(outside - 3.9)
    assert og["bri"] == pytest.approx(outside * (5.86 - 2.875))
    # the gable walls of the attic carry render; its eaves sides are the slab's edge, which
    # the same render grows
    assert db["bgf"] == pytest.approx(outside)

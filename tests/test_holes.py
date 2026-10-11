"""Openings without a fill (decision 0039): holes through walls and slabs, chases, and the
handoff from the services that need them. Hand-computed on the box of test_plumb: walls of 0.3
core with 0.02 render outside and 0.01 plaster inside, an OG at FFL 2.9 on a slab sl2 of 0.2
concrete and 0.01 plaster under it (its SSL 2.75, its ceiling 2.54)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import math
import re
from pathlib import Path

import ifcopenshell
import pytest

from tests.conftest import Shell, derive_text, model_from
from tests.test_elec import found
from tests.test_plumb import HOUSE, PLUMB
from uea.derive import Derived, Report
from uea.export.drawing import Text
from uea.export.ifc import export_ifc
from uea.export.paper import L_VOID
from uea.export.sheet import sheet_plan
from uea.export.tables import tables

HOLES = (
    "hole ho1 w1 0.2x0.2 x=W+3 sill=1 round\n"
    "hole ho2 w4.e 0.05x1 y=S+2 sill=0.3 d=0.03\n"
    "hole ho3 sl2 0.3x0.2 at=W+5,S+4\n"
    "hole ho4 sl2 0.1x0.1 at=W+1,N-1 round\n"
)
HEAT = (
    "type HKV man outlets=8 default\n"
    "type FBH ufh spacing=0.15 q=60 max=100 default\n"
    "man hv1 w5 t1 x=W+2\n"
    "ufh uh1 r2 hv1\n"
)
VENT = (
    "type KWL ahu flow=150 default\n"
    "type R duct sizes=80,100,125 k=0.15 bend=0.3 tee=0.6 default\n"
    "ahu lg1 r1 at=W+4,S+4\n"
    "air ld1 r2 sup at=W+6,S+4 z=2.4\n"
    "air ld2 w4 oda y=S+6 z=2.4\n"
)


def box(extra: str) -> tuple[Derived, Report]:
    return derive_text(HOUSE + extra)


def test_kinds_say_what_is_wrong() -> None:
    for line, msg in (
        ("hole ho1 w1 0.2x0.3 x=W+3 round", "one diameter"),
        ("hole ho1 w1.n 0.2x0.3 x=W+3", "a chase is in a wall face and has a depth"),
        ("hole ho1 w1 0.2x0.3 x=W+3 d=0.1", "a chase is in a wall face and has a depth"),
        ("hole ho1 w1 0.2x0.3", "give its position"),
    ):
        with pytest.raises(Exception, match=msg):
            model_from(HOUSE + line + "\n")
    _, rep = box("hole ho1 w1 0.2x0.2 at=W+1,S+1\nhole ho2 sl2 0.2x0.2 x=W+1\n")
    assert [(i.el, i.msg.split(":")[0]) for i in rep.issues if i.code == "E-GEO-001"] == [
        ("ho1", "ho1 is in the wall w1"),
        ("ho2", "ho2 is in the slab sl2"),
    ]


def test_geometry() -> None:
    d, rep = box(HOLES)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    g = d.arch
    # through w1 and its finishes: x 3..3.2, y -0.02..0.31, z 1..1.2
    h = g.holes["ho1"]
    assert h.wall is not None and (h.wall.lo, h.wall.hi) == (3, pytest.approx(3.2))
    assert (h.z0, h.z1, h.round, h.chase) == (1, pytest.approx(1.2), True, False)
    assert h.poly.bounds == pytest.approx((3, -0.02, 3.2, 0.31))
    # a chase 0.03 into the core of w4 from its inside face (x 0.3), through the plaster
    h = g.holes["ho2"]
    assert h.chase and h.poly.bounds == pytest.approx((0.27, 2, 0.31, 2.05))
    # in sl2, from the plastered ceiling of the EG to the FFL of the OG
    h = g.holes["ho3"]
    assert (h.level, h.z0, h.z1) == ("OG", pytest.approx(2.54), pytest.approx(2.9))
    assert h.poly.bounds == pytest.approx((4.85, 3.9, 5.15, 4.1))
    assert g.holes["ho4"].poly.area == pytest.approx(math.pi * 0.05**2, rel=2e-3)
    assert g.holes["ho4"].centre == pytest.approx((1, 7))


def test_arch_checks() -> None:
    _, rep = box(
        "win f1 w1 1.2x1.2 x=W+1\n"
        "hole ho1 w1 0.2x0.2 x=E+0.1\n"  # beyond the end of w1
        "hole ho2 w1 0.2x0.2 x=W+1.5 sill=1.5\n"  # in the window f1 (1.06..2.26)
        "hole ho3 w4.e 0.05x1 y=S+2 d=0.3\n"  # as deep as the core of w4
        "hole ho4 sl2 0.4x0.4 at=E+1,S+1\n"  # beyond the slab
    )
    assert found(rep, "E-ARCH-001") == ["ho1"]
    assert found(rep, "E-ARCH-002") == ["ho2"]
    assert found(rep, "E-ARCH-007") == ["ho3"]
    assert found(rep, "W-ARCH-032") == ["ho4"]


def test_plumbing_asks_for_its_holes() -> None:
    _, rep = box(PLUMB)
    # the riser at (1, 7) and the stack at (2, 7) pass sl2
    assert sorted(found(rep, "W-PLUMB-006")) == ["fl1", "sr1"]
    issue = next(i for i in rep.issues if i.code == "W-PLUMB-006" and i.el == "sr1")
    assert issue.msg == "sr1:EG>sr1:OG passes sl2 at 1,7, and no hole is there"
    assert issue.fix is not None and issue.fix.startswith("ask arch for one: + req _ plumb sl2")
    _, rep = box(PLUMB + HOLES)
    assert found(rep, "W-PLUMB-006") == ["fl1"]


def test_heating_through_a_hole() -> None:
    d, rep = box(HEAT)
    assert found(rep, "W-HEAT-005") == ["t1"]
    s = d.heat.nets["t1"].sections[0]
    t1, hv1 = d.heat.at["t1"], d.heat.at["hv1"]
    dz = abs(hv1.z - t1.z)
    # t1 at (3, 1), hv1 on the core face of w5 at (2, 0.3): 1 + 0.7 + dz, three legs
    assert (s.length, s.legs) == (pytest.approx(1 + 0.7 + dz), 3)
    # a hole that the tank does not name in via= does not help
    _, rep = box(HEAT + "hole ho5 sl2 0.2x0.2 at=W+3,S+0.5\n")
    assert found(rep, "W-HEAT-005") == ["t1"]


def test_heating_via() -> None:
    text = (HOUSE + HEAT).replace("tank t1 r1 at=W+3,S+1", "tank t1 r1 at=W+3,S+1 via=ho5")
    d, rep = derive_text(text + "hole ho5 sl2 0.2x0.2 at=W+3,S+0.5\n")
    assert found(rep, "W-HEAT-005") == []
    s = d.heat.nets["t1"].sections[0]
    dz = abs(d.heat.at["hv1"].z - d.heat.at["t1"].z)
    # up through the hole at (3, 0.5): 0.5 to it, then 1 and 0.2 to hv1
    assert (s.length, s.legs, s.via) == (pytest.approx(0.5 + 1 + 0.2 + dz), 4, ["ho5"])


def test_ventilation_asks_for_its_holes() -> None:
    d, rep = box(VENT)
    assert found(rep, "W-VENT-006") == ["ld2"]
    assert found(rep, "W-VENT-007") == ["lg1"]
    hole = "hole ho5 w4 0.2x0.2 y=S+5.9 sill=2.3 round\nhole ho6 sl2 0.3x0.2 at=W+4,S+3\n"
    d, rep = box(VENT.replace("ahu lg1 r1 at=W+4,S+4", "ahu lg1 r1 at=W+4,S+4 via=ho6") + hole)
    assert found(rep, "W-VENT-006") == found(rep, "W-VENT-007") == []
    assert d.vent.holes == {"ld2": "ho5"}
    # lg1 at (4, 4) to ld1 at (6, 4) through (4, 3): 1 + 2 + 1 in plan, then the height
    s = d.vent.ducts[("lg1", "sup")].sections[0]
    dz = abs(d.vent.at["ld1"].z - d.vent.at["lg1"].z)
    assert (s.length, s.via) == (pytest.approx(4 + dz), ["ho6"])


def test_sheets_ifc_and_table(tmp_path: Path) -> None:
    d, _ = box(PLUMB + HOLES)

    def labels(level: str) -> list[str]:
        dw = sheet_plan(d, level)
        assert dw is not None
        return sorted(t.text for t in dw.items if isinstance(t, Text) and t.layer == L_VOID)

    # the EG: its two wall holes, and those of sl2 above it, dashed; the OG: sl2 is its floor
    assert labels("EG") == ["DD 30/20", "KB Ø10", "KB Ø20 UK +1,00", "S 5/100 T 3 UK +0,30"]
    assert labels("OG") == ["DD 30/20", "KB Ø10"]
    export_ifc(d, tmp_path / "h.ifc")
    f = ifcopenshell.open(str(tmp_path / "h.ifc"))
    ops = {o.Name: o for o in f.by_type("IfcOpeningElement") if o.Name.startswith("ho")}
    assert sorted(ops) == ["ho1", "ho2", "ho3", "ho4"]
    assert ops["ho2"].PredefinedType == "RECESS"
    assert [r.RelatingBuildingElement.Name for r in ops["ho4"].VoidsElements] == ["sl2"]
    circle = ops["ho1"].Representation.Representations[0].Items[0].SweptArea
    assert circle.is_a("IfcCircleProfileDef") and circle.Radius == pytest.approx(0.1)
    t = next(t for t in tables(d) if t.name == "Aussparungen")
    assert [(r[0], r[1], r[3], r[12]) for r in t.rows] == [
        ("ho1", "Kernbohrung Wand", "w1", None),
        ("ho2", "Schlitz", "w4", None),
        ("ho3", "Deckendurchbruch", "sl2", None),
        ("ho4", "Kernbohrung Decke", "sl2", "sr1"),
    ]


def test_on_the_command_line(sh: Shell) -> None:
    text = HOUSE + PLUMB + HOLES + HEAT + "hole ho5 sl2 0.2x0.2 at=W+3,S+2\n"
    ops = re.sub(r"\b((?:w|sl|r|sr|fl|wz|kn|sa|t|ho|hv|uh)\d)\b", r"@\1", text)
    code, out = sh(
        "apply", "--by", "t", "-m", "holes", stdin="".join(f"+ {x}\n" for x in ops.splitlines())
    )
    assert code == 0, out
    code, out = sh("get", "ho1", "ho4")
    assert " x 3..3.2 in w1 | sill 1 top 1.2 (z 1..1.2) | through | round" in out
    assert " in sl2 | centre 1,7 | round | z 2.54..2.9" in out
    # the pipe to hv1 now runs through ho5: it follows, named by the manifold at its end
    code, out = sh("apply", "--by", "t", "-m", "via", stdin="~ t1 via=ho5\n")
    assert code == 0 and "fixed: W-HEAT-005 t1" in out and "follows: hv1 (heat)" in out, out

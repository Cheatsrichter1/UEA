"""IFC export: schema-valid, every shape builds, GlobalIds stable."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import logging
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import BOX, model_from
from uea.derive import report
from uea.project import Project

ifcopenshell = pytest.importorskip("ifcopenshell")


def export(p: Project, path: Path) -> Any:
    from uea.export.ifc import export_ifc

    d, _ = report(p.load())
    export_ifc(d, path)
    return ifcopenshell.open(str(path))


def check_valid_and_buildable(f: Any) -> None:
    import ifcopenshell.geom
    import ifcopenshell.validate

    errors: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            errors.append(record.getMessage())

    log = logging.getLogger("ifc-validate")
    log.addHandler(Collect())
    ifcopenshell.validate.validate(f, log)
    assert errors == []
    settings = ifcopenshell.geom.settings()
    for e in f.by_type("IfcProduct"):
        if e.Representation:
            ifcopenshell.geom.create_shape(settings, e)


def test_valid_and_buildable(prototype: Project, tmp_path: Path) -> None:
    f = export(prototype, tmp_path / "h.ifc")
    check_valid_and_buildable(f)
    kinds = ("IfcWall", "IfcDoor", "IfcWindow", "IfcSpace", "IfcSlab")
    counts = {c: len(f.by_type(c)) for c in kinds}
    # 17 walls, 9 doors, 13 windows, 11 rooms; 3 floor slabs + 2 roof planes
    assert counts == {"IfcWall": 17, "IfcDoor": 9, "IfcWindow": 13, "IfcSpace": 11, "IfcSlab": 5}


def export_text(text: str, path: Path) -> Any:
    from uea.export.ifc import export_ifc

    d, _ = report(model_from(text))
    export_ifc(d, path)
    return ifcopenshell.open(str(path))


def test_chamfer_and_stairs(tmp_path: Path) -> None:
    text = (
        BOX
        + "slab sl1 EG DE\nslab sl2 OG DE\ntype TK wall layers=*mw:0.2\n"
        + "wall w5 EG TK a=0.15,3.15 b=3.15,0.15\n"
        + "door d1 w5 0.9x2.01 s=2+ into=r1 hand=l\nwin f1 w5 0.6x0.6 s=d1+0.3 sill=1\n"
        + "niche ni1 w5.l 0.5x0.5 s=0.4+ d=0.05\n"
        + "room r1 EG living at=5,4\nroom r2 EG storage at=0.6,0.6\n"
        + "stair st1 EG OG x=4+ y=1+ up=n w=1 n=16 tread=0.26 shape=l turn=l winders=3\n"
        + "stair st2 EG OG x=7+ y=1+ up=n w=1 n=16 tread=0.26 shape=u turn=r\n"
        + "void v1 sl2 over=st1\nvoid v2 sl2 over=st2\n"
    )
    f = export_text(text, tmp_path / "c.ifc")
    check_valid_and_buildable(f)
    types = {e.PredefinedType for e in f.by_type("IfcStair")}
    assert types == {"QUARTER_WINDING_STAIR", "HALF_TURN_STAIR"}
    # st1: two flights and the winders; st2: two flights and a landing
    flights = [e.PredefinedType for e in f.by_type("IfcStairFlight")]
    assert sorted(flights) == ["STRAIGHT"] * 4 + ["WINDER"]
    assert [e.PredefinedType for e in f.by_type("IfcSlab")].count("LANDING") == 1


L_ROOFS = """\
project l
level EG z=0 fb=0
grid W x=0
grid E x=10
grid E2 x=4
grid S y=0
grid N y=10
grid N2 y=4
type TK wall layers=*mw:0.3
type DA roof layers=ziegel:0.05,*sparren:0.15
wall w1 EG TK y=S+ x=W..E top=rf1
wall w2 EG TK x=E- y=w1..w3 top=rf1
wall w3 EG TK y=N2- x=E2..E top=rf1
wall w4 EG TK x=E2- y=w3.s..w5 top=rf1
wall w5 EG TK y=N- x=W..E2 top=rf1
wall w6 EG TK x=W+ y=w1..w5 top=rf1
room r1 EG living at=1,1
roof rf1 EG DA {a} knee=0.5 eave=0.4 x=W..E y=S..N2
roof rf2 EG DA {b} knee=0.5 eave=0.4 x=W..E2 y=S..N
"""


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("gable ridge=x pitch=40", "gable ridge=y pitch=40"),
        ("hip pitch=35", "hip pitch=35"),
        ("gable ridge=x pitch=40 verge=0.3", "shed up=n pitch=20"),
        ("gable ridge=x pitch=40 halfhip=1", "gable ridge=y pitch=40 halfhip=1"),
        ("mansard pitch=60 upper=25 rise=1", "mansard ridge=y pitch=60 upper=25 rise=1"),
        ("flat", "flat"),
    ],
)
def test_roofs_with_wings(a: str, b: str, tmp_path: Path) -> None:
    f = export_text(L_ROOFS.format(a=a, b=b), tmp_path / "l.ifc")
    check_valid_and_buildable(f)
    assert len(f.by_type("IfcRoof")) == 2
    assert len(f.by_type("IfcWall")) == 6


@pytest.mark.parametrize(
    ("roof", "predefined"),
    [
        ("gable ridge=x pitch=40", "GABLE_ROOF"),
        ("gable ridge=x pitch=40 halfhip=1", "HIPPED_GABLE_ROOF"),
        ("hip pitch=40", "HIP_ROOF"),
        ("shed up=n pitch=10", "SHED_ROOF"),
        ("mansard pitch=60 upper=25 rise=1.5", "MANSARD_ROOF"),
        ("mansard ridge=x pitch=60 upper=25 rise=1.5", "GAMBREL_ROOF"),
        ("flat knee=2.7", "FLAT_ROOF"),
    ],
)
def test_roof_shapes_in_the_ifc(roof: str, predefined: str, tmp_path: Path) -> None:
    text = L_ROOFS.splitlines(keepends=True)
    house = "".join(x for x in text if not x.startswith("roof"))
    f = export_text(house + f"roof rf1 EG DA {roof} x=W..E y=S..N\n", tmp_path / "r.ifc")
    check_valid_and_buildable(f)
    # an occurrence with a type takes its predefined type from the type
    assert [t.PredefinedType for t in f.by_type("IfcRoofType")] == [predefined]
    assert len(f.by_type("IfcRoof")) == 1


def test_global_ids_are_stable(prototype: Project, tmp_path: Path) -> None:
    a = export(prototype, tmp_path / "a.ifc")
    b = export(prototype, tmp_path / "b.ifc")

    def ids(f: Any) -> dict[str, str]:
        return {e.Name: e.GlobalId for e in f.by_type("IfcWall")}

    assert ids(a) == ids(b)
    assert len(set(ids(a).values())) == 17

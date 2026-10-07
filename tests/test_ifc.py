"""IFC export: schema-valid, every shape builds, GlobalIds stable."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import logging
from pathlib import Path
from typing import Any

import pytest

from uea.derive import report
from uea.project import Project

ifcopenshell = pytest.importorskip("ifcopenshell")


def export(p: Project, path: Path) -> Any:
    from uea.export.ifc import export_ifc

    d, _ = report(p.load())
    export_ifc(d, path)
    return ifcopenshell.open(str(path))


def test_valid_and_buildable(prototype: Project, tmp_path: Path) -> None:
    import ifcopenshell.geom
    import ifcopenshell.validate

    f = export(prototype, tmp_path / "h.ifc")
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
    kinds = ("IfcWall", "IfcDoor", "IfcWindow", "IfcSpace", "IfcSlab")
    counts = {c: len(f.by_type(c)) for c in kinds}
    # 17 walls, 9 doors, 13 windows, 11 rooms; 3 floor slabs + 2 roof planes
    assert counts == {"IfcWall": 17, "IfcDoor": 9, "IfcWindow": 13, "IfcSpace": 11, "IfcSlab": 5}


def test_global_ids_are_stable(prototype: Project, tmp_path: Path) -> None:
    a = export(prototype, tmp_path / "a.ifc")
    b = export(prototype, tmp_path / "b.ifc")

    def ids(f: Any) -> dict[str, str]:
        return {e.Name: e.GlobalId for e in f.by_type("IfcWall")}

    assert ids(a) == ids(b)
    assert len(set(ids(a).values())) == 17

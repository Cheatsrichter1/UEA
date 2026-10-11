"""`uea import ifc`, the ways programs write a file (decision 0031): units, survey coordinates and
turned plans, several buildings, walls in parts, curved walls, curtain walls and niches.

Fixtures come from `tests/ifc_make.py` like those of `test_import.py`: a 6 m by 4 m house on two
storeys around the axes of its outer walls, whose bodies reach 0.17 m outside them (0.15 m of core
and 0.02 m of render) and 0.165 m inside (0.015 m of plaster). Most expectations are the plain
house's own lines, so what each variant must not change is that whole model.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import contextlib
import io
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("ifcopenshell")

import ifcopenshell
import ifcopenshell.util.unit as uu

from tests.conftest import Shell
from tests.ifc_make import (
    INNER,
    OUTER,
    CurtainSpec,
    CurvedSpec,
    House,
    RecessSpec,
    WallSpec,
    house,
    write,
)
from tests.test_import import do_import, lines, load
from tests.test_import_shapes import everything
from uea.cli import main
from uea.project import Project


def base() -> House:
    h = house()
    h.extras = []
    return h


def model_of(tmp_path: Path, name: str, path: Path, *extra: str) -> tuple[str, list[str]]:
    """Import a file into a new project: the report and the sorted lines of the model."""
    root = tmp_path / name
    assert main(["init", str(root)]) == 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["-C", str(root), "import", "ifc", str(path), "--by", "t", *extra])
    out = buf.getvalue()
    assert code == 0, out
    return out, sorted(e.line() for e in Project(root).load())


def plain(tmp_path: Path) -> list[str]:
    write(base(), tmp_path / "plain.ifc")
    return model_of(tmp_path, "plain", tmp_path / "plain.ifc")[1]


def turned(degrees: float) -> tuple[float, float]:
    r = math.radians(degrees)
    return (math.cos(r), math.sin(r))


def records(sh: Shell) -> list[dict[str, object]]:
    log = (sh.root / "log.jsonl").read_text().splitlines()
    return [rec["ifc"] for rec in map(json.loads, log) if "ifc" in rec]


# ---------- units ----------


@pytest.mark.parametrize("unit", ["MILLIMETERS", "CENTIMETERS", "FOOT"])
def test_lengths_in_other_units_give_the_same_model(tmp_path: Path, unit: str) -> None:
    # the house with its grid, stair, opening and gable roof, once in metres and once converted
    write(everything("IFC4"), tmp_path / "m.ifc")
    f = uu.convert_file_length_units(ifcopenshell.open(str(tmp_path / "m.ifc")), unit)
    f.write(str(tmp_path / "other.ifc"))
    assert uu.calculate_unit_scale(f) == pytest.approx(
        {"MILLIMETERS": 0.001, "CENTIMETERS": 0.01, "FOOT": 0.3048}[unit]
    )
    _, metres = model_of(tmp_path, "m", tmp_path / "m.ifc")
    _, other = model_of(tmp_path, "other", tmp_path / "other.ifc")
    assert other == metres


# ---------- where the plan lies ----------


def test_a_plan_turned_off_the_axes_is_turned_back(tmp_path: Path) -> None:
    h = base()
    h.site_x = turned(30)
    write(h, tmp_path / "turned.ifc")
    out, got = model_of(tmp_path, "turned", tmp_path / "turned.ifc")
    # turned back about the origin, which the house shares with the file: the plain model
    assert "note: the file's plan is turned by -30°, so its walls run along x and y" in out
    assert got == plain(tmp_path)


def far() -> House:
    """The house in survey coordinates: its site 485 km east and 5520 km north, 112.5 m above
    sea level, and turned by 30°."""
    h = base()
    h.site_at = (485000.0, 5520000.0, 112.5)
    h.site_x = turned(30)
    return h


def test_a_plan_far_from_the_origin_is_moved_to_it(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, far(), tmp_path)
    assert "turned by -30°, so its walls run along x and y near the origin" in out
    assert "note: ground storey EG (±0.00), the lowest; its elevation in the file is 112.5 m" in out
    assert "issues: 0 errors · 0 warnings" in out
    # the lower left corner of the bodies is 0,0: the axes of the outer walls 0.17 further in
    assert lines(sh, "w1", "w2", "w9", "f1", "EG", "OG") == [
        "wall w1 EG AW-33-5 a=0.17,0.17 b=6.17,0.17 lb",
        "wall w2 EG AW-33-5 a=6.17,0.17 b=6.17,4.17 lb",
        "wall w9 EG IW-11-5 a=3.67,0.3195 b=3.67,4.0205",
        "win f1 w1 1.2x1.35 x=1.17+ type=FENSTER-120",
        "level EG z=0 fb=0.15 head=2.25",
        "level OG z=2.9 fb=0.15 head=2.25",
    ]
    # the history keeps the move, in the file's coordinates (where the house's corner lies), and
    # the turn
    frame = records(sh)[0]["frame"]
    assert isinstance(frame, list)
    assert frame[0] == pytest.approx(-30, abs=0.001)
    assert frame[1] == pytest.approx(-485000, abs=1) and frame[2] == pytest.approx(-5520000, abs=1)


def test_a_later_file_lands_where_the_first_did(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, far(), tmp_path)
    # a garden wall 2 m west of the house moves the corner of the plan: the first import's frame
    # still counts, so nothing else moves, and the new wall lies at -2 + 0.17
    h = far()
    garden = WallSpec("Garten", (-2.0, 0.0), (-2.0, 3.0), "EG", INNER, (-1.0, 0.0))
    h.walls.append(replace(garden, type_name="IW 11.5"))
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert out.splitlines()[0].endswith("ok (batch 2): 1 walls")
    assert "as at the first import" in out
    assert lines(sh, "w1", "w10") == [
        "wall w1 EG AW-33-5 a=0.17,0.17 b=6.17,0.17 lb",
        "wall w10 EG IW-11-5 a=-1.83,0.17 b=-1.83,3.17",
    ]


def test_storeys_told_apart_only_by_their_elevation(tmp_path: Path) -> None:
    # every storey placed at the building's height, the elements carrying their own heights
    h = base()
    h.flat = True
    write(h, tmp_path / "flat.ifc")
    assert model_of(tmp_path, "flat", tmp_path / "flat.ifc")[1] == plain(tmp_path)


# ---------- several buildings ----------


def with_garage() -> House:
    h = base()
    h.annex = {"G": 0.0}
    h.walls += [
        WallSpec("G-south", (10.0, 0.0), (14.0, 0.0), "G", OUTER, (0.0, -1.0)),
        WallSpec("G-north", (14.0, 3.0), (10.0, 3.0), "G", OUTER, (0.0, 1.0)),
    ]
    return h


def test_one_building_per_import(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, with_garage(), tmp_path)
    # the house has more walls: it is read, the garage is named, its walls are not counted
    assert (
        'not imported: 1 IfcBuilding "Garage" (one building per import; --building picks it)\n'
        in out
    )
    assert sorted(e.line() for e in load(sh)) == plain(tmp_path)


def test_the_building_asked_for_and_kept(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, with_garage(), tmp_path, "h.ifc", "--building", "garage")
    assert 'not imported: 1 IfcBuilding "Haus"' in out
    assert lines(sh, "G", "w1", "w2") == [
        "level G z=0",
        "wall w1 G W335 a=10,0 b=14,0 h=2.55",
        "wall w2 G W335 a=14,3 b=10,3 h=2.55 flip",
    ]
    # the next file goes to the same building without being told
    write(with_garage(), tmp_path / "h2.ifc")
    code, out = sh("import", "ifc", str(tmp_path / "h2.ifc"), "--by", "t")
    assert code == 0 and "nothing to change" in out.splitlines()[0]
    code, out = sh("import", "ifc", str(tmp_path / "h2.ifc"), "--by", "t", "--building", "Schuppen")
    assert code == 1
    assert (
        out.strip() == 'uea: h2.ifc has no building \'Schuppen\'; its buildings: "Haus", "Garage"'
    )


# ---------- walls ----------


def test_a_layer_set_on_the_wall_type_only(tmp_path: Path) -> None:
    h = base()
    h.walls = [replace(w, first=None, on_type=True) if w.type_name else w for w in h.walls]
    write(h, tmp_path / "typed.ifc")
    # without a usage the body is centred on the line, which is the core's centre in the fixture
    assert model_of(tmp_path, "typed", tmp_path / "typed.ifc")[1] == plain(tmp_path)


@pytest.mark.parametrize(
    ("parts", "note"),
    [
        ("skins", "made of 3 parts, one per layer; imported as one wall"),
        ("stacked", "made of 2 parts one above another; imported as one wall, the tallest part's"),
    ],
)
def test_a_wall_in_parts_is_one_wall(tmp_path: Path, parts: str, note: str) -> None:
    # skins: a part per layer, each with its material, side by side; stacked: the wall's own
    # layers up to 2 m, a thinner wall of timber above it
    h = base()
    h.walls = [replace(w, parts=parts) if w.name == "EG-south" else w for w in h.walls]
    write(h, tmp_path / "parts.ifc")
    out, got = model_of(tmp_path, "parts", tmp_path / "parts.ifc")
    assert f"note: wall EG-south: {note}" in out
    assert got == plain(tmp_path)


@pytest.mark.parametrize(
    ("axis", "why"), [(True, "curved"), (False, "its footprint is no straight strip")]
)
def test_a_curved_wall_is_reported(sh: Shell, tmp_path: Path, axis: bool, why: str) -> None:
    # a bay of 140° on a radius of 2 m south of the house: its axis says it is an arc; without
    # one, its footprint fills less than 80 % of the strip around it
    h = base()
    h.curved.append(CurvedSpec("Erker", (3.0, -2.0), 2.0, 200.0, 340.0, axis=axis))
    out = do_import(sh, h, tmp_path)
    assert f'not imported: 1 IfcWall "Erker" ({why})' in out
    assert "9 walls" in out


# ---------- curtain walls ----------


def glass_front(*doors: tuple[float, float, float]) -> House:
    """The north wall of the EG as a curtain wall 0.15 deep on the same axis, from the slab to the
    underside of the slab above; the inner wall reaches it."""
    h = base().without("EG-north")
    h.walls = [replace(w, p1=(3.5, 3.925)) if w.name == "EG-inner" else w for w in h.walls]
    h.curtains.append(
        CurtainSpec("Glas", "EG", (6.0, 4.0), (0.0, 4.0), type_name="PR 50", u=1.1, doors=doors)
    )
    return h


def test_a_curtain_wall_is_a_wall_with_windows(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, glass_front(), tmp_path)
    assert "issues: 0 errors · 0 warnings" in out
    # a wall of its depth, and its glass from the FFL to the top of the wall (2.55 - 0): one
    # window over its whole length, of a type named after the curtain wall's with its U-value
    assert lines(sh, "CW150", "PR-50", "w9", "f3") == [
        "type CW150 wall layers=*curtain:0.15",
        "type PR-50 win uw=1.1",
        "wall w9 EG CW150 a=6,4 b=0,4",
        "win f3 w9 6x2.55 x=0+ sill=0 type=PR-50",
    ]
    # the rooms close against it as they did against the wall
    assert sh("check")[1].startswith("0 errors")


def test_the_doors_of_a_curtain_wall(sh: Shell, tmp_path: Path) -> None:
    # a door 1 m wide, 1 m from the east end: x=4..5. The glass is the rest on either side
    do_import(sh, glass_front((1.0, 1.0, 2.2)), tmp_path)
    assert lines(sh, "d1", "f3", "f4") == [
        "door d1 w9 1x2.2 x=4+",
        "win f3 w9 4x2.55 x=0+ sill=0 type=PR-50",
        "win f4 w9 1x2.55 x=5+ sill=0 type=PR-50",
    ]
    # the door moves 0.5 m west in a newer file: the glass on both sides follows, ids stay
    out = do_import(sh, glass_front((1.5, 1.0, 2.2)), tmp_path, "h2.ifc")
    assert out.splitlines()[0].endswith("ok (batch 2): 1 doors · 2 windows")
    assert lines(sh, "d1", "f3", "f4") == [
        "door d1 w9 1x2.2 x=3.5+",
        "win f3 w9 3.5x2.55 x=0+ sill=0 type=PR-50",
        "win f4 w9 1.5x2.55 x=4.5+ sill=0 type=PR-50",
    ]


# ---------- niches ----------


def test_niches(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.recesses += [
        # 0.1 m into the inside face of the south wall: past 0.015 m of plaster, 0.085 m of core
        RecessSpec("N1", "EG-south", 4.0, 0.8, 0.5, 1.0, depth=0.1, side=1.0),
        # 0.12 m into the outside face of the east wall, from the floor: 0.02 m render, 0.1 core
        RecessSpec("N2", "EG-east", 1.0, 0.6, 0.0, 2.0, depth=0.12, side=-1.0),
        # through the north wall (which runs west): an opening without a fill, a hole (0039)
        RecessSpec("N3", "EG-north", 3.0, 0.6, 0.3, 0.6),
    ]
    out = do_import(sh, h, tmp_path)
    assert "2 niches · 1 holes" in out and "issues: 0 errors · 0 warnings" in out
    assert "not imported" not in out
    assert [x.line() for x in load(sh).of_kind("hole")] == ["hole ho1 w3 0.6x0.6 x=2.4+ sill=0.3"]
    assert lines(sh, "ni1", "ni2") == [
        "niche ni1 w1.n 0.8x1 x=4+ sill=0.5 d=0.085",
        "niche ni2 w2.e 0.6x2 y=1+ d=0.1",
    ]

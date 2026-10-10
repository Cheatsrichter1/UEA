"""`uea import ifc`, the shapes (decision 0030): grids, openings in floors, stairs and roofs.

Fixtures come from `tests/ifc_make.py` like those of `test_import.py`: a 6 m by 4 m house on two
storeys, EG at 0 and OG at 2.9 (the SSLs are -0.15 and 2.75), outer walls of 0.335 m with a 0.30 m
core, so the faces of the cores lie 0.15 m from the axes. Every number is worked out beside the
assertion that uses it.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from shapely.geometry import Polygon

pytest.importorskip("ifcopenshell")

from tests.conftest import Shell, model_from
from tests.ifc_make import (
    GridSpec,
    House,
    RecessSpec,
    Ring,
    RoofSpec,
    SlabSpec,
    StairSpec,
    Tread,
    VoidSpec,
    gable_x,
    house,
    outward,
    rect,
    stair_steps,
    write,
)
from tests.test_import import derived, do_import, lines, load
from uea.cli import main
from uea.derive import Derived, report
from uea.export.ifc import export_ifc
from uea.importer.build import rects
from uea.importer.roofs import nice, pitch_degrees
from uea.importer.surfaces import Shape, flat_tops, merge, planes, top_z
from uea.packs.arch.geometry import RoofGeo
from uea.project import Project

RISE = 2.9 / 16
"""16 risers between EG and OG."""


def base() -> House:
    """The house of `test_import` without its extras (a roof without a body, a column)."""
    h = house()
    h.extras = []
    return h


# ---------- the surfaces of a body ----------


def solid(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Shape:
    """A box of triangles with every face looking out."""
    verts = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    faces = [  # bottom, top, y0, y1, x0, x1
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
        (1, 2, 6),
        (1, 6, 5),
    ]
    return Shape(np.array(verts, dtype=float), np.array(faces))


def surface(*rings: Ring) -> Shape:
    """Quadrilaterals that look up, two triangles each."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for ring in rings:
        k = len(verts)
        verts += outward(ring, (0.0, 0.0, 1.0))
        faces += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    return Shape(np.array(verts, dtype=float), np.array(faces))


def joined(*shapes: Shape) -> Shape:
    got = merge(shapes)
    assert got is not None
    return got


def test_flat_tops_are_one_tread_within_4_mm() -> None:
    # two neighbours 3 mm apart are one tread at the mean height (0.5 + 0.503) / 2; the third is
    # one riser (0.18125) higher
    s = joined(
        solid(0, 0, 0, 1, 1, 0.5), solid(1, 0, 0, 2, 1, 0.503), solid(2, 0, 0, 3, 1, 0.68125)
    )
    got = flat_tops(s)
    assert [z for z, _ in got] == pytest.approx([0.5015, 0.68125])
    assert [g.area for _, g in got] == pytest.approx([2.0, 1.0])


def test_flat_tops_leave_out_undersides_and_scraps() -> None:
    # the underside of the slab looks down; 0.1 x 0.1 is 0.01 m², below the 0.02 m² of a tread
    got = flat_tops(joined(solid(0, 0, 0, 2, 1, 0.2), solid(5, 5, 0, 5.1, 5.1, 0.4)))
    assert [z for z, _ in got] == pytest.approx([0.2])


def test_top_z_is_the_highest_face_above_a_point() -> None:
    s = joined(solid(0, 0, 0, 2, 2, 1.0), solid(0.5, 0.5, 1.0, 1.5, 1.5, 1.4))
    assert top_z(s, [(1.0, 1.0), (0.25, 0.25), (3.0, 3.0)]) == [
        pytest.approx(1.4),
        pytest.approx(1.0),
        None,
    ]


def test_the_planes_of_a_gable_are_two_planes_of_the_same_slope() -> None:
    south, north = gable_x(0.0, 6.0, 0.0, 4.0, 3.0, 30)
    got = planes(surface(south, north))
    assert len(got) == 2
    t = math.tan(math.radians(30))
    assert sorted(p.b for p in got) == pytest.approx([-t, t], abs=1e-4)
    assert [p.a for p in got] == pytest.approx([0.0, 0.0], abs=1e-4)
    assert [p.area for p in got] == pytest.approx([12.0, 12.0])  # 6 m long, 2 m in plan each
    low = next(p for p in got if p.b > 0)
    assert (low(3.0, 0.0), low(3.0, 2.0)) == pytest.approx((3.0, 3.0 + 2 * t), abs=1e-4)


def test_planes_leave_out_faces_steeper_than_a_roof() -> None:
    # the sides of a box are vertical; its top is flat, its underside faces down
    top = planes(solid(0, 0, 0, 2, 1, 0.5))
    assert [(p.area, p.slope, p(1.0, 0.5)) for p in top] == [
        (pytest.approx(2.0), pytest.approx(0.0), pytest.approx(0.5))
    ]
    under = planes(solid(0, 0, 0, 2, 1, 0.5), up=False)
    assert [p(1.0, 0.5) for p in under] == pytest.approx([0.0])


def test_merge_keeps_the_faces_of_each_body() -> None:
    s = joined(solid(0, 0, 0, 1, 1, 1), solid(2, 0, 0, 3, 1, 2))
    assert s.verts.shape == (16, 3) and s.faces.shape == (24, 3)
    assert int(s.faces[12:].min()) == 8 and int(s.faces[:12].max()) == 7
    assert merge([]) is None


def test_rectilinear_outlines_are_cut_into_rectangles() -> None:
    assert rects(Polygon(rect(0, 0, 2, 1))) == [pytest.approx((0, 0, 2, 1))]
    ell = Polygon(((1, 1), (2, 1), (2, 1.5), (1.5, 1.5), (1.5, 2), (1, 2)))
    assert rects(ell) == [pytest.approx((1, 1, 2, 1.5)), pytest.approx((1, 1.5, 1.5, 2))]
    assert rects(Polygon(((3, 1), (4, 1), (3.5, 2)))) is None
    # 1 cm out of square is still one rectangle, 2 m by 1 m
    assert rects(Polygon(((0, 0), (2, 0.01), (2, 1), (0, 1.01)))) == [
        pytest.approx((0, 0, 2, 1.01))
    ]


def test_lengths_go_to_5_mm_and_pitches_to_half_degrees() -> None:
    assert (nice(0.4949), nice(0.7078), nice(0.0024), nice(1.2)) == (0.495, 0.71, 0.0, 1.2)
    # within 0.05° of a half degree: that half degree; else two decimals
    assert pitch_degrees(math.tan(math.radians(30.04))) == 30.0
    assert pitch_degrees(math.tan(math.radians(30.2))) == 30.2
    assert pitch_degrees(0.3) == 16.7  # atan 0.3 = 16.699°, 0.2° from 16.5
    assert pitch_degrees(1.0) == 45.0


# ---------- grids ----------


def grid_house(x: float = 0.5, *, other: bool = True) -> House:
    """Grid A at x (the origin of the grid) and B 1.5 m east of it."""
    h = base()
    h.grids = [GridSpec("A", (0, -1), (0, 5))]
    h.grid_at = (x, 0.0)
    if other:
        h.grids.append(GridSpec("B", (1.5, -1), (1.5, 5)))
    return h


def test_grid_axes_become_grids(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.grid_at = (0.5, 0.25)
    h.grids = [
        GridSpec("A", (0, -1), (0, 5)),
        GridSpec("B", (3.5, -1), (3.5, 5)),
        GridSpec("1", (-1, 0), (7, 0), True),
        GridSpec("2", (-1, 4), (7, 4), True),
        GridSpec("D", (0, 0), (5, 5)),
        GridSpec("EG", (6, -1), (6, 5)),
    ]
    out = do_import(sh, h, tmp_path)
    # the grid starts at (0.5, 0.25): its U axes at 0, 3.5 and 6 lie at x = 0.5, 4 and 6.5, its V
    # axes at 0 and 4 at y = 0.25 and 4.25. "1" and "2" are numbers, so they get a letter; "EG" is
    # the name of a level; D runs diagonally.
    assert lines(sh, "A", "B", "EG_2", "G1", "G2") == [
        "grid A x=0.5",
        "grid B x=4",
        "grid EG_2 x=6.5",
        "grid G1 y=0.25",
        "grid G2 y=4.25",
    ]
    assert "5 grids" in out
    assert "not imported: 1 IfcGrid axis (not parallel to x or y)" in out


def test_a_grid_turned_a_quarter_turn_swaps_its_axes(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.grid_at = (10.0, 2.0)
    h.grid_x = (0.0, 1.0)
    h.grids = [GridSpec("A", (1.5, -1), (1.5, 5)), GridSpec("B", (-1, 3), (7, 3), True)]
    do_import(sh, h, tmp_path)
    # the x of the grid points north and its y west: (gx, gy) lies at (10 - gy, 2 + gx), so the
    # axis gx = 1.5 is the line y = 3.5 and the axis gy = 3 is the line x = 7
    assert lines(sh, "A", "B") == ["grid A y=3.5", "grid B x=7"]


def test_grids_follow_the_file(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, grid_house(), tmp_path)
    assert lines(sh, "A", "B") == ["grid A x=0.5", "grid B x=2"]
    out = do_import(sh, grid_house(0.6), tmp_path, "h2.ifc")
    assert "ok (batch 2): 2 grids" in out
    assert lines(sh, "A", "B") == ["grid A x=0.6", "grid B x=2.1"]
    # moved in UEA: kept, the other one still follows
    assert sh("apply", "--by", "t", "-m", "move", stdin="~ A x=1")[0] == 0
    out = do_import(sh, grid_house(0.7), tmp_path, "h3.ifc")
    assert "kept: A (A): edited in UEA since the import" in out
    assert lines(sh, "A", "B") == ["grid A x=1", "grid B x=2.2"]
    # a grid the file lost goes; the summary names only what happened
    out = do_import(sh, grid_house(0.7, other=False), tmp_path, "h4.ifc")
    assert out.splitlines()[0].endswith("ok (batch 5): 1 removed")
    assert "B" not in load(sh)


def test_a_grid_the_file_lost_stays_while_a_wall_stands_on_it(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, grid_house(), tmp_path)
    own = "+ wall _ EG AW-33-5 y=2+ x=A..B"
    assert sh("apply", "--by", "t", "-m", "own wall", stdin=own)[0] == 0
    out = do_import(sh, grid_house(other=False), tmp_path, "h2.ifc")
    assert "kept: B: gone from the IFC, but w10 still refers to it" in out
    assert "B" in load(sh)


# ---------- openings in the floor ----------


def stair_at(
    x0: float,
    y0: float,
    up: str,
    w: float,
    n: int,
    tread: float,
    *,
    name: str = "Treppe",
    parts: bool = True,
    root: bool = True,
    status: str | None = None,
    **steps: Any,
) -> House:
    """A stair of n risers from EG to OG, its first step at the corner (x0, y0)."""
    h = base()
    fl, land = stair_steps(x0, y0, up, w, n, tread, 2.9 / n, **steps)
    h.stairs.append(StairSpec(name, "EG", fl, land, parts=parts, root=root, status=status))
    return h


STRAIGHT = "stair st1 EG OG x=1+ y=0.5+ up=e w=1 n=16 tread=0.27"


def stair_house(
    tread: float = 0.27,
    name: str = "Treppe",
    *,
    x0: float = 1.0,
    void: bool = True,
    margin: float = 0.0,
    **spec: Any,
) -> House:
    """The straight stair 1 m wide from (x0, 0.5) climbing east, and the opening over it, `margin`
    larger than the stair on each side."""
    h = stair_at(x0, 0.5, "e", 1.0, 16, tread, name=name, **spec)
    if void:
        x1 = x0 + 15 * tread
        h.voids.append(
            VoidSpec("Loch", "OG-slab", rect(x0 - margin, 0.5 - margin, x1 + margin, 1.5 + margin))
        )
    return h


def test_openings_in_a_floor_become_voids_in_rectangles(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.voids += [
        VoidSpec("Schacht", "OG-slab", rect(4.5, 3.0, 5.1, 3.8)),
        VoidSpec("L", "OG-slab", ((1, 1), (2, 1), (2, 1.5), (1.5, 1.5), (1.5, 2), (1, 2))),
        VoidSpec("Dreieck", "OG-slab", ((3, 1), (4, 1), (3.5, 2))),
    ]
    out = do_import(sh, h, tmp_path)
    assert "3 voids" in out
    assert "not imported: 1 slab opening (not made of rectangles)" in out
    m = load(sh)
    # the L is two rectangles: 1 m x 0.5 m and 0.5 m x 0.5 m; the triangle is left out
    assert {m[v].line().removeprefix(f"void {v} sl2 ") for v in ("v1", "v2", "v3")} == {
        "x=4.5..5.1 y=3..3.8",
        "x=1..2 y=1..1.5",
        "x=1..1.5 y=1.5..2",
    }
    assert sum(derived(sh).arch.voids[v].poly.area for v in ("v1", "v2", "v3")) == (
        pytest.approx(0.6 * 0.8 + 0.5 + 0.25)
    )


@pytest.mark.parametrize("element", [False, True], ids=["hole in the body", "and an element"])
def test_a_hole_in_the_body_of_a_slab_is_a_void_too(
    sh: Shell, tmp_path: Path, element: bool
) -> None:
    h = base()
    h.slabs[1] = replace(h.slabs[1], holes=(rect(4.5, 0.5, 5.1, 1.3),))
    if element:  # the same opening, written twice: one void
        h.voids.append(VoidSpec("Loch", "OG-slab", rect(4.5, 0.5, 5.1, 1.3)))
    out = do_import(sh, h, tmp_path)
    assert "1 voids" in out
    assert lines(sh, "v1") == ["void v1 sl2 x=4.5..5.1 y=0.5..1.3"]
    assert "v2" not in load(sh)


@pytest.mark.parametrize(
    ("margin", "tied"), [(0.0, True), (0.01, True), (0.03, False)], ids=["0 cm", "1 cm", "3 cm"]
)
def test_the_opening_over_a_stair_stays_tied_to_it(
    sh: Shell, tmp_path: Path, margin: float, tied: bool
) -> None:
    do_import(sh, stair_house(margin=margin), tmp_path)
    # the stair covers 15 x 0.27 = 4.05 m by 1 m, the opening the margin more on every side: it
    # overlaps 4.05 / (4.07 x 1.02) = 0.9756 at 1 cm, 4.05 / (4.11 x 1.06) = 0.9296 at 3 cm. Above
    # 0.95 it is the stair's opening, below it a rectangle of its own.
    want = "void v1 sl2 over=st1" if tied else "void v1 sl2 x=0.97..5.08 y=0.47..1.53"
    assert lines(sh, "v1", "st1") == [want, STRAIGHT]


def test_an_opening_in_a_storey_without_walls_is_reported(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.storeys["DG"] = 5.8
    ring = ((-0.2, -0.2), (6.2, -0.2), (6.2, 4.2), (-0.2, 4.2))
    h.slabs.append(SlabSpec("DG-slab", "DG", 5.8, ring))
    h.voids.append(VoidSpec("Loch", "DG-slab", rect(1, 1, 2, 2)))
    out = do_import(sh, h, tmp_path)
    assert (
        "not imported: 1 IfcSlab (no storey with walls at its top)"
        " · 1 slab opening (its slab was not imported)"
    ) in out


def test_a_niche_in_a_wall_is_not_a_window(sh: Shell, tmp_path: Path) -> None:
    h = base()
    h.recesses.append(RecessSpec("Nische", "EG-south", 4.0, 0.8, 0.5, 1.0))
    out = do_import(sh, h, tmp_path)
    assert "not imported: 1 IfcOpeningElement (a recess in a wall)" in out
    assert "3 windows" in out and "1 doors" in out


# ---------- stairs ----------


@pytest.mark.parametrize(
    "spec",
    [{}, {"parts": False}, {"root": False}],
    ids=["flights and a landing", "one body", "a lone flight"],
)
def test_a_straight_stair_however_it_is_written(
    sh: Shell, tmp_path: Path, spec: dict[str, Any]
) -> None:
    out = do_import(sh, stair_house(void=False, **spec), tmp_path)
    # 16 risers of 2.9 / 16 between EG and OG, 15 treads of 0.27 from (1, 0.5) climbing east
    assert "1 stairs" in out
    assert lines(sh, "st1") == [STRAIGHT]
    s = derived(sh).arch.stairs["st1"]
    assert (s.x0, s.x1, s.y0, s.y1) == pytest.approx((1.0, 5.05, 0.5, 1.5))
    assert s.riser == pytest.approx(RISE)


@pytest.mark.parametrize(
    ("status", "word", "spec"),
    [("DEMOLISH", "demolish", {}), ("TEMPORARY", "temp", {"root": False})],
    ids=["a stair", "a flight"],
)
def test_the_status_of_a_stair_is_kept(
    sh: Shell, tmp_path: Path, status: str, word: str, spec: dict[str, Any]
) -> None:
    do_import(sh, stair_house(void=False, status=status, **spec), tmp_path)
    assert lines(sh, "st1") == [f"{STRAIGHT} {word}"]


SHAPED = [
    pytest.param(
        {
            "x0": 2.0,
            "y0": 1.0,
            "up": "n",
            "w": 1.0,
            "n": 16,
            "tread": 0.27,
            "shape": "l",
            "turn": "r",
        },
        "x=2+ y=1+ up=n w=1 n=16 tread=0.27 shape=l turn=r",
        id="L with a landing, turning right",
    ),
    pytest.param(
        {
            "x0": 2.0,
            "y0": 1.0,
            "up": "n",
            "w": 1.0,
            "n": 16,
            "tread": 0.27,
            "shape": "l",
            "turn": "l",
        },
        "x=2+ y=1+ up=n w=1 n=16 tread=0.27 shape=l turn=l",
        id="L with a landing, turning left",
    ),
    pytest.param(
        {"x0": 1.0, "y0": 1.0, "up": "e", "w": 1.0, "n": 16, "tread": 0.26, "shape": "l", "n1": 5},
        "x=1+ y=1+ up=e w=1 n=16 tread=0.26 shape=l turn=l n1=5",
        id="L with a short first flight",
    ),
    pytest.param(
        {
            "x0": 1.0,
            "y0": 1.0,
            "up": "n",
            "w": 0.9,
            "n": 17,
            "tread": 0.26,
            "shape": "u",
            "gap": 0.2,
        },
        "x=1+ y=1+ up=n w=0.9 n=17 tread=0.26 shape=u turn=l gap=0.2",
        id="U with a well of 0.2",
    ),
    pytest.param(
        {
            "x0": 1.0,
            "y0": 1.0,
            "up": "n",
            "w": 0.9,
            "n": 17,
            "tread": 0.26,
            "shape": "u",
            "gap": 0.0,
        },
        "x=1+ y=1+ up=n w=0.9 n=17 tread=0.26 shape=u turn=l gap=0",
        id="U with the flights touching",
    ),
]


@pytest.mark.parametrize("parts", [True, False], ids=["parts", "one body"])
@pytest.mark.parametrize(("kw", "tail"), SHAPED)
def test_stairs_with_a_turn(
    sh: Shell, tmp_path: Path, kw: dict[str, Any], tail: str, parts: bool
) -> None:
    do_import(sh, stair_at(**kw, parts=parts), tmp_path)
    assert lines(sh, "st1") == [f"stair st1 EG OG {tail}"]


def test_a_deeper_last_tread_is_a_note(sh: Shell, tmp_path: Path) -> None:
    h = stair_house(void=False)
    steps = list(h.stairs[0].flights[0])
    z, o = steps[-1]
    steps[-1] = (z, rect(o[0][0], o[0][1], o[0][0] + 0.40, o[2][1]))
    h.stairs[0] = replace(h.stairs[0], flights=(tuple(steps),))
    out = do_import(sh, h, tmp_path)
    # 0.13 m² more than the 4.05 m² of a regular stair: 0.13 / 4.18 = 3.1 %
    assert lines(sh, "st1") == [STRAIGHT]
    assert "note: stair Treppe: its treads differ from UEA's by 3% of their area" in out


def stair_of(
    flights: tuple[tuple[Tread, ...], ...], landings: tuple[Tread, ...] = (), **spec: Any
) -> House:
    h = base()
    h.stairs.append(StairSpec("Treppe", "EG", flights, landings, **spec))
    return h


def staggered() -> House:
    """The straight stair with its upper half 0.5 m further north: no stair of UEA."""
    (fl,), _ = stair_steps(1.0, 0.5, "e", 1.0, 16, 0.27, RISE)
    moved = tuple(
        (z, tuple((x, y + (0.5 if i >= 8 else 0.0)) for x, y in o)) for i, (z, o) in enumerate(fl)
    )
    return stair_of((moved,))


def to_a_storey_without_walls() -> House:
    """A stair from OG up to a DG that has a slab but no walls, so no level in the model."""
    h = base()
    h.storeys["DG"] = 5.8
    fl, _ = stair_steps(1.0, 0.5, "e", 1.0, 16, 0.27, RISE, z0=2.9)
    h.stairs.append(StairSpec("Treppe", "OG", fl))
    return h


(FLIGHT,), _ = stair_steps(1.0, 0.5, "e", 1.0, 16, 0.27, RISE)


@pytest.mark.parametrize(
    ("h", "why"),
    [
        pytest.param(
            stair_of(stair_steps(1.0, 0.5, "e", 1.0, 8, 0.27, 0.35)[0]),
            "its steps are not between 8 and 30 cm high",
            id="risers of 35 cm",
        ),
        # 2.9 m is 14.5 risers of 0.20: no whole number of them
        pytest.param(
            stair_of(stair_steps(1.0, 0.5, "e", 1.0, 14, 0.27, 0.2)[0]),
            "no two storeys of the model have a whole number of its risers between them",
            id="risers that do not fit the storeys",
        ),
        pytest.param(
            to_a_storey_without_walls(),
            "no two storeys of the model have a whole number of its risers between them",
            id="to a storey without walls",
        ),
        pytest.param(
            stair_of(((FLIGHT[0],),)), "fewer than two tread levels in its body", id="one step"
        ),
        pytest.param(stair_of(()), "no body", id="no body"),
        pytest.param(
            stair_of((FLIGHT[2:],)), "its first two treads are missing", id="first treads missing"
        ),
        pytest.param(
            stair_of(stair_steps(1.0, 0.5, "e", 1.0, 16, 0.12, RISE)[0]),
            "its treads are 0.12 deep and 1 wide",
            id="treads of 12 cm",
        ),
        pytest.param(
            staggered(), "its treads match no straight, L or U stair of UEA", id="staggered"
        ),
    ],
)
def test_a_stair_that_fits_no_stair_of_uea_is_reported(
    sh: Shell, tmp_path: Path, h: House, why: str
) -> None:
    out = do_import(sh, h, tmp_path)
    assert f'not imported: 1 IfcStair "Treppe" ({why})' in out
    assert not list(load(sh).of_kind("stair"))


def test_the_lone_flights_of_an_l_stair_are_not_one_stair(sh: Shell, tmp_path: Path) -> None:
    # without the IfcStair and its landing, the first flight is 7 of the 15 treads and the second
    # starts at the ninth
    fl, land = stair_steps(2.0, 1.0, "n", 1.0, 16, 0.27, RISE, shape="l", turn="r")
    out = do_import(sh, stair_of(fl, land, root=False), tmp_path)
    assert (
        'not imported: 1 IfcStairFlight "Treppe Lauf 1" (its treads match no straight, L or U'
        ' stair of UEA) · 1 IfcStairFlight "Treppe Lauf 2" (its first two treads are missing)'
    ) in out


def test_a_moved_stair_follows_and_its_opening_stays_tied(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, stair_house(), tmp_path)
    out = do_import(sh, stair_house(x0=1.2), tmp_path, "h2.ifc")
    assert out.splitlines()[0].endswith("ok (batch 2): 1 stairs")
    assert lines(sh, "st1", "v1") == [
        "stair st1 EG OG x=1.2+ y=0.5+ up=e w=1 n=16 tread=0.27",
        "void v1 sl2 over=st1",
    ]
    assert sh("apply", "--by", "t", "-m", "wider", stdin="~ st1 w=1.1")[0] == 0
    out = do_import(sh, stair_house(x0=1.4), tmp_path, "h3.ifc")
    assert "kept: st1 (stair Treppe): edited in UEA since the import" in out
    assert lines(sh, "st1") == ["stair st1 EG OG x=1.2+ y=0.5+ up=e w=1.1 n=16 tread=0.27"]


def test_an_opening_over_a_stair_deleted_in_uea_is_a_rectangle(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, stair_house(void=False), tmp_path)
    assert sh("apply", "--by", "t", "-m", "no stair", stdin="- st1")[0] == 0
    out = do_import(sh, stair_house(), tmp_path, "h2.ifc")
    assert "kept: st1 (stair Treppe): removed in UEA since the import" in out
    # the opening is new; the stair it was cut for is not in the model, so it is its rectangle
    assert lines(sh, "v1") == ["void v1 sl2 x=1..5.05 y=0.5..1.5"]
    assert "st1" not in load(sh)


# ---------- roofs ----------

T30 = math.tan(math.radians(30))
SKIN = 0.2 * math.sqrt(1 + T30 * T30)
"""The 0.2 m of tiles and rafters square to a 30° slope, measured vertically: 0.2309."""
GABLE = "roof rf1 OG DACH-20 gable ridge=x pitch=30 knee=0.5 eave=0.4 verge=0.3"


def tilted(
    x0: float, y0: float, x1: float, y1: float, z: float, a: float = 0.0, b: float = 0.0
) -> Ring:
    """A rectangle in the plane that is z at (x0, y0) and rises a per metre in x, b in y."""
    return tuple(
        (x, y, z + a * (x - x0) + b * (y - y0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    )


def gabled(knee: float = 0.5, *, follow: bool = True, **spec: Any) -> House:
    """The OG under a 30° gable roof with its ridge along x: the rafters `knee` above the SSL (2.75)
    at the outer faces of the cores (y = -0.15 and 4.15), eaves 0.4 and verges 0.3 past them, the
    ridge over y = 2. With `follow` the long walls end under the rafters over their axes and the
    gable walls rise with them to the ridge. The OG window would stick out of its wall."""
    h = base().without("OG-win-1")
    foot = 2.75 + knee
    top = gable_x(-0.45, 6.45, -0.55, 4.55, foot + SKIN - 0.4 * T30, 30)
    eaves, ridge = foot + 0.15 * T30, foot + 2.15 * T30
    for i, w in enumerate(h.walls):
        if w.storey != "OG" or not follow:
            continue
        if w.name in ("OG-south", "OG-north"):
            h.walls[i] = replace(w, z1=eaves)
        else:
            h.walls[i] = replace(w, top=((0.0, eaves), (2.0, ridge), (4.0, eaves)))
    spec.setdefault("drop", SKIN)
    h.roofs = [RoofSpec("Dach", "OG", top, **spec)]
    return h


def roof_only(*top: Ring, **spec: Any) -> House:
    h = base().without("OG-win-1")
    h.roofs = [RoofSpec("Dach", "OG", top, **spec)]
    return h


@pytest.mark.parametrize(
    ("spec", "type_line"),
    [
        ({}, "type DACH-20 roof layers=ziegel:0.05,*sparren:0.15"),
        ({"parts": False}, "type DACH-20 roof layers=ziegel:0.05,*sparren:0.15"),
        ({"type_name": None}, "type R200 roof layers=ziegel:0.05,*sparren:0.15"),
        ({"layers": None}, "type DACH-20 roof layers=*roof:0.2"),
        ({"drop": None}, "type DACH-20 roof layers=ziegel:0.05,*sparren:0.15"),
    ],
    ids=["slabs in a roof", "one body", "no type", "no layers", "a surface with layers"],
)
def test_a_gable_roof(sh: Shell, tmp_path: Path, spec: dict[str, Any], type_line: str) -> None:
    out = do_import(sh, gabled(**spec), tmp_path)
    assert "1 roofs" in out and "note: roof" not in out and "note: wall" not in out
    name = type_line.split()[1]
    # the rafters lie 0.5 above the SSL at the faces of the cores; the eaves and verges reach
    # 0.4 and 0.3 past those faces
    assert lines(sh, name, "rf1") == [type_line, GABLE.replace("DACH-20", name)]
    # every wall of the OG ends under the roof
    assert lines(sh, "w5", "w6", "w7", "w8") == [
        "wall w5 OG AW-33-5 a=0,0 b=6,0 top=rf1 lb",
        "wall w6 OG AW-33-5 a=6,0 b=6,4 top=rf1 lb",
        "wall w7 OG AW-33-5 a=6,4 b=0,4 top=rf1 lb",
        "wall w8 OG AW-33-5 a=0,4 b=0,0 top=rf1 lb",
    ]
    g = derived(sh).arch.roofs["rf1"]
    # eaves: 2.75 + 0.5 + 0.2309 of skin; ridge 2.15 m in from the face: 1.2413 higher
    assert (g.eaves_z, g.ridge_z) == pytest.approx((3.4809, 4.7222), abs=1e-4)


def test_roof_slabs_without_a_roof_are_one_roof(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, gabled(root=False), tmp_path)
    # no type either: the name says the thickness
    assert lines(sh, "R200", "rf1") == [
        "type R200 roof layers=ziegel:0.05,*sparren:0.15",
        GABLE.replace("DACH-20", "R200"),
    ]
    assert "rf2" not in load(sh)


@pytest.mark.parametrize(
    ("spec", "type_line", "knee", "note"),
    [
        # the body is 0.3 deep vertically: 0.3 / 1.1547 = 0.2598 square to the slope; the
        # rafters lie 0.3 below the top, 0.3 - 0.2309 lower than the layers say
        (
            {"drop": 0.3},
            "type DACH-20 roof layers=*sparren:0.26",
            0.43,
            "note: roof Dach: its layers add up to 0.2 m, its body is 0.2598 m thick;"
            " the body counts",
        ),
        # a surface of 2 cm: the rafters lie 0.02 x 1.1547 below the top, 0.2309 - 0.0231 higher
        # than the walls say: knee 0.7078
        (
            {"drop": None, "layers": None},
            "type DACH-20 roof layers=*roof:0.02",
            0.71,
            "note: roof Dach: its body has no thickness in the file; 2 cm taken",
        ),
    ],
    ids=["the body counts", "a bare surface"],
)
def test_a_roof_whose_thickness_is_not_its_layers(
    sh: Shell, tmp_path: Path, spec: dict[str, Any], type_line: str, knee: float, note: str
) -> None:
    out = do_import(sh, gabled(**spec), tmp_path)
    assert note in out
    assert lines(sh, "DACH-20", "rf1") == [
        type_line,
        GABLE.replace("knee=0.5", f"knee={knee}"),
    ]
    # the walls end under the rafters the file has, not under these: they get their heights
    assert (
        "note: wall OG-east: its top slopes and is not the underside of the roof fitted on OG;"
        " set to its highest point"
    ) in out
    assert lines(sh, "w5", "w6") == [
        "wall w5 OG AW-33-5 a=0,0 b=6,0 h=0.5866 lb",
        "wall w6 OG AW-33-5 a=6,0 b=6,4 h=1.7413 lb",
    ]


def test_walls_under_a_roof_that_is_not_imported_get_their_height(
    sh: Shell, tmp_path: Path
) -> None:
    out = do_import(sh, replace(gabled(), roofs=[]), tmp_path)
    for side in ("east", "west"):
        assert (
            f"note: wall OG-{side}: its top slopes (under a roof); set to its highest point until"
            " the roof is modelled"
        ) in out
    # the long walls end at 2.75 + 0.5 + 0.15 x tan 30° = 3.3366, the gable walls at the ridge,
    # 2.75 + 0.5 + 2.15 x tan 30° = 4.4913
    assert lines(sh, "w5", "w6", "w7", "w8") == [
        "wall w5 OG AW-33-5 a=0,0 b=6,0 h=0.5866 lb",
        "wall w6 OG AW-33-5 a=6,0 b=6,4 h=1.7413 lb",
        "wall w7 OG AW-33-5 a=6,4 b=0,4 h=0.5866 lb",
        "wall w8 OG AW-33-5 a=0,4 b=0,0 h=1.7413 lb",
    ]


def test_a_roof_over_the_storey_below_stands_on_it(sh: Shell, tmp_path: Path) -> None:
    # the file puts it on the OG, but its rafters lie 1.2 above the SSL of the EG (-0.15)
    top = gable_x(-0.45, 6.45, -0.55, 4.55, -0.15 + 1.2 + SKIN - 0.4 * T30, 30)
    do_import(sh, roof_only(*top, drop=SKIN), tmp_path)
    assert lines(sh, "rf1") == [GABLE.replace("OG", "EG").replace("knee=0.5", "knee=1.2")]


def test_eaves_that_differ_by_side_are_averaged(sh: Shell, tmp_path: Path) -> None:
    south, _ = gable_x(-0.45, 6.45, -0.55, 4.55, 3.25 + SKIN - 0.4 * T30, 30)
    north = tilted(-0.45, 2.0, 6.45, 4.95, south[2][2], b=-T30)  # 0.8 past the north wall
    out = do_import(sh, roof_only(south, north, drop=SKIN), tmp_path)
    assert "note: roof Dach: eave overhang differs by side (0.4 to 0.8 m); the mean is taken" in out
    assert lines(sh, "rf1") == [GABLE.replace("eave=0.4", "eave=0.6")]


@pytest.mark.parametrize(
    ("gap", "want"),
    [
        (0.04, [GABLE.replace("DACH-20", "R200")]),
        # 6 cm apart: two sheds over their own extents, the rafters at their low edges 0.4 x
        # tan 30° = 0.2309 below the 0.5 at the walls
        (
            0.06,
            [
                "roof rf1 OG R200 shed up=n pitch=30 knee=0.27 x=-0.45..6.45 y=-0.55..2",
                "roof rf2 OG R200 shed up=s pitch=30 knee=0.27 x=-0.45..6.45 y=2.06..4.55",
            ],
        ),
    ],
    ids=["4 cm apart", "6 cm apart"],
)
def test_roof_slabs_that_touch_are_one_roof(
    sh: Shell, tmp_path: Path, gap: float, want: list[str]
) -> None:
    south, north = gable_x(-0.45, 6.45, -0.55, 4.55, 3.25 + SKIN - 0.4 * T30, 30)
    north = tilted(-0.45, 2.0 + gap, 6.45, 4.55, north[0][2] - gap * T30, b=-T30)
    out = do_import(sh, roof_only(south, north, drop=SKIN, root=False), tmp_path)
    assert [e.line() for e in load(sh).of_kind("roof")] == want
    if gap > 0.05:
        # the strip between them, 6.3 m along the outline of the OG and 6 cm wide, is open
        assert "W-ARCH-042 rf1 0.38 m² of the outline of OG lie under no roof" in out
        assert "its extent is given by x= y=, the outline of the storey does not fit it" in out


@pytest.mark.parametrize(
    ("top", "why"),
    [
        pytest.param(
            gable_x(-0.45, 6.45, -0.55, 4.55, -2.0, 30),
            "no storey lies below its eaves",
            id="below every storey",
        ),
        pytest.param(  # the rafters 0.2 below the SSL of the EG
            gable_x(-0.45, 6.45, -0.55, 4.55, -0.35 + SKIN - 0.4 * T30, 30),
            "its eaves lie below the slab of the storey it would stand on",
            id="eaves below the slab",
        ),
        pytest.param(  # 0.2 thick, its underside on the SSL of the EG
            (tilted(-0.5, -0.5, 6.5, 4.5, 0.05),),
            "its underside is not above the storey it would stand on",
            id="flat on the slab",
        ),
        pytest.param(
            (tilted(-0.5, -0.5, 6.5, 4.5, 5.0, a=0.1, b=0.1),),
            "a plane of its top is not parallel to the x or y axis",
            id="falling diagonally",
        ),
        pytest.param(
            (
                tilted(-0.5, -0.5, 6.5, 2.0, 3.5, b=0.4),
                tilted(-0.5, 2.0, 6.5, 4.5, 3.5, b=0.4),
            ),
            "its top has two planes falling to the s side",
            id="sawtooth",
        ),
        pytest.param(
            (
                tilted(-0.5, -0.5, 6.5, 2.0, 3.5, b=0.6),
                tilted(-0.5, 2.0, 6.5, 4.5, 5.0, b=-0.3),
                tilted(6.5, -0.5, 8.5, 4.5, 3.0, a=1.2),
            ),
            "its top has planes of more than two slopes",
            id="three slopes",
        ),
        pytest.param(  # same pitch, the ridge 0.55 off the middle: the eaves differ in height
            (
                tilted(-0.45, -0.55, 6.45, 1.45, 3.5, b=T30),
                tilted(-0.45, 1.45, 6.45, 4.55, 3.5 + 2 * T30, b=-T30),
            ),
            "its top matches no single gable, hip, shed, flat or mansard roof of UEA",
            id="ridge off the middle",
        ),
    ],
)
def test_a_roof_that_is_no_roof_of_uea_is_reported(
    sh: Shell, tmp_path: Path, top: tuple[Ring, ...], why: str
) -> None:
    out = do_import(sh, roof_only(*top, drop=0.2), tmp_path)
    assert f'not imported: 1 IfcRoof "Dach" ({why})' in out
    assert not list(load(sh).of_kind("roof"))


def test_a_roof_follows_the_file_and_goes_when_the_file_loses_it(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, gabled(), tmp_path)
    # higher: the roof changes, the walls still end under it
    out = do_import(sh, gabled(knee=0.6), tmp_path, "h2.ifc")
    assert out.splitlines()[0].endswith("ok (batch 2): 1 roofs")
    assert lines(sh, "rf1", "w6") == [
        GABLE.replace("knee=0.5", "knee=0.6"),
        "wall w6 OG AW-33-5 a=6,0 b=6,4 top=rf1 lb",
    ]
    # gone: the walls get their heights, then the roof can go
    out = do_import(sh, replace(gabled(knee=0.6), roofs=[]), tmp_path, "h3.ifc")
    assert out.splitlines()[0].endswith("ok (batch 3): 4 walls · 1 removed")
    assert "rf1" not in load(sh)
    assert lines(sh, "w5", "w6") == [
        "wall w5 OG AW-33-5 a=0,0 b=6,0 h=0.6866 lb",
        "wall w6 OG AW-33-5 a=6,0 b=6,4 h=1.8413 lb",
    ]


# ---------- the schemas ----------


def everything(schema: str) -> House:
    """A grid, the stair with its opening and the gable roof in one file."""
    h = gabled()
    h.schema = schema  # type: ignore[assignment]
    h.grids = [GridSpec("A", (0, -1), (0, 5)), GridSpec("1", (-1, 0), (7, 0), True)]
    s = stair_house()
    h.stairs, h.voids = s.stairs, s.voids
    return h


def test_the_three_schemas_give_the_same_model(sh: Shell, tmp_path: Path) -> None:
    got: dict[str, list[str]] = {}
    for schema in ("IFC2X3", "IFC4", "IFC4X3"):
        root = tmp_path / schema
        assert main(["init", str(root)]) == 0
        write_to = tmp_path / f"{schema}.ifc"
        write(everything(schema), write_to)
        code = main(["-C", str(root), "import", "ifc", str(write_to), "--by", "t"])
        assert code == 0
        got[schema] = sorted(e.line() for e in Project(root).load())
    assert got["IFC4X3"] == got["IFC4"]
    # IFC2X3 has no roof types: the type is named after its thickness
    assert got["IFC2X3"] == sorted(x.replace("DACH-20", "R200") for x in got["IFC4"])
    lines4 = got["IFC4"]
    for want in ("grid A x=0", "grid G1 y=0", GABLE, STRAIGHT, "void v1 sl2 over=st1"):
        assert want in lines4


# ---------- UEA's own exports, relabelled as another program's ----------

RT = """\
project rt "RT"
level EG z=0 fb=0.15 head=2.26
level OG z=2.9 fb=0.15 head=2.26
grid W x=0
grid E x=8
grid S y=0
grid N y=6
type AW wall layers=gips:0.01,*mw:0.3,putz:0.02
type DE slab layers=*stb:0.2
type DA roof layers=ziegel:0.05,*sparren:0.15
wall w1 EG AW y=S+ x=W..E lb
wall w2 EG AW x=E- y=w1..w3 lb
wall w3 EG AW y=N- x=W..E lb
wall w4 EG AW x=W+ y=w1..w3 lb
wall w5 OG AW y=S+ x=W..E lb{top}
wall w6 OG AW x=E- y=w5..w7 lb{top}
wall w7 OG AW y=N- x=W..E lb{top}
wall w8 OG AW x=W+ y=w5..w7 lb{top}
slab sl1 EG DE
slab sl2 OG DE
"""
"""8 m by 6 m to the outer faces, two storeys."""


def trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
) -> tuple[Derived, Derived, str]:
    """The model, exported, relabelled and imported into an empty project."""
    import ifcopenshell

    d0, rep = report(model_from(text))
    assert not rep.errors()
    export_ifc(d0, tmp_path / "own.ifc")
    f = ifcopenshell.open(str(tmp_path / "own.ifc"))
    f.header.file_name.originating_system = "Other 1.0"
    f.write(str(tmp_path / "other.ifc"))
    target = tmp_path / "new"
    assert main(["init", str(target)]) == 0
    capsys.readouterr()
    code = main(["-C", str(target), "import", "ifc", str(tmp_path / "other.ifc"), "--by", "t"])
    out = capsys.readouterr().out
    assert code == 0, out
    return d0, report(Project(target).load())[0], out


def roof_top(g: RoofGeo, x: float, y: float) -> float:
    """The top of the roof skin over a point: the rafters are the lowest of the planes there."""
    q = min(g.planes, key=lambda q: q.a * x + q.b * y + q.c)
    return q.a * x + q.b * y + q.c + g.skin_of(q)


@pytest.mark.parametrize(
    "roof",
    [
        "gable ridge=x pitch=45 knee=0.6",
        "gable ridge=y pitch=35 knee=0.4 eave=0.5 verge=0.3",
        "hip pitch=30 knee=0.3 eave=0.6",
        "shed up=n pitch=12 knee=0.2 eave=0.4 verge=0.25",
        "flat knee=2.7",
        "gable ridge=x pitch=40 halfhip=1.2 knee=0.5 eave=0.4",
        "mansard ridge=x pitch=70 upper=30 rise=1.8 knee=0.3 eave=0.3 verge=0.2",
    ],
)
def test_roofs_come_back(tmp_path: Path, capsys: pytest.CaptureFixture[str], roof: str) -> None:
    text = RT.format(top=" top=rf1") + f"roof rf1 OG DA {roof}\n"
    d0, d1, out = trip(tmp_path, capsys, text)
    assert "1 roofs" in out and "issues: 0 errors · 0 warnings" in out
    old, new = d0.model["rf1"], d1.model["rf1"]
    for name in ("shape", "ridge", "up", "pitch", "upper"):
        assert getattr(new, name) == getattr(old, name), name
    # the walls of a UEA export have no layer set usage: their axes, and with them the outline
    # the roof stands on, lie 5 mm out (half of 0.02 - 0.01 of finish). The knee and overhangs are
    # measured from there; the roof itself lies where it lay.
    g0, g1 = d0.arch.roofs["rf1"], d1.arch.roofs["rf1"]
    for x in (0.5, 2.0, 4.0, 6.0, 7.5):
        for y in (0.5, 1.5, 3.0, 4.5, 5.5):
            assert roof_top(g1, x, y) == pytest.approx(roof_top(g0, x, y), abs=0.005), (x, y)
    assert g1.foot.symmetric_difference(g0.foot).area < 0.15  # a 5 mm frame around 28 m
    assert all("top=rf1" in d1.model[w].line() for w in ("w5", "w6", "w7", "w8"))


@pytest.mark.parametrize(
    "stair",
    [
        "x=1+ y=1+ up=e w=1 n=16 tread=0.26",
        "x=6- y=1+ up=w w=1.1 n=17 tread=0.27",
        "x=1+ y=1+ up=n w=1 n=16 tread=0.26 shape=l turn=r",
        "x=1+ y=1+ up=n w=1 n=16 tread=0.26 shape=l turn=l n1=10",
        "x=1+ y=1+ up=s w=1 n=16 tread=0.26 shape=l turn=r winders=3",
        "x=1+ y=1+ up=n w=1 n=16 tread=0.26 shape=u turn=l",
        "x=1+ y=1+ up=e w=1 n=16 tread=0.26 shape=u turn=r gap=0.3",
        "x=1+ y=1+ up=n w=0.9 n=16 tread=0.26 shape=u turn=l gap=0",
        "x=1+ y=1+ up=w w=1 n=17 tread=0.26 shape=u turn=l n1=6 gap=0.2",
    ],
)
def test_stairs_come_back(tmp_path: Path, capsys: pytest.CaptureFixture[str], stair: str) -> None:
    text = RT.format(top="") + f"stair st1 EG OG {stair}\nvoid v1 sl2 over=st1\n"
    d0, d1, out = trip(tmp_path, capsys, text)
    assert "1 stairs · 1 voids" in out
    old, new = d0.model["st1"].line(), d1.model["st1"].line()
    # the same stair; its place may be written from the other side (x=6- is x=1.68+)
    assert new.split(" up=")[1] == old.split(" up=")[1]
    s0, s1 = d0.arch.stairs["st1"], d1.arch.stairs["st1"]
    assert s1.poly.symmetric_difference(s0.poly).area < 1e-6
    assert d1.model["v1"].line() == "void v1 sl2 over=st1"

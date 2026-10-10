"""`uea import ifc`: another program's IFC becomes a model, and a later file updates it.

The fixtures are written by `tests/ifc_make.py` with numbers worked out by hand: a 6 m by 4 m
house on two storeys, outer walls of 0.335 m (0.02 plaster outside, 0.30 core, 0.015 plaster
inside), an inner wall of 0.135 m at x=3.5, a floor slab with 0.15 m of finish on a 0.20 m core.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import json
from pathlib import Path

import pytest

pytest.importorskip("ifcopenshell")

from tests.conftest import Shell
from tests.ifc_make import INNER, OUTER, House, OpeningSpec, WallSpec, house, write
from uea.core.model import Model
from uea.derive import Derived, report
from uea.importer.build import SNAP, frame, room_use, slug
from uea.project import Project


def load(sh: Shell) -> Model:
    return Project(sh.root).load()


def derived(sh: Shell) -> Derived:
    return report(load(sh))[0]


def do_import(sh: Shell, h: House, tmp_path: Path, name: str = "h.ifc", *extra: str) -> str:
    write(h, tmp_path / name)
    code, out = sh("import", "ifc", str(tmp_path / name), "--by", "test", *extra)
    assert code == 0, out
    return out


def lines(sh: Shell, *ids: str) -> list[str]:
    m = load(sh)
    return [m[i].line() for i in ids]


# ---------- the first import ----------


def test_first_import_summary(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, house(), tmp_path)
    assert out.splitlines()[0] == (
        "h.ifc: IFC4 from Test-CAD 1.0: ok (batch 1): 2 levels · 7 types · 9 walls · 2 slabs"
        " · 1 doors · 3 windows · 1 separators · 4 rooms"
    )
    assert "issues: 0 errors · 0 warnings" in out
    assert "not imported: 1 IfcColumn · 1 IfcRoof" in out
    assert "note: ground storey EG (±0.00)" in out
    assert sh("check")[1].startswith("0 errors")


def test_levels_from_storeys_slabs_and_windows(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    # fb = FFL - SSL: the finish above the 0.20 core is 0.15; head = the most common window top
    assert lines(sh, "EG", "OG") == [
        "level EG z=0 fb=0.15 head=2.25",
        "level OG z=2.9 fb=0.15 head=2.25",
    ]


def test_types_from_layers_and_floors_from_slab_finish(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert lines(sh, "AW-33-5", "IW-11-5", "DECKE-35", "FB-DECKE-35") == [
        # the file lists the outer wall outside to inside, UEA inside to outside
        "type AW-33-5 wall layers=innenputz:0.015,*mauerwerk:0.3,aussenputz:0.02",
        "type IW-11-5 wall layers=gipsputz:0.01,*kalksandstein:0.115,gipsputz:0.01",
        "type DECKE-35 slab layers=*stahlbeton:0.2",
        "type FB-DECKE-35 floor layers=fliese:0.02,estrich:0.13",
    ]
    # both storeys' slabs are the same build-up, one written top first and one bottom first
    m = load(sh)
    assert [e.id for e in m.of_kind("type") if e.category == "slab"] == ["DECKE-35"]
    assert [e.id for e in m.of_kind("type") if e.category == "floor"] == ["FB-DECKE-35"]
    assert lines(sh, "sl1", "sl2") == ["slab sl1 EG DECKE-35", "slab sl2 OG DECKE-35"]


def test_walls_are_axes_through_the_core(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    # the body of the south wall is y=-0.17..0.165: UEA's axis runs through the middle of the core
    assert lines(sh, "w1", "w2", "w3", "w4") == [
        "wall w1 EG AW-33-5 a=0,0 b=6,0 lb",
        "wall w2 EG AW-33-5 a=6,0 b=6,4 lb",
        "wall w3 EG AW-33-5 a=6,4 b=0,4 lb",
        "wall w4 EG AW-33-5 a=0,4 b=0,0 lb",
    ]
    # under no slab: the height is given, from the SSL 2.75 to 5.40
    assert load(sh)["w5"].line() == "wall w5 OG AW-33-5 a=0,0 b=6,0 h=2.65 lb"
    d = derived(sh)
    assert d.arch.walls["w1"].ext is not None
    assert d.arch.walls["w9"].ext is None


def test_wall_ends_a_finish_short_of_a_core_are_closed(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    # the inner wall's body stops at the finished faces 0.165 m from the axes of the outer walls;
    # its ends now reach 0.0005 m into their cores, so UEA joins them
    assert load(sh)["w9"].line() == "wall w9 EG IW-11-5 a=3.5,0.1495 b=3.5,3.8505"


def test_openings(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert lines(sh, "d1", "f1", "f2", "f3") == [
        # from the finished wall end (0.165) plus 0.8; a door on the floor has no sill
        "door d1 w9 0.9x2.01 y=0.965+ type=TUER-90",
        # a window with the head of its level has no sill
        "win f1 w1 1.2x1.35 x=1+ type=FENSTER-120",
        # this one ends at 1.9, not at the head 2.25
        "win f2 w3 0.6x0.7 x=4.4+ sill=1.2 type=FENSTER-60",
        "win f3 w5 1.2x1.35 x=2+ type=FENSTER-120",
    ]
    assert lines(sh, "FENSTER-120", "TUER-90") == [
        "type FENSTER-120 win uw=1.1",
        "type TUER-90 door",
    ]
    d = derived(sh)
    assert d.arch.openings["f1"].sill == pytest.approx(0.9)
    assert d.arch.openings["f1"].top == pytest.approx(2.25)


def test_rooms_open_plan_and_areas(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    m = load(sh)
    assert m["r1"].line() == 'room r1 EG living "Wohnzimmer" at=1.7987,2 floor=FB-DECKE-35'
    assert [m[r].use for r in ("r2", "r3", "r4")] == ["kitchen", "dining", "bedroom"]
    # the kitchen and the dining room share an edge with no wall: a separator at y=2
    assert m["rs1"].line().startswith("sep rs1 EG y=2 x=")
    d = derived(sh)
    # finished areas: 3.2675 x 3.67; 2.2675 x 1.835 (twice); 5.67 x 3.67
    fin = {r: d.arch.rooms[r].area_fin for r in ("r1", "r2", "r3", "r4")}
    assert fin["r1"] == pytest.approx(3.2675 * 3.67, abs=1e-3)
    assert fin["r2"] == pytest.approx(2.2675 * 1.835, abs=1e-3)
    assert fin["r3"] == pytest.approx(2.2675 * 1.835, abs=1e-3)
    assert fin["r4"] == pytest.approx(5.67 * 3.67, abs=1e-3)


def test_a_space_without_a_storey_goes_by_its_height(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    # R4 hangs in the air at z=2.9, so it belongs to OG
    assert load(sh)["r4"].level.id == "OG"


# ---------- layers and sides ----------


def test_first_layer_inside_needs_no_reversal(sh: Shell, tmp_path: Path) -> None:
    h = house()
    inside_out = tuple(reversed(OUTER))
    for w in h.walls:
        if w.layers == OUTER:
            w.layers = inside_out
            w.first = (-w.first[0], -w.first[1]) if w.first else None
    do_import(sh, h, tmp_path)
    assert lines(sh, "AW-33-5", "w1") == [
        "type AW-33-5 wall layers=innenputz:0.015,*mauerwerk:0.3,aussenputz:0.02",
        "wall w1 EG AW-33-5 a=0,0 b=6,0 lb",
    ]


def test_a_wall_drawn_the_other_way_round_is_flipped(sh: Shell, tmp_path: Path) -> None:
    h = house()
    h.wall("EG-west").first = (1.0, 0.0)
    do_import(sh, h, tmp_path)
    # its first layer is inside while the other three have it outside; the axis still runs
    # through the middle of the core
    assert lines(sh, "w4", "w1") == [
        "wall w4 EG AW-33-5 a=0,4 b=0,0 lb flip",
        "wall w1 EG AW-33-5 a=0,0 b=6,0 lb",
    ]
    assert sh("check")[1].startswith("0 errors")


def test_a_layer_set_without_usage_centres_the_body(sh: Shell, tmp_path: Path) -> None:
    h = house()
    for w in h.walls:
        w.first = None
    do_import(sh, h, tmp_path)
    m = load(sh)
    # the side is unknown, so the axis is the middle of the body, 2.5 mm off the core;
    # the first layer is taken to be the outside, as the exterior walls are drawn
    assert m["w1"].line().startswith("wall w1 EG AW-33-5 a=0,0")
    assert "layers=innenputz:0.015,*mauerwerk:0.3,aussenputz:0.02" in m["AW-33-5"].line()
    assert sh("check")[1].startswith("0 errors")


def test_layers_that_do_not_add_up_take_the_body(sh: Shell, tmp_path: Path) -> None:
    h = house()
    for w in h.walls:
        if w.name == "EG-inner":
            w.layers = (("Kalksandstein", 0.100),)
            w.first = None
            w.body = 0.135
    out = do_import(sh, h, tmp_path)
    assert "its layers add up to 0.1 m, its footprint is 0.135 m; the footprint counts" in out
    m = load(sh)
    assert m["w9"].type.id.startswith("IW")
    assert "layers=*kalksandstein:0.135" in m[m["w9"].type.id].line()


# ---------- positions in any direction ----------


@pytest.mark.parametrize(
    ("a", "b", "o"),
    [
        ((0.0, 0.0), (6.0, 0.0), "h"),
        ((0.0, 0.0), (6.0, 0.005), "h"),  # 0.05° off: an ordinary wall
        ((1.0, 2.0), (1.004, 6.0), "v"),
        ((0.0, 0.0), (6.0, 0.05), "d"),  # 0.48°: skew
        ((0.0, 0.0), (3.0, 3.0), "d"),
    ],
)
def test_walls_close_to_a_grid_direction_snap_to_it(
    a: tuple[float, float], b: tuple[float, float], o: str
) -> None:
    sa, sb, got = frame(a, b)
    assert got == o
    if o == "h":
        assert sa[1] == sb[1] == pytest.approx((a[1] + b[1]) / 2)
    if o == "v":
        assert sa[0] == sb[0] == pytest.approx((a[0] + b[0]) / 2)
    assert pytest.approx(0.0017) == SNAP


def test_a_skew_wall_with_a_window(sh: Shell, tmp_path: Path) -> None:
    h = house()
    # a free-standing diagonal partition (0.6, 0.6) to (2.6, 2.6), a window 1.0 from its start
    h.walls.append(
        WallSpec(
            "EG-skew", (0.6, 0.6), (2.6, 2.6), "EG", INNER, (-1.0, 1.0), -0.15, 2.55, "IW 11.5"
        )
    )
    h.openings.append(OpeningSpec("EG-skew-win", "EG-skew", 1.0, 0.6, 0.9, 1.35))
    do_import(sh, h, tmp_path)
    m = load(sh)
    w = m["w10"]
    assert w.line().startswith("wall w10 EG IW-11-5 a=0.6,0.6 b=2.6,2.6")
    # along the wall from its start: 1.0 m of a 2.83 m long wall
    assert m["f4"].line() == "win f4 w10 0.6x1.35 s=1+"


# ---------- floor heights ----------


def test_storeys_not_at_zero_are_counted_from_the_ground_storey(sh: Shell, tmp_path: Path) -> None:
    out = do_import(sh, house().raised(3.0), tmp_path)
    assert "note: ground storey EG (±0.00), the lowest; its elevation in the file is 3 m" in out
    assert lines(sh, "EG", "OG") == [
        "level EG z=0 fb=0.15 head=2.25",
        "level OG z=2.9 fb=0.15 head=2.25",
    ]
    assert load(sh)["w5"].line() == "wall w5 OG AW-33-5 a=0,0 b=6,0 h=2.65 lb"


def test_a_wall_that_stops_short_of_the_slab_above_is_given_its_height(
    sh: Shell, tmp_path: Path
) -> None:
    h = house()
    h.wall("EG-north").z1 = 1.0
    do_import(sh, h, tmp_path)
    # 1.00 above the FFL is 1.15 above the SSL at -0.15
    assert load(sh)["w3"].line() == "wall w3 EG AW-33-5 a=6,4 b=0,4 h=1.15 lb"


# ---------- what is not mapped, what is refused ----------


def test_json_report(sh: Shell, tmp_path: Path) -> None:
    write(house(), tmp_path / "h.ifc")
    code, out = sh("--json", "import", "ifc", str(tmp_path / "h.ifc"), "--by", "t")
    data = json.loads(out)
    assert code == 0
    assert data["import"]["counts"]["wall"] == 9
    assert data["import"]["not_imported"] == {"IfcColumn": 1, "IfcRoof": 1}
    assert data["result"]["ok"] is True


def test_dry_run_changes_nothing(sh: Shell, tmp_path: Path) -> None:
    write(house(), tmp_path / "h.ifc")
    code, out = sh("import", "ifc", str(tmp_path / "h.ifc"), "--by", "t", "--dry-run")
    assert code == 0 and "dry run, nothing written" in out
    assert "w1" not in load(sh)
    assert "import" not in sh("log")[1]


def test_uea_exports_are_not_read_back(
    prototype: Project, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from uea.cli import main
    from uea.export.ifc import export_ifc

    d, _ = report(prototype.load())
    export_ifc(d, tmp_path / "own.ifc")
    capsys.readouterr()
    code = main(
        ["-C", str(prototype.root), "import", "ifc", str(tmp_path / "own.ifc"), "--by", "t"]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "exported by UEA" in out and "never read back" in out


def test_other_refusals(sh: Shell, tmp_path: Path) -> None:
    code, out = sh("import", "ifc", str(tmp_path / "missing.ifc"), "--by", "t")
    assert code == 1 and "is not a file" in out
    (tmp_path / "x.ifc").write_text("not an ifc file")
    code, out = sh("import", "ifc", str(tmp_path / "x.ifc"), "--by", "t")
    assert code == 1 and "cannot read" in out
    code, out = sh("import", "dwg", str(tmp_path / "x.ifc"), "--by", "t")
    assert code == 1 and "cannot import 'dwg'" in out
    code, out = sh("import", "ifc", str(tmp_path / "x.ifc"))
    assert code == 2


def test_an_ifc_without_walls_imports_nothing(sh: Shell, tmp_path: Path) -> None:
    h = house().without(*[w.name for w in house().walls])
    out = do_import(sh, h, tmp_path)
    assert "nothing to change" in out
    assert "no walls with a storey" in out


# ---------- naming ----------


def test_slugs_and_room_uses() -> None:
    assert slug("AW 33.5") == "AW-33-5"
    assert slug("Außenwand Müller & Söhne") == "Aussenwand-Mueller-S"
    assert room_use("Küche K1") == "kitchen"
    assert room_use("WC") == "wc"
    assert room_use("Abstellraum") == "storage"
    assert room_use("Zimmer 4") == "other"


# ---------- importing again ----------


def test_the_same_file_again_changes_nothing(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    before = sh("log")[1]
    out = do_import(sh, house(), tmp_path, "again.ifc")
    assert "nothing to change" in out
    assert sh("log")[1] == before


def test_a_moved_wall_is_updated_in_place(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    h = house()
    h.wall("EG-inner").p0 = (3.6, 0.165)
    h.wall("EG-inner").p1 = (3.6, 3.835)
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert "ok (batch 2): 1 walls" in out
    assert load(sh)["w9"].line() == "wall w9 EG IW-11-5 a=3.6,0.1495 b=3.6,3.8505"
    assert len(load(sh).of_kind("wall")) == 9


def test_a_new_window_gets_a_new_id(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    h = house()
    h.openings.append(
        OpeningSpec("EG-win-3", "EG-east", 1.0, 1.0, 0.9, 1.35, "win", "Fenster 120", 1.1)
    )
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert "ok (batch 2): 1 windows" in out
    assert load(sh)["f4"].line() == "win f4 w2 1x1.35 y=1+ type=FENSTER-120"


def test_what_the_file_lost_is_removed(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    out = do_import(sh, house().without("EG-win-2"), tmp_path, "h2.ifc")
    assert "1 removed" in out
    assert "f2" not in load(sh)
    # a removed wall takes its door; the rooms it divided become one region: reported, not blocked
    out = do_import(sh, house().without("EG-win-2", "EG-inner"), tmp_path, "h3.ifc")
    assert "2 removed" in out
    m = load(sh)
    assert "w9" not in m and "d1" not in m
    assert "E-ARCH-021" in out


def test_edits_made_in_uea_are_kept_and_reported(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert sh("apply", "--by", "t", "-m", "lower", stdin="~ w5 h=2.4")[0] == 0
    h = house()
    h.wall("OG-south").p0 = (0.0, 0.1)
    h.wall("OG-south").p1 = (6.0, 0.1)
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert "kept: w5 (OG-south): edited in UEA since the import" in out
    assert load(sh)["w5"].line() == "wall w5 OG AW-33-5 a=0,0 b=6,0 h=2.4 lb"


def test_edits_in_the_files_by_hand_count_too(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    arch = sh.root / "arch.uea"
    arch.write_text(arch.read_text().replace("b=6,4 lb", "b=6,4 lb temp", 1))
    h = house()
    h.wall("EG-east").p1 = (6.0, 4.0)
    h.wall("EG-east").lb = False
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert "external edit recorded" in out
    assert "kept: w2 (EG-east): edited in UEA since the import" in out


def test_an_element_deleted_in_uea_stays_deleted(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert sh("apply", "--by", "t", "-m", "no window", stdin="- f2")[0] == 0
    out = do_import(sh, house(), tmp_path, "h2.ifc")
    assert "kept: f2 (win in EG-north): removed in UEA since the import" in out
    assert "f2" not in load(sh)


def test_a_wall_the_file_lost_stays_while_something_refers_to_it(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert sh("apply", "--by", "t", "-m", "own door", stdin="+ door _ w9 0.8x2.01 y=3+")[0] == 0
    out = do_import(sh, house().without("EG-inner"), tmp_path, "h2.ifc")
    assert "w9: gone from the IFC, but d" in out and "still refers to it" in out
    assert "w9" in load(sh)


def test_a_reverted_import_is_forgotten_and_ids_are_not_reused(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    assert sh("revert", "1", "--by", "t")[0] == 0
    assert len(load(sh).of_kind("wall")) == 0
    out = do_import(sh, house(), tmp_path, "h2.ifc")
    assert "9 walls" in out
    m = load(sh)
    assert len(m.of_kind("wall")) == 9
    assert "w1" not in m and "w10" in m


def test_reverting_a_later_import_goes_back_to_the_earlier_one(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    h = house()
    h.wall("EG-inner").p0 = (3.6, 0.165)
    h.wall("EG-inner").p1 = (3.6, 3.835)
    do_import(sh, h, tmp_path, "h2.ifc")
    assert sh("revert", "2", "--by", "t")[0] == 0
    assert load(sh)["w9"].line() == "wall w9 EG IW-11-5 a=3.5,0.1495 b=3.5,3.8505"
    out = do_import(sh, h, tmp_path, "h2.ifc")
    assert "1 walls" in out
    assert load(sh)["w9"].line() == "wall w9 EG IW-11-5 a=3.6,0.1495 b=3.6,3.8505"


def test_the_record_holds_only_what_an_import_changed(sh: Shell, tmp_path: Path) -> None:
    do_import(sh, house(), tmp_path)
    h = house()
    h.wall("EG-inner").p0 = (3.6, 0.165)
    h.wall("EG-inner").p1 = (3.6, 3.835)
    do_import(sh, h, tmp_path, "h2.ifc")
    entries = Project(sh.root).history.entries()
    first, second = entries[0].ifc, entries[1].ifc
    assert first is not None and second is not None
    assert len(first["ids"]) == 29
    assert list(second["lines"]) == ["w9"]


def test_haus_mueller_through_another_program(
    prototype: Project, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """UEA's own export, relabelled as another program's, comes back as the same house."""
    import ifcopenshell

    from uea.cli import main
    from uea.export.ifc import export_ifc

    d0, _ = report(prototype.load())
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
    assert (
        "3 levels · 9 types · 17 walls · 3 slabs · 9 doors · 13 windows · 1 separators · 11 rooms"
        in out
    )
    assert "issues: 0 errors" in out
    assert "not imported: 1 IfcRoof · 1 IfcStair" in out
    d1, rep = report(Project(target).load())
    assert not rep.errors()
    # the rooms keep their shapes to a few millimetres (no layer set usage in a UEA export:
    # the axis is the middle of each body)
    for rid, old in d0.arch.rooms.items():
        assert d1.arch.rooms[rid].area_fin == pytest.approx(old.area_fin, rel=0.005), rid

"""The `uea` command line, driven like an agent drives it."""

import io
import json
from pathlib import Path

import pytest

from tests.test_batch import SETUP, WALLS
from uea.cli import main


class Shell:
    def __init__(
        self, root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.root = root
        self.capsys = capsys
        self.monkeypatch = monkeypatch

    def __call__(self, *args: str, stdin: str | None = None) -> tuple[int, str]:
        if stdin is not None:
            self.monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = main(["-C", str(self.root), *args])
        return code, self.capsys.readouterr().out


@pytest.fixture
def sh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Shell:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "p"]) == 0
    capsys.readouterr()
    return Shell(tmp_path / "p", capsys, monkeypatch)


def build(sh: Shell) -> None:
    assert sh("apply", "--by", "t", "-m", "setup", stdin=SETUP)[0] == 0
    assert sh("apply", "--by", "t", "-m", "walls", stdin=WALLS)[0] == 0


def test_init_and_help(sh: Shell) -> None:
    code, out = sh("help")
    assert code == 0 and "uea apply" in out
    for topic in ("start", "ops", "positions", "arch", "wall", "type", "codes", "calc"):
        code, out = sh("help", topic)
        assert code == 0 and out.strip(), topic
    assert sh("help", "nonsense")[0] == 1
    assert "flags: lb flip existing demolish temp" in sh("help", "wall")[1]


def test_help_answers_what_agents_had_to_guess(sh: Shell) -> None:
    """The first agent run (bench/agent) guessed these; the help must say them."""
    start = sh("help", "start")[1]
    assert "+ project " in start and "layers=plaster:0.015,*brick:0.365" in start
    # project is a pack and a kind; the kind's fields win
    code, out = sh("help", "project")
    assert code == 0 and "postcode=" in out and "ground=" in out and "level grid" in out
    assert "layers=" in sh("help", "type")[1]
    for topic in ("export", "render"):
        code, out = sh("help", topic)
        assert code == 0 and "uea export ifc" in out
    assert "x=w6-0.135" in sh("help", "positions")[1]


def test_format_is_english(sh: Shell) -> None:
    build(sh)
    code, out = sh("apply", "--by", "t", "-m", "x", stdin="+ door _ w1 1x2 x=W+1 din=l\n")
    assert code == 1 and "unknown field 'din'" in out and "hand" in out
    ops = "+ door _ w1 1x2 x=W+1 into=r1 hand=l type=TI\n"
    assert sh("apply", "--by", "t", "-m", "x", stdin=ops)[0] == 0
    out = sh("show", "EG")[1] + sh("get", "r1", "d1")[1]
    assert "hand=l type=TI" in out
    for word in ("Fertig", "Rohbau", "Traufe", "First", "OKFF", "rd="):
        assert word not in out


def test_default_type_counts_implicit_users(sh: Shell) -> None:
    build(sh)
    sh("apply", "--by", "t", "-m", "x", stdin="+ win _ w1 1x1 x=W+1\n+ win _ w2 1x1 y=S+1\n")
    assert sh("get", "FE")[1].splitlines()[1] == " used by f1 f2"
    assert sh("get", "TI")[1].splitlines()[1] == " unused"


def test_apply_output(sh: Shell) -> None:
    code, out = sh("apply", "--by", "t", "-m", "setup", stdin=SETUP)
    assert code == 0 and out.startswith("ok batch 1 (project, arch): +")
    code, out = sh("apply", "--by", "t", "-m", "walls", stdin=WALLS)
    assert out.splitlines()[:3] == [
        "ok batch 2 (arch): +5",
        " @s=w1 @o=w2 @n=w3 @w=w4 r1",
        "r1 69.22 m² fin",
    ]


def test_apply_needs_who_and_why(sh: Shell, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UEA_BY", raising=False)
    assert sh("apply", "-m", "x", stdin="~ x")[0] == 2
    assert sh("apply", "--by", "t", stdin="~ x")[0] == 2


def test_rejected_batch(sh: Shell) -> None:
    build(sh)
    code, out = sh("apply", "--by", "t", "-m", "x", stdin="+ win _ w1 1x1 x=E+1")
    assert code == 1
    assert out.splitlines()[0] == "rejected: 1 new error in arch. Nothing changed."
    assert out.splitlines()[1].startswith("E-ARCH-001 f1 x 11..12 lies outside w1")


def test_follows(sh: Shell) -> None:
    build(sh)
    sh(
        "apply",
        "--by",
        "t",
        "-m",
        "x",
        stdin="+ wall _ EG IW x=w4+3 y=w1..w3\n+ win _ w1 1x1 x=w5+0.5",
    )
    code, out = sh("apply", "--by", "t", "-m", "move", stdin="~ w5 x=w4+3.5")
    assert code == 0
    assert "follows: f1 r1 (arch)" in out


def test_read_commands(sh: Shell) -> None:
    build(sh)
    code, out = sh("show")
    assert code == 0 and "EG z=0" in out and "r1 living 69.22" in out
    code, out = sh("show", "EG")
    assert out.startswith("EG z=0 fb=0.15 ssl=-0.15 head=2.26 h=2.75")
    code, out = sh("get", "r1", "w1")
    assert "shell 9.4x7.4=69.56 | fin 9.38x7.38=69.22" in out
    assert "wall w1 EG AW y=S+ x=W..E lb" in out
    assert sh("get", "w99")[0] == 1
    code, out = sh("find", "wall", "ext", "lb")
    assert len(out.splitlines()) == 4
    code, out = sh("find", "wall", "--ids")
    assert out.strip() == "w1-w4"
    code, out = sh("check")
    assert code == 0 and out.startswith("0 errors")
    code, out = sh("log")
    assert out.splitlines()[0].startswith("2 t  walls  +w1-w4 r1")


def test_json(sh: Shell) -> None:
    build(sh)
    data = json.loads(sh("--json", "get", "r1")[1])
    assert data["elements"][0]["fields"]["use"] == "living"
    data = json.loads(sh("--json", "check")[1])
    assert data["errors"] == []
    data = json.loads(
        sh("--json", "apply", "--by", "t", "-m", "x", stdin="+ win _ w1 1x1 x=W+1")[1]
    )
    assert data["ok"] and data["added"] == [{"placeholder": None, "id": "f1"}]


def test_revert_command(sh: Shell) -> None:
    build(sh)
    sh("apply", "--by", "t", "-m", "x", stdin="+ win _ w1 1x1 x=W+1")
    code, out = sh("revert", "3", "--by", "t")
    assert code == 0 and out.startswith("ok batch 4 (arch): reverted 3 · -1 (f1)")


def test_calc(sh: Shell) -> None:
    build(sh)
    sh("apply", "--by", "t", "-m", "x", stdin="+ slab _ OG DE")
    code, out = sh("calc")
    assert "wofl  norm" in out
    code, out = sh("calc", "wofl")
    assert code == 0
    assert out.splitlines()[0].startswith("norm wofl 0.1.0 · Wohnfläche per WoFlV · all")
    assert "Wohnfläche 69.22 m²" in out
    assert (sh.root / "out" / "wofl.md").exists()
    report = json.loads((sh.root / "out" / "wofl.json").read_text())
    assert report["kind"] == "norm" and report["state"]["batch"] == 3


def test_custom_calc_is_never_norm(sh: Shell) -> None:
    build(sh)
    (sh.root / "calc").mkdir()
    (sh.root / "calc" / "mine.py").write_text(
        "from uea.calc import Calculator, Output\n"
        "def run(d, scope):\n"
        "    return Output(lines=[f'{len(d.arch.rooms)} rooms'], report='# x')\n"
        "CALCULATOR = Calculator('mine', 'Rooms', 'norm', '0.1', run)\n"
    )
    code, out = sh("calc", "mine")
    assert code == 0
    assert out.splitlines()[0] == "custom mine 0.1 · Rooms · all · not norm-compliant"


def test_render_and_export(sh: Shell) -> None:
    build(sh)
    code, out = sh("render", "EG")
    assert code == 0 and (sh.root / "out" / "plan-EG.png").exists()
    code, out = sh("export", "svg", "EG")
    assert (sh.root / "out" / "plan-EG.svg").read_text().startswith("<svg")
    pytest.importorskip("ifcopenshell")
    code, out = sh("export", "ifc")
    assert code == 0 and "4 IfcWall" in out
    assert (sh.root / "out" / "p.ifc").exists() or any((sh.root / "out").glob("*.ifc"))


def test_export_xlsx(sh: Shell) -> None:
    build(sh)
    code, out = sh("export", "xlsx")
    # four walls and a room; no openings, slabs, roofs or stairs; quantities: the walls, the room
    assert code == 0
    assert out.strip() == "p/out/box.xlsx Räume(1) Wände(4) Mengen(2)"
    code, out = sh("export", "xlsx", "EG")
    assert code == 0 and out.startswith("p/out/box-EG.xlsx ")
    assert sorted(f.name for f in (sh.root / "out").glob("*.xlsx")) == ["box-EG.xlsx", "box.xlsx"]
    code, out = sh("export", "xlsx", "XX")
    assert code == 1 and "unknown level" in out
    code, out = sh("export", "docx")
    assert code == 1 and "xlsx" in out and "pdf" in out


def test_export_sheets(sh: Shell) -> None:
    build(sh)
    out_dir = sh.root / "out"
    code, out = sh("export", "pdf", "EG")
    assert code == 0 and out.strip() == "p/out/plan-EG.pdf A3 1:100"
    assert (out_dir / "plan-EG.pdf").read_bytes().startswith(b"%PDF")
    code, out = sh("export", "dxf")
    # the OG of the test project has no walls; then the four elevations
    assert code == 0 and out.splitlines() == [
        "p/out/plan-EG.dxf A3 1:100",
        "OG: no walls, nothing to draw",
        *(f"p/out/elevation-{side}.dxf A3 1:100" for side in ("north", "east", "south", "west")),
    ]
    assert (out_dir / "plan-EG.dxf").read_text().startswith("  0\nSECTION")
    code, out = sh("export", "svg", "EG")
    assert (out_dir / "plan-EG.svg").read_text().startswith("<svg")
    code, out = sh("export", "png", "EG")
    assert code == 0 and (out_dir / "plan-EG.png").exists()
    # render stays the working plan for the agent, with the ids of the elements
    code, out = sh("render", "EG")
    assert code == 0 and out.startswith("p/out/plan-EG.png ")
    assert sh("export", "pdf", "XX")[0] == 1


def test_export_sections(sh: Shell) -> None:
    build(sh)
    out_dir = sh.root / "out"
    code, out = sh("apply", "--by", "t", "-m", "cut", stdin="+ section A x=W+2.5 look=w\n")
    assert code == 0
    code, out = sh("show", "A")
    assert code == 0 and "cut x 2.5 looking w" in out
    # a section by its name; with no scope every plan and every section
    code, out = sh("export", "pdf", "A")
    assert code == 0 and out.strip() == "p/out/section-A.pdf A3 1:100"
    assert (out_dir / "section-A.pdf").read_bytes().startswith(b"%PDF")
    code, out = sh("export", "dxf")
    assert code == 0 and out.splitlines()[:3] == [
        "p/out/plan-EG.dxf A3 1:100",
        "OG: no walls, nothing to draw",
        "p/out/section-A.dxf A3 1:100",
    ]
    code, out = sh("export", "png", "A")
    assert code == 0 and (out_dir / "section-A.png").exists()
    code, out = sh("export", "pdf", "B")
    assert code == 1 and out.strip() == (
        "unknown level, section or side 'B'. Levels: EG OG. Sections: A."
        " Sides: north east south west"
    )
    # a cut that meets no wall is a warning, and there is nothing to draw
    assert sh("apply", "--by", "t", "-m", "cut", stdin="+ section B x=50\n")[0] == 0
    code, out = sh("export", "pdf", "B")
    assert code == 0 and out.strip() == "B: the cut meets no wall, nothing to draw"


ELEC = """\
+ board @b w4 y=w1+1 z=1.4 main=SLS-E35
+ rcd @fi @b 40/0.03 A
+ circ @c1 @fi NYM-J3x1.5 B10 "Licht"
+ circ @c2 @fi NYM-J3x2.5 B16
+ type DL lum "LED" w=11 flux=1000 default
+ lum @l r1
+ switch @sw w4 @c1 y=w1+2 ctl=@l
+ sock _ w4 @c2 y=w1+3 n=2
"""


def test_electrical_batch(sh: Shell) -> None:
    build(sh)
    code, out = sh("apply", "--by", "elec-agent", "-m", "Elektro", stdin=ELEC)
    assert code == 0 and out.splitlines()[0] == "ok batch 3 (light, elec): +8"
    assert "@sw=sw1" in out and "@l=l1" in out
    assert (sh.root / "elec.uea").exists() and (sh.root / "light.uea").exists()
    code, out = sh("get", "sw1", "l1")
    assert code == 0
    assert "switch sw1 w4 c1 y=w1+2 ctl=l1" in out
    assert "w4.e y 2.3 z 1.05 | r1 EG | c1 fi1 b1 | 1 channel" in out
    assert "switched by sw1 (c1): single" in out
    code, out = sh("find", "sock", "room=r1")
    assert code == 0 and out.strip() == "sock s1 w4 c2 y=w1+3 n=2"
    code, out = sh("show", "EG")
    assert "light 1 lum · elec 1 board 1 sock (2 outlets) 1 switch" in out
    code, out = sh("show", "elec")
    assert out.startswith("elec: 1 board · 1 rcd · 2 circ · 1 sock · 1 switch")
    # a wall moved by its grid takes the devices with it, and the batch says so
    code, out = sh("apply", "--by", "arch-agent", "-m", "Achse", stdin="> grid W x=0.5\n")
    assert code == 0 and "follows:" in out
    follows = next(x for x in out.splitlines() if x.startswith("follows:"))
    assert "s1" in follows and "sw1" in follows and "l1 (light)" in follows
    # the xlsx has the electrical sheets
    code, out = sh("export", "xlsx")
    assert "Stromkreise(2)" in out and "Leuchten(1)" in out
    # a wrong reference is rejected with the discipline graph's words
    code, out = sh("apply", "--by", "elec-agent", "-m", "x", stdin="+ sock _ w4 w1 y=w1+5\n")
    assert code == 1


def test_outside_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(tmp_path), "show"]) == 2
    assert "no project.uea" in capsys.readouterr().out


def test_broken_files_stop_everything(sh: Shell) -> None:
    build(sh)
    p = sh.root / "arch.uea"
    p.write_text(p.read_text() + "wall w9 EG AW y=S+ x=W..E heavy\n")
    code, out = sh("show")
    assert code == 2
    assert "arch.uea:" in out and "unknown flag 'heavy'" in out

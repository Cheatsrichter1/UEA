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
    code, out = sh("export", "dxf")
    assert code == 1 and "xlsx" in out


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

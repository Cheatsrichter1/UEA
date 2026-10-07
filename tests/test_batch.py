"""Operations, atomic batches, history, revert and edits made outside UEA."""

import json

import pytest

from tests.conftest import BOX
from uea.batch import replay, revert, run
from uea.project import LoadError, Project

SETUP = "\n".join("+ " + line for line in BOX.splitlines() if not line.startswith("wall"))
WALLS = """\
+ wall @s EG AW y=S+ x=W..E lb
+ wall @o EG AW x=E- y=@s..@n lb
+ wall @n EG AW y=N- x=W..E lb
+ wall @w EG AW x=W+ y=@s..@n lb
+ room _ EG living at=@w+1,@s+1
"""


def setup(p: Project) -> None:
    assert run(p, SETUP, "t", "setup").ok
    assert run(p, WALLS, "t", "walls").ok


def test_ids_and_placeholders(empty: Project) -> None:
    assert run(empty, SETUP, "t", "setup").batch == 1
    res = run(empty, WALLS, "t", "walls")
    assert res.ok and res.batch == 2 and res.applied is not None
    # placeholders may be used before they are defined (@n in the second line)
    assert res.applied.added == [
        ("@s", "w1"),
        ("@o", "w2"),
        ("@n", "w3"),
        ("@w", "w4"),
        (None, "r1"),
    ]
    text = (empty.root / "arch.uea").read_text()
    assert "wall w2 EG AW x=E- y=w1..w3 lb" in text


def test_ids_are_never_reused(empty: Project) -> None:
    setup(empty)
    assert run(empty, "- r1", "t", "remove").ok
    res = run(empty, "+ room _ EG living at=W+1,S+1", "t", "again")
    assert res.applied is not None and res.applied.added == [(None, "r2")]


def test_explicit_ids_are_rejected(empty: Project) -> None:
    setup(empty)
    res = run(empty, "+ wall w9 EG AW y=S+1 x=W..E", "t", "x")
    assert not res.ok and "UEA assigns ids" in res.errors[0]


def test_unknown_placeholder(empty: Project) -> None:
    setup(empty)
    res = run(empty, "+ win _ @x 1x1 x=W+1", "t", "x")
    assert not res.ok and "placeholder @x" in res.errors[0]


def test_set_fields(empty: Project) -> None:
    setup(empty)
    assert run(empty, "+ win _ w1 1.26x1.26 x=W+1.51", "t", "win").ok
    res = run(empty, "~ f1 1.51x1.26 sill=0.8", "t", "wider")
    assert res.ok and res.applied is not None
    assert res.applied.ops == ["~ f1 size=1.51x1.26 sill=0.8"]
    assert "win f1 w1 1.51x1.26 x=W+1.51 sill=0.8" in (empty.root / "arch.uea").read_text()
    res = run(empty, "~ f1 sill=", "t", "back to head")
    assert res.ok and "win f1 w1 1.51x1.26 x=W+1.51\n" in (empty.root / "arch.uea").read_text()


def test_set_errors(empty: Project) -> None:
    setup(empty)
    assert "no field 'colour'" in run(empty, "~ w1 colour=red", "t", "x").errors[0]
    assert "required" in run(empty, "~ w1 type=", "t", "x").errors[0]
    assert "w99 does not exist" in run(empty, "~ w99 lb", "t", "x").errors[0]
    assert "what is" in run(empty, "~ w1 heavy", "t", "x").errors[0]


def test_replace_keeps_kind(empty: Project) -> None:
    setup(empty)
    assert run(empty, "> grid E x=11", "t", "move grid").ok
    res = run(empty, "> level E z=1", "t", "x")
    assert not res.ok and "keeps the kind" in res.errors[0]


def test_named_kinds_cannot_be_added_twice(empty: Project) -> None:
    setup(empty)
    res = run(empty, "+ level EG z=1", "t", "x")
    assert not res.ok and "change it with ~ EG" in res.errors[0]


def test_batch_with_new_error_is_rejected(empty: Project) -> None:
    setup(empty)
    before = (empty.root / "arch.uea").read_text()
    res = run(empty, "+ win _ w1 1x1 x=E+1", "t", "outside")
    assert not res.ok
    assert [i.code for i in res.rejected] == ["E-ARCH-001"]
    assert (empty.root / "arch.uea").read_text() == before
    assert empty.history.last() == 2


def test_existing_errors_do_not_block(empty: Project) -> None:
    setup(empty)
    # break the model from outside, then repair it step by step
    p = empty.root / "arch.uea"
    p.write_text(p.read_text() + "win f1 w1 1x1 x=E+1\nwin f2 w1 1x1 x=E+3\n")
    res = run(empty, "~ f1 x=W+1", "t", "fix one")
    assert res.ok
    assert [i.code + " " + i.el for i in res.fixed] == ["E-ARCH-001 f1"]


def test_dry_run_writes_nothing(empty: Project) -> None:
    setup(empty)
    res = run(empty, "+ win _ w1 1x1 x=W+1", "t", "x", dry=True)
    assert res.ok and res.dry and res.batch is None
    assert "win f1" not in (empty.root / "arch.uea").read_text()
    assert empty.history.last() == 2


def test_request_lifecycle(empty: Project) -> None:
    setup(empty)
    res = run(empty, '+ req _ elec w1 "Schlitz 10x5"', "elec", "ask")
    assert res.ok and res.opened == ["q1"]
    res = run(empty, "~ q1 done", "arch", "done")
    assert res.ok and res.applied is not None and res.applied.closed == ["q1"]
    assert 'req q1 elec w1 "Schlitz 10x5" done=4' in (empty.root / "issues.uea").read_text()


def test_history_entry(empty: Project) -> None:
    setup(empty)
    run(empty, "~ w1 lb=", "arch-agent", "w1 nicht tragend")
    entry = json.loads((empty.root / "log.jsonl").read_text().splitlines()[-1])
    assert entry["batch"] == 3
    assert entry["by"] == "arch-agent"
    assert entry["msg"] == "w1 nicht tragend"
    assert entry["ops"] == ["~ w1 lb="]
    assert entry["inverse"] == ["> wall w1 EG AW y=S+ x=W..E lb"]
    assert list(entry["files"]) == ["arch.uea"]
    assert entry["files"]["arch.uea"].startswith("sha256:")


def test_revert(empty: Project) -> None:
    setup(empty)
    original = (empty.root / "arch.uea").read_text()
    assert run(empty, "+ win _ w1 1x1 x=W+1\n~ w1 lb=", "t", "change").ok
    res = revert(empty, 3, "t")
    assert res.ok and res.revert == 3 and res.batch == 4
    assert (empty.root / "arch.uea").read_text() == original
    assert empty.history.get(4) is not None and empty.history.get(4).revert == 3  # type: ignore[union-attr]


def test_revert_restores_removed_ids(empty: Project) -> None:
    setup(empty)
    original = (empty.root / "arch.uea").read_text()
    assert run(empty, "- r1", "t", "remove").ok
    assert revert(empty, 3, "t").ok
    assert (empty.root / "arch.uea").read_text() == original


def test_revert_conflict(empty: Project) -> None:
    setup(empty)
    assert run(empty, "~ w1 lb=", "t", "a").ok
    assert run(empty, "~ w1 lb", "t", "b").ok
    res = revert(empty, 3, "t")
    assert not res.ok and "batch 4 changed w1" in res.errors[0]


def test_external_edit_is_recorded(empty: Project) -> None:
    setup(empty)
    p = empty.root / "arch.uea"
    p.write_text(p.read_text().replace("wall w1 EG AW y=S+ x=W..E lb", "wall w1 EG AW y=S+ x=W..E"))
    res = run(empty, "+ win _ w1 1x1 x=W+1", "t", "next")
    assert res.ok and res.external is not None and "batch 3" in res.external
    ext = empty.history.get(3)
    assert ext is not None and ext.external
    assert ext.ops == ["> wall w1 EG AW y=S+ x=W..E"]
    assert res.batch == 4
    assert replay(empty).get("w1") is not None


def test_invalid_external_edit_stops(empty: Project) -> None:
    setup(empty)
    p = empty.root / "arch.uea"
    p.write_text(p.read_text() + "wall w9 EG AW y=S+ x=W..E heavy\n")
    with pytest.raises(LoadError, match=r"arch\.uea:"):
        run(empty, "~ w1 lb=", "t", "x")


def test_replay_matches_files(empty: Project) -> None:
    setup(empty)
    run(empty, "+ win _ w1 1x1 x=W+1\n~ w1 lb=", "t", "x")
    run(empty, "- f1", "t", "y")
    m = replay(empty)
    assert m.pack_text("arch") == (empty.root / "arch.uea").read_text()


def test_add_then_remove_in_one_batch(empty: Project) -> None:
    setup(empty)
    res = run(empty, "+ win @a w1 1x1 x=W+1\n- @a", "t", "x")
    assert res.ok and res.applied is not None and res.applied.added == []


def test_comment_and_blank_lines_in_ops(empty: Project) -> None:
    setup(empty)
    assert run(empty, "# a window\n\n+ win _ w1 1x1 x=W+1  # south\n", "t", "x").ok


def test_empty_batch(empty: Project) -> None:
    res = run(empty, "# nothing\n", "t", "x")
    assert not res.ok and "no operations" in res.errors[0]

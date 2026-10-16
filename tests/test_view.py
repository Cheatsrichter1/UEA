"""Partial views: selectors, context, and writes limited to a slice at a base (decision 0046).

The project is the generated block of 2 storeys with 2 flats each (bench/large.py): on OG1 the
manifolds hv3 and hv4 with the loops uh5 to uh8, room r5 with the sockets s13 to s15.
"""

from pathlib import Path

import pytest

from bench.large import write
from tests.conftest import Shell
from uea.batch import run, sync
from uea.derive import Derived, report
from uea.project import Project
from uea.view import ViewError, context, select, view


@pytest.fixture
def block(tmp_path: Path) -> Project:
    write(tmp_path / "block", storeys=2, units=2)
    p = Project(tmp_path / "block")
    with p.lock():
        sync(p)
    assert p.history.last() == 1
    return p


def derived(p: Project) -> Derived:
    return report(p.load())[0]


def test_discipline_on_a_level(block: Project) -> None:
    assert select(derived(block), "heat:OG1") == {"hv3", "hv4", "uh5", "uh6", "uh7", "uh8"}


def test_discipline_in_a_room(block: Project) -> None:
    # the board b3 hangs on the north face of the middle wall, so it is in the bedroom r6
    assert select(derived(block), "elec:r5") == {"s13", "s14", "s15"}


def test_element_with_what_hangs_on_it(block: Project) -> None:
    ids = {"b2", "fi2", "c3", "c4", "s7", "s8", "s9", "s10", "s11", "s12"}
    assert select(derived(block), "b2") == ids


def test_terms_add_up(block: Project) -> None:
    d = derived(block)
    assert select(d, "heat:OG1,elec:r5") == select(d, "heat:OG1") | select(d, "elec:r5")


@pytest.mark.parametrize(
    ("selector", "message"),
    [
        ("uv9", "unknown selector 'uv9'"),
        ("heat:DG", "'DG' in heat:DG is not a level or a room"),
        ("gas:EG", "unknown discipline 'gas'"),
        ("heat,", "empty term"),
    ],
)
def test_bad_selectors(block: Project, selector: str, message: str) -> None:
    with pytest.raises(ViewError, match=message):
        select(derived(block), selector)


def test_context_resolves_every_reference(block: Project) -> None:
    m = block.load()
    ctx = context(m, {"hv3"})
    # the niche and its wall, the wall below it and what that one spans between, the tank,
    # its room, its generator, the levels and the types
    assert {"ni3", "w13", "w6", "w4", "w5", "t1", "r1", "g1", "OG1", "EG", "IW", "SP"} <= ctx
    assert not ctx & {"hv3", "hv4", "uh5", "s1"}


def test_view_lines(block: Project) -> None:
    v = view(derived(block), "heat:OG1", 1)
    assert v.base == 1
    assert v.elements == [
        "man hv3 ni3 t1",
        "man hv4 ni4 t1",
        "ufh uh5 r5 hv3",
        "ufh uh6 r6 hv3",
        "ufh uh7 r7 hv4",
        "ufh uh8 r8 hv4",
    ]
    assert "level OG1 z=2.9 fb=0.15 head=2.26" in v.context


def test_write_inside_the_view(block: Project) -> None:
    res = run(block, "~ hv3 type=HKV\n- uh6\n+ ufh _ r6 hv3", "heat", "x", view="heat:OG1", base=1)
    assert res.ok and res.batch == 2


def test_change_outside_the_view(block: Project) -> None:
    res = run(block, "~ hv1 type=HKV", "heat", "x", view="heat:OG1", base=1)
    assert not res.ok
    assert res.errors == [
        "hv1 is outside heat:OG1. Write them with a view that holds them, or without --view"
    ]


def test_add_outside_the_view(block: Project) -> None:
    res = run(block, "+ ufh _ r2 hv3", "heat", "x", view="heat:OG1", base=1)
    assert not res.ok and res.errors[0].startswith("uh9 is outside heat:OG1")


def test_bad_selector_on_write(block: Project) -> None:
    res = run(block, "~ hv3 type=HKV", "heat", "x", view="heat:DG")
    assert not res.ok and "is not a level or a room" in res.errors[0]


def test_base_conflict(block: Project) -> None:
    assert run(block, "~ hv3 type=HKV", "heat-a", "a").batch == 2
    res = run(block, "- uh5\n~ hv3 type=", "heat-b", "b", view="heat:OG1", base=1)
    assert not res.ok
    assert res.errors == [
        "batch 2 changed hv3 after base 1. Read them again (uea view heat:OG1) and write the"
        " batch on the new base"
    ]
    # the other flat's manifold was not touched since the base
    assert run(block, "~ hv4 type=HKV", "heat-b", "b", view="heat:OG1", base=1).ok


def test_reference_changed_since_base_is_no_conflict(block: Project) -> None:
    assert run(block, "~ ni3 sill=0.4", "arch", "a").ok
    assert run(block, "~ hv3 type=HKV", "heat", "b", view="heat:OG1", base=1).ok


def test_base_without_view(block: Project) -> None:
    assert run(block, "~ hv3 type=HKV", "heat-a", "a").ok
    res = run(block, "~ hv3 type=", "heat-b", "b", base=1)
    assert not res.ok and "(uea get)" in res.errors[0]


def test_base_ahead(block: Project) -> None:
    res = run(block, "~ hv3 type=HKV", "heat", "x", base=7)
    assert res.errors == ["base 7 is ahead of the history: the last batch is 1"]


def test_cli(block: Project, sh: Shell) -> None:
    sh.root = block.root
    code, text = sh("view", "heat:OG1")
    lines = text.splitlines()
    assert code == 0
    assert lines[0].startswith("# heat:OG1 at base 1 · 6 elements · ")
    assert lines[0].endswith(" context first, read-only")
    assert lines[-7:] == [
        "# heat:OG1",
        "man hv3 ni3 t1",
        "man hv4 ni4 t1",
        "ufh uh5 r5 hv3",
        "ufh uh6 r6 hv3",
        "ufh uh7 r7 hv4",
        "ufh uh8 r8 hv4",
    ]
    code, text = sh(
        "apply", "--by", "heat", "-m", "x", "--view", "heat:OG1", "--base", "1",
        stdin="~ hv1 type=HKV",
    )  # fmt: skip
    assert code == 1 and "hv1 is outside heat:OG1" in text
    code, text = sh("view", "uv9")
    assert code == 1 and "unknown selector" in text


def test_cli_pages(block: Project, sh: Shell, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("uea.cli.VIEW_LIMIT", 4)
    sh.root = block.root
    _, text = sh("view", "b2")
    # 10 elements after their context; the header stays on every page
    head, *page, more = text.splitlines()
    assert head.startswith("# b2 at base 1 · 10 elements · ") and len(page) == 4
    _, text = sh("view", "b2", "--skip", more.split()[-1])
    assert text.splitlines()[0] == head
    *_, last = sh("view", "b2", "--skip", "1000")[1].splitlines()
    assert last == head

"""The agent test's harness: the logging `uea` and the comparison with the reference."""

import subprocess
from pathlib import Path

from bench.agent import REFERENCE, calcs, calls, compare, find_project, setup
from bench.tasks import BATCH1, BATCH_DB, BATCH_EG, BATCH_OG
from uea.derive import report


def agent(run: Path, batches: list[str]) -> None:
    """Drive the logging `uea` the way an agent's shell does."""
    uea = str(run / "bin" / "uea")
    subprocess.run([uea, "init", str(run / "haus")], check=True, capture_output=True)
    for ops in batches:
        subprocess.run(
            [uea, "-C", str(run / "haus"), "apply", "--by", "a", "-m", "b"],
            input=ops,
            text=True,
            check=True,
            capture_output=True,
        )


def test_reference_solution_matches_everything(tmp_path: Path) -> None:
    run = tmp_path / "run"
    prompt = setup(run)
    assert str(run / "bin" / "uea") in prompt and "haus-mueller.md" in prompt
    agent(run, [BATCH1, BATCH_EG, BATCH_OG, BATCH_DB])
    c = compare(find_project(run))
    assert c.errors == [] and c.matching == c.expected == 58
    assert c.wohnflaeche is not None and round(c.wohnflaeche, 2) == 134.89
    log = calls(run)
    assert [x["code"] for x in log] == [0] * 5
    assert log[1]["ops"] == BATCH1


def test_a_wrong_wall_shows_up(tmp_path: Path) -> None:
    run = tmp_path / "run"
    setup(run)
    # the HWR 0.25 wider than the brief says: w6, the WC wall and the rooms around it move
    agent(run, [BATCH1, BATCH_EG.replace("x=@w+2.26", "x=@w+2.51"), BATCH_OG, BATCH_DB])
    c = compare(find_project(run))
    # w6 at 0.365 + 2.26 = 2.625, the WC wall 1.385 further at 2.74 + 1.385 = 4.125
    assert c.missing["walls"] == [
        "z0.0 v 2.625..2.74 along 5.115..8.125 t=0.145 lb=False",
        "z0.0 v 4.125..4.24 along 5.115..8.125 t=0.145 lb=False",
    ]
    assert c.matching < c.expected


def test_services_run(tmp_path: Path) -> None:
    """The services run: the shell without niches and holes, the tables installed; the reference
    solution matches every fact and meets every calculation, a missing hole shows up."""
    run = tmp_path / "run"
    prompt = setup(run, services=True)
    assert "haus-mueller-services.md" in prompt and str(run / "haus") in prompt
    arch = (run / "haus" / "arch.uea").read_text(encoding="utf-8")
    assert "niche " not in arch and "hole " not in arch and "wall w1 EG" in arch
    assert len(list((run / "data" / "tables").glob("*.json"))) == 10
    empty = compare(find_project(run), full=True)
    assert empty.matching == 0 and empty.expected == 116
    for name in ("light", "elec", "heat", "plumb", "vent", "issues", "arch"):
        lines = (REFERENCE / f"{name}.uea").read_text(encoding="utf-8").splitlines()
        text = "\n".join(x for x in lines if not x.startswith("illum")) + "\n"
        (run / "haus" / f"{name}.uea").write_text(text, encoding="utf-8")
    c = compare(find_project(run), full=True)
    assert c.errors == [] and c.matching == c.expected == 116
    d, _ = report(find_project(run).load())
    assert calcs(d, run / "data") == dict.fromkeys(
        ("heatload", "hydronic", "airflow", "ducts"), "ok"
    )
    # the riser's hole left out: the fact of the hole is missing
    arch = (run / "haus" / "arch.uea").read_text(encoding="utf-8")
    (run / "haus" / "arch.uea").write_text(arch.replace("hole ho6", "# hole ho6"), encoding="utf-8")
    c = compare(find_project(run), full=True)
    assert c.missing["holes"] == ["slab for riser"] and "W-PLUMB-006 sr1" in c.warnings

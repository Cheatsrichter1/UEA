"""The agent test: an off-the-shelf agent builds Haus Müller from a written brief.

    uv run python -m bench.agent setup RUN       run folder with a logging `uea`, prints the prompt
    uv run python -m bench.agent compare RUN     the agent's model against the reference

The agent sees only the brief (`haus-mueller.md`), an empty folder and `uea help`. The logging
`uea` records every call with its operations, exit code and output in RUN/calls.jsonl, so
errors are counted from the log, not from the agent's report. The comparison works on derived
geometry, not on ids or expressions: storeys by height, walls by footprint, openings by
position, rooms by name and finished area, the roof by eaves and ridge. Results: results.md.
"""

import json
import shutil
import stat
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uea.derive import Derived, report
from uea.packs.arch.wofl import wofl
from uea.project import Project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BRIEF = HERE / "haus-mueller.md"
REFERENCE = ROOT / "docs" / "prototype" / "haus-mueller"

WRAPPER = '''\
#!{python}
"""uea, plus a log of every call in ../calls.jsonl (written by bench.agent setup)."""
import contextlib, io, json, sys, time
from pathlib import Path
from uea.cli import main

args = sys.argv[1:]
ops = None
if "apply" in args and "-f" not in args and not sys.stdin.isatty():
    ops = sys.stdin.read()
    sys.stdin = io.StringIO(ops)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try:
        code = main(args)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0 if e.code is None else 2
sys.stdout.write(buf.getvalue())
rec = {{"t": time.time(), "args": args, "ops": ops, "code": code, "out": buf.getvalue()}}
with (Path(__file__).resolve().parent.parent / "calls.jsonl").open("a") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
sys.exit(code)
'''

PROMPT = """\
You are testing a building-modelling CLI called UEA the way an ordinary agent user would.
Your job: model a house from an architect's brief.

- The brief: {brief}
- Your run folder: {run}
- The CLI is not on PATH. Call it as {run}/bin/uea (a normal `uea`; `-C <dir>` runs it in
  another folder). Start with `uea help`, then create the project with `uea init {run}/haus`.

Rules (the test is void if you break them):
- Learn UEA only from `uea help` and its topics. Do not read, list or search any file outside
  your run folder except the brief: other folders contain the reference solution.
- Change the model only through `uea apply` batches (and `uea revert`). Do not edit .uea files.
- Do not compute areas, heights or other derived values yourself; read them from UEA.
- Work like a careful professional: build in batches, run `uea check`, look at
  `uea render <level>` if useful, fix what is wrong. Follow the brief's dimensions exactly.

When you are done, reply with (under 400 words):
1. The deliverables from the brief, and the paths of the IFC and plan images.
2. An honest list of every problem you hit: unclear help, rejected batches and why, guesses
   you had to make, anything you could not model or are unsure about.
"""


def setup(run: Path) -> str:
    """Create the run folder with its logging `uea`; return the prompt for the agent."""
    (run / "bin").mkdir(parents=True, exist_ok=False)
    wrapper = run / "bin" / "uea"
    wrapper.write_text(WRAPPER.format(python=sys.executable), encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return PROMPT.format(brief=BRIEF, run=run.resolve())


def _r(v: float) -> float:
    return round(v + 0.0, 3)


def _label(d: Derived, key: str | None) -> str | None:
    if key is None:
        return None
    el = d.model.get(key)
    return (el.label or "").strip().lower() if el is not None else key


def facts(d: Derived) -> dict[str, Counter[str]]:
    """What the brief fixes, as comparable strings. Storeys are named by height."""
    g = d.arch
    m = d.model
    lv = {k: f"z{_r(x.z)}" for k, x in g.levels.items()}
    out: dict[str, Counter[str]] = {
        "levels": Counter(f"z={_r(x.z)} fb={_r(x.fb)} head={x.head}" for x in g.levels.values()),
        "walls": Counter(
            f"{lv[w.level]} {w.o} {_r(w.lo)}..{_r(w.hi)} along {_r(w.s0)}..{_r(w.s1)}"
            f" t={_r(w.layers.total)} lb={w.lb}"
            for w in g.walls.values()
        ),
        "openings": Counter(),
        "stairs": Counter(
            f"{lv[s.level]}->{lv[s.to]} {_r(s.x0)}..{_r(s.x1)} x {_r(s.y0)}..{_r(s.y1)}"
            f" up={s.up} n={s.n} riser={_r(s.riser)} tread={_r(s.tread)}"
            for s in g.stairs.values()
        ),
        "slabs": Counter(
            f"{lv[s.level]} area={s.outline.area:.2f} top={_r(s.top)} net={s.net.area:.2f}"
            for s in g.slabs.values()
        ),
        "roofs": Counter(
            f"{lv[r.level]} {r.shape} {r.pitch:g} eaves={r.eaves_z:.2f} ridge={r.ridge_z:.2f}"
            f" over={tuple(round(v, 3) for v in r.over.bounds)}"
            for r in g.roofs.values()
        ),
        "rooms": Counter(
            f"{lv[rg.level]} {_label(d, rg.id)} {getattr(m[rg.id], 'use', '')}"
            f" fin={rg.area_fin:.2f}"
            for rg in g.rooms.values()
        ),
    }
    for o in g.openings.values():
        if o.kind == "niche":  # the brief has none
            continue
        el = m[o.id]
        extra = ""
        if o.kind == "door":
            into = getattr(el, "into", None)
            typ = getattr(el, "type", None)
            extra = (
                f" into={_label(d, into.id) if into is not None else None}"
                f" hand={getattr(el, 'hand', None)}"
                f" type={_label(d, typ.id) if typ is not None else 'default'}"
            )
        out["openings"][
            f"{lv[o.level]} {o.kind} {o.axis} {_r(o.lo)}..{_r(o.hi)}"
            f" z {_r(o.sill)}..{_r(o.top)}{extra}"
        ] += 1
    return out


@dataclass
class Comparison:
    errors: list[str]
    warnings: list[str]
    missing: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    extra: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    expected: int = 0
    wohnflaeche: float | None = None
    reference_wohnflaeche: float = 0.0

    @property
    def matching(self) -> int:
        return self.expected - sum(len(v) for v in self.missing.values())


def reference() -> Project:
    root = Path(tempfile.mkdtemp()) / "reference"
    Project.init(root)
    for name in ("project.uea", "arch.uea"):
        shutil.copy(REFERENCE / name, root / name)
    return Project(root)


def compare(project: Project) -> Comparison:
    dr, _ = report(reference().load())
    da, rep = report(project.load())
    c = Comparison(
        [f"{i.code} {i.el}" for i in rep.errors()],
        [f"{i.code} {i.el}" for i in rep.warnings()],
    )
    fr, fa = facts(dr), facts(da)
    for k in fr:
        c.expected += sum(fr[k].values())
        c.missing[k] = sorted((fr[k] - fa[k]).elements())
        c.extra[k] = sorted((fa[k] - fr[k]).elements())
    c.reference_wohnflaeche = float(wofl(dr, None).data["total"])
    try:
        c.wohnflaeche = float(wofl(da, None).data["total"])
    except ValueError:
        c.wohnflaeche = None
    return c


def calls(run: Path) -> list[dict[str, Any]]:
    log = run / "calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def find_project(run: Path) -> Project:
    hits = [p.parent for p in run.rglob("log.jsonl")]
    if len(hits) != 1:
        raise SystemExit(f"expected one project under {run}, found {len(hits)}")
    return Project(hits[0])


def summary(run: Path) -> str:
    project = find_project(run)
    c = compare(project)
    lines = [f"project {project.root}", f"errors {c.errors} · warnings {c.warnings}"]
    for k in c.missing:
        for x in c.missing[k]:
            lines.append(f"  - {k}: {x}")
        for x in c.extra[k]:
            lines.append(f"  + {k}: {x}")
    lines.append(f"facts matching {c.matching}/{c.expected}")
    w = "failed" if c.wohnflaeche is None else f"{c.wohnflaeche:.2f}"
    lines.append(f"Wohnfläche {w} (reference {c.reference_wohnflaeche:.2f})")
    out = project.out
    files = sorted(p.name for p in out.iterdir()) if out.exists() else []
    lines.append(f"out/ {' '.join(files) or '-'}")
    log = calls(run)
    if log:
        applies = [x for x in log if "apply" in x["args"]]
        failed = [x for x in log if x["code"] != 0]
        lines.append(f"{len(log)} uea calls, {len(applies)} apply, {len(failed)} nonzero exit")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("setup", "compare"):
        print(__doc__)
        return 1
    run = Path(argv[1])
    if argv[0] == "setup":
        print(setup(run))
        return 0
    print(summary(run))
    return 0

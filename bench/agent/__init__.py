"""The agent test: an off-the-shelf agent builds Haus Müller from a written brief.

    uv run python -m bench.agent setup RUN [--services]   run folder with a logging `uea`, prints
                                                          the prompt
    uv run python -m bench.agent compare RUN              the agent's model against the reference

The shell run: the agent sees only the brief (`haus-mueller.md`), an empty folder and `uea help`.
The services run (`--services`): the reference shell without its niches and holes, the brief
`haus-mueller-services.md`, and synthetic norm tables of our own (`tables/`, not a standard's
values) installed for the run, so the calculators work; the agent plans electrical, heating,
plumbing and ventilation, and answers its own requests as the architect.

The logging `uea` records every call with its operations, exit code and output in
RUN/calls.jsonl, so errors are counted from the log, not from the agent's report. The comparison
works on derived values, not on ids or expressions: storeys by height, walls by footprint,
openings by position, rooms by name and finished area, the roof by eaves and ridge; the
services by what is in which room, which rooms each circuit serves, and what passes each hole.
Results: results.md.
"""

import json
import os
import stat
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uea.calc import Env, builtin
from uea.calc import data as norm_data
from uea.core.schema import Element
from uea.derive import Derived, report
from uea.packs.arch.wofl import wofl
from uea.packs.net import hole_users
from uea.project import Project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BRIEF = HERE / "haus-mueller.md"
SERVICES_BRIEF = HERE / "haus-mueller-services.md"
TABLES = HERE / "tables"
REFERENCE = ROOT / "docs" / "prototype" / "haus-mueller"
PACKS = ("project", "arch", "light", "elec", "heat", "plumb", "vent", "issues")
SETTINGS: dict[str, dict[str, str]] = {
    "heatload": {"tb": "0.05", "n50": "1.5", "shielding": "moderate"},
    "hydronic": {"tb": "0.05", "n50": "1.5", "shielding": "moderate", "spread": "5", "vmax": "0.8"},
    "airflow": {"n50": "1.5", "insulation": "high"},
    "ducts": {"n50": "1.5", "insulation": "high", "vmax": "3"},
}
"""The settings the services brief gives for each calculator."""

WRAPPER = '''\
#!{python}
"""uea, plus a log of every call in ../calls.jsonl (written by bench.agent setup)."""
import contextlib, io, json, sys, time
from pathlib import Path
import os
data = Path(__file__).resolve().parent.parent / "data"
if data.is_dir():
    os.environ["UEA_DATA"] = str(data)
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


PROMPT_SERVICES = """\
You are testing a building-modelling CLI called UEA the way an ordinary agent user would.
Your job: plan the building services of a house from the Fachplaner's brief.

- The brief: {brief}
- The house: {run}/haus, a UEA project with the architecture already modelled.
- The CLI is not on PATH. Call it as {run}/bin/uea (a normal `uea`; `-C <dir>` runs it in
  another folder). Start with `uea help`. The norm tables the calculators need are installed.

Rules (the test is void if you break them):
- Learn UEA only from `uea help` and its topics. Do not read, list or search any file outside
  your run folder except the brief: other folders contain the reference solution.
- Change the model only through `uea apply` batches (and `uea revert`). Do not edit .uea files.
- Do not compute areas, loads, air flows, pipe sizes or other derived values yourself; read them
  from UEA or run its calculators.
- Work as each Fachplaner in turn (--by elec, heat, plumb, vent). Where a discipline needs
  something of the architecture (a niche, a hole), ask with a request; then act as the architect
  only to answer it (--by arch) and close it. Change nothing else of the architecture.
- Work like a careful professional: build in batches, run `uea check`, fix what is wrong.

When you are done, reply with (under 400 words):
1. The deliverables from the brief, and the paths of the reports and plans.
2. An honest list of every problem you hit: unclear help, rejected batches and why, guesses
   you had to make, anything you could not model or are unsure about.
"""


def setup(run: Path, services: bool = False) -> str:
    """Create the run folder with its logging `uea`; return the prompt for the agent. For the
    services run also the house (the reference shell without niches and holes) and the tables."""
    (run / "bin").mkdir(parents=True, exist_ok=False)
    wrapper = run / "bin" / "uea"
    wrapper.write_text(WRAPPER.format(python=sys.executable), encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if not services:
        return PROMPT.format(brief=BRIEF, run=run.resolve())
    house = Project.init(run / "haus")
    for name in ("project.uea", "arch.uea"):
        lines = (REFERENCE / name).read_text(encoding="utf-8").splitlines()
        keep = [x for x in lines if x.split(" ")[0] not in ("niche", "hole")]
        (house.root / name).write_text("\n".join(keep) + "\n", encoding="utf-8")
    install_tables(run / "data")
    return PROMPT_SERVICES.format(brief=SERVICES_BRIEF, run=run.resolve())


def install_tables(target: Path) -> None:
    """The synthetic tables of the services run, as `uea data add` stores them."""
    specs = norm_data.specs_of(builtin().values())
    before = os.environ.get(norm_data.ENV)
    os.environ[norm_data.ENV] = str(target)
    try:
        for f in sorted(TABLES.glob("*.csv")):
            table, errors = norm_data.add(specs[f.stem], f, "synthetic (agent test)")
            if table is None:
                raise SystemExit(f"{f.name}: {'; '.join(errors)}")
    finally:
        if before is None:
            del os.environ[norm_data.ENV]
        else:
            os.environ[norm_data.ENV] = before


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


def _where(d: Derived, key: str) -> str:
    """The room an element of the services is in, by name, or outside its storey."""
    mt = d.mounts.get(key) or d.heat.at.get(key) or d.plumb.at.get(key) or d.vent.at.get(key)
    if mt is None:
        return "nowhere"
    return _label(d, mt.room) or f"outside {d.arch.levels[mt.level].z:g}"


def _v(el: Element, name: str) -> Any:
    """A field of an element whose kind the caller knows."""
    return getattr(el, name)


def services(d: Derived) -> dict[str, Counter[str]]:
    """What the services brief fixes, as comparable strings: what is in which room, which rooms
    each circuit serves, what each hole is for. Rooms by name, storeys by height."""
    m = d.model

    def of(kind: str, text: Callable[[Element], str]) -> Counter[str]:
        return Counter(text(el) for el in m.of_kind(kind))

    def per_room(kind: str, field: str | None = None) -> Counter[str]:
        total: Counter[str] = Counter()
        for el in m.of_kind(kind):
            total[_where(d, el.id)] += int(_v(el, field)) if field else 1
        return Counter(f"{room} {kind} {k}" for room, k in total.items())

    def where(el: Element, *fields: str) -> str:
        return " ".join([el.kind, _where(d, el.id), *(str(_v(el, f)) for f in fields)])

    circuits: Counter[str] = Counter()
    for c in d.elec.circuits.values():
        rooms = {_where(d, k) for k in [*c.devices, *c.lums] if m[k].kind != "feed"}
        rooms |= {
            _where(d, _v(f, "target").id) for f in m.of_kind("feed") if _v(f, "circuit").id == c.id
        }
        rcd = _v(m[c.rcd], "type") if c.rcd in m else None
        circuits[f"{c.breaker.fmt()} p={c.phases} rcd={rcd} in {','.join(sorted(rooms))}"] += 1
    users = hole_users(d)
    holes: Counter[str] = Counter()
    for h in d.arch.holes.values():
        kinds = sorted({m[k].kind for k in users.get(h.id, []) if k in m})
        holes[f"{'wall' if h.wall is not None else 'slab'} for {','.join(kinds) or '-'}"] += 1
    niches: Counter[str] = Counter()
    for o in d.arch.openings.values():
        if o.kind == "niche":
            room = o.sides[0] if o.face == "lo" else o.sides[1]
            niches[f"z{d.arch.levels[o.level].z:g} niche in {_label(d, room)}"] += 1
    return {
        "boards": of("board", lambda el: f"{_where(d, el.id)} media={_v(el, 'media')}"),
        "rcds": of("rcd", lambda el: f"{_v(el, 'rating').fmt()} {_v(el, 'type')}"),
        "circuits": circuits,
        "sockets": per_room("sock", "n"),
        "connections": per_room("conn"),
        "switches": per_room("switch"),
        "luminaires": per_room("lum"),
        "data": per_room("data", "n"),
        "smoke": per_room("smoke"),
        "feeds": of("feed", lambda el: where(m[_v(el, "target").id])),
        "heating": Counter(
            [where(el) for k in ("gen", "tank", "rad") for el in m.of_kind(k)]
            + [f"{where(el)} in {m[_v(el, 'host').id].kind}" for el in m.of_kind("man")]
            + [f"ufh {_label(d, _v(el, 'room').id)}" for el in m.of_kind("ufh")]
        ),
        "plumbing": Counter(
            [where(el) for k in ("meter", "riser", "stack", "sewer") for el in m.of_kind(k)]
            + [where(el, "fixture") for el in m.of_kind("san")]
        ),
        "ventilation": Counter(
            [where(el) for el in m.of_kind("ahu")]
            + [where(el, "role") for el in m.of_kind("air")]
            + [where(el, "mode") for el in m.of_kind("fan")]
        ),
        "niches": niches,
        "holes": holes,
    }


def calcs(d: Derived, data: Path) -> dict[str, str]:
    """Each calculator of the services brief with its settings: ok, not met, or why it failed."""
    before = os.environ.get(norm_data.ENV)
    os.environ[norm_data.ENV] = str(data)
    out: dict[str, str] = {}
    try:
        for name, given in SETTINGS.items():
            calc = builtin()[name]
            try:
                o = calc.fn(d, None, Env(calc, given))
                out[name] = "ok" if o.ok else "not met"
            except ValueError as e:
                out[name] = f"failed: {e}"
    finally:
        if before is None:
            del os.environ[norm_data.ENV]
        else:
            os.environ[norm_data.ENV] = before
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


def reference(full: bool = False) -> Project:
    """The reference: the shell, or the whole house (without the illuminance targets, which
    wait for the lighting design)."""
    root = Path(tempfile.mkdtemp()) / "reference"
    Project.init(root)
    for name in PACKS if full else ("project", "arch"):
        lines = (REFERENCE / f"{name}.uea").read_text(encoding="utf-8").splitlines()
        keep = [x for x in lines if x.split(" ")[0] != "illum"]
        (root / f"{name}.uea").write_text("\n".join(keep) + "\n", encoding="utf-8")
    return Project(root)


def compare(project: Project, full: bool = False) -> Comparison:
    """The shell's facts against the reference, or with full= the services' facts."""
    dr, _ = report(reference(full).load())
    da, rep = report(project.load())
    c = Comparison(
        [f"{i.code} {i.el}" for i in rep.errors()],
        [f"{i.code} {i.el}" for i in rep.warnings()],
    )
    fr, fa = (services(dr), services(da)) if full else (facts(dr), facts(da))
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
    full = (run / "data").is_dir()
    c = compare(project, full)
    lines = [f"project {project.root}", f"errors {c.errors} · warnings {c.warnings}"]
    for k in c.missing:
        for x in c.missing[k]:
            lines.append(f"  - {k}: {x}")
        for x in c.extra[k]:
            lines.append(f"  + {k}: {x}")
    lines.append(f"facts matching {c.matching}/{c.expected}")
    w = "failed" if c.wohnflaeche is None else f"{c.wohnflaeche:.2f}"
    lines.append(f"Wohnfläche {w} (reference {c.reference_wohnflaeche:.2f})")
    if full:
        dr, _ = report(reference(True).load())
        da, _ = report(project.load())
        mine, ref = calcs(da, run / "data"), calcs(dr, run / "data")
        lines += [f"calc {k}: {v} (reference {ref[k]})" for k, v in mine.items()]
        lines.append(f"open requests {[r.id for r in report(project.load())[1].requests]}")
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
    flags = [a for a in argv if a.startswith("--")]
    argv = [a for a in argv if not a.startswith("--")]
    if len(argv) != 2 or argv[0] not in ("setup", "compare") or set(flags) - {"--services"}:
        print(__doc__)
        return 1
    run = Path(argv[1])
    if argv[0] == "setup":
        print(setup(run, "--services" in flags))
        return 0
    print(summary(run))
    return 0

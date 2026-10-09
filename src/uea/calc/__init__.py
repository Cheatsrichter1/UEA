"""Calculators: typed modules with declared inputs and outputs.

`norm` calculators ship with a pack and implement one method of one standard; `custom`
calculators are written by agents for one project and live in its `calc/` folder. Every
result records calculator, kind, version, inputs and the model state it ran on, and a
`custom` result is never presented as norm-compliant (docs/decisions/0007).
"""

import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from uea.calc import data

if TYPE_CHECKING:
    from uea.cli import Ctx


KIND_DE = {"norm": "Normverfahren", "custom": "projektspezifisch (custom), nicht normkonform"}


@dataclass
class Output:
    lines: list[str]
    """Terse result for the agent."""
    report: str
    """Markdown for humans (German, for German offices)."""
    data: dict[str, Any] = field(default_factory=dict[str, Any])
    inputs: dict[str, Any] = field(default_factory=dict[str, Any])
    tables: list[str] = field(default_factory=list[str])
    """Norm tables used, with edition."""
    ok: bool = True


@dataclass(frozen=True)
class Param:
    """A setting of a calculator, given as `name=value` after the scope."""

    name: str
    kind: type[float] | type[int] | type[str]
    default: float | int | str | None
    """None: the caller must give it."""
    doc: str
    choices: tuple[str, ...] = ()
    optional: bool = False
    """With no default: leaving it out is allowed and the calculator gets None."""


@dataclass(frozen=True)
class Calculator:
    name: str
    title: str
    kind: Literal["norm", "custom"]
    version: str
    fn: Callable[..., Output]
    """`fn(d, scope)`, or `fn(d, scope, env)` when the calculator declares params or tables."""
    norm: str | None = None
    """The standard and edition a norm calculator implements."""
    params: tuple[Param, ...] = ()
    tables: tuple[data.Spec, ...] = ()
    """The norm tables it needs from the office (decision 0008)."""

    @property
    def wants_env(self) -> bool:
        return bool(self.params or self.tables)


class Env:
    """What a calculator is given besides the model: its settings and the office's tables."""

    def __init__(self, calc: Calculator, given: dict[str, str]) -> None:
        self.calc = calc
        self.values: dict[str, Any] = {}
        self.used: dict[str, data.Table] = {}
        known = {p.name: p for p in calc.params}
        for k in given:
            if k not in known:
                names = ", ".join(known) or "none"
                raise ValueError(f"unknown setting {k}=. {calc.name} takes: {names}")
        for p in calc.params:
            self.values[p.name] = self._value(p, given.get(p.name))

    def _value(self, p: Param, raw: str | None) -> Any:
        if raw is None:
            if p.default is None and not p.optional:
                raise ValueError(f"{self.calc.name} needs {p.name}=<value>: {p.doc}")
            return p.default
        try:
            v: Any = p.kind(raw)
        except ValueError:
            raise ValueError(f"{p.name}={raw} is not a {p.kind.__name__}: {p.doc}") from None
        if p.choices:
            for c in p.choices:
                if c.casefold() == str(v).casefold():
                    return c
            raise ValueError(f"{p.name}={raw} is not one of {', '.join(p.choices)}")
        return v

    def param(self, name: str) -> Any:
        return self.values[name]

    def table(self, spec: data.Spec) -> data.Table:
        got = self.used.get(spec.id)
        if got is None:
            got = self.used[spec.id] = data.need(spec)
        return got

    @property
    def cites(self) -> list[str]:
        return [t.cite() for t in self.used.values()]


@dataclass
class Result:
    calc: Calculator
    scope: str | None
    out: Output
    state: dict[str, Any]

    def head(self) -> str:
        scope = self.scope or "all"
        tail = f" · {self.calc.norm}" if self.calc.kind == "norm" and self.calc.norm else ""
        if self.calc.kind == "custom":
            tail = " · not norm-compliant"
        c = self.calc
        return f"{c.kind} {c.name} {c.version} · {c.title} · {scope}{tail}"

    def provenance_md(self) -> str:
        c = self.calc
        lines = [
            "| | |",
            "|---|---|",
            f"| Rechenverfahren | `{c.name}` {c.version} ({c.title}) |",
            f"| Art | **{KIND_DE[c.kind]}** |",
        ]
        if c.norm:
            lines.append(f"| Norm | {c.norm} |")
        lines.append(f"| Umfang | {self.scope or 'gesamtes Projekt'} |")
        lines.append(f"| Modellstand | Batch {self.state['batch']} |")
        lines.append(f"| Erstellt | {self.state['time']} |")
        if self.out.tables:
            lines.append(f"| Normtabellen | {'<br>'.join(self.out.tables)} |")
        return "\n".join(lines)

    def as_json(self) -> dict[str, Any]:
        return {
            "calculator": self.calc.name,
            "kind": self.calc.kind,
            "version": self.calc.version,
            "norm": self.calc.norm,
            "scope": self.scope,
            "state": self.state,
            "inputs": self.out.inputs,
            "tables": self.out.tables,
            "ok": self.out.ok,
            "data": self.out.data,
        }


def builtin() -> dict[str, Calculator]:
    from uea.packs.arch.wofl import WOFL
    from uea.packs.elec.cable import CABLE
    from uea.packs.elec.vdrop import VDROP

    return {c.name: c for c in (WOFL, CABLE, VDROP)}


def project_calcs(root: Path) -> tuple[dict[str, Calculator], list[str]]:
    """Custom calculators in <project>/calc/*.py. Each defines CALCULATOR = Calculator(...)."""
    out: dict[str, Calculator] = {}
    errors: list[str] = []
    folder = root / "calc"
    if not folder.is_dir():
        return out, errors
    for path in sorted(folder.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"uea_project_calc_{path.stem}", path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:  # agent-written code: report, never crash
            errors.append(f"calc/{path.name}: {type(e).__name__}: {e}")
            continue
        c = getattr(mod, "CALCULATOR", None)
        if not isinstance(c, Calculator):
            errors.append(f"calc/{path.name}: define CALCULATOR = Calculator(...)")
            continue
        # project calculators are custom, whatever they declare
        out[c.name] = Calculator(
            c.name, c.title, "custom", c.version, c.fn, None, c.params, c.tables
        )
    return out, errors


def md_table(head: list[str], rows: list[list[str]], right: tuple[int, ...] = ()) -> str:
    """A Markdown table; the columns in `right` are right-aligned (numbers)."""
    sep = ["---:" if i in right else "---" for i in range(len(head))]
    lines = [head, sep, *rows]
    return "\n".join("| " + " | ".join(r) + " |" for r in lines)


def de(v: float, places: int = 2) -> str:
    """A number with a decimal comma, for the German reports."""
    return f"{v:.{places}f}".replace(".", ",")


def split_args(rest: list[str]) -> tuple[str | None, dict[str, str]]:
    """The scope (the one argument without =) and the settings (name=value) after a calculator."""
    scope: str | None = None
    given: dict[str, str] = {}
    for a in rest:
        if "=" in a:
            k, _, v = a.partition("=")
            given[k] = v
        elif scope is None:
            scope = a
        else:
            raise ValueError(f"give one scope at most, not {scope} and {a}")
    return scope, given


def run_calc(ctx: "Ctx", out: Callable[[Any], None], out_json: Callable[[Any], None]) -> int:
    project = ctx.project
    calcs = builtin()
    custom, errors = project_calcs(project.root)
    for name, c in custom.items():
        if name in calcs:
            errors.append(f"calc/{name}: the name {name} is taken by a norm calculator; rename it")
        else:
            calcs[name] = c
    name: str | None = ctx.args.name
    if name is None:
        lines = [f"{c.name}  {c.kind} {c.version}  {c.title}" for c in calcs.values()]
        out([*lines, *errors] or "no calculators")
        return 0
    if name not in calcs:
        out([f"unknown calculator {name!r}. Available: {' '.join(calcs)}", *errors])
        return 1
    calc = calcs[name]
    d, _ = ctx.derived()
    scope: str | None = None
    try:
        scope, given = split_args(ctx.args.rest)
        if not calc.wants_env and given:
            raise ValueError(f"{calc.name} takes no settings (got {', '.join(given)})")
        if calc.wants_env:
            env = Env(calc, given)
            o = calc.fn(d, scope, env)
            o.tables = [*o.tables, *env.cites]
            o.inputs = {**o.inputs, "settings": env.values}
        else:
            o = calc.fn(d, scope)
    except ValueError as e:
        out(f"{calc.name}: {e}")
        return 1
    state = {
        "batch": project.history.last(),
        "files": project.hashes(),
        "time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    res = Result(calc, scope, o, state)
    project.out.mkdir(exist_ok=True)
    stem = calc.name + (f"-{scope}" if scope else "")
    md = project.out / f"{stem}.md"
    md.write_text(res.provenance_md() + "\n\n" + o.report, encoding="utf-8")
    (project.out / f"{stem}.json").write_text(
        json.dumps(res.as_json(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if ctx.json:
        out_json(res.as_json())
    else:
        out([res.head(), *o.lines, f"report: out/{md.name}"])
    return 0 if o.ok else 1

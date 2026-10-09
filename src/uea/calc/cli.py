"""`uea data`: the norm tables an office supplies (decision 0028). Needs no project."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from uea.calc import builtin, data

if TYPE_CHECKING:
    from uea.cli import Ctx

USAGE = (
    "uea data                              the tables the calculators need; which are installed\n"
    "uea data show <id>                    its columns and what to copy into them\n"
    "uea data add <id> <file.csv> --edition <e> [--source <s>]   check and install a table\n"
    "uea data remove <id>"
)


def _row(t: data.Table, n: int) -> str:
    return " ".join(
        f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in t.rows[n].items()
    )


def run_data(
    ctx: "Ctx", out: Callable[[str | Sequence[str]], None], out_json: Callable[[Any], None]
) -> int:
    specs = data.specs_of(builtin().values())
    action: str | None = ctx.args.action
    rest: list[str] = ctx.args.rest
    if action is None:
        if ctx.json:
            out_json(
                {
                    k: {
                        "title": s.title,
                        "standard": s.standard,
                        "installed": data.load(s) is not None,
                    }
                    for k, s in specs.items()
                }
            )
            return 0
        lines: list[str] = []
        for s in specs.values():
            t = data.load(s)
            state = f"edition {t.edition}, {len(t.rows)} rows" if t else "missing"
            lines.append(f"{s.id}  {state}  {s.title} ({s.standard})")
        out([*lines, f"folder: {data.root()}"])
        return 0
    if action not in ("show", "add", "remove"):
        out([f"unknown action {action!r}", USAGE])
        return 2
    if not rest or rest[0] not in specs:
        out([f"{action} needs a table id: {' '.join(specs)}", USAGE])
        return 2
    spec = specs[rest[0]]
    if action == "show":
        t = data.load(spec)
        lines = [f"{spec.id}: {spec.title} ({spec.standard})"]
        if spec.doc:
            lines.append(spec.doc)
        lines.append("columns (CSV, first line the header):")
        for c in spec.cols:
            allowed = f" one of {', '.join(c.choices)}" if c.choices else ""
            lines.append(f"  {c.name}  {c.kind}{allowed}  {c.doc}".rstrip())
        lines.append(f"one row per {', '.join(spec.key)}")
        if t is None:
            lines.append("not installed")
        else:
            lines.append(
                f"installed: edition {t.edition}"
                + (f", {t.source}" if t.source else "")
                + f", {len(t.rows)} rows, added {t.added}, sha256 {t.sha[:8]}"
            )
            lines += [f"  {_row(t, i)}" for i in range(min(3, len(t.rows)))]
        out(lines)
        return 0
    if action == "remove":
        out(f"ok {spec.id}: removed" if data.remove(spec) else f"{spec.id} is not installed")
        return 0
    if len(rest) != 2 or not ctx.args.edition:
        out(["add needs a file and the edition it comes from:", USAGE])
        return 2
    table, errors = data.add(spec, Path(rest[1]), ctx.args.edition, ctx.args.source)
    if table is None:
        out([f"{spec.id}: {rest[1]} is not valid. Nothing was installed.", *errors])
        return 1
    out(f"ok {spec.id}: {len(table.rows)} rows, edition {table.edition} (sha256 {table.sha[:8]})")
    return 0

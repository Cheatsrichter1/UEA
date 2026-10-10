"""CLI glue for `uea import`."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from uea.batch import Result, run

if TYPE_CHECKING:
    from uea.cli import Ctx

FORMATS = ("ifc",)
SHOWN = 15
"""How many new issues are listed; `uea check` has the rest."""
LABEL = {
    "level": "levels",
    "type": "types",
    "wall": "walls",
    "door": "doors",
    "win": "windows",
    "slab": "slabs",
    "sep": "separators",
    "room": "rooms",
}


def run_import(
    ctx: "Ctx",
    by: str,
    out: Callable[[Any], None],
    out_json: Callable[[Any], None],
    issue_lines: Callable[[Any], list[str]],
    result_json: Callable[[Result], dict[str, Any]],
) -> int:
    from uea.importer.build import Known, plan
    from uea.importer.ifc import NotImportable, read

    fmt: str = ctx.args.format
    if fmt not in FORMATS:
        out(f"uea: cannot import {fmt!r}. Formats: {' '.join(FORMATS)}")
        return 1
    path = Path(ctx.args.file)
    if not path.is_file():
        out(f"uea: {path} is not a file")
        return 1
    try:
        src = read(path)
    except NotImportable as e:
        out(f"uea: {e}")
        return 1
    project = ctx.project
    state = {k: Known(*v) for k, v in project.history.ifc_state().items()}
    pl = plan(src, ctx.model, state)
    head = f"{src.file}: {src.schema}" + (f" from {src.app}" if src.app else "")
    if not pl.ops:
        lines = [f"{head}: nothing to change", *_tail(pl)]
        if ctx.json:
            out_json({"ok": True, "batch": None, "notes": pl.notes, "kept": pl.kept})
        else:
            out(lines)
        return 0
    msg: str = ctx.args.m or f"import {src.file}"
    res = run(project, pl.text, by, msg, dry=ctx.args.dry_run, ifc=pl.record, block=False)
    if ctx.json:
        out_json(
            {
                "import": {
                    "file": src.file,
                    "counts": pl.counts(res.applied),
                    "not_imported": dict(pl.skipped),
                    "notes": pl.notes,
                    "kept": pl.kept,
                },
                "result": result_json(res),
            }
        )
        return 0 if res.ok else 1
    if res.external:
        out(res.external)
    if res.errors:
        out(["rejected, nothing changed:", *res.errors])
        return 1
    if res.applied is not None and not res.applied.ops:
        out([f"{head}: nothing to change", *_tail(pl)])
        return 0
    counts = " · ".join(f"{n} {LABEL.get(k, k)}" for k, n in pl.counts(res.applied).items())
    gone = f" · {len(pl.gone)} removed" if pl.gone else ""
    where = "dry run, nothing written" if res.dry else f"batch {res.batch}"
    lines = [f"{head}: ok ({where}): {counts}{gone}"]
    if res.after is not None:
        errors = [i for i in res.new_issues if i.severity == "error"]
        warns = [i for i in res.new_issues if i.severity == "warning"]
        lines.append(f"issues: {len(errors)} errors · {len(warns)} warnings")
        shown = [*errors, *warns][:SHOWN]
        lines += issue_lines(shown)
        if len(errors) + len(warns) > SHOWN:
            lines.append(f"... {len(errors) + len(warns) - SHOWN} more: uea check arch")
    lines += _tail(pl)
    out(lines)
    return 0


def _tail(pl: Any) -> list[str]:
    lines: list[str] = []
    if pl.skipped:
        lines.append("not imported: " + " · ".join(f"{n} {k}" for k, n in pl.skipped.items()))
    lines += [f"note: {x}" for x in pl.notes[:SHOWN]]
    if len(pl.notes) > SHOWN:
        lines.append(f"... {len(pl.notes) - SHOWN} more notes")
    lines += [f"kept: {x}" for x in pl.kept]
    return lines

"""CLI glue for `uea import`."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from uea.batch import Result, run

if TYPE_CHECKING:
    from uea.cli import Ctx

FORMATS = ("ifc", "gaeb")
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
    "roof": "roofs",
    "stair": "stairs",
    "void": "voids",
    "grid": "grids",
    "niche": "niches",
    "hole": "holes",
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
    from uea.importer.ifc import Frame, NotImportable, read

    fmt: str = ctx.args.format
    if fmt not in FORMATS:
        out(f"uea: cannot import {fmt!r}. Formats: {' '.join(FORMATS)}")
        return 1
    path = Path(ctx.args.file)
    if not path.is_file():
        out(f"uea: {path} is not a file")
        return 1
    if fmt == "gaeb":
        return run_bid(ctx, path, by, out, out_json, issue_lines, result_json)
    project = ctx.project
    # a later import keeps where the first one put the plan, and the building it read
    last = project.history.ifc_last()
    frame = None if last is None else Frame(*(float(x) for x in last.get("frame", (0, 0, 0))))
    remembered = None if last is None else last.get("building")
    try:
        src = read(path, building=ctx.args.building, remembered=remembered, frame=frame)
    except NotImportable as e:
        out(f"uea: {e}")
        return 1
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
    done = [f"{n} {LABEL.get(k, k)}" for k, n in pl.counts(res.applied).items()]
    if pl.gone:
        done.append(f"{len(pl.gone)} removed")
    where = "dry run, nothing written" if res.dry else f"batch {res.batch}"
    lines = [f"{head}: ok ({where}): {' · '.join(done)}"]
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


def run_bid(
    ctx: "Ctx",
    path: Path,
    by: str,
    out: Callable[[Any], None],
    out_json: Callable[[Any], None],
    issue_lines: Callable[[Any], list[str]],
    result_json: Callable[[Result], dict[str, Any]],
) -> int:
    """A bidder's GAEB DA XML, phase 84, into the bid pack (0051)."""
    from uea.importer.gaeb import NotImportable, plan, read

    try:
        offer = read(path)
        d, _ = ctx.derived()
        pl = plan(offer, d, ctx.args.bidder)
    except NotImportable as e:
        out(f"uea: {e}")
        return 1
    msg: str = ctx.args.m or f"bid {offer.file}"
    res = run(ctx.project, pl.text, by, msg, dry=ctx.args.dry_run)
    if ctx.json:
        out_json(
            {
                "import": {"file": offer.file, "prices": pl.prices, "notes": pl.notes},
                "not_imported": pl.skipped,
                "result": result_json(res),
            }
        )
        return 0 if res.ok else 1
    if res.external:
        out(res.external)
    if res.errors or res.rejected:
        out(["rejected, nothing changed:", *res.errors, *issue_lines(res.rejected)])
        return 1
    bid = next((i for p, i in res.applied.added if p == "@b"), "?") if res.applied else "?"
    where = "dry run, nothing written" if res.dry else f"batch {res.batch}"
    lines = [f"{offer.file}: GAEB DA XML ({offer.phase}): ok ({where}): {bid}, {pl.prices} prices"]
    if res.derived is not None and bid in res.derived.bid.bids:
        s = res.derived.bid.bids[bid]
        lines[0] += f", {s.checked:.2f} € checked"
    lines += issue_lines(res.new_issues[:SHOWN])
    if len(res.new_issues) > SHOWN:
        lines.append(f"... {len(res.new_issues) - SHOWN} more: uea check bid")
    if pl.skipped:
        lines.append(f"not in the LV, not imported: {' · '.join(pl.skipped[:SHOWN])}")
    lines += [f"note: {x}" for x in pl.notes]
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

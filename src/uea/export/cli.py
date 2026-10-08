"""CLI glue for renders and exports. Exports are views: never read back into the model."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uea.cli import Ctx

FORMATS = ("ifc", "xlsx", "pdf", "dxf", "svg", "png")
SHEETS = ("pdf", "dxf", "svg", "png")
"""The formats of the floor plan sheet."""


def _levels(ctx: "Ctx", scope: str | None) -> list[str] | str:
    d, _ = ctx.derived()
    levels = d.arch.level_order()
    if scope is None or scope == "all":
        return levels
    if scope not in d.arch.levels:
        return f"unknown level {scope!r}. Levels: {' '.join(levels)}"
    return [scope]


def _plans(ctx: "Ctx", scope: str | None, out_path: str | None) -> list[str] | str:
    """The working plan of each storey as PNG, for an agent to look at."""
    from uea.export.drawing import to_png
    from uea.export.plan import plan

    levels = _levels(ctx, scope)
    if isinstance(levels, str):
        return levels
    d, _ = ctx.derived()
    folder = ctx.project.out
    folder.mkdir(exist_ok=True)
    lines: list[str] = []
    for lv in levels:
        dw = plan(d, lv, ctx.project.history.last())
        path = Path(out_path) if out_path and len(levels) == 1 else folder / f"plan-{lv}.png"
        w, h = to_png(dw, path)
        lines.append(f"{_rel(ctx, path)} {w}x{h} px")
    return lines


def _sheets(ctx: "Ctx", scope: str | None, fmt: str, out_path: str | None) -> list[str] | str:
    """The floor plan sheet of each storey, for humans (decision 0022)."""
    from uea.export.drawing import to_png, to_svg
    from uea.export.dxf import to_dxf
    from uea.export.pdf import to_pdf
    from uea.export.sheet import LAYER_COLORS, Stand, sheet_plan

    levels = _levels(ctx, scope)
    if isinstance(levels, str):
        return levels
    d, _ = ctx.derived()
    entries = ctx.project.history.entries()
    stand = Stand(entries[-1].batch, entries[-1].time[:10]) if entries else Stand()
    folder = ctx.project.out
    folder.mkdir(exist_ok=True)
    lines: list[str] = []
    for lv in levels:
        dw = sheet_plan(d, lv, stand)
        if dw is None or dw.sheet is None:
            lines.append(f"{lv}: no walls, nothing to draw")
            continue
        path = Path(out_path) if out_path and len(levels) == 1 else folder / f"plan-{lv}.{fmt}"
        if fmt == "svg":
            path.write_text(to_svg(dw), encoding="utf-8")
        elif fmt == "png":
            to_png(dw, path, max_px=2400)
        elif fmt == "pdf":
            to_pdf(dw, path)
        else:
            to_dxf(dw, path, LAYER_COLORS)
        lines.append(f"{_rel(ctx, path)} {dw.sheet.size} 1:{dw.sheet.scale}")
    return lines


def _rel(ctx: "Ctx", path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path


def _xlsx(ctx: "Ctx", scope: str | None, out_path: str | None) -> str | list[str]:
    from uea.export.tables import tables
    from uea.export.xlsx import write_xlsx

    levels = _levels(ctx, scope)
    if isinstance(levels, str):
        return levels
    d, _ = ctx.derived()
    level = None if scope is None or scope == "all" else scope
    sheets = tables(d, level)
    if not sheets:
        return "nothing to put in a table yet"
    name = d.model.project_name() or "project"
    ctx.project.out.mkdir(exist_ok=True)
    default = f"{name}-{level}.xlsx" if level else f"{name}.xlsx"
    path = Path(out_path) if out_path else ctx.project.out / default
    proj = d.model.of_kind("project")
    label = (proj[0].label or proj[0].id) if proj else name
    write_xlsx(sheets, path, label, ctx.project.history.last())
    return [f"{_rel(ctx, path)} " + " ".join(f"{t.name}({len(t.rows)})" for t in sheets)]


def render(ctx: "Ctx", out: Callable[[Any], None]) -> int:
    res = _plans(ctx, ctx.args.scope, ctx.args.out)
    if isinstance(res, str):
        out(res)
        return 1
    out(res)
    return 0


def export(ctx: "Ctx", out: Callable[[Any], None]) -> int:
    fmt: str = ctx.args.format
    if fmt not in FORMATS:
        out(f"unknown format {fmt!r}. Formats: {' '.join(FORMATS)}")
        return 1
    if fmt == "xlsx":
        res = _xlsx(ctx, ctx.args.scope, ctx.args.out)
        out(res)
        return 1 if isinstance(res, str) else 0
    if fmt in SHEETS:
        res = _sheets(ctx, ctx.args.scope, fmt, ctx.args.out)
        if isinstance(res, str):
            out(res)
            return 1
        out(res)
        return 0
    try:
        from uea.export.ifc import export_ifc
    except ImportError:
        out("IFC export needs IfcOpenShell: pip install 'uea[ifc]'")
        return 1
    d, _ = ctx.derived()
    name = d.model.project_name() or "project"
    ctx.project.out.mkdir(exist_ok=True)
    path = Path(ctx.args.out) if ctx.args.out else ctx.project.out / f"{name}.ifc"
    counts = export_ifc(d, path)
    out(f"{_rel(ctx, path)} IFC4: " + " ".join(f"{n} {k}" for k, n in counts.items()))
    return 0

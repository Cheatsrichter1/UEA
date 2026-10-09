"""CLI glue for renders and exports. Exports are views: never read back into the model."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from uea.core.registry import natural

if TYPE_CHECKING:
    from uea.cli import Ctx

FORMATS = ("ifc", "xlsx", "pdf", "dxf", "svg", "png")
SHEETS = ("pdf", "dxf", "svg", "png")
"""The formats of the sheets: floor plans and sections."""


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


def _sheet_targets(ctx: "Ctx", scope: str | None) -> list[tuple[str, str]] | str:
    """What to draw for humans: (kind, id) of floor plans, sections, elevations and the
    electrical sheets."""
    from uea.export.elevation import SIDES

    d, _ = ctx.derived()
    levels = d.arch.level_order()
    sections = sorted(d.arch.sections, key=natural)
    wired = {mt.level for mt in d.mounts.values()}
    installs = [("install", lv) for lv in levels if lv in wired]
    boards = sorted({c.board for c in d.elec.circuits.values() if c.board}, key=natural)
    electrical = [*installs, *(("board", b) for b in boards)]
    if scope is None or scope == "all":
        return [
            *(("plan", lv) for lv in levels),
            *(("section", k) for k in sections),
            *(("elevation", side) for side in SIDES),
            *electrical,
        ]
    if scope == "elec":
        return electrical or "nothing electrical to draw yet"
    if scope.startswith("elec:") or scope in boards:
        rest = scope.removeprefix("elec:")
        if rest in levels:
            return [("install", rest)] if rest in wired else f"nothing electrical on {rest}"
        if rest in boards:
            return [("board", rest)]
        known = f"Levels: {' '.join(levels)}. Boards: {' '.join(boards)}"
        return f"unknown level or board {rest!r}. {known}"
    if scope in SIDES:
        return [("elevation", scope)]
    if scope in d.arch.levels:
        return [("plan", scope)]
    if scope in d.arch.sections:
        return [("section", scope)]
    if scope in d.model and d.model[scope].kind == "section":
        return f"section {scope} has an error: uea check"
    known = f"Levels: {' '.join(levels)}. Sections: {' '.join(sections) or 'none'}."
    more = f" Electrical: elec, elec:<level>, {' '.join(boards)}." if boards else ""
    return f"unknown level, section or side {scope!r}. {known} Sides: {' '.join(SIDES)}.{more}"


def _sheets(ctx: "Ctx", scope: str | None, fmt: str, out_path: str | None) -> list[str] | str:
    """The floor plan of each storey, each section and elevation and the electrical sheets, as
    sheets for humans (decisions 0022 to 0026)."""
    from uea.export.board import sheet_board
    from uea.export.drawing import to_png, to_svg
    from uea.export.dxf import to_dxf
    from uea.export.elevation import sheet_elevation
    from uea.export.install import ELEC_LAYER_COLORS, sheet_install
    from uea.export.paper import LAYER_COLORS, Stand
    from uea.export.pdf import to_pdf
    from uea.export.section import sheet_section
    from uea.export.sheet import sheet_plan

    targets = _sheet_targets(ctx, scope)
    if isinstance(targets, str):
        return targets
    d, _ = ctx.derived()
    entries = ctx.project.history.entries()
    stand = Stand(entries[-1].batch, entries[-1].time[:10]) if entries else Stand()
    folder = ctx.project.out
    folder.mkdir(exist_ok=True)
    lines: list[str] = []
    for kind, key in targets:
        if kind == "plan":
            dw = sheet_plan(d, key, stand)
        elif kind == "section":
            dw = sheet_section(d, key, stand)
        elif kind == "install":
            dw = sheet_install(d, key, stand)
        elif kind == "board":
            dw = sheet_board(d, key, stand)
        else:
            dw = sheet_elevation(d, key, stand)
        if dw is None or dw.sheet is None:
            why = "the cut meets no wall" if kind == "section" else "no walls"
            lines.append(f"{key}: {why}, nothing to draw")
            continue
        name = {"install": "elec", "board": "board"}.get(kind, kind)
        path = Path(out_path) if out_path and len(targets) == 1 else folder / f"{name}-{key}.{fmt}"
        if fmt == "svg":
            path.write_text(to_svg(dw), encoding="utf-8")
        elif fmt == "png":
            to_png(dw, path, max_px=2400)
        elif fmt == "pdf":
            to_pdf(dw, path)
        else:
            to_dxf(dw, path, {**LAYER_COLORS, **ELEC_LAYER_COLORS})
        scale = "o. M." if kind == "board" else f"1:{dw.sheet.scale}"
        lines.append(f"{_rel(ctx, path)} {dw.sheet.size} {scale}")
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

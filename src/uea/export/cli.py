"""CLI glue for renders and exports. Exports are views: never read back into the model."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uea.cli import Ctx

FORMATS = ("ifc", "svg", "png")


def _levels(ctx: "Ctx", scope: str | None) -> list[str] | str:
    d, _ = ctx.derived()
    levels = d.arch.level_order()
    if scope is None or scope == "all":
        return levels
    if scope not in d.arch.levels:
        return f"unknown level {scope!r}. Levels: {' '.join(levels)}"
    return [scope]


def _drawings(ctx: "Ctx", scope: str | None, fmt: str, out_path: str | None) -> list[str] | str:
    from uea.export.drawing import to_png, to_svg
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
        path = Path(out_path) if out_path and len(levels) == 1 else folder / f"plan-{lv}.{fmt}"
        if fmt == "svg":
            path.write_text(to_svg(dw), encoding="utf-8")
            lines.append(str(_rel(ctx, path)))
        else:
            w, h = to_png(dw, path)
            lines.append(f"{_rel(ctx, path)} {w}x{h} px")
    return lines


def _rel(ctx: "Ctx", path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path


def render(ctx: "Ctx", out: Callable[[Any], None]) -> int:
    res = _drawings(ctx, ctx.args.scope, "png", ctx.args.out)
    if isinstance(res, str):
        out(res)
        return 1
    out(res)
    return 0


def export(ctx: "Ctx", out: Callable[[Any], None]) -> int:
    fmt: str = ctx.args.format
    if fmt not in FORMATS:
        out(
            f"unknown format {fmt!r}. Formats: {' '.join(FORMATS)}"
            " (dxf, pdf and xlsx come in phase 2)"
        )
        return 1
    if fmt in ("svg", "png"):
        res = _drawings(ctx, ctx.args.scope, fmt, ctx.args.out)
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

"""A neutral 2D drawing: polygons, lines, arcs, circles and text in plan metres.

Plans are built once as a Drawing and rendered to SVG, PNG, DXF and PDF, so every output shows
the same thing. A drawing with a `Sheet` is a sheet of paper at a scale (a plan to print): pen
widths and text sizes are then metres at that scale, and the renderers cut the view to the
paper.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image, ImageFont

Pt = tuple[float, float]


@dataclass(frozen=True)
class Pen:
    color: str = "#000000"
    width: float = 0.02
    """Line width in metres at plan scale."""
    dash: tuple[float, ...] = ()
    """Dash pattern in metres."""


@dataclass
class Poly:
    pts: list[Pt]
    fill: str | None = None
    pen: Pen | None = None
    layer: str = "0"
    holes: list[list[Pt]] = field(default_factory=list[list[Pt]])


@dataclass
class Line:
    a: Pt
    b: Pt
    pen: Pen
    layer: str = "0"


@dataclass
class Arc:
    c: Pt
    r: float
    a0: float
    """Start angle in degrees, counter-clockwise from +x."""
    a1: float
    pen: Pen
    layer: str = "0"


@dataclass
class Circle:
    c: Pt
    r: float
    pen: Pen
    fill: str | None = None
    layer: str = "0"


@dataclass
class Text:
    at: Pt
    text: str
    size: float = 0.18
    """Height in metres."""
    color: str = "#000000"
    anchor: str = "middle"
    """Horizontal anchor of the baseline point `at`: start, middle or end."""
    bold: bool = False
    layer: str = "0"
    rot: float = 0.0
    """Rotation in degrees, counter-clockwise."""


Item = Poly | Line | Arc | Circle | Text


@dataclass(frozen=True)
class Sheet:
    """A sheet of paper laid over the drawing, at a scale."""

    size: str
    """Paper format, e.g. A3."""
    paper: tuple[float, float]
    """Width and height in mm, landscape."""
    scale: int
    """The drawing is 1:scale on paper."""
    origin: Pt
    """Where the lower-left corner of the paper lies, in plan metres."""

    def m(self, mm: float) -> float:
        """A length on paper in mm, as plan metres."""
        return mm * self.scale / 1000

    def mm(self, m: float) -> float:
        """A length in plan metres, as mm on paper."""
        return m * 1000 / self.scale

    def pt(self, x_mm: float, y_mm: float) -> Pt:
        """A point on paper (mm from the lower-left corner), as plan metres."""
        return (self.origin[0] + self.m(x_mm), self.origin[1] + self.m(y_mm))

    def bounds(self) -> tuple[float, float, float, float]:
        x0, y0 = self.origin
        return (x0, y0, x0 + self.m(self.paper[0]), y0 + self.m(self.paper[1]))


@dataclass
class Drawing:
    title: str
    items: list[Item] = field(default_factory=list[Item])
    sheet: Sheet | None = None

    def add(self, item: Item) -> None:
        self.items.append(item)

    def bounds(self) -> tuple[float, float, float, float]:
        if self.sheet is not None:
            return self.sheet.bounds()
        xs: list[float] = []
        ys: list[float] = []
        for it in self.items:
            if isinstance(it, Poly):
                xs += [p[0] for p in it.pts]
                ys += [p[1] for p in it.pts]
            elif isinstance(it, Line):
                xs += [it.a[0], it.b[0]]
                ys += [it.a[1], it.b[1]]
            elif isinstance(it, Arc | Circle):
                xs += [it.c[0] - it.r, it.c[0] + it.r]
                ys += [it.c[1] - it.r, it.c[1] + it.r]
            else:
                xs.append(it.at[0])
                ys.append(it.at[1])
        if not xs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PX_PER_MM = 96 / 25.4
"""Pixels per mm of paper when a sheet is drawn at 96 dpi."""


def _view(dw: Drawing, scale: float, margin: float) -> tuple[float, float, float, float, float]:
    """Plan bounds with margin, the pixel scale and the height of the title strip (pixels)."""
    x0, y0, x1, y1 = dw.bounds()
    if dw.sheet is not None:
        return x0, y0, x1, y1, PX_PER_MM * 1000 / dw.sheet.scale
    return x0 - margin, y0 - margin, x1 + margin, y1 + margin, scale


def to_svg(dw: Drawing, scale: float = 50.0, margin: float = 1.0) -> str:
    x0, y0, x1, y1, scale = _view(dw, scale, margin)
    foot = 0 if dw.sheet is not None else 30
    w, h = (x1 - x0) * scale, (y1 - y0) * scale + foot

    def X(x: float) -> float:
        return (x - x0) * scale

    def Y(y: float) -> float:
        return (y1 - y) * scale

    def pen(p: Pen | None) -> str:
        if p is None:
            return 'stroke="none"'
        s = f'stroke="{p.color}" stroke-width="{max(p.width * scale, 0.5):.2f}"'
        if p.dash:
            s += f' stroke-dasharray="{" ".join(f"{d * scale:.1f}" for d in p.dash)}"'
        return s

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}"'
        f' viewBox="0 0 {w:.0f} {h:.0f}" font-family="DejaVu Sans, Arial, sans-serif">',
        f'<rect width="{w:.0f}" height="{h:.0f}" fill="white"/>',
    ]
    for it in dw.items:
        if isinstance(it, Poly):
            d = "M" + " L".join(f"{X(px):.1f},{Y(py):.1f}" for px, py in it.pts) + " Z"
            for hole in it.holes:
                d += " M" + " L".join(f"{X(px):.1f},{Y(py):.1f}" for px, py in hole) + " Z"
            fill = it.fill or "none"
            out.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd" {pen(it.pen)}/>')
        elif isinstance(it, Line):
            out.append(
                f'<line x1="{X(it.a[0]):.1f}" y1="{Y(it.a[1]):.1f}" x2="{X(it.b[0]):.1f}"'
                f' y2="{Y(it.b[1]):.1f}" {pen(it.pen)}/>'
            )
        elif isinstance(it, Circle):
            fill = it.fill or "none"
            out.append(
                f'<circle cx="{X(it.c[0]):.1f}" cy="{Y(it.c[1]):.1f}" r="{it.r * scale:.1f}"'
                f' fill="{fill}" {pen(it.pen)}/>'
            )
        elif isinstance(it, Arc):
            a0, a1 = math.radians(it.a0), math.radians(it.a1)
            sx, sy = it.c[0] + it.r * math.cos(a0), it.c[1] + it.r * math.sin(a0)
            ex, ey = it.c[0] + it.r * math.cos(a1), it.c[1] + it.r * math.sin(a1)
            large = 1 if (it.a1 - it.a0) % 360 > 180 else 0
            out.append(
                f'<path d="M{X(sx):.1f},{Y(sy):.1f} A{it.r * scale:.1f},{it.r * scale:.1f} 0'
                f' {large} 0 {X(ex):.1f},{Y(ey):.1f}" fill="none" {pen(it.pen)}/>'
            )
        else:
            weight = ' font-weight="bold"' if it.bold else ""
            tx, ty = X(it.at[0]), Y(it.at[1])
            turn = f' transform="rotate({-it.rot:.1f} {tx:.1f} {ty:.1f})"' if it.rot else ""
            for i, line in enumerate(it.text.split("\n")):
                out.append(
                    f'<text x="{tx:.1f}" y="{ty + i * it.size * scale * 1.2:.1f}"'
                    f' font-size="{it.size * scale:.1f}" fill="{it.color}"'
                    f' text-anchor="{it.anchor}"{weight}{turn}>{_esc(line)}</text>'
                )
    if dw.sheet is None:
        out.append(f'<text x="8" y="{h - 10:.0f}" font-size="14">{_esc(dw.title)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def to_png(dw: Drawing, path: Path, max_px: int = 1400, margin: float = 1.0) -> tuple[int, int]:
    from PIL import Image, ImageDraw, ImageFont

    x0, y0, x1, y1, _ = _view(dw, 1.0, margin)
    scale = max_px / max(x1 - x0, y1 - y0)
    foot = 0 if dw.sheet is not None else 30
    w, h = round((x1 - x0) * scale), round((y1 - y0) * scale) + foot
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)

    def P(p: Pt) -> tuple[float, float]:
        return ((p[0] - x0) * scale, (y1 - p[1]) * scale)

    fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def font(px: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (px, bold)
        if key not in fonts:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            try:
                fonts[key] = ImageFont.truetype(name, px)
            except OSError:
                fonts[key] = ImageFont.load_default(px)
        return fonts[key]

    def seg(a: Pt, b: Pt, p: Pen) -> None:
        width = max(1, round(p.width * scale))
        if not p.dash:
            dr.line([P(a), P(b)], fill=p.color, width=width)
            return
        length = math.dist(a, b)
        if length == 0:
            return
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos, i = 0.0, 0
        while pos < length:
            step = p.dash[i % len(p.dash)]
            if i % 2 == 0:
                end = min(pos + step, length)
                dr.line(
                    [P((a[0] + ux * pos, a[1] + uy * pos)), P((a[0] + ux * end, a[1] + uy * end))],
                    fill=p.color,
                    width=width,
                )
            pos += step
            i += 1

    for it in dw.items:
        if isinstance(it, Poly):
            if it.fill:
                if it.holes:
                    mask = Image.new("L", (w, h), 0)
                    md = ImageDraw.Draw(mask)
                    md.polygon([P(p) for p in it.pts], fill=255)
                    for hole in it.holes:
                        md.polygon([P(p) for p in hole], fill=0)
                    img.paste(it.fill, (0, 0, w, h), mask)
                else:
                    dr.polygon([P(p) for p in it.pts], fill=it.fill)
            if it.pen is not None:
                for ring in [it.pts, *it.holes]:
                    for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
                        seg(a, b, it.pen)
        elif isinstance(it, Line):
            seg(it.a, it.b, it.pen)
        elif isinstance(it, Circle):
            cx, cy = P(it.c)
            rr = it.r * scale
            dr.ellipse(
                [cx - rr, cy - rr, cx + rr, cy + rr],
                fill=it.fill,
                outline=it.pen.color,
                width=max(1, round(it.pen.width * scale)),
            )
        elif isinstance(it, Arc):
            cx, cy = P(it.c)
            rr = it.r * scale
            # PIL angles run clockwise from +x in image coordinates
            dr.arc(
                [cx - rr, cy - rr, cx + rr, cy + rr],
                start=-it.a1,
                end=-it.a0,
                fill=it.pen.color,
                width=max(1, round(it.pen.width * scale)),
            )
        else:
            px = max(6 if dw.sheet is not None else 9, round(it.size * scale))
            f = font(px, it.bold)
            x, y = P(it.at)
            for i, line in enumerate(it.text.split("\n")):
                anchor = {"middle": "ms", "start": "ls", "end": "rs"}[it.anchor]
                if it.rot:
                    _turned_text(img, (x, y + i * px * 1.2), line, f, px, it)
                else:
                    dr.text((x, y + i * px * 1.2), line, fill=it.color, font=f, anchor=anchor)
    if dw.sheet is None:
        dr.text((8, h - 22), dw.title, fill="black", font=font(14, False))
    img.save(path)
    return w, h


def _turned_text(
    img: "Image.Image",
    at: Pt,
    line: str,
    f: "ImageFont.FreeTypeFont | ImageFont.ImageFont",
    size: int,
    it: Text,
) -> None:
    """Draw text turned by it.rot degrees so that its baseline anchor lands on `at`."""
    from PIL import Image, ImageDraw

    width = f.getlength(line)
    pad = 2
    layer = Image.new("L", (round(width) + 2 * pad, round(size * 1.6) + 2 * pad), 0)
    base = pad + round(size * 1.15)
    ImageDraw.Draw(layer).text((pad, base), line, fill=255, font=f, anchor="ls")
    k = {"start": 0.0, "middle": 0.5, "end": 1.0}[it.anchor]
    ax, ay = pad + width * k, float(base)
    turned = layer.rotate(it.rot, expand=True, resample=Image.Resampling.BICUBIC)
    th = math.radians(it.rot)
    dx, dy = ax - layer.width / 2, ay - layer.height / 2
    # rotating counter-clockwise on screen, with y pointing down
    rx = dx * math.cos(th) + dy * math.sin(th)
    ry = -dx * math.sin(th) + dy * math.cos(th)
    px, py = turned.width / 2 + rx, turned.height / 2 + ry
    img.paste(it.color, (round(at[0] - px), round(at[1] - py)), turned)

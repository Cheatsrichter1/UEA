"""DXF writer for a Drawing (ezdxf, MIT).

Model space in millimetres (INSUNITS: millimetre, what DXF readers assume), the items on layers
by their name, colours on the layer. Line weights follow the pen widths on paper when the drawing
is a sheet; dashes become linetypes. The sheet frame and title block are ordinary items of the
drawing, at the scale of the sheet, so the file plots as it is at 1:scale.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false, reportPrivateImportUsage=false

import math
from pathlib import Path

import ezdxf
from ezdxf import bbox, units, zoom
from ezdxf.colors import RGB
from ezdxf.document import Drawing as DxfDoc
from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts.layout import Modelspace

from uea.export.drawing import Arc, Circle, Drawing, Line, Pen, Poly, Pt, Text

LINE_WEIGHTS = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120)
"""The line weights DXF knows, in hundredths of a mm (up to 1.2 mm)."""
ALIGN = {
    "start": TextEntityAlignment.LEFT,
    "middle": TextEntityAlignment.CENTER,
    "end": TextEntityAlignment.RIGHT,
}


def rgb(color: str) -> RGB:
    c = color.lstrip("#")
    return RGB(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


K = 1000.0
"""Millimetres per plan metre."""


def P(p: Pt) -> Pt:
    return (p[0] * K, p[1] * K)


class _Writer:
    def __init__(self, dw: Drawing) -> None:
        self.dw = dw
        self.doc: DxfDoc = ezdxf.new("R2010", setup=True)
        self.doc.units = units.MM
        self.doc.header["$LWDISPLAY"] = 1
        self.doc.styles.add("UEA", font="arial.ttf")
        self.doc.styles.add("UEA-Bold", font="arialbd.ttf")
        self.msp: Modelspace = self.doc.modelspace()
        self.layers: set[str] = {"0"}
        self.dashes: dict[tuple[float, ...], str] = {}

    def layer(self, name: str, color: str | None = None) -> str:
        if name not in self.layers:
            self.layers.add(name)
            lay = self.doc.layers.add(name)
            if color is not None:
                lay.rgb = rgb(color)
        return name

    def weight(self, pen: Pen) -> int | None:
        """The DXF line weight of a pen on paper; none for a drawing without a sheet."""
        if self.dw.sheet is None:
            return None
        hundredths = self.dw.sheet.mm(pen.width) * 100
        return min(LINE_WEIGHTS, key=lambda w: abs(w - hundredths))

    def linetype(self, dash: tuple[float, ...]) -> str:
        if not dash:
            return "CONTINUOUS"
        if dash not in self.dashes:
            name = f"UEA-{len(self.dashes) + 1}"
            seq = list(dash) if len(dash) % 2 == 0 else [*dash, *dash]
            pattern = [sum(seq) * K]
            for i, v in enumerate(seq):
                pattern.append((v if i % 2 == 0 else -v) * K)
            self.doc.linetypes.add(name, pattern=pattern, description=name)
            self.dashes[dash] = name
        return self.dashes[dash]

    def attribs(self, layer: str, pen: Pen | None = None) -> dict[str, object]:
        out: dict[str, object] = {"layer": self.layer(layer)}
        if pen is not None:
            out["true_color"] = ezdxf.colors.rgb2int(rgb(pen.color))
            lw = self.weight(pen)
            if lw is not None:
                out["lineweight"] = lw
            if pen.dash:
                out["linetype"] = self.linetype(pen.dash)
        return out

    def poly(self, it: Poly) -> None:
        if it.fill is not None:
            hatch = self.msp.add_hatch(dxfattribs={"layer": self.layer(it.layer)})
            hatch.set_solid_fill(rgb=rgb(it.fill))
            hatch.paths.add_polyline_path([P(q) for q in it.pts], is_closed=True)
            for hole in it.holes:
                hatch.paths.add_polyline_path([P(q) for q in hole], is_closed=True)
        if it.pen is not None:
            for ring in [it.pts, *it.holes]:
                self.msp.add_lwpolyline(
                    [P(q) for q in ring], close=True, dxfattribs=self.attribs(it.layer, it.pen)
                )

    def text(self, it: Text) -> None:
        th = math.radians(it.rot)
        down = (math.sin(th), -math.cos(th))
        for i, line in enumerate(it.text.split("\n")):
            at = P((it.at[0] + down[0] * i * it.size * 1.2, it.at[1] + down[1] * i * it.size * 1.2))
            attribs: dict[str, object] = {
                "layer": self.layer(it.layer),
                "height": it.size * K,
                "style": "UEA-Bold" if it.bold else "UEA",
                "rotation": it.rot,
                "true_color": ezdxf.colors.rgb2int(rgb(it.color)),
            }
            self.msp.add_text(line, dxfattribs=attribs).set_placement(at, align=ALIGN[it.anchor])

    def write(self, path: Path, colors: dict[str, str]) -> dict[str, int]:
        for name, color in colors.items():
            self.layer(name, color)
        counts: dict[str, int] = {}
        for it in self.dw.items:
            kind = type(it).__name__
            counts[kind] = counts.get(kind, 0) + 1
            if isinstance(it, Poly):
                self.poly(it)
            elif isinstance(it, Line):
                self.msp.add_line(P(it.a), P(it.b), dxfattribs=self.attribs(it.layer, it.pen))
            elif isinstance(it, Arc):
                self.msp.add_arc(
                    P(it.c), it.r * K, it.a0, it.a1, dxfattribs=self.attribs(it.layer, it.pen)
                )
            elif isinstance(it, Circle):
                self.msp.add_circle(P(it.c), it.r * K, dxfattribs=self.attribs(it.layer, it.pen))
                if it.fill is not None:
                    hatch = self.msp.add_hatch(dxfattribs={"layer": self.layer(it.layer)})
                    hatch.set_solid_fill(rgb=rgb(it.fill))
                    hatch.paths.add_edge_path().add_arc(P(it.c), it.r * K, 0, 360)
            else:
                self.text(it)
        zoom.extents(self.msp)
        # the extents in the header: programs that read them to size the view collapse the
        # drawing if they keep their defaults (+-1e20)
        box = bbox.extents(self.msp)
        self.msp.dxf.extmin = tuple(box.extmin)
        self.msp.dxf.extmax = tuple(box.extmax)
        self.doc.saveas(path)
        return counts


def to_dxf(dw: Drawing, path: Path, colors: dict[str, str] | None = None) -> dict[str, int]:
    """Write the drawing; `colors` gives layer name -> colour. Returns the item counts."""
    return _Writer(dw).write(path, colors or {})

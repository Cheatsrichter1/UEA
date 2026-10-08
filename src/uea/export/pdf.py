"""PDF writer for a sheet drawing (reportlab, BSD): one page of the paper size, vector output.

The page is the paper of the drawing's sheet. Pen widths, dashes and text sizes are metres at the
sheet's scale, so they come out in mm on paper. Text is set in Helvetica, which has the German
letters; the drawing builder keeps to Latin-1 characters.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from uea import __version__
from uea.export.drawing import Arc, Circle, Drawing, Line, Pen, Poly, Pt, Sheet, Text

PT_PER_MM = 72 / 25.4


class _Page:
    def __init__(self, dw: Drawing, sheet: Sheet, path: Path) -> None:
        self.dw = dw
        self.sheet = sheet
        w, h = sheet.paper
        self.c = Canvas(str(path), pagesize=(w * PT_PER_MM, h * PT_PER_MM))
        self.c.setTitle(dw.title)
        self.c.setAuthor("UEA")
        self.c.setCreator(f"UEA {__version__}")

    def P(self, p: Pt) -> Pt:
        x0, y0 = self.sheet.origin
        return (self.sheet.mm(p[0] - x0) * PT_PER_MM, self.sheet.mm(p[1] - y0) * PT_PER_MM)

    def L(self, metres: float) -> float:
        return self.sheet.mm(metres) * PT_PER_MM

    def stroke(self, pen: Pen) -> None:
        self.c.setStrokeColor(HexColor(pen.color))
        self.c.setLineWidth(self.L(pen.width))
        self.c.setDash([self.L(d) for d in pen.dash] if pen.dash else [])

    def poly(self, it: Poly) -> None:
        path = self.c.beginPath()
        for ring in [it.pts, *it.holes]:
            x, y = self.P(ring[0])
            path.moveTo(x, y)
            for p in ring[1:]:
                path.lineTo(*self.P(p))
            path.close()
        if it.fill is not None:
            self.c.setFillColor(HexColor(it.fill))
        if it.pen is not None:
            self.stroke(it.pen)
        self.c.drawPath(
            path, stroke=int(it.pen is not None), fill=int(it.fill is not None), fillMode=0
        )

    def arc(self, it: Arc) -> None:
        self.stroke(it.pen)
        cx, cy = self.P(it.c)
        r = self.L(it.r)
        self.c.arc(cx - r, cy - r, cx + r, cy + r, it.a0, (it.a1 - it.a0) % 360)

    def text(self, it: Text) -> None:
        size = self.L(it.size)
        self.c.saveState()
        self.c.translate(*self.P(it.at))
        self.c.rotate(it.rot)
        self.c.setFillColor(HexColor(it.color))
        self.c.setFont("Helvetica-Bold" if it.bold else "Helvetica", size)
        for i, line in enumerate(it.text.split("\n")):
            y = -i * size * 1.2
            if it.anchor == "start":
                self.c.drawString(0, y, line)
            elif it.anchor == "end":
                self.c.drawRightString(0, y, line)
            else:
                self.c.drawCentredString(0, y, line)
        self.c.restoreState()

    def write(self) -> None:
        for it in self.dw.items:
            if isinstance(it, Poly):
                self.poly(it)
            elif isinstance(it, Line):
                self.stroke(it.pen)
                self.c.line(*self.P(it.a), *self.P(it.b))
            elif isinstance(it, Arc):
                self.arc(it)
            elif isinstance(it, Circle):
                self.stroke(it.pen)
                if it.fill is not None:
                    self.c.setFillColor(HexColor(it.fill))
                self.c.circle(*self.P(it.c), self.L(it.r), stroke=1, fill=int(it.fill is not None))
            else:
                self.text(it)
        self.c.showPage()
        self.c.save()


def to_pdf(dw: Drawing, path: Path) -> None:
    """Write the sheet as a one-page PDF."""
    if dw.sheet is None:
        raise ValueError("a PDF needs a drawing on a sheet")
    _Page(dw, dw.sheet, path).write()

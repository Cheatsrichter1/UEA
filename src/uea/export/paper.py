"""What every sheet to print shares (decision 0022): paper sizes, layers, pens, dimension chains,
the frame and the title block that stays unsigned.

Lengths are chosen in mm on paper and turned into plan metres by the sheet's scale, so a pen of
0.35 mm is 0.35 mm at any scale. The floor plan (`sheet.py`) and the section (`section.py`)
are built on `Paper`.
"""

from dataclasses import dataclass
from itertools import pairwise

from shapely.geometry import Polygon

from uea import __version__
from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Pen, Poly, Pt, Sheet, Text

PAPER = {"A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}
FITS = (
    ("A3", 100),
    ("A3", 200),
    ("A2", 100),
    ("A2", 200),
    ("A1", 100),
    ("A1", 200),
    ("A0", 100),
    ("A0", 200),
    ("A0", 500),
)
"""Sheets and scales to try, the first that fits wins."""
LEVEL_DE = {
    "KG": "Kellergeschoss",
    "UG": "Untergeschoss",
    "EG": "Erdgeschoss",
    "OG": "Obergeschoss",
    "DG": "Dachgeschoss",
    "DB": "Dachboden",
}

# layers, with the colour they show in a CAD program (they print black and grey)
L_LB = "A-WAND-TRAG"
L_NLB = "A-WAND-NICHTTRAG"
L_FINISH = "A-WAND-PUTZ"
L_EXISTING = "A-WAND-BESTAND"
L_DEMOLISH = "A-WAND-ABBRUCH"
L_DOOR = "A-TUER"
L_WIN = "A-FENSTER"
L_NICHE = "A-NISCHE"
L_STAIR = "A-TREPPE"
L_VOID = "A-AUSSPARUNG"
L_GRID = "A-RASTER"
L_DIM = "A-BEMASSUNG"
L_TEXT = "A-RAUM-TEXT"
L_FRAME = "A-RAHMEN"
L_BLOCK = "A-SCHRIFTFELD"
L_SLAB = "A-DECKE"
L_ROOF = "A-DACH"
L_TERRAIN = "A-GELAENDE"
L_VIEW = "A-ANSICHT"
L_CUT = "A-SCHNITT"
LAYER_COLORS = {
    L_LB: "#000000",
    L_NLB: "#404040",
    L_FINISH: "#909090",
    L_EXISTING: "#808080",
    L_DEMOLISH: "#c8a000",
    L_DOOR: "#a04000",
    L_WIN: "#2266cc",
    L_NICHE: "#2266cc",
    L_STAIR: "#006060",
    L_VOID: "#707070",
    L_GRID: "#3366aa",
    L_DIM: "#008000",
    L_TEXT: "#000000",
    L_FRAME: "#000000",
    L_BLOCK: "#000000",
    L_SLAB: "#000000",
    L_ROOF: "#802020",
    L_TERRAIN: "#706030",
    L_VIEW: "#606060",
    L_CUT: "#c00000",
}

BLACK = "#000000"
GREY = "#666666"
TOL = 1e-3

# paper sizes in mm
FRAME_LEFT, FRAME_OTHER = 20.0, 10.0
BLOCK_W, BLOCK_H = 185.0, 55.0
DIM_FIRST, DIM_STEP, DIM_TEXT = 10.0, 8.0, 2.0
BUBBLE_R = 4.0
CAPTION = 14.0


def de(v: float, nd: int = 2) -> str:
    """A number the German way: 15,66."""
    return f"{v:.{nd}f}".replace(".", ",")


def dim_text(v: float) -> str:
    """A dimension in m with two or three decimals: 10,49 and 1,135."""
    t = f"{v:.3f}"
    if t.endswith("0"):
        t = t[:-1]
    return t.replace(".", ",")


def height_text(z: float) -> str:
    if abs(z) < 1e-9:
        return "±0,00"
    return ("+" if z > 0 else "-") + dim_text(abs(z))


def text_width(txt: str, h: float) -> float:
    """Width of digits and a comma set in Helvetica at height h."""
    return sum(0.278 if ch in ",." else 0.556 for ch in txt) * h


@dataclass(frozen=True)
class Stand:
    """What a sheet says about the model state it was drawn from."""

    batch: int | None = None
    date: str | None = None
    """ISO date of that batch."""

    def date_de(self) -> str:
        if not self.date:
            return "-"
        y, m, d = self.date[:10].split("-")
        return f"{d}.{m}.{y}"


@dataclass
class Chain:
    kind: str
    """open (openings and piers), walls (wall faces), levels (storeys) or total."""
    pts: list[float]
    """Ascending coordinates along the side."""


def uniq(vals: list[float]) -> list[float]:
    out: list[float] = []
    for v in sorted(vals):
        if not out or v - out[-1] > TOL:
            out.append(v)
    return out


def frame(paper: tuple[float, float]) -> tuple[float, float, float, float]:
    """The frame on the paper: x0, y0, x1, y1 in mm."""
    return (FRAME_LEFT, FRAME_OTHER, paper[0] - FRAME_OTHER, paper[1] - FRAME_OTHER)


def place(
    paper: tuple[float, float],
    w_mm: float,
    h_mm: float,
    extra: float = 0.0,
    strip: float = 0.0,
) -> tuple[float, float] | None:
    """Where a block of w x h mm goes on the paper without touching the title block.

    It is centred in the frame; if that is too close to the title block, in the area above it,
    or in the area to its left. Returns the block's lower-left corner in mm. A legend counts as
    part of the title block: extra mm high on top of it, or a strip of that width mm to its left.
    """
    fx0, fy0, fx1, fy1 = frame(paper)
    tx0, ty1 = fx1 - BLOCK_W - strip, fy0 + BLOCK_H + extra
    for x0, y0, x1, y1 in (
        (fx0, fy0, fx1, fy1),
        (fx0, ty1 + 5, fx1, fy1),
        (fx0, fy0, tx0 - 5, fy1),
    ):
        if w_mm > x1 - x0 or h_mm > y1 - y0:
            continue
        x, y = x0 + (x1 - x0 - w_mm) / 2, y0 + (y1 - y0 - h_mm) / 2
        if x + w_mm <= tx0 or y >= ty1:
            return (x, y)
    return None


def allowance(n: int, bubbles: bool) -> float:
    """Paper space in mm that n dimension chains and the axis bubbles of one side need."""
    return DIM_FIRST + DIM_STEP * (n - 1) + (2 * BUBBLE_R + 6.5 + 6.0 if bubbles else 7.0)


def fit_sheet(
    extent: tuple[float, float, float, float],
    need: dict[str, float],
    caption: float = CAPTION,
    extra: float = 0.0,
    strip: float = 0.0,
    fits: tuple[tuple[str, int], ...] = FITS,
) -> Sheet:
    """The first sheet and scale on which the drawing fits, with `need` mm free on each side.

    extent: x0, y0, x1, y1 of what is drawn, in metres. need: mm on paper beyond the extent on
    the sides S, N, W and E. The caption sits below.
    """
    x0, y0, x1, y1 = extent
    spot: tuple[float, float] = (0.0, 0.0)
    size, scale = fits[-1]
    for size, scale in fits:
        w_mm = (x1 - x0) * 1000 / scale + need["W"] + need["E"]
        h_mm = (y1 - y0) * 1000 / scale + need["S"] + need["N"] + caption
        found = place(PAPER[size], w_mm, h_mm, extra, strip)
        if found is not None:
            spot = found
            break
    else:
        # nothing fits: the largest sheet, above the title block
        _, f_y0, _, _ = frame(PAPER[size])
        spot = (FRAME_LEFT, f_y0 + BLOCK_H + extra + 5)
    # the lower-left corner of the extent on paper
    px, py = spot[0] + need["W"], spot[1] + need["S"] + caption
    return Sheet(size, PAPER[size], scale, (x0 - px * scale / 1000, y0 - py * scale / 1000))


def wall_fill(status: str, lb: bool, umbau: bool) -> tuple[str, str]:
    """Fill colour and layer of a cut wall."""
    if status == "demolish":
        return "#ffd800", L_DEMOLISH
    if status == "existing":
        return ("#707070" if lb else "#b4b4b4"), L_EXISTING
    if umbau:
        return ("#b02020" if lb else "#e08c8c"), (L_LB if lb else L_NLB)
    return ("#1a1a1a" if lb else "#9a9a9a"), (L_LB if lb else L_NLB)


def ring(p: Polygon) -> tuple[list[Pt], list[list[Pt]]]:
    return (
        [(x, y) for x, y in list(p.exterior.coords)[:-1]],
        [[(x, y) for x, y in list(h.coords)[:-1]] for h in p.interiors],
    )


def poly_item(p: Polygon, fill: str | None, pen: Pen | None, layer: str) -> Poly:
    pts, holes = ring(p)
    return Poly(pts, fill, pen, layer, holes)


class Paper:
    """A sheet being drawn: pens and text in mm on paper, dimension chains, frame, title block."""

    def __init__(self, d: Derived, stand: Stand, title: str) -> None:
        self.d = d
        self.g = d.arch
        self.m = d.model
        self.stand = stand
        proj = self.m.of_kind("project")
        self.project = (proj[0].label or proj[0].id) if proj else "UEA"
        self.dw = Drawing(f"{self.project}: {title}")

    @property
    def sh(self) -> Sheet:
        assert self.dw.sheet is not None
        return self.dw.sheet

    def pen(self, mm: float, color: str = BLACK, dash: tuple[float, ...] = ()) -> Pen:
        return Pen(color, self.sh.m(mm), tuple(self.sh.m(x) for x in dash))

    def text(
        self,
        at: Pt,
        txt: str,
        mm: float,
        layer: str,
        *,
        anchor: str = "middle",
        bold: bool = False,
        color: str = BLACK,
        rot: float = 0.0,
    ) -> None:
        self.dw.add(Text(at, txt, self.sh.m(mm), color, anchor, bold, layer, rot))

    # dimensions

    def dimension(
        self, bbox: tuple[float, float, float, float], chains: dict[str, list[Chain]]
    ) -> None:
        """The chains of the sides given. Each chain has its own extension lines, which start at
        the dimension line before it, so no line crosses the numbers of another chain."""
        cx0, cy0, cx1, cy1 = bbox
        edge = {"S": cy0, "N": cy1, "W": cx0, "E": cx1}
        ext = self.pen(0.13)
        for side, cs in chains.items():
            horizontal = side in "SN"
            sign = -1.0 if side in "SW" else 1.0
            prev = edge[side] + sign * self.sh.m(1.5)
            before: set[float] = set()
            for k, chain in enumerate(cs):
                line_at = edge[side] + sign * self.sh.m(DIM_FIRST + DIM_STEP * k)
                end = line_at + sign * self.sh.m(2.0)
                for p in chain.pts:
                    # a point the chain before had already reaches 2 mm beyond its line
                    start = prev + sign * self.sh.m(2.0) if round(p, 3) in before else prev
                    a, b = ((p, start), (p, end)) if horizontal else ((start, p), (end, p))
                    self.dw.add(Line(a, b, ext, L_DIM))
                self.chain(side, chain, line_at)
                prev = line_at
                before = {round(p, 3) for p in chain.pts}

    def chain(self, side: str, chain: Chain, line_at: float) -> None:
        """One chain: the line, a slash at each point and the lengths between the points.

        The numbers stand on the building's side of the line, in the band between this line and
        the one before. A number wider than its segment moves up a row.
        """
        horizontal = side in "SN"
        sh = self.sh
        pts = chain.pts

        def at(along: float, across: float) -> Pt:
            return (along, across) if horizontal else (across, along)

        self.dw.add(Line(at(pts[0], line_at), at(pts[-1], line_at), self.pen(0.13), L_DIM))
        d = sh.m(1.0)
        tick = self.pen(0.35)
        for p in pts:
            self.dw.add(Line(at(p - d, line_at - d), at(p + d, line_at + d), tick, L_DIM))
        rows = [float("-inf")] * 3
        for a, b in pairwise(pts):
            txt = dim_text(b - a)
            half = sh.m(text_width(txt, DIM_TEXT) / 2)
            mid = (a + b) / 2
            row = next((r for r in range(3) if mid - half >= rows[r] + sh.m(0.8)), 2)
            rows[row] = mid + half
            gap = 1.6 + row * (DIM_TEXT + 0.8)
            if side == "N":
                base, rot = line_at - sh.m(gap + DIM_TEXT), 0.0
            elif side == "S":
                base, rot = line_at + sh.m(gap), 0.0
            elif side == "E":
                base, rot = line_at - sh.m(gap), 90.0
            else:
                base, rot = line_at + sh.m(gap + DIM_TEXT), 90.0
            self.text(at(mid, base), txt, DIM_TEXT, L_DIM, rot=rot)

    # frame and title block

    def title_block(
        self, content: str, note: str, number: str, scale_text: str | None = None
    ) -> None:
        """The frame and the title block, which stays unsigned.

        content: what the sheet shows ("Grundriss Erdgeschoss"). note: a small line below it.
        """
        sh = self.sh
        heavy, mid = self.pen(0.7), self.pen(0.35)
        x0, y0, x1, y1 = frame(sh.paper)
        self.rect(x0, y0, x1, y1, heavy, L_FRAME)
        bx, by = x1 - BLOCK_W, y0
        self.rect(bx, by, x1, by + BLOCK_H, heavy, L_BLOCK)
        # the block in mm from its lower-left corner: a strip at the bottom, then two columns
        split = 105.0
        self.seg(bx, by + 10, x1, by + 10, mid)
        self.seg(bx + split, by + 10, bx + split, by + BLOCK_H, mid)
        for y in (22.0, 42.0):
            self.seg(bx, by + y, bx + split, by + y, mid)
        for x in (35.0, 70.0):
            self.seg(bx + x, by + 10, bx + x, by + 22, mid)
        for y in (29.0, 42.0):
            self.seg(bx + split, by + y, x1, by + y, mid)
        self.cell(bx, by + 42, 13, "Bauvorhaben", self.project, 3.5, True, 3.5)
        self.cell(bx, by + 22, 20, "Planinhalt", content, 4.0, True, 9.0)
        self.text(sh.pt(bx + 2, by + 25.5), note, 2.0, L_BLOCK, anchor="start", color=GREY)
        self.cell(bx, by + 10, 12, "Maßstab", scale_text or f"1:{sh.scale}", 3.0, True, 3.0)
        self.cell(bx + 35, by + 10, 12, "Format", sh.size, 3.0, True, 3.0)
        self.cell(bx + 70, by + 10, 12, "Plan-Nr.", number, 3.0, True, 3.0)
        self.cell(bx + split, by + 42, 13, "Bauherr")
        self.cell(bx + split, by + 29, 13, "Planverfasser")
        self.cell(bx + split, by + 10, 19, "Unterschrift")
        batch = f"Batch {self.stand.batch}" if self.stand.batch is not None else "ohne Verlauf"
        self.text(
            sh.pt(bx + 2, by + 3.2),
            "ENTWURF – nicht unterzeichnet",
            2.8,
            L_BLOCK,
            anchor="start",
            bold=True,
        )
        self.text(
            sh.pt(x1 - 2, by + 3.2),
            f"Stand {self.stand.date_de()} · {batch} · UEA {__version__}",
            2.0,
            L_BLOCK,
            anchor="end",
            color=GREY,
        )

    def cell(
        self,
        x: float,
        y: float,
        height: float,
        label: str,
        value: str = "",
        size: float = 2.5,
        bold: bool = False,
        up: float = 2.6,
    ) -> None:
        """A cell of the title block: a small label at its top, a value `up` mm above its bottom.

        x, y: its lower-left corner, in mm on paper.
        """
        sh = self.sh
        self.text(sh.pt(x + 1.5, y + height - 3.2), label, 1.6, L_BLOCK, anchor="start", color=GREY)
        if value:
            self.text(sh.pt(x + 2.0, y + up), value, size, L_BLOCK, anchor="start", bold=bold)

    def rect(self, x0: float, y0: float, x1: float, y1: float, pen: Pen, layer: str) -> None:
        sh = self.sh
        pts = [sh.pt(x0, y0), sh.pt(x1, y0), sh.pt(x1, y1), sh.pt(x0, y1)]
        self.dw.add(Poly(pts, None, pen, layer))

    def seg(self, x0: float, y0: float, x1: float, y1: float, pen: Pen) -> None:
        self.dw.add(Line(self.sh.pt(x0, y0), self.sh.pt(x1, y1), pen, L_BLOCK))

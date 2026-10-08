"""A floor plan as a sheet to print (decision 0022): the plan of one storey on a sheet of paper.

Rohbau plan at Entwurf level: cut walls as filled shapes with real openings, door swings and
window symbols, stairs, room stamps, three dimension chains per side, grid axes with bubbles,
a frame and a title block that stays unsigned. Lengths are chosen in mm on paper and turned into
plan metres by the sheet's scale, so a pen of 0.35 mm is 0.35 mm at any scale.

Not drawn yet: a north arrow (the project has no north direction), windows above the cut plane
as dashed outlines (every opening is drawn as cut), roofs, furniture.
"""

from dataclasses import dataclass
from itertools import pairwise

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from uea import __version__
from uea.derive import Derived
from uea.export.drawing import Arc, Circle, Drawing, Line, Pen, Poly, Pt, Sheet, Text
from uea.export.plan import door_swing
from uea.export.tables import USE_DE
from uea.geom import polys
from uea.packs.arch.geometry import OpeningGeo, WallGeo
from uea.packs.arch.kinds import Room
from uea.packs.project import Grid

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
    """open (openings and piers), walls (wall faces) or total."""
    pts: list[float]
    """Ascending coordinates along the side."""


def _uniq(vals: list[float]) -> list[float]:
    out: list[float] = []
    for v in sorted(vals):
        if not out or v - out[-1] > TOL:
            out.append(v)
    return out


def side_chains(
    d: Derived, walls: list[WallGeo], side: str, bbox: tuple[float, float, float, float]
) -> list[Chain]:
    """The dimension chains of one side of the building, nearest to the building first."""
    cx0, cy0, cx1, cy1 = bbox
    horizontal = side in "SN"
    low = side in "SW"
    edge = {"S": cy0, "N": cy1, "W": cx0, "E": cx1}[side]
    a0, a1 = (cx0, cx1) if horizontal else (cy0, cy1)
    facade_o, cross_o = ("h", "v") if horizontal else ("v", "h")
    facade = [
        w
        for w in walls
        if w.o == facade_o
        and w.ext == ("lo" if low else "hi")
        and abs((w.lo if low else w.hi) - edge) < TOL
    ]
    out: list[Chain] = []
    ids = {w.id for w in facade}
    opening_pts: list[float] = []
    for o in d.arch.openings.values():
        if o.host in ids and o.kind != "niche" and o.status != "demolish":
            opening_pts += [o.lo, o.hi]
    if opening_pts:
        ends = [v for w in facade for v in (w.s0, w.s1)]
        out.append(Chain("open", _uniq([*ends, *opening_pts])))
    # the walls that run into this side: their faces
    inner = edge
    if facade:
        inner = max(w.hi for w in facade) if low else min(w.lo for w in facade)

    def reaches(w: WallGeo) -> bool:
        return w.s0 <= inner + TOL if low else w.s1 >= inner - TOL

    faces = [v for w in walls if w.o == cross_o and reaches(w) for v in (w.lo, w.hi)]
    inside = [v for v in faces if a0 - TOL <= v <= a1 + TOL]
    cross = _uniq([a0, a1, *inside])
    if len(cross) > 2:
        out.append(Chain("walls", cross))
    out.append(Chain("total", [a0, a1]))
    return out


def frame(paper: tuple[float, float]) -> tuple[float, float, float, float]:
    """The frame on the paper: x0, y0, x1, y1 in mm."""
    return (FRAME_LEFT, FRAME_OTHER, paper[0] - FRAME_OTHER, paper[1] - FRAME_OTHER)


def place(paper: tuple[float, float], w_mm: float, h_mm: float) -> tuple[float, float] | None:
    """Where a block of w x h mm goes on the paper without touching the title block.

    It is centred in the frame; if that is too close to the title block, in the area above it,
    or in the area to its left. Returns the block's lower-left corner in mm.
    """
    fx0, fy0, fx1, fy1 = frame(paper)
    tx0, ty1 = fx1 - BLOCK_W, fy0 + BLOCK_H
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


class _Plan:
    """Draws the plan of one storey on a sheet."""

    def __init__(self, d: Derived, level: str, stand: Stand) -> None:
        self.d = d
        self.g = d.arch
        self.m = d.model
        self.level = level
        self.stand = stand
        self.walls = self.g.walls_on(level, active=False)
        self.live = [w for w in self.walls if w.active]
        self.openings = [o for o in self.g.openings.values() if o.level == level]
        slab = self.g.slab_on(level)
        self.status_set = {w.status for w in self.walls} | {o.status for o in self.openings}
        if slab is not None:
            self.status_set.add(slab.status)
        self.umbau = bool(self.status_set - {"new"})
        proj = self.m.of_kind("project")
        self.project = (proj[0].label or proj[0].id) if proj else "UEA"
        el = self.m[level]
        self.level_name = el.label or LEVEL_DE.get(level, level)
        self.dw = Drawing(f"{self.project}: Grundriss {self.level_name}")

    # ---------- layout ----------

    def bbox(self) -> tuple[float, float, float, float] | None:
        if not self.live:
            return None
        cores = unary_union([w.core for w in self.live])
        x0, y0, x1, y1 = cores.bounds
        return (x0, y0, x1, y1)

    def grids(self, bbox: tuple[float, float, float, float]) -> list[Grid]:
        cx0, cy0, cx1, cy1 = bbox
        out: list[Grid] = []
        for el in self.m.of_kind("grid"):
            assert isinstance(el, Grid)
            lo, hi = (cx0, cx1) if el.axis == "x" else (cy0, cy1)
            if lo - TOL <= el.coord <= hi + TOL:
                out.append(el)
        return out

    def allowance(self, n: int, bubbles: bool) -> float:
        """Paper space in mm that the chains and the axis bubbles of one side need."""
        return DIM_FIRST + DIM_STEP * (n - 1) + (2 * BUBBLE_R + 6.5 + 6.0 if bubbles else 7.0)

    def fit(
        self, bbox: tuple[float, float, float, float], chains: dict[str, list[Chain]], bubbles: str
    ) -> Sheet:
        """Choose the first sheet and scale on which the plan with its chains fits."""
        cx0, cy0, cx1, cy1 = bbox
        need = {s: self.allowance(len(chains[s]), s in bubbles) for s in "SNWE"}
        spot: tuple[float, float] = (0.0, 0.0)
        size, scale = FITS[-1]
        for size, scale in FITS:
            w_mm = (cx1 - cx0) * 1000 / scale + need["W"] + need["E"]
            h_mm = (cy1 - cy0) * 1000 / scale + need["S"] + need["N"] + CAPTION
            found = place(PAPER[size], w_mm, h_mm)
            if found is not None:
                spot = found
                break
        else:
            # nothing fits: the largest sheet, above the title block
            _, f_y0, _, _ = frame(PAPER[size])
            spot = (FRAME_LEFT, f_y0 + BLOCK_H + 5)
        # the building's lower-left corner on paper
        px, py = spot[0] + need["W"], spot[1] + need["S"] + CAPTION
        return Sheet(size, PAPER[size], scale, (cx0 - px * scale / 1000, cy0 - py * scale / 1000))

    # ---------- the plan ----------

    def draw(self) -> Drawing | None:
        bbox = self.bbox()
        if bbox is None:
            return None
        chains = {s: side_chains(self.d, self.live, s, bbox) for s in "SNWE"}
        grids = self.grids(bbox)
        bubbles = ("S" if any(g.axis == "x" for g in grids) else "") + (
            "W" if any(g.axis == "y" for g in grids) else ""
        )
        self.sh = self.dw.sheet = self.fit(bbox, chains, bubbles)
        self.cut_all = unary_union([w.poly for w in self.live])
        # a stair with room for its label under it
        self.stair_zone = unary_union(
            [s.poly.buffer(self.sh.m(5.0)) for s in self.g.stairs.values() if s.level == self.level]
        )
        self.walls_and_openings()
        self.stairs_and_voids()
        self.dimension(bbox, chains)
        self.axes(bbox, grids, chains)
        self.rooms()
        self.caption(bbox, chains, bubbles)
        self.frame()
        return self.dw

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

    # walls

    def fill(self, status: str, lb: bool) -> tuple[str, str]:
        """Fill colour and layer of a wall."""
        if status == "demolish":
            return "#ffd800", L_DEMOLISH
        if status == "existing":
            return ("#707070" if lb else "#b4b4b4"), L_EXISTING
        if self.umbau:
            return ("#b02020" if lb else "#e08c8c"), (L_LB if lb else L_NLB)
        return ("#1a1a1a" if lb else "#9a9a9a"), (L_LB if lb else L_NLB)

    def cut_shape(self, w: WallGeo) -> BaseGeometry | None:
        """What of the wall is cut: raw walls give way to the walls they run into."""
        cores = unary_union([o.core for o in self.live if o is not w and w.raw])
        poly = w.poly.difference(cores) if w.raw else w.poly
        return poly if not poly.is_empty else None

    def cutters(self) -> list[Polygon]:
        """The openings and niches, through the whole wall with its finishes."""
        out: list[Polygon] = []
        for o in self.openings:
            w = self.g.walls[o.host]
            if not w.active or o.status == "demolish":
                continue
            if o.kind == "niche":
                f = o.depth
                lo_f, hi_f = w.lo - w.finish("lo"), w.hi + w.finish("hi")
                band = (w.hi - f, hi_f) if o.face == "hi" else (lo_f, w.lo + f)
            else:
                band = (w.lo - w.finish("lo"), w.hi + w.finish("hi"))
            out.append(
                Polygon(
                    [
                        w.plan_point(o.lo, band[0]),
                        w.plan_point(o.hi, band[0]),
                        w.plan_point(o.hi, band[1]),
                        w.plan_point(o.lo, band[1]),
                    ]
                )
            )
        return out

    def walls_and_openings(self) -> None:
        cut = unary_union(self.cutters()) if self.openings else Polygon()
        # finishes first, under the cut walls
        bands: list[BaseGeometry] = []
        for w in self.live:
            for side in ("lo", "hi"):
                f = w.finish(side)
                if f > 0:
                    band = w.box(w.lo - f, w.lo) if side == "lo" else w.box(w.hi, w.hi + f)
                    if w.raw:
                        band = band.difference(
                            unary_union([o.core for o in self.live if o is not w])
                        )
                    bands.append(band)
        cores = unary_union([w.core for w in self.live])
        finish = unary_union(bands).difference(cores).difference(cut) if bands else Polygon()
        for p in polys(finish, 0.0):
            self.dw.add(_poly(p, "#dcdcd4", None, L_FINISH))
        # the cut walls by status and load bearing, each group takes what the others left
        taken: BaseGeometry = Polygon()
        groups = [
            (status, lb)
            for status in ("new", "existing", "demolish")
            for lb in (True, False)
            if any(w.status == status and w.lb == lb for w in self.walls)
        ]
        pen = self.pen(0.35)
        for status, lb in groups:
            shapes = [
                s
                for w in self.walls
                if w.status == status and w.lb == lb and (s := self.cut_shape(w)) is not None
            ]
            if not shapes:
                continue
            area = unary_union(shapes)
            if status != "demolish":
                area = area.difference(cut)
            area = area.difference(taken)
            taken = unary_union([taken, area])
            fill, layer = self.fill(status, lb)
            line = self.pen(0.25, BLACK, (0.6, 0.4)) if status == "demolish" else pen
            for p in polys(area, 0.0):
                self.dw.add(_poly(p, fill, line, layer))
        for o in self.openings:
            if o.kind == "win" and self.g.walls[o.host].active:
                self.window(o)
            elif o.kind == "door" and self.g.walls[o.host].active and o.status != "demolish":
                self.door(o)

    def window(self, o: OpeningGeo) -> None:
        """The frame and glass of a window, or of a door without a swinging leaf."""
        w = self.g.walls[o.host]
        pen = self.pen(0.18)
        layer = L_WIN if o.kind == "win" else L_DOOR
        for c in (w.lo, w.mid, w.hi):
            self.dw.add(Line(w.plan_point(o.lo, c), w.plan_point(o.hi, c), pen, layer))

    def door(self, o: OpeningGeo) -> None:
        sw = door_swing(self.d, o)
        if sw is None:
            self.window(o)
            return
        self.dw.add(Line(sw.hinge, sw.open_end, self.pen(0.25), L_DOOR))
        self.dw.add(Arc(sw.hinge, o.width, sw.a0, sw.a1, self.pen(0.13), L_DOOR))

    # stairs and voids

    def stairs_and_voids(self) -> None:
        g = self.g
        thin, edge, dash = self.pen(0.13), self.pen(0.25), self.pen(0.18, GREY, (1.5, 1.0))
        slab = g.slab_on(self.level)
        for v in g.voids.values():
            if slab is None or v.slab != slab.id:
                continue
            pts, _ = _ring(v.poly)
            self.dw.add(Poly(pts, None, dash, L_VOID))
            x0, y0, x1, y1 = v.poly.bounds
            self.dw.add(Line((x0, y0), (x1, y1), thin, L_VOID))
            self.dw.add(Line((x0, y1), (x1, y0), thin, L_VOID))
        for s in g.stairs.values():
            if s.to == self.level:
                self.dw.add(Poly(_ring(s.poly)[0], None, dash, L_STAIR))
            if s.level != self.level:
                continue
            self.dw.add(Poly(_ring(s.poly)[0], None, edge, L_STAIR))
            for ln in s.lines:
                a, b = ln.coords[0], ln.coords[-1]
                self.dw.add(Line((a[0], a[1]), (b[0], b[1]), thin, L_STAIR))
            walk = s.walk
            for p0, p1 in pairwise(walk):
                self.dw.add(Line(p0, p1, edge, L_STAIR))
            self.dw.add(Circle(walk[0], self.sh.m(0.8), edge, BLACK, L_STAIR))
            p0, p1 = walk[-2], walk[-1]
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            ln_ = (dx * dx + dy * dy) ** 0.5
            ux, uy = dx / ln_, dy / ln_
            tip = self.sh.m(2.5)
            for k in (-1, 1):
                b = (p1[0] - tip * ux - k * tip * 0.4 * uy, p1[1] - tip * uy + k * tip * 0.4 * ux)
                self.dw.add(Line(p1, b, edge, L_STAIR))
            label = f"{s.n} Stg. {de(s.riser * 100, 1)}/{de(s.tread * 100, 1)}"
            x0, y0, x1, y1 = s.poly.bounds
            cx = (x0 + x1) / 2
            half = self.sh.m(text_width(label, 1.8) / 2)
            below = (cx, y0 - self.sh.m(3.2))
            above = (cx, y1 + self.sh.m(1.5))
            spot = below
            for cand in (below, above):
                box = Polygon(
                    [
                        (cand[0] - half, cand[1]),
                        (cand[0] + half, cand[1]),
                        (cand[0] + half, cand[1] + self.sh.m(1.8)),
                        (cand[0] - half, cand[1] + self.sh.m(1.8)),
                    ]
                )
                if not box.intersects(self.cut_all):
                    spot = cand
                    break
            self.text(spot, label, 1.8, L_TEXT, color=GREY)

    # rooms

    def rooms(self) -> None:
        for rg in self.g.rooms.values():
            if rg.level != self.level:
                continue
            el = self.m[rg.id]
            assert isinstance(el, Room)
            # the stamp stands where no stair is
            free = rg.fin.difference(self.stair_zone) if not self.stair_zone.is_empty else rg.fin
            if free.is_empty or free.area < 0.25 * rg.fin.area:
                free = rg.fin
            at = free.centroid
            if not free.contains(at):
                at = free.representative_point()
            x, y = at.x, at.y
            name = el.label or USE_DE[el.use]
            self.text((x, y + self.sh.m(2.6)), rg.id, 1.8, L_TEXT, color=GREY)
            self.text((x, y - self.sh.m(0.3)), name, 2.5, L_TEXT, bold=True)
            self.text((x, y - self.sh.m(3.2)), f"{de(rg.area_fin)} m²", 2.0, L_TEXT)

    # dimensions

    def dimension(
        self, bbox: tuple[float, float, float, float], chains: dict[str, list[Chain]]
    ) -> None:
        """The chains of all four sides. Each chain has its own extension lines, which start at
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

    # axes

    def axes(
        self,
        bbox: tuple[float, float, float, float],
        grids: list[Grid],
        chains: dict[str, list[Chain]],
    ) -> None:
        cx0, cy0, _, _ = bbox
        sh = self.sh
        pen = self.pen(0.13, BLACK, (6.0, 1.5, 1.0, 1.5))
        ring = self.pen(0.18)
        r = sh.m(BUBBLE_R)
        for el in grids:
            label = el.label or el.id
            if el.axis == "x":
                far = self.allowance(len(chains["S"]), True) - 2 * BUBBLE_R - 6.0
                yc = cy0 - sh.m(far + BUBBLE_R)
                self.dw.add(Line((el.coord, yc + r), (el.coord, cy0 - sh.m(1.5)), pen, L_GRID))
                c = (el.coord, yc)
            else:
                far = self.allowance(len(chains["W"]), True) - 2 * BUBBLE_R - 6.0
                xc = cx0 - sh.m(far + BUBBLE_R)
                self.dw.add(Line((xc + r, el.coord), (cx0 - sh.m(1.5), el.coord), pen, L_GRID))
                c = (xc, el.coord)
            self.dw.add(Circle(c, r, ring, None, L_GRID))
            self.text((c[0], c[1] - sh.m(1.1)), label, 3.0, L_GRID, bold=True)

    # caption, frame, title block

    def caption(
        self,
        bbox: tuple[float, float, float, float],
        chains: dict[str, list[Chain]],
        bubbles: str,
    ) -> None:
        sh = self.sh
        cx0, cy0, cx1, _ = bbox
        y = cy0 - sh.m(self.allowance(len(chains["S"]), "S" in bubbles) + 5.0)
        self.text(
            ((cx0 + cx1) / 2, y),
            f"Grundriss {self.level_name}   M 1:{sh.scale}",
            3.5,
            L_TEXT,
            bold=True,
        )

    def frame(self) -> None:
        """The frame and the title block, which stays unsigned."""
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
        lv = self.g.levels[self.level]
        nr = f"A-{self.g.level_order().index(self.level) + 1:02d}"
        self.cell(bx, by + 42, 13, "Bauvorhaben", self.project, 3.5, True, 3.5)
        self.cell(bx, by + 22, 20, "Planinhalt", f"Grundriss {self.level_name}", 4.0, True, 9.0)
        okff = f"OKFF {height_text(lv.z)} m"
        if abs(lv.z) > 1e-9:
            okff += " (±0,00 = OKFF des Erdgeschosses)"
        self.text(sh.pt(bx + 2, by + 25.5), okff, 2.0, L_BLOCK, anchor="start", color=GREY)
        self.cell(bx, by + 10, 12, "Maßstab", f"1:{sh.scale}", 3.0, True, 3.0)
        self.cell(bx + 35, by + 10, 12, "Format", sh.size, 3.0, True, 3.0)
        self.cell(bx + 70, by + 10, 12, "Plan-Nr.", nr, 3.0, True, 3.0)
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


def _ring(p: Polygon) -> tuple[list[Pt], list[list[Pt]]]:
    return (
        [(x, y) for x, y in list(p.exterior.coords)[:-1]],
        [[(x, y) for x, y in list(h.coords)[:-1]] for h in p.interiors],
    )


def _poly(p: Polygon, fill: str | None, pen: Pen | None, layer: str) -> Poly:
    pts, holes = _ring(p)
    return Poly(pts, fill, pen, layer, holes)


def sheet_plan(d: Derived, level: str, stand: Stand | None = None) -> Drawing | None:
    """The floor plan of a storey on a sheet; none if the storey has no walls."""
    return _Plan(d, level, stand or Stand()).draw()

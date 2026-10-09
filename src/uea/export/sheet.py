"""A floor plan as a sheet to print (decision 0022): the plan of one storey on a sheet of paper.

Rohbau plan at Entwurf level: cut walls as filled shapes with real openings, door swings and
window symbols, stairs, room stamps, three dimension chains per side, grid axes with bubbles,
the cut lines of the sections, a frame and a title block that stays unsigned. Lengths are chosen
in mm on paper and turned into plan metres by the sheet's scale (`paper.py`).

Not drawn yet: a north arrow (the project has no north direction), windows above the cut plane
as dashed outlines (every opening is drawn as cut), roofs, furniture.
"""

from itertools import pairwise

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from uea.derive import Derived
from uea.export.drawing import Arc, Circle, Drawing, Line, Poly
from uea.export.paper import (
    BLACK,
    BUBBLE_R,
    GREY,
    L_CUT,
    L_DOOR,
    L_FINISH,
    L_GRID,
    L_STAIR,
    L_TEXT,
    L_VOID,
    L_WIN,
    LEVEL_DE,
    TOL,
    Chain,
    Paper,
    Stand,
    allowance,
    de,
    fit_sheet,
    height_text,
    poly_item,
    ring,
    text_width,
    uniq,
    wall_fill,
)
from uea.export.plan import door_swing
from uea.export.tables import USE_DE
from uea.geom import polys
from uea.packs.arch.geometry import OpeningGeo, SectionGeo, WallGeo
from uea.packs.arch.kinds import Room
from uea.packs.project import Grid

MARK = 14.0
"""Paper space in mm that the end of a section line needs beyond the dimension chains."""


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
        out.append(Chain("open", uniq([*ends, *opening_pts])))
    # the walls that run into this side: their faces
    inner = edge
    if facade:
        inner = max(w.hi for w in facade) if low else min(w.lo for w in facade)

    def reaches(w: WallGeo) -> bool:
        return w.s0 <= inner + TOL if low else w.s1 >= inner - TOL

    faces = [v for w in walls if w.o == cross_o and reaches(w) for v in (w.lo, w.hi)]
    inside = [v for v in faces if a0 - TOL <= v <= a1 + TOL]
    cross = uniq([a0, a1, *inside])
    if len(cross) > 2:
        out.append(Chain("walls", cross))
    out.append(Chain("total", [a0, a1]))
    return out


class _Plan(Paper):
    """Draws the plan of one storey on a sheet."""

    def __init__(self, d: Derived, level: str, stand: Stand) -> None:
        el = d.model[level]
        self.level = level
        self.level_name = el.label or LEVEL_DE.get(level, level)
        super().__init__(d, stand, f"Grundriss {self.level_name}")
        self.walls = self.g.walls_on(level, active=False)
        self.live = [w for w in self.walls if w.active]
        self.openings = [o for o in self.g.openings.values() if o.level == level]
        slab = self.g.slab_on(level)
        self.status_set = {w.status for w in self.walls} | {o.status for o in self.openings}
        if slab is not None:
            self.status_set.add(slab.status)
        self.umbau = bool(self.status_set - {"new"})

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

    def marked(self, bbox: tuple[float, float, float, float]) -> list[SectionGeo]:
        """The sections whose cut line crosses this storey."""
        cx0, cy0, cx1, cy1 = bbox
        out: list[SectionGeo] = []
        for sc in sorted(self.g.sections.values(), key=lambda k: k.id):
            lo, hi = (cx0, cx1) if sc.axis == "x" else (cy0, cy1)
            if lo - TOL <= sc.coord <= hi + TOL:
                out.append(sc)
        return out

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
        cuts = self.marked(bbox)
        marks = {s for sc in cuts for s in ("SN" if sc.axis == "x" else "WE")}
        need = {
            s: allowance(len(chains[s]), s in bubbles) + (MARK if s in marks else 0.0)
            for s in "SNWE"
        }
        self.dw.sheet = fit_sheet(bbox, need)
        self.cut_all = unary_union([w.poly for w in self.live])
        # a stair with room for its label under it
        self.stair_zone = unary_union(
            [s.poly.buffer(self.sh.m(5.0)) for s in self.g.stairs.values() if s.level == self.level]
        )
        self.walls_and_openings()
        self.stairs_and_voids()
        self.dimension(bbox, chains)
        self.axes(bbox, grids, chains)
        self.section_marks(bbox, cuts, chains, bubbles)
        self.rooms()
        self.caption(bbox, need)
        lv = self.g.levels[self.level]
        okff = f"OKFF {height_text(lv.z)} m"
        if abs(lv.z) > 1e-9:
            okff += " (±0,00 = OKFF des Erdgeschosses)"
        nr = f"A-{self.g.level_order().index(self.level) + 1:02d}"
        self.title_block(f"Grundriss {self.level_name}", okff, nr)
        return self.dw

    # walls

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
            self.dw.add(poly_item(p, "#dcdcd4", None, L_FINISH))
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
            fill, layer = wall_fill(status, lb, self.umbau)
            line = self.pen(0.25, BLACK, (0.6, 0.4)) if status == "demolish" else pen
            for p in polys(area, 0.0):
                self.dw.add(poly_item(p, fill, line, layer))
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
            pts, _ = ring(v.poly)
            self.dw.add(Poly(pts, None, dash, L_VOID))
            x0, y0, x1, y1 = v.poly.bounds
            self.dw.add(Line((x0, y0), (x1, y1), thin, L_VOID))
            self.dw.add(Line((x0, y1), (x1, y0), thin, L_VOID))
        for s in g.stairs.values():
            if s.to == self.level:
                self.dw.add(Poly(ring(s.poly)[0], None, dash, L_STAIR))
            if s.level != self.level:
                continue
            self.dw.add(Poly(ring(s.poly)[0], None, edge, L_STAIR))
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
                far = allowance(len(chains["S"]), True) - 2 * BUBBLE_R - 6.0
                yc = cy0 - sh.m(far + BUBBLE_R)
                self.dw.add(Line((el.coord, yc + r), (el.coord, cy0 - sh.m(1.5)), pen, L_GRID))
                c = (el.coord, yc)
            else:
                far = allowance(len(chains["W"]), True) - 2 * BUBBLE_R - 6.0
                xc = cx0 - sh.m(far + BUBBLE_R)
                self.dw.add(Line((xc + r, el.coord), (cx0 - sh.m(1.5), el.coord), pen, L_GRID))
                c = (xc, el.coord)
            self.dw.add(Circle(c, r, ring, None, L_GRID))
            self.text((c[0], c[1] - sh.m(1.1)), label, 3.0, L_GRID, bold=True)

    # section lines

    def section_marks(
        self,
        bbox: tuple[float, float, float, float],
        cuts: list[SectionGeo],
        chains: dict[str, list[Chain]],
        bubbles: str,
    ) -> None:
        """The cut line of each section through this storey: thick through the building, and at
        both ends beyond the dimension chains a bold stub, an arrow in the viewing direction and
        the name of the section."""
        sh = self.sh
        cx0, cy0, cx1, cy1 = bbox
        edge = {"S": cy0, "N": cy1, "W": cx0, "E": cx1}
        inside = self.pen(0.5, BLACK, (8.0, 1.5, 1.0, 1.5))
        bold, shaft = self.pen(0.7), self.pen(0.35)
        for sc in cuts:
            horizontal = sc.axis == "y"  # the line runs along x
            ends = ("W", "E") if horizontal else ("S", "N")
            lo, hi = (cx0, cx1) if horizontal else (cy0, cy1)
            a, b = lo - sh.m(2.5), hi + sh.m(2.5)
            pts = ((a, sc.coord), (b, sc.coord)) if horizontal else ((sc.coord, a), (sc.coord, b))
            self.dw.add(Line(pts[0], pts[1], inside, L_CUT))
            vx, vy = sc.view
            for side in ends:
                sign = -1.0 if side in "SW" else 1.0
                reach = allowance(len(chains[side]), side in bubbles) + 1.0
                near = edge[side] + sign * sh.m(reach)
                far = near + sign * sh.m(7.0)
                p0 = (near, sc.coord) if horizontal else (sc.coord, near)
                p1 = (far, sc.coord) if horizontal else (sc.coord, far)
                self.dw.add(Line(p0, p1, bold, L_CUT))
                tip = (p1[0] + vx * sh.m(7.0), p1[1] + vy * sh.m(7.0))
                self.dw.add(Line(p1, tip, shaft, L_CUT))
                # the arrow head: 3 mm long, 2 mm wide
                h, w = sh.m(3.0), sh.m(1.0)
                base = (tip[0] - vx * h, tip[1] - vy * h)
                head = [
                    tip,
                    (base[0] - vy * w, base[1] + vx * w),
                    (base[0] + vy * w, base[1] - vx * w),
                ]
                self.dw.add(Poly(head, BLACK, None, L_CUT))
                # the name beyond the stub
                out = far + sign * sh.m(2.5)
                if horizontal:
                    anchor = "end" if side == "W" else "start"
                    at = (out, sc.coord - sh.m(1.2))
                else:
                    anchor = "middle"
                    at = (sc.coord, out if side == "N" else out - sh.m(3.5))
                self.text(at, sc.id, 3.5, L_CUT, anchor=anchor, bold=True)

    # caption

    def caption(self, bbox: tuple[float, float, float, float], need: dict[str, float]) -> None:
        sh = self.sh
        cx0, cy0, cx1, _ = bbox
        y = cy0 - sh.m(need["S"] + 5.0)
        self.text(
            ((cx0 + cx1) / 2, y),
            f"Grundriss {self.level_name}   M 1:{sh.scale}",
            3.5,
            L_TEXT,
            bold=True,
        )


def sheet_plan(d: Derived, level: str, stand: Stand | None = None) -> Drawing | None:
    """The floor plan of a storey on a sheet; none if the storey has no walls."""
    return _Plan(d, level, stand or Stand()).draw()

"""A section as a sheet to print (decision 0023): a vertical cut through the building.

The drawing's x is the position across the cut to the right (u) and its y the height (z), both in
metres. Everything is found by cutting the plan with the cut plane: walls, slabs, the roof and the
stairs become filled shapes with their layers, openings become gaps, rooms get a label with their
clear height. Behind the cut the walls, windows, roof planes and stairs are drawn as thin outlines
with the hidden lines taken out (nearest first, each shape loses what the nearer ones cover).

Not drawn yet: the stair rail, niches seen behind the cut, slabs and floors seen from the side,
footings, a section that jogs.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise

from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as SPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from uea.derive import Derived
from uea.export.drawing import Circle, Drawing, Line, Poly, Pt
from uea.export.paper import (
    BLACK,
    BUBBLE_R,
    GREY,
    L_DIM,
    L_DOOR,
    L_FINISH,
    L_GRID,
    L_ROOF,
    L_SLAB,
    L_STAIR,
    L_TERRAIN,
    L_TEXT,
    L_VIEW,
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
    text_width,
    uniq,
    wall_fill,
)
from uea.export.tables import USE_DE
from uea.geom import polys
from uea.packs.arch.geometry import (
    LevelGeo,
    OpeningGeo,
    RoofGeo,
    RoomGeo,
    SectionGeo,
    StairGeo,
    StairPartGeo,
    WallGeo,
    roof_pieces,
)
from uea.packs.arch.kinds import Room
from uea.packs.project import Grid, Project

EPS = 1e-4
FINISH_FILL = "#dcdcd4"
STAIR_THICK = 0.17
"""Thickness of a stair's slab square to the flight, in m."""
TERRAIN = 8.0
"""How far the ground line reaches beyond the building, in mm on paper."""
MARK_ARM = 24.0
"""Where the height marks stand left of the building, in mm on paper."""


def lines_of(g: BaseGeometry) -> list[LineString]:
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    parts: Iterable[BaseGeometry] = getattr(g, "geoms", ())
    return [ln for part in parts for ln in lines_of(part)]


def merge(ivs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


@dataclass
class Shape:
    """A filled shape of the cut, in (u, z)."""

    geo: BaseGeometry
    fill: str
    layer: str
    outline: bool = True


@dataclass
class Face:
    """Something behind the cut, in (u, z), with its distance from the cut plane."""

    depth: float
    geo: BaseGeometry
    layer: str
    detail: bool = False
    """A window: draw its glass inside when all of it can be seen."""
    solid: bool = False
    """Labels keep off the whole shape, not only off its outline."""
    fill: str | None = None


@dataclass
class Mark:
    z: float
    text: str


@dataclass
class _Cut:
    """What the cut plane meets, collected before it is drawn."""

    walls: list[Shape] = field(default_factory=list[Shape])
    others: list[Shape] = field(default_factory=list[Shape])
    windows: list[tuple[float, float, float, float]] = field(
        default_factory=list[tuple[float, float, float, float]]
    )
    """Windows in the cut: u0, u1, z0, z1."""
    levels: set[str] = field(default_factory=set[str])
    gaps: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])
    """z0, z1 of each opening in the cut."""
    faces: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])
    """u0, u1 of each cut wall core."""
    roofs: dict[str, RoofGeo] = field(default_factory=dict[str, RoofGeo])
    """The roofs the cut goes through."""


class SectionSheet(Paper):
    outside = False
    """An elevation: the plane is outside the building and nothing is cut."""

    @property
    def label(self) -> str | None:
        """What the agent wrote after the name of the section."""
        return self.m[self.sc.id].label

    def __init__(self, d: Derived, sc: SectionGeo, stand: Stand, title: str | None = None) -> None:
        self.sc = sc
        self.name = f"{sc.id}-{sc.id}"
        self.heading = title or f"Schnitt {self.name}"
        super().__init__(d, stand, self.heading)
        rx, ry = sc.right
        vx, vy = sc.view
        self.at = sc.coord * (vx if sc.axis == "x" else vy)
        self.matrix = [rx, ry, vx, vy, 0.0, -self.at]
        self.axis = LineString([(-1e4, 0.0), (1e4, 0.0)])
        self.cut = _Cut()
        self.door_holes: list[BaseGeometry] = []
        self.walls = list(self.g.walls.values())
        proj = self.m.of_kind("project")
        self.ground = proj[0].ground if proj and isinstance(proj[0], Project) else None
        statuses = {w.status for w in self.walls} | {s.status for s in self.g.slabs.values()}
        statuses |= {r.status for r in self.g.roofs.values()}
        statuses |= {s.status for s in self.g.stairs.values()}
        self.umbau = bool(statuses - {"new"})

    # ---------- the cut plane ----------

    def tr(self, g: BaseGeometry) -> BaseGeometry:
        """A plan shape in (u, depth): across the cut to the right, and distance behind it."""
        return affine_transform(g, self.matrix)

    def plan(self, u: float, depth: float = 0.0) -> Pt:
        rx, ry = self.sc.right
        vx, vy = self.sc.view
        return (rx * u + vx * (depth + self.at), ry * u + vy * (depth + self.at))

    def ivs(self, g: BaseGeometry) -> list[tuple[float, float]]:
        """The stretches of the cut line (as u) that lie inside a plan shape."""
        if g.is_empty:
            return []
        hit = self.tr(g).intersection(self.axis)
        out = [(min(c[0] for c in ln.coords), max(c[0] for c in ln.coords)) for ln in lines_of(hit)]
        return merge([(a, b) for a, b in out if b - a > 1e-6])

    def level_of(self, o: OpeningGeo) -> LevelGeo:
        return self.g.levels[o.level]

    # ---------- walls and openings ----------

    def column(self, w: WallGeo, ua: float, ub: float) -> Polygon | None:
        """The wall above a stretch of the cut line, with its top along the wall's profile."""
        if not w.top:
            return None
        sa, sb = w.s_of(*self.plan(ua)), w.s_of(*self.plan(ub))
        za, zb = w.top_at(sa), w.top_at(sb)
        if za is None or zb is None:
            return None
        top: list[Pt] = [(ua, za), (ub, zb)]
        if abs(sb - sa) > 1e-6:
            lo, hi = min(sa, sb), max(sa, sb)
            top += [(ua + (s - sa) / (sb - sa) * (ub - ua), z) for s, z in w.top if lo < s < hi]
        top.sort()
        return Polygon([(ua, w.bottom), (ub, w.bottom), *reversed(top)])

    def cutters(self) -> list[Polygon]:
        """The openings and niches in the cut as rectangles (u, z), through the whole wall."""
        out: list[Polygon] = []
        for o in self.g.openings.values():
            w = self.g.walls[o.host]
            if not w.active or o.status == "demolish":
                continue
            lv = self.level_of(o)
            if o.kind == "niche":
                lo_f, hi_f = w.lo - w.finish("lo"), w.hi + w.finish("hi")
                band = (w.hi - o.depth, hi_f) if o.face == "hi" else (lo_f, w.lo + o.depth)
            else:
                band = (w.lo - w.finish("lo"), w.hi + w.finish("hi"))
            plan = Polygon(
                [
                    w.plan_point(o.lo, band[0]),
                    w.plan_point(o.hi, band[0]),
                    w.plan_point(o.hi, band[1]),
                    w.plan_point(o.lo, band[1]),
                ]
            )
            z0, z1 = lv.z + o.sill, lv.z + o.top
            for ua, ub in self.ivs(plan):
                out.append(box(ua, z0, ub, z1))
                if o.kind != "niche":
                    self.cut.gaps.append((z0, z1))
                if o.kind == "win":
                    self.cut.windows.append((ua, ub, z0, z1))
        return out

    def finish_bands(self, w: WallGeo) -> list[BaseGeometry]:
        """The finish layers (plaster) beside the core of a wall, as plan shapes."""
        out: list[BaseGeometry] = []
        for side in ("lo", "hi"):
            f = w.finish(side)
            if f <= 0:
                continue
            band: BaseGeometry = w.box(w.lo - f, w.lo) if side == "lo" else w.box(w.hi, w.hi + f)
            if w.raw:
                others = [o.core for o in self.g.walls_on(w.level) if o is not w]
                band = band.difference(unary_union(others))
            out.append(band)
        return out

    def walls_cut(self, cutters: BaseGeometry) -> None:
        """Cores and finishes of the cut walls, grouped by status and load bearing."""
        taken: BaseGeometry = Polygon()
        groups = [
            (status, lb)
            for status in ("new", "existing", "demolish")
            for lb in (True, False)
            if any(w.status == status and w.lb == lb for w in self.walls)
        ]
        finish: list[BaseGeometry] = []
        for status, lb in groups:
            cores: list[BaseGeometry] = []
            for w in self.walls:
                if w.status != status or w.lb != lb:
                    continue
                for ua, ub in self.ivs(w.core):
                    col = self.column(w, ua, ub)
                    if col is not None:
                        cores.append(col)
                        self.cut.levels.add(w.level)
                        if status != "demolish":
                            self.cut.faces.append((ua, ub))
                for band in self.finish_bands(w):
                    for ua, ub in self.ivs(band):
                        col = self.column(w, ua, ub)
                        if col is not None:
                            finish.append(col)
            if not cores:
                continue
            area = unary_union(cores)
            if status != "demolish":
                area = area.difference(cutters)
            area = area.difference(taken)
            taken = unary_union([taken, area])
            fill, layer = wall_fill(status, lb, self.umbau)
            self.cut.walls.append(Shape(area, fill, layer))
        if finish:
            area = unary_union(finish).difference(cutters).difference(taken)
            self.cut.walls.insert(0, Shape(area, FINISH_FILL, L_FINISH, outline=False))

    # ---------- slabs, roof, stairs ----------

    def slabs_cut(self) -> None:
        floors: list[BaseGeometry] = []
        layers: list[BaseGeometry] = []
        for sl in self.g.slabs.values():
            lv = self.g.levels[sl.level]
            ssl = sl.top
            core = sl.layers.core
            below, above = sl.layers.after_core(), sl.layers.before_core()
            shapes: list[Shape] = []
            for ua, ub in self.ivs(sl.net):
                self.cut.levels.add(sl.level)
                if below > 0:
                    layers.append(box(ua, ssl - core - below, ub, ssl - core))
                if above > 0:
                    layers.append(box(ua, ssl, ub, ssl + above))
                if lv.z - ssl - above > 1e-6:
                    floors.append(box(ua, ssl + above, ub, lv.z))
                fill, _ = wall_fill(sl.status, True, self.umbau)
                shapes.append(Shape(box(ua, ssl - core, ub, ssl), fill, L_SLAB))
            self.cut.others += shapes
        if layers or floors:
            self.cut.others.insert(
                0, Shape(unary_union([*layers, *floors]), FINISH_FILL, L_FINISH, outline=False)
            )

    def roof_cut(self) -> None:
        by_status: dict[str, list[BaseGeometry]] = {}
        for lv in self.g.levels:
            roofs = self.g.roofs_on(lv)
            if not roofs:
                continue
            for idx, plane, piece in roof_pieces(self.g, lv):
                rf = roofs[idx]
                for ua, ub in self.ivs(piece):
                    za = plane(*self.plan(ua))
                    zb = plane(*self.plan(ub))
                    skin, lin = rf.skin_of(plane), rf.lining_of(plane)
                    by_status.setdefault(rf.status, []).append(
                        Polygon(
                            [
                                (ua, za - lin),
                                (ub, zb - lin),
                                (ub, zb + skin),
                                (ua, za + skin),
                            ]
                        )
                    )
                    self.cut.roofs[rf.id] = rf
        for status, shapes in by_status.items():
            fill, _ = wall_fill(status, False, self.umbau)
            self.cut.others.append(Shape(unary_union(shapes).buffer(0), fill, L_ROOF))

    def along(self, part: StairPartGeo, u: float) -> float:
        """How far along its climb a flight is where the cut line is at u."""
        x, y = self.plan(u)
        return (x - part.start[0]) * part.climb[0] + (y - part.start[1]) * part.climb[1]

    def stair_cut(self, st: StairGeo) -> list[BaseGeometry]:
        """A stair as solid steps on a sloping slab: flights, landings and winders."""
        a = self.g.levels[st.level]
        t = st.tread
        slope = st.riser / t
        e_s = st.riser + STAIR_THICK * math.hypot(1.0, slope)
        out: list[BaseGeometry] = []
        for part in st.parts:
            if part.kind != "flight":
                z = a.z + part.tread * st.riser
                for ua, ub in self.ivs(part.poly):
                    out.append(box(ua, z - STAIR_THICK - 0.02, ub, z))
                continue
            zb = a.z + part.tread * st.riser
            for ua, ub in self.ivs(part.poly):
                pa, pb = self.along(part, ua), self.along(part, ub)
                top: list[Pt] = []
                if abs(pb - pa) < 1e-6:
                    k = math.floor((pa + 1e-9) / t) + 1
                    top = [(ua, zb + k * st.riser), (ub, zb + k * st.riser)]
                else:
                    breaks = [ua]
                    lo, hi = min(pa, pb), max(pa, pb)
                    j = math.floor(lo / t) + 1
                    while j * t < hi - 1e-9:
                        breaks.append(ua + (j * t - pa) / (pb - pa) * (ub - ua))
                        j += 1
                    breaks.append(ub)
                    breaks.sort()
                    for u0, u1 in pairwise(breaks):
                        pm = self.along(part, (u0 + u1) / 2)
                        k = math.floor(pm / t) + 1
                        z = zb + k * st.riser
                        top += [(u0, z), (u1, z)]
                soff = [(u, zb + st.riser + self.along(part, u) * slope - e_s) for u in (ua, ub)]
                out.append(Polygon([*soff, *reversed(top)]).buffer(0))
        return out

    def stairs_cut(self) -> None:
        by_status: dict[str, list[BaseGeometry]] = {}
        for st in self.g.stairs.values():
            shapes = self.stair_cut(st)
            if shapes:
                by_status.setdefault(st.status, []).extend(shapes)
                self.cut.levels.add(st.level)
        for status, shapes in by_status.items():
            fill, _ = wall_fill(status, True, self.umbau)
            self.cut.others.append(Shape(unary_union(shapes).buffer(0), fill, L_STAIR))

    # ---------- behind the cut ----------

    def walls_behind(self) -> list[Face]:
        out: list[Face] = []
        ahead = box(-1e4, EPS, 1e4, 1e4)
        for w in self.walls:
            if not w.active or not w.top:
                continue
            seen = self.tr(w.poly).intersection(ahead)
            if seen.is_empty or seen.area < 1e-6:
                continue
            x0, y0, x1, _ = seen.bounds
            rx, ry = self.sc.right
            parallel = abs(rx * w.u[0] + ry * w.u[1]) > 0.7
            tops: list[Pt] = []
            if parallel:
                # the wall's profile along u
                for s, z in w.top:
                    px, py = w.plan_point(s, w.mid)
                    tops.append((self.sc.u(px, py), z))
                tops.sort()
                pts = [(x0, self.top_at(tops, x0)), (x1, self.top_at(tops, x1))]
                pts += [(u, z) for u, z in tops if x0 < u < x1]
                pts.sort()
            else:
                z = max(z for _, z in w.top)
                pts = [(x0, z), (x1, z)]
            face: BaseGeometry = Polygon([(x0, w.bottom), (x1, w.bottom), *reversed(pts)])
            if parallel:
                holes: list[BaseGeometry] = []
                for o in self.g.openings.values():
                    if o.host != w.id or o.kind == "niche" or o.status == "demolish":
                        continue
                    lv = self.level_of(o)
                    pa = w.plan_point(o.lo, w.mid)
                    pb = w.plan_point(o.hi, w.mid)
                    ua, ub = sorted((self.sc.u(*pa), self.sc.u(*pb)))
                    rect = box(ua, lv.z + o.sill, ub, lv.z + o.top)
                    holes.append(rect)
                    if o.kind == "win":
                        out.append(Face(y0 + 1e-3, rect, L_WIN, detail=True, solid=True))
                    elif self.outside:
                        out.append(Face(y0 + 1e-3, rect, L_DOOR, detail=True, solid=True))
                    else:
                        self.door_holes.append(rect)
                face = face.difference(unary_union(holes)) if holes else face
            out.append(Face(y0, face, L_VIEW))
        return out

    @staticmethod
    def top_at(tops: list[Pt], u: float) -> float:
        if u <= tops[0][0]:
            return tops[0][1]
        for (ua, za), (ub, zb) in pairwise(tops):
            if ua <= u <= ub:
                return za if ub == ua else za + (zb - za) * (u - ua) / (ub - ua)
        return tops[-1][1]

    def roof_behind(self) -> list[Face]:
        out: list[Face] = []
        ahead = box(-1e4, EPS, 1e4, 1e4)
        for lv in self.g.levels:
            if not self.g.roofs_on(lv):
                continue
            for _, plane, piece in roof_pieces(self.g, lv):
                seen = self.tr(piece).intersection(ahead)
                if seen.is_empty:
                    continue
                for p in polys(seen, 1e-6):
                    ring: list[Pt] = []
                    for u, dep in p.exterior.coords:
                        x, y = self.plan(u, dep)
                        ring.append((u, plane(x, y)))
                    face = Polygon(ring).buffer(0)
                    if face.area > 1e-4:
                        out.append(Face(p.bounds[1], face, L_VIEW))
        return out

    def stairs_behind(self) -> list[Face]:
        out: list[Face] = []
        ahead = box(-1e4, EPS, 1e4, 1e4)
        for st in self.g.stairs.values():
            a = self.g.levels[st.level]
            for part in st.parts:
                z = a.z + part.tread * st.riser
                if part.kind != "flight":
                    seen = self.tr(part.poly).intersection(ahead)
                    if not seen.is_empty:
                        x0, y0, x1, _ = seen.bounds
                        out.append(
                            Face(y0, box(x0, z - STAIR_THICK - 0.02, x1, z), L_STAIR, solid=True)
                        )
                    continue
                cx, cy = part.climb
                nx, ny = -cy, cx
                sx, sy = part.start
                for k in range(1, part.risers):
                    p0, p1 = (k - 1) * st.tread, k * st.tread
                    h = st.w / 2
                    ring = [
                        (sx + cx * p0 + nx * h, sy + cy * p0 + ny * h),
                        (sx + cx * p1 + nx * h, sy + cy * p1 + ny * h),
                        (sx + cx * p1 - nx * h, sy + cy * p1 - ny * h),
                        (sx + cx * p0 - nx * h, sy + cy * p0 - ny * h),
                    ]
                    seen = self.tr(Polygon(ring)).intersection(ahead)
                    if seen.is_empty:
                        continue
                    x0, y0, x1, _ = seen.bounds
                    zk = z + k * st.riser
                    out.append(
                        Face(y0, box(x0, zk - st.riser - STAIR_THICK, x1, zk), L_STAIR, solid=True)
                    )
        return out

    # ---------- drawing ----------

    def emit(self, shapes: list[Shape]) -> BaseGeometry:
        """Draw shapes, the later ones on top: each loses what the later ones cover."""
        above: BaseGeometry = Polygon()
        solid: list[BaseGeometry] = []
        for sh in reversed(shapes):
            geo = sh.geo.difference(above) if not above.is_empty else sh.geo
            above = unary_union([above, sh.geo])
            solid.append(geo)
        pen = self.pen(0.35)
        for sh, geo in zip(shapes, reversed(solid), strict=True):
            for p in polys(geo, 1e-6):
                self.dw.add(poly_item(p, sh.fill, pen if sh.outline else None, sh.layer))
        return above

    def view(self, faces: list[Face], occluder: BaseGeometry) -> BaseGeometry:
        """The outlines of what is behind the cut, nearest first, hidden lines left out.

        Returns what labels must keep off: windows, stairs, door openings and every outline.
        """
        thin = self.pen(0.13, "#505050")
        glass = {L_WIN: self.pen(0.13, "#2266cc"), L_DOOR: self.pen(0.13, "#504040")}
        keep = self.sh.m(0.4)
        blockers: list[BaseGeometry] = list(self.door_holes)
        for f in sorted(faces, key=lambda f: f.depth):
            vis = f.geo.difference(occluder) if not occluder.is_empty else f.geo
            if vis.is_empty:
                continue
            if f.detail:
                for p in polys(vis, 1e-6):
                    self.dw.add(poly_item(p, None, glass[f.layer], f.layer))
                    if p.area > 0.99 * f.geo.area:
                        x0, y0, x1, y1 = f.geo.bounds
                        g = 0.05
                        pane = [
                            (x0 + g, y0 + g),
                            (x1 - g, y0 + g),
                            (x1 - g, y1 - g),
                            (x0 + g, y1 - g),
                        ]
                        self.dw.add(Poly(pane, None, glass[f.layer], f.layer))
            else:
                if f.fill is not None:
                    for p in polys(vis, 1e-6):
                        self.dw.add(poly_item(p, f.fill, None, f.layer))
                edge = vis.boundary
                if not occluder.is_empty:
                    # an edge that is also an edge of something nearer is drawn there
                    edge = edge.difference(occluder.boundary.buffer(2e-4))
                for ln in lines_of(linemerge(lines_of(edge))) if not edge.is_empty else []:
                    pts = list(ln.coords)
                    for a, b in pairwise(pts):
                        self.dw.add(Line((a[0], a[1]), (b[0], b[1]), thin, f.layer))
            blockers.append(vis if f.solid else vis.boundary.buffer(keep))
            occluder = unary_union([occluder, f.geo])
        return unary_union(blockers) if blockers else Polygon()

    def window_symbols(self) -> None:
        """A window in the cut: the glass as a line between sill and head, in the opening."""
        pen = self.pen(0.25, "#2266cc")
        for ua, ub, z0, z1 in self.cut.windows:
            m = (ua + ub) / 2
            self.dw.add(Line((m, z0), (m, z1), pen, L_WIN))
            w = (ub - ua) * 0.3
            for z in (z0, z1):
                self.dw.add(Line((m - w, z), (m + w, z), pen, L_WIN))

    def terrain(self, poche: BaseGeometry, u0: float, u1: float) -> None:
        if self.ground is None:
            return
        g = self.ground
        a, b = u0 - self.sh.m(TERRAIN), u1 + self.sh.m(TERRAIN)
        line = LineString([(a, g), (b, g)])
        left = line.difference(poche)
        segs = sorted(lines_of(left), key=lambda ln: ln.bounds[0])
        if not segs:
            return
        pen, hatch = self.pen(0.35, "#706030"), self.pen(0.13, "#706030")
        outer = [segs[0]] if len(segs) == 1 else [segs[0], segs[-1]]
        for ln in outer:
            x0, _, x1, _ = ln.bounds
            self.dw.add(Line((x0, g), (x1, g), pen, L_TERRAIN))
            step = self.sh.m(3.0)
            n = int((x1 - x0) / step)
            for i in range(n + 1):
                x = x0 + i * step
                self.dw.add(
                    Line((x, g), (x - self.sh.m(2.0), g - self.sh.m(2.0)), hatch, L_TERRAIN)
                )

    def grid_lines(self, u0: float, u1: float, z0: float, z1: float) -> float:
        """Grids across the cut with their bubbles on top; returns the paper space they need."""
        sh = self.sh
        pen = self.pen(0.13, BLACK, (6.0, 1.5, 1.0, 1.5))
        ring = self.pen(0.18)
        r = sh.m(BUBBLE_R)
        n = 0
        for el in self.m.of_kind("grid"):
            assert isinstance(el, Grid)
            if el.axis == self.sc.axis:
                continue
            x, y = (self.sc.coord, el.coord) if self.sc.axis == "x" else (el.coord, self.sc.coord)
            u = self.sc.u(x, y)
            if not u0 - TOL <= u <= u1 + TOL:
                continue
            n += 1
            yc = z1 + sh.m(6.0 + BUBBLE_R)
            self.dw.add(Line((u, z0 - sh.m(1.5)), (u, yc - r), pen, L_GRID))
            self.dw.add(Circle((u, yc), r, ring, None, L_GRID))
            self.text((u, yc - sh.m(1.1)), el.label or el.id, 3.0, L_GRID, bold=True)
        return n

    # ---------- labels ----------

    def clear_at(self, rg: RoomGeo, u: float) -> float | None:
        """The clear height of a room above its FFL where the cut line is at u."""
        x, y = self.plan(u)
        at = SPoint(x, y)
        for f, piece in rg.ceiling.pieces(rg.fin):
            if piece.buffer(1e-6).contains(at):
                return f(x, y)
        return None

    def rooms(self, blockers: BaseGeometry, poche: BaseGeometry) -> None:
        """A label in each room the cut goes through: name and clear height, on a free spot."""
        sh = self.sh
        for rg in self.g.rooms.values():
            ivs = self.ivs(rg.fin)
            if not ivs:
                continue
            el = self.m[rg.id]
            assert isinstance(el, Room)
            lv = self.g.levels[rg.level]
            hr = rg.height_range()
            name = el.label or USE_DE[el.use]
            heights = ""
            if hr is not None:
                lo, hi = hr
                heights = de(lo) if hi - lo < 0.005 else f"{de(lo)} – {de(hi)}"
            # the full note, a short one, or none, where the room is crowded with lines
            notes = [f"lichte Höhe {heights} m", f"l. H. {heights} m", ""] if heights else [""]
            spot: tuple[float, float] | None = None
            note = ""
            for hold, tries in ((blockers, notes), (poche, notes[:1])):
                for note in tries:
                    w_m = sh.m(max(text_width(name, 2.5), text_width(note, 2.0)) + 1.0)
                    spot = self.free_spot(rg, lv, ivs, w_m, sh.m(2.6), sh.m(3.8), hold)
                    if spot is not None:
                        break
                if spot is not None:
                    break
            if spot is None:
                continue
            u, zc = spot
            self.text((u, zc + sh.m(1.0)), name, 2.5, L_TEXT, bold=True)
            if note:
                self.text((u, zc - sh.m(2.2)), note, 2.0, L_TEXT, color=GREY)

    def free_spot(
        self,
        rg: RoomGeo,
        lv: LevelGeo,
        ivs: list[tuple[float, float]],
        w: float,
        down: float,
        up: float,
        hold: BaseGeometry,
    ) -> tuple[float, float] | None:
        """Where a label of w m width fits in the room: nearest the middle, clear of `hold`."""
        offs = [0.0]
        for k in range(1, 80):
            offs += [k * 0.1, -k * 0.1]
        # at mid height, or low down, or under the ceiling
        for where in ("mid", "low", "high"):
            for ua, ub in sorted(ivs, key=lambda iv: iv[0] - iv[1]):
                mid = (ua + ub) / 2
                for off in offs:
                    u = mid + off
                    if u - w / 2 < ua or u + w / 2 > ub:
                        continue
                    h = self.clear_at(rg, u)
                    top = lv.z + (2.5 if h is None else h) - 0.05
                    zc = {
                        "mid": min(lv.z + 1.2, (lv.z + top) / 2),
                        "low": lv.z + 0.1 + down,
                        "high": top - up,
                    }[where]
                    zc = min(zc, top - up)
                    if zc - down < lv.z + 0.05:
                        continue
                    if not box(u - w / 2, zc - down, u + w / 2, zc + up).intersects(hold):
                        return (u, zc)
        return None

    def height_marks(self, marks: list[Mark], u0: float) -> None:
        """Height marks (Höhenkoten) left of the building: a leader, a triangle, the value."""
        sh = self.sh
        pen, thin = self.pen(0.25), self.pen(0.13)
        x = u0 - sh.m(MARK_ARM)
        last = -1e9
        for mk in sorted(marks, key=lambda m: m.z):
            self.dw.add(Line((u0 - sh.m(1.5), mk.z), (x, mk.z), thin, L_DIM))
            h, w = sh.m(2.2), sh.m(1.2)
            self.dw.add(Poly([(x, mk.z), (x - w, mk.z + h), (x + w, mk.z + h)], None, pen, L_DIM))
            self.dw.add(Line((x - w, mk.z), (x + w, mk.z), pen, L_DIM))
            base = max(mk.z + sh.m(0.8), last + sh.m(3.3))
            last = base
            self.text((x - sh.m(2.5), base), mk.text, 2.2, L_DIM, anchor="end")

    # ---------- the sheet ----------

    def draw(self) -> Drawing | None:
        cutters = self.cutters()
        self.walls_cut(unary_union(cutters) if cutters else Polygon())
        if not self.cut.faces:
            return None
        self.slabs_cut()
        self.roof_cut()
        self.stairs_cut()
        # lowest first; finishes and floors lie under the solid shapes
        shapes = sorted([*self.cut.others, *self.cut.walls], key=lambda s: s.outline)
        poche = unary_union([s.geo for s in shapes])
        u0, z0, u1, z1 = poche.bounds
        faces = [*self.walls_behind(), *self.roof_behind(), *self.stairs_behind()]
        for f in faces:
            fx0, fy0, fx1, fy1 = f.geo.bounds
            u0, u1 = min(u0, fx0), max(u1, fx1)
            z0, z1 = min(z0, fy0), max(z1, fy1)
        top = max((rf.ridge_z for rf in self.cut.roofs.values()), default=z1)
        z1 = max(z1, top)
        if self.ground is not None:
            z0, z1 = min(z0, self.ground), max(z1, self.ground)
        marks = self.marks()
        chains = self.chains(top, z0)
        need = self.layout((u0, z0, u1, z1), marks, chains)
        self.terrain(poche, u0, u1)
        self.emit(shapes)
        self.window_symbols()
        blockers = self.view(faces, poche)
        self.dimension((u0, z0, u1, z1), chains)
        self.grid_lines(u0, u1, z0, z1)
        self.height_marks(marks, u0)
        self.rooms(blockers, poche)
        self.caption(u0, u1, z0, need)
        self.title_block(self.heading, self.zero_note(), self.number())
        return self.dw

    def number(self) -> str:
        """The plan number: after the plans of the storeys."""
        return f"A-{len(self.g.levels) + sorted(self.g.sections).index(self.sc.id) + 1:02d}"

    def layout(
        self,
        extent: tuple[float, float, float, float],
        marks: list[Mark],
        chains: dict[str, list[Chain]],
    ) -> dict[str, float]:
        """Choose the sheet: room for the height marks, the chains and the grid bubbles."""
        grids = [
            el for el in self.m.of_kind("grid") if isinstance(el, Grid) and el.axis != self.sc.axis
        ]
        need = {
            "W": MARK_ARM + 3.5 + max((text_width(m.text, 2.2) for m in marks), default=10.0) + 4.0,
            "E": allowance(len(chains["E"]), False),
            "S": allowance(len(chains["S"]), False),
            "N": 10.0 + (2 * BUBBLE_R + 6.0 if grids else 0.0),
        }
        self.dw.sheet = fit_sheet(extent, need)
        return need

    def zero_note(self) -> str:
        for lv in self.g.levels.values():
            if abs(lv.z) < 1e-9:
                el = self.m[lv.id]
                name = el.label or LEVEL_DE.get(lv.id, lv.id)
                return f"Höhen in m, ±0,00 = OKFF {name}"
        return "Höhen in m"

    def marks(self) -> list[Mark]:
        out: list[Mark] = []
        for lid in self.g.level_order():
            if lid in self.cut.levels:
                lv = self.g.levels[lid]
                out.append(Mark(lv.z, f"{lid} {height_text(lv.z)}"))
        for rf in self.cut.roofs.values():
            if rf.pitch < 0.5:
                out.append(Mark(rf.ridge_z, f"OK Dach {height_text(rf.ridge_z)}"))
                continue
            out.append(Mark(rf.ridge_z, f"First {height_text(rf.ridge_z)}"))
            out.append(Mark(rf.eaves_z, f"Traufe {height_text(rf.eaves_z)}"))
        if self.ground is not None:
            out.append(Mark(self.ground, f"Gelände {height_text(self.ground)}"))
        return list({(m.z, m.text): m for m in out}.values())

    def along_chains(self) -> list[Chain]:
        """The faces of the cut walls and the overall width."""
        faces = uniq([v for a, b in self.cut.faces for v in (a, b)])
        out = [Chain("walls", faces)] if len(faces) > 2 else []
        return [*out, Chain("total", [faces[0], faces[-1]])]

    def chains(self, top: float, bottom: float) -> dict[str, list[Chain]]:
        """Dimension chains: along the bottom, and on the right openings, storeys and the total
        height."""
        out: dict[str, list[Chain]] = {"S": self.along_chains(), "N": [], "W": [], "E": []}
        floors = [self.g.levels[k].z for k in self.g.level_order() if k in self.cut.levels]
        base = self.ground if self.ground is not None else floors[0] if floors else bottom
        gaps = uniq([z for g in self.cut.gaps for z in g])
        if gaps:
            above = [f for f in floors if f > gaps[-1]]
            out["E"].append(Chain("open", uniq([*floors, *gaps, *above[:1]])))
        storeys = uniq([*floors, top])
        if len(storeys) > 2:
            out["E"].append(Chain("levels", storeys))
        out["E"].append(Chain("total", uniq([base, top])))
        return out

    def caption(self, u0: float, u1: float, z0: float, need: dict[str, float]) -> None:
        sh = self.sh
        y = z0 - sh.m(need["S"] + 5.0)
        label = f"  –  {self.label}" if self.label else ""
        self.text(
            ((u0 + u1) / 2, y),
            f"{self.heading}{label}   M 1:{sh.scale}",
            3.5,
            L_TEXT,
            bold=True,
        )


def sheet_section(d: Derived, key: str, stand: Stand | None = None) -> Drawing | None:
    """The section on a sheet; none if the cut meets no wall."""
    return SectionSheet(d, d.arch.sections[key], stand or Stand()).draw()

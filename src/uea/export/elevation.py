"""An elevation as a sheet to print (decision 0024): one facade seen from outside.

An elevation is a section whose plane stands outside the building: nothing is cut and everything
lies behind the plane. The same machinery draws it (`section.py`): faces nearest first, each losing
what nearer ones cover, so no hidden line is drawn. Outside, the walls show their openings with
frames and glass, the slab edges close the facade between the storeys, the roof is seen from above
with its thickness at the eaves and the verges, and the ground hides the foot of the building.

Not drawn yet: sun shading, balconies and chimneys (the model has none), facade materials, a
facade that is not square to x or y.
"""

from itertools import pairwise
from typing import Literal

from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from uea.derive import Derived
from uea.export.drawing import Drawing
from uea.export.paper import L_ROOF, L_VIEW, Chain, Stand, uniq
from uea.export.section import EPS, Face, Mark, SectionSheet, lines_of
from uea.packs.arch.geometry import SectionGeo, WallGeo, roof_pieces

SIDES = ("north", "east", "south", "west")
DE = {"north": "Nord", "east": "Ost", "south": "Süd", "west": "West"}
LOOK: dict[str, tuple[Literal["x", "y"], Literal["n", "s", "e", "w"]]] = {
    "south": ("y", "n"),
    "north": ("y", "s"),
    "east": ("x", "w"),
    "west": ("x", "e"),
}
"""The plane's axis and the direction one looks in, for the facade named."""
FACING = {"south": ("h", "lo"), "north": ("h", "hi"), "west": ("v", "lo"), "east": ("v", "hi")}
"""The direction of a wall that forms the facade, and which of its faces is the outside."""
ROOF_FILL = "#e4ded6"
ROOF_FIRST = 0.001
"""The roof counts as 1 mm nearer than the wall it rests on: at the eaves it is in front."""
STAND_OFF = 1.0
"""How far the plane stands from the building, in m."""


class _Elevation(SectionSheet):
    outside = True

    def __init__(
        self,
        d: Derived,
        side: str,
        bounds: tuple[float, float, float, float],
        stand: Stand,
    ) -> None:
        self.side = side
        axis, look = LOOK[side]
        x0, y0, x1, y1 = bounds
        coord = {"south": y0, "north": y1, "west": x0, "east": x1}[side]
        sign = -1.0 if side in ("south", "west") else 1.0
        sc = SectionGeo(side, axis, coord + sign * STAND_OFF, look)
        super().__init__(d, sc, stand, f"Ansicht {DE[side]}")
        self.name = DE[side]

    @property
    def label(self) -> str | None:
        return None

    def facade(self) -> list[WallGeo]:
        """The walls that form this facade, on every storey."""
        o, ext = FACING[self.side]
        return [w for w in self.walls if w.active and w.o == o and w.ext == ext]

    def u_of(self, w: WallGeo, s: float) -> float:
        return self.sc.u(*w.plan_point(s, w.mid))

    # ---------- faces ----------

    def slab_edges(self) -> list[Face]:
        """The edge of each slab closes the facade between the storeys; under a roof it reaches
        up to the rafters at the eaves."""
        out: list[Face] = []
        for sl in self.g.slabs.values():
            if sl.status == "demolish":
                continue
            roofs = self.g.roofs_on(sl.level)
            for poly in lines_of(sl.outline.boundary):
                pts = list(poly.coords)
                for (xa, ya), (xb, yb) in pairwise(pts):
                    ua, ub = self.sc.u(xa, ya), self.sc.u(xb, yb)
                    if abs(ub - ua) < 1e-6:
                        continue
                    tops: list[float] = []
                    for x, y in ((xa, ya), (xb, yb)):
                        under = [
                            rf.underside(x, y)
                            for rf in roofs
                            if rf.foot.buffer(0.01).contains(Point(x, y))
                        ]
                        tops.append(max(sl.top, min(under)) if under else sl.top)
                    z0 = sl.underside
                    face = Polygon([(ua, z0), (ub, z0), (ub, tops[1]), (ua, tops[0])]).buffer(0)
                    depth = min(self.sc.depth(xa, ya), self.sc.depth(xb, yb))
                    if face.area > 1e-5 and depth > -EPS:
                        out.append(Face(depth, face, L_VIEW))
        return out

    def roof_outside(self) -> list[Face]:
        """The roof seen from above: each plane, and the thickness along its edges."""
        out: list[Face] = []
        for lv in self.g.levels:
            roofs = self.g.roofs_on(lv)
            if not roofs:
                continue
            pieces = roof_pieces(self.g, lv)
            for i, (idx, plane, piece) in enumerate(pieces):
                rf = roofs[idx]
                skin, lin = rf.skin_of(plane), rf.lining_of(plane)
                shape = self.tr(piece)
                assert isinstance(shape, Polygon)
                ring = [
                    (u, plane(*self.plan(u, dep)) + skin) for u, dep in list(shape.exterior.coords)
                ]
                top = Polygon(ring).buffer(0)
                if top.area > 1e-4:
                    out.append(Face(shape.bounds[1] - ROOF_FIRST, top, L_ROOF, fill=ROOF_FILL))
                others = [o for j, (_, _, o) in enumerate(pieces) if j != i]
                edge: BaseGeometry = piece.boundary
                if others:
                    edge = edge.difference(unary_union(others).buffer(1e-4))
                for ln in lines_of(edge):
                    for (xa, ya), (xb, yb) in pairwise(list(ln.coords)):
                        ua, ub = self.sc.u(xa, ya), self.sc.u(xb, yb)
                        if abs(ub - ua) < 1e-6:
                            continue
                        za, zb = plane(xa, ya), plane(xb, yb)
                        quad = Polygon(
                            [(ua, za - lin), (ub, zb - lin), (ub, zb + skin), (ua, za + skin)]
                        ).buffer(0)
                        depth = min(self.sc.depth(xa, ya), self.sc.depth(xb, yb))
                        if quad.area > 1e-5:
                            out.append(Face(depth - ROOF_FIRST, quad, L_ROOF, fill=ROOF_FILL))
        return out

    @staticmethod
    def joined(faces: list[Face]) -> list[Face]:
        """Wall faces that lie in one plane are one face: a corner has no line in the facade."""
        plain = sorted((f for f in faces if not f.detail), key=lambda f: f.depth)
        out = [f for f in faces if f.detail]
        group: list[Face] = []
        for f in plain:
            if group and f.depth - group[0].depth > 0.005:
                out.append(Face(group[0].depth, unary_union([g.geo for g in group]), L_VIEW))
                group = []
            group.append(f)
        if group:
            out.append(Face(group[0].depth, unary_union([g.geo for g in group]), L_VIEW))
        return out

    # ---------- dimensions ----------

    def along_chains(self) -> list[Chain]:
        """Along the bottom: the openings and piers of the facade, and its overall width."""
        walls = self.facade()
        ids = {w.id for w in walls}
        ends = [self.u_of(w, s) for w in walls for s in (w.s0, w.s1)]
        pts = [
            self.u_of(self.g.walls[o.host], v)
            for o in self.g.openings.values()
            if o.host in ids and o.kind != "niche" and o.status != "demolish"
            for v in (o.lo, o.hi)
        ]
        out = [Chain("open", uniq([*ends, *pts]))] if pts else []
        return [*out, Chain("total", [min(ends), max(ends)])]

    def number(self) -> str:
        n = len(self.g.levels) + len(self.g.sections)
        return f"A-{n + SIDES.index(self.side) + 1:02d}"

    # ---------- the sheet ----------

    def draw(self) -> Drawing | None:
        ids = {w.id for w in self.facade()}
        self.cut.levels = {w.level for w in self.walls if w.active}
        self.cut.roofs = {k: rf for k, rf in self.g.roofs.items() if rf.status != "demolish"}
        for o in self.g.openings.values():
            if o.host in ids and o.kind != "niche" and o.status != "demolish":
                lv = self.g.levels[o.level]
                self.cut.gaps.append((lv.z + o.sill, lv.z + o.top))
        faces = [
            *self.joined(self.walls_behind()),
            *self.joined(self.slab_edges()),
            *self.roof_outside(),
        ]
        if not faces or not self.facade():
            return None
        u0, z0, u1, z1 = faces[0].geo.bounds
        for f in faces:
            fx0, fy0, fx1, fy1 = f.geo.bounds
            u0, u1 = min(u0, fx0), max(u1, fx1)
            z0, z1 = min(z0, fy0), max(z1, fy1)
        top = max((rf.ridge_z for rf in self.cut.roofs.values()), default=z1)
        z1 = max(z1, top)
        below: BaseGeometry = Polygon()
        if self.ground is not None:
            z0 = self.ground
            below = box(-1e4, -1e4, 1e4, self.ground)
        marks: list[Mark] = self.marks()
        chains = self.chains(top, z0)
        need = self.layout((u0, z0, u1, z1), marks, chains)
        self.terrain(Polygon(), u0, u1)
        self.view(faces, below)
        self.dimension((u0, z0, u1, z1), chains)
        self.grid_lines(u0, u1, z0, z1)
        self.height_marks(marks, u0)
        self.caption(u0, u1, z0, need)
        self.title_block(self.heading, self.zero_note(), self.number())
        return self.dw


def sheet_elevation(d: Derived, side: str, stand: Stand | None = None) -> Drawing | None:
    """The facade on a sheet, seen from outside; none if the model has no walls."""
    walls = [w.poly for w in d.arch.walls.values() if w.active]
    if not walls:
        return None
    x0, y0, x1, y1 = unary_union(walls).bounds
    return _Elevation(d, side, (x0, y0, x1, y1), stand or Stand()).draw()

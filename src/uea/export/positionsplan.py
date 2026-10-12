"""The Positionsplan of a storey (decision 0040): the floor plan in grey, the load-bearing walls
in blue, and the number of every position of the Statische Berechnung where it is: the slab
over the storey and its beams, the walls, the lintels over their openings, the roof and its
eaves, and on the lowest storey the strip footings. The numbers are those of `uea calc struct`
(`packs/struct/positions.py`): both come from the model.
"""

from shapely.ops import unary_union

from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Pen
from uea.export.install import FITS_INSTALL, ROW, InstallPlan, ghost
from uea.export.paper import BLACK, BLOCK_H, BLOCK_W, Stand, fit_sheet, frame, poly_item
from uea.export.symbols import Ink, Spot
from uea.packs.struct.positions import Pos, lintel_openings, positions

T_WALL = "T-WAND-TRAGEND"
T_LINTEL = "T-STURZ"
T_BEAM = "T-UNTERZUG"
T_EAVES = "T-TRAUFE"
T_POS = "T-POSITION"
T_LEGEND = "T-LEGENDE"
BLUE = "#1f5fbf"
WALL_FILL = "#d6e4f7"
RED = "#c0392b"
STRUCT_LAYER_COLORS = {
    T_WALL: BLUE,
    T_LINTEL: RED,
    T_BEAM: BLUE,
    T_EAVES: BLUE,
    T_POS: BLACK,
    T_LEGEND: BLACK,
}
KEYS = {
    "wall": "Tragende Wand",
    "lintel": "Sturz über Öffnung",
    "beam": "Unterzug",
    "eaves": "Traufe (Auflager des Daches)",
    "pos": "Positionsnummer (Statische Berechnung)",
}
STRIP = 72.0


class PosPlan(InstallPlan):
    def __init__(self, d: Derived, level: str, stand: Stand, pos: list[Pos]) -> None:
        super().__init__(d, level, stand)
        self.heading = f"Positionsplan {self.level_name}"
        self.dw.title = f"{self.project}: {self.heading}"
        self.pos = [p for p in pos if p.sheet == level]
        self.no = {(p.kind, p.id): p.no for p in self.pos}

    def draw(self) -> Drawing | None:
        bbox = self.bbox()
        if bbox is None or not self.pos:
            return None
        need = dict.fromkeys("SNWE", 8.0)
        self.dw.sheet = fit_sheet(bbox, need, strip=STRIP, fits=FITS_INSTALL)
        self.cut_all = unary_union([w.poly for w in self.live])
        self.stair_zone = unary_union(
            [s.poly.buffer(self.sh.m(5.0)) for s in self.g.stairs.values() if s.level == self.level]
        )
        start = len(self.dw.items)
        self.walls_and_openings()
        self.stairs_and_voids()
        ghost(self.dw.items[start:])
        self.names()
        self.bearing_walls()
        self.lintels()
        self.beams()
        self.roofs()
        self.slab()
        self.legend()
        self.caption(bbox, need)
        nr = f"T-{self.g.level_order().index(self.level) + 1:02d}"
        note = "Positionen der Statischen Berechnung (uea calc struct); tragende Wände blau"
        self.title_block(self.heading, note, nr)
        return self.dw

    def label(self, x: float, y: float, txt: str, rot: float = 0.0, size: float = 2.2) -> None:
        self.text((x, y), txt, size, T_POS, bold=True, color=BLUE, rot=rot)

    # ---------- members ----------

    def bearing_walls(self) -> None:
        first = self.g.level_order()[0]
        for w in self.live:
            no = self.no.get(("wall", w.id))
            if no is None:
                continue
            self.dw.add(poly_item(w.core, WALL_FILL, self.pen(0.25, BLUE), T_WALL))
            txt = no
            if w.level == first and ("footing", w.id) in self.no:
                txt += f" · {self.no[('footing', w.id)]}"
            s = (w.s0 + w.s1) / 2
            # beside the lintels' labels, a third along the wall
            s = w.s0 + (w.s1 - w.s0) * 0.3 if any(lintel_openings(self.g, w.id)) else s
            x, y = w.plan_point(s, w.mid)
            rot = 90.0 if w.o == "v" else 0.0
            self.label(
                x - (self.sh.m(0.8) if rot else 0), y - (0 if rot else self.sh.m(0.8)), txt, rot
            )

    def lintels(self) -> None:
        pen = self.pen(0.7, RED)
        for w in self.live:
            if ("wall", w.id) not in self.no:
                continue
            for o in lintel_openings(self.g, w.id):
                no = self.no.get(("lintel", o.id))
                if no is None:
                    continue
                a, b = w.plan_point(o.lo, w.mid), w.plan_point(o.hi, w.mid)
                self.dw.add(Line(a, b, pen, T_LINTEL))
                out = w.t / 2 + self.sh.m(3.0)
                side = 1.0 if w.ext == "lo" else -1.0
                x, y = w.plan_point(o.mid, w.mid + side * out)
                self.text((x, y - self.sh.m(0.8)), no, 1.8, T_POS, bold=True, color=RED)

    def beams(self) -> None:
        sg = getattr(self.d, "struct", None)
        if sg is None:
            return
        pen = self.pen(0.5, BLUE, (6.0, 1.5, 1.0, 1.5))
        for p in self.pos:
            if p.kind != "beam":
                continue
            b = sg.beams[p.id]
            self.dw.add(Line(b.a, b.b, pen, T_BEAM))
            mx, my = (b.a[0] + b.b[0]) / 2, (b.a[1] + b.b[1]) / 2
            self.label(
                mx + self.sh.m(1.5), my + self.sh.m(1.5), f"{p.no} {p.id} {b.section}", 0.0, 1.8
            )

    def roofs(self) -> None:
        pen = self.pen(0.5, BLUE, (3.0, 1.5))
        for p in self.pos:
            if p.kind != "roof":
                continue
            rg = self.g.roofs[p.id]
            edges = {
                "s": ((rg.x0, rg.y0), (rg.x1, rg.y0)),
                "n": ((rg.x0, rg.y1), (rg.x1, rg.y1)),
                "w": ((rg.x0, rg.y0), (rg.x0, rg.y1)),
                "e": ((rg.x1, rg.y0), (rg.x1, rg.y1)),
            }
            for e in rg.eave_edges:
                a, b = edges[e]
                self.dw.add(Line(a, b, pen, T_EAVES))
            c = rg.foot.centroid
            self.label(c.x, c.y - self.sh.m(6.0), f"{p.no} Dach {p.id}", 0.0, 2.6)

    def slab(self) -> None:
        for p in self.pos:
            if p.kind != "slab":
                continue
            sl = self.g.slabs[p.id]
            # the middle of the largest room, below its name
            rooms = [r for r in self.g.rooms.values() if r.level == self.level]
            if rooms:
                big = max(rooms, key=lambda r: r.area_fin)
                at = (
                    big.fin.centroid
                    if big.fin.contains(big.fin.centroid)
                    else big.fin.representative_point()
                )
                x, y = at.x, at.y - self.sh.m(7.0)
            else:
                c = sl.net.representative_point()
                x, y = c.x, c.y
            h = f"{sl.layers.core * 100:.0f}".replace(".", ",")
            self.label(x, y, f"{p.no} Decke {p.id} über {self.level_name}, h = {h} cm", 0.0, 2.4)

    # ---------- legend ----------

    def legend(self) -> None:
        sh = self.sh
        _, y0, x1, _ = frame(sh.paper)
        top = y0 + BLOCK_H
        bx = x1 - BLOCK_W - STRIP
        self.rect(bx, y0, x1 - BLOCK_W, top, self.pen(0.7), T_LEGEND)
        self.text(sh.pt(bx + 2, top - 4.2), "Legende", 2.4, T_LEGEND, anchor="start", bold=True)
        kinds = {p.kind for p in self.pos}
        shown = ["wall"] if "wall" in kinds else []
        shown += [k for k in ("lintel", "beam") if k in kinds]
        if "roof" in kinds:
            shown.append("eaves")
        shown.append("pos")
        y = top - 7.0
        for key in shown:
            self.mark(key, bx + 6.0, y - 0.8)
            self.text(sh.pt(bx + 12.0, y - 1.3), KEYS[key], 1.6, T_LEGEND, anchor="start")
            y -= ROW

    def mark(self, key: str, x: float, y: float) -> None:
        sh = self.sh
        if key == "wall":
            ink = Ink(self.dw, sh, Spot(sh.pt(x, y)), BLUE, T_LEGEND)
            ink.poly([(-2.4, -0.9), (2.4, -0.9), (2.4, 0.9), (-2.4, 0.9)], WALL_FILL, 0.25)
            return
        if key == "pos":
            self.text(sh.pt(x, y - 0.6), "2.01", 1.8, T_LEGEND, bold=True, color=BLUE)
            return
        pen = {
            "lintel": Pen(RED, sh.m(0.7)),
            "beam": Pen(BLUE, sh.m(0.5), (sh.m(6.0), sh.m(1.5), sh.m(1.0), sh.m(1.5))),
            "eaves": Pen(BLUE, sh.m(0.5), (sh.m(3.0), sh.m(1.5))),
        }[key]
        self.dw.add(Line(sh.pt(x - 3.0, y), sh.pt(x + 3.0, y), pen, T_LEGEND))


def struct_levels(d: Derived) -> list[str]:
    """The storeys with a position on their plan."""
    found = {p.sheet for p in positions(d)}
    return [lv for lv in d.arch.level_order() if lv in found]


def sheet_positions(d: Derived, level: str, stand: Stand | None = None) -> Drawing | None:
    return PosPlan(d, level, stand or Stand(), positions(d)).draw()

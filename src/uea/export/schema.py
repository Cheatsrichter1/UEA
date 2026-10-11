"""The Heizungs- und Trinkwasserschema (decision 0036): a diagram, not to scale, of what supplies
what in `heat.uea` and `plumb.uea`.

On the left the generators and the tanks; from each, supply (red) and return (blue) run to its
manifolds, one row each, and to the radiators it feeds directly. Under a manifold's header each
underfloor heating has one loop per derived loop and each radiator a box, with its room and
output. At the foot the drinking water: cold from the meter, hot from the tanks that heat it, to
each fixture. The diagram follows the `src=` links and the derived loops; it is 1:1 and the
title block says "o. M.".
"""

from dataclasses import dataclass, field
from itertools import pairwise

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Poly, Pt, Sheet
from uea.export.paper import BLACK, BLOCK_H, BLOCK_W, GREY, PAPER, Paper, Stand, de, frame
from uea.export.tables import USE_DE
from uea.export.tga import FIXTURE_DE
from uea.packs.heat.geometry import heat_type, tank_type
from uea.packs.heat.kinds import GenType, ManType, RadType
from uea.packs.plumb.kinds import San

H_SCHEMA = "H-SCHEMA"
VL = "#c0392b"
RL = "#1f77b4"
PWH = "#ff7f0e"
PWC = "#2ca02c"
COL = 17.0
"""Width of the column of a loop or radiator, in mm."""
ROW_H = 66.0
"""Height of a manifold's row, in mm."""
X_HEAD = 160.0
"""Where the headers and the fixtures start, in mm."""
BOX_H = 34.0
FIX_W = 24.0


@dataclass
class Branch:
    """One row of the diagram: a manifold, or the radiators a tank or generator feeds itself."""

    key: str
    src: str
    """Where the row gets its heat: the manifold's source, or the tank or generator itself."""
    title: str
    columns: list[tuple[str, int, int]] = field(default_factory=list[tuple[str, int, int]])
    """(emitter, loop k, loops n); a radiator is one column with n 0."""
    y: float = 0.0


class Diagram(Paper):
    """A diagram drawn 1:1 in mm from its top left corner, on the first paper it fits."""

    layer: str = H_SCHEMA
    width: float = 0.0
    height: float = 0.0
    ox: float = 0.0
    oy: float = 0.0

    # ---------- coordinates ----------

    def P(self, x: float, y: float) -> Pt:
        return self.sh.pt(self.ox + x, self.oy - y)

    def line(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        color: str,
        mm: float = 0.5,
        dash: tuple[float, ...] = (),
    ) -> None:
        pen = self.pen(mm, color, dash)
        self.dw.add(Line(self.P(x0, y0), self.P(x1, y1), pen, self.layer))

    def box(self, x0: float, y0: float, x1: float, y1: float, fill: str = "#f4f4f4") -> None:
        pts = [self.P(x0, y0), self.P(x1, y0), self.P(x1, y1), self.P(x0, y1)]
        self.dw.add(Poly(pts, fill, self.pen(0.35), self.layer))

    def say(
        self,
        x: float,
        y: float,
        txt: str,
        mm: float = 2.0,
        *,
        anchor: str = "middle",
        bold: bool = False,
        color: str = BLACK,
    ) -> None:
        self.text(self.P(x, y), txt, mm, self.layer, anchor=anchor, bold=bold, color=color)

    # ---------- the sheet ----------

    def sheet(self) -> Sheet:
        """The first paper whose frame holds the diagram above the title block's top."""
        for size in ("A3", "A2", "A1", "A0"):
            fx0, fy0, fx1, fy1 = frame(PAPER[size])
            if self.width <= fx1 - fx0 - 8 and self.height <= fy1 - fy0 - BLOCK_H - 10:
                self.ox, self.oy = fx0 + 6, fy1 - 4
                return Sheet(size, PAPER[size], 1, (0.0, 0.0))
        fx0, _, _, fy1 = frame(PAPER["A0"])
        self.ox, self.oy = fx0 + 6, fy1 - 4
        return Sheet("A0", PAPER["A0"], 1, (0.0, 0.0))


class Schema(Diagram):
    def __init__(self, d: Derived, stand: Stand) -> None:
        self.heading = "Heizungs- und Trinkwasserschema"
        super().__init__(d, stand, self.heading)
        h, m = d.heat, d.model
        self.gens = sorted((el.id for el in m.of_kind("gen")), key=natural)
        self.tanks = sorted((el.id for el in m.of_kind("tank")), key=natural)
        self.rows: list[Branch] = []
        for el in m.of_kind("man"):
            src = getattr(el, "src").id  # noqa: B009
            self.rows.append(Branch(el.id, src, self.man_title(el.id), self.columns(el.id)))
        for k in [*self.tanks, *self.gens]:
            direct = [x for x in h.supplies.get(k, []) if m[x].kind == "rad"]
            if direct:
                b = Branch(k, k, f"Heizkörper direkt an {k}", [(x, 1, 0) for x in direct])
                self.rows.append(b)
        self.sources = list(dict.fromkeys(b.src for b in self.rows))
        p = d.plumb
        self.fixtures = sorted(
            (
                k
                for k, mt in p.at.items()
                if mt.kind == "san" and getattr(m[k], "supply", "none") != "none"
            ),
            key=natural,
        )
        self.meter = next((el.id for el in m.of_kind("meter") if el.id in p.at), None)
        self.x_head = X_HEAD + 8.0 * max(len(self.sources) - 1, 0)
        widest = max([len(b.columns) for b in self.rows] + [0])
        self.width = max(self.x_head + widest * COL, self.x_head + len(self.fixtures) * FIX_W) + 8
        for i, b in enumerate(self.rows):
            b.y = 22.0 + i * ROW_H
        left = 22.0 + 45.0 * max(len(self.gens), len(self.tanks))
        self.y_water = max(22.0 + len(self.rows) * ROW_H, left) + 6.0
        self.height = self.y_water + (38.0 if self.fixtures else 0.0)
        self.ox = self.oy = 0.0

    # ---------- what is drawn ----------

    def man_title(self, key: str) -> str:
        mt = self.d.heat.at.get(key)
        el = self.m[key]
        t = heat_type(self.m, el, ManType, "man")
        loops = sum(
            self.d.heat.loops[x].n
            for x in self.d.heat.supplies.get(key, [])
            if x in self.d.heat.loops
        )
        rads = sum(1 for x in self.d.heat.supplies.get(key, []) if self.m[x].kind == "rad")
        outlets = f" von {t.outlets}" if t is not None else ""
        where = ""
        if mt is not None:
            host = getattr(el, "host").id  # noqa: B009
            kind = "Nische" if self.m[host].kind == "niche" else "Wand"
            where = f" in {kind} {host}"
        lv = f"{mt.level}: " if mt is not None else ""
        name = f" {t.id}" if t is not None else ""
        return f"{lv}{key} Heizkreisverteiler{name}{where} · {loops + rads}{outlets} Abgänge belegt"

    def columns(self, key: str) -> list[tuple[str, int, int]]:
        h = self.d.heat
        out: list[tuple[str, int, int]] = []
        for x in h.supplies.get(key, []):
            lp = h.loops.get(x)
            if lp is not None:
                n = max(lp.n, 1)
                out += [(x, k, lp.n) for k in range(1, n + 1)]
            else:
                out.append((x, 1, 0))
        return out

    def draw(self) -> Drawing | None:
        if not (self.rows or self.gens or self.tanks or self.fixtures):
            return None
        self.dw.sheet = self.sheet()
        self.say(0.0, 6.0, f"{self.heading} (Prinzip)", 3.5, anchor="start", bold=True)
        self.left()
        for b in self.rows:
            self.row(b)
        self.feeds()
        if self.fixtures:
            self.water()
        self.legend()
        self.title_block(self.heading, "Abgeleitet aus dem Modell, unmaßstäblich", "H-00", "o. M.")
        return self.dw

    def gen_y(self, k: str) -> float:
        return 22.0 + 45.0 * self.gens.index(k)

    def tank_y(self, k: str) -> float:
        return 22.0 + 45.0 * self.tanks.index(k)

    def src_xy(self, k: str) -> tuple[float, float]:
        """The right edge of a source box and the height of its supply."""
        if k in self.gens:
            return 50.0, self.gen_y(k) + 10.0
        return 130.0, self.tank_y(k) + 10.0

    def left(self) -> None:
        h = self.d.heat
        for k in self.gens:
            y = self.gen_y(k)
            self.box(0.0, y, 50.0, y + 28.0)
            el = self.m[k]
            t = heat_type(self.m, el, GenType, "gen")
            self.say(25.0, y + 6.0, f"{k} Wärmeerzeuger", 2.3, bold=True)
            self.say(25.0, y + 10.5, el.label or "", 1.7)
            if t is not None:
                self.say(25.0, y + 15.0, f"{t.id} · {de(t.kw, 1)} kW", 1.7)
            mt = h.at.get(k)
            if mt is not None:
                where = f"{mt.room} {mt.level}" if mt.room else f"außen, {mt.level}"
                self.say(25.0, y + 19.5, where, 1.5, color=GREY)
        for k in self.tanks:
            y = self.tank_y(k)
            self.box(70.0, y, 130.0, y + BOX_H)
            el = self.m[k]
            t = tank_type(self.d, el)
            self.say(100.0, y + 6.0, f"{k} Speicher", 2.3, bold=True)
            self.say(100.0, y + 10.5, el.label or "", 1.6)
            if t is not None:
                self.say(
                    100.0, y + 15.0, f"{t.id} · {t.vol:g} l" + (" · TWW" if t.dhw else ""), 1.7
                )
            src = getattr(el, "src", None)
            if src is not None and src.id in self.gens:
                gy = self.gen_y(src.id)
                for dy, color in ((10.0, VL), (16.0, RL)):
                    x_mid = 58.0 if color == VL else 62.0
                    self.line(50.0, gy + dy, x_mid, gy + dy, color)
                    self.line(x_mid, gy + dy, x_mid, y + dy, color)
                    self.line(x_mid, y + dy, 70.0, y + dy, color)

    def feeds(self) -> None:
        """From each source, supply and return down a trunk to the headers of its rows."""
        for i, src in enumerate(self.sources):
            if src not in self.gens and src not in self.tanks:
                continue
            x0, ys = self.src_xy(src)
            tx = 140.0 + 8.0 * i
            rows = [b for b in self.rows if b.src == src]
            for dy, color, dx in ((0.0, VL, 0.0), (6.0, RL, 3.0)):
                bottom = max(b.y + 8.0 + (5.0 if color == RL else 0.0) for b in rows)
                self.line(x0, ys + dy, tx + dx, ys + dy, color)
                self.line(tx + dx, min(ys + dy, bottom), tx + dx, max(ys + dy, bottom), color)
                for b in rows:
                    yy = b.y + 8.0 + (5.0 if color == RL else 0.0)
                    self.line(tx + dx, yy, self.x_head, yy, color)

    def row(self, b: Branch) -> None:
        h = self.d.heat
        end = self.x_head + max(len(b.columns), 1) * COL
        self.say(self.x_head, b.y + 3.0, b.title, 2.2, anchor="start", bold=True)
        self.line(self.x_head, b.y + 8.0, end, b.y + 8.0, VL, 0.8)
        self.line(self.x_head, b.y + 13.0, end, b.y + 13.0, RL, 0.8)
        for c, (key, k, n) in enumerate(b.columns):
            x = self.x_head + c * COL + COL / 2
            el = self.m[key]
            self.line(x - 2.0, b.y + 8.0, x - 2.0, b.y + 20.0, VL, 0.25)
            self.line(x + 2.0, b.y + 13.0, x + 2.0, b.y + 20.0, RL, 0.25)
            if el.kind == "ufh":
                self.loop(x, b.y + 20.0)
            else:
                self.radiator(x, b.y + 20.0)
            room = self.room_of(key)
            self.say(x, b.y + 47.0, f"{key} {room or ''}".strip(), 1.6, bold=True)
            self.say(x, b.y + 50.5, self.room_name(room), 1.4)
            if el.kind == "ufh":
                lp = h.loops.get(key)
                self.say(x, b.y + 54.0, f"Kreis {k}/{n}" if n else "zu weit", 1.3, color=GREY)
                if k == 1 and lp is not None:
                    self.say(x, b.y + 57.5, f"{de(lp.area, 1)} m²", 1.3, color=GREY)
                    w = h.output.get(key)
                    if w is not None:
                        self.say(x, b.y + 61.0, f"{w:.0f} W", 1.3, color=GREY)
            else:
                t = heat_type(self.m, el, RadType, "rad")
                self.say(x, b.y + 54.0, f"{t.w:.0f} W" if t else "Heizkörper", 1.3, color=GREY)

    def loop(self, x: float, y: float) -> None:
        """A loop: a zigzag from the supply down and back to the return."""
        pts = [(x - 2.0, y)]
        for k in range(6):
            pts.append((x + (2.8 if k % 2 == 0 else -2.8), y + 3.0 + k * 3.4))
        pts.append((x + 2.0, y + 22.0))
        for (x0, y0), (x1, y1) in pairwise(pts):
            self.line(x0, y0, x1, y1, VL, 0.18)

    def radiator(self, x: float, y: float) -> None:
        self.box(x - 4.0, y + 2.0, x + 4.0, y + 18.0, "#ffffff")
        for k in range(1, 4):
            self.line(x - 4.0 + 2.0 * k, y + 2.0, x - 4.0 + 2.0 * k, y + 18.0, VL, 0.13)

    def room_of(self, key: str) -> str | None:
        el = self.m[key]
        room = getattr(el, "room", None)
        if room is not None:
            return str(room.id)
        mt = self.d.heat.at.get(key) or self.d.plumb.at.get(key)
        return mt.room if mt is not None else None

    def room_name(self, room: str | None) -> str:
        if room is None or room not in self.m:
            return ""
        el = self.m[room]
        return el.label or USE_DE.get(getattr(el, "use", ""), "")

    def water(self) -> None:
        p = self.d.plumb
        y = self.y_water
        self.say(self.x_head, y, "Trinkwasser-Entnahmestellen", 2.2, anchor="start", bold=True)
        hot_y, cold_y, box_y = y + 6.0, y + 12.0, y + 24.0
        end = self.x_head + len(self.fixtures) * FIX_W
        self.line(self.x_head - 6.0, cold_y, end, cold_y, PWC, 0.6)
        if self.meter is not None:
            self.box(0.0, cold_y - 6.0, 50.0, cold_y + 6.0)
            el = self.m[self.meter]
            pressure = getattr(el, "p", None)
            self.say(25.0, cold_y - 1.0, f"{self.meter} Hausanschluss", 2.0, bold=True)
            self.say(25.0, cold_y + 3.4, f"{pressure:g} bar" if pressure else "", 1.6, color=GREY)
            self.line(50.0, cold_y, self.x_head - 6.0, cold_y, PWC, 0.6)
        if p.hot:
            self.line(self.x_head - 3.0, hot_y, end, hot_y, PWH, 0.6)
        for t in p.hot:
            if t not in self.tanks:
                continue
            ty = self.tank_y(t) + BOX_H
            self.line(110.0, ty, 110.0, hot_y, PWH, 0.6)
            self.line(110.0, hot_y, self.x_head - 3.0, hot_y, PWH, 0.6)
            self.line(90.0, ty, 90.0, cold_y, PWC, 0.6)
            self.say(112.0, ty + 4.0, "PWH", 1.5, anchor="start", color=PWH)
            self.say(88.0, ty + 4.0, "PWC", 1.5, anchor="end", color=PWC)
        for i, k in enumerate(self.fixtures):
            x = self.x_head + i * FIX_W
            el = self.m[k]
            assert isinstance(el, San)
            self.line(x + 8.0, cold_y, x + 8.0, box_y, PWC, 0.35)
            if k in p.hot_from:
                self.line(x + 15.0, hot_y, x + 15.0, box_y, PWH, 0.35)
            self.box(x + 1.0, box_y, x + FIX_W - 1.0, box_y + 11.0, "#ffffff")
            name = FIXTURE_DE[el.fixture][1]
            self.say(x + FIX_W / 2, box_y + 4.6, f"{k} {name}", 1.5, bold=True)
            room = p.at[k].room
            self.say(x + FIX_W / 2, box_y + 8.4, f"{room or ''} {self.room_name(room)}", 1.3)

    def legend(self) -> None:
        sh = self.sh
        fx0, fy0, _, _ = frame(sh.paper)
        x, y = fx0 + 6.0, fy0 + BLOCK_H - 6.0
        items = (
            (VL, "Heizung Vorlauf"),
            (RL, "Heizung Rücklauf"),
            (PWH, "Trinkwasser warm (PWH)"),
            (PWC, "Trinkwasser kalt (PWC)"),
        )
        for k, (color, txt) in enumerate(items):
            yy = y - k * 5.0
            self.dw.add(Line(sh.pt(x, yy), sh.pt(x + 10.0, yy), self.pen(0.6, color), H_SCHEMA))
            self.text(sh.pt(x + 13.0, yy - 0.8), txt, 2.0, H_SCHEMA, anchor="start")
        notes = [
            "Kreise je Raum abgeleitet aus Fläche, Verlegeabstand und längstem Kreis des Typs;",
            "Leistung nach Herstellerangabe im Typ. Zuordnung nach den src-Angaben des Modells.",
            "Trinkwasser: kalt vom Hausanschluss, warm vom nächsten Speicher mit TWW.",
            "Nicht dargestellt: Pumpen, Ventile, Sicherheitsgruppe, Ausdehnungsgefäß, Zirkulation.",
        ]
        width = max(len(n) for n in notes) * 0.95 + 70.0
        nx = x + 70.0
        if nx + width > frame(sh.paper)[2] - BLOCK_W:
            nx = x
            y -= 22.0
        for k, t in enumerate(notes):
            self.text(sh.pt(nx, y - k * 4.4 - 0.8), t, 1.8, H_SCHEMA, anchor="start", color=GREY)


def sheet_schema(d: Derived, stand: Stand | None = None) -> Drawing | None:
    """The Heizungs- und Trinkwasserschema; none if there is no heating and no water."""
    return Schema(d, stand or Stand()).draw()

"""The electrical installation plan of a storey (decision 0026): the floor plan in grey and the
devices on it, a symbol for each, coloured by circuit, with the circuit written beside it and
dashed lines from each switch to the luminaires it controls. A legend above the title block lists
the symbols and the circuits on the sheet. The title block stays unsigned.

Symbols are simplified (`symbols.py`); heights, positions and quantities are in the tables.
"""

from dataclasses import dataclass
from math import ceil

from shapely.ops import unary_union

from uea.core.registry import natural
from uea.derive import Derived
from uea.export import symbols as sy
from uea.export.drawing import Arc, Circle, Drawing, Item, Line, Pen, Poly
from uea.export.paper import (
    BLACK,
    BLOCK_H,
    BLOCK_W,
    GREY,
    L_DEMOLISH,
    L_DOOR,
    L_EXISTING,
    L_FINISH,
    L_LB,
    L_NICHE,
    L_NLB,
    L_STAIR,
    L_TEXT,
    L_VOID,
    L_WIN,
    Stand,
    fit_sheet,
    frame,
)
from uea.export.sheet import PlanSheet
from uea.export.symbols import Ink, Spot
from uea.export.tables import USE_DE
from uea.packs.arch.kinds import Room
from uea.packs.elec.kinds import Switch
from uea.packs.mount import Mounted

E_WALL = "E-GRUND-WAND"
E_DOOR = "E-GRUND-TUER"
E_WIN = "E-GRUND-FENSTER"
E_STAIR = "E-GRUND-TREPPE"
E_TEXT = "E-GRUND-TEXT"
E_SOCK = "E-STECKDOSE"
E_CONN = "E-ANSCHLUSS"
E_SWITCH = "E-SCHALTER"
E_LUM = "E-LEUCHTE"
E_SMOKE = "E-RAUCHMELDER"
E_DATA = "E-DATEN"
E_BOARD = "E-VERTEILER"
E_LINE = "E-SCHALTLINIE"
E_LABEL = "E-BESCHRIFTUNG"
E_LEGEND = "E-LEGENDE"
ELEC_LAYER_COLORS = {
    E_WALL: "#808080",
    E_DOOR: "#a08060",
    E_WIN: "#7090c0",
    E_STAIR: "#608080",
    E_TEXT: "#808080",
    E_SOCK: "#d62728",
    E_CONN: "#d62728",
    E_SWITCH: "#1f77b4",
    E_LUM: "#ff7f0e",
    E_SMOKE: "#555555",
    E_DATA: "#7a3fb0",
    E_BOARD: "#000000",
    E_LINE: "#888888",
    E_LABEL: "#000000",
    E_LEGEND: "#000000",
}
BACKGROUND = {
    L_LB: E_WALL,
    L_NLB: E_WALL,
    L_FINISH: E_WALL,
    L_EXISTING: E_WALL,
    L_DEMOLISH: E_WALL,
    L_DOOR: E_DOOR,
    L_WIN: E_WIN,
    L_NICHE: E_WIN,
    L_STAIR: E_STAIR,
    L_VOID: E_STAIR,
    L_TEXT: E_TEXT,
}
"""The floor plan's layers, as the background of an electrical plan."""
WALL_FILL = "#dcdcd6"
GREY_PEN = "#a0a0a0"
PALETTE = (
    "#d62728",
    "#1f77b4",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
    "#7f7f7f",
)
"""Circuit colours, in the order of the circuits; they repeat after ten."""
ROW = 3.6
"""Height of a line of the legend, in mm."""

SYMBOL_TEXT = {
    "sock": "Steckdose (ein Halbkreis je Auslass)",
    "conn": "Geräteanschluss",
    "switch": "Schalter (Strich je Kanal, beidseitig = Wechsel)",
    "lum": "Leuchte, Decke",
    "walllum": "Leuchte, Wand",
    "smoke": "Rauchwarnmelder",
    "data": "Datendose (ein Dreieck je Anschluss)",
    "board": "Verteiler",
    "line": "Schaltverbindung Schalter → Leuchte",
}


def circuit_colors(d: Derived) -> dict[str, str]:
    ids = sorted(d.elec.circuits, key=natural)
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(ids)}


FITS_INSTALL = (
    ("A3", 50),
    ("A3", 100),
    ("A2", 50),
    ("A2", 100),
    ("A1", 50),
    ("A1", 100),
    ("A0", 50),
    ("A0", 100),
    ("A0", 200),
)
"""Installation plans are drawn at 1:50 where they fit."""
SYMBOLS_W, COLUMN_W, MAX_ROWS, MAX_COLS = 66.0, 58.0, 12, 3
"""The legend: a column of symbols, then columns of circuits, in mm."""


@dataclass
class Legend:
    keys: list[str]
    circuits: list[str]
    """The circuits that fit; the rest is in the table."""
    more: int = 0

    @property
    def cols(self) -> int:
        return ceil(len(self.circuits) / MAX_ROWS) if self.circuits else 0

    @property
    def rows(self) -> int:
        return ceil(len(self.circuits) / self.cols) if self.cols else 0

    @property
    def strip(self) -> float:
        """The width of the legend left of the title block, in mm."""
        return SYMBOLS_W + self.cols * COLUMN_W + 2.0


class InstallPlan(PlanSheet):
    """The installation plan of one storey."""

    def __init__(self, d: Derived, level: str, stand: Stand) -> None:
        super().__init__(d, level, stand)
        self.heading = f"Elektroinstallation {self.level_name}"
        self.dw.title = f"{self.project}: {self.heading}"
        self.colors = circuit_colors(d)
        self.here = [
            mt for mt in sorted(d.mounts.values(), key=lambda m: natural(m.id)) if mt.level == level
        ]

    # ---------- what is on the sheet ----------

    def legend_of(self) -> Legend:
        e = self.d.elec
        keys: list[str] = []
        for mt in self.here:
            key = "walllum" if mt.kind == "lum" and mt.wall else mt.kind
            if key in SYMBOL_TEXT and key not in keys:
                keys.append(key)
        order = list(SYMBOL_TEXT)
        keys.sort(key=order.index)
        if any(mt.kind == "switch" for mt in self.here) and any(k.endswith("lum") for k in keys):
            keys.append("line")
        circuits: list[str] = []
        for mt in self.here:
            cid = self.circuit_of(mt)
            if cid is not None and cid in e.circuits and cid not in circuits:
                circuits.append(cid)
        ordered = sorted(circuits, key=natural)
        fit = MAX_ROWS * MAX_COLS
        return Legend(keys, ordered[:fit], max(0, len(ordered) - fit))

    def circuit_of(self, mt: Mounted) -> str | None:
        el = self.m[mt.id]
        circuit = getattr(el, "circuit", None)
        if circuit is not None:
            return str(circuit.id)
        if mt.kind == "lum":
            cs = self.d.elec.lum_circuits.get(mt.id)
            return cs[0] if cs else None
        return None

    def color_of(self, mt: Mounted) -> str:
        cid = self.circuit_of(mt)
        if cid is not None and cid in self.colors:
            return self.colors[cid]
        return {"data": "#7a3fb0", "board": BLACK}.get(mt.kind, "#555555")

    # ---------- the sheet ----------

    def draw(self) -> Drawing | None:
        bbox = self.bbox()
        if bbox is None or not self.here:
            return None
        legend = self.legend_of()
        need = dict.fromkeys("SNWE", 8.0)
        self.dw.sheet = fit_sheet(bbox, need, strip=legend.strip, fits=FITS_INSTALL)
        self.cut_all = unary_union([w.poly for w in self.live])
        self.stair_zone = unary_union(
            [s.poly.buffer(self.sh.m(5.0)) for s in self.g.stairs.values() if s.level == self.level]
        )
        start = len(self.dw.items)
        self.walls_and_openings()
        self.stairs_and_voids()
        ghost(self.dw.items[start:])
        self.names()
        self.switch_lines()
        for mt in self.here:
            self.device(mt)
        self.draw_legend(legend)
        self.caption(bbox, need)
        nr = f"E-{self.g.level_order().index(self.level) + 1:02d}"
        self.title_block(self.heading, "Symbole vereinfacht, in Anlehnung an DIN EN 60617", nr)
        return self.dw

    def names(self) -> None:
        """Room names in grey, so the plan reads."""
        for rg in self.g.rooms.values():
            if rg.level != self.level:
                continue
            el = self.m[rg.id]
            assert isinstance(el, Room)
            free = rg.fin.difference(self.stair_zone) if not self.stair_zone.is_empty else rg.fin
            if free.is_empty or free.area < 0.25 * rg.fin.area:
                free = rg.fin
            at = free.centroid
            if not free.contains(at):
                at = free.representative_point()
            name = el.label or USE_DE[el.use]
            self.text((at.x, at.y + self.sh.m(0.5)), name, 2.4, E_TEXT, bold=True, color="#9a9a9a")
            self.text((at.x, at.y - self.sh.m(2.4)), rg.id, 1.6, E_TEXT, color="#9a9a9a")

    def spot_of(self, mt: Mounted) -> Spot:
        if mt.wall is None:
            return Spot(mt.point)
        w = self.g.walls[mt.wall]
        sign = 1.0 if mt.face == "hi" else -1.0
        return Spot(mt.point, w.u, (sign * w.n[0], sign * w.n[1]))

    def switch_lines(self) -> None:
        """A dashed line from each switch to each luminaire it controls, on the same storey."""
        for mt in self.here:
            el = self.m[mt.id]
            if not isinstance(el, Switch):
                continue
            sp = self.spot_of(mt)
            ink = Ink(self.dw, self.sh, sp, self.color_of(mt), E_LINE)
            start = ink.at(0.0, 1.3)
            pen = Pen(self.color_of(mt), self.sh.m(0.13), (self.sh.m(1.2), self.sh.m(0.8)))
            for ref in el.ctl.refs():
                target = self.d.mounts.get(ref)
                if target is not None and target.level == self.level:
                    self.dw.add(Line(start, target.point, pen, E_LINE))

    def device(self, mt: Mounted) -> None:
        el = self.m[mt.id]
        ink = Ink(self.dw, self.sh, self.spot_of(mt), self.color_of(mt), E_LABEL)
        reach = 2.0
        if mt.kind == "sock":
            ink.layer = E_SOCK
            reach = sy.sock(ink, int(getattr(el, "n", 1)))
        elif mt.kind == "conn":
            ink.layer = E_CONN
            reach = sy.conn(ink)
        elif mt.kind == "switch":
            assert isinstance(el, Switch)
            ink.layer = E_SWITCH
            two_way = any(len(self.d.elec.controls.get(r, [])) >= 2 for r in el.ctl.refs())
            reach = sy.switch(ink, len(el.ctl.groups), two_way, el.dim)
        elif mt.kind == "lum":
            ink.layer = E_LUM
            reach = sy.lum(ink, mt.wall is not None)
        elif mt.kind == "smoke":
            ink.layer = E_SMOKE
            reach = sy.smoke(ink)
        elif mt.kind == "data":
            ink.layer = E_DATA
            reach = sy.data(ink, int(getattr(el, "n", 1)))
        elif mt.kind == "board":
            ink.layer = E_BOARD
            reach = sy.board(ink, self.sh.mm(mt.width))
        ink.layer = E_LABEL
        cid = self.circuit_of(mt)
        if mt.kind == "lum":
            ink.color = GREY
            ink.text(0.0, -3.6 if mt.wall is None else reach + 1.9, mt.id, 1.4)
        elif mt.kind == "board":
            ink.text(0.0, reach + 1.9, f"{mt.id}", 1.8, True)
        elif cid is not None:
            ink.text(0.0, reach + 1.9, cid, 1.5)

    # ---------- the legend ----------

    def draw_legend(self, legend: Legend) -> None:
        """The legend stands left of the title block and is as high as it."""
        sh = self.sh
        _, y0, x1, _ = frame(sh.paper)
        top = y0 + BLOCK_H
        bx = x1 - BLOCK_W - legend.strip
        self.rect(bx, y0, x1 - BLOCK_W, top, self.pen(0.7), E_LEGEND)
        self.text(sh.pt(bx + 2, top - 4.2), "Legende", 2.4, E_LEGEND, anchor="start", bold=True)
        y = top - 7.0
        for key in legend.keys:
            self.legend_symbol(key, bx + 6.0, y - 0.8)
            self.text(sh.pt(bx + 12.0, y - 1.3), SYMBOL_TEXT[key], 1.6, E_LEGEND, anchor="start")
            y -= ROW
        e = self.d.elec
        for i, cid in enumerate(legend.circuits):
            col, row = divmod(i, legend.rows)
            cx = bx + SYMBOLS_W + col * COLUMN_W
            cy = top - 7.0 - row * ROW
            cg = e.circuits[cid]
            el = self.m[cid]
            self.dw.add(
                Poly(
                    [
                        sh.pt(cx, cy - 2.2),
                        sh.pt(cx + 2.4, cy - 2.2),
                        sh.pt(cx + 2.4, cy),
                        sh.pt(cx, cy),
                    ],
                    self.colors[cid],
                    None,
                    E_LEGEND,
                )
            )
            label = f" {el.label}" if el.label else ""
            phases = "3p " if cg.phases == 3 else ""
            self.text(
                sh.pt(cx + 3.4, cy - 1.7),
                f"{cid} {cg.breaker.fmt()} {phases}{getattr(el, 'cable').fmt()}{label}",  # noqa: B009
                1.5,
                E_LEGEND,
                anchor="start",
            )
        if legend.more:
            self.text(
                sh.pt(bx + 2, y0 + 3.0),
                f"+ {legend.more} weitere Stromkreise: siehe Tabelle Stromkreise",
                1.5,
                E_LEGEND,
                anchor="start",
            )

    def legend_symbol(self, key: str, x: float, y: float) -> None:
        sh = self.sh
        spot = Spot(sh.pt(x, y))
        ink = Ink(self.dw, sh, spot, BLACK, E_LEGEND)
        if key == "sock":
            sy.sock(ink, 2)
        elif key == "conn":
            sy.conn(ink)
        elif key == "switch":
            sy.switch(ink, 1, True)
        elif key == "lum":
            sy.lum(ink)
        elif key == "walllum":
            sy.lum(ink, True)
        elif key == "smoke":
            sy.smoke(ink)
        elif key == "data":
            sy.data(ink, 1)
        elif key == "board":
            sy.board(ink)
        elif key == "line":
            pen = Pen(BLACK, sh.m(0.13), (sh.m(1.2), sh.m(0.8)))
            self.dw.add(Line(sh.pt(x - 3.0, y), sh.pt(x + 3.0, y), pen, E_LEGEND))


def ghost(items: list[Item]) -> None:
    """Turn the floor plan into a background: grey fills and lines, on the background layers."""
    for it in items:
        it.layer = BACKGROUND.get(it.layer, it.layer)
        if isinstance(it, Poly):
            if it.fill is not None:
                it.fill = WALL_FILL
            if it.pen is not None:
                it.pen = Pen(GREY_PEN, it.pen.width, it.pen.dash)
        elif isinstance(it, Line | Arc | Circle):
            it.pen = Pen(GREY_PEN, it.pen.width, it.pen.dash)
        else:
            it.color = "#9a9a9a"


def sheet_install(d: Derived, level: str, stand: Stand | None = None) -> Drawing | None:
    """The installation plan of a storey; none if nothing electrical is on it."""
    return InstallPlan(d, level, stand or Stand()).draw()

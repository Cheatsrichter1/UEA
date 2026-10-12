"""The heating and the plumbing plan of a storey (decision 0036): the floor plan in grey, as on
the installation plan (`install.py`), and the elements of `heat.uea` or `plumb.uea` on it.

Heating: each underfloor heating fills its room in pale red, with its loops and output beside
the room's name, and a dashed line to its manifold; manifolds, radiators, generators and tanks
as symbols; the derived heating pipes (decision 0037) as right-angled lines, flow red, return
blue and dashed, side by side, with a ring where a pipe rises to another storey.

Plumbing: the fixtures, the meter, risers, stacks and the sewer connection as symbols, and the
derived pipes as right-angled lines, cold water green, hot water orange, waste water brown and
dashed.

Ventilation (decision 0038): the central units, the decentral units with a dashed line to their
pair, the air terminals, and the derived ducts side by side: outdoor air green, supply blue,
extract yellow, exhaust brown. The pipes are the derived shortest trees, not routes a planner chose.
"""

import math
from dataclasses import replace
from itertools import pairwise

from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon
from shapely.ops import nearest_points, unary_union

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.drawing import Drawing, Line, Pen, Pt
from uea.export.install import FITS_INSTALL, ROW, InstallPlan, ghost
from uea.export.paper import BLACK, BLOCK_H, BLOCK_W, Stand, de, fit_sheet, frame, poly_item
from uea.export.symbols import Ink, Spot
from uea.packs.heat.geometry import heat_type
from uea.packs.heat.kinds import GenType, Ufh
from uea.packs.mount import Mounted
from uea.packs.net import Net
from uea.packs.plumb.geometry import nets
from uea.packs.plumb.kinds import San

H_UFH = "H-FUSSBODENHEIZUNG"
H_MAN = "H-VERTEILER"
H_RAD = "H-HEIZKOERPER"
H_GEN = "H-ERZEUGER"
H_LINK = "H-ANBINDUNG"
H_FLOW = "H-VORLAUF"
H_RETURN = "H-RUECKLAUF"
H_LABEL = "H-BESCHRIFTUNG"
H_LEGEND = "H-LEGENDE"
S_FIX = "S-OBJEKT"
S_NODE = "S-ANSCHLUSS"
S_COLD = "S-TRINKWASSER-KALT"
S_HOT = "S-TRINKWASSER-WARM"
S_WASTE = "S-ABWASSER"
S_CIRC = "S-ZIRKULATION"
S_LABEL = "S-BESCHRIFTUNG"
S_LEGEND = "S-LEGENDE"
L_UNIT = "L-GERAET"
L_TERMINAL = "L-DURCHLASS"
L_ODA = "L-AUSSENLUFT"
L_SUP = "L-ZULUFT"
L_ETA = "L-ABLUFT"
L_EHA = "L-FORTLUFT"
L_LABEL = "L-BESCHRIFTUNG"
L_LEGEND = "L-LEGENDE"
RED = "#c0392b"
UFH_FILL = "#f8dcd8"
BLUE = "#1f5fbf"
COLD = "#2ca02c"
HOT = "#ff7f0e"
WASTE = "#8c564b"
CIRC = "#9467bd"
AIR = {"oda": "#2ca02c", "sup": "#1f77b4", "ext": "#d4a017", "eha": "#8c564b"}
AIR_LAYER = {"oda": L_ODA, "sup": L_SUP, "ext": L_ETA, "eha": L_EHA}
AIR_OFF = {"oda": 1.05, "sup": 0.35, "ext": -0.35, "eha": -1.05}
AIR_MARK = {"oda": "AU", "sup": "ZU", "ext": "AB", "eha": "FO"}
TGA_LAYER_COLORS = {
    H_UFH: RED,
    H_MAN: RED,
    H_RAD: RED,
    H_GEN: RED,
    H_LINK: RED,
    H_FLOW: RED,
    H_RETURN: BLUE,
    H_LABEL: BLACK,
    H_LEGEND: BLACK,
    S_FIX: "#1f77b4",
    S_NODE: BLACK,
    S_COLD: COLD,
    S_HOT: HOT,
    S_WASTE: WASTE,
    S_CIRC: CIRC,
    S_LABEL: BLACK,
    S_LEGEND: BLACK,
    L_UNIT: "#1f77b4",
    L_TERMINAL: "#1f77b4",
    L_ODA: AIR["oda"],
    L_SUP: AIR["sup"],
    L_ETA: AIR["ext"],
    L_EHA: AIR["eha"],
    L_LABEL: BLACK,
    L_LEGEND: BLACK,
}
FIXTURE_DE = {
    "basin": ("WT", "Waschtisch"),
    "sink": ("SP", "Spüle"),
    "wc": ("WC", "WC"),
    "urinal": ("UR", "Urinal"),
    "bidet": ("BD", "Bidet"),
    "shower": ("DU", "Dusche"),
    "bath": ("BW", "Badewanne"),
    "wm": ("WM", "Waschmaschine"),
    "dw": ("GS", "Geschirrspüler"),
    "tap": ("AV", "Außenzapfstelle"),
    "floor": ("BA", "Bodenablauf"),
}
"""Short mark on the plan and the German name of each fixture."""
HEAT_KEYS = {
    "ufh": "Fußbodenheizung (Fläche, Kreise, Leistung)",
    "man": "Heizkreisverteiler",
    "rad": "Heizkörper",
    "gen": "Wärmeerzeuger",
    "tank": "Speicher",
    "link": "Anbindung Verteiler – Raum",
    "flow": "Heizung Vorlauf",
    "ret": "Heizung Rücklauf",
    "rise": "Leitung in ein anderes Geschoss",
}
PLUMB_KEYS = {
    "san": "Sanitärobjekt",
    "meter": "Hausanschluss mit Wasserzähler",
    "riser": "Steigleitung (TW kalt/warm)",
    "stack": "Fallleitung",
    "sewer": "Anschluss Kanal",
    "tank": "Speicher mit Trinkwassererwärmung",
    "cold": "Trinkwasser kalt (PWC)",
    "hot": "Trinkwasser warm (PWH)",
    "circ": "Zirkulation (PWH-C)",
    "waste": "Schmutzwasser",
}
VENT_KEYS = {
    "ahu": "Lüftungsgerät mit Wärmerückgewinnung",
    "fan": "Dezentrales Lüftungsgerät (Paar gestrichelt)",
    "air": "Luftdurchlass (ZU, AB, AU, FO)",
    "oda": "Außenluft",
    "sup": "Zuluft",
    "ext": "Abluft",
    "eha": "Fortluft",
    "rise": "Leitung in ein anderes Geschoss",
}
STRIP = 72.0
"""Width of the legend left of the title block, in mm."""


class TgaPlan(InstallPlan):
    """The heating or plumbing plan of one storey."""

    def __init__(self, d: Derived, level: str, stand: Stand, pack: str) -> None:
        super().__init__(d, level, stand)
        self.pack = pack
        name = {"heat": "Heizung", "plumb": "Sanitär", "vent": "Lüftung"}[pack]
        self.heading = f"{name} {self.level_name}"
        self.dw.title = f"{self.project}: {self.heading}"
        at = {"heat": d.heat.at, "plumb": d.plumb.at, "vent": d.vent.at}[pack]
        here = [mt for mt in at.values() if mt.level == level]
        if pack == "plumb":
            # risers and stacks pass through the storeys above their own
            seen = {mt.id for mt in here}
            for net in nets(d):
                for k, nd in net.nodes.items():
                    rid = k.partition(":")[0]
                    if ":" in k and nd.level == level and rid not in seen and rid in at:
                        seen.add(rid)
                        here.append(replace(at[rid], level=level, z=nd.z, room=None))
            # the tanks the hot water comes from
            here += [d.heat.at[t] for t in d.plumb.hot if d.heat.at[t].level == level]
        self.here = sorted(here, key=lambda m: natural(m.id))
        self.ufh = [
            el
            for el in d.model.of_kind("ufh")
            if isinstance(el, Ufh) and pack == "heat" and _room_level(d, el.room.id) == level
        ]

    def draw(self) -> Drawing | None:
        bbox = self.bbox()
        if bbox is None or not (self.here or self.ufh):
            return None
        need = dict.fromkeys("SNWE", 8.0)
        self.dw.sheet = fit_sheet(bbox, need, strip=STRIP, fits=FITS_INSTALL, extra=self.north_room)
        self.cut_all = unary_union([w.poly for w in self.live])
        self.stair_zone = unary_union(
            [s.poly.buffer(self.sh.m(5.0)) for s in self.g.stairs.values() if s.level == self.level]
        )
        if self.pack == "heat":
            self.floors()
        start = len(self.dw.items)
        self.walls_and_openings()
        self.stairs_and_voids()
        ghost(self.dw.items[start:])
        self.names()
        if self.pack == "heat":
            self.links()
            self.heat_pipes()
            for mt in self.here:
                self.heat_symbol(mt)
            keys = HEAT_KEYS
            note = "Kreise, Leistung und Leitungen abgeleitet; kürzester Baum, keine Trasse"
            nr = f"H-{self.g.level_order().index(self.level) + 1:02d}"
        elif self.pack == "plumb":
            self.pipes()
            for mt in self.here:
                self.plumb_symbol(mt)
            keys = PLUMB_KEYS
            note = "Leitungen abgeleitet: kürzester rechtwinkliger Baum, keine Trasse"
            nr = f"S-{self.g.level_order().index(self.level) + 1:02d}"
        else:
            self.ducts()
            self.pair_lines()
            for mt in self.here:
                self.vent_symbol(mt)
            keys = VENT_KEYS
            note = "Luftleitungen abgeleitet: kürzester rechtwinkliger Baum, keine Trasse"
            nr = f"L-{self.g.level_order().index(self.level) + 1:02d}"
        self.legend(keys)
        self.caption(bbox, need)
        self.north_arrow()
        self.title_block(self.heading, note, nr)
        return self.dw

    # ---------- heating ----------

    def floors(self) -> None:
        for el in self.ufh:
            rg = self.g.rooms.get(el.room.id)
            if rg is None:
                continue
            for piece in getattr(rg.fin, "geoms", [rg.fin]):
                if isinstance(piece, Polygon):
                    self.dw.add(poly_item(piece, UFH_FILL, self.pen(0.18, RED), H_UFH))

    def names(self) -> None:
        super().names()
        if self.pack != "heat":
            return
        h = self.d.heat
        for el in self.ufh:
            rg = self.g.rooms.get(el.room.id)
            lp = h.loops.get(el.id)
            if rg is None or lp is None:
                continue
            free = rg.fin.difference(self.stair_zone) if not self.stair_zone.is_empty else rg.fin
            if free.is_empty or free.area < 0.25 * rg.fin.area:
                free = rg.fin
            at = free.centroid if free.contains(free.centroid) else free.representative_point()
            loops = f"{lp.n} Kreis{'e' if lp.n != 1 else ''}" if lp.n else "zu weit"
            w = h.output.get(el.id)
            power = f" · {w:.0f} W" if w is not None else ""
            txt = f"{el.id} · {de(lp.area, 1)} m² · {loops}{power}"
            self.text((at.x, at.y - self.sh.m(5.4)), txt, 1.8, H_LABEL, color=RED)

    def links(self) -> None:
        """A dashed line from each manifold to the rooms of its underfloor heating."""
        pen = Pen(RED, self.sh.m(0.18), (self.sh.m(1.5), self.sh.m(1.0)))
        for el in self.ufh:
            man = self.d.heat.at.get(el.src.id)
            rg = self.g.rooms.get(el.room.id)
            if man is None or rg is None or man.level != self.level:
                continue
            p = SPoint(man.point)
            if rg.fin.covers(p):
                continue
            q = nearest_points(rg.fin, p)[0]
            self.dw.add(Line(man.point, (q.x, q.y), pen, H_LINK))

    def heat_pipes(self) -> None:
        """Flow and return of each heating pipe, right-angled on the storey of its upper end
        (toward the generator), with a ring where it rises or falls to its other end."""
        flow = Pen(RED, self.sh.m(0.35))
        ret = Pen(BLUE, self.sh.m(0.35), (self.sh.m(2.0), self.sh.m(1.0)))
        for net in self.d.heat.nets.values():
            for pen, layer, off in ((flow, H_FLOW, 0.35), (ret, H_RETURN, -0.35)):
                self.net_lines(net, pen, layer, off, across=True)

    def heat_symbol(self, mt: Mounted) -> None:
        el = self.m[mt.id]
        ink = Ink(self.dw, self.sh, self.spot_of(mt), RED, H_MAN)
        reach = 2.0
        label = mt.id
        if mt.kind == "man":
            w = self.sh.mm(max(mt.width, 0.3)) / 2
            ink.poly([(-w, 0.0), (w, 0.0), (w, 1.6), (-w, 1.6)], "#ffffff", 0.35)
            ink.text(0.0, 0.35, "HV", 1.1, True)
            reach = 1.6
        elif mt.kind == "rad":
            ink.layer = H_RAD
            w = self.sh.mm(mt.width) / 2
            ink.poly([(-w, 0.4), (w, 0.4), (w, 1.6), (-w, 1.6)], "#ffffff", 0.35)
            for k in range(1, 6):
                a = -w + 2 * w * k / 6
                ink.line(a, 0.4, a, 1.6, 0.13)
            w = self.d.heat.output.get(mt.id)
            label = f"{mt.id} {w:.0f} W" if w is not None else mt.id
            reach = 1.6
        elif mt.kind == "gen":
            ink.layer = H_GEN
            ink.poly([(-2.5, -2.5), (2.5, -2.5), (2.5, 2.5), (-2.5, 2.5)], "#ffffff", 0.35)
            ink.text(0.0, -0.6, "WE", 1.6, True)
            t = heat_type(self.m, el, GenType, "gen")
            label = f"{mt.id} {de(t.kw, 1)} kW" if t is not None else mt.id
            reach = 2.5
        elif mt.kind == "tank":
            ink.layer = H_GEN
            ink.circle(0.0, 0.0, 2.6, "#ffffff", 0.35)
            ink.text(0.0, -0.6, "SP", 1.6, True)
            reach = 2.6
        ink.layer = H_LABEL
        ink.color = BLACK
        ink.text(0.0, reach + 1.9, label, 1.5)

    # ---------- plumbing ----------

    def pipes(self) -> None:
        """Each section of the derived networks with both ends on this storey, right-angled:
        first along x, then along y. Cold, hot and waste water lie side by side."""
        p = self.d.plumb
        nets: list[tuple[Net, str, str, float, tuple[float, ...]]] = []
        if p.cold is not None:
            nets.append((p.cold, COLD, S_COLD, 0.0, ()))
        for net in p.hot.values():
            nets.append((net, HOT, S_HOT, 0.7, ()))
        for net in p.recirc.values():
            nets.append((net, CIRC, S_CIRC, 1.4, (1.2, 0.6)))
        if p.drain is not None:
            nets.append((p.drain, WASTE, S_WASTE, -0.7, (2.0, 1.0)))
        for net, color, layer, off, dash in nets:
            pen = Pen(color, self.sh.m(0.35), tuple(self.sh.m(x) for x in dash))
            self.net_lines(net, pen, layer, off)

    def net_lines(self, net: Net, pen: Pen, layer: str, off: float, across: bool = False) -> None:
        """Each section with both ends on this storey, first along x, then along y. With across,
        a section to another storey is drawn on the storey of its end a, and both storeys get
        a ring at its end b."""
        o = self.sh.m(off)
        for s in net.sections:
            a, b = net.nodes[s.a], net.nodes[s.b]
            if a.level != b.level and across:
                if self.level in (a.level, b.level) and off > 0:
                    r = self.sh.m(1.0)
                    c = (b.point[0], b.point[1])
                    ring = [(c[0] + r * dx, c[1] + r * dy) for dx, dy in _RING]
                    for u, v in pairwise(ring):
                        self.dw.add(Line(u, v, Pen(pen.color, self.sh.m(0.25)), layer))
                if a.level != self.level:
                    continue
            elif a.level != self.level or b.level != self.level:
                continue
            pts: list[Pt] = [
                (a.point[0] + o, a.point[1] + o),
                (b.point[0] + o, a.point[1] + o),
                (b.point[0] + o, b.point[1] + o),
            ]
            for u, v in pairwise(pts):
                if abs(u[0] - v[0]) + abs(u[1] - v[1]) > 1e-6:
                    self.dw.add(Line(u, v, pen, layer))

    def plumb_symbol(self, mt: Mounted) -> None:
        el = self.m[mt.id]
        ink = Ink(self.dw, self.sh, self.spot_of(mt), "#1f77b4", S_FIX)
        reach = 2.0
        if isinstance(el, San):
            mark = FIXTURE_DE[el.fixture][0]
            b0 = 0.0 if mt.wall else -1.6
            ink.poly([(-2.4, b0), (2.4, b0), (2.4, b0 + 3.2), (-2.4, b0 + 3.2)], "#ffffff", 0.35)
            ink.text(0.0, b0 + 1.0, mark, 1.5, True)
            reach = b0 + 3.2
        else:
            ink.layer, ink.color = S_NODE, BLACK
            if mt.kind == "meter":
                ink.circle(0.0, 0.0, 2.0, "#ffffff", 0.35)
                ink.text(0.0, -0.5, "WZ", 1.3, True)
            elif mt.kind == "riser":
                ink.color = COLD
                ink.circle(0.0, 0.0, 1.6, "#ffffff", 0.35)
                ink.circle(0.0, 0.0, 0.5, COLD, 0.18)
            elif mt.kind == "stack":
                ink.color = WASTE
                ink.circle(0.0, 0.0, 1.8, WASTE, 0.35)
            elif mt.kind == "tank":
                ink.color = HOT
                ink.circle(0.0, 0.0, 2.6, "#ffffff", 0.35)
                ink.text(0.0, -0.6, "SP", 1.6, True)
                reach = 2.6
            elif mt.kind == "sewer":
                ink.color = WASTE
                ink.poly([(-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)], "#ffffff", 0.35)
                ink.text(0.0, -0.5, "K", 1.5, True)
        ink.layer, ink.color = S_LABEL, BLACK
        ink.text(0.0, reach + 1.9, mt.id, 1.5)

    # ---------- ventilation ----------

    def ducts(self) -> None:
        for (_, role), net in self.d.vent.ducts.items():
            pen = Pen(AIR[role], self.sh.m(0.5))
            self.net_lines(net, pen, AIR_LAYER[role], AIR_OFF[role], across=True)

    def pair_lines(self) -> None:
        """A dashed line between the two units of a push-pull pair on this storey."""
        v = self.d.vent
        pen = Pen(AIR["sup"], self.sh.m(0.18), (self.sh.m(1.5), self.sh.m(1.0)))
        for a, b in v.pairs.items():
            if natural(a) < natural(b) and v.at[a].level == v.at[b].level == self.level:
                self.dw.add(Line(v.at[a].point, v.at[b].point, pen, L_UNIT))

    def vent_symbol(self, mt: Mounted) -> None:
        el = self.m[mt.id]
        ink = Ink(self.dw, self.sh, self.spot_of(mt), AIR["sup"], L_UNIT)
        reach = 2.0
        label = mt.id
        if mt.kind == "ahu":
            ink.poly([(-3.0, -2.2), (3.0, -2.2), (3.0, 2.2), (-3.0, 2.2)], "#ffffff", 0.35)
            ink.text(0.0, -0.6, "LG", 1.6, True)
            reach = 2.2
        elif mt.kind == "fan":
            ink.circle(0.0, 1.6, 1.6, "#ffffff", 0.35)
            ink.text(0.0, 1.0, "DZ", 1.1, True)
            mode = getattr(el, "mode")  # noqa: B009
            label = f"{mt.id} {'Abluft' if mode == 'ext' else ''}".strip()
            reach = 3.2
        else:
            role = getattr(el, "role")  # noqa: B009
            ink.layer, ink.color = L_TERMINAL, AIR[role]
            if mt.wall:
                ink.poly([(-1.6, 0.0), (1.6, 0.0), (1.6, 2.4), (-1.6, 2.4)], "#ffffff", 0.35)
                ink.text(0.0, 0.7, AIR_MARK[role], 1.1, True)
                reach = 2.4
            else:
                ink.circle(0.0, 0.0, 1.5, "#ffffff", 0.35)
                ink.text(0.0, -0.45, AIR_MARK[role], 1.1, True)
                reach = 1.5
        ink.layer, ink.color = L_LABEL, BLACK
        ink.text(0.0, reach + 1.9, label, 1.5)

    # ---------- the legend ----------

    def legend(self, keys: dict[str, str]) -> None:
        sh = self.sh
        layer = {"heat": H_LEGEND, "plumb": S_LEGEND, "vent": L_LEGEND}[self.pack]
        _, y0, x1, _ = frame(sh.paper)
        top = y0 + BLOCK_H
        bx = x1 - BLOCK_W - STRIP
        self.rect(bx, y0, x1 - BLOCK_W, top, self.pen(0.7), layer)
        self.text(sh.pt(bx + 2, top - 4.2), "Legende", 2.4, layer, anchor="start", bold=True)
        y = top - 7.0
        shown = self.shown(keys)
        for key in shown:
            self.legend_mark(key, bx + 6.0, y - 0.8, layer)
            self.text(sh.pt(bx + 12.0, y - 1.3), keys[key], 1.6, layer, anchor="start")
            y -= ROW

    def shown(self, keys: dict[str, str]) -> list[str]:
        kinds = {mt.kind for mt in self.here}
        out: list[str] = []
        for key in keys:
            if key in kinds or (key == "ufh" and self.ufh) or (key == "link" and self.ufh):
                out.append(key)
            if key in ("cold", "hot", "circ", "waste") and self._has(key):
                out.append(key)
            if key in ("flow", "ret") and self._heat_pipes():
                out.append(key)
            if key in AIR and any(
                role == key and any(net.nodes[s.a].level == self.level for s in net.sections)
                for (_, role), net in self.d.vent.ducts.items()
            ):
                out.append(key)
            if key == "rise" and any(
                net.nodes[s.a].level != net.nodes[s.b].level
                and self.level in (net.nodes[s.a].level, net.nodes[s.b].level)
                for net in self._nets()
                for s in net.sections
            ):
                out.append(key)
        return out

    def _nets(self) -> list[Net]:
        if self.pack == "heat":
            return list(self.d.heat.nets.values())
        return list(self.d.vent.ducts.values()) if self.pack == "vent" else []

    def _heat_pipes(self) -> bool:
        return any(
            net.nodes[s.a].level == self.level
            for net in self.d.heat.nets.values()
            for s in net.sections
        )

    def _has(self, key: str) -> bool:
        p = self.d.plumb
        nets = {
            "cold": [p.cold],
            "hot": list(p.hot.values()),
            "circ": list(p.recirc.values()),
            "waste": [p.drain],
        }[key]
        return any(
            n is not None and any(n.nodes[s.b].level == self.level for s in n.sections)
            for n in nets
        )

    def legend_mark(self, key: str, x: float, y: float, layer: str) -> None:
        sh = self.sh
        ink = Ink(self.dw, sh, Spot(sh.pt(x, y)), RED, layer)
        if key == "ufh":
            ink.poly([(-2.4, -1.4), (2.4, -1.4), (2.4, 1.4), (-2.4, 1.4)], UFH_FILL, 0.18)
        elif key == "man":
            ink.poly([(-2.4, -0.8), (2.4, -0.8), (2.4, 0.8), (-2.4, 0.8)], "#ffffff", 0.35)
        elif key == "rad":
            ink.poly([(-2.4, -0.6), (2.4, -0.6), (2.4, 0.6), (-2.4, 0.6)], "#ffffff", 0.35)
        elif key == "gen":
            ink.poly([(-1.4, -1.4), (1.4, -1.4), (1.4, 1.4), (-1.4, 1.4)], "#ffffff", 0.35)
        elif key == "tank":
            ink.color = RED if layer == H_LEGEND else HOT
            ink.circle(0.0, 0.0, 1.4, "#ffffff", 0.35)
        elif key == "link":
            ink.dw.add(Line(ink.at(-3.0, 0.0), ink.at(3.0, 0.0), ink.pen(0.18, (1.5, 1.0)), layer))
        elif key == "san":
            ink.color = "#1f77b4"
            ink.poly([(-2.4, -1.2), (2.4, -1.2), (2.4, 1.2), (-2.4, 1.2)], "#ffffff", 0.35)
        elif key == "meter":
            ink.color = BLACK
            ink.circle(0.0, 0.0, 1.4, "#ffffff", 0.35)
        elif key == "riser":
            ink.color = COLD
            ink.circle(0.0, 0.0, 1.4, "#ffffff", 0.35)
            ink.circle(0.0, 0.0, 0.5, COLD, 0.18)
        elif key == "stack":
            ink.color = WASTE
            ink.circle(0.0, 0.0, 1.4, WASTE, 0.35)
        elif key == "sewer":
            ink.color = WASTE
            ink.poly([(-1.4, -1.4), (1.4, -1.4), (1.4, 1.4), (-1.4, 1.4)], "#ffffff", 0.35)
        elif key == "rise":
            r = sh.m(1.0)
            c = sh.pt(x, y)
            ring = [(c[0] + r * dx, c[1] + r * dy) for dx, dy in _RING]
            color = AIR["sup"] if self.pack == "vent" else RED
            for u, v in pairwise(ring):
                self.dw.add(Line(u, v, Pen(color, sh.m(0.25)), layer))
        elif key == "ahu":
            ink.color = AIR["sup"]
            ink.poly([(-2.4, -1.4), (2.4, -1.4), (2.4, 1.4), (-2.4, 1.4)], "#ffffff", 0.35)
        elif key == "fan":
            ink.color = AIR["sup"]
            ink.circle(0.0, 0.0, 1.4, "#ffffff", 0.35)
        elif key == "air":
            ink.color = AIR["sup"]
            ink.circle(0.0, 0.0, 1.2, "#ffffff", 0.35)
        elif key in AIR:
            pen = Pen(AIR[key], sh.m(0.5))
            self.dw.add(Line(sh.pt(x - 3.0, y), sh.pt(x + 3.0, y), pen, layer))
        else:
            color = {"cold": COLD, "hot": HOT, "circ": CIRC, "waste": WASTE, "flow": RED}.get(
                key, BLUE
            )
            dash = (sh.m(2.0), sh.m(1.0)) if key in ("waste", "ret") else ()
            if key == "circ":
                dash = (sh.m(1.2), sh.m(0.6))
            pen = Pen(color, sh.m(0.35), dash)
            self.dw.add(Line(sh.pt(x - 3.0, y), sh.pt(x + 3.0, y), pen, layer))


_RING = [(math.cos(k * math.pi / 8), math.sin(k * math.pi / 8)) for k in range(17)]


def _room_level(d: Derived, room: str) -> str | None:
    rg = d.arch.rooms.get(room)
    return rg.level if rg is not None else None


def tga_levels(d: Derived, pack: str) -> list[str]:
    """The storeys with something of the pack on them."""
    if pack == "heat":
        found = {mt.level for mt in d.heat.at.values()}
        for el in d.model.of_kind("ufh"):
            if isinstance(el, Ufh) and (lv := _room_level(d, el.room.id)) is not None:
                found.add(lv)
    elif pack == "vent":
        found = {mt.level for mt in d.vent.at.values()}
    else:
        found = {mt.level for mt in d.plumb.at.values()}
    return [lv for lv in d.arch.level_order() if lv in found]


def sheet_tga(d: Derived, level: str, pack: str, stand: Stand | None = None) -> Drawing | None:
    """The heating, plumbing or ventilation plan of a storey; none if nothing of the pack is on
    it."""
    return TgaPlan(d, level, stand or Stand(), pack).draw()

"""The Strangschema of the plumbing (decision 0037): a diagram, not to scale, of the drinking
water and the waste water storey by storey.

The storeys are bands, the highest on top, each over its FFL with its height. On the left the
meter and the tanks that heat drinking water on their storeys, then the risers (cold and hot) and
the stacks as verticals through the storeys they serve, each stack up through the roof and down
to the pipes under the building and the sewer connection. On each storey the cold and the hot
distribution run from the meter, a tank or a riser to the fixtures; each fixture drops its waste
to a collecting pipe to its stack or to the sewer connection. Which storey, riser, tank and stack
serves each fixture follows the derived networks (`packs/plumb/geometry.py`); sizes are left out,
because they depend on the office's tables (`uea calc water`, `drain`).
"""

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.drawing import Drawing, Line
from uea.export.paper import BLOCK_H, GREY, Stand, frame
from uea.export.schema import Diagram
from uea.export.tables import USE_DE
from uea.export.tga import CIRC, COLD, FIXTURE_DE, HOT, WASTE
from uea.packs.net import Net
from uea.packs.plumb.kinds import San

S_SCHEMA = "S-SCHEMA"
BAND = 50.0
"""Height of a storey's band, mm."""
TOP = 26.0
FIX_W = 26.0
X_SRC = 32.0
"""Left edge of the meter's and the sewer connection's box."""
TANK_W = 24.0
DASH = (2.0, 1.0)


class Strang(Diagram):
    layer = S_SCHEMA

    def __init__(self, d: Derived, stand: Stand) -> None:
        self.heading = "Strangschema Trinkwasser und Abwasser"
        super().__init__(d, stand, self.heading)
        p = d.plumb
        order = d.arch.level_order()
        idx = {lv: i for i, lv in enumerate(order)}
        found = {mt.level for mt in p.at.values()}
        for net in self.nets():
            found |= {nd.level for nd in net.nodes.values()}
        found |= {d.heat.at[t].level for t in p.hot}
        if found:
            lo, hi = min(idx[x] for x in found), max(idx[x] for x in found)
            self.levels = order[lo : hi + 1][::-1]
        else:
            self.levels = []
        m = d.model
        self.fixtures = {
            lv: sorted(
                (k for k, mt in p.at.items() if mt.kind == "san" and mt.level == lv), key=natural
            )
            for lv in self.levels
        }
        self.meter = next((el.id for el in m.of_kind("meter") if el.id in p.at), None)
        self.sewer = next((el.id for el in m.of_kind("sewer") if el.id in p.at), None)
        self.tanks = sorted(p.hot, key=natural)
        self.risers = sorted((el.id for el in m.of_kind("riser") if el.id in p.at), key=natural)
        drained = p.drain.nodes if p.drain is not None else {}
        self.stacks = sorted(
            (el.id for el in m.of_kind("stack") if any(k.startswith(f"{el.id}:") for k in drained)),
            key=natural,
        )
        self.x_tank = {t: 62.0 + (TANK_W + 4.0) * i for i, t in enumerate(self.tanks)}
        x = 62.0 + (TANK_W + 4.0) * len(self.tanks) + 8.0
        self.x_riser = {r: x + 12.0 * i for i, r in enumerate(self.risers)}
        x += 12.0 * len(self.risers) + 6.0
        self.x_stack = {s: x + 10.0 * i for i, s in enumerate(self.stacks)}
        self.x_fix = x + 10.0 * len(self.stacks) + 8.0
        widest = max([len(v) for v in self.fixtures.values()] + [0])
        self.width = self.x_fix + widest * FIX_W + 6.0
        self.y_ground = TOP + len(self.levels) * BAND + 12.0
        self.height = self.y_ground + 10.0

    def nets(self) -> list[Net]:
        p = self.d.plumb
        return [n for n in (p.cold, *p.hot.values(), p.drain) if n is not None]

    # ---------- where ----------

    def top(self, lv: str) -> float:
        return TOP + self.levels.index(lv) * BAND

    def y_cold(self, lv: str) -> float:
        return self.top(lv) + 12.0

    def y_hot(self, lv: str) -> float:
        return self.top(lv) + 17.0

    def y_circ(self, lv: str) -> float:
        return self.top(lv) + 20.0

    def circ_at(self, node: str) -> bool:
        """Whether a circulation runs to this node of a hot-water net."""
        return any(
            node in {x for s in n.sections for x in (s.a, s.b)}
            for n in self.d.plumb.recirc.values()
        )

    def y_waste(self, lv: str) -> float:
        return self.top(lv) + BAND - 6.0

    def fix_x(self, k: str) -> float:
        lv = self.d.plumb.at[k].level
        return self.x_fix + self.fixtures[lv].index(k) * FIX_W

    def taker_x(self, k: str) -> float:
        return self.x_stack[k] if k in self.x_stack else X_SRC + 12.0

    # ---------- the sheet ----------

    def draw(self) -> Drawing | None:
        p = self.d.plumb
        if not self.levels or not (p.cold or p.drain or p.hot):
            return None
        self.dw.sheet = self.sheet()
        self.say(0.0, 6.0, f"{self.heading} (Prinzip)", 3.5, anchor="start", bold=True)
        for lv in self.levels:
            self.storey(lv)
        self.risers_and_stacks()
        for lv in self.levels:
            self.water(lv)
            self.waste(lv)
        self.ground()
        self.legend()
        self.title_block(self.heading, "Abgeleitet aus dem Modell, unmaßstäblich", "S-00", "o. M.")
        return self.dw

    def storey(self, lv: str) -> None:
        y = self.top(lv) + BAND
        self.line(0.0, y, self.width, y, GREY, 0.18, (4.0, 1.5))
        z = self.g.levels[lv].z
        height = "±0,00" if abs(z) < 5e-4 else f"{z:+.2f}".replace(".", ",")
        self.say(1.0, y - 7.0, lv, 2.6, anchor="start", bold=True)
        self.say(1.0, y - 2.5, f"OKFF {height}", 1.6, anchor="start", color=GREY)
        p = self.d.plumb
        if self.meter is not None and p.at[self.meter].level == lv:
            yt = self.top(lv)
            self.box(X_SRC, yt + 7.0, X_SRC + 24.0, yt + 19.0)
            self.say(X_SRC + 12.0, yt + 11.5, f"{self.meter} WZ", 1.8, bold=True)
            pressure = getattr(self.m[self.meter], "p", None)
            if pressure:
                self.say(X_SRC + 12.0, yt + 15.5, f"{pressure:g} bar", 1.4, color=GREY)
        for t in self.tanks:
            if self.d.heat.at[t].level == lv:
                x, yt = self.x_tank[t], self.top(lv)
                self.box(x, yt + 22.0, x + TANK_W, yt + 37.0)
                self.say(x + TANK_W / 2, yt + 28.0, f"{t} Speicher", 1.7, bold=True)
                self.say(x + TANK_W / 2, yt + 32.0, "TWW", 1.4, color=GREY)

    def risers_and_stacks(self) -> None:
        p = self.d.plumb
        for r, x in self.x_riser.items():
            on: list[str] = []
            for net, color, dx, y_of in (
                (p.cold, COLD, 0.0, self.y_cold),
                *((n, HOT, 4.0, self.y_hot) for n in p.hot.values()),
            ):
                if net is None:
                    continue
                lvs = [k.partition(":")[2] for k in net.nodes if k.startswith(f"{r}:")]
                lvs = [lv for lv in lvs if lv in self.levels]
                if len(lvs) > 1:
                    ys = [y_of(lv) for lv in lvs]
                    self.line(x + dx, min(ys), x + dx, max(ys), color, 0.6)
                on += lvs
            lvs = [lv for lv in self.levels if self.circ_at(f"{r}:{lv}")]
            if len(lvs) > 1:
                ys = [self.y_circ(lv) for lv in lvs]
                self.line(x + 8.0, min(ys), x + 8.0, max(ys), CIRC, 0.5, (1.2, 0.6))
            if on:
                y = min(self.top(lv) for lv in on) + 4.0
                self.say(x + 2.0, y, r, 1.6, bold=True)
        for s, x in self.x_stack.items():
            assert p.drain is not None
            lvs = [k.partition(":")[2] for k in p.drain.nodes if k.startswith(f"{s}:")]
            y0 = min(self.top(lv) for lv in lvs if lv in self.levels) - 8.0
            self.line(x, y0, x, self.y_ground, WASTE, 0.7)
            self.say(x, y0 - 2.0, f"{s} über Dach", 1.5, color=WASTE)

    def water(self, lv: str) -> None:
        p = self.d.plumb
        yc, yh, yt = self.y_cold(lv), self.y_hot(lv), self.top(lv)
        cold: list[float] = []
        hot: list[float] = []
        circ: list[float] = []
        if self.meter is not None and p.at[self.meter].level == lv:
            cold.append(X_SRC + 24.0)
        for r, x in self.x_riser.items():
            if p.cold is not None and f"{r}:{lv}" in p.cold.nodes:
                cold.append(x)
            if any(f"{r}:{lv}" in n.nodes for n in p.hot.values()):
                hot.append(x + 4.0)
            if self.circ_at(f"{r}:{lv}"):
                circ.append(x + 8.0)
        for t in self.tanks:
            if self.d.heat.at[t].level != lv:
                continue
            x = self.x_tank[t]
            if p.cold is not None and p.cold.has(t):
                self.line(x + 6.0, yc, x + 6.0, yt + 22.0, COLD, 0.35)
                cold.append(x + 6.0)
            self.line(x + TANK_W - 6.0, yt + 22.0, x + TANK_W - 6.0, yh, HOT, 0.35)
            hot.append(x + TANK_W - 6.0)
            if t in p.recirc and p.recirc[t].sections:
                yz = self.y_circ(lv)
                self.line(
                    x + TANK_W - 10.0, yt + 22.0, x + TANK_W - 10.0, yz, CIRC, 0.35, (1.2, 0.6)
                )
                circ.append(x + TANK_W - 10.0)
        for k in self.fixtures[lv]:
            el = self.m[k]
            assert isinstance(el, San)
            x = self.fix_x(k)
            if p.cold is not None and p.cold.has(k):
                self.line(x + 8.0, yc, x + 8.0, yt + 24.0, COLD, 0.35)
                cold.append(x + 8.0)
            t = p.hot_from.get(k)
            if t is not None and t in p.hot and p.hot[t].has(k):
                self.line(x + 15.0, yh, x + 15.0, yt + 24.0, HOT, 0.35)
                hot.append(x + 15.0)
            self.box(x + 1.0, yt + 24.0, x + FIX_W - 1.0, yt + 36.0, "#ffffff")
            mark, name = FIXTURE_DE[el.fixture]
            self.say(x + FIX_W / 2, yt + 28.0, f"{k} {mark}", 1.6, bold=True)
            self.say(x + FIX_W / 2, yt + 31.5, name, 1.3)
            room = p.at[k].room
            self.say(x + FIX_W / 2, yt + 34.8, f"{room or ''} {self.room_name(room)}", 1.2,
                     color=GREY)  # fmt: skip
        if len(cold) > 1:
            self.line(min(cold), yc, max(cold), yc, COLD, 0.6)
        if len(hot) > 1:
            self.line(min(hot), yh, max(hot), yh, HOT, 0.6)
        if len(circ) > 1:
            self.line(min(circ), self.y_circ(lv), max(circ), self.y_circ(lv), CIRC, 0.5, (1.2, 0.6))

    def waste(self, lv: str) -> None:
        p = self.d.plumb
        takers = sorted({p.drains_to[k] for k in self.fixtures[lv] if k in p.drains_to},
                        key=natural)  # fmt: skip
        for i, taker in enumerate(takers):
            y = self.y_waste(lv) + 1.6 * i
            xs = [self.taker_x(taker)]
            for k in self.fixtures[lv]:
                if p.drains_to.get(k) == taker:
                    x = self.fix_x(k) + FIX_W / 2
                    self.line(x, self.top(lv) + 36.0, x, y, WASTE, 0.35, DASH)
                    xs.append(x)
            self.line(min(xs), y, max(xs), y, WASTE, 0.5, DASH)
            if taker == self.sewer:
                x = self.taker_x(taker)
                self.line(x, y, x, self.y_ground - 5.0, WASTE, 0.5, DASH)

    def ground(self) -> None:
        if self.sewer is None:
            return
        y = self.y_ground
        self.box(X_SRC, y - 5.0, X_SRC + 24.0, y + 6.0)
        self.say(X_SRC + 12.0, y - 0.8, f"{self.sewer} Kanal", 1.8, bold=True)
        self.say(X_SRC + 12.0, y + 3.4, "Anschluss", 1.4, color=GREY)
        if self.stacks:
            self.line(X_SRC + 24.0, y, max(self.x_stack.values()), y, WASTE, 0.7)
            self.say(X_SRC + 27.0, y - 1.5, "Grundleitung", 1.4, anchor="start", color=WASTE)

    def room_name(self, room: str | None) -> str:
        if room is None or room not in self.m:
            return ""
        el = self.m[room]
        return el.label or USE_DE.get(getattr(el, "use", ""), "")

    def legend(self) -> None:
        sh = self.sh
        fx0, fy0, _, _ = frame(sh.paper)
        x, y = fx0 + 6.0, fy0 + BLOCK_H - 6.0
        items = (
            (COLD, "Trinkwasser kalt (PWC)", ()),
            (HOT, "Trinkwasser warm (PWH)", ()),
            (CIRC, "Zirkulation (PWH-C)", (1.2, 0.6)),
            (WASTE, "Schmutzwasser, Fall- und Grundleitung", DASH),
        )
        for k, (color, txt, dash) in enumerate(items):
            yy = y - k * 5.0
            pen = self.pen(0.6, color, dash)
            self.dw.add(Line(sh.pt(x, yy), sh.pt(x + 10.0, yy), pen, S_SCHEMA))
            self.text(sh.pt(x + 13.0, yy - 0.8), txt, 2.0, S_SCHEMA, anchor="start")
        notes = [
            "Leitungen abgeleitet: je Netz der kürzeste Baum über die rechtwinkligen Abstände.",
            "Nennweiten: uea calc water und uea calc drain mit den Tabellen des Büros.",
            "Zirkulation bis an die Einzelzuleitungen: uea calc recirc.",
            "Nicht dargestellt: Armaturen, Sicherungseinrichtungen, Nebenlüftungen.",
        ]
        for k, t in enumerate(notes):
            self.text(sh.pt(x + 82.0, y - k * 4.4 - 0.8), t, 1.8, S_SCHEMA, anchor="start",
                      color=GREY)  # fmt: skip


def sheet_strang(d: Derived, stand: Stand | None = None) -> Drawing | None:
    """The Strangschema; none if there is no plumbing."""
    return Strang(d, stand or Stand()).draw()

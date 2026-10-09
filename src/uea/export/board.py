"""The distribution board diagram of a board (decision 0026): the single-line diagram from the
supply to every circuit, with its phase, cable, label and what hangs on it, and the derived
occupation of the board's field in rows of 12 TE.

It is a diagram, not a drawing to scale: the sheet is 1:1 and the title block says "o. M.".
"""

from dataclasses import dataclass

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.drawing import Circle, Drawing, Line, Poly, Pt, Sheet
from uea.export.install import circuit_colors
from uea.export.paper import (
    BLACK,
    BLOCK_H,
    BLOCK_W,
    GREY,
    PAPER,
    Paper,
    Stand,
    frame,
    text_width,
)
from uea.packs.elec.geometry import CircGeo
from uea.packs.elec.kinds import Board, Circ, Rcd

E_DIAGRAM = "E-SCHALTPLAN"
E_FIELD = "E-VERTEILERFELD"
COL = 13.0
"""Width of the column of a circuit, in mm."""
GAP = 6.0
GROUP_MIN = 32.0
"""An RCD box is 30 mm wide; a group of one or two circuits is as wide as that."""
TE = 7.5
"""Width of one Teilungseinheit in the drawing of the field, in mm."""
ROW_TE = 12
"""TE in one row of the field. An RCD takes 4, a miniature breaker 1 per pole, an SPD 4."""
LABEL_MAX = 44.0
"""Longest label of a circuit, in mm."""
ROW_H = 6.5
Y = {
    "net": 14.0,
    "meter": 38.0,
    "sls": 50.0,
    "bus": 72.0,
    "rcd": 80.0,
    "gbus": 102.0,
    "mcb": 108.0,
    "arrow": 130.0,
    "id": 138.0,
    "phase": 145.0,
    "cable": 151.0,
    "label": 156.0,
}


@dataclass
class Group:
    rcd: Rcd
    circuits: list[CircGeo]
    x0: float = 0.0
    width: float = 0.0


@dataclass
class Row:
    items: list[tuple[str, str, int]]
    """(kind, id, TE): spd, rcd, cont (an RCD's row goes on) or mcb."""

    @property
    def used(self) -> int:
        return sum(te for _, _, te in self.items)


def field_rows(has_spd: bool, groups: list[Group]) -> list[Row]:
    """The occupation of the board's field in rows: SPD, then each RCD with its breakers."""
    rows: list[Row] = []
    if has_spd:
        rows.append(Row([("spd", "SPD", 4)]))
    for g in groups:
        cur = Row([("rcd", g.rcd.id, 4)])
        for cg in g.circuits:
            te = 3 if cg.phases == 3 else 1
            if cur.used + te > ROW_TE:
                rows.append(cur)
                cur = Row([("cont", g.rcd.id, 4)])
            cur.items.append(("mcb", cg.id, te))
        rows.append(cur)
    return rows


class BoardPlan(Paper):
    def __init__(self, d: Derived, key: str, stand: Stand) -> None:
        self.board = d.model[key]
        assert isinstance(self.board, Board)
        name = self.board.label or key
        self.heading = f"Verteilungsplan {key} {name}"
        super().__init__(d, stand, self.heading)
        self.colors = circuit_colors(d)
        self.groups: list[Group] = []
        for r in d.model.of_kind("rcd"):
            if isinstance(r, Rcd) and r.board.id == key:
                cs = [c for c in d.elec.circuits.values() if c.rcd == r.id]
                self.groups.append(Group(r, sorted(cs, key=lambda c: natural(c.id))))
        self.groups = [g for g in self.groups if g.circuits]
        self.has_spd = self.board.spd is not None
        self.rows = field_rows(self.has_spd, self.groups)
        # the columns
        cursor = 46.0
        self.spd_x = 0.0
        if self.has_spd:
            self.spd_x = cursor + 12.0
            cursor += 30.0
        for g in self.groups:
            g.width = max(len(g.circuits) * COL, GROUP_MIN)
            g.x0 = cursor
            cursor += g.width + GAP
        self.width = cursor + 4.0
        lower = max(self.width, 140.0)
        self.field_y = Y["label"] + LABEL_MAX + 16.0
        self.height = self.field_y + 8.0 + len(self.rows) * ROW_H + 6.0
        self.width = lower
        self.ox = 0.0
        self.oy = 0.0

    # ---------- coordinates ----------

    def P(self, x: float, y: float) -> Pt:
        """A point of the diagram: mm from its top left corner, y downwards."""
        return self.sh.pt(self.ox + x, self.oy - y)

    def line(
        self, x0: float, y0: float, x1: float, y1: float, mm: float = 0.25, color: str = BLACK
    ) -> None:
        self.dw.add(Line(self.P(x0, y0), self.P(x1, y1), self.pen(mm, color), E_DIAGRAM))

    def box(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        mm: float = 0.35,
        color: str = BLACK,
        fill: str | None = None,
    ) -> None:
        pts = [self.P(x0, y0), self.P(x1, y0), self.P(x1, y1), self.P(x0, y1)]
        self.dw.add(Poly(pts, fill, self.pen(mm, color), E_DIAGRAM))

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
        rot: float = 0.0,
    ) -> None:
        """Text with its baseline at y (the top of the text for rot=270)."""
        self.text(self.P(x, y), txt, mm, E_DIAGRAM, anchor=anchor, bold=bold, color=color, rot=rot)

    def arrow(self, x: float, y0: float, y1: float, color: str) -> None:
        self.line(x, y0, x, y1 - 1.2, 0.35, color)
        pts = [self.P(x, y1), self.P(x - 1.1, y1 - 2.4), self.P(x + 1.1, y1 - 2.4)]
        self.dw.add(Poly(pts, color, None, E_DIAGRAM))

    # ---------- the diagram ----------

    def draw(self) -> Drawing | None:
        if not self.groups:
            return None
        self.dw.sheet = self.sheet()
        sx = 22.0
        end = self.groups[-1].x0 + self.groups[-1].width / 2 + 2.0
        self.say(
            0.0,
            6.0,
            f"{self.heading} – Übersichtsschaltplan (einpolig)",
            3.5,
            anchor="start",
            bold=True,
        )
        self.supply(sx, end)
        for g in self.groups:
            self.rcd(g, sx)
        self.field()
        self.notes()
        nr = f"E-{len(self.g.levels) + self.numbers().index(self.board.id) + 1:02d}"
        self.title_block(
            self.heading, "Übersichtsschaltplan einpolig, Belegung abgeleitet", nr, "o. M."
        )
        return self.dw

    def numbers(self) -> list[str]:
        return sorted((b.id for b in self.m.of_kind("board")), key=natural)

    def sheet(self) -> Sheet:
        """The first paper that holds the diagram at 1:1.

        It hangs from the top of the frame. The field at its foot is short, so it may stand left
        of the title block while the wide part above it clears the block's top.
        """
        lower_w = ROW_TE * TE + 36.0
        lower_h = self.height - self.field_y + 4.0
        for size in ("A3", "A2", "A1", "A0"):
            fx0, fy0, fx1, fy1 = frame(PAPER[size])
            tx0, ty1 = fx1 - BLOCK_W, fy0 + BLOCK_H
            x = fx0 + (fx1 - fx0 - self.width) / 2
            y = fy1 - 4.0 - self.height
            if self.width > fx1 - fx0 or y < fy0:
                continue
            if y + lower_h >= ty1 + 4.0 or (x + lower_w <= tx0 - 4.0 and x + self.width <= tx0):
                self.ox, self.oy = x, y + self.height
                return Sheet(size, PAPER[size], 1, (0.0, 0.0))
        x0, _, _, y1 = frame(PAPER["A0"])
        self.ox, self.oy = x0, y1
        return Sheet("A0", PAPER["A0"], 1, (0.0, 0.0))

    def supply(self, sx: float, end: float) -> None:
        b = self.board
        assert isinstance(b, Board)
        self.box(sx - 20, Y["net"], sx + 20, Y["net"] + 10, 0.35, BLACK, "#f4f4f4")
        self.say(sx, Y["net"] + 4.8, "Netz / HAK", 2.4, bold=True)
        self.say(sx, Y["net"] + 8.2, "(nicht im Modell)", 1.5, color=GREY)
        self.line(sx, Y["net"] + 10, sx, Y["meter"] - 4)
        if b.meters:
            self.dw.add(
                Circle(self.P(sx, Y["meter"]), self.sh.m(4.0), self.pen(0.35), None, E_DIAGRAM)
            )
            self.say(sx, Y["meter"] + 0.7, "kWh", 1.8)
            self.say(sx + 7.0, Y["meter"] + 0.7, f"Zähler ({b.meters})", 2.0, anchor="start")
            self.line(sx, Y["meter"] + 4, sx, Y["sls"])
        else:
            self.line(sx, Y["meter"] - 4, sx, Y["sls"])
        name, _, rating = (b.main or "").partition("-")
        self.box(sx - 11, Y["sls"], sx + 11, Y["sls"] + 12, 0.35)
        self.say(sx, Y["sls"] + 5.2, name or "Hauptschalter", 2.6, bold=True)
        if rating:
            self.say(sx, Y["sls"] + 9.4, rating, 2.2)
        self.line(sx, Y["sls"] + 12, sx, Y["bus"])
        self.line(sx, Y["bus"], end, Y["bus"], 0.8)
        self.say(sx + 3.0, Y["bus"] - 1.6, "L1 L2 L3 N PE", 1.6, anchor="start", color=GREY)
        if self.has_spd:
            x = self.spd_x
            self.line(x, Y["bus"], x, Y["rcd"])
            self.box(x - 10, Y["rcd"], x + 10, Y["rcd"] + 12, 0.35)
            self.say(x, Y["rcd"] + 5.2, "SPD", 2.6, bold=True)
            self.say(x, Y["rcd"] + 9.4, b.spd or "", 2.0)
            self.line(x, Y["rcd"] + 12, x, Y["rcd"] + 17)
            for k, half in enumerate((3.2, 2.0, 0.8)):
                self.line(x - half, Y["rcd"] + 17 + k * 1.5, x + half, Y["rcd"] + 17 + k * 1.5)

    def rcd(self, g: Group, sx: float) -> None:
        cx = g.x0 + g.width / 2
        self.line(cx, Y["bus"], cx, Y["rcd"])
        self.box(cx - 15, Y["rcd"], cx + 15, Y["rcd"] + 14, 0.35)
        r = g.rcd
        self.say(cx, Y["rcd"] + 5.4, f"{r.id} RCD", 2.6, bold=True)
        amps, idn = f"{r.rating.amps:g}".replace(".", ","), f"{r.rating.idn:g}".replace(".", ",")
        self.say(cx, Y["rcd"] + 9.0, f"{amps} A / {idn} A", 1.9)
        self.say(cx, Y["rcd"] + 12.4, f"Typ {r.type}, 4-polig", 1.6)
        first = g.x0 + (g.width - len(g.circuits) * COL) / 2 + COL / 2
        xs = [first + k * COL for k in range(len(g.circuits))]
        self.line(cx, Y["rcd"] + 14, cx, Y["gbus"])
        self.line(min([*xs, cx]), Y["gbus"], max([*xs, cx]), Y["gbus"], 0.5)
        for x, cg in zip(xs, g.circuits, strict=True):
            self.circuit(x, cg)

    def circuit(self, x: float, cg: CircGeo) -> None:
        color = self.colors[cg.id]
        el = self.m[cg.id]
        assert isinstance(el, Circ)
        self.line(x, Y["gbus"], x, Y["mcb"])
        self.box(x - 5.5, Y["mcb"], x + 5.5, Y["mcb"] + 14, 0.5, color)
        self.say(x, Y["mcb"] + 6.2, cg.breaker.fmt(), 2.2, bold=True)
        self.say(x, Y["mcb"] + 10.4, f"{cg.phases}-polig", 1.4)
        self.arrow(x, Y["mcb"] + 14, Y["arrow"], color)
        self.say(x, Y["id"], cg.id, 3.2, bold=True, color=color)
        self.say(x, Y["phase"], cg.phase.replace("-", "–"), 2.0)
        self.say(x, Y["cable"], el.cable.fmt(), 1.4)
        self.say(
            x - 2.3,
            Y["label"],
            fit(el.label or "", LABEL_MAX, 1.9),
            1.9,
            anchor="start",
            bold=True,
            rot=270.0,
        )
        self.say(
            x + 1.9,
            Y["label"],
            fit(self.counts(cg), LABEL_MAX, 1.4),
            1.4,
            anchor="start",
            color=GREY,
            rot=270.0,
        )

    def counts(self, cg: CircGeo) -> str:
        """What hangs on a circuit: `3 Dosen / 5 Steckpl.`"""
        kinds: dict[str, list[str]] = {}
        for k in cg.devices:
            kinds.setdefault(self.m[k].kind, []).append(k)
        out: list[str] = []
        if "sock" in kinds:
            outlets = sum(int(getattr(self.m[k], "n", 1)) for k in kinds["sock"])
            out.append(f"{len(kinds['sock'])} Dosen / {outlets} Steckpl.")
        if "switch" in kinds:
            out.append(f"{len(kinds['switch'])} Schalter")
        if cg.lums:
            out.append(f"{len(cg.lums)} Leuchten")
        if "conn" in kinds:
            out.append(f"{len(kinds['conn'])} Anschluss")
        feeds = [str(getattr(self.m[k], "target").id) for k in kinds.get("feed", [])]  # noqa: B009
        if feeds:
            out.append("→ " + " ".join(feeds))
        return ", ".join(out)

    # ---------- the field ----------

    def field(self) -> None:
        y = self.field_y
        self.say(
            0.0,
            y,
            f"Belegung Verteilerfeld {self.board.id} (abgeleitet), {ROW_TE} TE je Reihe",
            3.0,
            anchor="start",
            bold=True,
        )
        y += 3.0
        for n, row in enumerate(self.rows, 1):
            x = 0.0
            self.box(0.0, y, ROW_TE * TE, y + ROW_H - 1.0, 0.18, "#bbbbbb")
            for kind, key, te in row.items:
                w = te * TE
                if kind in ("rcd", "cont", "spd"):
                    text = {"rcd": f"{key} RCD", "cont": f"{key} (Forts.)", "spd": "SPD"}[kind]
                    self.box(x, y, x + w, y + ROW_H - 1.0, 0.35, BLACK, "#eeeeee")
                    self.say(x + w / 2, y + 3.6, text, 1.8, bold=True)
                else:
                    color = self.colors[key]
                    self.box(x, y, x + w, y + ROW_H - 1.0, 0.35, color)
                    if te > 1:
                        el = self.d.elec.circuits[key]
                        self.say(x + w / 2, y + 3.6, f"{key} {el.breaker.fmt()}", 1.8)
                    else:
                        self.say(x + w / 2 + 0.7, y + 4.9, key, 1.6, rot=90.0)
                x += w
            self.say(
                ROW_TE * TE + 3.0,
                y + 3.6,
                f"Reihe {n}: {row.used} TE",
                1.8,
                anchor="start",
                color=GREY,
            )
            y += ROW_H

    def notes(self) -> None:
        circuits = [c for g in self.groups for c in g.circuits]
        x = 80.0
        y = 12.0
        lines = [
            f"{len(circuits)} Stromkreise an {len(self.groups)} RCD · {len(self.rows)} Reihen"
            f" à {ROW_TE} TE im Verteilerfeld.",
            "Annahmen: RCD 4 TE, Leitungsschutzschalter 1 TE je Pol, SPD 4 TE.",
            "Phasenaufteilung abgeleitet: einphasige Stromkreise nacheinander auf die Phase",
            "mit der kleinsten angenommenen Last, ohne Lastberechnung.",
            "Zähler, SLS und SPD stehen als Felder des Verteilers; Netzanschluss nicht modelliert.",
            "Leitungen wie im Modell angegeben; Leitungslängen, Spannungsfall und Selektivität",
            "folgen mit den Berechnungen.",
        ]
        for k, t in enumerate(lines):
            self.say(x, y + k * 4.2, t, 1.7, anchor="start", color=GREY)


def fit(txt: str, limit_mm: float, size: float) -> str:
    """Cut a text so that it is no longer than limit_mm at that size."""
    if text_width(txt, size) <= limit_mm:
        return txt
    while txt and text_width(txt + "…", size) > limit_mm:
        txt = txt[:-1]
    return txt + "…"


def sheet_board(d: Derived, key: str, stand: Stand | None = None) -> Drawing | None:
    """The diagram of a board; none if it has no circuits."""
    el = d.model.get(key)
    if not isinstance(el, Board) or el.media:
        return None
    return BoardPlan(d, key, stand or Stand()).draw()

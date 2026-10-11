"""Heating and plumbing tables for humans (decision 0036): emitters, manifolds, fixtures, pipe
sections and pipe quantities. German, from the derived model; outputs are the manufacturer's
values in the types, lengths are the derived lower bounds.
"""

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.tables import USE_DE, Cell, Col, Table
from uea.export.tga import FIXTURE_DE
from uea.packs.heat.geometry import heat_type, man_type
from uea.packs.heat.kinds import RadType, Ufh, UfhType
from uea.packs.plumb.geometry import Net
from uea.packs.plumb.kinds import San

M1 = "0.0"
M2 = "0.00"
W0 = "0"
WATER_DE = {"cold": "kalt", "both": "kalt + warm", "none": "–"}
SECTION_DE = {
    "pipe": "Leitung",
    "riser": "Steigleitung",
    "branch": "Anschlussleitung",
    "stack": "Fallleitung",
    "ground": "Grundleitung",
}


def _q(v: float) -> float:
    return round(v, 6) + 0.0


class _Tga:
    def __init__(self, d: Derived, level: str | None) -> None:
        self.d = d
        self.m = d.model
        self.level = level
        self.rank = {lv: i for i, lv in enumerate(d.arch.level_order())}
        proj = self.m.of_kind("project")
        self.project = (proj[0].label or proj[0].id) if proj else "UEA"
        self.scope = "" if level is None else f" {level}"

    def title(self, name: str) -> str:
        return f"{name}{self.scope} – {self.project}"

    def room_name(self, room: str | None) -> str | None:
        if room is None or room not in self.m:
            return None
        el = self.m[room]
        return el.label or USE_DE.get(getattr(el, "use", ""))

    def mine(self, level: str | None) -> bool:
        return self.level is None or level == self.level

    # ---------- heating ----------

    def emitters(self) -> Table:
        h = self.d.heat
        rows: list[list[Cell]] = []
        keys = [el.id for el in self.m.of_kind("ufh")] + [el.id for el in self.m.of_kind("rad")]
        for k in keys:
            el = self.m[k]
            if isinstance(el, Ufh):
                rg = self.d.arch.rooms.get(el.room.id)
                level, room = (rg.level, rg.id) if rg is not None else (None, el.room.id)
                lp = h.loops.get(k)
                t = heat_type(self.m, el, UfhType, "ufh")
                area = _q(lp.area) if lp else None
                n = lp.n if lp else None
                each = _q(lp.each) if lp and lp.n else None
                pipe = _q(lp.pipe) if lp else None
                kind = "Fußbodenheizung"
            else:
                mt = h.at.get(k)
                level, room = (mt.level, mt.room) if mt is not None else (None, None)
                t = heat_type(self.m, el, RadType, "rad")
                area = n = each = pipe = None
                kind = "Heizkörper"
            if not self.mine(level):
                continue
            src = getattr(el, "src").id  # noqa: B009
            w = h.output.get(k)
            rows.append(
                [k, level, room, self.room_name(room), kind, t.id if t else None, area, n, each,
                 pipe, _q(w) if w is not None else None, src]
            )  # fmt: skip
        rows.sort(key=lambda r: (self.rank.get(str(r[1]), 99), natural(str(r[0]))))
        cols = [
            Col("Nr.", 6),
            Col("Geschoss", 9),
            Col("Raum", 7),
            Col("Raumname", 18),
            Col("Art", 16),
            Col("Typ", 10),
            Col("Fläche m²", 10, M2),
            Col("Kreise", 7, W0),
            Col("Kreislänge m", 12, M1),
            Col("Rohr m", 9, M1),
            Col("Leistung W", 11, W0),
            Col("Von", 6),
        ]
        total: list[Cell] = ["Summe", *([None] * 5)]
        total += [_sum(rows, 6), _sum(rows, 7), None, _sum(rows, 9), _sum(rows, 10), None]
        notes = [
            "Leistung nach Herstellerangabe im Typ (Fußbodenheizung q mal Fläche), nicht nach"
            " DIN EN 1264 oder DIN EN 442 berechnet. Kreise abgeleitet: Rohr in der Fläche durch"
            " den Verlegeabstand, je Kreis mit Anbindung hin und zurück, höchstens die längste"
            " Kreislänge des Typs.",
        ]
        return Table("Heizflächen", self.title("Heizflächen"), cols, rows, total, notes)

    def manifolds(self) -> Table:
        h = self.d.heat
        rows: list[list[Cell]] = []
        for el in self.m.of_kind("man"):
            mt = h.at.get(el.id)
            level = mt.level if mt is not None else None
            if not self.mine(level):
                continue
            t = man_type(self.d, el)
            served = h.supplies.get(el.id, [])
            loops = sum(h.loops[k].n for k in served if k in h.loops)
            loops += sum(1 for k in served if self.m[k].kind == "rad")
            host = getattr(el, "host").id  # noqa: B009
            rows.append(
                [el.id, level, mt.room if mt else None, host, t.id if t else None,
                 t.outlets if t else None, loops,
                 (t.outlets - loops) if t else None, " ".join(served)]
            )  # fmt: skip
        cols = [
            Col("Nr.", 6),
            Col("Geschoss", 9),
            Col("Raum", 7),
            Col("Ort", 8),
            Col("Typ", 10),
            Col("Abgänge", 9, W0),
            Col("Belegt", 8, W0),
            Col("Frei", 7, W0),
            Col("Versorgt", 30),
        ]
        return Table("Heizkreisverteiler", self.title("Heizkreisverteiler"), cols, rows)

    # ---------- plumbing ----------

    def fixtures(self) -> Table:
        p = self.d.plumb
        rows: list[list[Cell]] = []
        for el in self.m.of_kind("san"):
            assert isinstance(el, San)
            mt = p.at.get(el.id)
            if mt is None or not self.mine(mt.level):
                continue
            cold = _reach(p.cold, el.id)
            t = p.hot_from.get(el.id)
            hot = _reach(p.hot.get(t), el.id) if t is not None else None
            to = p.drains_to.get(el.id)
            waste = _reach(p.drain, el.id) if to is not None else None
            where = f"{mt.wall}.{mt.letter}" if mt.wall else "Raum"
            rows.append(
                [el.id, mt.level, mt.room, self.room_name(mt.room), FIXTURE_DE[el.fixture][1],
                 WATER_DE[el.supply], where, _q(mt.z - self.d.arch.levels[mt.level].z), cold, t,
                 hot, to, waste]
            )  # fmt: skip
        rows.sort(key=lambda r: (self.rank.get(str(r[1]), 99), natural(str(r[0]))))
        cols = [
            Col("Nr.", 6),
            Col("Geschoss", 9),
            Col("Raum", 7),
            Col("Raumname", 16),
            Col("Objekt", 16),
            Col("Wasser", 11),
            Col("Ort", 8),
            Col("Auslass m", 10, M2),
            Col("Weg kalt m", 11, M1),
            Col("Warm von", 9),
            Col("Weg warm m", 11, M1),
            Col("Ablauf an", 9),
            Col("Weg Kanal m", 12, M1),
        ]
        notes = [
            "Wege entlang der abgeleiteten Leitungen: kalt vom Hausanschluss, warm vom Speicher,"
            " Schmutzwasser bis zum Anschluss an den Kanal. Untergrenzen, ohne Trasse.",
        ]
        return Table("Sanitärobjekte", self.title("Sanitärobjekte"), cols, rows, None, notes)

    def sections(self) -> Table:
        p = self.d.plumb
        rows: list[list[Cell]] = []
        nets: list[tuple[str, Net]] = []
        if p.cold is not None:
            nets.append(("Trinkwasser kalt", p.cold))
        nets += [(f"Trinkwasser warm ({k})", n) for k, n in p.hot.items()]
        if p.drain is not None:
            nets.append(("Schmutzwasser", p.drain))
        for name, net in nets:
            for s in net.sections:
                level = net.nodes[s.b].level
                if not self.mine(level):
                    continue
                rows.append(
                    [name, s.a, s.b, level, SECTION_DE[s.kind], _q(s.length), s.bends,
                     " ".join(s.serves)]
                )  # fmt: skip
        cols = [
            Col("Netz", 22),
            Col("Von", 9),
            Col("Nach", 9),
            Col("Geschoss", 9),
            Col("Art", 16),
            Col("Länge m", 9, M2),
            Col("Bögen", 7, W0),
            Col("Versorgt / entwässert", 28),
        ]
        total: list[Cell] = ["Summe", None, None, None, None, _sum(rows, 5), _sum(rows, 6), None]
        notes = [
            "Teilstrecken abgeleitet: je Netz der kürzeste Baum über die rechtwinkligen Abstände;"
            " ein Bogen je Richtungswechsel. Nennweiten liefern uea calc water und uea calc drain"
            " mit den Tabellen des Büros.",
        ]
        return Table("Rohrleitungen", self.title("Rohrleitungen"), cols, rows, total, notes)

    def quantities(self) -> Table:
        p, h = self.d.plumb, self.d.heat
        rows: list[list[Cell]] = []
        if p.cold is not None:
            rows.append(["Trinkwasser kalt", len(p.cold.sections), _q(p.cold.total)])
        for k, n in p.hot.items():
            rows.append([f"Trinkwasser warm ({k})", len(n.sections), _q(n.total)])
        if p.drain is not None:
            rows.append(["Schmutzwasser", len(p.drain.sections), _q(p.drain.total)])
        by_type: dict[str, list[float]] = {}
        for el in self.m.of_kind("ufh"):
            lp = h.loops.get(el.id)
            t = heat_type(self.m, el, UfhType, "ufh")
            if lp is not None and t is not None:
                got = by_type.setdefault(t.id, [0.0, 0.0])
                got[0] += lp.n
                got[1] += lp.pipe
        for name, (n, m) in sorted(by_type.items()):
            rows.append([f"Fußbodenheizung {name}", int(n), _q(m)])
        cols = [Col("Leitung", 30), Col("Teilstrecken / Kreise", 12, W0), Col("Länge m", 10, M1)]
        total: list[Cell] = ["Summe", None, _sum(rows, 2)]
        notes = ["Abgeleitete Längen ohne Verschnitt; keine Ausschreibungsmenge."]
        if self.level is not None:
            notes.append("Mengen für das ganze Gebäude.")
        return Table("Rohrmengen", self.title("Rohrmengen"), cols, rows, total, notes)


def _reach(net: Net | None, k: str) -> float | None:
    return _q(net.reach(k)) if net is not None and net.has(k) else None


def _sum(rows: list[list[Cell]], i: int) -> float:
    return _q(sum(v for r in rows if isinstance(v := r[i], int | float)))


def tga_tables(d: Derived, level: str | None = None) -> list[Table]:
    """The heating and plumbing tables; tables without rows are left out."""
    b = _Tga(d, level)
    tables = [b.emitters(), b.manifolds(), b.fixtures(), b.sections(), b.quantities()]
    return [t for t in tables if t.rows]

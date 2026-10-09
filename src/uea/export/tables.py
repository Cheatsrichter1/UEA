"""Tables for humans: rooms, walls, openings, slabs, roofs, stairs and quantities.

The tables are plain data (`Table`); `xlsx.py` writes them. They are German, because offices
read them. Quantities are taken on the structural sizes of the model (core faces, Rohbaumaße)
and follow no deduction rules of the VOB/C: a Leistungsverzeichnis applies those itself.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from uea.core.registry import natural
from uea.core.values import Layers
from uea.derive import Derived
from uea.packs.arch.geometry import ArchGeo, WallGeo, opening_type, roof_pieces
from uea.packs.arch.kinds import Door, DoorType, Roof, Room, WinType

Cell = str | float | int | None

USE_DE = {
    "living": "Wohnen",
    "dining": "Essen",
    "kitchen": "Küche",
    "bedroom": "Schlafen",
    "office": "Arbeiten",
    "bath": "Bad",
    "wc": "WC",
    "hall": "Flur",
    "utility": "Hauswirtschaftsraum",
    "storage": "Abstellraum",
    "laundry": "Waschküche",
    "technical": "Technik",
    "cellar": "Keller",
    "attic": "Dachboden",
    "garage": "Garage",
    "other": "Sonstiges",
}
STATUS_DE = {"new": "Neu", "existing": "Bestand", "demolish": "Abbruch", "temp": "Temporär"}
OPENING_DE = {"door": "Tür", "win": "Fenster", "niche": "Nische"}
ROOF_DE = {
    "gable": "Satteldach",
    "shed": "Pultdach",
    "hip": "Walmdach",
    "mansard": "Mansarddach",
    "flat": "Flachdach",
}
STAIR_DE = {"straight": "gerade", "l": "Viertelwendel (L)", "u": "Halbwendel (U)"}
HAND_DE = {"l": "links", "r": "rechts"}
DEMOLISH = STATUS_DE["demolish"]

NOTE_BASIS = (
    "Rohbaumaße aus dem UEA-Modell; Abzüge nach VOB/C sind Sache des Leistungsverzeichnisses."
)

M = "0.000"
M2 = "0.00"


@dataclass(frozen=True)
class Col:
    head: str
    width: int = 12
    """Width in characters."""
    fmt: str | None = None
    """Excel number format; text if left out."""


@dataclass
class Table:
    name: str
    """Sheet name."""
    title: str
    cols: list[Col]
    rows: list[list[Cell]] = field(default_factory=list[list[Cell]])
    total: list[Cell] | None = None
    """A sum row under the data, outside the filter."""
    notes: list[str] = field(default_factory=list[str])


def _q(v: float) -> float:
    """A value without float noise. The number format of the column does the rounding."""
    return round(v, 6) + 0.0


def _opt(v: float | None) -> float | None:
    return None if v is None else _q(v)


def _col(rows: list[list[Cell]], i: int) -> float:
    """Sum of column i of the rows: what a SUM in the sheet gives."""
    return _q(sum(v for r in rows if isinstance(v := r[i], int | float)))


def _live(rows: list[list[Cell]], status: int) -> list[list[Cell]]:
    return [r for r in rows if r[status] != DEMOLISH]


def layers_de(layers: Layers) -> str:
    """The build-up with thicknesses in cm: `putz 1,5 | *ziegel 36,5 | putz 2`."""

    def cm(t: float) -> str:
        return f"{t * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",")

    return " | ".join(f"{'*' if x.core else ''}{x.material} {cm(x.t)}" for x in layers.items)


def wall_profile(w: WallGeo) -> list[tuple[float, float]] | None:
    """Height of the wall above its bottom along its run, at every break of the top."""
    if not w.top:
        return None
    ss = sorted({w.s0, w.s1, *(s for s, _ in w.top if w.s0 < s < w.s1)})
    out: list[tuple[float, float]] = []
    for s in ss:
        z = w.top_at(s)
        assert z is not None
        out.append((s, z - w.bottom))
    return out


@dataclass
class WallQty:
    gross: float | None
    """Elevation area between the wall ends, under the top profile."""
    openings: float
    """Doors and windows, in structural sizes."""
    net: float | None
    volume: float | None
    """Core volume: net area times core thickness."""
    h_min: float | None
    h_max: float | None


def wall_qty(g: ArchGeo, w: WallGeo) -> WallQty:
    holes = sum(
        (o.hi - o.lo) * (o.top - o.sill)
        for o in g.openings.values()
        if o.host == w.id and o.kind != "niche"
    )
    prof = wall_profile(w)
    if prof is None:
        return WallQty(None, holes, None, None, None, None)
    gross = sum((b - a) * (ha + hb) / 2 for (a, ha), (b, hb) in pairwise(prof))
    net = gross - holes
    return WallQty(
        gross,
        holes,
        net,
        net * (w.hi - w.lo),
        min(h for _, h in prof),
        max(h for _, h in prof),
    )


class _Builder:
    def __init__(self, d: Derived, level: str | None) -> None:
        self.m = d.model
        self.g = d.arch
        order = self.g.level_order()
        self.levels = order if level is None else [level]
        self.rank = {lv: i for i, lv in enumerate(order)}
        proj = self.m.of_kind("project")
        self.project = (proj[0].label or proj[0].id) if proj else "UEA"
        self.scope = "" if level is None else f" {level}"
        self._sloped: dict[str, float] | None = None

    def on_levels(self, items: Any) -> list[Any]:
        """The items on the chosen storeys, in storey order, then by id."""
        mine = [x for x in items if x.level in self.levels]
        return sorted(mine, key=lambda x: (self.rank[x.level], natural(x.id)))

    def title(self, name: str) -> str:
        return f"{name}{self.scope} – {self.project}"

    def type_label(self, tid: str | None) -> str | None:
        if tid is None or tid not in self.m:
            return None
        return getattr(self.m[tid], "label", None)

    def type_id(self, key: str) -> str | None:
        t = getattr(self.m[key], "type", None)
        return None if t is None else t.id

    def sloped(self) -> dict[str, float]:
        """Sloped area of each roof, including its overhangs."""
        if self._sloped is None:
            out: dict[str, float] = defaultdict(float)
            for lv in self.levels:
                ids = [rf.id for rf in self.g.roofs_on(lv)]
                if not ids:
                    continue
                for i, plane, poly in roof_pieces(self.g, lv):
                    out[ids[i]] += poly.area * (1 + plane.a**2 + plane.b**2) ** 0.5
            self._sloped = out
        return self._sloped

    # ---------- the tables ----------

    def rooms(self) -> Table:
        rows: list[list[Cell]] = []
        for rg in self.on_levels(self.g.rooms.values()):
            el = self.m[rg.id]
            assert isinstance(el, Room)
            hr = rg.height_range()
            rows.append(
                [
                    rg.id,
                    rg.level,
                    USE_DE[el.use],
                    el.label,
                    _q(rg.area),
                    _q(rg.area_fin),
                    _opt(hr[0] if hr else None),
                    _opt(hr[1] if hr else None),
                    _opt(rg.volume),
                    None if el.floor is None else el.floor.id,
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Geschoss", 10),
            Col("Nutzung", 20),
            Col("Bezeichnung", 22),
            Col("Rohbaufläche m²", 16, M2),
            Col("Fertigfläche m²", 16, M2),
            Col("Höhe min m", 12, M),
            Col("Höhe max m", 12, M),
            Col("Volumen m³", 12, M2),
            Col("Bodenaufbau", 14),
        ]
        total: list[Cell] = ["Summe", None, None, None]
        total += [_col(rows, 4), _col(rows, 5), None, None, _col(rows, 8), None]
        notes = [
            "Fertigfläche: zwischen den fertigen Wandflächen. Das ist keine Wohnfläche nach WoFlV;"
            " die berechnet `uea calc wofl`.",
            "Höhe: lichte Höhe über dem fertigen Fußboden; min und max unterscheiden sich unter"
            " Dachschrägen.",
        ]
        return Table("Räume", self.title("Räume"), cols, rows, total, notes)

    def walls(self) -> Table:
        rows: list[list[Cell]] = []
        no_top: list[str] = []
        for w in self.on_levels(self.g.walls.values()):
            q = wall_qty(self.g, w)
            if q.gross is None:
                no_top.append(w.id)
            rows.append(
                [
                    w.id,
                    w.level,
                    self.type_id(w.id),
                    layers_de(w.layers),
                    "Außenwand" if w.ext is not None else "Innenwand",
                    "ja" if w.lb else "nein",
                    STATUS_DE[w.status],
                    _q(w.length),
                    _q(w.t),
                    _q(w.t + w.layers.before_core() + w.layers.after_core()),
                    _opt(q.h_min),
                    _opt(q.h_max),
                    _opt(q.gross),
                    _q(q.openings),
                    _opt(q.net),
                    _opt(q.volume),
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Geschoss", 10),
            Col("Typ", 12),
            Col("Aufbau (cm, * Kern)", 44),
            Col("Lage", 11),
            Col("Tragend", 9),
            Col("Status", 10),
            Col("Länge m", 10, M),
            Col("Kerndicke m", 12, M),
            Col("Gesamtdicke m", 14, M),
            Col("Höhe min m", 11, M),
            Col("Höhe max m", 11, M),
            Col("Fläche brutto m²", 16, M2),
            Col("Öffnungen m²", 13, M2),
            Col("Fläche netto m²", 15, M2),
            Col("Kernvolumen m³", 15, M2),
        ]
        live = _live(rows, 6)
        total: list[Cell] = ["Summe ohne Abbruch", *[None] * 6, _col(live, 7), *[None] * 4]
        total += [_col(live, 12), _col(live, 13), _col(live, 14), _col(live, 15)]
        notes = [
            "Länge und Fläche zwischen den Wandenden, in der Kernschicht; Fläche brutto unter der"
            " Oberkante der Wand. Öffnungen: Türen und Fenster in Rohbaumaßen, Nischen nicht."
            " Kernvolumen = Fläche netto x Kerndicke.",
            NOTE_BASIS,
        ]
        if no_top:
            notes.append(
                f"Ohne Oberkante (keine Decke oder Dach darüber), ohne Fläche: {' '.join(no_top)}"
            )
        return Table("Wände", self.title("Wände"), cols, rows, total, notes)

    def openings(self) -> Table:
        rows: list[list[Cell]] = []
        for o in self.on_levels(self.g.openings.values()):
            el = self.m[o.id]
            typ = opening_type(self.m, el)
            rooms = sorted((s or "außen" for s in o.sides), key=lambda s: s == "außen")
            u = None
            if isinstance(typ, DoorType):
                u = typ.ud if typ.ud is not None else typ.uw
            elif isinstance(typ, WinType):
                u = typ.uw
            into = hand = None
            if isinstance(el, Door):
                into = el.into.id if el.into is not None else None
                hand = HAND_DE.get(el.hand or "")
            width, height = o.hi - o.lo, o.top - o.sill
            rows.append(
                [
                    o.id,
                    OPENING_DE[o.kind],
                    o.level,
                    o.host,
                    None if typ is None else typ.id,
                    _q(width),
                    _q(height),
                    _q(o.sill),
                    _q(o.top),
                    _q(width * height),
                    _q(o.depth) if o.kind == "niche" else None,
                    rooms[0],
                    rooms[1],
                    into,
                    hand,
                    u,
                    STATUS_DE[o.status],
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Art", 10),
            Col("Geschoss", 10),
            Col("Wand", 8),
            Col("Typ", 12),
            Col("Breite m", 10, M),
            Col("Höhe m", 10, M),
            Col("Brüstung m", 11, M),
            Col("Sturz m", 10, M),
            Col("Fläche m²", 11, M2),
            Col("Tiefe m", 9, M),
            Col("Raum 1", 9),
            Col("Raum 2", 9),
            Col("öffnet in", 10),
            Col("Anschlag", 10),
            Col("U-Wert W/(m²K)", 15, M2),
            Col("Status", 10),
        ]
        live = [r for r in _live(rows, 16) if r[1] != OPENING_DE["niche"]]
        total: list[Cell] = ["Summe Türen und Fenster ohne Abbruch", *[None] * 8]
        total += [_col(live, 9), *[None] * 7]
        notes = [
            "Rohbaumaße (Maueröffnung). Brüstung und Sturz über dem fertigen Fußboden des"
            " Geschosses. Anschlag nach DIN, von dem Raum aus gesehen, in den die Tür öffnet.",
        ]
        return Table("Öffnungen", self.title("Öffnungen"), cols, rows, total, notes)

    def slabs(self) -> Table:
        rows: list[list[Cell]] = []
        for s in self.on_levels(self.g.slabs.values()):
            rows.append(
                [
                    s.id,
                    s.level,
                    self.type_id(s.id),
                    layers_de(s.layers),
                    STATUS_DE[s.status],
                    _q(s.outline.area),
                    _q(s.outline.area - s.net.area),
                    _q(s.net.area),
                    _q(s.layers.core),
                    _q(s.net.area * s.layers.core),
                    _q(s.top),
                    _q(s.underside),
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Geschoss", 10),
            Col("Typ", 12),
            Col("Aufbau (cm, * Kern)", 40),
            Col("Status", 10),
            Col("Fläche brutto m²", 16, M2),
            Col("Aussparungen m²", 16, M2),
            Col("Fläche netto m²", 15, M2),
            Col("Kerndicke m", 12, M),
            Col("Kernvolumen m³", 15, M2),
            Col("OK Rohdecke m", 14, M),
            Col("UK Rohdecke m", 14, M),
        ]
        live = _live(rows, 4)
        total: list[Cell] = ["Summe ohne Abbruch", *[None] * 4]
        total += [_col(live, 5), _col(live, 6), _col(live, 7), None, _col(live, 9), None, None]
        notes = [
            "OK und UK Rohdecke als Höhen über ±0 des Projekts (OK = Oberkante der Kernschicht,"
            " SSL des Geschosses).",
            NOTE_BASIS,
        ]
        return Table("Decken", self.title("Decken"), cols, rows, total, notes)

    def roofs(self) -> Table:
        rows: list[list[Cell]] = []
        sloped = self.sloped()
        for rf in self.on_levels(self.g.roofs.values()):
            el = self.m[rf.id]
            assert isinstance(el, Roof)
            shape = "Krüppelwalmdach" if el.halfhip is not None else ROOF_DE[rf.shape]
            rows.append(
                [
                    rf.id,
                    rf.level,
                    shape,
                    self.type_id(rf.id),
                    STATUS_DE[rf.status],
                    None if rf.shape == "flat" else _q(rf.pitch),
                    _opt(el.upper),
                    _q(rf.eaves_z),
                    _q(rf.ridge_z),
                    _q(rf.over.area),
                    _q(sloped[rf.id]) if rf.id in sloped else None,
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Geschoss", 10),
            Col("Form", 18),
            Col("Typ", 12),
            Col("Status", 10),
            Col("Neigung °", 11, "0.0"),
            Col("Neigung oben °", 15, "0.0"),
            Col("Traufe m", 11, M),
            Col("First m", 10, M),
            Col("Grundfläche m²", 15, M2),
            Col("Dachfläche m²", 14, M2),
        ]
        live = _live(rows, 4)
        total: list[Cell] = ["Summe ohne Abbruch", *[None] * 8, _col(live, 9), _col(live, 10)]
        notes = [
            "Traufe: Oberkante der Dacheindeckung über der Außenfläche der Traufwand; First:"
            " höchster Punkt der Eindeckung; beide als Höhen über ±0 des Projekts.",
            "Grundfläche: Dach im Grundriss mit Überständen. Dachfläche: die geneigten Flächen"
            " einschließlich Überstände, ohne Abzug von Dachfenstern.",
        ]
        return Table("Dächer", self.title("Dächer"), cols, rows, total, notes)

    def stairs(self) -> Table:
        rows: list[list[Cell]] = []
        for s in self.on_levels(self.g.stairs.values()):
            rows.append(
                [
                    s.id,
                    s.level,
                    s.to,
                    STAIR_DE[s.shape],
                    STATUS_DE[s.status],
                    s.n,
                    _q(s.riser),
                    _q(s.tread),
                    _q(s.step),
                    _q(s.w),
                    s.winders or None,
                    _q(s.poly.area),
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("von", 10),
            Col("nach", 10),
            Col("Form", 20),
            Col("Status", 10),
            Col("Steigungen", 12),
            Col("Steigung m", 12, M),
            Col("Auftritt m", 11, M),
            Col("Schrittmaß m", 13, M),
            Col("Laufbreite m", 13, M),
            Col("Wendelstufen", 14),
            Col("Grundfläche m²", 15, M2),
        ]
        notes = ["Schrittmaß: 2 x Steigung + Auftritt. Grundfläche: Läufe, Podest und Treppenloch."]
        return Table("Treppen", self.title("Treppen"), cols, rows, None, notes)

    def quantities(self) -> Table:
        """Per group, type, storey and status: count, length, area, volume."""
        # group -> (has length, has area, has volume)
        measures = {
            "Wand": (True, True, True),
            "Decke": (False, True, True),
            "Boden": (False, True, False),
            "Raum": (False, True, True),
            "Dach": (False, True, False),
            "Tür": (False, True, False),
            "Fenster": (False, True, False),
        }
        acc: dict[tuple[str, str | None, str | None, str, str], list[float]] = defaultdict(
            lambda: [0.0, 0.0, 0.0, 0.0]
        )

        def put(
            group: str,
            tid: str | None,
            label: str | None,
            level: str,
            status: str,
            length: float = 0.0,
            area: float = 0.0,
            volume: float = 0.0,
        ) -> None:
            a = acc[(group, tid, label, level, status)]
            a[0] += 1
            a[1] += length
            a[2] += area
            a[3] += volume

        no_top: list[str] = []
        for w in self.on_levels(self.g.walls.values()):
            q = wall_qty(self.g, w)
            if q.net is None:
                no_top.append(w.id)
            tid = self.type_id(w.id)
            put("Wand", tid, self.type_label(tid), w.level, STATUS_DE[w.status], w.length,
                q.net or 0.0, q.volume or 0.0)  # fmt: skip
        for s in self.on_levels(self.g.slabs.values()):
            tid = self.type_id(s.id)
            put("Decke", tid, self.type_label(tid), s.level, STATUS_DE[s.status], 0.0,
                s.net.area, s.net.area * s.layers.core)  # fmt: skip
        for rg in self.on_levels(self.g.rooms.values()):
            el = self.m[rg.id]
            assert isinstance(el, Room)
            put("Raum", None, USE_DE[el.use], rg.level, "", 0.0, rg.area_fin, rg.volume or 0.0)
            if el.floor is not None:
                tid = el.floor.id
                put("Boden", tid, self.type_label(tid), rg.level, "", 0.0, rg.area_fin)
        sloped = self.sloped()
        for rf in self.on_levels(self.g.roofs.values()):
            tid = self.type_id(rf.id)
            put("Dach", tid, self.type_label(tid), rf.level, STATUS_DE[rf.status], 0.0,
                sloped.get(rf.id, 0.0))  # fmt: skip
        for o in self.on_levels(self.g.openings.values()):
            if o.kind == "niche":
                continue
            typ = opening_type(self.m, self.m[o.id])
            tid = None if typ is None else typ.id
            put(OPENING_DE[o.kind], tid, self.type_label(tid), o.level, STATUS_DE[o.status], 0.0,
                (o.hi - o.lo) * (o.top - o.sill))  # fmt: skip

        order = list(measures)
        keys = sorted(
            acc,
            key=lambda k: (
                order.index(k[0]),
                natural(k[1] or ""),
                k[2] or "",
                self.rank[k[3]],
                k[4],
            ),
        )
        rows: list[list[Cell]] = []
        for key in keys:
            group, tid, label, level, status = key
            n, length, area, volume = acc[key]
            has_l, has_a, has_v = measures[group]
            rows.append(
                [
                    group,
                    tid,
                    label,
                    level,
                    status or None,
                    int(n),
                    _q(length) if has_l else None,
                    _q(area) if has_a else None,
                    _q(volume) if has_v else None,
                ]
            )
        cols = [
            Col("Gruppe", 10),
            Col("Typ", 12),
            Col("Bezeichnung", 36),
            Col("Geschoss", 10),
            Col("Status", 10),
            Col("Anzahl", 9),
            Col("Länge m", 11, M),
            Col("Fläche m²", 12, M2),
            Col("Volumen m³", 12, M2),
        ]
        notes = [
            "Wand, Decke: Fläche netto, Volumen der Kernschicht. Raum: Fertigfläche (keine"
            " Wohnfläche). Boden: Fertigfläche der Räume mit diesem Bodenaufbau. Dach: geneigte"
            " Fläche. Tür, Fenster: Öffnungsfläche in Rohbaumaßen.",
            NOTE_BASIS,
        ]
        if no_top:
            notes.append(f"Wände ohne Oberkante gehen ohne Fläche ein: {' '.join(no_top)}")
        return Table("Mengen", self.title("Mengen"), cols, rows, None, notes)


def tables(d: Derived, level: str | None = None) -> list[Table]:
    """All tables of the model, or of one storey. Tables without rows are left out."""
    b = _Builder(d, level)
    all_tables = [
        b.rooms(),
        b.walls(),
        b.openings(),
        b.slabs(),
        b.roofs(),
        b.stairs(),
        b.quantities(),
    ]
    from uea.export.tables_elec import elec_tables

    return [t for t in [*all_tables, *elec_tables(d, level)] if t.rows]

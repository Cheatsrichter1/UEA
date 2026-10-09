"""Electrical tables for humans: boards, circuits, devices and luminaires (decision 0025).

Like the other tables they are plain data, German, and take their numbers from the derived
model. A sum is a connected load as declared on the elements, not a calculation of the circuit.
"""

from typing import Any

from uea.core.registry import natural
from uea.derive import Derived
from uea.export.tables import USE_DE, Cell, Col, Table
from uea.packs.elec.geometry import switching
from uea.packs.elec.kinds import Board, Circ, Rcd, Sock, Switch
from uea.packs.light.geometry import lum_type
from uea.packs.light.kinds import Lum

KIND_DE = {
    "sock": "Steckdose",
    "conn": "Anschluss",
    "switch": "Schalter",
    "data": "Datendose",
    "smoke": "Rauchwarnmelder",
}
SWITCHING_DE = {
    "single": "Ausschaltung",
    "two-way": "Wechselschaltung",
    "intermediate": "Kreuzschaltung",
}
SWITCH_DE = {1: "Ausschalter", 2: "Serienschalter"}
W0 = "0"
M3 = "0.000"
M2 = "0.00"
M1 = "0.0"


def _q(v: float) -> float:
    return round(v, 6) + 0.0


class _Elec:
    def __init__(self, d: Derived, level: str | None) -> None:
        self.d = d
        self.m = d.model
        self.g = d.arch
        self.level = level
        order = self.g.level_order()
        self.rank = {lv: i for i, lv in enumerate(order)}
        proj = self.m.of_kind("project")
        self.project = (proj[0].label or proj[0].id) if proj else "UEA"
        self.scope = "" if level is None else f" {level}"

    def title(self, name: str) -> str:
        return f"{name}{self.scope} – {self.project}"

    def room_name(self, room: str | None) -> str | None:
        if room is None:
            return None
        el = self.m[room]
        return el.label or USE_DE.get(getattr(el, "use", ""))

    def mounted(self, *kinds: str) -> list[Any]:
        """What is mounted on the chosen storeys, in storey order, then by id."""
        mine = [
            mt
            for mt in self.d.mounts.values()
            if mt.kind in kinds and (self.level is None or mt.level == self.level)
        ]
        return sorted(mine, key=lambda x: (self.rank[x.level], natural(x.id)))

    def where(self, mt: Any) -> str:
        return f"{mt.wall}.{mt.letter}" if mt.wall else "Decke"

    # ---------- the tables ----------

    def boards(self) -> Table:
        rows: list[list[Cell]] = []
        for mt in self.mounted("board"):
            el = self.m[mt.id]
            assert isinstance(el, Board)
            rcds = [r for r in self.m.of_kind("rcd") if isinstance(r, Rcd) and r.board.id == el.id]
            circuits = [c for c in self.d.elec.circuits.values() if c.board == el.id]
            rows.append(
                [
                    el.id,
                    el.label,
                    mt.level,
                    self.room_name(mt.room),
                    self.where(mt),
                    _q(mt.z - self.g.levels[mt.level].z),
                    el.main,
                    el.spd,
                    el.meters or None,
                    "ja" if el.media else None,
                    "; ".join(
                        f"{r.id} {r.rating.amps:g} A / {r.rating.idn * 1000:g} mA Typ {r.type}"
                        for r in rcds
                    )
                    or None,
                    len(circuits) or None,
                ]
            )
        cols = [
            Col("Nr", 8),
            Col("Bezeichnung", 24),
            Col("Geschoss", 10),
            Col("Raum", 18),
            Col("Wand", 8),
            Col("Höhe m", 9, M2),
            Col("Hauptschalter", 14),
            Col("Überspannungsschutz", 14),
            Col("Zähler", 8),
            Col("Medien", 8),
            Col("FI-Schutzschalter", 44),
            Col("Stromkreise", 11),
        ]
        notes = ["Höhe: Mitte des Verteilers über dem fertigen Fußboden."]
        return Table("Verteiler", self.title("Verteiler"), cols, rows, None, notes)

    def circuits(self) -> Table:
        rows: list[list[Cell]] = []
        on = {mt.id for mt in self.mounted("sock", "conn", "switch")}
        lums = {mt.id for mt in self.mounted("lum")}
        for cg in sorted(self.d.elec.circuits.values(), key=lambda c: natural(c.id)):
            el = self.m[cg.id]
            assert isinstance(el, Circ)
            devs = [self.m[k] for k in cg.devices if self.level is None or k in on]
            ls = [k for k in cg.lums if self.level is None or k in lums]
            if self.level is not None and not devs and not ls:
                continue
            outlets = sum(x.n for x in devs if isinstance(x, Sock))
            route = self.d.elec.routes.get(cg.id)
            far = route.far if route else None
            rows.append(
                [
                    cg.id,
                    el.label,
                    cg.rcd,
                    cg.board,
                    el.cable.fmt(),
                    el.breaker.fmt(),
                    cg.phases,
                    cg.phase.replace("-", "–"),
                    sum(1 for x in devs if x.kind == "sock") or None,
                    outlets or None,
                    sum(1 for x in devs if x.kind == "conn") or None,
                    sum(1 for x in devs if x.kind == "switch") or None,
                    len(ls) or None,
                    _q(cg.load_w) if cg.load_w else None,
                    _q(cg.capacity_w),
                    _q(route.total) if route and route.runs else None,
                    _q(far[1]) if far else None,
                ]
            )
        cols = [
            Col("Nr", 7),
            Col("Bezeichnung", 26),
            Col("FI", 7),
            Col("Verteiler", 9),
            Col("Leitung", 14),
            Col("Sicherung", 10),
            Col("Phasen", 8),
            Col("Phase", 8),
            Col("Steckdosen", 11),
            Col("Auslässe", 9),
            Col("Anschlüsse", 11),
            Col("Schalter", 9),
            Col("Leuchten", 9),
            Col("Anschlussleistung W", 14, W0),
            Col("Belastbarkeit W", 14, W0),
            Col("Leitungslänge m", 12, M1),
            Col("Längster Weg m", 12, M1),
        ]
        notes = [
            "Phase: abgeleitet, einphasige Stromkreise nacheinander auf die Phase mit der kleinsten"
            " angenommenen Last (mindestens 1000 W je Stromkreis); keine Lastberechnung.",
            "Anschlussleistung: Leuchten, Anschlüsse und Einspeisungen mit ihrer angegebenen"
            " Leistung; Steckdosen haben keine angegebene Leistung. Belastbarkeit: Nennstrom der"
            " Sicherung mal 230 V mal Phasen. Keine Leitungsberechnung.",
            "Leitungslänge: abgeleitet, Summe aller Abschnitte ab dem Verteiler (Blatt Leitungen);"
            " Längster Weg: vom Verteiler bis zum entferntesten Gerät.",
        ]
        if self.level is not None:
            notes.append(
                "Zahlen nur für die Geräte dieses Geschosses, Längen für den ganzen Kreis."
            )
        return Table("Stromkreise", self.title("Stromkreise"), cols, rows, None, notes)

    def devices(self) -> Table:
        rows: list[list[Cell]] = []
        for mt in self.mounted("sock", "conn", "switch", "data", "smoke"):
            el = self.m[mt.id]
            circuit = getattr(el, "circuit", None) or getattr(el, "board", None)
            kind = KIND_DE[mt.kind]
            how = None
            if isinstance(el, Switch):
                n = len(el.ctl.groups)
                how = SWITCH_DE.get(n, f"{n}-fach") + (", dimmbar" if el.dim else "")
            rows.append(
                [
                    el.id,
                    kind,
                    mt.level,
                    mt.room,
                    self.room_name(mt.room),
                    self.where(mt),
                    None if mt.wall is None else _q(mt.s),
                    _q(mt.z - self.g.levels[mt.level].z),
                    None if circuit is None else circuit.id,
                    getattr(el, "n", None),
                    how,
                    el.label,
                ]
            )
        cols = [
            Col("Nr", 7),
            Col("Art", 16),
            Col("Geschoss", 10),
            Col("Raum", 7),
            Col("Raumname", 18),
            Col("Wand", 8),
            Col("Lage m", 9, M3),
            Col("Höhe m", 9, M2),
            Col("Stromkreis / Verteiler", 12),
            Col("Anzahl", 8),
            Col("Ausführung", 20),
            Col("Bemerkung", 24),
        ]
        sockets = sum(r[9] for r in rows if r[1] == KIND_DE["sock"] and isinstance(r[9], int))
        total: list[Cell] = ["Summe Steckdosen", None, None, None, None, None, None, None, None]
        total += [sockets, None, None]
        notes = [
            "Lage: Abstand der Gerätemitte entlang der Wand, wie die Öffnungen es angeben;"
            " Höhe: Mitte des Geräts über dem fertigen Fußboden. Wand: Wand und Seite.",
        ]
        return Table(
            "Installationsgeräte", self.title("Installationsgeräte"), cols, rows, total, notes
        )

    def luminaires(self) -> Table:
        rows: list[list[Cell]] = []
        e = self.d.elec
        for mt in self.mounted("lum"):
            el = self.m[mt.id]
            assert isinstance(el, Lum)
            t = lum_type(self.m, el)
            sws = e.controls.get(el.id, [])
            rows.append(
                [
                    el.id,
                    mt.level,
                    mt.room,
                    self.room_name(mt.room),
                    t.id if t else None,
                    t.w if t and t.w else None,
                    t.flux if t and t.flux else None,
                    "Wand" if mt.wall else "Decke",
                    _q(mt.z - self.g.levels[mt.level].z),
                    ", ".join(sws) or None,
                    SWITCHING_DE[switching(len(sws))] if sws else None,
                    ", ".join(e.lum_circuits.get(el.id, [])) or None,
                ]
            )
        cols = [
            Col("Nr", 7),
            Col("Geschoss", 10),
            Col("Raum", 7),
            Col("Raumname", 18),
            Col("Typ", 12),
            Col("Leistung W", 11, W0),
            Col("Lichtstrom lm", 12, W0),
            Col("Montage", 9),
            Col("Höhe m", 9, M2),
            Col("Schalter", 14),
            Col("Schaltung", 16),
            Col("Stromkreis", 11),
        ]
        watts = _q(sum(r[5] for r in rows if isinstance(r[5], int | float)))
        lumen = _q(sum(r[6] for r in rows if isinstance(r[6], int | float)))
        total: list[Cell] = ["Summe", None, None, None, None, watts, lumen, *[None] * 5]
        notes = ["Schaltung: nach der Zahl der Schalter, die die Leuchte schalten."]
        return Table("Leuchten", self.title("Leuchten"), cols, rows, total, notes)

    def runs(self) -> Table:
        rows = _runs_rows(self)
        cols = [
            Col("Stromkreis", 12),
            Col("Von", 8),
            Col("Nach", 8),
            Col("Geschoss", 10),
            Col("Länge m", 10, M1),
        ]
        total: list[Cell] = ["Summe", None, None, None]
        total.append(_q(sum(r[4] for r in rows if isinstance(r[4], int | float))))
        notes = [
            "Abgeleitet: das kürzeste Leitungsnetz vom Verteiler über alle Geräte des Stromkreises,"
            " gemessen als Summe der Wege in x, y und z (Leitungen laufen entlang der Wände und"
            " senkrecht daneben), je Abschnitt 0,3 m für die Anschlüsse. Ohne Schächte: die"
            " Decke wird an der günstigsten Stelle durchstoßen. Datenleitungen: ein Abschnitt je"
            " Port, Länge je Dose mal Anzahl der Ports.",
        ]
        return Table("Leitungen", self.title("Leitungen"), cols, rows, total, notes)

    def quantities(self) -> Table:
        rows = _quantity_rows(self)
        cols = [Col("Leitung", 28), Col("Stromkreise / Dosen", 12), Col("Länge m", 10, M1)]
        total: list[Cell] = ["Summe", None, _q(sum(r[2] for r in rows if isinstance(r[2], float)))]
        notes = [
            "Abgeleitete Längen ohne Verschnitt und ohne Zuleitung zum Hausanschluss; keine"
            " Ausschreibungsmenge.",
        ]
        if self.level is not None:
            notes.append("Mengen für das ganze Gebäude.")
        return Table("Kabelmengen", self.title("Kabelmengen"), cols, rows, total, notes)


def _runs_rows(b: _Elec) -> list[list[Cell]]:
    e = b.d.elec
    rows: list[list[Cell]] = []
    here = {mt.id for mt in b.mounted("board", "sock", "conn", "switch", "data", "lum")}
    for cid in sorted(e.routes, key=natural):
        for r in e.routes[cid].runs:
            if b.level is None or r.b in here:
                rows.append([cid, r.a, r.b, b.d.mounts[r.b].level, _q(r.length)])
    for k in sorted(e.homeruns, key=natural):
        r = e.homeruns[k]
        if b.level is None or r.b in here:
            n = int(getattr(b.m[k], "n", 1))
            rows.append([f"Daten {r.a}", r.a, r.b, b.d.mounts[r.b].level, _q(r.length * n)])
    return rows


def _quantity_rows(b: _Elec) -> list[list[Cell]]:
    e = b.d.elec
    by_cable: dict[str, list[float]] = {}
    for cid, route in e.routes.items():
        el = b.m[cid]
        assert isinstance(el, Circ)
        got = by_cable.setdefault(el.cable.fmt(), [0.0, 0.0])
        got[0] += 1
        got[1] += route.total
    rows: list[list[Cell]] = [
        [name, int(n), _q(m)] for name, (n, m) in sorted(by_cable.items(), key=lambda kv: kv[0])
    ]
    data = [(k, r) for k, r in e.homeruns.items()]
    if data:
        ports = sum(int(getattr(b.m[k], "n", 1)) for k, _ in data)
        meters = sum(r.length * int(getattr(b.m[k], "n", 1)) for k, r in data)
        rows.append([f"Datenleitung ({ports} Ports)", len(data), _q(meters)])
    return rows


def elec_tables(d: Derived, level: str | None = None) -> list[Table]:
    """The electrical tables of the model, or of one storey; tables without rows are left out."""
    b = _Elec(d, level)
    tables = [b.boards(), b.circuits(), b.devices(), b.luminaires(), b.runs(), b.quantities()]
    return [t for t in tables if t.rows]

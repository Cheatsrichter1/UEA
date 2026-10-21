"""The LV for humans and bidders: titles, positions, quantities, texts and prices (0048).

The structure and quantities come from the derived LV (`packs/lv`); the long texts come from
the office's table `lv-texts`, its own texts, installed like a norm table (`uea data add`).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from uea.calc import data, de
from uea.calc.data import Col, Spec
from uea.derive import Derived, Report
from uea.packs.lv.kinds import Pos, Title

if TYPE_CHECKING:
    from uea.export.tables import Table

TEXTS = Spec(
    "lv-texts",
    "Long texts of LV positions",
    "the office's own texts",
    (
        Col("key", "text", "what a position names with text=: FE-01"),
        Col("text", "text", "the long text; a line break or | starts a new paragraph"),
    ),
    ("key",),
    "The office's own position texts. Standard texts such as STLB-Bau are licensed; an office"
    " with a licence may put them here for its projects.",
)


@dataclass
class LvPos:
    id: str
    oz: str
    """Its number within its title: 0010."""
    short: str
    long: list[str]
    """Paragraphs of its long text; empty if it has none."""
    qty: float
    unit: str
    ep: float | None
    kg: int | None

    @property
    def gp(self) -> float | None:
        return self.qty * self.ep if self.ep is not None else None


@dataclass
class LvTitle:
    id: str
    oz: str
    text: str
    positions: list[LvPos] = field(default_factory=list[LvPos])


@dataclass
class Lv:
    titles: list[LvTitle]
    texts: str | None
    """The table of long texts used, as a result records it; None if none."""
    missing: list[str]
    """Positions whose text= the office's table does not hold (or no table is installed)."""

    @property
    def positions(self) -> list[LvPos]:
        return [p for t in self.titles for p in t.positions]


class LvError(ValueError):
    pass


def build(d: Derived, rep: Report | None = None) -> Lv:
    """The LV of the model. With the report, LvError if it has an E-LV issue; without, a
    position that has no quantity (such an issue) is left out."""
    bad = [i for i in rep.issues if i.code.startswith("E-LV")] if rep is not None else []
    if bad:
        raise LvError("fix the LV first: " + "; ".join(i.text() for i in bad))
    lv = d.lv
    table = data.load(TEXTS)
    texts = {str(r["key"]).casefold(): str(r["text"]) for r in table.rows} if table else {}
    missing: list[str] = []
    titles: list[LvTitle] = []
    for tid, pids in lv.positions.items():
        t = d.model[tid]
        assert isinstance(t, Title)
        title = LvTitle(tid, lv.oz[tid], t.label or tid)
        for pid in pids:
            p = d.model[pid]
            assert isinstance(p, Pos)
            q = lv.qty.get(pid)
            if q is None:
                continue
            long: list[str] = []
            if p.text is not None:
                got = texts.get(p.text.casefold())
                if got is None:
                    missing.append(pid)
                else:
                    long = [x.strip() for x in got.replace("|", "\n").splitlines() if x.strip()]
            oz = lv.oz[pid].split(".", 1)[1]
            title.positions.append(
                LvPos(pid, oz, p.label or pid, long, q.value, q.unit, p.ep, p.kg)
            )
        titles.append(title)
    return Lv(titles, table.cite() if table else None, missing)


def lv_tables(d: Derived) -> list["Table"]:
    """The LV as a sheet, and the costs per DIN 276 cost group if prices are given."""
    from uea.export.tables import M2, Cell, M, Table
    from uea.export.tables import Col as TCol

    lv = build(d)
    proj = d.model.of_kind("project")
    name = (proj[0].label or proj[0].id) if proj else "UEA"
    rows: list[list[Cell]] = []
    for t in lv.titles:
        sums = [p.gp for p in t.positions if p.gp is not None]
        rows.append(
            [t.oz, t.text, None, None, None, None, round(sum(sums), 2) if sums else None, None]
        )
        for p in t.positions:
            rows.append(
                [
                    f"{t.oz}.{p.oz}",
                    p.short,
                    " ".join(p.long) or None,
                    round(p.qty, 3),
                    p.unit,
                    p.ep,
                    round(p.gp, 2) if p.gp is not None else None,
                    p.kg,
                ]
            )
    gps = [p.gp for p in lv.positions if p.gp is not None]
    cols = [
        TCol("OZ", 10),
        TCol("Kurztext", 40),
        TCol("Langtext", 60),
        TCol("Menge", 12, M),
        TCol("Einheit", 8),
        TCol("EP €", 11, M2),
        TCol("GP €", 13, M2),
        TCol("KG", 6),
    ]
    total: list[Cell] = ["Summe", None, None, None, None, None, round(sum(gps), 2), None]
    notes = [
        "Mengen aus dem UEA-Modell abgeleitet, ohne Zuschläge; Abrechnung nach Aufmaß und VOB/C.",
        "Preise sind Schätzungen des Büros (EP); ohne EP keine Summe.",
    ]
    if lv.texts:
        notes.append(f"Langtexte: {lv.texts}")
    if lv.missing:
        notes.append(f"Ohne Langtext (Schlüssel fehlt in lv-texts): {' '.join(lv.missing)}")
    out = [Table("LV", f"Leistungsverzeichnis – {name}", cols, rows, total if gps else None, notes)]
    if gps:
        by_kg: dict[int | None, list[float]] = {}
        for p in lv.positions:
            if p.gp is not None:
                by_kg.setdefault(p.kg, []).append(p.gp)
        krows: list[list[Cell]] = [
            [k if k is not None else "ohne KG", len(v), round(sum(v), 2)]
            for k, v in sorted(by_kg.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        ]
        kcols = [TCol("KG (DIN 276)", 14), TCol("Positionen", 11), TCol("Summe €", 14, M2)]
        ktotal: list[Cell] = ["Summe", None, round(sum(gps), 2)]
        knotes = ["Summen der bepreisten Positionen je Kostengruppe; netto, ohne Umsatzsteuer."]
        out.append(Table("Kosten", f"Kosten nach DIN 276 – {name}", kcols, krows, ktotal, knotes))
    return out


def bid_tables(d: Derived) -> list["Table"]:
    """The bids after the arithmetic check (0051): one row per bid, and the Preisspiegel with
    each bid's unit and total price per position. The flags of `uea calc bids` depend on its
    threshold (dev=) and stay in its report."""
    from uea.calc.bids import ranks
    from uea.export.tables import M2, Cell, M, Table
    from uea.export.tables import Col as TCol
    from uea.packs.bid.geometry import QTY_TOL, gp
    from uea.packs.bid.kinds import Bid

    all_bids = d.bid.bids
    if not all_bids:
        return []
    proj = d.model.of_kind("project")
    name = (proj[0].label or proj[0].id) if proj else "UEA"
    rk = ranks(all_bids)
    keys = list(all_bids)
    rows: list[list[Cell]] = []
    notes: list[str] = []
    for k, s in all_bids.items():
        b = d.model[k]
        assert isinstance(b, Bid)
        rank = f"{rk[k][0]} von {rk[k][1]}" if k in rk else "unvollständig"
        rows.append(
            [
                k,
                b.label,
                b.date,
                " ".join(d.lv.oz[t] for t in s.titles) or None,
                round(s.checked, 2),
                b.total,
                s.disc or None,
                round(s.net, 2),
                rank,
            ]
        )
        if s.unpriced:
            notes.append(f"{k}: ohne Preis für {', '.join(d.lv.oz[p] for p in s.unpriced)}")
        if b.total is not None and abs(b.total - s.checked) > 0.005:
            notes.append(
                f"{k}: angegebene Summe {de(b.total)} €, rechnerisch geprüft {de(s.checked)} €."
            )
    cols = [
        TCol("Angebot", 9),
        TCol("Bieter", 30),
        TCol("Datum", 11),
        TCol("Titel", 10),
        TCol("Summe geprüft €", 15, M2),
        TCol("Summe angegeben €", 15, M2),
        TCol("Nachlass %", 10, M2),
        TCol("Wertungssumme €", 15, M2),
        TCol("Rang", 13),
    ]
    notes += [
        "Rechnerische Prüfung nach VOB/A § 16c Abs. 2: Menge des Angebots × Einheitspreis;"
        " weicht der Gesamtpreis des Bieters ab, ist der Einheitspreis maßgebend.",
        "Rang nach der Wertungssumme unter den vollständigen Angeboten auf dieselben Titel,"
        " nur nach dem Preis; über den Zuschlag entscheidet der Auftraggeber.",
    ]
    out = [Table("Angebote", f"Angebote – {name}", cols, rows, None, notes)]

    mcols = [TCol("OZ", 10), TCol("Kurztext", 40), TCol("Menge", 12, M), TCol("Einheit", 8)]
    for k in keys:
        mcols += [TCol(f"EP {k} €", 11, M2), TCol(f"GP {k} €", 13, M2)]
    mrows: list[list[Cell]] = []
    mnotes: list[str] = []
    for t, pids in d.lv.positions.items():
        if not any(t in all_bids[k].titles for k in keys):
            continue
        el = d.model[t]
        assert isinstance(el, Title)
        row: list[Cell] = [d.lv.oz[t], el.label or t, None, None]
        for k in keys:
            v = all_bids[k].by_title.get(t)
            row += [None, round(v, 2) if v is not None else None]
        mrows.append(row)
        for pid in pids:
            q = d.lv.qty.get(pid)
            if q is None:
                continue
            p = d.model[pid]
            row = [d.lv.oz[pid], p.label or pid, round(q.value, 3), q.unit]
            for k in keys:
                pr = all_bids[k].prices.get(pid)
                if pr is None:
                    row += ["–" if t in all_bids[k].titles else None, None]
                    continue
                row += [pr.ep, gp(d, pr)]
                if pr.qty is not None and abs(pr.qty - q.value) > QTY_TOL:
                    mnotes.append(
                        f"{k}, {d.lv.oz[pid]}: Menge des Angebots {de(pr.qty, 3)} {q.unit},"
                        f" im LV jetzt {de(q.value, 3)} {q.unit}."
                    )
                if pr.gp is not None:
                    mnotes.append(
                        f"{k}, {d.lv.oz[pid]}: Gesamtpreis des Bieters {de(pr.gp)} €;"
                        " der Einheitspreis ist maßgebend."
                    )
            mrows.append(row)
    total: list[Cell] = ["Summe geprüft", None, None, None]
    for k in keys:
        total += [None, round(all_bids[k].checked, 2)]
    mnotes += [
        "GP = Menge des Angebots × EP, auf Cent gerundet; Titelzeilen tragen die Summe je Titel.",
        "– : Position eines angebotenen Titels ohne Preis.",
        "Einheitspreise fern vom Median: uea calc bids (Schwelle dev=, Sache des Büros).",
    ]
    out.append(Table("Preisspiegel", f"Preisspiegel – {name}", mcols, mrows, total, mnotes))
    return out

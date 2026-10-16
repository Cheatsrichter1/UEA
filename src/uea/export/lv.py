"""The LV for humans and bidders: titles, positions, quantities, texts and prices (0048).

The structure and quantities come from the derived LV (`packs/lv`); the long texts come from
the office's table `lv-texts`, its own texts, installed like a norm table (`uea data add`).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from uea.calc import data
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

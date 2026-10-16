"""Cost estimate (Kostenschätzung) per DIN 276 from the DIN 277 reference quantities.

A `norm` calculator. DIN 276 is licensed: its text and the titles of its cost groups are not
in this repository. The office supplies its reference prices per cost group (Kostenkennwerte,
from its own projects or a licensed source) in the table `cost-ref`, each on a reference
quantity of DIN 277: BGF, NRF, NUF, KGF or BRI (`uea calc din277`). The estimate is the
reference quantity times the price for each row; rows sum up to the first level of the cost
groups (100 to 800) and to the total, net and with VAT.

Where the LV (`lv.uea`) has priced positions with a cost group, the sum of those inside each
row's group is shown beside the estimate, for comparison; it is not added.
"""

from dataclasses import dataclass

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.fmt import ar
from uea.packs.arch.din277 import USES, reference
from uea.packs.lv.kinds import Pos

VERSION = "0.1.0"
NORM = "DIN 276:2018-12"
BASES = ("bgf", "nrf", "nuf", "kgf", "bri")
UNIT = {"bgf": "m²", "nrf": "m²", "nuf": "m²", "kgf": "m²", "bri": "m³"}

REF = Spec(
    "cost-ref",
    "Reference prices per cost group (Kostenkennwerte)",
    "DIN 276; the office's own prices",
    (
        Col("kg", "num", "cost group, three digits: 300, 330, 334"),
        Col("name", "text", "the office's name of the cost group"),
        Col("basis", "text", "reference quantity per DIN 277", choices=BASES),
        Col("price", "num", "net price per m² or m³ of the basis, €", sign="zero"),
    ),
    ("kg",),
    "One row per cost group the estimate covers, at any level (300, or 330 and 340). A group"
    " and one of its own subgroups may not both have a row.",
)

PARAMS = (
    Param("ust", float, 19.0, "VAT in percent, for the gross total"),
    Param(
        "stand",
        str,
        None,
        "the price level (Kostenstand) of the prices, e.g. 2026-Q3",
        optional=True,
    ),
)


def span(kg: int) -> tuple[int, int]:
    """The cost groups a group covers: 300 covers 300-399, 330 covers 330-339."""
    if kg % 100 == 0:
        return kg, kg + 99
    if kg % 10 == 0:
        return kg, kg + 9
    return kg, kg


@dataclass
class CostRow:
    kg: int
    name: str
    basis: str
    qty: float
    price: float
    lv: float | None
    """The priced LV positions in this group, for comparison."""

    @property
    def cost(self) -> float:
        return self.qty * self.price


def estimate(d: Derived, env: Env) -> list[CostRow]:
    """The rows of the estimate. ValueError if a row cannot be computed."""
    table = env.table(REF)
    ref = reference(d, env)
    rows: list[CostRow] = []
    seen: list[tuple[int, int, int]] = []
    for r in table.rows:
        kg_f, basis = r["kg"], str(r["basis"])
        assert isinstance(kg_f, float)
        if not kg_f.is_integer() or not 100 <= kg_f <= 899:
            raise ValueError(f"cost-ref: kg {kg_f:g} is not a cost group (three digits)")
        kg = int(kg_f)
        lo, hi = span(kg)
        for other, olo, ohi in seen:
            if lo <= ohi and olo <= hi:
                raise ValueError(f"cost-ref: {kg} and {other} overlap; give a group or its parts")
        seen.append((kg, lo, hi))
        qty = ref[basis]
        if qty is None:
            why = (
                "a storey has no roof over it (uea calc din277)"
                if basis == "bri"
                else "the table din277-uses is not installed (uea data show din277-uses)"
            )
            raise ValueError(f"cost-ref: {kg} is priced on {basis.upper()}, but {why}")
        price = r["price"]
        assert isinstance(price, float)
        rows.append(CostRow(kg, str(r["name"]), basis, qty, price, _lv(d, lo, hi)))
    return sorted(rows, key=lambda x: x.kg)


def _lv(d: Derived, lo: int, hi: int) -> float | None:
    out: float | None = None
    for p in d.model.of_kind("pos"):
        assert isinstance(p, Pos)
        q = d.lv.qty.get(p.id)
        if p.kg is not None and lo <= p.kg <= hi and p.ep is not None and q is not None:
            out = (out or 0.0) + q.value * p.ep
    return out


def costs(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("the estimate covers the whole project; give no scope")
    rows = estimate(d, env)
    if not rows:
        raise ValueError("cost-ref has no rows")
    ust = float(env.param("ust"))
    net = sum(r.cost for r in rows)
    vat = net * ust / 100
    first: dict[int, float] = {}
    for r in rows:
        first[r.kg // 100 * 100] = first.get(r.kg // 100 * 100, 0.0) + r.cost
    lines = [
        f"{r.kg} {r.name}: {ar(r.qty)} {UNIT[r.basis]} {r.basis.upper()} × {ar(r.price)}"
        f" = {ar(r.cost)} €" + (f" (LV {ar(r.lv)} €)" if r.lv is not None else "")
        for r in rows
    ]
    lines.append(" · ".join(f"{k} {ar(v)}" for k, v in sorted(first.items())))
    lines.append(f"net {ar(net)} € · VAT {ust:g} % {ar(vat)} € · gross {ar(net + vat)} €")
    return Output(
        lines=lines,
        report=_report(d, rows, first, net, ust, env.param("stand")),
        data={
            "rows": [
                {
                    "kg": r.kg,
                    "name": r.name,
                    "basis": r.basis,
                    "qty": round(r.qty, 4),
                    "price": r.price,
                    "cost": round(r.cost, 2),
                    "lv": round(r.lv, 2) if r.lv is not None else None,
                }
                for r in rows
            ],
            "first": {str(k): round(v, 2) for k, v in sorted(first.items())},
            "net": round(net, 2),
            "vat": round(vat, 2),
            "gross": round(net + vat, 2),
        },
        inputs={
            "reference": {k: round(v, 4) for k, v in reference(d, env).items() if v is not None}
        },
    )


def _report(
    d: Derived,
    rows: list[CostRow],
    first: dict[int, float],
    net: float,
    ust: float,
    stand: str | None,
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    table = md_table(
        ["KG", "Bezeichnung", "Bezugsgröße", "Menge", "Kennwert €", "Kosten €", "aus LV €"],
        [
            [
                str(r.kg),
                r.name,
                r.basis.upper(),
                f"{de(r.qty)} {UNIT[r.basis]}",
                de(r.price),
                de(r.cost),
                de(r.lv) if r.lv is not None else "",
            ]
            for r in rows
        ],
        (3, 4, 5, 6),
    )
    sums = md_table(["KG", "Kosten €"], [[str(k), de(v)] for k, v in sorted(first.items())], (1,))
    vat = net * ust / 100
    out = [
        f"# Kostenschätzung nach DIN 276: {title}",
        "",
        f"Kostenstand: {stand}" if stand else "Kostenstand: nicht angegeben",
        "",
        table,
        "",
        "## Summen der ersten Ebene",
        "",
        sums,
        "",
        f"- Summe netto: {de(net)} €",
        f"- Umsatzsteuer {de(ust, 0)} %: {de(vat)} €",
        f"- **Summe brutto: {de(net + vat)} €**",
        "",
        "## Verfahren",
        "",
        "- Kosten je Kostengruppe = Bezugsgröße nach DIN 277 (aus dem Modell, `uea calc din277`)"
        " × Kostenkennwert des Büros (Tabelle cost-ref).",
        "- Die Spalte „aus LV“ zeigt zum Vergleich die Summe der bepreisten LV-Positionen dieser"
        " Kostengruppe; sie geht nicht in die Summe ein.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


COSTS = Calculator(
    name="costs",
    title="Cost estimate per DIN 276 (Kostenschätzung)",
    kind="norm",
    version=VERSION,
    fn=costs,
    norm=NORM,
    params=PARAMS,
    tables=(REF, USES),
)

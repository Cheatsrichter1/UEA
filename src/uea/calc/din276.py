"""Costs per DIN 276: the estimate from the DIN 277 reference quantities, and the calculation
from the priced LV.

A `norm` calculator. DIN 276 is licensed: its text and the titles of its cost groups are not
in this repository. The office supplies its reference prices per cost group (Kostenkennwerte,
from its own projects or a licensed source) in the table `cost-ref`, each on a reference
quantity of DIN 277: BGF, NRF, NUF, KGF or BRI (`uea calc din277`). The estimate is the
reference quantity times the price for each row; rows sum up to the first level of the cost
groups (100 to 800) and to the total, net and with VAT.

Where the LV (`lv.uea`) has priced positions with a cost group, the sum of those inside each
row's group is shown beside the estimate, for comparison; it is not added. The calculation
(Kostenberechnung, stage=calculation) takes the priced LV per cost group instead, and keeps a
reference price's row only where no priced position falls in its group.
"""

from dataclasses import dataclass

from uea.calc import Calculator, Env, Output, Param, data, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.fmt import ar
from uea.packs.arch.din277 import USES, reference
from uea.packs.lv.kinds import Pos

VERSION = "0.2.0"
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
    Param(
        "stage",
        str,
        "estimate",
        "estimate (Kostenschätzung, by reference prices) or calculation (Kostenberechnung, from"
        " the priced LV, the estimate for what it does not price)",
        ("estimate", "calculation"),
    ),
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


@dataclass
class Cost:
    """A row of the estimate or of the calculation."""

    kg: int
    name: str
    cost: float
    source: str
    """estimate (a reference price) or lv (priced positions)."""
    how: str
    """How it was found: `161.44 m² BGF × 1000.00`, `LV p1 p4`."""


def priced(d: Derived) -> list[Pos]:
    """The LV's positions with a price, a cost group and a quantity."""
    out: list[Pos] = []
    for p in d.model.of_kind("pos"):
        assert isinstance(p, Pos)
        if p.ep is not None and p.kg is not None and p.id in d.lv.qty:
            out.append(p)
    return out


def calculation(d: Derived, env: Env) -> tuple[list[Cost], list[str]]:
    """The Kostenberechnung: the priced LV per cost group; a reference price's row stays
    where no priced position falls in its group. Also what is left out, and why."""
    lv = priced(d)
    if not lv:
        raise ValueError(
            "the LV has no positions with ep= and kg=, so there is no calculation yet;"
            " use stage=estimate"
        )
    by_kg: dict[int, list[Pos]] = {}
    for p in lv:
        assert p.kg is not None
        by_kg.setdefault(p.kg, []).append(p)
    est = estimate(d, env) if data.load(REF) is not None else []
    notes: list[str] = []
    rows: list[Cost] = []
    for e in est:
        lo, hi = span(e.kg)
        if any(lo <= k <= hi for k in by_kg):
            notes.append(f"{e.kg}: priced in the LV; its estimate of {ar(e.cost)} € is not used")
        else:
            rows.append(Cost(e.kg, e.name, e.cost, "estimate", _how(e)))
    for kg, ps in by_kg.items():
        name = next((e.name for e in est if span(e.kg)[0] <= kg <= span(e.kg)[1]), "")
        cost = sum(d.lv.qty[p.id].value * (p.ep or 0.0) for p in ps)
        rows.append(Cost(kg, name, cost, "lv", "LV " + " ".join(p.id for p in ps)))
    unpriced = [
        p.id for p in d.model.of_kind("pos") if getattr(p, "ep", None) is None and p.id in d.lv.qty
    ]
    if unpriced:
        notes.append(f"no price (ep=), not in it: {' '.join(unpriced)}")
    nokg = [
        p.id
        for p in d.model.of_kind("pos")
        if getattr(p, "ep", None) is not None and getattr(p, "kg", None) is None
    ]
    if nokg:
        notes.append(f"no cost group (kg=), not in it: {' '.join(nokg)}")
    return sorted(rows, key=lambda r: r.kg), notes


def cost_rows(d: Derived, env: Env, stage: str) -> tuple[list[Cost], list[str]]:
    """The rows of the estimate or of the calculation, and notes on what is left out."""
    if stage == "calculation":
        return calculation(d, env)
    return [Cost(e.kg, e.name, e.cost, "estimate", _how(e)) for e in estimate(d, env)], []


def _how(e: CostRow) -> str:
    return f"{ar(e.qty)} {UNIT[e.basis]} {e.basis.upper()} × {ar(e.price)}"


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
        raise ValueError("the costs cover the whole project; give no scope")
    stage = str(env.param("stage"))
    rows, notes = cost_rows(d, env, stage)
    if not rows:
        raise ValueError("cost-ref has no rows")
    lv_beside: dict[int, float] = {}
    if stage == "estimate":
        lv_beside = {e.kg: e.lv for e in estimate(d, env) if e.lv is not None}
    ust = float(env.param("ust"))
    net = sum(r.cost for r in rows)
    vat = net * ust / 100
    first: dict[int, float] = {}
    for r in rows:
        first[r.kg // 100 * 100] = first.get(r.kg // 100 * 100, 0.0) + r.cost
    lines = [
        f"{r.kg} {r.name}: {r.how} = {ar(r.cost)} €".replace(" :", ":")
        + (f" (LV {ar(lv_beside[r.kg])} €)" if r.kg in lv_beside else "")
        for r in rows
    ]
    lines += notes
    lines.append(" · ".join(f"{k} {ar(v)}" for k, v in sorted(first.items())))
    lines.append(f"net {ar(net)} € · VAT {ust:g} % {ar(vat)} € · gross {ar(net + vat)} €")
    ref = reference(d, env) if stage == "estimate" or data.load(REF) is not None else {}
    return Output(
        lines=lines,
        report=_report(d, stage, rows, lv_beside, notes, first, net, ust, env.param("stand")),
        data={
            "stage": stage,
            "rows": [
                {
                    "kg": r.kg,
                    "name": r.name,
                    "source": r.source,
                    "how": r.how,
                    "cost": round(r.cost, 2),
                    "lv": round(lv_beside[r.kg], 2) if r.kg in lv_beside else None,
                }
                for r in rows
            ],
            "notes": notes,
            "first": {str(k): round(v, 2) for k, v in sorted(first.items())},
            "net": round(net, 2),
            "vat": round(vat, 2),
            "gross": round(net + vat, 2),
        },
        inputs={"reference": {k: round(v, 4) for k, v in ref.items() if v is not None}},
    )


def _report(
    d: Derived,
    stage: str,
    rows: list[Cost],
    lv_beside: dict[int, float],
    notes: list[str],
    first: dict[int, float],
    net: float,
    ust: float,
    stand: str | None,
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    kind = "Kostenschätzung" if stage == "estimate" else "Kostenberechnung"
    source = {"estimate": "Kennwert", "lv": "LV"}
    head = ["KG", "Bezeichnung", "Grundlage", "Ermittlung", "Kosten €"]
    if lv_beside:
        head.append("aus LV €")
    body: list[list[str]] = []
    for r in rows:
        row = [str(r.kg), r.name, source[r.source], r.how.replace(".", ","), de(r.cost)]
        if lv_beside:
            row.append(de(lv_beside[r.kg]) if r.kg in lv_beside else "")
        body.append(row)
    sums = md_table(["KG", "Kosten €"], [[str(k), de(v)] for k, v in sorted(first.items())], (1,))
    vat = net * ust / 100
    out = [
        f"# {kind} nach DIN 276: {title}",
        "",
        f"Kostenstand: {stand}" if stand else "Kostenstand: nicht angegeben",
        "",
        md_table(head, body, (4, 5)),
        "",
    ]
    if notes:
        out += [f"- {n}" for n in notes] + [""]
    out += [
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
        "- Kennwert: Bezugsgröße nach DIN 277 (aus dem Modell, `uea calc din277`) × Kostenkennwert"
        " des Büros (Tabelle cost-ref).",
        "- LV: Summe der bepreisten Positionen des Leistungsverzeichnisses mit dieser"
        " Kostengruppe (Menge aus dem Modell × Einheitspreis).",
        "- In der Kostenberechnung ersetzt das LV den Kennwert einer Kostengruppe, sobald es eine"
        " bepreiste Position darin hat; in der Kostenschätzung steht es nur zum Vergleich daneben.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


COSTS = Calculator(
    name="costs",
    title="Costs per DIN 276 (Kostenschätzung, Kostenberechnung)",
    kind="norm",
    version=VERSION,
    fn=costs,
    norm=NORM,
    params=PARAMS,
    tables=(REF, USES),
)

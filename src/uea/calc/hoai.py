"""The fee (Honorar) per HOAI 2021 for a building, its technical equipment or its structure.

A `norm` calculator. The HOAI is a federal ordinance (an amtliches Werk), so its rules can be
implemented and cited freely. Its fee tables (Honorartafeln) are not typed into this repository
from memory: the office copies them once from the official text into the table `hoai-fees`
(decision 0049), and every result records which copy it used.

- § 33 Abs. 2: the chargeable costs (anrechenbare Kosten) of a building are the costs of its
  construction (KG 300) and of its technical equipment (KG 400): the latter fully up to 25 % of
  the former, the part above that by half. They come from the cost estimate (`uea calc
  costs`), net (§ 4 Abs. 1 and § 16), or are given with kosten=.
- § 54: the chargeable costs of the technical equipment are its costs (KG 400); the estimate
  gives them for all equipment together, or kosten= for one group of systems.
- § 50: the chargeable costs of the structure are given with kosten=.
- § 13: fees between the table's steps are interpolated linearly.
- § 5, § 35, § 52, § 56: the fee zone (I to V) and the rate between the base rate
  (Basishonorarsatz) and the upper rate (oberer Honorarsatz) are agreed; rate=0 is the base
  rate, rate=100 the upper one.
- § 34 Abs. 3, § 51 Abs. 1, § 55 Abs. 1: the share of each service phase (Leistungsphase).
- § 7 Abs. 2: chargeable costs outside the table: the fee is free to agree, so it stops.
- § 6 Abs. 2, § 36: a surcharge for conversions (Umbauzuschlag), as agreed.
- § 14: incidental costs (Nebenkosten) as agreed, in percent of the fee.
- § 16: VAT on top.
"""

from dataclasses import dataclass
from itertools import pairwise

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.calc.din276 import REF, estimate
from uea.derive import Derived
from uea.fmt import ar
from uea.packs.arch.din277 import USES

VERSION = "0.1.0"
NORM = "HOAI 2021"
ZONES = ("I", "II", "III", "IV", "V")

SERVICES: dict[str, tuple[str, tuple[int, ...], str]] = {
    "building": ("Gebäude", (2, 7, 15, 3, 25, 10, 4, 32, 2), "§ 34 Abs. 3"),
    "services": ("Technische Ausrüstung", (2, 9, 17, 2, 22, 7, 5, 35, 1), "§ 55 Abs. 1"),
    "structure": ("Tragwerksplanung", (3, 10, 15, 30, 40, 2), "§ 51 Abs. 1"),
}
"""Per service: its German name, the percent of the fee for each service phase, and the clause."""
TABLE_CLAUSE = {"building": "§ 35 Abs. 1", "services": "§ 56 Abs. 1", "structure": "§ 52 Abs. 1"}

FEES = Spec(
    "hoai-fees",
    "Fee tables (Honorartafeln) of the HOAI",
    "HOAI 2021, § 35, § 52, § 56",
    (
        Col(
            "service",
            "text",
            "building (§ 35), services (§ 56) or structure (§ 52)",
            tuple(SERVICES),
        ),
        Col("cost", "num", "chargeable costs of the table's row, €"),
        Col("zone", "text", "fee zone", ZONES),
        Col("base", "num", "fee at the base rate (Basishonorarsatz), €"),
        Col("top", "num", "fee at the upper rate (oberer Honorarsatz), €"),
    ),
    ("service", "cost", "zone"),
    "The HOAI is an ordinance and free to copy: one row per service, row of the table and zone,"
    " from the official text (gesetze-im-internet.de).",
)

PARAMS = (
    Param("service", str, "building", "what is planned", tuple(SERVICES)),
    Param("zone", str, None, "the fee zone (Honorarzone), I to V", ZONES),
    Param("rate", float, 0.0, "where between the base rate (0) and the upper rate (100), %"),
    Param(
        "lph", str, None, "the service phases, e.g. 1-4 or 1-3,5; all if left out", optional=True
    ),
    Param(
        "kosten", float, None, "chargeable costs in €, net; else from the estimate", optional=True
    ),
    Param("umbau", float, 0.0, "surcharge for a conversion (Umbauzuschlag), %"),
    Param("nk", float, 0.0, "incidental costs (Nebenkosten), % of the fee"),
    Param("ust", float, 19.0, "VAT, %"),
)


def phases(text: str | None, n: int) -> list[int]:
    """The phases a text names: 1-4, 1-3,5. All n if None."""
    if text is None:
        return list(range(1, n + 1))
    out: set[int] = set()
    for part in text.split(","):
        a, _, b = part.strip().partition("-")
        try:
            lo, hi = int(a), int(b or a)
        except ValueError:
            raise ValueError(f"lph={text}: give phases like 1-4 or 1-3,5") from None
        if not 1 <= lo <= hi <= n:
            raise ValueError(f"lph={text}: this service has the phases 1 to {n}")
        out.update(range(lo, hi + 1))
    return sorted(out)


def chargeable_building(kg300: float, kg400: float) -> tuple[float, float, float]:
    """§ 33 Abs. 2: KG 400 counts fully up to 25 % of KG 300, the part above by half.
    Returns the chargeable costs, the full part of KG 400 and the halved part."""
    full = min(kg400, 0.25 * kg300)
    half = max(0.0, kg400 - 0.25 * kg300) / 2
    return kg300 + full + half, full, half


@dataclass
class Interp:
    base: float
    top: float
    lo: float
    hi: float
    """The table's rows it lies between (equal if it is on a row)."""


def interpolate(rows: list[tuple[float, float, float]], cost: float, service: str) -> Interp:
    """§ 13: base and upper fee between the rows (cost, base, top) around cost."""
    rows = sorted(rows)
    if not rows:
        raise ValueError(f"hoai-fees has no rows for {service} in this zone")
    if not rows[0][0] <= cost <= rows[-1][0]:
        raise ValueError(
            f"chargeable costs {ar(cost)} € lie outside the table ({ar(rows[0][0])} to"
            f" {ar(rows[-1][0])} €): the fee is free to agree (§ 7 Abs. 2 HOAI)"
        )
    for (c0, b0, t0), (c1, b1, t1) in pairwise(rows):
        if c0 <= cost <= c1:
            k = 0.0 if c1 == c0 else (cost - c0) / (c1 - c0)
            return Interp(b0 + k * (b1 - b0), t0 + k * (t1 - t0), c0, c1)
    c, b, t = rows[0]
    return Interp(b, t, c, c)


def hoai(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("the fee is for the whole project; give no scope")
    service = str(env.param("service"))
    name, shares, phase_clause = SERVICES[service]
    zone = str(env.param("zone"))
    rate = float(env.param("rate"))
    if not 0 <= rate <= 100:
        raise ValueError(f"rate={rate:g}: give 0 (base rate) to 100 (upper rate)")
    lph = phases(env.param("lph"), len(shares))
    given = env.param("kosten")
    basis: list[str] = []
    if given is not None:
        cost = float(given)
        basis.append(f"given: {ar(cost)} €")
    elif service == "structure":
        raise ValueError("the structure's chargeable costs (§ 50) need kosten=<€>")
    else:
        rows = estimate(d, env)
        kg300 = sum(r.cost for r in rows if 300 <= r.kg <= 399)
        kg400 = sum(r.cost for r in rows if 400 <= r.kg <= 499)
        if service == "building":
            cost, full, half = chargeable_building(kg300, kg400)
            basis.append(
                f"KG 300 {ar(kg300)} + KG 400 {ar(kg400)}: {ar(full)} in full, {ar(half)} by"
                " half (§ 33 Abs. 2)"
            )
        else:
            cost = kg400
            basis.append(f"KG 400 {ar(kg400)} (§ 54)")
    if cost <= 0:
        raise ValueError("the chargeable costs are 0; check the estimate or give kosten=")
    table = env.table(FEES)
    trows: list[tuple[float, float, float]] = []
    for r in table.rows:
        if str(r["service"]) == service and str(r["zone"]) == zone:
            c, b, t = r["cost"], r["base"], r["top"]
            assert isinstance(c, float) and isinstance(b, float) and isinstance(t, float)
            trows.append((c, b, t))
    it = interpolate(trows, cost, service)
    full_fee = it.base + (it.top - it.base) * rate / 100
    share = sum(shares[p - 1] for p in lph)
    fee = full_fee * share / 100
    umbau = float(env.param("umbau"))
    surcharge = fee * umbau / 100
    nk = (fee + surcharge) * float(env.param("nk")) / 100
    net = fee + surcharge + nk
    ust = float(env.param("ust"))
    vat = net * ust / 100
    lines = [
        f"{service} ({name}), zone {zone}, rate {rate:g} %: chargeable costs {ar(cost)} €"
        f" ({'; '.join(basis)})",
        f"table {ar(it.base)} to {ar(it.top)} € (between {ar(it.lo)} and {ar(it.hi)} €, § 13)"
        f" → {ar(full_fee)} € for 100 %",
        f"phases {_ranges(lph)} = {share:g} % ({phase_clause}): {ar(fee)} €"
        + (f" · conversion +{umbau:g} % {ar(surcharge)} €" if surcharge else "")
        + (f" · incidental {ar(nk)} €" if nk else ""),
        f"net {ar(net)} € · VAT {ust:g} % {ar(vat)} € · gross {ar(net + vat)} €",
    ]
    return Output(
        lines=lines,
        report=_report(
            d,
            service,
            zone,
            rate,
            cost,
            basis,
            it,
            full_fee,
            lph,
            shares,
            fee,
            umbau,
            surcharge,
            nk,
            net,
            ust,
        ),
        data={
            "service": service,
            "zone": zone,
            "rate": rate,
            "chargeable": round(cost, 2),
            "table": {
                "base": round(it.base, 2),
                "top": round(it.top, 2),
                "between": [it.lo, it.hi],
            },
            "full": round(full_fee, 2),
            "phases": lph,
            "share": share,
            "fee": round(fee, 2),
            "conversion": round(surcharge, 2),
            "incidental": round(nk, 2),
            "net": round(net, 2),
            "vat": round(vat, 2),
            "gross": round(net + vat, 2),
        },
        inputs={"chargeable": basis},
    )


def _ranges(ps: list[int]) -> str:
    out: list[str] = []
    start = prev = ps[0]
    for p in [*ps[1:], 0]:
        if p != prev + 1:
            out.append(f"{start}-{prev}" if prev > start else str(start))
            start = p
        prev = p
    return ",".join(out)


def _report(
    d: Derived,
    service: str,
    zone: str,
    rate: float,
    cost: float,
    basis: list[str],
    it: Interp,
    full_fee: float,
    lph: list[int],
    shares: tuple[int, ...],
    fee: float,
    umbau: float,
    surcharge: float,
    nk: float,
    net: float,
    ust: float,
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    name, _, phase_clause = SERVICES[service]
    vat = net * ust / 100
    phase_rows = [
        [f"LPH {p}", f"{shares[p - 1]} %", de(full_fee * shares[p - 1] / 100)] for p in lph
    ]
    out = [
        f"# Honorarermittlung nach HOAI 2021: {title}",
        "",
        f"Leistungsbild: {name}. Honorarzone {zone}, Honorarsatz {de(rate, 0)} % zwischen"
        " Basishonorarsatz und oberem Honorarsatz.",
        "",
        f"- Anrechenbare Kosten: {de(cost)} € netto ({'; '.join(basis)})",
        f"- Honorartafel ({TABLE_CLAUSE[service]}), Zone {zone}: Basishonorarsatz {de(it.base)} €,"
        f" oberer Honorarsatz {de(it.top)} €, linear interpoliert zwischen {de(it.lo)} € und"
        f" {de(it.hi)} € (§ 13)",
        f"- Honorar für 100 %: {de(full_fee)} €",
        "",
        f"## Leistungsphasen ({phase_clause})",
        "",
        md_table(["Leistungsphase", "Anteil", "Honorar €"], phase_rows, (1, 2)),
        "",
        f"- Honorar der beauftragten Leistungsphasen: {de(fee)} €",
    ]
    if surcharge:
        out.append(f"- Umbauzuschlag {de(umbau, 0)} % (§ 36): {de(surcharge)} €")
    if nk:
        out.append(f"- Nebenkosten (§ 14): {de(nk)} €")
    out += [
        f"- Summe netto: {de(net)} €",
        f"- Umsatzsteuer {de(ust, 0)} % (§ 16): {de(vat)} €",
        f"- **Summe brutto: {de(net + vat)} €**",
        "",
        "Seit der HOAI 2021 sind die Tafelwerte Orientierungswerte; das Honorar wird vereinbart."
        " Berechnet aus dem Modell; Prüfung und Verantwortung liegen beim Büro.",
        "",
    ]
    return "\n".join(out)


HOAI = Calculator(
    name="hoai",
    title="Fee per HOAI 2021 (Honorar)",
    kind="norm",
    version=VERSION,
    fn=hoai,
    norm=NORM,
    params=PARAMS,
    tables=(FEES, REF, USES),
)

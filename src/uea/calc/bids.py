"""The comparison of the bids (Preisspiegel) after the arithmetic check of VOB/A § 16c Abs. 2.

A `norm` calculator for the arithmetic only: each bid's sum is its quantities times its unit
prices, position by position; where the bidder's total price of a position differs, the unit
price counts (§ 16c Abs. 2 Nr. 1), and the stated total does not count. The discount is taken
off the checked sum. Bids are ranked by that sum among the bids on the same titles; a bid that
leaves a position of its titles without a price is listed, not ranked. A unit price far from the
median of the bids is flagged for the planner to look at (dev=); that threshold is the office's
choice, not a rule of the VOB. Which bid wins is the client's decision (the Wertung covers more
than the price), so the calculator ranks and flags and never awards.
"""

from dataclasses import dataclass
from statistics import median

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.derive import Derived
from uea.fmt import ar
from uea.packs.bid.geometry import BidSum, gp
from uea.packs.bid.kinds import Bid
from uea.packs.lv.kinds import Pos, Title

VERSION = "0.1.0"
NORM = "VOB/A 2019 § 16c Abs. 2 (rechnerische Prüfung)"
SHOWN = 12
"""How many flagged unit prices the agent's lines list; the report has all."""

PARAMS = (
    Param(
        "dev",
        float,
        30.0,
        "flag a unit price this many % above or below the median of the bids on its position",
    ),
)


@dataclass
class Flag:
    pos: str
    bid: str
    ep: float
    median: float

    @property
    def dev(self) -> float:
        return (self.ep / self.median - 1) * 100

    def text(self) -> str:
        on = f"{self.dev:+.0f} % on the median {ar(self.median)}"
        return f"{self.pos}: {self.bid} {ar(self.ep)} is {on}"


def ranks(bids: dict[str, BidSum]) -> dict[str, tuple[int, int]]:
    """Each complete bid's rank and the number ranked with it, among the bids on its titles."""
    groups: dict[tuple[str, ...], list[str]] = {}
    for k, s in bids.items():
        if not s.unpriced and s.prices:
            groups.setdefault(tuple(s.titles), []).append(k)
    out: dict[str, tuple[int, int]] = {}
    for ks in groups.values():
        ks.sort(key=lambda k: (round(bids[k].net, 2), k))
        for i, k in enumerate(ks, 1):
            out[k] = (i, len(ks))
    return out


def flags(d: Derived, dev: float, titles: list[str]) -> list[Flag]:
    out: list[Flag] = []
    for t in titles:
        for pid in d.lv.positions.get(t, []):
            eps = {k: s.prices[pid].ep for k, s in d.bid.bids.items() if pid in s.prices}
            if len(eps) < 2:
                continue
            m = median(eps.values())
            if m <= 0:
                continue
            out += [Flag(pid, k, ep, m) for k, ep in eps.items() if abs(ep / m - 1) * 100 > dev]
    return out


def _lv_sum(d: Derived, title: str) -> float | None:
    """The office's own prices (ep=) on the title, for comparison."""
    vals: list[float] = []
    for pid in d.lv.positions.get(title, []):
        p = d.model[pid]
        assert isinstance(p, Pos)
        total = d.lv.total(p)
        if total is not None:
            vals.append(total)
    return sum(vals) if vals else None


def bids(d: Derived, scope: str | None, env: Env) -> Output:
    all_bids = d.bid.bids
    if not all_bids:
        raise ValueError("no bids yet: uea import gaeb <file.x84> --by <who>")
    if scope is not None and scope not in d.lv.positions:
        raise ValueError(f"unknown title {scope!r}. Titles: {' '.join(d.lv.positions)}")
    titles = (
        [scope]
        if scope
        else [t for t in d.lv.positions if any(t in s.titles for s in all_bids.values())]
    )
    dev = float(env.param("dev"))
    rk = ranks(all_bids)
    lines: list[str] = []
    for k, s in all_bids.items():
        b = d.model[k]
        assert isinstance(b, Bid)
        line = f"{k} {b.label}: {ar(s.checked)} €"
        if s.disc:
            line += f" · {s.disc:g} % off {ar(s.net)} €"
        if k in rk:
            n, of = rk[k]
            line += f" · rank {n} of {of}"
        elif s.unpriced:
            line += f" · incomplete, not ranked: no price for {' '.join(s.unpriced)}"
        if len({tuple(x.titles) for x in all_bids.values()}) > 1:
            line += f" · on {' '.join(s.titles)}"
        lines.append(line)
        corrected = [pr.pos.id for pr in s.prices.values() if pr.gp is not None]
        if corrected:
            lines.append(
                f"{k}: total price of {' '.join(corrected)} is not qty × ep; the ep counts"
            )
        if b.total is not None and abs(b.total - s.checked) > 0.005:
            lines.append(f"{k}: states {ar(b.total)} €, checked {ar(s.checked)} €")
    for t in titles:
        el = d.model[t]
        assert isinstance(el, Title)
        on = sorted((s.by_title[t], k) for k, s in all_bids.items() if t in s.by_title)
        parts = [f"{k} {ar(v)}" for v, k in on]
        own = _lv_sum(d, t)
        if own is not None:
            parts.append(f"LV {ar(own)}")
        lines.append(f"{t} {el.label}: {' · '.join(parts)}")
    fl = flags(d, dev, titles)
    lines += [f.text() for f in fl[:SHOWN]]
    if len(fl) > SHOWN:
        lines.append(f"... {len(fl) - SHOWN} more prices off the median: see the report")
    return Output(
        lines=lines,
        report=_report(d, titles, rk, fl, dev),
        data={
            "bids": [
                {
                    "id": k,
                    "bidder": d.model[k].label,
                    "titles": s.titles,
                    "checked": round(s.checked, 2),
                    "disc": s.disc,
                    "net": round(s.net, 2),
                    "rank": rk[k][0] if k in rk else None,
                    "unpriced": s.unpriced,
                    "by_title": {t: round(v, 2) for t, v in s.by_title.items()},
                }
                for k, s in all_bids.items()
            ],
            "flags": [
                {"pos": f.pos, "bid": f.bid, "ep": f.ep, "median": f.median, "dev": round(f.dev, 1)}
                for f in fl
            ],
        },
        inputs={"bids": list(all_bids), "titles": titles},
    )


def _report(
    d: Derived,
    titles: list[str],
    rk: dict[str, tuple[int, int]],
    fl: list[Flag],
    dev: float,
) -> str:
    proj = d.model.of_kind("project")
    name = proj[0].label or proj[0].id if proj else "Projekt"
    all_bids = d.bid.bids
    keys = [k for k, s in all_bids.items() if any(t in s.titles for t in titles)]
    flagged = {(f.pos, f.bid) for f in fl}
    out = [f"# Preisspiegel: {name}", ""]
    out += [
        md_table(
            [
                "Angebot",
                "Bieter",
                "Datum",
                "Summe geprüft €",
                "Nachlass",
                "Wertungssumme €",
                "Rang",
            ],
            [
                [
                    k,
                    str(d.model[k].label),
                    getattr(d.model[k], "date", None) or "",
                    de(all_bids[k].checked),
                    f"{de(all_bids[k].disc, 1)} %" if all_bids[k].disc else "",
                    de(all_bids[k].net),
                    f"{rk[k][0]} von {rk[k][1]}" if k in rk else "unvollständig",
                ]
                for k in keys
            ],
            (3, 5),
        ),
        "",
    ]
    for t in titles:
        el = d.model[t]
        out += [f"## {d.lv.oz[t]} {el.label}", ""]
        head = ["OZ", "Kurztext", "Menge", "Einheit"]
        for k in keys:
            head += [f"EP {k} €", f"GP {k} €"]
        rows: list[list[str]] = []
        for pid in d.lv.positions[t]:
            q = d.lv.qty.get(pid)
            if q is None:
                continue
            p = d.model[pid]
            row = [d.lv.oz[pid], str(p.label), _qty(q.value), q.unit]
            for k in keys:
                pr = all_bids[k].prices.get(pid)
                if pr is None:
                    row += ["–" if t in all_bids[k].titles else "", ""]
                else:
                    mark = " ⚑" if (pid, k) in flagged else ""
                    row += [de(pr.ep) + mark, de(gp(d, pr))]
            rows.append(row)
        sums = ["", "Summe Titel", "", ""]
        for k in keys:
            v = all_bids[k].by_title.get(t)
            sums += ["", de(v) if v is not None else ""]
        rows.append(sums)
        right = tuple(i for i in range(4, 4 + 2 * len(keys)))
        out += [md_table(head, rows, (2, *right)), ""]
    out += ["## Hinweise", ""]
    for k in keys:
        s = all_bids[k]
        b = d.model[k]
        assert isinstance(b, Bid)
        if s.unpriced:
            out.append(f"- {k}: ohne Preis für {', '.join(d.lv.oz[p] for p in s.unpriced)}")
        for pr in s.prices.values():
            if pr.gp is not None:
                oz = d.lv.oz.get(pr.pos.id, pr.pos.id)
                out.append(
                    f"- {k}, {oz}: Gesamtpreis des Bieters {de(pr.gp)} €,"
                    f" Menge × Einheitspreis {de(gp(d, pr))} €; der Einheitspreis ist maßgebend."
                )
        if b.total is not None and abs(b.total - s.checked) > 0.005:
            out.append(
                f"- {k}: angegebene Summe {de(b.total)} €, rechnerisch geprüft {de(s.checked)} €."
            )
    if fl:
        out.append(
            f"- ⚑ Einheitspreis weicht um mehr als {de(dev, 0)} % vom Median der Angebote ab:"
            " aufklären."
        )
    out += [
        "",
        "## Verfahren",
        "",
        "- Rechnerische Prüfung nach VOB/A § 16c Abs. 2: Gesamtpreis = Menge des Angebots ×"
        " Einheitspreis, auf Cent gerundet; weicht der Gesamtpreis des Bieters ab, ist der"
        " Einheitspreis maßgebend.",
        "- Wertungssumme: geprüfte Summe abzüglich des Nachlasses. Rang unter den vollständigen"
        " Angeboten auf dieselben Titel, nur nach dem Preis.",
        "- Die Markierung ⚑ ist ein Hinweis des Büros (Schwelle dev), keine Regel der VOB.",
        "",
        "Die Wertung umfasst mehr als den Preis; über den Zuschlag entscheidet der Auftraggeber."
        " Prüfung und Verantwortung liegen bei der unterzeichnenden fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


def _qty(v: float) -> str:
    return de(v, 0) if v == int(v) else de(v, 3)


BIDS = Calculator(
    name="bids",
    title="Comparison of the bids (Preisspiegel)",
    kind="norm",
    version=VERSION,
    fn=bids,
    norm=NORM,
    params=PARAMS,
)

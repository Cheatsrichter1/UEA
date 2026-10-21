"""The bids derived from the model: what each bid prices, what it leaves out, its checked sum
(decision 0051).

A bid covers the titles of the positions it prices; a position of those titles it gives no
price for makes it incomplete. Its checked sum is the bidder's quantity times the unit price,
position by position, rounded to cents: where the bidder's own total price differs, the unit
price counts (VOB/A § 16c Abs. 2 Nr. 1).
"""

from dataclasses import dataclass, field

from uea.core.issues import Issue
from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ar, ids
from uea.packs.bid.kinds import Bid, Price
from uea.packs.lv.kinds import Pos

RULE = "VOB/A § 16c Abs. 2 Nr. 1"
QTY_TOL = 0.0005
"""Quantities go to bidders with three decimals."""


@dataclass
class BidSum:
    prices: dict[str, Price] = field(default_factory=dict[str, Price])
    """Its price of each position it prices."""
    titles: list[str] = field(default_factory=list[str])
    """The titles it covers, in LV order."""
    unpriced: list[str] = field(default_factory=list[str])
    """Positions of those titles it gives no price for."""
    by_title: dict[str, float] = field(default_factory=dict[str, float])
    """Its checked sum per title."""
    checked: float = 0.0
    """Its checked net sum, before the discount."""
    disc: float = 0.0
    """Its discount, %."""

    @property
    def net(self) -> float:
        """The checked sum after the discount."""
        return self.checked * (1 - self.disc / 100)


@dataclass
class BidGeo:
    bids: dict[str, BidSum] = field(default_factory=dict[str, BidSum])
    issues: list[Issue] = field(default_factory=list[Issue])


def gp(d: Derived, pr: Price) -> float:
    """The checked total price of a position: the bidder's quantity times the unit price."""
    qty = pr.qty
    if qty is None:
        q = d.lv.qty.get(pr.pos.id)
        qty = q.value if q is not None else 0.0
    return round(qty * pr.ep, 2)


def _title_of(d: Derived, pos: str) -> str | None:
    p = d.model.get(pos)
    return p.title.id if isinstance(p, Pos) else None


def derive_bids(d: Derived) -> None:
    g = BidGeo()
    d.bid = g
    for b in d.model.of_kind("bid"):
        assert isinstance(b, Bid)
        g.bids[b.id] = BidSum(disc=b.disc or 0.0)
    for pr in d.model.of_kind("price"):
        assert isinstance(pr, Price)
        s = g.bids.get(pr.bid.id)
        if s is None:
            continue
        if pr.pos.id in s.prices:
            g.issues.append(
                Issue(
                    "E-BID-001",
                    pr.id,
                    f"prices {pr.pos.id} for {pr.bid.id} again, as {s.prices[pr.pos.id].id} does",
                    f"remove one: - {pr.id}",
                    (s.prices[pr.pos.id].id,),
                )
            )
            continue
        s.prices[pr.pos.id] = pr
    order = list(d.lv.positions)
    for bid_id, s in g.bids.items():
        covered = {t for p in s.prices if (t := _title_of(d, p)) is not None}
        s.titles = [t for t in order if t in covered]
        for t in s.titles:
            for pid in d.lv.positions[t]:
                if pid not in s.prices and pid in d.lv.qty:
                    s.unpriced.append(pid)
        for pid, pr in s.prices.items():
            v = gp(d, pr)
            s.checked += v
            t = _title_of(d, pid)
            if t is not None:
                s.by_title[t] = s.by_title.get(t, 0.0) + v
        _check(d, g, d.model[bid_id], s)


def _check(d: Derived, g: BidGeo, b: Element, s: BidSum) -> None:
    assert isinstance(b, Bid)
    if s.unpriced:
        g.issues.append(
            Issue(
                "W-BID-002",
                b.id,
                f"gives no price for {ids(s.unpriced)} of the titles it bids on",
                "ask the bidder; uea calc bids leaves an incomplete bid out of the ranking",
                tuple(s.unpriced),
            )
        )
    changed: list[str] = []
    for pid, pr in s.prices.items():
        q = d.lv.qty.get(pid)
        if pr.qty is not None and q is not None and abs(q.value - pr.qty) > QTY_TOL:
            changed.append(pid)
        if pr.gp is not None:
            g.issues.append(
                Issue(
                    "W-BID-004",
                    pr.id,
                    f"{b.id} states {ar(pr.gp)} € for {pid}, but {_num(pr.qty)} × {ar(pr.ep)}"
                    f" = {ar(gp(d, pr))} €; the unit price counts",
                    "uea calc bids uses the unit price; tell the bidder",
                    rule=RULE,
                )
            )
    if changed:
        g.issues.append(
            Issue(
                "W-BID-003",
                b.id,
                f"priced other quantities than the LV has now for {ids(changed)}",
                "the LV changed since the bid: the comparison uses the bid's quantities, the"
                " Kostenanschlag the model's",
                tuple(changed),
            )
        )
    if b.total is not None and abs(b.total - s.checked) > 0.005:
        g.issues.append(
            Issue(
                "W-BID-005",
                b.id,
                f"states a total of {ar(b.total)} €, its prices give {ar(s.checked)} €",
                "uea calc bids uses the checked sum; tell the bidder",
                rule=RULE,
            )
        )


def bid_checks(d: Derived) -> list[Issue]:
    return list(d.bid.issues)


def describe(d: Derived, el: Element) -> list[str]:
    g = d.bid
    if isinstance(el, Bid):
        s = g.bids[el.id]
        out = f"{len(s.prices)} prices · {ar(s.checked)} €"
        if s.disc:
            out += f" · {s.disc:g} % off {ar(s.net)} €"
        lines = [out]
        if s.titles:
            lines.append(f"titles: {' '.join(s.titles)}")
        if s.unpriced:
            lines.append(f"no price: {ids(s.unpriced)}")
        return lines
    if isinstance(el, Price):
        oz = d.lv.oz.get(el.pos.id, "?")
        return [f"{oz} · {_num(el.qty)} × {ar(el.ep)} = {ar(gp(d, el))} €"]
    if isinstance(el, Pos):
        got = [f"{b} {ar(s.prices[el.id].ep)}" for b, s in g.bids.items() if el.id in s.prices]
        return [f"bids: {' · '.join(got)}"] if got else []
    return []


def _num(v: float | None) -> str:
    if v is None:
        return "?"
    return f"{v:g}" if v == int(v) else f"{v:.3f}"

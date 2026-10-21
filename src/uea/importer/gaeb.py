"""A bid as GAEB DA XML, phase 84 (Angebotsabgabe), into the bid pack (decision 0051).

The bidder returns the LV of `uea export gaeb` (phase 83) with unit prices. Each item is matched
to its position by the item ID UEA wrote (`UEA_p3`), else by its number (OZ); the bid becomes a
`bid` line and one `price` line per priced position, with the quantity the bidder priced. The
reader takes the GAEB elements it needs by their local names and ignores the rest; it has not
been validated against the official schema in this repository.
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from uea.core.syntax import fmt_num, quote
from uea.derive import Derived
from uea.packs.bid.kinds import DATE_RE, Bid
from uea.packs.lv.kinds import Pos

PHASE = "84"


class NotImportable(Exception):
    """The file cannot be imported at all."""


@dataclass
class Item:
    oz: str
    """Its number as the file has it: 01.0010."""
    id: str | None
    qty: float | None
    up: float | None
    it: float | None
    short: str


@dataclass
class Offer:
    file: str
    phase: str
    bidder: str | None
    date: str | None
    total: float | None
    disc: float | None
    items: list[Item] = field(default_factory=list[Item])


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, *path: str) -> ET.Element | None:
    """The first descendant along the local names of path."""
    cur: ET.Element | None = el
    for name in path:
        if cur is None:
            return None
        cur = next((c for c in cur if _local(c.tag) == name), None)
    return cur


def _text(el: ET.Element, *path: str) -> str | None:
    got = _child(el, *path)
    if got is None or got.text is None or not got.text.strip():
        return None
    return got.text.strip()


def _num(el: ET.Element, *path: str) -> float | None:
    t = _text(el, *path)
    if t is None:
        return None
    try:
        return float(t)
    except ValueError:
        raise NotImportable(f"{'/'.join(path)}={t!r} is not a number") from None


def _short(item: ET.Element) -> str:
    box = _child(item, "Description", "CompleteText", "OutlineText")
    if box is None:
        return ""
    return " ".join(t.strip() for t in box.itertext() if t.strip())


def _items(body: ET.Element, prefix: tuple[str, ...], out: list[Item]) -> None:
    for c in body:
        name = _local(c.tag)
        if name == "BoQCtgy":
            sub = _child(c, "BoQBody")
            if sub is not None:
                _items(sub, (*prefix, c.get("RNoPart", "")), out)
        elif name == "Itemlist":
            for item in c:
                if _local(item.tag) != "Item":
                    continue
                oz = ".".join((*prefix, item.get("RNoPart", "")))
                out.append(
                    Item(
                        oz,
                        item.get("ID"),
                        _num(item, "Qty"),
                        _num(item, "UP"),
                        _num(item, "IT"),
                        _short(item),
                    )
                )


def read(path: Path) -> Offer:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise NotImportable(f"{path.name} is not XML: {e}") from None
    if _local(root.tag) != "GAEB":
        raise NotImportable(f"{path.name} is not a GAEB DA XML file")
    award = _child(root, "Award")
    if award is None:
        raise NotImportable(f"{path.name} has no Award")
    phase = _text(award, "DP") or "?"
    if phase != PHASE:
        why = (
            "the request for bids, without prices (uea export gaeb)"
            if phase == "83"
            else "not a bid"
        )
        raise NotImportable(f"{path.name} is phase {phase}, {why}; import the bidder's phase 84")
    boq = _child(award, "BoQ")
    if boq is None:
        raise NotImportable(f"{path.name} has no BoQ")
    bidder = _text(award, "CTR", "Address", "Name1")
    date = _text(root, "GAEBInfo", "Date")
    offer = Offer(
        path.name,
        phase,
        bidder,
        date if date is not None and DATE_RE.match(date) else None,
        _num(boq, "BoQInfo", "Totals", "Total"),
        _num(boq, "BoQInfo", "Totals", "DiscountPcnt"),
    )
    body = _child(boq, "BoQBody")
    if body is not None:
        _items(body, (), offer.items)
    if not offer.items:
        raise NotImportable(f"{path.name} has no items")
    return offer


def _oz_key(oz: str) -> tuple[int | str, ...]:
    """01.0010 and 1.10 are the same number."""
    return tuple(int(p) if p.isdigit() else p for p in oz.split("."))


@dataclass
class Plan:
    text: str = ""
    prices: int = 0
    notes: list[str] = field(default_factory=list[str])
    skipped: list[str] = field(default_factory=list[str])
    """Items that match no position, with their number and short text."""


def plan(offer: Offer, d: Derived, bidder: str | None) -> Plan:
    """The ops that add the bid and its prices. NotImportable if it cannot be added."""
    name = bidder or offer.bidder
    if not name:
        raise NotImportable(f"{offer.file} names no bidder (Award/CTR); give it: --bidder <name>")
    name = name.replace('"', "'")
    for b in d.model.of_kind("bid"):
        assert isinstance(b, Bid)
        if b.label == name and b.file == offer.file:
            raise NotImportable(
                f"{offer.file} of {name} is in the model as {b.id}; to read it again, revert"
                " the batch that imported it (uea log)"
            )
    by_oz = {_oz_key(oz): k for k, oz in d.lv.oz.items() if isinstance(d.model.get(k), Pos)}
    pl = Plan()
    head = ["+ bid @b", quote(name)]
    if offer.date:
        head.append(f"date={offer.date}")
    if offer.total is not None:
        head.append(f"total={fmt_num(offer.total)}")
    if offer.disc:
        head.append(f"disc={fmt_num(offer.disc)}")
    head.append(f"file={quote(offer.file) if ' ' in offer.file else offer.file}")
    lines = [" ".join(head)]
    seen: dict[str, str] = {}
    unpriced: list[str] = []
    for it in offer.items:
        pid: str | None = None
        if it.id and it.id.startswith("UEA_") and isinstance(d.model.get(it.id[4:]), Pos):
            pid = it.id[4:]
        else:
            pid = by_oz.get(_oz_key(it.oz))
        if pid is None:
            pl.skipped.append(f"{it.oz} {quote(it.short)}" if it.short else it.oz)
            continue
        if pid in seen:
            pl.notes.append(f"{it.oz}: {pid} is priced by {seen[pid]} already; not read")
            continue
        seen[pid] = it.oz
        if it.up is None:
            unpriced.append(pid)
            continue
        line = f"+ price _ @b {pid} ep={fmt_num(it.up)}"
        if it.qty is not None:
            line += f" qty={fmt_num(it.qty)}"
            if it.it is not None and abs(it.it - round(it.qty * it.up, 2)) > 0.005:
                line += f" gp={fmt_num(it.it)}"
        lines.append(line)
        pl.prices += 1
    if unpriced:
        pl.notes.append(f"no unit price in the file: {' '.join(unpriced)}")
    if not pl.prices:
        raise NotImportable(f"{offer.file} prices no position of the LV")
    pl.text = "\n".join(lines) + "\n"
    return pl

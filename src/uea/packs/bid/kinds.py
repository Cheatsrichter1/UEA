"""Kinds of the bid pack: the bids on the LV and their unit prices (decision 0051)."""

import re
from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Ref

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Bid(Element):
    kind: ClassVar[str] = "bid"
    pack: ClassVar[str] = "bid"
    prefix: ClassVar[str | None] = "bd"
    doc: ClassVar[str] = (
        'A bid on the LV (Angebot), as uea import gaeb reads it: bid bd1 "Muster Bau GmbH"'
        " date=2026-11-02 total=48231.5 disc=3. The label is the bidder. Its unit prices are"
        " price lines; uea calc bids compares the bids."
    )
    date: Annotated[str | None, F("date of the bid: 2026-11-02")] = None
    total: Annotated[
        float | None, F("the net total the bidder states, before the discount", unit="€")
    ] = None
    disc: Annotated[float | None, F("discount on the whole bid (Nachlass)", unit="%")] = None
    file: Annotated[str | None, F("the file it was read from")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.label:
            raise ValueError('a bid needs its bidder as a quoted label: "Muster Bau GmbH"')
        if self.date is not None and not DATE_RE.match(self.date):
            raise ValueError(f"date={self.date} must be YYYY-MM-DD")
        if self.disc is not None and not 0 <= self.disc < 100:
            raise ValueError("disc is a percentage from 0 to below 100")
        return self


class Price(Element):
    kind: ClassVar[str] = "price"
    pack: ClassVar[str] = "bid"
    prefix: ClassVar[str | None] = "pr"
    positional: ClassVar[tuple[str, ...]] = ("bid", "pos")
    doc: ClassVar[str] = (
        "A bid's unit price for a position: price _ bd1 p3 ep=52.1 qty=124.5. qty= is the"
        " quantity the bidder priced; gp= only where the bidder's total price differs from"
        " qty × ep."
    )
    bid: Annotated[Ref, F("the bid", targets=("bid",))]
    pos: Annotated[Ref, F("the LV position it prices", targets=("pos",))]
    ep: Annotated[float, F("unit price (Einheitspreis)", unit="€")]
    qty: Annotated[float | None, F("the quantity the bidder priced")] = None
    gp: Annotated[
        float | None, F("the bidder's total price, where it differs from qty × ep", unit="€")
    ] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.ep < 0:
            raise ValueError("ep must be 0 or more")
        if self.qty is not None and self.qty < 0:
            raise ValueError("qty must be 0 or more")
        return self


KINDS: tuple[type[Element], ...] = (Bid, Price)

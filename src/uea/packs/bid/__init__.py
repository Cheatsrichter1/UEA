"""The bid pack: the bids on the LV and their unit prices, read from GAEB 84 (decision 0051)."""

from uea.core.registry import Pack
from uea.packs.bid.geometry import bid_checks, derive_bids, describe
from uea.packs.bid.kinds import KINDS

CODES: dict[str, str] = {
    "E-BID-001": "a bid prices a position twice",
    "W-BID-002": "bid without prices for some positions of the titles it bids on",
    "W-BID-003": "bid priced other quantities than the LV has now",
    "W-BID-004": "bidder's total price of a position is not quantity times unit price",
    "W-BID-005": "bidder's stated total is not the sum of its prices",
}

PACK = Pack(
    name="bid",
    title="Bids on the LV and their unit prices",
    kinds=KINDS,
    derive=derive_bids,
    checks=(bid_checks,),
    codes=CODES,
    describe=describe,
    also=("pos",),
)

# Validation report: `bids` (comparison of the bids)

| | |
|---|---|
| Calculator | `bids` 0.1.0, kind `norm` |
| Standard | VOB/A 2019, § 16c Abs. 2 (rechnerische Prüfung der Angebote) |
| Code | `src/uea/calc/bids.py`; the checked sums in `src/uea/packs/bid/geometry.py`; reading GAEB 84 in `src/uea/importer/gaeb.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_bids.py` at commit `517c07e` |
| Review | **Not yet reviewed** by a licensed person. |

`norm` covers the arithmetic check only. The rank by price, the median and the threshold `dev` are tools for the planner, not rules of the VOB, and the report says so. The Wertung beyond the price and the award are not computed (`docs/decisions/tender.md#0051-bids`).

## What it computes

- Per price: the checked total price, the bid's quantity times its unit price, rounded to cents. Where the bidder's total price differs (`gp=`), the unit price counts (§ 16c Abs. 2 Nr. 1).
- Per bid: the checked sum per title and in total; less its discount (`disc=`), the sum it is ranked by.
- The rank among the complete bids on the same titles. A bid without a price for a position of its titles is listed as incomplete and not ranked.
- Per position priced by two bids or more: the median of their unit prices, and each unit price more than `dev` % above or below it.
- Beside each title: the office's own prices of the LV (`ep=` times the model's quantity).

## Assumptions to check when signing

- The quantities are the bid's, as the bidder priced them. Where the LV has changed since, W-BID-003 names the positions.
- The discount applies to the whole bid. Discounts on titles or conditional discounts (Skonto) are not read.
- A unit price of 0 is a price; a missing unit price is none.

## Test cases (passed at commit `517c07e`)

| Test | Case | Expected |
|---|---|---|
| `test_checked_sums_and_checks` | two bids on the box's LV (the table in the test's docstring); bd2 states 9100.00 for 90.51 × 100.00 and a total of 23233.35 | bd1 23820.96 €, 2 % off 23344.54 €; bd2 23184.35 €; W-BID-004 on bd2's price of p1, W-BID-005 on bd2 |
| `test_incomplete_and_changed_quantities` | a third bid on title T02 that prices p3 only; a second window | bd3 incomplete for p4; W-BID-003 on all three bids for p3 |
| `test_comparison` | the two bids, dev 30 | bd2 rank 1, bd1 rank 2; T01 19653.84 and 20602.00 beside the LV's 11051.00; p3 450 and 900 flagged at ∓33 % around the median 675; nothing flagged at dev 40 |
| `test_an_incomplete_bid_is_not_ranked` | the third bid on T02 | listed, not ranked; the scope T02 shows that title only |
| `test_kostenanschlag` | `costs stage=offer bid=bd2`, then `bid=bd1` | 331 16653.84, 334 900.00, 352 69.2244 × 38 = 2630.53, 391 3000.00; bd1's 331 is 18102.00 less 2 % |
| `test_kostenanschlag_from_part_of_the_lv` | `bid=bd3`, which prices p3 only | 334 480.00 from bd3, 331 and 391 from the LV's own prices, p2 and p4 listed as left out |
| `test_read_and_plan`, `test_by_number_and_what_is_left_out`, `test_files_that_cannot_be_read` | phase 84 files made from the box's phase 83 export | the lines imported; matching by number without UEA's ids; refusals of phase 83, no bidder, no prices, no XML |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

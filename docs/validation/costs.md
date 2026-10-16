# Validation report: `costs` (cost estimate per DIN 276)

| | |
|---|---|
| Calculator | `costs` 0.1.0, kind `norm` |
| Standard | DIN 276:2018-12, Kosten im Bauwesen (Kostenschätzung) |
| Code | `src/uea/calc/din276.py`; reference quantities from `src/uea/packs/arch/din277.py` |
| Tests | `tests/test_costs_hoai.py` |
| Review | **Not yet reviewed** by a licensed person. The clause numbers of DIN 276 are not given here: the reviewer adds them with the text at hand, which is not in this repository. |

DIN 276 is licensed; the titles of its cost groups are not in the repository. The office supplies its reference prices per cost group, with its own names for the groups, in the table `cost-ref` (`docs/decisions/0008-office-supplied-norm-data.md`, `0049-cost-estimate-and-hoai-fee.md`).

## What it computes

- For each row of `cost-ref`: the reference quantity per DIN 277 of the whole project (BGF, NRF, NUF, KGF or BRI, from `uea calc din277`) times the office's net price per unit.
- The sums per first level of the cost groups (100 to 800), the net total, VAT (`ust=`, default 19 %) and the gross total.
- Beside each row, for comparison only, the sum of the LV's priced positions whose cost group lies in the row's group.

## Assumptions to check when signing

- The prices are net; VAT is added on the total.
- A row priced on NUF needs the use table of DIN 277; a row priced on BRI needs a roof over the top storey.
- A cost group and one of its subgroups may not both have a row: 300 covers 300 to 399, 330 covers 330 to 339.

## Test cases

| Test | Case | Expected |
|---|---|---|
| `test_estimate` | box with BGF 161.4432 m², BRI 481.907952 m³; KG 300 at 1000 €/m² BGF, KG 400 at 100 €/m³ BRI | 161443.20 € and 48190.80 €, net 209634.00 €, VAT 39830.46 €, gross 249464.45 € |
| `test_the_priced_lv_beside_the_estimate` | LV: exterior walls 34.8 × (2.7 + 2.6) m² at 100 € in KG 331, a lump sum of 5000 € in KG 420 | beside KG 300 18444.00 €, beside KG 400 5000.00 €; the estimate unchanged |
| `test_bad_prices` | 300 and 330; 1000; NUF without the use table | errors |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

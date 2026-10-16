# 0049: The cost estimate per DIN 276 and the fee per HOAI

Status: Accepted (built)
Date: 2026-10-16

## Context

Version 2 goes from the model to the tender and the offer (`FUTURE.md`). An office needs the cost estimate (Kostenschätzung) per DIN 276 long before there is an LV, and its own fee per HOAI for the offer. The model already gives the reference quantities per DIN 277 (`0047-din277-areas.md`), and the LV can carry cost groups and prices (`0048-leistungsverzeichnis.md`). Reading bids (GAEB 84) is deferred.

DIN 276 is licensed. The HOAI is a federal ordinance and so an amtliches Werk: its rules and its fee tables may be implemented and cited freely.

## Decision

- **`uea calc costs`** (`norm`, DIN 276:2018-12): the office's reference prices per cost group in the table `cost-ref` (cost group, its name, the DIN 277 quantity it is priced on, the net price). Each row's cost is the reference quantity times the price; the rows sum up to the first level of the cost groups and to the total, net and with VAT (`ust=`, default 19 %). A group and one of its own subgroups may not both have a row. Where the LV has priced positions of a row's group, their sum is shown beside it and not added. `stand=` records the price level.
- **`uea calc hoai`** (`norm`, HOAI 2021): `service=building|services|structure`, `zone=I..V`, `rate=` between the base and the upper rate (0 to 100), `lph=` the service phases, `kosten=` the chargeable costs if they are not taken from the estimate, `umbau=`, `nk=`, `ust=`.
  - The chargeable costs of a building follow § 33 Abs. 2 from the estimate's KG 300 and KG 400; of the technical equipment, KG 400 (§ 54), for all of it together; of the structure, `kosten=` (§ 50).
  - The fee table is interpolated linearly (§ 13); outside the table the fee is free to agree (§ 7 Abs. 2) and the calculator stops.
  - The shares of the service phases are in code with their clauses (§ 34 Abs. 3, § 55 Abs. 1, § 51 Abs. 1).
- **The cost calculation** (Kostenberechnung, `stage=calculation`) takes the priced LV per cost group (its positions' quantities from the model times their `ep=`). A row of `cost-ref` stays where no priced position falls in its group, marked as such, so a half-priced LV still gives a whole total; what is left out (positions without a price or without a cost group) is listed.
- **The fee follows § 6 Abs. 1:** its chargeable costs come from the cost calculation where the LV is priced, else from the estimate (`costs=auto`); `costs=estimate` or `calculation` chooses. The technical equipment's fee can be computed per group of systems (`groups=410,420`, § 54 Abs. 1).
- **The HOAI's fee tables come from the office** (`hoai-fees`: service, chargeable costs, zone, base and upper fee), copied once from the official text. They could be shipped, since the ordinance is free; they are not typed into the repository from memory, because a single wrong value would be worse than none. Shipping a checked copy is open.

## Alternatives

- **Ship the HOAI tables now.** Free to copy, but no checked source is at hand in this repository's tooling; a transcription error in a fee table would go unnoticed until someone signs an offer with it.
- **Costs from the LV only** (Kostenberechnung): needs a full, priced LV, which comes late; the estimate by reference quantities is what an office needs first. The LV's sums stand beside it for comparison.
- **The chargeable costs given by hand only.** Simple, but the model already knows them; `kosten=` stays for the cases the rule does not cover.

## Consequences

- Two calculators, two office tables, validation reports `docs/validation/costs.md` and `hoai.md`.
- The technical equipment's fee per group of systems (Anlagengruppe, § 54 Abs. 1) takes the groups' rows of the calculation; with the estimate it needs reference prices per group (410, 420, ... in `cost-ref`).
- The structure's chargeable costs per § 50 Abs. 2 (shares of KG 300 and KG 400) could follow from the estimate; open.

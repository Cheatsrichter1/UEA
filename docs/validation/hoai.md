# Validation report: `hoai` (fee per HOAI 2021)

| | |
|---|---|
| Calculator | `hoai` 0.2.0, kind `norm` |
| Standard | Honorarordnung für Architekten und Ingenieure (HOAI) in the version of 2021 |
| Code | `src/uea/calc/hoai.py`; chargeable costs from `src/uea/calc/din276.py` |
| Tests | Removed (`docs/decisions/0052-no-tests-in-the-repo.md`); the cases below passed in `tests/test_costs_hoai.py` at commit `517c07e` |
| Review | **Not yet reviewed** by a licensed person. |

The HOAI is a federal ordinance and so an amtliches Werk: its rules may be implemented and cited freely. Its fee tables are supplied by the office in the table `hoai-fees`, copied from the official text (`docs/decisions/0049-cost-estimate-and-hoai-fee.md`). Since 2021 the table values are guidance (Orientierungswerte) and the fee is agreed; the calculator computes the fee for the agreed zone, rate and phases.

## Clauses and how they are implemented

| Clause | Rule | Implementation |
|---|---|---|
| § 6 Abs. 1 | The chargeable costs on the cost calculation, or the estimate where there is none | `costs=auto`: the calculation when the LV has priced positions with a cost group, else the estimate; `costs=` chooses |
| § 4 Abs. 1, § 16 | Chargeable costs are net; VAT on top | The estimate's net costs; VAT `ust=` on the net fee |
| § 33 Abs. 2 | Building: KG 400 counts in full up to 25 % of the other chargeable costs, above that by half | Other chargeable costs = KG 300 of the estimate |
| § 54 | Technical equipment: its costs, per group of systems (Abs. 1) | KG 400, or the groups named with `groups=410,420`, or `kosten=` |
| § 50 | Structure | `kosten=` only |
| § 13 | Linear interpolation between the table's steps | Base and upper fee each interpolated between the rows around the chargeable costs |
| § 5, § 35, § 52, § 56 | Fee zone; fee between base and upper rate | `zone=`, `rate=` 0 to 100 % |
| § 34 Abs. 3 | Building, phases 1 to 9: 2, 7, 15, 3, 25, 10, 4, 32, 2 % | `lph=` |
| § 55 Abs. 1 | Technical equipment, phases 1 to 9: 2, 9, 17, 2, 22, 7, 5, 35, 1 % | `lph=` |
| § 51 Abs. 1 | Structure, phases 1 to 6: 3, 10, 15, 30, 40, 2 % | `lph=` |
| § 7 Abs. 2 | Outside the table the fee is free to agree | Stops with that message |
| § 6 Abs. 2, § 36 | Surcharge for conversions as agreed | `umbau=` % of the phases' fee |
| § 14 | Incidental costs as agreed | `nk=` % of fee and surcharge |

## Not implemented

- The structure's chargeable costs from the costs (§ 50 Abs. 2).
- Special services (besondere Leistungen), repeated services, the reduction of single phases, interior design and open spaces.

## Assumptions to check when signing

- The phase shares above are typed from the ordinance; they are checked by the tests to sum to 100 %.
- The cost estimate gives the chargeable costs; costs that § 33 Abs. 3 adds or removes are not in it.

## Test cases (passed at commit `517c07e`)

All tables are synthetic test data, not the HOAI's values.

| Test | Case | Expected |
|---|---|---|
| `test_chargeable_costs_of_a_building` | KG 300 400 000, KG 400 80 000; and 140 000 | 480 000; 520 000 (100 000 full, 20 000 by half) |
| `test_fee_of_the_building_from_the_estimate` | KG 300 161 443.20, KG 400 48 190.80; zone III rows 200 000 → 35 000 / 43 000 and 300 000 → 50 000 / 62 000 | chargeable 205 719.00; base 35 857.85; phases 1 to 9 = 100 % |
| `test_phases_rate_conversion_and_incidental_costs` | 250 000, rate 50, phases 1 to 4, +20 %, NK 5 % | full 47 500; fee × 27 %; surcharge, NK and net as computed |
| `test_technical_equipment_takes_kg_400` | KG 400 48 190.80, zone II, phases 1 to 3 and 5 | interpolated between 40 000 and 60 000; 50 % |
| `test_fee_on_the_calculation` | priced LV: KG 300 18444, KG 400 8000 | the calculation is used; 18444 + 4611 + 3389 / 2 = 24749.50; base 5000 + 0.47495 × 2000 = 5949.90 |
| `test_fee_per_group_of_technical_systems` | groups=420: 5000; 420,430: 8000; 410: 0; on a building; 510 | 1200 halfway in the table; outside the table; 0; errors |
| `test_fee_stops_outside_the_table_and_without_what_it_needs` | 50 000 below the table; no zone; structure without kosten; no rows for the zone | errors |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.2.0 | The cost calculation where there is one (§ 6 Abs. 1); per group of technical systems |

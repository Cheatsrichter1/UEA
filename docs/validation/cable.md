# Validation report: `cable` (cable against its breaker)

| | |
|---|---|
| Calculator | `cable` 0.1.0, kind `norm` |
| Standards | DIN VDE 0100-430 (IEC 60364-4-43), 433.1, protection against overload; DIN VDE 0100-520 (IEC 60364-5-52) and DIN VDE 0298-4, current-carrying capacity and correction factors |
| Code | `src/uea/packs/elec/cable.py`; lengths and circuits from `src/uea/packs/elec/geometry.py`; tables from `src/uea/calc/data.py` |
| Tests | `tests/test_calc_elec.py`, `tests/test_data.py` |
| Review | **Not yet reviewed** by a licensed person. The worked examples of the standards have **not** been run. |

The tables of the standards are licensed and are not in this repository (`docs/decisions/0008-office-supplied-norm-data.md`, `0028-norm-tables-and-electrical-calculators.md`). The code holds the formulas; the office supplies the numbers with `uea data add`, and every result names the edition of each table it used. The tests use tables of our own with invented values that are not any standard's.

## What it computes

For each circuit (or the circuits of one circuit, RCD or board): is the cable big enough for the circuit breaker in front of it? The result per circuit is `ok`, `fail`, `no table data` (the table has no row for the case) or `not checked`. It also names the smallest cross-section of the table that would carry the breaker's rated current, as a hint and not a recommendation. The record is `out/cable.json`, the report for humans `out/cable.md`.

## Clauses and how they are implemented

| Clause | Rule | Implementation |
|---|---|---|
| 433.1 (DIN VDE 0100-430) | Ib ≤ In ≤ Iz and I2 ≤ 1.45 · Iz | In ≤ Iz is tested. I2 = 1.45 · In is the conventional tripping current of a miniature circuit-breaker of characteristic B, C or D (EN 60898), so the second condition follows. For other characteristics the circuit is `not checked`. |
| Ib ≤ In | the design current must not exceed In | Ib is known only from the declared load (luminaires, connections, feeds); with no declared load Ib stays open. A circuit whose declared load needs more than In fails. |
| DIN VDE 0100-520, DIN VDE 0298-4 | Iz is the table value for installation method, insulation and loaded conductors, times the correction factors | Iz = `ampacity` row (method, insulation, loaded conductors 2 for one phase or 3 for three phases, cross-section) × `temp-factor` row (insulation, ambient temperature, only if `temp=` is given) × `group-factor` row (arrangement, number of circuits, only if `group=` is above 1). |

A cross-section, temperature or group the table does not list is `no table data`. It is never interpolated or rounded to a neighbour.

## Not implemented

- Short-circuit protection and the fault loop (breaking time, loop impedance).
- The minimum cross-section by use, and the neutral conductor, PE and harmonics.
- Aluminium conductors, and installation methods the office's table does not list.
- The temperature and the grouping are settings of the call, not derived from the model (the cable routes do not yet know what lies together).
- Overload protection by fuses or breakers other than B, C, D.

## Assumptions to check when signing

- The installation method is one setting for the whole call (`method=`). Run the calculator per scope for circuits laid in different ways.
- The loaded conductors are 2 for one-phase and 3 for three-phase circuits (the neutral is taken as unloaded).
- The insulation is PVC unless `insulation=` says otherwise; the model's cable designation (NYM-J, ...) is not interpreted.
- The table is exactly what the office entered. UEA checks its shape (columns, numbers, duplicates), not its content.

## Test cases

All expected values are computed by hand from our own invented table: B2 PVC with two loaded conductors 1.5 mm² → 12 A, 2.5 mm² → 16 A, 4 mm² → 22 A; three loaded conductors 2.5 mm² → 14 A; C PVC two loaded 1.5 mm² → 15 A; at 40 °C PVC factor 0.8; three grouped, bundled, factor 0.7.

| Test | Case | Expected |
|---|---|---|
| `test_cable_at_reference_conditions` | NYM-J3x1.5 B10 | Iz 12 A ≥ 10 A: ok |
| | NYM-J3x2.5 B16 | Iz 16 A = 16 A: ok |
| | NYM-J3x1.5 B16 | fail; 2.5 mm² is the smallest that carries 16 A |
| | NYM-J5x2.5 B16, three-phase | Iz 14 A < 16 A: fail; no larger row |
| | NYM-J3x6 B25 | no table data (no row for 6 mm²) |
| | NYM-J3x2.5 K10 | not checked |
| `test_cable_other_installation_method` | method C | NYM-J3x1.5: Iz 15 A; NYM-J3x2.5: no table data |
| `test_cable_corrections_for_temperature_and_grouping` | 40 °C | NYM-J3x1.5 B10: 12 × 0.8 = 9.6 A, fail; NYM-J3x2.5 B16: 12.8 A, fail, smallest 4 mm² (22 × 0.8 = 17.6 A) |
| | three grouped | NYM-J3x1.5 B10: 12 × 0.7 = 8.4 A |
| | both | 12 × 0.8 × 0.7 = 6.72 A |
| | 35 °C, group of 4 | no table data |
| `test_cable_declared_load_above_the_breaker` | 3680 W on a B16 | Ib 16.0 A: ok; 4600 W: Ib 20.0 A, fail |
| `test_a_calculator_without_its_table_stops` | no tables installed | stops and names the table and the command to add it |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

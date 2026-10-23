# Validation report: `equip` (minimum equipment of a room)

| | |
|---|---|
| Calculator | `equip` 0.1.0, kind `norm` |
| Standards | DIN 18015-2, minimum equipment of electrical installations in dwellings |
| Code | `src/uea/packs/elec/equip.py`; what lies in each room from `src/uea/packs/mount.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_calc_elec.py` at commit `517c07e` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/foundations.md#0008-office-supplied-norm-data`). |

The numbers of the standard are licensed and not in this repository (`0008`). The office supplies them as the table `elec-minimum`; the tests use invented values.

## What it computes

For each room: the sockets, lighting outlets, communication outlets and dedicated connections it has, against the row of the table for its use, the grade and its finished area. The result per room is `ok`, `short`, `waived`, `no row` or `ok, larger than the table`. The record is `out/equip.json`, the report `out/equip.md`.

## Rules as implemented

| Rule | Implementation |
|---|---|
| The number of each by use and area | The rows of `elec-minimum` with the room's use and the grade, by area: the first whose `upto` ≥ the room's finished area. Larger than the last row: the last row, and the result says so. |
| What the room has | Wall devices on the face towards the room (5 cm in front of the face, `mount.py`), luminaires in or facing it. `sock`, `lum`, `data`, `conn`. |
| A frame with several outlets | `combos=one`: once; `combos=each`: per outlet (`n=`). |
| An accepted shortfall | A waiver of `W-ELEC-010` on the room: `waived`, the result stays ok, the reason is in the report. |

## Not implemented

- The number of circuits per dwelling, and where in the room the outlets are.
- Rooms outside dwellings.

## Assumptions to check when signing

- That each room's use is the use the standard means (a kitchen-living room is one room of one use in UEA).
- The grade the client chose.
- How a combination of outlets counts (`combos=`).

## Test cases (passed at commit `517c07e`)

Table: living, grade 1, up to 20 m²: 3 sockets, 1 light, 1 data; up to 100 m²: 5, 2, 1; kitchen up to 999 m²: 5, 2, 0, 2 connections.

| Test | Case | Expected |
|---|---|---|
| `test_equip_counts_against_the_table` | the living room 9.38 × 7.38 = 69.22 m² with a double and two single sockets and two luminaires | row up to 100 m²; sockets 3/5, data 0/1 short, light 2/2; with `combos=each` 4 sockets |
| `test_equip_waiver_grade_and_area` | a waiver on the room | waived, ok, reason in the report |
| | grade 3 | no row |
| | a table only up to 20 m² | the last row, ok |
| | scope `zz` | stops |

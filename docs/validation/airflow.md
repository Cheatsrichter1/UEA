# Validation report: `airflow` (Lüftungskonzept und Luftvolumenströme)

| | |
|---|---|
| Calculator | `airflow` 0.1.0, kind `norm` |
| Standard | DIN 1946-6:2019-12 |
| Code | `src/uea/packs/vent/airflow.py`; the units and terminals from `geometry.py` |
| Tests | `tests/test_vent.py` |
| Review | **Not yet reviewed** by a licensed person. The worked examples of the standard have **not** been run. The formulas below are as implemented; the review must check them, and the meaning of each table's columns, against the text of the standard, which is not in this repository. |

All numbers of the standard come from the office's tables; n_50 and the insulation are the planner's settings (`docs/decisions/0038-ventilation.md`). Every result names the edition of each table.

## What it computes

The dwelling's area and volume, its total air flow at the four ventilation levels, its infiltration, whether a ventilation measure is needed, the design flow, and each supply and extract room's flow at the nominal level. Against the system in `vent.uea`: what each room gets, what each central unit carries, and what falls short. The record is `out/airflow.json`, the report `out/airflow.md`.

## Formulas as implemented

- A_NE = Σ A_fin, V_NE = Σ V of the rooms whose use is not `none` in `vent-room`.
- q_v,ges,level = f · (a · A_NE² + b · A_NE + c), with the row `fl-high` or `fl-low` for FL by the setting `insulation`, else `rl`, `nl`, `il`.
- q_v,inf = komp · V_NE · n_50 · (lage · dp / 50)^n.
- Measure needed ⇔ q_v,inf < q_v,ges,FL.
- q_design = max(q_v,ges,NL, Σ q_extract,R).
- Extract room: q_R = q_extract,R · q_design / Σ q_extract. Supply room: q_R = q_design · f_R / Σ f_R. Overflow rooms: none.
- Central terminals of a room: together the room's flow (less what decentral units in it give), in equal shares; outdoor and exhaust air terminals share their unit's supply and extract.
- Decentral unit: flow/2 to supply and to extract (mode alt), flow to both (both), flow to extract (ext).
- Fails if a room gets less than q_R (with a system), a unit's type flow is below its supply or extract, or a measure is needed and there is no system.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| A_NE, V_NE | the rooms' finished areas and volumes |
| a, b, c, f | table `vent-total` |
| komp, lage, dp, n | table `vent-infiltration` |
| Role, q_extract, f_R by room use | table `vent-room` |
| n_50, insulation | settings |
| Unit flows | the `ahu` and `fan` types |

## Deviations and not implemented

- One dwelling per project.
- No overflow openings, no outdoor air inlets of exhaust systems, no fireplaces.
- The infiltration by the formula above; the review checks how the standard distinguishes it by system and location.
- A system is checked at the nominal level only; the reduced and intensive levels are reported, not checked.
- Heat recovery is not carried into the Heizlast.

## Assumptions to check when signing

- Which rooms belong to the dwelling (the rows marked `none`).
- The building's insulation and n_50.
- The units' flows from the manufacturer.

## Test cases

The box of `tests/test_heatload.py` with r1 living (supply, f_R 3) and r2 kitchen (extract 40 m³/h). Synthetic tables: NL = A + 20, FL (high) = 0.3 A + 10, IL = 1.3 A + 26; komp 0.5, lage 1, dp 2, n 1.

| Test | Case | Expected |
|---|---|---|
| `test_airflow_without_a_system` | no units | A_NE 4.68 · 7.38 + 4.565 · 7.38; the totals; q_v,inf = 0.5 · V · 1.5 · 0.04; a measure needed and no system: fails; with n_50 40 no measure: ok |
| `test_airflow_against_the_units` | a push-pull pair; a central unit; a unit of 60 m³/h | 15 m³/h in each room, short; every terminal the nominal flow, the unit carries it; too small: fails |
| `test_haus_mueller_ventilation` | the prototype | loads, pairs derived, feeds reach the units |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

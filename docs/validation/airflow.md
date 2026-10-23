# Validation report: `airflow` (Lüftungskonzept und Luftvolumenströme)

| | |
|---|---|
| Calculator | `airflow` 0.2.0, kind `norm` |
| Standard | DIN 1946-6:2019-12 |
| Code | `src/uea/packs/vent/airflow.py`; the units and terminals from `geometry.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_vent.py` at commit `517c07e` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/foundations.md#0008-office-supplied-norm-data`). |

All numbers of the standard come from the office's tables; n_50 and the insulation are the planner's settings (`docs/decisions/services.md#0038-ventilation`). Every result names the edition of each table.

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
- Outdoor air inlet (`inlet`): its type's flow to its room's supply.
- Overflow, once `vent.uea` has an `over`: for each supply and extract room, the area its flow q_R needs (the first row of `vent-overflow` with upto ≥ q_R) against the free area of the overflow openings in its doors (`area=`, or the door's width × `cut=`).
- Fails if a room gets less than q_R (with a system), a unit's type flow is below its supply or extract, a measure is needed and there is no system, or a room's overflow openings are smaller than its flow needs.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| A_NE, V_NE | the rooms' finished areas and volumes |
| a, b, c, f | table `vent-total` |
| komp, lage, dp, n | table `vent-infiltration` |
| Role, q_extract, f_R by room use | table `vent-room` |
| n_50, insulation | settings |
| Unit flows | the `ahu`, `fan` and `inlet` types |
| Overflow area by flow | table `vent-overflow` |

## Deviations and not implemented

- One dwelling per project.
- No fireplaces. Overflow is checked room by room at its doors; the air's way through the overflow zone (the hall) is not followed. An inlet gives its type's flow at the system's design pressure, which is not computed.
- The infiltration by the formula above; the review checks how the standard distinguishes it by system and location.
- A system is checked at the nominal level only; the reduced and intensive levels are reported, not checked.
- The heat recovery goes into the Heizlast with `uea calc heatload ... insulation=` (`heatload.md`).

## Assumptions to check when signing

- Which rooms belong to the dwelling (the rows marked `none`).
- The building's insulation and n_50.
- The units' flows from the manufacturer.

## Test cases (passed at commit `517c07e`)

The box of `tests/test_heatload.py` with r1 living (supply, f_R 3) and r2 kitchen (extract 40 m³/h). Synthetic tables: NL = A + 20, FL (high) = 0.3 A + 10, IL = 1.3 A + 26; komp 0.5, lage 1, dp 2, n 1.

| Test | Case | Expected |
|---|---|---|
| `test_airflow_without_a_system` | no units | A_NE 4.68 · 7.38 + 4.565 · 7.38; the totals; q_v,inf = 0.5 · V · 1.5 · 0.04; a measure needed and no system: fails; with n_50 40 no measure: ok |
| `test_airflow_against_the_units` | a push-pull pair; a central unit; a unit of 60 m³/h | 15 m³/h in each room, short; every terminal the nominal flow, the unit carries it; too small: fails |
| `test_inlets_supply_their_room` (`tests/test_vent_more.py`) | an exhaust fan in r2, two inlets of 30 m³/h in r1 | r1 gets 60, r2 30; an inlet on an interior wall: `W-VENT-003` |
| `test_overflow_openings` | door d2 between r1 and r2, 0.885 m wide; table 150 cm² up to 150 m³/h | no `over`: not checked; undercut 0.01 m: 88.5 cm² < 150, fails; and an element of 100 cm²: ok |
| `test_haus_mueller_ventilation` | the prototype | loads, pairs derived, feeds reach the units |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.2.0 | Outdoor air inlets, overflow openings against `vent-overflow` (decision 0043) |

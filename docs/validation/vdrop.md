# Validation report: `vdrop` (voltage drop of a circuit)

| | |
|---|---|
| Calculator | `vdrop` 0.1.0, kind `norm` |
| Standard | DIN VDE 0100-520 (IEC 60364-5-52), Annex G, voltage drop in consumers' installations |
| Code | `src/uea/packs/elec/vdrop.py`; lengths from `src/uea/packs/elec/routes.py`; tables from `src/uea/calc/data.py` |
| Tests | `tests/test_calc_elec.py`, `tests/test_routes.py` |
| Review | **Not yet reviewed** by a licensed person. The worked examples of the standard have **not** been run. |

The standard's constants are licensed and are not in this repository (`docs/decisions/0008-office-supplied-norm-data.md`, `0028-norm-tables-and-electrical-calculators.md`). The code holds the formula; the office supplies ρ and λ in the table `conductor`, and every result names the edition of the table it used. The tests use values of our own that are not any standard's.

## What it computes

For each circuit: the voltage drop from its board to the farthest device on its cable, in volts and in percent of 230 V, against a limit that the caller gives. The record is `out/vdrop.json`, the report for humans `out/vdrop.md`.

## Formula

ΔU = b · (ρ · L / S · cos φ + λ · L · sin φ) · I, ΔU % = 100 · ΔU / U₀

b = 2 for a single-phase and 1 for a three-phase circuit; U₀ = 230 V (phase to neutral); ρ in Ω·mm²/m (resistivity of the conductor in service), λ in mΩ/m (reactance of the cable per length), L the one-way length in m, S the cross-section in mm², I the current in A. Copper unless the cable designation starts NA (aluminium).

## Inputs and how they are chosen

| Input | Source |
|---|---|
| L | the derived cable length from the board to the farthest device (`0027-cable-routes.md`, a rectilinear shortest tree plus 0.3 m per run) times `reserve` (1.2 unless given). The derived length is a minimum; the reserve stands for the route on site and is the planner's call. |
| I | for a circuit with no socket and a declared load: the current of that load, P / (230 V · phases · cos φ). For a circuit with sockets, or none declared: In times `demand` (1 unless given). `current=in` takes In always. The whole current is taken over the whole length, which is the safe side. |
| cos φ | setting `cos` (1 unless given); sin φ = √(1 − cos²). |
| ρ, λ | table `conductor`, one row per material. |
| limit | setting `limit`, required. |

## Not implemented

- The voltage drop in the feeder from the house connection to the board (it is not in the model), and the limit for the whole route: DIN 18015-1 sets one for the route from the meter.
- Motor starting, harmonics, the temperature rise of the cable during the calculation.
- Distributed loads: a load spread along the cable would drop less than the whole current at the end.

## Assumptions to check when signing

- The length is derived from the electrical model, not measured. Check the farthest device and the reserve.
- The current on socket circuits is a planning assumption (In times `demand`), recorded in the result.
- ρ must be the resistivity at the temperature the planner designs for, as the standard defines it; UEA does not adjust it.

## Test cases

All expected values are computed by hand with our own invented table (`Cu`: ρ 0.02 Ω·mm²/m, λ 0.1 mΩ/m; `Al`: ρ 0.036, λ 0.1). The circuits are on a 10 × 8 box house, the board 1.4 m above the floor on the west wall, sockets 0.3 m above it.

| Test | Case | Expected |
|---|---|---|
| `test_voltage_drop_single_phase_on_sockets` | NYM-J3x2.5 B16 with two sockets; cable to the farther one 3.7 m (board to socket 2.4 m, socket to socket 1.3 m, with 0.3 m a run) | L = 3.7 × 1.2 = 4.44 m, I = 16 A: ΔU = 2 · 16 · 4.44 · 0.02 / 2.5 = 1.13664 V = 0.49419 %; fails a limit of 0.4 %, meets 0.5 % |
| `test_voltage_drop_with_a_power_factor_and_a_reserve` | cos φ 0.8 | 142.08 · (0.008 · 0.8 + 0.0001 · 0.6) = 0.917837 V |
| | `demand=0.5` | 8 A, 0.56832 V |
| | `reserve=1` | 2 · 16 · 3.7 · 0.008 = 0.94720 V |
| `test_voltage_drop_three_phase_on_a_declared_load` | NYM-J5x2.5 B16, one connection of 9000 W | cable 3.4 m, L = 4.08 m, I = 9000 / (3 · 230) = 13.0435 A, b = 1: ΔU = 13.0435 · 4.08 · 0.008 = 0.42574 V = 0.18510 %; `current=in`: 16 · 4.08 · 0.008 V |
| `test_voltage_drop_aluminium` | NAYY-J3x16 B25, one socket | cable 5.4 m, L = 6.48 m: ΔU = 2 · 25 · 6.48 · 0.036 / 16 = 0.729 V |
| `test_voltage_drop_circuit_without_a_place` | nothing on the circuit has a place | "without a length", not counted as a pass |
| `test_voltage_drop_settings_are_checked` | limit 0, cos 1.5, reserve 0.9, demand 0 or 1.2 | stops with a message |
| `test_voltage_drop_needs_a_conductor_row` | aluminium cable, table with copper only | stops and names the missing row |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

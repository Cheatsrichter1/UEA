# Validation report: `heatload` (Heizlast room by room)

| | |
|---|---|
| Calculator | `heatload` 0.3.0, kind `norm` |
| Standard | DIN EN 12831-1:2017-09 with the national supplement DIN/TS 12831-1:2020-04 |
| Code | `src/uea/packs/heat/heatload.py`; surfaces from `envelope.py`, U-values from `thermal.py` (`docs/validation/uvalue.md`) |
| Tests | `tests/test_heatload.py` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

All numbers of the standards come from the office's tables or are the planner's settings (`docs/decisions/0033-u-values-and-heizlast.md`). Every result names the edition of each table.

## What it computes

For each heated room: the transmission heat loss Φ_T, the ventilation heat loss Φ_V and the design heat load Φ_HL = Φ_T + Φ_V, with every surface listed. For the whole project, the building's heat load. Once `heat.uea` has emitters, each heated room's emitters against its load and the generators against the building's (`docs/decisions/0034-heating-elements.md`): their output is the type's at the design temperatures (`w=`, `q=`), or, for types with the manufacturer's test values, calculated per DIN EN 442-2 (radiators, `wn=` and `n=`) and DIN EN 1264-2 (underfloor heating, `kh=`) at the circuit's temperatures (the manifold's `flow=`/`spread=`, else the settings `flow=` and `spread=`); a shortfall makes the result fail. With `floor=` (and `bathfloor=` for baths and WCs), an underfloor heating whose mean floor surface temperature is above the limit fails too (`docs/decisions/0042-heating-and-hot-water-details.md`). The record is `out/heatload.json`, the report for humans `out/heatload.md`.

## Formulas as implemented

- Φ_T,i = Σ_k A_k · U_c,k · f_k · (θ_int,i − θ_e)
- U_c,k = U_k + ΔU_TB against outside air, the ground and unheated rooms; U_k against heated rooms
- f_k = 1 against outside air (and against a stretch with no room beyond, which is noted)
- f_k = f_g1 · (θ_int,i − θ_m,e) / (θ_int,i − θ_e) · G_w against the ground
- f_k = (θ_int,i − θ_j) / (θ_int,i − θ_e) against a room j, heated or not; negative when j is warmer
- Φ_V,i = V̇_i · ρc_p · (θ_int,i − θ_e), V̇_i = max(V̇_inf,i, n_min · V_i)
- V̇_inf,i = 2 · V_i · n_50 · e_i · ε_i
- With a ventilation system (`insulation=`; the flows from `airflow`): V̇_i = V̇_inf,i + V̇_su,i · f_V,su,i + max(0, V̇_min,i − V̇_inf,i − V̇_su,i − V̇_tr,i), f_V,su = (θ_int − θ_su) / (θ_int − θ_e), θ_su = θ_e + η · (θ_ex − θ_e) per unit with η its type's `hr=` (an inlet: η 0), θ_ex the extract rooms' θ_int weighted by their flows; V̇_tr of an extract room its flow, taken at its own temperature (DIN EN 12831-1, 6.3.3, simplified)
- Building: Φ_HL = Σ_i over heated rooms (Φ_T,i without the surfaces to heated rooms) + Σ_i Φ_V,i

## Inputs and how they are chosen

| Input | Source |
|---|---|
| A | the surfaces of the room (`envelope.py`). Lengths along the shell outline (core faces). Wall heights from FFL to the FFL above, or to the wall's top under a roof. Floors and ceilings with the area of the shell outline. Roofs with their sloped area. Windows and doors with width × height. |
| U | `docs/validation/uvalue.md`; windows and doors from `uw=`/`ud=` of their type (a door: `ud`, else `uw`) |
| θ_e, θ_m,e | table `outdoor` by the project's `postcode=`, or the settings `te`, `tme` |
| θ_int, θ_j, n_min, heated | table `room-temp` by the room's use |
| ΔU_TB | setting `tb`, required |
| n_50 | setting `n50`, required |
| e | table `infiltration` by the number of outside walls of the room with windows or doors (0, 1, 2+) and the setting `shielding` |
| ε | table `height-factor`: the first row whose `upto` reaches the height of the room's middle (FFL plus half the mean clear height) above the terrain |
| V | the room's derived volume: finished floor area times clear height |
| f_g1, G_w, ρc_p | table `heatload-factors`; G_w by the setting `groundwater` (deep unless given) |

## Deviations and not implemented

- **Ground:** the component's U (R_se = 0) instead of U_equiv per DIN EN ISO 13370 with B' and the depth. This overestimates the loss to the ground.
- **Infiltration:** the room formula above, not the 2017 method with q_env50 and the building's air flow distributed over the rooms. The building's load does not reduce the infiltration.
- Reheat (Aufheizleistung), mechanical ventilation, heat flows to neighbouring buildings, rooms higher than the table's heights.
- A room's temperature follows its use; a room that differs (a bath at 24 °C in a table that says 20) needs its own use or a later `ti=`.

## Assumptions to check when signing

- The convention for dimensions (shell outline, storey heights) and the ΔU_TB that goes with it.
- The room uses and their rows in `room-temp`, the shielding and n_50.
- Surfaces the report shows as "außen (kein Raum)": UEA found no room there.

## Test cases

Synthetic tables of our own (`tests/test_heatload.py`): θ_e −10 °C, θ_m,e 10 °C; living 20 °C, bedroom 18 °C, storage unheated at 5 °C, n_min 0.5; e 0 / 0.02 / 0.03; ε 1 up to 10 m; f_g1 1.45, G_w 1, ρc_p 0.34; settings tb 0.05, n50 3. The house is a 10 × 8 box: exterior walls U 0.16, the wall between the two rooms U 1.25, the floor to the ground U = 1/2.82, a flat roof U = 1/5.24. The shell of r1 is 4.7 × 7.4 m, the storey 3 m.

| Test | Case | Expected |
|---|---|---|
| `test_heat_load_of_two_rooms` | r1, living | outside walls (22.2 + 14.1 + 14.1 − 1.44) × 0.21; window 1.44 × 1.05; to r2 22.2 × 1.25 × 2/30; floor 34.78 × (1/2.82 + 0.05) × 1.45 × 10/30; roof 34.78 × (1/5.24 + 0.05); all × 30 K |
| | r1, air | V = 4.68 × 7.38 × 2.45; V̇_inf = 2 · V · 3 · 0.02 < V̇_min = 0.5 V; Φ_V = 0.5 V · 0.34 · 30 |
| | r2, bedroom | to the warmer r1: f = (18 − 20)/28; no window, e = 0 |
| | building | the sum without the two flows between r1 and r2 |
| `test_an_unheated_room_and_the_terrain` | r2 an unheated storage room at 5 °C, terrain 0.5 m above the FFL | to r2: U + 0.05, f = 0.5; the west wall 7.4 × 0.5 m² to the ground with f = 1.45 × 10/30, 7.4 × 2.5 m² to outside air |
| `test_settings_and_tables_are_checked` | missing settings, tables, postcode, room use; n50 0; an unknown shielding; `te=`/`tme=` given | stops and names what is missing; with `te`/`tme`, no table `outdoor` needed |
| `test_a_window_without_a_u_value` | window type without `uw=` | stops and names the window and its type |
| `test_radiator_and_floor_at_their_temperatures` (`tests/test_emitters.py`) | radiator wn 1000 W, n 1.3 in r2 at 18 °C; underfloor kh 6 in r1 at 20 °C; system 55/45 | Φ = 1000 · (Δθ/Δθ_n)^1.3 with Δθ = 10/ln(37/27), Δθ_n = 10/ln(55/45); q = 6 · 10/ln(35/25); θ_F,m = 20 + (q/8.92)^(1/1.1); with floor=29 it fails; without temperatures no output |
| `test_heat_recovery_in_the_heat_load` (`tests/test_vent_more.py`) | a central unit with η 0.85 supplying r1 and extracting from r2, θ_e −10 °C | r1: V̇_su = NL, θ_su = −10 + 0.85 · 30 = 15.5 °C, V̇ = V̇_inf + NL · 4.5/30 + max(0, V̇_min − V̇_inf − NL); r2: V̇_tr = NL, V̇ = V̇_inf + max(0, V̇_min − V̇_inf − NL); Φ_V = V̇ · 0.34 · 30 |
| `test_the_envelope_of_haus_mueller` | the reference house | no unknown neighbours; floors cover every room; the kitchen's outside walls are its two shell lengths × 2.875 m |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.2.0 | Emitters and generators against the loads (`test_emitters_against_the_heat_load` in `tests/test_heat.py`) |
| 0.3.0 | Emitter output per DIN EN 442-2 and DIN EN 1264-2 at the circuit's temperatures, the floor surface temperature against `floor=` (decision 0042); with `insulation=`, the ventilation system's flows and heat recovery in Φ_V (decision 0043) |

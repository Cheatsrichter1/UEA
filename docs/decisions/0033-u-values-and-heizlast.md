# 0033: U-values and the Heizlast, slices 6a and 6b

Status: Accepted (slices 6a and 6b built)
Date: 2026-10-10

## Context

Phase 6 is plumbing and heating, with the Heizlast per DIN EN 12831-1 as its `norm` calculator. The user chose the order: the Heizlast first, because emitters are sized to the room loads, then the heating elements, plumbing with pipe sizing, and the exports. The Heizlast needs the U-value of every surface around a room (DIN EN ISO 6946) and the surfaces themselves: which wall, slab or roof, how large, and what lies beyond it. The model has the build-ups as layers with material names and thicknesses, windows and doors with `uw=`/`ud=`, and rooms with a use. It has no thermal data: conductivities, surface resistances, design temperatures and air change rates are numbers of licensed standards, which the office supplies (`0008-office-supplied-norm-data.md`, `0028-norm-tables-and-electrical-calculators.md`).

## Decision

**Two calculators.**
- `uea calc uvalue [scope]`: the U-value of each build-up, once for each way the rooms use it. A build-up is a wall, slab or roof type, or a slab with the floor type of the room on it (`DE-20 + FB-par`). The way it is used is the direction of the heat flow (horizontal through walls, down through floors, up through ceilings and roofs) and what lies beyond it (outside air, the ground, a room). Scope: a room or a type.
- `uea calc heatload tb= n50= shielding= [scope]`: the Heizlast of each heated room and of the building. Scope: a storey or a room.

Neither shows up in `uea get`: the results depend on the tables installed on the machine, and `uea get` must be the same everywhere (the reason `W-ELEC-010` became a calculator in 0028).

**U-value** (DIN EN ISO 6946): R = d / λ per layer, R_T = R_si + Σ R + R_se, U = 1 / R_T, homogeneous layers only. λ comes from the table `material`, keyed by the material name the layers write (`ziegel-t9`), so the office's names and the project's must match; a missing material stops the calculator and names all of them. R_si and R_se come from the table `surface` by the direction of the heat flow. Beyond the ground R_se = 0; beyond a room, heated or not, R_se = R_si of the same direction.

**The surfaces of a room** (`src/uea/packs/heat/envelope.py`):
- Walls: the room's shell outline (the core faces) is matched to the walls it runs along. Beyond each stretch of a wall, a strip 0.3 m deep is searched for rooms of the same storey. A stretch with no room is outside air if the wall is an exterior wall, else unknown. The end of a wall that meets this one from the far side counts with the room next to it.
- Height: from the FFL to the FFL of the storey above, or to the wall's top where no storey is above. The part of an exterior wall below the terrain (`ground=` of the project) borders the ground.
- Windows and doors lie in the stretch that holds their middle, with their width times their height, and are subtracted from the wall. An interior door without a U-value is part of its wall.
- Floor: the slab of the storey with the room's floor type, against the rooms of the storey below in proportion to their overlap. The part over that storey's walls is shared out among the rooms in proportion. The ground where no storey is below.
- Ceiling: the slab of the storey above with the floor type of each room on it. Where nothing is on it, it is a flat roof to outside air. With no slab above, the roof: its sloped area over the room, from the planes of the room's ceiling.
- Unknown neighbours count as outside air (the safe side), with a note.

**Heizlast** (DIN EN 12831-1 with DIN/TS 12831-1), room by room:
- Φ_HL,i = Φ_T,i + Φ_V,i.
- Φ_T,i = Σ A · U_c · f · (θ_int,i − θ_e), with U_c = U + ΔU_TB against outside air, the ground and unheated rooms.
- f = 1 against outside air; f_g1 · (θ_int − θ_m,e)/(θ_int − θ_e) · G_w against the ground; (θ_int − θ_j)/(θ_int − θ_e) against a room at θ_j. The last can be negative, when the neighbour is warmer.
- Φ_V,i = V̇ · ρc_p · (θ_int − θ_e), with V̇ = max(V̇_inf, n_min · V) and V̇_inf = 2 · V · n_50 · e · ε.
  - V is the room's derived volume (finished floor area times clear height).
  - e depends on the number of outside walls of the room with windows or doors (0, 1, 2+) and on the shielding.
  - ε depends on the height of the room's middle above the terrain.
- The building's load is the sum over the heated rooms without the flows between them.

**Office tables** (`uea data`): `material`, `surface`, `outdoor` (θ_e and θ_m,e by postcode), `room-temp` (heated or not, θ_int and n_min by UEA's room use), `infiltration` (e), `height-factor` (ε), `heatload-factors` (f_g1, G_w for deep and shallow groundwater, ρc_p). Table columns may now allow 0 or negative numbers (`Col.sign`), for temperatures and coefficients that are 0.

**Settings:**
- The planner's decisions have no default: `tb` (ΔU_TB, which depends on how the details are built), `n50` (the airtightness the building is to meet) and `shielding`.
- `groundwater` defaults to deep.
- `te=` and `tme=` replace the table `outdoor`, for a site the office has no row for.

**Deviations from the standard, stated in every report and in `docs/validation/heatload.md`:**
- The ground uses the component's U instead of U_equiv per DIN EN ISO 13370. This overestimates the loss, so it is on the safe side.
- Infiltration uses the room formula above instead of distributing the building's air flow through q_env50.
- No reheat, no mechanical ventilation, no neighbouring buildings.
- The building's load does not reduce the infiltration.

These are to be settled in the review with a licensed person, against the text of the standard, which UEA does not have.

## Alternatives

- **U-values in `uea get`.** The model would read differently on every machine.
- **λ in the model (`mat ziegel-t9 lambda=0.09`).** It is right for a manufacturer's declared value, but the values from DIN 4108-4 are licensed and would travel with every copy of the project. An office's table can hold both kinds.
- **Room dimensions between finished surfaces.** The standard allows several conventions. The shell outline with storey heights is closer to outer dimensions and is what the model derives exactly; thermal bridges are in ΔU_TB.
- **Temperature correction factors b_u for unheated spaces instead of a temperature.** One temperature per use is one number and gives the same f.
- **The 2017 infiltration method now.** It needs the building's envelope area and q_env50, and a distribution over the rooms that the review should confirm first. The room formula is transparent and replaceable.
- **One calculator for both.** The U-values are useful alone (GEG, the architect's build-ups), with their own standard and validation report.

## Consequences

- Tested with hand-computed values (`tests/test_heatload.py`) on a box of two rooms with synthetic tables. The tests cover the U-values, transmission to outside, ground, a warmer and an unheated neighbour, a flat roof, the terrain, ventilation and the building's sum, and the checks of settings and tables. Haus Müller's envelope has no unknown neighbours, and floor and ceiling cover every room.
- Both calculators are `norm` calculators (`docs/validation/uvalue.md`, `heatload.md`).
- `help calc` names both; the bench's reading of the help is unchanged, since `calc` is a topic of its own.
- Open: U_equiv for the ground, the 2017 infiltration method, reheat, mechanical ventilation (phase 7), air layers and inhomogeneous layers (rafters with insulation, timber frames), a room temperature that differs from its use (`ti=` on a room), the heating elements that cover the loads (slice 6c).

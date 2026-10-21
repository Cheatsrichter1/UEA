# Validation report: `water` (Trinkwasser-Rohrbemessung)

| | |
|---|---|
| Calculator | `water` 0.1.0, kind `norm` |
| Standard | DIN 1988-300:2012-05 |
| Code | `src/uea/packs/plumb/water.py`; sections from `geometry.py`, the hydraulics in `hydraulics.py` |
| Tests | Removed (`docs/decisions/0052-no-tests-in-the-repo.md`); the cases below passed in `tests/test_plumb.py` at commit `517c07e` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

All numbers of the standard come from the office's tables or the planner's settings, and the product values from the model's types (`docs/decisions/0035-plumbing.md`). Every result names the edition of each table.

## What it computes

For each section (Teilstrecke) of the cold-water network (from the meter) and of each hot-water network (from a storage tank that heats drinking water): the sum of the design flows, the peak flow, the pipe size, the velocity, the pressure loss per metre and the loss of the section. For each fixture, cold and hot: the pressure left over its minimum flow pressure. A fixture short of pressure, or a section faster than v_max in the largest size, makes the result fail. The record is `out/water.json`, the report for humans `out/water.md`.

## Formulas as implemented

- ΣV̇_R: the fixtures beyond the section. On the cold side, a tank counts with the hot V̇_R of the fixtures it supplies.
- V̇_S = min(ΣV̇_R, max(V̇_R,max, a · (ΣV̇_R)^b − c)).
- Size: the smallest of the pipe type with v = V̇_S / (π d_i² / 4) ≤ v_max; the largest if none.
- R = λ / d_i · ρv²/2. λ by Colebrook-White, 1/√λ = −2 lg(2.51 / (Re √λ) + k / (3.71 d_i)), iterated; λ = 64/Re below Re 2320. Water at 10 °C (ρ 999.7 kg/m³, ν 1.306 · 10⁻⁶ m²/s) cold, 60 °C (983.2, 0.474 · 10⁻⁶) hot.
- Z = Σζ · ρv²/2, Σζ = bends · ζ_bend + ζ_tee unless the section starts at the meter or the tank. Bends: one fewer than the axes (x, y, z) the section runs along.
- Δp = R · l + Z.
- Reserve = p_min,V − Δp_apparatus − ρ g Δh − Σ Δp − Δp_tank (hot water) − p_min,Fl, with Δh from the meter to the fixture's outlet.
- While a reserve is below 0: on the way of the fixture with the lowest reserve, the section with the largest Δp that can still grow takes the next size; all is computed again.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Sections, lengths, bends | the derived networks (`geometry.py`): rectilinear, lower bounds |
| V̇_R cold and hot, p_min,Fl | table `fixture-flow` by fixture |
| a, b, c | table `peak-flow` by the setting `building` (default residential) |
| v_max | table `water-factors` |
| p_min,V, Δp_apparatus | the meter's `p=` (bar) and `dp=` (hPa) |
| Δp_tank | the tank type's `dp=` |
| Sizes, k, ζ_bend, ζ_tee | the meter's pipe type (`type … pipe`) |
| Heights | the meter's z and each fixture's outlet (`z=`, else a default per fixture) |

## Deviations and not implemented

- One v_max for every section, without the standard's distinction by kind of pipe, flow duration and fittings.
- Fittings: only bends and tees, from the rectilinear run. No valves, no meter or filter as a ζ (they are in Δp_apparatus).
- The rule that keeps V̇_S between the largest single flow and ΣV̇_R.
- No continuous consumers, no circulation, no pressure booster or reducer.

## Assumptions to check when signing

- The derived pipe routes and their lengths, which are lower bounds.
- The fixtures' outlet heights.
- The rows of `fixture-flow` against the fittings chosen, and the building use.

## Test cases (passed at commit `517c07e`)

Synthetic tables of our own (`tests/test_plumb.py`): sink 0.1/0.1 l/s, shower 0.2/0.2 l/s, WC 0.1/0 l/s; p_min,Fl 1000 hPa, the WC 500 hPa; a = 1, b = 0.5, c = 0; v_max 2 m/s. The pipe type has 16x2, 20x2, 26x3 and 32x3, with k 0.007 mm and ζ 1 for a bend and a tee. The meter supplies 4 bar with 400 hPa of apparatus, and the tank loses 100 hPa.

| Test | Case | Expected |
|---|---|---|
| `test_hydraulics` | λ laminar and smooth at Re 10⁵; Colebrook's equation; 0.1 l/s in 12 mm; 1 m of height; a circle full and half full; DN 100 at 1 % | 0.064; 0.0180; the equation holds; v 0.8842 m/s, ρv²/2 3.908 hPa; 98.07 hPa; π/8 and π/4, R_h = d/4; 5.574 l/s full, half of it half full |
| `test_peak_flow` | ΣV̇_R 4, 0.3, and with c 1.2 | 2; 0.3 (ΣV̇_R); 0.5 (the largest single flow) |
| `test_water` | the box with an OG, a tank and a riser | 0.4 l/s from the meter to the tank in 20x2 (16x2 would be 3.54 m/s); the section to the sink with ζ 3 cold, 2 hot; the WC's reserve 4000 − 400 − 98.07 · 3.4 − its pipes − 500; the shower's hot way with the tank and the cold way to it |
| `test_water_enlarges_the_worst_way` | 2.6 bar; 1.5 bar | the 10.1 m section to the shower grows to 20x2 and every fixture has its pressure; at 1.5 bar it fails |
| `test_water_needs_its_data` | no p=, no tank dp=, a fixture missing from the table | stops and names it |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

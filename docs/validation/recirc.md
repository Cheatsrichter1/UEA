# Validation report: `recirc` (Zirkulation)

| | |
|---|---|
| Calculator | `recirc` 0.1.0, kind `norm` |
| Standards | DIN 1988-300:2012-05, the short method of the circulation; the limit of water without circulation is the planner's (DVGW W 551 sets 3 l) |
| Code | `src/uea/packs/plumb/recirc.py`; the circulated pipes from `src/uea/packs/plumb/geometry.py` (`circulated`); the hot-water sizes from `water.py`; the hydraulics in `src/uea/packs/hydraulics.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_plumb.py` at commit `517c07e` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/foundations.md#0008-office-supplied-norm-data`). |

The settings `loss` (W/m), `dt` (K) and `dead` (l) are the planner's. The tables are those of `water`, whose hot-water pipe sizes this calculator uses.

## What it computes

For each circulation (`recirc` in `plumb.uea`): for each circulated hot-water section its heat loss with everything beyond it, the circulation flow, the size of the circulation pipe beside it, and the loss in both pipes; the pump's flow and head; what the regulating valve at each other end throttles; and, for each fixture, the length and the water of the branch without circulation, against `dead`. A branch over the limit, or a circulation pipe faster than v_max in its largest size, makes the result fail. The record is `out/recirc.json`, the report `out/recirc.md`.

## Formulas as implemented

- Circulated: every hot-water section but those that end at a fixture and serve only it.
- Q̇_s = q · (l_s + Σ l beyond it), q = `loss`.
- V̇_s = Q̇_s / (ρ c_p Δθ), ρ = 983.2 kg/m³ (water at 60 °C), c_p = 4.179 kJ/(kg·K), Δθ = `dt`.
- Circulation pipe: the smallest of its pipe type with v ≤ v_max (`water-factors`); the largest if none.
- Δp = R · l + Σζ · ρv²/2 in the hot-water pipe (its size from `water`) and the circulation pipe at V̇_s; ζ: the bends of the run, a tee where it does not start at the tank.
- End: Δp_end = Σ over its way of both; head = max Δp_end; throttle = head − Δp_end.
- Water without circulation: Σ π d_i² / 4 · l from the fixture back to the circulated part.

## Not implemented

- The loss of the circulation pipe itself and of fittings and valves; one loss per metre for all pipes.
- The differential method (Differenzdruckverfahren), thermostatic valves with their characteristic, trace heating.

## Assumptions to check when signing

- That the circulation runs to every branch as derived, and the branches are as short as the plan.
- The loss per metre for the insulation built, the allowed temperature drop.

## Test cases (passed at commit `517c07e`)

The 10 × 8 box of `test_plumb`, the tank t1 with the sink sa1 on the EG and the shower sa2 up the riser sr1; pipe 16x2 (d_i 12 mm) first; v_max 2 m/s; q = 10 W/m, Δθ = 5 K.

| Test | Case | Expected |
|---|---|---|
| `test_circulation` | circulated t1>sr1:EG (8 m) and the riser (2.9 m) | Q̇ 109 and 29 W; V̇ = Q̇ / (983.2 · 4.179 · 5); circulation 16x2 with Δp = R · 8 + 1 · ρv²/2; the head the one end's loss; sa1's branch 8.7 m, sa2's 10.1 m with π · 0.012²/4 · 10.1 m³; with dead = 1 l sa2 fails |
| `test_circulation_needs_pipes_to_circulate` | t1 feeds one fixture | `W-PLUMB-007` |

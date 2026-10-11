# Validation report: `loads` (Lastannahmen und Lastabtrag)

| | |
|---|---|
| Calculator | `loads` 0.1.0, kind `norm` |
| Standards | DIN EN 1991-1-1:2010-12 with NA (actions), DIN EN 1990:2010-12 with NA (partial factors) |
| Code | `src/uea/packs/struct/loads.py`; the load path in `model.py` |
| Tests | `tests/test_struct.py` |
| Review | **Not yet reviewed** by a licensed person. Phase 8 goes on only with a licensed engineer who reviews this report (`ROADMAP.md`). The standard's worked examples have **not** been run. |

All values of the standards come from the office's tables; the soil resistance is the planner's setting from the geotechnical report (`docs/decisions/0040-structure.md`). Every result names the edition of each table.

## What it computes

For each slab: its area, its own weight per m², the floor build-ups and imposed loads of the rooms on it, the partition surcharge, G and Q, and the area each load-bearing wall under it carries. For each load-bearing wall: its own weight, and G and Q at its base. For each wall of the lowest storey: the characteristic and design line load on its footing and, with `soil=`, the footing's width. For each light partition: its weight per metre. The record is `out/loads.json`, the report `out/loads.md`.

## Formulas as implemented

- Weight of a build-up: g = Σ t_i · γ_i (kN/m²), t the layer's thickness, γ from `unit-weight`.
- Slab: G = A_net · g_slab + Σ_rooms A_fin · g_floor; Q = Σ_rooms A_fin · (q_k(use) + q_partition). A_net is the slab's outline without its voids; A_fin each room's finished area.
- Partition (a wall that is not load-bearing, above the lowest storey): w = g_wall · A_net,elevation / L (kN/m); q_partition = q_k of the first row of `partition-load` with w ≤ upto; the largest on a storey applies to its slab. Heavier than the last row: not taken, the result fails.
- Shares: the slab is cut into 5 cm cells; each cell goes to the nearest core of a load-bearing wall of the storey below (ties to the lower id). A_w = the cells of wall w; the wall takes G · A_w / A and Q · A_w / A.
- Wall: G_own = g_wall · A_net,elevation (the elevation between the wall's ends under its top, less doors and windows).
- Takedown, from the top storey down: G_base = G_own + slab shares + what the walls above pass on; a wall passes G_base and Q_base to the walls it stands on in proportion to the overlap of the cores.
- Footing: n_k = (G + Q) / L, n_d = (γ_G · G + γ_Q · Q) / L, b ≥ n_d / σ_R,d.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Layers, areas, heights, openings | the model (`arch.uea`), derived |
| Which walls carry | the architect's `lb` flag; the load path from the geometry |
| γ by material | table `unit-weight` |
| q_k by room use | table `imposed-load` |
| Partition surcharge | table `partition-load` |
| γ_G, γ_Q | table `struct-factors` |
| σ_R,d | setting `soil=`, from the geotechnical report |

## Deviations and not implemented

- No roof, snow or wind loads; no point or line loads; no beams, lintels or columns.
- Loads uniform over each slab (per slab, not per room); no continuity over interior supports, no cantilevers, no free edges.
- The load of a wall uniform over its length; no concentrated loads at the ends of lintels.
- Load-bearing walls on a slab are not carried (`W-STRUCT-001`); partitions on the ground slab are left out.
- No combinations with ψ factors; no design of walls, slabs or footings beyond the footing width.
- The shares on a 5 cm grid: within about 0.2 m² of the exact bisector areas in the tests.

## Assumptions to check when signing

- Which walls are load-bearing (the architect's flag), and that the slabs span as the nearest-wall partition assumes.
- The unit weights of the products used.
- The imposed loads by use, and whether the Spitzboden's use is right.
- The soil's design resistance.

## Test cases

The 10 × 8 box of conftest with an OG of the same walls (2.5 high), slabs of 0.2 concrete and 0.01 plaster, floors of 0.02 tiles and 0.13 screed. Synthetic tables: γ gips 10, mw 8, putz 15, stb 25, fliese 20, estrich 20, ks 15 kN/m³; q_k 1.5 kN/m² for living; partitions up to 4 kN/m 0.7, up to 6 kN/m 1.1 kN/m²; γ_G 1.3, γ_Q 1.4.

| Test | Case | Expected |
|---|---|---|
| `test_checks` | an OG wall marked load-bearing over the open EG; the EG walls not load-bearing | `W-STRUCT-001` on it; `W-STRUCT-002` on sl2 and `W-STRUCT-001` on the OG walls |
| `test_loads` | the box | sl2: G = 80 · 5.1 + 69.2244 · 3.0, Q = 69.2244 · 1.5; shares 24.09, 15.91, 24.09, 15.91 m² (45° split of the 9.4 × 7.4 field plus the cores); own weights 10 · 2.7 · 2.8 and 10 · 2.5 · 2.8 kN; w1 at its base its own, its share and w5; n_d and b with σ_R,d 150 |
| `test_partitions` | a partition of 1.925 kN/m² · 2.5 m = 4.8125 kN/m in the OG | 1.1 kN/m² on the OG's 68.2281 m² of rooms; with a table up to 4 kN/m: fails |
| `test_missing_data` | a material not in the table | stops and names it |
| `test_haus_mueller` | the prototype | no `W-STRUCT`; the footings carry every wall's own weight and every slab but the ground slab |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

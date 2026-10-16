# Validation report: `loads` (Lastannahmen und Lastabtrag)

| | |
|---|---|
| Calculator | `loads` 0.3.0, kind `norm` |
| Standards | DIN EN 1991-1-1:2010-12 (actions), DIN EN 1991-1-3:2010-12 (snow), DIN EN 1991-1-4:2010-12 (wind), each with NA; DIN EN 1990:2010-12 with NA (combination) |
| Code | `src/uea/packs/struct/loads.py`, `actions.py`; the load path in `model.py`; beams on `frame.py` |
| Tests | `tests/test_struct.py` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

All values of the standards come from the office's tables. The soil's resistance, the snow load s_k and the wind pressure q_p are the planner's settings for the site. Every result names the edition of each table.

## What it computes

**For each slab:**

- its area and its own weight per m²;
- the floor build-ups and imposed loads of the rooms on it;
- the partition surcharge;
- G and Q;
- the area each support under it carries (load-bearing walls and beams).

**For each roof:** per plane, its pitch, its plan area and its loads on plan. Per eaves line:

- G, S and W, and the walls under it;
- the uplift.

**For each point or line load:** the support it goes to.

**For each beam:** its reactions on its walls and columns, per action.

**For each column:** what its beams put on it, its own weight, and what it stands on (a support of the slab under it, or its pad footing).

**For each load-bearing wall:**

- its own weight;
- what arrives at its top;
- G, Q, S and W at its base.

**For each wall of the lowest storey:**

- n_k and n_d on its footing;
- with `soil=`, the footing's width.

The record is `out/loads.json`, the report `out/loads.md`.

## Formulas as implemented

- **Build-up:** g = Σ t_i · γ_i (kN/m²).
- **Slab:**
  - G = A_net · g_slab + Σ_rooms A_fin · g_floor.
  - Q = Σ_rooms A_fin · (q_k(use) + q_partition).
- **Partition** (a wall that is not load-bearing, above the lowest storey):
  - w = g_wall · A_net,elevation / L.
  - Up to the last row of `partition-load`: the first q_k with w ≤ upto. The largest on a storey applies to its slab.
  - Heavier: a line load w along its axis.
- **Shares:**
  - The slab is cut into 5 cm cells. Each cell goes to the nearest support: a wall's core or a beam's axis, ties to the first.
  - A support takes G and Q in proportion to its cells.
  - A beam takes its share as a uniform load over its length.
- **Roof plane** z = a·x + b·y + c:
  - Slope k = √(a² + b²), pitch α = atan k.
  - On plan: g = g_roof · √(1 + k²), s = μ1(α) · s_k, w = c_pe,pressure(α) · q_p, w⁻ = c_pe,suction(α) · q_p. μ1 and c_pe are interpolated linearly between the rows of the tables.
  - The plane falls to the eaves on its low side and carries the cells of the roof's outline, with its overhangs, where it is the lowest plane.
- **Eaves line:**
  - It rests on the load-bearing walls running along it whose cores lie within 0.6 m inside it: on the roof's storey, or else on the storey below.
  - Each wall's share is the length of its core along the line.
  - Uplift: n = (γ_G,inf · G + γ_Q · W⁻) / L.
- **Point and line loads:** a line is split into points 5 cm apart. Each point goes to the nearest support of its slab; on a beam it is a point load at its projection.
- **Beam:** a continuous beam from a to b on pinned supports at the middle of each bearing on a wall and at each column on its axis, solved per action. The reactions do not depend on EI for a beam of one section.
- **Column:** G_own = g · h, h from the storey's SSL to the underside of the slab above (`column-section`); its base to the nearest support of the slab it stands on, as a point load, or on the lowest storey to its pad footing.
- **Wall:** G_own = g_wall · A_net,elevation.
- **Takedown,** from the top storey down:
  - G_base = G_own + what arrives at the top.
  - A wall passes its base to what it stands on, in proportion to the overlap. On a beam this is the length of its core over the beam's free span, as a uniform load.
  - The beams of a storey are solved after its walls.
- **Combination:** E_d = γ_G · G + γ_Q · max over the leading action (Q_1 + Σ ψ0,i · Q_i), over the actions that push down.
- **Footing:**
  - n_k = (G + Q + S + W) / L.
  - n_d = E_d / L.
  - b ≥ n_d / σ_R,d.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Layers, areas, heights, openings, the roof's planes | the model (`arch.uea`), derived |
| Which walls carry | the architect's `lb` flag; the load path from the geometry |
| Beams, point and line loads | `struct.uea` |
| γ by material | table `unit-weight` |
| q_k by room use | table `imposed-load` |
| Partition surcharge | table `partition-load` |
| μ1 by pitch | table `snow-shape` |
| c_pe by pitch | table `wind-roof` (the office's choice of zone) |
| γ_G, γ_Q, γ_G,inf | table `struct-factors` |
| ψ0 | table `struct-psi` |
| A beam's weight | table `beam-section` |
| A column's weight | table `column-section` |
| s_k, q_p | settings `sk=`, `qp=`, from the snow load and wind zones of the site |
| σ_R,d | setting `soil=`, from the geotechnical report |

## Deviations and not implemented

- **Wind:** here only as the roof's load on the walls; the horizontal wind and the bracing are `struct`'s (`struct.md`).
- **Snow:** no drifts or accumulations; each plane is fully loaded, with no asymmetric case.
- **The roof:** a couple roof bearing at its eaves. A purlin roof needs its purlins as beams.
- **Uniform loads:**
  - A slab's load per support is uniform over the support's length. There is no continuity, no fixity, and no concentrated loads at lintel ends.
  - A slab's share on a beam is uniform along it.
- **The cells:** shares and roof areas on a 5 cm grid, within about 0.2 m² of the exact areas in the tests.

## Assumptions to check when signing

- Which walls are load-bearing (the architect's flag), and that the slabs span as the nearest-support partition assumes.
- That the roof bears at its eaves, and the walls the eaves rest on.
- The unit weights of the products used, including the rafter layer, smeared.
- The imposed loads by use, and whether the Spitzboden's use is right.
- s_k, q_p and the zone the office took the c_pe of.
- The soil's design resistance.

## Test cases

**The test house:**

- The 10 × 8 box of conftest with an OG of the same walls (2.5 high).
- Slabs of 0.2 concrete and 0.01 plaster; floors of 0.02 tiles and 0.13 screed.

**Synthetic tables:**

- γ: gips 10, mw 8, putz 15, stb 25, fliese 20, estrich 20, ks 15, ziegel 20, sparren 2 kN/m³.
- q_k: 1.5 kN/m² for living.
- Partitions: up to 4 kN/m 0.7, up to 6 kN/m 1.1 kN/m².
- Factors: γ_G 1.3, γ_Q 1.4, γ_G,inf 0.9.
- ψ0: imposed 0.65, snow 0.45, wind 0.55.
- μ1: 0.7 up to 30°.
- c_pe at 30°: 0.4 pressure, −0.4 suction.

| Test | Case | Expected |
|---|---|---|
| `test_checks` | an OG wall marked load-bearing over the open EG; the EG walls not load-bearing | `W-STRUCT-001` on it; `W-STRUCT-002` on sl2 and `W-STRUCT-001` on the OG walls |
| `test_loads` | the box | sl2: G = 80 · 5.1 + 69.2244 · 3.0, Q = 69.2244 · 1.5; shares 24.09, 15.91, 24.09, 15.91 m²; own weights 10 · 2.7 · 2.8 and 10 · 2.5 · 2.8 kN; w1 at its base its own, its share and w5; n_d and b with σ_R,d 150 |
| `test_partitions` | a partition of 1.925 kN/m² · 2.5 m = 4.8125 kN/m in the OG | 1.1 kN/m² on the OG's 68.2281 m² of rooms; with a table up to 4 kN/m, a line load of 4.8125 · 7.4 kN, half to w1 and half to w3 |
| `test_roof` | a gable roof of 30° on the OG, 1.4 kN/m² along the slope, eaves 0.5 | per plane 45 m² on plan: G = 45 · 1.4 / cos 30°, S = 45 · 0.595, W = 45 · 0.2, suction −9 kN; eaves s on w5, n on w7; uplift (0.9 · G − 1.4 · 9) / 10; w1's n_d with the leading action |
| `test_combination` | G 10, Q 4, S 2, W 1 | 1.3 · 10 + 1.4 · (4 + 0.45 · 2 + 0.55 · 1); with uplift only Q counts |
| `test_point_load` | 3 kN + 1 kN at 0.2 m from w2 | w2's top grows by exactly that |
| `test_beam` | an OG wall on a beam from w1 to w3 | the reactions equal, summing to the beam's weight, its share of sl2 and the wall |
| `test_missing_data` | a material not in the table | stops and names it |
| `test_haus_mueller` | the prototype with s_k 0.85, q_p 0.5 | no `W-STRUCT`; the eaves on w8 and w10; the footings carry every wall's own weight, every slab but the ground slab, and the roof |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.2.0 | Roofs with snow and wind on their eaves, beams, point and line loads, heavy partitions as line loads, combination with ψ0 |
| 0.3.0 | Columns under beams, with their pad footings (`test_columns` in `tests/test_struct.py`, decision 0044) |

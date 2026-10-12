# Validation report: `struct` (Statische Berechnung)

| | |
|---|---|
| Calculator | `struct` 0.1.0, kind `norm` |
| Standards | DIN EN 1996-3:2010-12 with NA (masonry, simplified method); DIN EN 1992-1-1:2011-01 with NA (bending of slabs); DIN EN 1993-1-1 and DIN EN 1995-1-1 with NA (beams, by the office's strengths); the loads of `loads` 0.2.0 (`loads.md`) |
| Code | `src/uea/packs/struct/design.py`, `plate.py`, `frame.py`, `positions.py`; the Positionsplan `src/uea/export/positionsplan.py` |
| Solver | PyNite (MIT), optional extra `uea[struct]`; the version is in the report |
| Tests | `tests/test_struct.py` |
| Review | **Not yet reviewed** by a licensed person (`docs/decisions/0040-structure.md`). The standards' worked examples have **not** been run. |

## What it computes

Every position of the Positionsplan, numbered by storey from the top:

- roofs;
- the slab over each storey and its beams;
- the load-bearing walls;
- the lintels over their openings;
- the strip footings.

For each it gives the design and its utilisation. The holes in load-bearing members are listed with how they are taken. The record is `out/struct.json`, the report `out/struct.md`, and `uea export pdf struct` sets it on A4 with an empty signature block.

## Formulas as implemented

**Slab** (a plate):

- **Elements and grid:** rectangular plate elements, at most 0.5 m, on a grid through the axes of the supports and the corners of the slab, its voids and its holes. Lines closer than 0.1 m merge, keeping the support's axis.
- **Plate edge:** the plate is the slab without the outer half of its exterior walls.
- **Supports:** a node on a support's axis is held vertically.
- **Loads:**
  - inside a room: γ_G·(g_slab + g_floor) + γ_Q·(q_k + q_partition);
  - elsewhere: γ_G·g_slab;
  - point loads E_d at the nearest node.
- **Material:** E = E_cm, ν = 0.2 (DIN EN 1992-1-1, 3.1.3(4)).
- **Design moments** at each element's middle:
  - bottom m_x + |m_xy| and m_y + |m_xy|;
  - top −m_x + |m_xy| and −m_y + |m_xy|.
- **Per direction and face**, with d = h − d1, f_cd = α_cc·f_ck/γ_C and f_yd = f_yk/γ_S:
  - μ = m/(d²·f_cd);
  - ω = 1 − √(1 − 2μ);
  - a_s = ω·d·f_cd/f_yd;
  - x/d = ω/λ, with λ = 0.8 (DIN EN 1992-1-1, 3.1.7(3), f_ck ≤ 50), ≤ the office's xi.
  - 2μ ≥ 1 cannot be designed.

**Beam:**

- A continuous beam on PyNite with EI = E·I.
- Combinations: γ_G·G + γ_Q·(Q_lead + Σ ψ0·Q_i) for each leading action; the characteristic sum for the deflection.
- Resistance: M_Rd = W·k_mod·f_k/γ_M, V_Rd = A_v·k_mod·f_v,k/γ_M.
- Deflection: w ≤ L/n, with L the longest span, or twice an overhang.

**Wall** (DIN EN 1996-3, 4.2.2):

- f_d = ζ·f_k/γ_M.
- h is the clear height (the wall from its bottom to its top).
- h_ef = ρ2·h if the slab above rests on it, else h.
- Φ1 = 0.85 − 0.0011·(h_ef/t)².
- An exterior wall carrying the end of the slab above: Φ2 from `masonry-end` by l_f, and Φ = min(Φ1, Φ2).
- l_f, on each side the slab lies:
  - the span across to the next support;
  - the span along the wall in the middle of that field;
  - the shorter of the two, and the longer over the sides.
- n_Ed = E_d(base) / (L − Σ openings); n_Rd = Φ·f_d·t.
- Conditions of the simplified method:
  - clear height, l_f, the largest q_k on the slab, and the building's height from the terrain to the ridge;
  - each against `struct-limits`.

**Lintel:**

- q_d = E_d(top/L + g_wall·h_above), where h_above is the wall over the opening, up to its top at the opening's middle.
- In table order, the first type for a wall of that core thickness whose smallest span ≥ the clear width has q_Rd ≥ q_d.
- Round holes (core drillings) have none.

**Footing:** n_d = E_d(base)/L, and b ≥ n_d/σ_R,d.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Everything of `loads` | `loads.md` |
| f_ck, E_cm by the slab's core material | table `concrete` |
| f_k by the wall's core material | table `masonry` |
| Φ2 by span | table `masonry-end` |
| γ_M, ζ, ρ2, γ_C, α_cc, γ_S, f_yk, d1 | table `struct-factors` |
| The limits of the methods, the deflection limit | table `struct-limits` |
| Lintels and their loads | table `lintel` (the manufacturer's approval) |
| Sections, strengths | tables `beam-section`, `beam-material` |

## Deviations and not implemented

- **Slabs:**
  - one load case (no pattern loading);
  - the moment at the elements' middles, not the peak over a support's axis;
  - one d for both directions;
  - no minimum or robustness reinforcement, shear, punching, deflection or crack check;
  - beams as rigid supports;
  - the ground slab not designed.
- **Walls:**
  - the load spread over the masonry between the openings;
  - no partial-area compression under bearings;
  - no Φ3 under the top slab;
  - no walls with earth pressure;
  - no bracing.
- **Lintels:** no arching; the wall's load at its top uniform over its length.
- **Roof:** the timber is not designed.
- **Footings:** only the width from σ_R,d; no bearing capacity, settlement, concrete design or frost depth.

## Assumptions to check when signing

- **The plate:** the model, its supports, and the plate ending at the exterior walls' axes.
- **The sections:** d1, the reinforcement layers, the concrete class.
- **The masonry:** ρ2, Φ2 for the project's masonry, and the conditions of the simplified method.
- **The lintels:** the lintel table, how the lintels sit in the wall, and the loads over them.
- **The holes:** each hole the report lists.

## Test cases

**The test house:**

- The 10 × 8 box of conftest (walls 0.3 mw, f_k 4) with the OG on top.
- Slab sl2 of 0.2 concrete.

**Synthetic tables** (as in `loads.md`, plus):

- Masonry: ζ 0.8, γ_M 1.6, ρ2 0.7; Φ2 0.75 up to 5 m and 0.45 up to 8 m.
- Concrete: f_ck 28, E_cm 30000, γ_C 1.6, α_cc 0.8.
- Reinforcement: γ_S 1.2, f_yk 480, d1 0.03.
- Limits: xi 0.4, span 8, clear height 2.8, q_k 4.5, building height 18, deflection L/250.
- Steel: f_k 230, f_v,k 130, E 200000, γ_M 1.1; section S-160 with W 300 cm³, I 2400 cm⁴, A_v 18 cm², g 0.42 kN/m.

| Test | Case | Expected |
|---|---|---|
| `test_plate` | sl2 on w1..w4 under 12 kN/m² | m_y within 1 % of Navier's series for the 9.7 × 7.7 rectangle of the axes; m_x + \|m_xy\| between m_x and 1.1 · m_x |
| `test_bending_and_slenderness` | m 20 kNm/m, d 0.17, f_cd 14, f_yd 400 N/mm²; h_ef/t 6.3 | μ 0.049432, x/d 0.050718/0.8, a_s 3.018 cm²/m; 300 kNm/m not designable; Φ1 0.806341 |
| `test_beam_solver` | q 10 over 4 m; two spans of 4 m | M 20, V 20, R 20, w = 5qL⁴/384EI; M_support 20, R_mid 50, M_field 11.25 |
| `test_beam` | an OG wall on S-160 from w1 to w3 | M_Ed within 2 % of q_d · 7.55² / 8; M_Rd = 300 · 230 / 1.1 = 62.7 kNm |
| `test_walls_and_lintels` | the box with a window 1.26 × 1.26 in w1 | w2: Φ1 0.806, l_f = min(9.7, 7.7) = 7.7, Φ2 0.45, n_Rd = 0.45 · 2000 · 0.3 = 270 kN/m, n_Ed = E_d / 7.4; w1 over 10 − 1.26 m; the lintel over f1: q_d = 1.3 · (G_top/10 + 2.8 · 0.29) + 1.4 · Q_top/10, L-B |
| `test_positions` | the box | 1.01 to 1.04 the OG walls, 2.01 sl2 on the EG's plan, 2.02 to 2.05 the EG walls, 3.01 to 3.04 the footings |
| `test_more_checks` | a beam on one wall; a hole over w4 | `W-STRUCT-003`, `W-STRUCT-004` |
| `test_haus_mueller` | the prototype with s_k 0.85, q_p 0.5, σ_R,d 200 | every position ok: 2 slabs, 20 lintels, 5 footings; the holes ho1 to ho6 listed |
| `test_on_the_command_line` | the box through the CLI | `uea calc struct`, the PDF, the Positionsplan of the EG with 2.01 and 2.02 · 3.01 |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

# Validation report: `struct` (Statische Berechnung)

| | |
|---|---|
| Calculator | `struct` 0.2.0, kind `norm` |
| Standards | DIN EN 1996-3:2010-12 with NA (masonry, simplified method); DIN EN 1996-1-1 with NA (shear walls); DIN EN 1992-1-1:2011-01 with NA (slabs: bending, shear, minimum reinforcement, slenderness); DIN EN 1993-1-1 with NA (beams, columns); DIN EN 1995-1-1 with NA (beams, rafters, collar beams); DIN EN 1991-1-4 with NA (wind on the walls); the loads of `loads` 0.3.0 (`loads.md`) |
| Code | `src/uea/packs/struct/design.py`, `plate.py`, `frame.py`, `bracing.py`, `positions.py`; the Positionsplan `src/uea/export/positionsplan.py` |
| Solver | PyNite (MIT), optional extra `uea[struct]`; the version is in the report |
| Tests | `tests/test_struct.py` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

## What it computes

Every position of the Positionsplan, numbered by storey from the top:

- roofs and their rafters;
- the slab over each storey and its beams;
- the load-bearing walls;
- the lintels over their openings;
- the columns;
- the bracing of each storey against wind;
- the strip footings and the columns' pad footings.

For each it gives the design and its utilisation. The holes in load-bearing members are listed with how they are taken. The record is `out/struct.json`, the report `out/struct.md`, and `uea export pdf struct` sets it on A4 with an empty signature block.

## Formulas as implemented

**Slab** (a plate):

- **Elements and grid:** rectangular plate elements, at most 0.5 m, on a grid through the axes of the supports and the corners of the slab, its voids and its holes. Lines closer than 0.1 m merge, keeping the support's axis.
- **Plate edge:** the plate is the slab without the outer half of its exterior walls.
- **Supports:** a node on a support's axis is held vertically.
- **Loads,** in three cases: the imposed load on every room, and on each of two groups of alternate rooms (neighbours across a wall in different groups, as far as two groups allow); each design value the largest of the cases:
  - inside a loaded room: γ_G·(g_slab + g_floor) + γ_Q·(q_k + q_partition); in an unloaded one γ_G·(g_slab + g_floor);
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
- **Minimum reinforcement** (9.3.1.1 with 9.2.1.1, 9.1N): a_s,min = max(rho-min-ft · f_ctm/f_yk, rho-min) · b · d with f_ctm = 0.30 · f_ck^(2/3) (Tabelle 3.1, f_ck ≤ 50); the bottom reinforcement is at least a_s,min.
- **Shear without shear reinforcement** (6.2.2, 6.2a/b): v_Ed is the largest line reaction of a support (the nodal reactions over the length each node stands for), more than 0.75 m from the corners of the supports; v_Rd,c = max(C_Rd,c · k · (100 ρ_l f_ck)^(1/3), vmin · k^1.5 · √f_ck) · d, k = min(1 + √(200/d), 2), ρ_l of a_s,min.
- **Slenderness** instead of a deflection calculation (7.4.2 with NA): l/d ≤ min(ld, ld-span / l), l the largest of the fields' shorter spans between the support axes.

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

**Rafters** (`rafter` in `struct.uea`, a gable roof):

- A pair of rafters as a plane frame on PyNite: from the eaves' tip over the bearing on the eaves wall's axis to the ridge, a hinge at the ridge, the feet pinned and held horizontally; with `collar=` a collar beam pinned to both rafters at that height.
- Loads per rafter, spacing e: g of the roof's build-up along the slope, s = μ1 · s_k on plan, w = c_pe · q_p normal to the planes (pressure on one, suction on the other). Combinations γ_G·G + γ_Q·(Q_lead + ψ0·Q_other) with snow or wind leading; characteristic for the deflection.
- Per group of bars (overhang, rafter, rafter below and above the collar, collar beam): σ_c/(k_c · f_c,0,d) + σ_m/f_m,d ≤ 1 and σ_t/f_t,0,d + σ_m/f_m,d ≤ 1 (6.2.3, 6.2.4, 6.3.2), k_c with the bar's length and i = h/√12 (the collar: the smaller side), λ_rel = λ/π · √(f_c,0,k/E_0,05), k = 0.5 (1 + β_c (λ_rel − 0.3) + λ_rel²); 1.5 · V/(k_cr · b · h) ≤ f_v,d; the relative deflection ≤ l/n (the overhang 2l/n); f_d = k_mod · f_k/γ_M.
- The horizontal thrust at the feet is reported per metre of eaves.

**Column** (`column` in `struct.uea`): pinned at both ends over its length from the storey's SSL to the underside of the slab above; λ̄ = l/(i π) · √(f_k/E), Φ = 0.5 (1 + α (λ̄ − 0.2) + λ̄²), χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1, N_Ed ≤ χ · A · k_mod · f_k/γ_M (DIN EN 1993-1-1, 6.3.1.2).

**Bracing** (`bracing.py`), per storey and direction of the wind:

- Bands of the facade per storey, from the terrain or the storey's SSL to the next SSL, the top one to the ridge or the highest wall top; F = q_p · (c_pe,D − c_pe,E) · width · height with c_pe by h/d from `wind-wall`, at the top of the band.
- The storey takes V = Σ F above its base and M = Σ F · (z − z_base).
- The piers of its load-bearing walls along the wind (the stretches between openings) share V and M by t · l³.
- Per pier: N_d = γ_G,inf · G (its share of the wall's permanent load), e = M/N, l_c = min(l, 3 (l/2 − e)) ≥ l/2; v_Ed = V/(t · l_c) ≤ f_vd = min(f_vk0 + 0.4 σ_d, f_vlt)/γ_M with σ_d = N/(t · l_c).
- A storey under a roof with no wall in one direction passes that wind through the roof's bracing to the storey below, where it is counted; the bracing of the roof plane is not proved.

**Footing:** n_d = E_d(base)/L, and b ≥ n_d/σ_R,d. A column's pad: a ≥ √(N_d/σ_R,d).

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Everything of `loads` | `loads.md` |
| f_ck, E_cm by the slab's core material | table `concrete` |
| f_k by the wall's core material | table `masonry` |
| Φ2 by span | table `masonry-end` |
| γ_M, ζ, ρ2, γ_C, α_cc, γ_S, f_yk, d1 | table `struct-factors` |
| The limits of the methods, the deflection limit, the slenderness of slabs | table `struct-limits` |
| C_Rd,c, vmin, the minimum reinforcement's factors | table `struct-factors` |
| Strength classes of timber, k_mod, γ_M, k_cr, β_c | table `timber` |
| Column sections, their buckling curve's α | table `column-section` |
| c_pe of the walls by h/d | table `wind-wall` |
| f_vk0, f_vlt of masonry | table `masonry-shear` |
| Lintels and their loads | table `lintel` (the manufacturer's approval) |
| Sections, strengths | tables `beam-section`, `beam-material` |

## Deviations and not implemented

- **Slabs:**
  - the moment at the elements' middles, not the peak over a support's axis;
  - one d for both directions;
  - the shear from the support reactions (an interior support's from both sides, on the safe side), away from the corners; ρ_l of the minimum reinforcement;
  - no robustness reinforcement, crack width or deflection calculation beyond the slenderness; no punching (the slabs rest on lines);
  - beams as rigid supports;
  - the ground slab not designed.
- **Walls:**
  - the load spread over the masonry between the openings;
  - no partial-area compression under bearings;
  - no Φ3 under the top slab;
  - no walls with earth pressure.
- **Bracing:** the slabs as rigid diaphragms without torsion of the plan; no imperfections; the bands' forces at their tops; the gable as a full rectangle (on the safe side); the roof plane's bracing not proved.
- **Lintels:** no arching; the wall's load at its top uniform over its length.
- **Rafters:** gable roofs only; one pair stands for all; no asymmetric snow; the connections (ridge, collar, feet) and the anchoring not designed.
- **Columns:** steel by the buckling curve of the section; no bending, no columns carrying slabs directly.
- **Footings:** only the width from σ_R,d; no bearing capacity, settlement, concrete design or frost depth.

## Assumptions to check when signing

- **The plate:** the model, its supports, and the plate ending at the exterior walls' axes.
- **The sections:** d1, the reinforcement layers, the concrete class.
- **The masonry:** ρ2, Φ2 for the project's masonry, and the conditions of the simplified method.
- **The lintels:** the lintel table, how the lintels sit in the wall, and the loads over them.
- **The holes:** each hole the report lists.
- **The roof:** the rafters' section and spacing, the collar's height, and how the feet's thrust is taken.
- **The bracing:** which walls brace, and that the slabs act as diaphragms.

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
| `test_slab_checks` | sl2 of the box | a_s,min = max(0.25 · 0.3 · 28^(2/3)/480, 0.0012) · 0.17 = 2.449 cm²/m; v_Rd,c = max(0.12 · 2 · (100 ρ_l · 28)^(1/3), 0.04 · 2^1.5 · √28) · 0.17; l/d = 7.7/0.17 against min(33, 145/7.7): too slender |
| `test_plate` (shear) | sl2 under 12 kN/m² | the line reaction in the middle of the long edge within 1 % of Kirchhoff's effective shear by the series |
| `test_load_patterns` | four rooms in a square | r1 and r4 against r2 and r3 |
| `test_rafter_frames` | a couple roof 8 m wide at 35° under 2 kN/m along the slope | M = w (L/2)²/8, H = w L²/(8f), N = H cos α + V sin α exactly; with a collar at half the rise the rafter's moment within 10 % under w (L/4)²/8, the collar in compression |
| `test_rafters` | the box with a gable roof, rafters C24 8/20 at 0.8 m with and without a collar | positions 1.02 and 1.03, ok; k_c by the formula; a hip roof's rafters not proved |
| `test_columns` | a beam across the box on w4, a column C-140 and w2 | the column carries the beam's reaction and 2.7 m · 0.3 kN/m; χ by α 0.49; N_Ed against χ · A · 230/1.1; the pad a = √(N_d/200) |
| `test_column_checks` | a column under no beam; a beam from a wall to a column | `W-STRUCT-005`; no `W-STRUCT-003` |
| `test_bracing` | the box with a door in w2, q_p 0.5 | the bands 0.5 · 1.3 · 8 · 2.75 and · 2.5; V and M of the EG; w1 half of it, N_d = 0.9 G, l_c, f_vd and v_Ed by hand; w2's two piers shared by t · l³ |
| `test_more_checks` | a beam on one wall; a hole over w4 | `W-STRUCT-003`, `W-STRUCT-004` |
| `test_haus_mueller` | the prototype with s_k 0.85, q_p 0.5, σ_R,d 200 | every position ok: 2 slabs, 20 lintels, 5 footings; the holes ho1 to ho6 listed |
| `test_on_the_command_line` | the box through the CLI | `uea calc struct`, the PDF, the Positionsplan of the EG with 2.01 and 2.02 · 3.01 |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.2.0 | Slab load patterns, shear, minimum reinforcement and slenderness; rafters and collar beams; columns and pad footings; bracing against wind (decision 0044) |

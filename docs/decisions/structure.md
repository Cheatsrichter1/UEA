# Structure

The `struct` pack: the load path, the loads and the Statische Berechnung. UEA computes; the Tragwerksplaner decides and signs, and the Prüfingenieur checks. Both records were reviewed together by a licensed engineer outside this repository. Index in [README.md](README.md).

## 0040 Structure

Built in four slices: 8a the load path and `uea calc loads`; 8b roof loads, beams and point and line loads, combinations; 8c `uea calc struct` on the solver PyNite; 8d the Positionsplan and the Statische Berechnung as a PDF to sign.

- **Load path** (`packs/struct/model.py`): a slab rests on the load-bearing walls below that its outline covers and on beams under it; a load-bearing wall on the walls below whose cores its core overlaps and on beams in its core; a beam on the walls below it crosses; the lowest storey on the foundation.
- **`struct.uea`** holds what the architecture does not: `beam bm1 OG S-160 a=… b=…` (an Unterzug under a storey's slab) and `load lo1 OG g= q= at=…` (a point load, or with `a=`/`b=` a line load). Sections and strengths are rows of office tables (`beam-section`, `beam-material`).
- **Checks** without tables: `W-STRUCT-001` (wall on nothing), `002` (slab on no wall), `003` (beam on fewer than two walls), `004` (a slab hole over its only bearing; the fix asks for a trimmer).
- **`uea calc loads [soil= sk= qp=]`:** each point of a slab to its nearest support on a 5 cm grid. The roof bears on its eaves lines as a couple roof: g = Σ t·γ / cos α, s = μ1(α)·s_k, w = c_pe(α)·q_p (tables `snow-shape`, `wind-roof`; s_k and q_p are the planner's), with the uplift for anchoring. Point loads and heavy partitions to the nearest support; beam reactions from the solver. Combination per DIN EN 1990 6.10 with ψ0 from `struct-psi`.
- **`uea calc struct`** proves every position:
  - **Slab:** a plate on PyNite, mesh ≤ 0.5 m through every support axis and corner, supports along wall and beam axes, ending at exterior wall axes (safe side). Wood-Armer moments m ± |m_xy|; a_s with the rectangular stress block and x/d against the office's limit.
  - **Beam:** a continuous beam; M_Ed ≤ W k_mod f_k / γ_M, V_Ed ≤ A_v k_mod f_v,k / γ_M, deflection ≤ L/n.
  - **Masonry wall:** DIN EN 1996-3 4.2.2, N_Ed ≤ Φ f_d t with Φ1 = 0.85 − 0.0011 (h_ef/t)², Φ2 at end supports from `masonry-end`, the method's limits from `struct-limits`.
  - **Lintel** over every rectangular opening in a load-bearing wall: the wall's load plus the masonry over it, no arching, the first fitting row of the maker's table `lintel`.
  - **Strip footing:** b ≥ n_d / σ_R,d. **Roof:** loads and uplift on the eaves.
  - **Holes** in load-bearing members are listed with how the calculation takes them. The engineer approves them by signing; UEA approves nothing.
- **Positions** are derived, grouped by storey from the top (roofs, the slab above and its beams, walls and lintels), the footings last; numbers read `2.07`. `uea export pdf struct:<level>` is the Positionsplan (walls blue, lintels red, beams dash-dotted, 1:50); `uea export pdf struct` the Statische Berechnung on A4 with an empty signature block.
- **PyNite** (MIT) is an optional extra (`uea[struct]`); within 1 % of Navier for a plate and exact for continuous beams. anaStruct and Code_Aster are GPL.
- **Office tables:** `unit-weight`, `imposed-load`, `partition-load`, `struct-factors`, `struct-psi`, `snow-shape`, `wind-roof`, `struct-limits`, `masonry`, `masonry-end`, `concrete`, `lintel`, `beam-section`, `beam-material`.

Why: a couple roof needs nothing the architecture lacks (a purlin is a beam the agent writes); Czerny's tables are licensed and only cover rectangles; a published solver is easier to trust than our own element; arching over openings is the engineer's judgement; a waiver for a hole would look like an approval nobody gave.

## 0044 Structure completion

- **Slabs:** pattern loading (imposed load on all rooms and on two groups of alternate rooms); minimum reinforcement (DIN EN 1992-1-1 9.3.1.1); shear without shear reinforcement (6.2.2) from the supports' line reactions away from corners, since plate-element shear at line supports is unreliable; slenderness l/d instead of a deflection calculation (7.4.2). Punching does not arise on line supports.
- **Rafters:** `rafter sp1 rf1 C24 b= h= e= [collar= cb= ch=]`: a pair of a gable roof as a plane frame from the eaves tip over the wall to a ridge hinge, optionally with a pinned collar; roof loads with snow or wind leading; proved per DIN EN 1995-1-1 with the office's `timber`; the thrust at the feet is reported. Other roof shapes are listed as not proved.
- **Columns:** `column co1 EG HEB-140 at=` under a beam; its load goes to the slab below as a point load or to its own pad (a ≥ √(N_d / σ_R,d)); flexural buckling per DIN EN 1993-1-1 6.3.1.2 with α from `column-section`. `W-STRUCT-005`: a column under no beam.
- **Bracing** (`bracing.py`): wind on the facades per storey from c_pe of zones D and E (`wind-wall`), shared among the piers along the wind by t · l³; each pier checked for the open joint and shear (DIN EN 1996-1-1 6.2, 3.6.2; `masonry-shear`).

Still not proved: the roof's connections and anchoring, the roof plane's bracing, torsion, robustness reinforcement and crack widths, timber columns, and the geotechnical checks of the footings.

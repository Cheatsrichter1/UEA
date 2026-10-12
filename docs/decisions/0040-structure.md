# 0040: Structure, phase 8

Status: Proposed; slices 8a to 8d built, none reviewed (for the user's veto, and for the review of the licensed engineer the phase needs)
Date: 2026-10-11, slices 8b to 8d 2026-10-12

## Context

Phase 8 (`ROADMAP.md`) is the structure: load-bearing elements, loads, frame analysis on an open-source solver. Its "done when" is that a licensed engineer reviews the validation. The architecture carries most of what the structure starts from: which walls are load-bearing (`lb`), their build-ups, the slabs and their build-ups, the floor build-ups and uses of the rooms, the roof, the openings and holes. The Haftung for the structure lies with the Tragwerksplaner and, for the check, the Prüfingenieur (`VISION.md`). UEA computes, and the engineer decides and signs, as with every `norm` calculator.

The plan was to build slice 8a and wait for the engineer's review before the next. The engineer is away; on 2026-10-12 the user decided to build 8b to 8d now. All four slices are unreviewed, and the review covers them together (`docs/validation/loads.md`, `docs/validation/struct.md`).

## Decision

**The phase in four slices, all built:**

| Slice | Content |
|---|---|
| 8a | The load path from the architecture and its checks; `uea calc loads`: dead and imposed loads of the slabs, the walls' own weight, light partitions, the takedown to the foundation, the line loads on the strip footings |
| 8b | The roof's own weight, snow and wind on the walls under its eaves; beams and point and line loads as elements of `struct.uea`; heavy partitions as line loads; combinations with ψ0 |
| 8c | `uea calc struct`: slabs as plates and beams as continuous beams on the solver PyNite, masonry walls (DIN EN 1996-3, simplified), lintels from the manufacturer's table, strip footings |
| 8d | The Positionsplan per storey (`uea export pdf struct:<level>`) and the Statische Berechnung as one A4 PDF to sign (`uea export pdf struct`), with the holes in load-bearing members listed for the engineer |

**The load path** (`packs/struct/model.py`). A slab rests on the load-bearing walls of the storey below that its outline covers and on the beams under it. A load-bearing wall stands on the load-bearing walls of the storey below whose cores its core overlaps, and on the beams of its storey that run inside its core between their bearings. A beam rests on the load-bearing walls of the storey below that it crosses. The lowest storey stands on the foundation, its slab on the ground.

**`struct.uea`** (`packs/struct/kinds.py`) holds what the architecture does not give:

- `beam bm1 OG S-160 a=… b=…`: a beam (Unterzug) under the slab of a storey. It carries that slab and the walls of the storey that stand on it.
- `load lo1 OG g= q= at=…`: a point load, or with `a=`/`b=` a line load, on the slab of a storey. A buffer tank or a heavy partition the agent writes is an example.
- Sections and strengths are rows of the office's tables (`beam-section`, `beam-material`), not types in the model, because their values are catalogue and norm data.

**Checks** need no tables:

- `W-STRUCT-001`: a load-bearing wall on nothing below.
- `W-STRUCT-002`: a slab on no wall.
- `W-STRUCT-003`: a beam on fewer than two walls.
- `W-STRUCT-004`: a hole in a slab over the wall that carries it, where the slab has no bearing; the fix asks for a trimmer (Auswechslung).

**`uea calc loads [soil= sk= qp=]`** (version 0.2.0):

- **Slabs, shares, takedown:** as in 8a. Every point of a slab goes to its nearest support, a wall or a beam (the 45° rule in a rectangle), on a 5 cm grid.
- **The roof** rests on its eaves. Each roof plane bears on the eaves line it falls to, as a couple roof (Sparrendach) does.
  - On plan: g = Σ t·γ / cos α, s = μ1(α)·s_k and w = c_pe(α)·q_p, with μ1 and c_pe interpolated by pitch in the office's tables `snow-shape` and `wind-roof`.
  - s_k and q_p are the planner's settings for the site, like the soil's resistance.
  - An eaves line rests on the load-bearing walls along it, on the roof's storey or else on the storey below (under the slab's edge).
  - The uplift at the eaves, γ_G,inf·G + γ_Q·W_suction per metre, says where the rafters need anchoring.
- **Point and line loads**, and partitions heavier than the table, go to the nearest support of their slab. Before, a heavy partition failed the calculation.
- **A beam's reactions** come from the solver per action and pass to its walls.
- **Combination** per DIN EN 1990, 6.10: γ_G·G + γ_Q·(Q_k,1 + Σ ψ0,i·Q_k,i), with the leading action that gives the most. ψ0 comes from the office's `struct-psi`.

**`uea calc struct [soil= sk= qp=]`**, the Statische Berechnung (`packs/struct/design.py`). Every position (`positions.py`) is proved:

- **Slab:** a plate on PyNite (`plate.py`).
  - **Mesh:** rectangular elements of at most 0.5 m on a grid through every support axis and the corners of the slab, its voids and its holes.
  - **Supports:** vertical, along the axes of the walls and beams under it.
  - **Edges:** the plate ends at the axes of the exterior walls. The strip over their outer half stiffens the plate's edge in twisting and lowers the field moments by a few per cent, so leaving it off is on the safe side.
  - **Loads:** γ_G·(slab + the room's floor) + γ_Q·(the room's q + the partition surcharge), room by room, and the point loads.
  - **Design moments:** m ± |m_xy| (Wood-Armer) at the elements' middles, which stands for the moment at the face of a support.
  - **Reinforcement:** a_s per direction and face with the rectangular stress block: μ = m/(d²·f_cd), ω = 1 − √(1 − 2μ), a_s = ω·d·f_cd/f_yd, and x/d = ω/0.8 against the office's limit.
- **Beam:** a continuous beam on PyNite.
  - M_Ed ≤ W·k_mod·f_k/γ_M and V_Ed ≤ A_v·k_mod·f_v,k/γ_M.
  - The characteristic deflection ≤ L/n.
- **Masonry wall:** DIN EN 1996-3, 4.2.2, N_Ed ≤ Φ·f_d·t per metre of the wall without its openings.
  - f_d = ζ·f_k/γ_M.
  - Φ1 = 0.85 − 0.0011·(h_ef/t)², with h_ef = ρ2·h under a slab (ρ2 from the office) and h under a roof.
  - At the end support of a slab, Φ = min(Φ1, Φ2) with Φ2 by the span l_f from the office's `masonry-end`.
  - l_f is the shorter of the field's two spans.
  - The conditions of the simplified method (clear height, span, imposed load, building height) come from the office's `struct-limits`.
- **Lintel** over every door, window and rectangular hole in a load-bearing wall (a core drilling needs none).
  - The load is the wall's load at its top per metre plus the masonry over the opening, with no arching.
  - It is checked against the manufacturer's table `lintel`. The first type in the table's order that carries the load over the span in a wall of that thickness is taken.
- **Strip footing:** b ≥ n_d/σ_R,d.
- **Roof:** its loads on the eaves and the uplift.
- **Holes:** every hole in a load-bearing wall or a slab is listed with how the calculation takes it. A slab hole is left out of the plate model. A wall hole shortens the wall and gets a lintel unless it is round. Approving a hole is the engineer's, by signing the Statische Berechnung that lists it; UEA approves nothing.

**The positions** are derived from the model, so the Positionsplan and the calculation always agree. They are grouped by storey from the top. Group k holds:

- the roofs on the k-th storey from the top;
- the slab above it and its beams;
- its load-bearing walls and the lintels over their openings.

The last group holds the strip footings. Numbers read `2.07`. A position is drawn on the plan of the storey it is in, so a slab and its beams appear on the plan of the storey below them.

**The sheets.** `uea export pdf struct:<level>` is the Positionsplan. It shows the floor plan in grey, the load-bearing walls in blue, the lintels in red, the beams dash-dotted and the eaves dashed, each with its number, at 1:50. `uea export pdf struct` sets `out/struct.md` on A4. That file holds the position list, the loads, each position's proof, the holes, what is not proved, and an empty signature block. The bare name is the calculation, and the plans take a level, so the two never clash.

**The solver: PyNite** (MIT), an optional extra (`pip install 'uea[struct]'`) like IfcOpenShell.

- **Why PyNite:** it is in Python, has plates and frames, and its licence and its dependencies (NumPy, SciPy, Matplotlib, PrettyTable) are Apache-compatible.
- **Without it:** `struct` stops and names it.
- **Accuracy:** the tests hold it to closed-form results. A simply supported plate is within 1 % of Navier's series; continuous beams match qL²/8, 1.25 qL and 5qL⁴/384EI.
- **Speed:** each plate is held in its plane only as far as a rigid body needs, so the solver computes reactions only at the supports. Haus Müller's two slabs take about 6 s.
- **Not chosen:** anaStruct (GPL-3) and Code_Aster (GPL) could only run as a separate process; OpenSeesPy was not checked.

**Tables from the office**, none of the standards' values in the repository (`0008`):

- From 8a: `unit-weight`, `imposed-load`, `partition-load`, `struct-factors`. `struct-factors` now also has γ_G,inf, γ_M, ζ and ρ2 of masonry, γ_C and α_cc, and γ_S, f_yk and d1.
- New in 8b to 8d: `struct-psi`, `snow-shape`, `wind-roof`, `struct-limits`, `masonry`, `masonry-end`, `concrete`, `lintel`, `beam-section` and `beam-material`.

## Alternatives

- **Wait for the engineer before 8b.** That was the plan. The user chose to build on, so the review now covers four slices at once. The slices stay separate in the code and the reports, so the engineer can review them in order.
- **A purlin roof (Pfettendach) by default.** It needs purlins and their supports, which the model does not have. The couple roof needs nothing more than the architecture gives. A purlin is a beam the agent can write.
- **Elements for supports and loads in `struct.uea` for every member.** For the Einfamilienhaus the supports are the walls the architect marks, so only beams and loads are elements; the rest is derived.
- **The slab's moments from tables (Czerny and others).** Those tables are licensed and cover rectangles only. A plate model covers any outline, its holes and point loads, with no tables.
- **Our own plate element.** A small one would be faster, but a published, tested solver is easier to trust and to review.
- **The full plate including the strips over the exterior walls.** It gives smaller field moments, as computed above, so it is left off to stay on the safe side.
- **Arching over openings (the 60° triangle).** It lowers lintel loads. It needs the wall over the opening to be high and whole enough, a judgment left to the engineer; without it UEA is on the safe side.
- **Approving holes in the model, with a waiver by struct.** A waiver would look like an approval nobody gave. The engineer approves by signing the calculation that lists every hole.

## Consequences

- **Haus Müller**, with synthetic tables of our own (`tests/test_struct.py`):
  - The load path is clean.
  - The roof rests on the OG's eaves walls under the slab of the Spitzboden.
  - Every kilonewton of walls, slabs and roof reaches the footings.
  - Every position is proved: 2 slabs, 12 walls, 20 lintels and 5 footings.
  - The six holes of the services are listed.
- **Tested by hand:**
  - the roof's loads and uplift;
  - the combination with ψ0;
  - a point load;
  - a beam under an OG wall (reactions and moment);
  - the beam solver against closed forms;
  - the plate against Navier;
  - the reinforcement formula and Φ1;
  - a wall with Φ2 and a lintel;
  - the positions;
  - the two new checks;
  - the command line with the Positionsplan and the PDF.
- **Validation reports:** `docs/validation/loads.md` (0.2.0) and `docs/validation/struct.md`.
- **Help:** it gains `struct`'s kinds, `uea calc struct` and the Positionsplan. These are a few lines more; the bench could not be rerun here.
- **Not proved**, listed in the Statische Berechnung:
  - the roof's timber (rafters, purlins, collar beams) and its anchoring in detail;
  - the bracing and horizontal wind;
  - for slabs: minimum and robustness reinforcement, shear, punching, deflection and cracks, and pattern loading;
  - the ground slab;
  - partial-area compression under bearings;
  - Φ3 under the top slab;
  - basement walls with earth pressure;
  - the geotechnical checks of the footings.
- **Open:**
  - columns;
  - a beam's own deflection in the slab model;
  - the standard's worked examples as a private test suite;
  - the review.

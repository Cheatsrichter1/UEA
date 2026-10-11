# 0040: Structure, phase 8

Status: Proposed for the phase; slice 8a built (for the user's veto, and for the review of the licensed engineer the phase needs)
Date: 2026-10-11

## Context

Phase 8 (`ROADMAP.md`) is the structure: load-bearing elements, loads, frame analysis on an open-source solver. Its "done when" is that a licensed engineer reviews the validation. The engineer partner is not available yet, so this decision plans the phase and builds the slice that needs the least engineering judgment: what the architecture already says about the load path, and the characteristic loads and their way down to the foundation. Everything else waits for the engineer's review of this slice.

The architecture carries most of what the structure starts from: which walls are load-bearing (`lb`), their build-ups, the slabs and their build-ups, the floor build-ups and uses of the rooms, the openings and holes in them. The Haftung for the structure lies with the Tragwerksplaner and, for the check, the Prüfingenieur (`VISION.md`). UEA computes and the engineer decides and signs, as with every `norm` calculator.

## Decision

**The phase in four slices:**

| Slice | Content |
|---|---|
| 8a (built) | The load path from the architecture and its checks; `uea calc loads`: dead and imposed loads of the slabs, the walls' own weight, light partitions, the takedown to the foundation, the line loads on the strip footings |
| 8b | The roof (its own weight, snow per DIN EN 1991-1-3 and wind per DIN EN 1991-1-4 by the office's zone tables) on the walls under its eaves; point and line loads and beams as elements of `struct.uea`; the lintels over the openings in load-bearing walls, derived |
| 8c | Member design: masonry walls (DIN EN 1996-3, the simplified method), lintels and beams, slabs; frames and continuous beams on an open-source solver (candidates below) |
| 8d | The Positionsplan per storey and the Statische Berechnung as one A4 PDF to sign; the approval of holes in load-bearing members |

**Slice 8a.**

- **The pack `struct`** has no elements of its own yet: the load-bearing walls and the slabs are the architect's. It holds the checks and the calculator. `uea help struct` says so.
- **The load path** (`packs/struct/model.py`): a slab rests on the load-bearing walls of the storey below that its outline covers; a load-bearing wall stands on the load-bearing walls of the storey below whose cores its core overlaps, each taking the share of the overlap. The lowest storey stands on the foundation, its slab on the ground.
- **Checks:** `W-STRUCT-001`, a load-bearing wall that stands on no load-bearing wall below (its load would go into the slab); `W-STRUCT-002`, a slab with no load-bearing wall under it. They need no tables, so they are checks.
- **`uea calc loads [soil=<kN/m²>]`**, a `norm` calculator (DIN EN 1991-1-1, DIN EN 1990), not yet reviewed:
  - A slab: G = its area · Σ t·γ of its layers + Σ over the rooms on it of their area · Σ t·γ of their floor build-up. Q = Σ over the rooms of their area · (q_k of their use + the partition surcharge).
  - A light partition (not load-bearing): its weight per metre, Σ t·γ · its net elevation area / its length, selects the surcharge from the office's table; the largest on a storey is added to the imposed load of its slab. A heavier partition is a line load, which 8a does not take: the result fails and names it.
  - The share of each wall: every point of the slab goes to its nearest load-bearing wall below, which divides a rectangular field along its 45° bisectors (the Lasteinzugsflächen of a slab supported on all sides), on a grid of 5 cm. A wall takes G and Q in proportion to its area.
  - A load-bearing wall: its own weight, Σ t·γ · its net elevation area; from the top storey down each wall passes what it carries to the walls it stands on.
  - The footings: under each wall of the lowest storey n_k = (G + Q) / L and n_d = (γ_G · G + γ_Q · Q) / L; with `soil=`, the design resistance of the soil from the geotechnical report, the width b ≥ n_d / σ_R,d.
  - **Tables from the office:** `unit-weight` (γ by material, DIN EN 1991-1-1 Anhang A or the manufacturer), `imposed-load` (q_k by room use, DIN EN 1991-1-1/NA), `partition-load` (the surcharge by the partition's weight per metre), `struct-factors` (γ_G, γ_Q, DIN EN 1990/NA). None of the standard's values are in the repository (`0008`).
  - The record is `out/loads.json`, the report `out/loads.md`, and `uea export pdf loads` sets it on A4 to sign.

**Solver candidates for 8c** (licences checked against `CLAUDE.md`): PyNite (MIT; 3D frames and plates, in Python) is the first candidate. anaStruct (GPL-3) and Code_Aster (GPL) could only run as a separate process. OpenSeesPy needs a licence check before it is considered. The choice is 8c's, with the engineer.

## Alternatives

- **Wait for the engineer before building anything.** The load path and the loads are the input to every later slice, need the least judgment, and can be reviewed on their own; starting with them gives the engineer something concrete to review.
- **Elements for supports and loads in `struct.uea` now.** For the Einfamilienhaus the supports are the load-bearing walls the architect already marks. Elements come with 8b, where loads that the architecture does not give (a heavy tank, a beam) need them.
- **The shares by the walls' lengths, or by halves of each span.** Lengths ignore where the slab spans; halves of spans need the span directions, which a two-way slab does not have. The nearest-wall partition gives the 45° rule in a rectangle and a sensible split in an L-shaped field, with no input from the agent.
- **Shares from a plate analysis of each slab.** That is 8c's solver, with the engineer; for the takedown to the foundation the tributary areas are the usual first estimate.
- **Load combinations with ψ factors now.** 8a gives characteristic G and Q and the one design value of the footings; the combinations come with the member design.

## Consequences

- Haus Müller's load path is clean: the OG walls stand on the EG's, the gable walls of the Spitzboden on the OG's west and east walls, both slabs on load-bearing walls. With tables of our own, `uea calc loads` carries every wall and slab to the footings without losing a kilonewton (tested).
- Tested by hand in `tests/test_struct.py`: the two checks; a slab's G and Q; the 45° shares of a 10 × 8 box within the grid's 0.2 m²; the walls' own weight; the takedown from the OG to the EG; n_d and the footing width; a partition's surcharge, and one too heavy; a material missing from the table; Haus Müller; the command line and the PDF.
- The validation report is `docs/validation/loads.md`.
- The help lists `struct` among the topics and `loads` among the calculators (a few lines more; the bench could not be rerun here).
- Open in 8a: loads per room instead of per slab (a bathroom's heavier floor spread over the whole slab now), continuity over interior supports, cantilevers and free edges, walls on a slab (they fail `W-STRUCT-001`), walls on the ground slab (left out), the approval of holes in load-bearing walls and slabs (`0039`), the standard's worked examples as a private test suite, and the review.

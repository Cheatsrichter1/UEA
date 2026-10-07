# Validation report: `wofl` (Wohnfläche per WoFlV)

| | |
|---|---|
| Calculator | `wofl` 0.1.0, kind `norm` |
| Standard | Wohnflächenverordnung (WoFlV) of 25 November 2003 |
| Code | `src/uea/packs/arch/wofl.py`; room outlines and heights from `src/uea/packs/arch/geometry.py` |
| Tests | `tests/test_wofl.py`, `tests/test_prototype.py` |
| Review | **Not yet reviewed** by a licensed person |

The WoFlV is a federal ordinance and so an amtliches Werk: its rules may be implemented and cited freely. It needs no office-supplied tables (`docs/decisions/0008-office-supplied-norm-data.md`).

## What it computes

The Wohnfläche of each room, each storey and the whole project, from the model. Every result records the calculator, version, model state (batch and file hashes), scope and the rooms used (`out/wofl.json`). The report for humans is `out/wofl.md`.

## Clauses and how they are implemented

| Clause | Rule | Implementation |
|---|---|---|
| §2 Abs. 3 Nr. 1 | Zubehörräume do not count | By room use: `cellar` (a), `laundry` (c), `attic` (d), `technical` (f), `garage` (g) are excluded. All other uses count. |
| §3 Abs. 1 | Grundfläche from the lichte Maße, starting at the front edge of the Bekleidung | The room's Fertig outline: the region between the wall cores, minus every non-core layer of the walls (`docs/decisions/0015-rooms-and-finishes.md`). |
| §3 Abs. 1 | (no floor, no Grundfläche) | Voids in the room's own slab (a stair hole) are deducted. |
| §3 Abs. 3 Nr. 2 | Stairs with more than three risers and their landings do not count | The stair footprint inside the Fertig outline is deducted on the storey it starts on. |
| §3 Abs. 3 Nr. 3 | Türnischen do not count | Rooms end at the wall face; door reveals are never part of a room. |
| §3 Abs. 3 Nr. 4 | Niches count only if they reach the floor and are deeper than 0.13 m | A niche with sill 0 and depth over 0.13 m adds width × depth, counted by its own height per §4. |
| §4 Nr. 1, 2 | Clear height ≥ 2 m full, 1 m to < 2 m half, < 1 m nothing | Clear height from OKFF to the finished ceiling or the roof's inner surface. The parts of the outline in each height band are cut exactly with the ceiling planes. |

## Not implemented

- §3 Abs. 3 Nr. 1: chimneys, Vormauerungen, freestanding pillars and columns. The model has no such elements yet.
- §4 Nr. 3 and 4: Wintergärten, Schwimmbäder, balconies, loggias, Dachgärten, terraces. The model has no such rooms yet.
- §2 Abs. 3 Nr. 2: rooms that do not meet the Landesbauordnung. That is a judgement for the planner.

A room with no ceiling (no storey and no roof above it) stops the calculation, because its clear height is unknown, unless its use excludes it anyway.

## Assumptions to check when signing

- A Hauswirtschaftsraum (`utility`) inside the dwelling counts. Use `laundry` or `technical` for a Waschküche or a Heizungsraum.
- The Fertigmaß comes from the wall types' layers. Tiles, skirting boards and fixed furniture are not deducted, as §3 Abs. 2 requires.
- A stair placed against the Rohbau face overlaps the plaster zone; only the part inside the Fertig outline is deducted.

## Test cases

All expected values are computed by hand, with our own data.

| Test | Case | Expected |
|---|---|---|
| `test_stair_and_hole_are_deducted` | 10 × 8 box, 30 cm walls with 1 cm Gips inside; 16-riser stair 3.9 × 1.0 against the north wall; Spitzboden | EG and OG each 9.38 × 7.38 − 3.9 × 0.99 = 65.3634 m²; Spitzboden excluded (§2 Abs. 3 Nr. 1 d) |
| `test_niche_to_the_floor_counts` | niche 1.0 wide, 0.2 deep, from the floor | +0.20 m² |
| `test_shallow_or_raised_niches_do_not_count` | niche 0.1 deep; niche from 0.3 m | +0 |
| `test_heights_under_a_roof` | 45° gable, rafter underside 0.5 m at the eaves, room 9.38 wide, y 0.31–7.69 | full 5.0 × 9.38, half 2.0 × 9.38, under 1 m 0.38 × 9.38; Wohnfläche 56.28 m² |
| `test_room_without_ceiling_stops` | living room with nothing above | error |
| `test_wohnflaeche` (prototype) | Haus Müller | EG 71.7216 − 3.8415 = 67.8801 m², OG 70.8545 − 3.8415 = 67.0130 m², total 134.8931 m² |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

# 0047: Areas and volumes per DIN 277

Status: Accepted (built)
Date: 2026-10-16

## Context

Version 2 goes from the model to the tender (`FUTURE.md`). A cost estimate per DIN 276 is built on the areas and volumes per DIN 277: BGF, NRF with its usage groups, KGF and BRI. The building application asks for them too. The model already derives the rooms' finished outlines, the walls with their layers, slabs, voids, stairs and roofs (`ARCHITECTURE.md` §10).

DIN 277 is licensed, unlike the WoFlV behind `wofl`. Its text, its clause numbers and its table of uses may not go into the repository (`CLAUDE.md`, `0008-office-supplied-norm-data.md`).

## Decision

- **A `norm` calculator `din277`** (`uea calc din277 [level]`), in the architecture pack. It gives BGF, NRF, KGF and BRI per storey and in total, a report for humans in German and the JSON record (`docs/validation/din277.md`).
- **The office's table maps uses to groups.** `din277-uses` has one row per UEA room use with its usage group, 1 to 7 for NUF, 8 for TF, 9 for VF, from the office's copy. Without it the calculator still gives the four totals and says that the split needs the table; with it, a use without a row stops the split and is named.
- **The BGF outline** is the storey's cores and slabs, filled, grown by the thinnest exterior finish, mitred, so render runs round corners and over wall ends. The finish bands of the walls alone would leave a gap at every corner, where one wall runs to the far face of the other.
- **The BRI** is taken storey by storey on the BGF outline: finished floor to finished floor; the lowest storey from the underside of its floor slab; the top storey up to the top of the roof covering, integrated exactly over the roof's planes. A roof's footprint grows like the outline.
- **KGF = BGF − NRF.** Floor that has no room in the model would land there silently; the result reports it.
- **Stairs are VF** on the storey they start from, and the hole above them is no floor.

## Alternatives

- **Ship the standard's table of uses.** Simpler for an office, but the table is part of a licensed text. Room uses that map to a group by their name (living to NUF 1) would still be the standard's table in our words.
- **KGF from the walls.** Summing wall footprints double-counts the joins and misses door reveals; BGF − NRF is exact on the model.
- **BRI from the rooms' volumes.** Rooms leave out walls, slabs and the roof; the standard measures the whole building.
- **Make it `custom` until reviewed.** A calculator implementing one standard's method is `norm`; the review is a separate step, recorded in its validation report, as for every other.

## Consequences

- `uea calc din277` and the table `din277-uses` (`uea data show din277-uses`); a validation report; the reference regenerated.
- The cost estimate per DIN 276 can take its reference quantities from this calculator.
- Balconies, loggias and terraces (the Sonderfall der Raumumschließung) need elements of their own before they can be measured.

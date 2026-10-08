# 0015: Rooms, finished sizes and slab outlines are derived from walls

Status: Accepted
Date: 2026-10-07

## Context

Rooms store only a seed point (`at=`), and slabs no outline at all (`ARCHITECTURE.md` §3, "derived, never stored"). Areas per WoFlV, Heizlast and every room schedule depend on how UEA turns walls into room outlines, and on which wall layers it subtracts for the Fertigmaß.

## Decision

- **Rooms are regions.** For each storey, the domain is the outline of its walls (filled) joined with the outlines of its slabs. The free space is the domain minus the wall cores, split along the separators (`sep`). A room is the region around its seed. Two seeds in one region are an error. A region without a room is a warning, on storeys that already have rooms.
- **Bounds** are the walls and separators that touch the region. Doors and windows lead to the rooms on either side of their wall.
- **Finished sizes** (Fertigmaß) subtract the non-core layers of every wall from the regions. Layers are listed inside to outside on exterior walls, and from the −x or −y face on interior walls; `flip` reverses this. A wall is exterior when one of its faces lies on the storey's outline.
- **Bestand:** a demolished wall bounds nothing.
- **Slab outline:** the filled outline of the walls on the storey below, or the storey's own walls for the lowest slab. Voids are cut out of it.
- **Heights:** a wall runs from the SSL to the underside of the next storey's slab core. A room's clear height runs from the FFL to the finished ceiling (the slab core minus the layers under it) or to the inner surface of a roof (`0016-roofs.md`).
- Geometry runs on Shapely, snapped to a micrometre. Regions under 1 cm² are dropped as slivers.

## Alternatives

- **Rooms from cycles in a wall graph:** fragile at T-junctions and gaps, and needs explicit wall joins.
- **Rooms list their bounding walls:** more tokens, and breaks whenever a wall is added or moved.
- **Finished sizes by offsetting the room outline:** wrong where adjacent walls have different finishes.
- **Layer order by the placement sign** (from the anchor face outward): silently flips an exterior wall placed from the inside.

## Consequences

- L-shaped and open-plan rooms need nothing extra. Rooms follow when walls move, because only the seed is stored.
- The Haus Müller room areas computed by hand for the prototype come out the same (`tests/test_prototype.py`).
- Walls are axis-aligned for now: the position grammar places them on x or y. Imported walls with raw coordinates in any direction need the same region approach with general polygons (phase 4).

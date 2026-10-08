# 0018: Walls in any direction

Status: Accepted
Date: 2026-10-08

## Context

Until now a wall has one position on one axis and a span on the other (`y=S+ x=W..E`), so it runs along x or y. Bay windows, chamfered corners, sites that are not square and every wall of an imported model need walls in any direction (`0011-ifc-import.md`). `0012-datums-and-positions.md` reserved raw coordinates for these.

## Decision

- **Form:** `wall w9 EG AW-365 a=W,S+2 b=4.5,6`. `a` and `b` are the start and end of the wall's **axis** (the middle of its core). Each is a point `x,y` of two anchors, so they can be raw numbers or relative to grids and walls (`a=w4.c,w1.c`: where the axes of w4 and w1 cross). A wall has either `x=`/`y=`, `on=`, or `a=`/`b=`.
- **Axis, not core face.** Plan positions elsewhere are core faces, because a dimension chain measures faces. A skew wall has no clear dimension along an axis, and IFC, DXF and Revit all give the axis, so raw walls follow them.
- **Axis-parallel raw walls become ordinary walls.** If `a` and `b` have the same y (or x), the wall is placed like `y=… x=…` with the same faces `.n .s .e .w`. Other walls can anchor on it.
- **Skew walls** have a frame: `s` runs from `a` to `b`, across runs to the left of `a→b` (`.l`, the `hi` side) and to the right (`.r`, the `lo` side). Layers are listed from the right face on interior walls, as for the −x or −y face of an axis-parallel wall.
- **Anchors never point at a skew wall.** A wall that is not parallel to an axis has no x or y position. An anchor on one is an error that says so. Points anchor on grids and axis-parallel walls.
- **Openings** in a skew wall are placed with `s=`, the distance of the first edge from `a` along the wall (`s=1.2+`, or `s=f1+0.5` from another opening in the same wall). `x=`/`y=` stay for axis-parallel walls.
- **Joins.** The body of a raw wall is a rectangle around the axis with square ends. Where an end touches another wall of the storey, it is extended to the far face of that wall, so the corner has no gap and no wedge, at any angle. A free end stays as given. Axis-parallel walls written with `x=`/`y=` end on faces and are never extended. The extension changes the body (areas, plan, IFC), not the wall's length or the openings' coordinates.
- **Overlaps.** The overlap check (E-ARCH-011) uses the bodies without extensions and ignores overlaps within a wall's thickness of an end point of a raw wall, because raw walls that meet on their axes overlap there by design.
- **Separators** (`sep`) stay axis-parallel.

## Alternatives

- **Core face line instead of the axis:** matches the datum elsewhere, but an agent would have to offset by half the core thickness, which is arithmetic it should not do, and imports would have to convert.
- **Footprint polygons (four corner points):** exact for any join an importer sees, and it is what a mitred Revit wall exports. But an agent would write four points per wall, and a wall would have no axis for its layers and openings. An importer can still compute the join and write the end points where the body should end.
- **Joins by mitre or by "join geometry" per pair of walls:** needs a join type per corner. Extending to the far face of the wall touched gives the same result for T-joins and for L-joins with the same thickness, and is one rule.
- **Square ends without any join:** leaves a triangle of up to 4.5 cm² per join at 45° with a 30 cm wall, which would end up in the room's Wohnfläche.

## Consequences

- Rooms, slab outlines, exterior detection, finishes, plan and IFC work on polygons already; they need the frame, not new algorithms.
- At very shallow angles (below about 12°) between a raw wall and the wall it touches, no join is made.
- Curved walls (`ROADMAP.md`) build on this: an arc is another way to give the axis.

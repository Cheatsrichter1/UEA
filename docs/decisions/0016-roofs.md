# 0016: Roofs as planes over the storey outline

Status: Accepted (roofs over outlines that are not rectangles: `0020-roof-parts.md`; more shapes: `0021-roof-shapes.md`)
Date: 2026-10-07

## Context

Roofs are where plain extrusion stops (`ARCHITECTURE.md` §10). Pitched roof planes cut the gable walls and set the clear height of the rooms under them, which the Wohnfläche depends on. `0012-datums-and-positions.md` fixed the stored value: `knee` (`kn` until `0017-english-format.md`), the rafter underside at the outer face of the eaves wall, above the SSL.

## Decision

- A roof covers the bounding box of its storey's outline, or the rectangle it is given with `x=` and `y=` (`0020-roof-parts.md`). If the outline is not a rectangle and no rectangle is given, UEA warns.
- The rafter underside is a set of planes, one per eave edge. Each plane starts at `knee` above the SSL at the outer wall face and rises inward with the pitch; the roof is their minimum. A `gable` roof has two eave edges (`ridge=x` or `ridge=y`), a `shed` roof one (`up=` is the side it rises to), a `hip` roof four. Half-hip, mansard and flat roofs are made from the same planes (`0021-roof-shapes.md`).
- The overhang is `eave` at eave edges and `verge` at the others.
- A wall with `top=<roof>` ends at the rafter underside along its centre line. A room under a roof takes the roof's inner surface (rafter underside minus any lining) as its ceiling, together with the flat ceiling of a storey above where there is one.
- Derived values: the eaves height is the top of the roof skin above the outer wall face, the ridge height the top of the skin at the highest point. Heights under the roof are integrated exactly, piece by piece, for volumes and the WoFlV height zones.
- Plane cuts only, no geometry kernel.

## Alternatives

- **Roof outline from explicit points:** needed for complex roofs later, but more tokens for the common case.
- **One element per roof plane:** more flexible (Kehlen, Gauben), more tokens and more ways to get it inconsistent.

## Consequences

- Gable, shed and hip roofs over a rectangular house work. Haus Müller gives eaves +6.12 and ridge +8.10, as computed by hand.
- Roofs over L-shaped houses are several roofs, one per wing (`0020-roof-parts.md`). Dormers and a roof that spans two storeys with a knee wall need further work.
- The IFC export writes each roof plane as an `IfcSlab` (ROOF) under the `IfcRoof`, and clips gable walls with half-spaces.

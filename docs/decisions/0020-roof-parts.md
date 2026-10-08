# 0020: Roofs over outlines that are not rectangles

Status: Accepted
Date: 2026-10-08

## Context

`0016-roofs.md` let a roof cover the bounding box of its storey and warned for any other outline. L-shaped, T-shaped and U-shaped houses are common; their roofs are a gable or hip roof on each wing that meet in a valley.

## Decision

- **A roof covers a rectangle.** Without `x=` and `y=` it is the bounding box of the storey's outline, as before. With them (`x=W..m2 y=S..N`, the same spans as a `void`) it covers that rectangle, with its own shape, ridge, pitch, knee and overhangs.
- **Several roofs on one storey are one roof.** The rafter underside is the highest of the roofs where they overlap: a wing's roof runs into the main roof and the planes meet in valleys, hips and ridges. For a roof on each of two overlapping rectangles that make an L this is exactly the roof of the L (checked against a straight-skeleton roof by hand for the hip roof; the gable roofs are the usual cross gable).
- **Walls with `top=<roof>` are cut by the combined roof** of that roof's storey, not only by the roof named. A gable wall at a Querhaus follows the higher roof.
- **Rooms:** the clear height is the lower of the slab above and the combined roof; where no roof covers a point, only the slab above counts. Heights, volumes and the WoFlV height zones are integrated piece by piece over the planes, as before.
- **Checks:** W-ARCH-041 (the outline is not a rectangle and the roof has no `x=`/`y=`) names the fix. W-ARCH-042 reports a part of the outline that no roof covers.
- IFC: the roof planes of all roofs of a storey are cut against each other, so the `IfcRoof` shows the valleys. A wall under several roofs is a set of prisms, not a clipped extrusion.

## Alternatives

- **A roof from explicit outline points** (`pts=`): covers any polygon, but costs tokens in the common case and needs a rule for which edges are eaves. Rectangles that overlap cover L, T, U and cross shapes.
- **A straight-skeleton roof over any polygon:** the mathematically clean hip roof for an arbitrary outline, but it needs a skeleton algorithm (a dependency, or our own) and it does not give a cross gable, which is the usual roof of an L-shaped house.
- **One element per roof plane:** more flexible (Gauben, Kehlen), more tokens and more ways to get it inconsistent. It stays an option for later (`ROADMAP.md`, more roof elements).

## Consequences

- Roofs stay axis-parallel rectangles. A roof over a house turned by some other angle, or over a trapezoid, is not covered; the outline warning stays for it.
- Two roofs that overlap with the same planes are one roof; the one with the lower index wins the tie.
- Dormers and roof windows are roofs on small rectangles whose plane is higher than the main roof; they need a knee that is not tied to a storey, which is open.

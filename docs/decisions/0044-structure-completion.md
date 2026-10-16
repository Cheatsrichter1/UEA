# 0044: The rest of the structure: slab checks, rafters, columns, bracing

Status: Accepted; built and reviewed (with 0040)
Date: 2026-10-12

## Context

`0040-structure.md` built the load path, the loads and the Statische Berechnung of slabs, beams, masonry walls, lintels and strip footings. It listed as not proved: the roof's timber, the bracing and the horizontal wind, columns, and the slab checks beyond bending (shear, punching, deflection, minimum reinforcement, pattern loading). The user asked to close them for the first version, before the engineer's review, which covers them together with 8a to 8d.

## Decision

**Slabs** (`plate.py`, `design.py`):

- **Pattern loading.** The plate is solved for the imposed load on every room and on two groups of alternate rooms. A room's neighbours across a wall go into the other group as far as two groups allow; rooms meeting only at a corner are not neighbours. Each design value is the largest of the cases.
- **Minimum reinforcement** (DIN EN 1992-1-1, 9.3.1.1 with 9.1N), with the factors from the office.
- **Shear** without shear reinforcement (6.2.2). The plate elements' own shear next to a line support is not reliable: in the test box it was more than three times Navier's. So v_Ed is the supports' line reaction, away from the corners of the supports, where a plate concentrates its corner forces. It matches Kirchhoff's effective shear within 1 %. An interior support's reaction counts in full, on the safe side.
- **Slenderness** l/d against the office's limits instead of a deflection calculation (7.4.2 with NA), with l the largest of the fields' shorter spans.
- **Punching** does not arise: the slabs rest on lines (walls and beams).

**Rafters** (`rafter sp1 rf1 C24 b= h= e= [collar= cb= ch=]` in `struct.uea`):

- A pair of rafters of a gable roof is a plane frame on PyNite. It runs from the eaves' tip over the bearing on the eaves wall to a hinge at the ridge, with the feet held. A collar beam can be pinned between the rafters.
- The loads are the roof's: g along the slope, snow on plan, wind normal to the planes. The combinations take snow or wind as the leading action.
- The rafters and the collar are proved with the office's timber table (DIN EN 1995-1-1: bending with compression and k_c, or with tension; shear; deflection).
- The thrust at the feet is reported for the slab to take. Other roof shapes are listed as not proved.

**Columns** (`column co1 EG HEB-140 at=` in `struct.uea`):

- A column stands in a storey under a beam of the slab above. The beam bears on it like on a wall.
- The column passes its load to the slab it stands on as a point load. On the lowest storey it goes to its own pad footing.
- It is proved against flexural buckling (DIN EN 1993-1-1, 6.3.1.2) with the α of its section from the office's `column-section`, pinned at both ends. The pad's side is a ≥ √(N_d/σ_R,d).
- `W-STRUCT-005` flags a column under no beam.

**Bracing** (`bracing.py`, one position per storey):

- The wind on the facades, band by band per storey, comes from the office's c_pe of zones D and E by h/d. It is carried down to each storey as V and M.
- V and M are shared among the piers of the load-bearing walls along the wind (the stretches between openings) by t · l³.
- Each pier is checked for the open joint (the resultant within l/2) and for shear (DIN EN 1996-1-1, 6.2 and 3.6.2) with f_vk0 and f_vlt from the office's `masonry-shear`.
- A storey under a roof with no wall in one direction passes that wind through the roof's bracing to the storey below.

## Alternatives

- **Shear from the plate elements:** unreliable at the supports (see above).
- **A deflection calculation of the cracked slab:** needs the creep and the cracked stiffness; the slenderness limit is the standard's simple route and conservative for a house.
- **The rafters as single-span beams on plan:** the classic hand method. The frame gives the same moment for a couple roof (tested) and also the axial forces, the collar's force and the thrust.
- **Bracing by the walls' length alone, or by l²:** t · l³ is the stiffness of cantilevering piers of equal height. Torsion of the plan is left to the engineer.
- **Timber columns by DIN EN 1995:** the column formula is the steel one, with the α of its section. Timber columns can follow with their own table.

## Consequences

- `struct` 0.2.0 and `loads` 0.3.0. New tables: `timber`, `column-section`, `wind-wall`, `masonry-shear`; new rows in `struct-factors` (crdc, vmin, rho-min-ft, rho-min) and `struct-limits` (ld, ld-span).
- The test box's slab, 0.2 m over 7.7 m, now fails its slenderness, as it should. Haus Müller's slabs, rafters and bracing pass with the synthetic tables.
- Still not proved: the connections and the anchoring of the roof, the roof plane's bracing, torsion, robustness reinforcement and crack widths, timber columns, and the geotechnical checks of the footings.

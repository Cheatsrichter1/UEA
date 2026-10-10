# 0030: IFC import, slice 4b: grids, slab openings, stairs and roofs

Status: Accepted (slice 4b built)
Date: 2026-10-10

## Context

Slice 4a (`0029-ifc-import.md`) left roofs, stairs, slab voids and grids for slice 4b. Walls map almost one to one: a body becomes an axis and a type. Stairs and roofs do not. In UEA they are parameters (`n`, `tread`, `shape=l`; `gable`, `pitch`, `knee`) from which UEA's own code lays out the geometry (`0016-roofs.md`, `0019-stair-shapes.md`, `0021-roof-shapes.md`). The file has only a body. The IFC attributes that could say it (`NumberOfRisers`, `RiserHeight`, the roof's `PredefinedType`) are optional and often missing or stale. They never say where the stair or roof is, and a mesh has none of them.

## Decision

**Fit by building.** For stairs and roofs the importer reads the faces of the tessellated body. The treads are the horizontal faces that look up; a roof is the planes of its top. It then proposes the UEA elements that could have made those faces, lays each one out with UEA's own code (`layout` in `packs/arch/stairs.py`, `make_roof`), and keeps the one that lies where the file's faces lie. One that fits none is listed as not imported, with the reason (`IfcStair "Treppe" (its treads match no straight, L or U stair of UEA)`). It is never approximated, so what an architect drew is never silently changed. The rules of what a stair or a roof is stay in one place.

**Grids.** Straight axes within 0.1° of x or y become `grid NAME x=` or `y=`, in world coordinates (the grid's placement and turn applied). The name is the tag reduced to letters, digits and `_`. A tag that does not start with a letter, or that reads like an element id (`a1`), gets a `G` in front (`1` → `G1`); a name already taken (a level `EG`) gets `_2`. Diagonal and curved axes are not imported. Imported walls keep their coordinates and do not refer to the grids. Anchoring them to the grids is intent the file does not state, and an agent can do it with a batch.

**Openings in floor slabs.**
- Opening elements in a floor slab and holes in a slab's own body (at least 0.05 m²) become voids in the slab UEA has for that storey. The same opening written both ways counts once (90 % overlap).
- An opening whose outline is the footprint of an imported stair arriving at that storey (overlap over union at least 0.95) becomes `over=<stair>`, so it moves with the stair. The others become rectangles `x=a..b y=c..d`. An outline whose edges all run along x or y (within 2 cm) is cut into rectangles; any other outline is not imported.
- An opening in a wall that nothing fills is not imported. A recess (a niche) is reported as such: UEA's niches (`niche`) are placed by intent, and mapping them is slice 4c.

**Stairs.**
- A stair is an IfcStair with its flights, landings, plates and proxies. Railings and stringers are left out, because their top faces would pass for treads. A flight that belongs to no IfcStair is a stair of its own; the lone flights of an L or U stair therefore are not importable (each alone is not a stair of UEA).
- Treads: horizontal faces that look up, grouped within 4 mm of height, of 0.02 m² or more.
- Storeys: the first pair of storeys (with walls) that is a whole number of risers apart. The riser is the median step between treads (8 to 30 cm, the exact one within 1.5 cm of it), and every tread must lie within 2 cm of a whole riser.
- Direction, tread depth and width come from the first two treads. The candidates are straight, then, from the first tread that leaves the straight line: L with a landing, L with 2 to 6 winders, and U with the well the treads show (0 to 1 m). Each turns either way, with the first flight ending at that tread or one before.
- The best candidate is kept if its treads differ from the file's by less than 6 % of their area (symmetric difference over the file's tread area). Above 3 % the report says so (`note: stair Treppe: its treads differ from UEA's by 3% of their area`).
- The footprint is placed by its corner (`x=X+ y=Y+`); the status comes from the stair's Pset.

**Roofs.**
- A roof is an IfcRoof with its slabs, plates, parts, proxies and nested roofs. A roof slab that no IfcRoof gathers is a roof. Lone roof slabs within 5 cm of each other are one roof, because some programs write every pitch as a slab of its own.
- The planes of the top are the faces that look up and are at most 75° steep. Planes smaller than 0.1 m² or 1 % of the top are details and are left out. Each plane must fall along x or y; a plane under 0.23° is flat.
- The shape follows from the planes. With one slope: shed (one side), gable (two opposite sides), hip (four sides at one eaves height), or a half-hip gable (four sides, the hipped ends starting higher). With two slopes it is a mansard. Anything else is not imported.
- Layers come from the material layer set, top to bottom, with the rafters as the core (by material name). The body says how thick the roof is. Where the layers do not add up to it, the roof gets one layer of the body's thickness, and the report says so. A surface without thickness gets 2 cm, also noted.
- Storey: the highest storey (with walls) whose SSL lies at most 1 m above the lowest point of the rafters, trying the file's own storey first (at most three are tried). A roof the file hangs on the OG whose eaves are 1.2 m above the EG's slab stands on the EG.
- Foot: the outline of that storey (the faces of the wall cores, where UEA's roofs stand), if it is a rectangle and the roof reaches 0 to 2 m past it. `eave=` and `verge=` are measured from the core faces; where they differ by side the mean is taken, noted. Otherwise the roof gets `x= y=` of its own extent and no overhang, also noted.
- `knee` is the height of the rafter underside at the foot edge above the SSL. Lengths go to 5 mm; the pitch goes to 0.01°, or to the half degree within 0.05° of one. A file's numbers are good to a few millimetres, and `knee=0.495` reads better than `0.4949`.
- The fitted roof is kept if its top lies within 2 cm of the file's on every plane (sampled away from the plane borders); above 1 cm the report says so.
- **Walls under a roof.** A wall's top is sampled at 11 points along its axis. Where it lies within 3 cm of the underside UEA cuts the wall to under the fitted roofs, the wall gets `top=<roof>` instead of `h=`. A sloped top that does not match is set to its highest point with `h=`, with a note that says whether a roof was fitted on that storey. A top counts as sloped where these samples differ by more than 2 cm, because the corners of a gable end lie below its middle.

**Re-import** works as in `0029`. Stairs, roofs and opening elements are keyed by GlobalId. Holes in a slab body are keyed by the slab's GlobalId and the hole's centre to 0.1 m; grid axes by the grid's GlobalId, U or V, and the tag. A grid the file lost is removed like an element, unless something refers to it (levels and types are still never removed). A new opening over a stair that was deleted in UEA becomes its rectangle; a new wall under a roof deleted in UEA gets `h=`. The summary line names only what happened (`ok (batch 5): 1 removed`).

**A fix in the core.** `gap=0` on a U stair (flights touching) was read as the default 0.1; 0 is now 0.

**The help** names what is mapped and that the rest is listed with its reason.

## Alternatives

- **Read the IFC attributes of stairs and roofs.** Optional, often missing or stale, silent on position; a mesh has none.
- **Fit the parameters by least squares.** The discrete choices (shape, turn, the first flight, winders) make it a search anyway. Building candidates with UEA's own layout keeps one definition of each stair and roof.
- **Take the closest UEA roof or stair when none fits.** It would change the architect's design without a word. The report names the element and why, and the agent decides (two roofs with `x= y=`, a simpler stair, a request to the architect).
- **Voids as polygons.** UEA's voids are rectangles or a stair's footprint; polygons would need a new value type for a rare case.
- **Walls anchored to the imported grids.** Which grid a wall means is intent the file does not hold; walls near a grid line are not necessarily on it.

## Consequences

- Tested with hand-built files (`tests/test_import_shapes.py`): grids, openings, stairs and roofs written several ways, the failure reasons, re-imports, and IFC2X3, IFC4 and IFC4X3 giving the same model (IFC2X3 has no roof types, so the type is named after its thickness, `R200`). UEA's own exports, relabelled as another program's, come back with the same parameters: seven roof shapes with their surface within 5 mm, nine stairs exactly, Haus Müller with its roof, stair and the void over it.
- The 5 mm comes from 4a: walls without a layer set usage have their axis in the middle of the body, a few millimetres off the core. The outline a roof stands on grows by as much, and `knee`, `eave` and `verge` come back 5 mm smaller (1.5 cm of knee on a 70° mansard). The roof itself lies where it lay.
- Not covered: roofs of L-, T- or U-shaped houses in one IfcRoof, dormers, planes not along x or y, gables whose ridge is off the middle; stairs with more than two flights, spiral and curved stairs, stairs turned off x or y, stairs to a storey without walls; openings that are not made of rectangles; niches. A file whose storey elevations are the raw slab rather than the finished floor puts the treads a finish thickness off whole risers, and its stairs are not imported. All of these are reported, not guessed.
- **Still not tried on a real office file.** Slice 4c (units, several buildings, curved walls, curtain walls, niches, BCF) is the polish a real file asks for; a real file should set its order.

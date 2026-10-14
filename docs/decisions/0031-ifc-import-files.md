# 0031: IFC import, slice 4c: how programs write a file

Status: Accepted (slice 4c built)
Date: 2026-10-10

## Context

Slices 4a and 4b (`0029-ifc-import.md`, `0030-ifc-import-shapes.md`) read a house as a test fixture writes it: in metres, near the origin, along the axes, one building, every wall one body with its layer set. Offices' files differ. Revit and Vectorworks often write millimetres; Allplan and Revit with shared coordinates place the building in survey coordinates (UTM eastings and northings, the height above sea level) and turn it to true north; a site may hold a garage as a second building; walls come stacked or as one part per layer; glass fronts are curtain walls; niches are recesses. This slice handles what UEA's model can already express, and reports the rest. It has not been tried on an office's file yet; the user tests one.

## Decision

**Units.** IfcOpenShell scales lengths to metres; the importer scales what it reads from attributes (elevations, layer thicknesses, grid axes) by the file's unit. Tested: millimetres, centimetres and feet give the same model as metres.

**Where the plan lies.**
- The importer chooses a frame for the plan: moved by (dx, dy), then turned about the origin. It is turned when at least half the length of the walls runs in one direction more than 0.1° off x or y, by that direction (the length-weighted mean of the walls within 0.1° of it), so that the walls run along x and y. It is moved when the middle of the walls lies more than 100 m from the origin, so that the lower left corner of the wall bodies is 0,0. A plan near the origin and along the axes is left as the file has it.
- The turn is measured after the move: footprints millions of metres from the origin lose the precision a direction needs (shapely's results drift by 0.01°).
- The note says what was done (`the file's plan is moved by -484999.9378,-5519999.7678 m and turned by -30°, so its walls run along x and y near the origin`). The frame goes into the history entry of the import, with the height in the file of the ground storey's FFL, and every later import of the project keeps it: a newer file whose garden wall moves the corner of the plan still lands where the first one did.
- A storey's height is the height of its placement in the file, where the geometry is. Where every storey has the same placement and only `Elevation` tells them apart, the elevation counts, added to the building's height (IFC gives it relative to the building).

**Several buildings.** One building per import: the one `--building <name>` names (its name or GlobalId), else the one an earlier import of the project read, else the one with the most walls. The others are reported (`1 IfcBuilding "Garage" (one building per import; --building picks it)`), their elements are not counted. Elements in no storey go with the building with the most walls. A garage is then a project of its own until UEA models a second building (`FUTURE.md`, Backlog).

**Walls in parts.** A wall whose body is in its parts (`IfcRelAggregates` to walls or building element parts) is one wall:
- Its body is the union of the parts. Where that is no plain strip (stacked parts of different thickness), the tallest part gives the axis and the thickness.
- Its layers come from the wall's own layer set; without one, from parts that lie side by side with one material each (a program that writes one part per layer), in their order across the wall; else from the tallest part's layer set.
- A note names it (`made of 3 parts, one per layer; imported as one wall`). Only the profile along the top decides whether its top slopes, as the top of a lower part lies inside the wall.
- The layer set of a wall's type counts where the wall has none of its own (IfcOpenShell's inheritance), tested.

**Curved and bent walls** are not imported, with the reason: `curved` where the wall's axis is an arc (`IfcTrimmedCurve` on a circle, an arc in a composite or indexed curve), `its axis bends` for a polyline, and `its footprint is no straight strip` where a wall without an axis fills less than 80 % of the strip around it. Before, such a wall became a strip across its chord, as thick as its sagitta. UEA has no curved walls yet (`FUTURE.md`, Backlog); straight walls in their place are an agent's decision.

**Curtain walls** become a wall with windows over its face, which UEA can already express: the rooms close against it, the electrical planner places nothing on it, a later Heizlast sees glazing.
- The wall is the strip around the footprints of its panels and mullions (their convex hull: a curtain wall's footprint is a comb), of a type `CW<depth in mm>` with one core layer `curtain`.
- Its glass is a window from the FFL (or the curtain wall's foot, if higher) to the top of the wall, over its length less the doors that are parts of it; one window per stretch of 5 cm or more. Their type is named after the curtain wall's type and carries its `ThermalTransmittance` as `uw=`. A window that is a part of the curtain wall is its glazing, not a window of its own.
- Keys of the windows are the curtain wall's GlobalId with `:glass#0`, `#1`, ... from one end; a door moved in a newer file moves the glass on both sides.

**Niches.** An opening element in a wall that nothing fills and that does not go through the wall (it reaches less than the wall's thickness less 1 cm) is a niche on the face it opens on: its width and place along the wall, its sill above the FFL, `d=` its depth from the core face (UEA measures niches from the core, as the export writes them). One that goes through stays reported (`a wall opening nothing fills`: UEA has no openings without a fill yet); one that touches neither face, or only the finish, is reported as such.

**A fix from 4a.** The note a wall's footprint gives (not a plain strip, made of parts) was computed but not reported; it is now.

## Alternatives

- **Keep survey coordinates.** Every number in the model would carry seven digits before the point, for every agent, in every command; the turn would leave every wall skew, and roofs and stairs, which UEA fits along x and y, would not import.
- **Move by the site's placement instead of the walls.** Exporters put the survey offset on the site, on the building or into the coordinates themselves; the walls are where the house is in all three.
- **Read every building into one project.** Levels are the project's; a garage's `EG` would merge with the house's or become `EG_2`, and the rooms, slabs and roofs of both would mix.
- **Curved walls as straight segments.** Rooms would close, but the model would hold walls the architect did not draw, keyed by one GlobalId, to be replaced when UEA has arcs.
- **Curtain walls as a kind of their own now.** The right model (a grid of mullions and transoms, panel types) is a design of its own (`FUTURE.md`, Facades); until then a wall with windows keeps the rooms and the glazing right.
- **Curtain walls as separators.** Rooms would close, but the facade would be open on every plan and in every quantity.

## Consequences

- Tested with hand-built files (`tests/test_import_files.py`): a file converted to millimetres, centimetres and feet; the house turned by 30° at the origin, and in survey coordinates 485 km east and 5520 km north at 112.5 m (the plain model, moved by 0.17 m, the outer face to 0); a later file with a garden wall outside the first plan; storeys told apart only by their elevation; a garage as a second building, read by name and kept; layer sets on the type only; walls in skins and stacked; a curved wall with and without an axis; a curtain wall with and without a door, and the door moved; niches inside and outside and one through the wall. Haus Müller's two niches now come back, as deep and where they were.
- The import help names niches, curtain walls, `--building`, one building per import and the moved plan (+49 tokens, 274 for `help import`); the token task set is unchanged.
- Not covered: curtain walls over several storeys (one wall on the storey that holds it), curved or sloped curtain walls, stacked walls whose parts need different types, a plan whose walls run in two directions of equal length (it stays as it is, the walls skew), more than one storey sharing a placement and an elevation.
- **Not tried on a real office file.** That is the phase's last check (`FUTURE.md`, Open for v1).

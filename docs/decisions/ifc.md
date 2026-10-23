# IFC import and BCF

How the architect's IFC comes in and how requests go back out. Index in [README.md](README.md).

## 0011 IFC import

`uea import ifc <file>` maps the architect's storeys, grids, walls, slabs, roofs, stairs, openings and spaces into `project.uea` and `arch.uea`, as the inverse of the IFC export. Ids stay stable across re-imports through the GlobalId; a new version updates `arch.uea` and reports its effects downstream like any upstream change. What cannot be mapped is reported, never dropped. UEA's own exports are never read back.

- Imported walls do not sit on grids, so raw coordinates are a normal input (0018).
- Imported elements belong to an architect outside UEA; requests on them go out as BCF (0032).

Why: electrical and services offices start from the architect's model. Remodelling from PDF plans costs tokens and errors; DWG is lines without meaning; reading own exports back would invite editing outside the model.

## 0029 IFC import of walls, openings and rooms

An IFC is geometry, UEA wants intent. The importer reads what the file says and asks UEA for what it derives itself (outside face, wall height), so no rule is written twice.

- **Command:** `uea import ifc <file> --by <who> [-m why] [--dry-run] [--json]`, one batch with revert and log. Output: counts per kind, new issues, what was not imported (by IFC class) and notes.
- **Geometry from IfcOpenShell's tessellation**, not the representations: the plan footprint is the same for extrusions, clippings, brep and mesh.
- **Walls:** the axis is the middle of the core (the thickest structural-material layer, else the thickest); the side of the first layer from the layer set usage, else assumed outside. A type is made from the layers in UEA's order; a wall the other way round gets `flip`. Walls within 0.1° of x or y are snapped; ends up to 3 cm short of another core are extended; `h=` only where it differs from the derived height by more than 5 cm; `lb` and status from Psets.
- **Levels:** the ground storey is the one at elevation 0, else the lowest with walls; names `EG`, `OG` or `L1`, `B1`; `head` is the most common window top.
- **Slabs:** one per storey, the largest; its outline is derived, its layers above the core become `fb` and a floor type.
- **Openings:** a position along the wall; sill and head only where they differ from the defaults; types with `ud=`/`uw=` from `ThermalTransmittance`.
- **Rooms:** a seed at each space's centroid; the use from its names (German and English); a `sep` where two spaces share 0.4 m or more with no wall.
- **Re-import:** identity is the GlobalId, kept in the batch's `ifc` history entry with a hash of each imported line, never in the model's lines. A later import updates unedited elements, adds new ones, removes unedited ones the file lost unless referenced, and lists everything else as `kept:` with the reason. Levels and types are never removed. An import that changes nothing writes no batch.
- **Errors do not reject an import**: the architect's model is not ours to reject; its errors become issues. Files from UEA are refused.

Why: representations differ per program; placement axes sit on a face, not the core; GlobalIds in lines would add 22 characters each; removing edited elements would delete work.

## 0030 IFC import of grids, voids, stairs and roofs

**Fit by building.** For stairs and roofs the importer reads the tessellated faces (treads: horizontal faces looking up; a roof: the planes of its top), lays out candidate UEA elements with UEA's own code (`layout`, `make_roof`) and keeps the one that lies where the file's faces lie. One that fits none is listed with the reason, never approximated.

- **Grids:** straight axes within 0.1° of x or y; tags reduced to a valid name (`1` → `G1`, a taken name `_2`). Walls keep their coordinates and do not refer to grids.
- **Slab openings:** opening elements and holes in a slab body (≥ 0.05 m²) become voids; one matching an imported stair's footprint becomes `over=<stair>`; rectilinear outlines are cut into rectangles, others are not imported.
- **Stairs:** an IfcStair with flights, landings and plates (railings and stringers left out). Storeys a whole number of risers apart; candidates straight, L with landing or 2–6 winders, U; kept if treads differ by less than 6 % of area (noted above 3 %).
- **Roofs:** an IfcRoof with its parts; lone roof slabs within 5 cm are one roof. Planes up to 75° along x or y; shed, gable, hip, half-hip or mansard by the planes. Layers from the layer set with the rafters as core. The storey is the highest whose SSL is at most 1 m above the rafters' lowest point; overhangs from the core faces; lengths to 5 mm, pitch to 0.01°. Kept if within 2 cm of the file on every plane.
- **Walls under a roof** whose top lies within 3 cm of the fitted roof get `top=<roof>`; otherwise `h=` at the highest point, noted.
- Re-import keys: GlobalId; slab holes by slab and centre; grid axes by grid, U/V and tag.

Why: IFC stair and roof attributes are optional, often stale and silent on position; least-squares fitting is a search anyway over discrete shapes; taking the closest candidate would change the design without a word.

## 0031 IFC import of real files

- **Units:** lengths read from attributes are scaled by the file's unit (mm, cm and feet tested).
- **Frame:** the plan is moved when the walls' middle lies more than 100 m from the origin (lower-left of the wall bodies to 0,0), then turned when at least half the wall length runs one direction off x or y. The note says so; the frame and the ground FFL's file height go into the history, and every later import keeps them.
- Storey heights come from placements, or from `Elevation` where all placements are equal.
- **One building per import:** `--building <name>`, else the one read before, else the one with most walls. Others are reported.
- **Walls in parts** are one wall: the union of the parts; layers from the wall, else from side-by-side single-material parts, else the tallest part. A type's layer set counts where the wall has none.
- **Curved and bent walls** are not imported, with the reason.
- **Curtain walls** become a wall of type `CW<depth>` with one `curtain` core and windows over its face (minus its doors), keyed `:glass#n`, carrying `uw=`.
- **Niches:** an unfilled wall opening that does not go through is a niche with `d=` from the core face.

Why: survey coordinates would put seven digits in every number and leave every wall skew; several buildings in one project would mix levels and rooms; straight segments for arcs would hold walls nobody drew. Tried on a real office file privately.

## 0032 BCF requests

- `uea export bcf [discipline]` writes the requests whose targets belong to it (default `arch`) as BCF 2.1 to `out/<project>-<discipline>.bcf`. No requests is an error.
- One topic per request, open or not. Guid derived from project and request id, so re-exports update the topic. Type `Request`, status `Open` or `Closed`, title the request text, label the asking discipline, author and date from the batch. German description; a closed request gets a comment (`Erledigt (Stand 15).`, `Abgelehnt: <reason>`).
- The viewpoint selects targets by the GlobalId of the architect's file where imported, else UEA's export GlobalId (`export/guid.py`), with a camera 6 m south-west and 4 m above, in the file's coordinates (the import's frame undone). No snapshot.
- Reading BCF back is not built: the architect answers in the next IFC and in comments; an agent closes the request.

Why: BCF is what Archicad, Revit, BIMcollab and Solibri share, and 2.1 is what they read today; the standard library writes the zip, so no bcf-client dependency.

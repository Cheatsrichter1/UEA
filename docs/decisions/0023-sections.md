# 0023: Sections

Status: Accepted (built)
Date: 2026-10-09

## Context

Step 3 of phase 2 (`0022-plans-and-tables.md`): a section, the vertical cut an architect reads next to the floor plans. It shows the storey heights, the slabs, the roof and the stair in profile, and it carries the height marks that the plan sheet only gives as OKFF in the title block. The cut is found from the model like everything else: no drawn geometry is stored.

## Decision

**A `section` element in the arch pack.** `section A x=W+5.2 look=w`: a name (A, B, ... for Schnitt A-A), a position `x=` or `y=` (an anchor like every position, so `y=w3-0.5` or `x=st1.c` work and move with the model), and `look=` for the direction you look in after the cut: `e` or `w` for `x=`, `n` or `s` for `y=`; the default is `e` and `n`. The cut goes through the whole building. It is a model element, not an export argument, because the floor plans must show where it runs and the cut must survive a handoff. W-ARCH-060 warns when it meets no wall. Section names share the id space with grids (`S` and `N` are taken): the help says "A, B".

**Commands.** `uea export pdf|dxf|svg|png [name]`: the name is a level (its floor plan) or a section; with none, every plan and every section. Files: `out/section-A.pdf`. `uea show A` gives the plane and the direction.

**The drawing.** The section is a `Drawing` like the plan, on the same sheets (first of A3 1:100 ... A0 1:500 that fits, the same frame and title block, which stays unsigned and reads "Schnitt A-A"). Its x is the position across the cut (u, to the right as seen in the viewing direction) and its y the height. Plan numbers continue after the floor plans.

- **Cut.** Every shape is found by cutting the plan polygons with the cut line and giving the stretches their heights.
  - Walls: the core dark (load bearing) or grey, the finish layers a light band, as in the plan. The height is the wall's top profile, so a gable wall is cut under the roof. Openings are gaps through the whole wall, from sill to head; windows get their glass as a line with a tick at sill and head.
  - Slabs: the core, the layers under it, the floor build-up between the SSL and the FFL over the room, and the voids as gaps.
  - Roof: each plane of `roof_pieces` (the planes the IFC export uses) is cut into a band from the lining under the rafters to the skin above them, measured vertically (steeper roofs have more). Overhangs are cut as they are.
  - Stairs: steps on a sloping slab, 0.17 m thick square to the flight, found from the tread numbers of the flights; landings and winders are slabs of that thickness. A cut along the flight shows the sawtooth; a cut across it one step.
  - Status colours as in the plan: Neu red, Bestand grey, Abbruch yellow once anything in the project is not new.
- **Behind the cut.** Thin grey outlines, hidden lines removed by geometry (nearest first, each shape loses what the nearer ones cover, an edge shared with a nearer shape is drawn once), not by white fills, so the DXF has no wipeouts and no doubled lines. What is drawn: walls that face the cut, with their doors and windows as holes and the windows' frame and glass; walls seen end-on; the roof planes seen from below; stairs.
- **Dimensions** (the chains of the plan sheet). Along the bottom: the faces of the cut walls and the overall width. On the right, nearest first: sills, openings and heads of the cut openings up to the next floor; the storeys (FFL to FFL, the last to the ridge); the overall height from the ground (or the FFL) to the ridge.
- **Height marks** (Höhenkoten) left of the building, a triangle on a leader: each storey the cut meets (`EG ±0,00`), the ridge and the eaves of the roofs it goes through (`First +8,099`, the eaves height from the roof's own formula), the ground. Values with a comma, ±0.00 at the FFL of the ground storey.
- **Ground line** at the project's `ground=`, hatched, outside the walls only. No ground line without `ground=`.
- **Grids** that cross the cut: a dash-dot line with its bubble above the roof.
- **Room labels.** Name and clear height, "lichte Höhe 2,52 m" (or the range under a roof) from the room's derived ceiling, set where nothing else is drawn: nearest the middle of the room at mid height, else low down, else under the ceiling; if the room is too crowded with the lines behind the cut, the short form "l. H. 2,52 m", then the name alone, and as a last resort over the lines.
- **Cut lines in the plans.** On every storey the cut crosses: a thick dash-dot line through the building and, beyond the dimension chains at both ends, a bold stub, an arrow in the viewing direction and the name. The sheet makes room for them (14 mm of paper on those two sides). The line is not drawn through the chains.
- **DXF layers**, German like the plan's: `A-DECKE` (slab cores), `A-DACH`, `A-GELAENDE`, `A-ANSICHT` (what is behind the cut), `A-SCHNITT` (the cut lines in the plans); walls, openings, stairs, dimensions and the rest reuse the plan's layers.

**Code.** The pens, dimension chains, frame and title block moved out of `export/sheet.py` into `export/paper.py` (class `Paper`), which the plan and `export/section.py` both build on. The plan's output did not change.

**Not drawn yet.** The stair rail; niches seen behind the cut; the slab edge and the floor seen from the side outside the cut; footings (the model has none); a section that jogs (a polyline cut) or covers only part of the building; furniture. A cut along a wall's length shows the wall's elevation as one cut shape; that is what the plane meets.

## Alternatives

- **A section as an export argument** (`uea export pdf --cut x=5`): nothing to show in the plans, the agent repeats it in every request, a handoff loses it.
- **A cut by slicing the IFC mesh** (IfcOpenShell): needs the whole geometry kernel and loses the layers, the profiles and the status; the plan polygons and the top profiles already hold exactly what a section shows.
- **Hidden lines by white fills** (painter's algorithm in the drawing): the DXF would carry fills that hide lines only on a light background, and every edge twice.
- **Automatic section names and positions** ("one through the stair, one across the ridge"): a choice the architect makes. An agent can write the two lines.
- **One required `look=`**: a default of east or north covers most sections; the line stays short.
- **A drawn terrain with a slope**: the project has one `ground=`, a level terrain. A surveyed terrain comes with a site model (`FUTURE.md`).

## Consequences

- The model has a new kind in `arch.uea`. The help grew by 34 tokens (`bench/results.md`); the task set is unchanged. Haus Müller (`docs/prototype/`) is left as it is, without sections.
- `export svg|png` shows a section as the PDF does; `render` stays the working plan.
- The sum of cut walls and the heights in a section come from the same derived values as the tables and the IFC; a person who signs checks the drawing, not UEA.
- Elevations (step 4, `0024-elevations.md`) reuse `Paper` and the behind-the-cut machinery: an elevation is a section looking at the outside, with nothing cut.

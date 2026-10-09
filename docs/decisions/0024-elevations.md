# 0024: Elevations

Status: Accepted (built)
Date: 2026-10-09

## Context

Step 4 of phase 2 (`0022-plans-and-tables.md`): the four facades an architect reads next to the floor plans and the sections. An elevation is a section whose plane stands outside the building: nothing is cut, everything lies behind the plane (`0023-sections.md`).

## Decision

**No new model element.** The four facades are always there, named by the compass side that is seen: `uea export pdf|dxf|svg|png south` draws the south facade, looking north (Ansicht Süd). With no name, the export writes every plan, every section and the four elevations; files are `out/elevation-south.pdf` and so on. A section needs a `section` element because the plans show it and its place is the agent's choice; a facade needs nothing the building does not say. A project whose walls are not square to x and y gets facades that are drawn square to the axes and are only exact for the walls along them.

**What is drawn**, with the same sheets, pens, dimension chains, height marks, ground line, grid bubbles, frame and unsigned title block as the section (`export/section.py` does the hidden-line work, `export/elevation.py` the elevation):

- **Walls** seen from outside, one plane: wall faces that lie in the same plane are joined (a corner has no line in the facade), per wall to its top profile, so a gable wall follows the roof. Openings are holes in the face; windows get frame and glass, doors an outline and an inner frame. They are opaque: nothing of the interior shows through them. Walls inside and walls on the far side are hidden by the nearer ones.
- **Slab edges** close the facade between the storeys and show the storey lines. Under a roof the edge of the top slab reaches up to the rafters at the eaves, because the model has no knee wall.
- **The roof** seen from above, as a light fill: each plane at the top of its skin (steeper roofs have more), and the thickness along its edges, so a gable end shows the roof as a band, an eaves side the slope with the overhang. Planes seen edge-on draw nothing. At the same distance the roof counts as 1 mm nearer than the wall below it.
- **The ground** hides what is below it (`ground=` of the project): the facade starts at the ground line, which runs 8 mm beyond the roof's width. Without `ground=` the whole facade is drawn down to the foot of the lowest slab.
- **Dimensions**: along the bottom the openings and piers of the facade (all storeys) and its overall width; on the right the heights of its openings, the storeys and the total from the ground (or the FFL) to the ridge. Height marks for every storey, the ridge, the eaves and the ground; grids that cross the facade with their bubbles.
- Plan numbers continue after the plans and the sections (north, east, south, west).

**Not drawn yet.** Facade materials and colours (the model has the layers, not their appearance), shading, sun, balconies, chimneys, dormers (the model has none), demolished walls (an Umbau elevation of the existing state), reveals and sills, opening symbols (Drehflügel).

## Alternatives

- **An `elevation` element** with a direction and a range, like the section: only worth it for facades that are not square to the axes or for part of a facade, and it would put four lines in every project for nothing.
- **Picking out the facade walls** and drawing only those: the roof, the slab edges and the walls on other storeys that stand back would be missing, and a notch or a wing would be drawn wrongly. Drawing everything and hiding what is covered is the same code as the section's view.
- **Lines for edges and no fill:** the roof would not read as a surface. A light fill is the one fill, and the hidden-line step gives it the right outline.

## Consequences

- The export with no name now writes four more files per format. `uea export xlsx` is unchanged.
- `section.py` gained what an elevation needs (opaque windows, a fill for a face, the layout of the sheet) and the class `SectionSheet` is public. The sections' output did not change except that a window in the far wall now hides what is behind it.
- The roof edge (a band as thick as the roof's own layers, measured vertically) and the slab edge at the eaves are the model's, not an architect's detailing; an Entwurf elevation does not need more.

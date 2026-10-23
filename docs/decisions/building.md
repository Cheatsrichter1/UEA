# Building

The architecture model and the drawings made from it. Index in [README.md](README.md).

## 0012 Datums and positions

- **Plan positions are core faces** (Rohbau): the faces of a type's core layer, marked `*` in its layers. Finished sizes are derived from the other layers.
- **Heights count from the storey's FFL** (OKFF). A level stores `z` (its FFL; ±0.00 is the ground storey's) and `fb` (floor build-up), so its SSL (OK Rohdecke) is `z − fb`.
- **Positions are relative:** `anchor±distance`, from a grid, a wall face, an opening edge or centre, or a device; the sign says from which face and in which direction, like a dimension chain. Raw coordinates are for imported elements and walls in any direction (0018).
- **Openings store the structural size `W x H`** (Rohbaurichtmaß). Windows hang from the storey's `head=`, so their sill is derived; `sill=` only where one deviates. Doors stand on the FFL.
- **Devices:** `z` is the box centre above the FFL; the position along the wall is the box centre.
- **Roofs store `knee`:** the rafter underside at the outer face of the eaves wall, above the SSL. Eaves, ridge and each Land's Kniestock are derived.
- **Names:** level and grid names start with a letter and contain no `-` (`W-1.2` means grid W minus 1.2 m). Numeric axes get a letter name and a label (`grid A1 x=0 label=1`).

Why: German dimension chains measure core faces; the heights a human checks (sills, switches) count from the FFL; a `sill` on every window would move heads and break the façade line; the Länder define the Kniestock differently. Haus Müller is the worked example.

## 0015 Rooms and finishes

- **Rooms are regions.** Per storey the domain is the filled outline of its walls joined with its slabs; the free space is the domain minus the wall cores, split by separators (`sep`). A room is the region around its seed (`at=`). Two seeds in one region are an error; a region without a room is a warning on storeys that have rooms.
- Bounds are the walls and separators touching the region; doors and windows lead to the rooms on either side.
- **Finished sizes** subtract the non-core layers of every wall. Layers run inside to outside on exterior walls, from the −x or −y face on interior walls; `flip` reverses. A wall is exterior when a face lies on the storey's outline. A demolished wall bounds nothing.
- **Slab outline:** the filled outline of the walls on the storey below (its own walls for the lowest slab), minus voids.
- **Heights:** a wall runs from the SSL to the underside of the next slab core. A room's clear height runs from the FFL to the finished ceiling or the roof's inner surface.
- Shapely, snapped to a micrometre; regions under 1 cm² are dropped.

Why: graph cycles are fragile at T-junctions; listing bounding walls costs tokens and breaks on every move; offsetting a room outline is wrong where finishes differ.

## 0016 Roofs

- A roof covers the bounding box of its storey's outline, or a rectangle given with `x=` and `y=` (0020); UEA warns for other outlines.
- The rafter underside is the minimum of planes, one per eave edge, each starting at `knee` above the SSL at the outer wall face and rising with the pitch. `gable` has two eave edges (`ridge=x|y`), `shed` one (`up=`), `hip` four. Overhangs: `eave` at eave edges, `verge` at the others.
- A wall with `top=<roof>` ends at the rafter underside along its centre line. A room under a roof takes the roof's inner surface as ceiling, with any flat ceiling above.
- Eaves height is the top of the skin above the outer wall face, ridge height the top of the skin at the highest point. Heights under the roof are integrated exactly for volumes and the WoFlV zones.
- Plane cuts only, no geometry kernel. IFC: each plane an `IfcSlab` (ROOF) under the `IfcRoof`, gable walls clipped by half-spaces.

Why: explicit outline points or one element per plane cost more tokens and allow inconsistency. Haus Müller gives eaves +6.12 and ridge +8.10, as computed by hand.

## 0018 Raw walls

- `wall w9 EG AW-365 a=W,S+2 b=4.5,6`: `a` and `b` are the ends of the wall's axis (the middle of its core), each a point of two anchors (`a=w4.c,w1.c`). A wall has `x=`/`y=`, `on=` or `a=`/`b=`.
- The axis, not a core face: a skew wall has no clear dimension, and IFC, DXF and Revit give the axis.
- An axis-parallel raw wall becomes an ordinary wall with faces `.n .s .e .w`. A skew wall has a frame: `s` from `a` to `b`, `.l` (`hi`) left, `.r` (`lo`) right; layers start at the right face on interior walls.
- Anchors never point at a skew wall (an error says so). Openings in it are placed with `s=` from `a`.
- **Joins:** a raw wall's body is a rectangle around the axis; an end touching another wall is extended to that wall's far face, at any angle (none below about 12°). Walls written with `x=`/`y=` are never extended. The overlap check (E-ARCH-011) ignores overlaps within a wall's thickness of a raw wall's end.
- Separators stay axis-parallel.

Why: a core-face line would make the agent offset by half the core; four corner points per wall cost tokens and lose the axis; per-corner join types need more fields, and square ends leave wedges in the Wohnfläche.

## 0019 Stair shapes

- `shape=straight|l|u`, `turn=l|r` (seen climbing), `up=` the first flight's direction.
- A stair of `n` risers has `n−1` treads. `n1` is the first tread in the turn (default `(n−m+1)//2`). The landing counts as one tread (`w x w` for `l`, `(2w+gap) x w` for `u`, `gap=0.1`); `winders=m` (shape `l`) replaces it with `m` wedges from the inner corner.
- `x=`/`y=` place the bounding box; the footprint polygon is used by voids (`over=`), the Wohnfläche and room checks. Risers are `rise/n`; the step rule is checked on the flights.
- IFC: `QUARTER_TURN_STAIR`, `QUARTER_WINDING_STAIR`, `HALF_TURN_STAIR`, with flights, `LANDING` slabs and `WINDER` flights.

Not covered: curved and spiral stairs, winders in a half turn, two landings, the DIN 18065 walking line. Why: a list of flights would make the agent write coordinates and balance risers by hand.

## 0020 Roof parts

- A roof covers a rectangle: the storey's bounding box, or `x=W..m2 y=S..N` with its own shape, ridge, pitch, knee and overhangs.
- Several roofs on one storey combine by the highest, so a wing runs into the main roof in valleys, hips and ridges; two overlapping rectangles give the L-shaped roof exactly.
- Walls with `top=` are cut by the combined roof of that storey. A room's clear height is the lower of the slab above and the combined roof.
- W-ARCH-041: outline not a rectangle and no `x=`/`y=`. W-ARCH-042: part of the outline no roof covers. IFC cuts the planes against each other.

Why: overlapping rectangles cover L, T, U and cross shapes; a straight skeleton would not give the usual cross gable. Roofs over turned or trapezoid outlines and dormers stay open.

## 0021 Roof shapes

- Zeltdach is a `hip` roof on a square.
- Krüppelwalmdach: `halfhip=<run>` on a gable roof; the hip plane has the roof's pitch, the gable wall a flat top where it meets it. E-ARCH-043 bounds the run.
- Mansarddach: `mansard` with `pitch=` below the break, `upper=` above, `rise=` the break above the eaves line; with `ridge=x|y` the ends are gables (gambrel). The upper pitch must be less.
- Flachdach: `flat` with `knee=` as the underside above the SSL, no pitch; a fall is a `shed` with a small pitch.
- Layer thickness is square to each plane: vertical thickness = t·√(1 + a² + b²).
- IFC: `HIPPED_GABLE_ROOF`, `MANSARD_ROOF`, `GAMBREL_ROOF`, `FLAT_ROOF`. Two outward sheds make a butterfly roof, several a sawtooth.

## 0022 Plans and tables

**One `Drawing`, many outputs.** It carries scale and sheet, pen classes, hatches, dimension chains, text styles and layers; SVG, PNG, DXF and PDF render from it, so they cannot differ. Tables are plain data (`export/tables.py`) with a thin XLSX writer. openpyxl, ezdxf and reportlab: pure Python, vector, no system packages. `export svg|png` shows the printed sheet; `render` is the working plan with ids.

**Floor plan sheet** (`export/sheet.py`, `export/paper.py`):

- The first of A3 1:100, A3 1:200, A2, A1, A0 (to 1:500) on which the plan and its chains fit; frame 20 mm left, 10 mm elsewhere; title block 185 × 55 mm bottom right. Pens and text in paper mm.
- Wall cores filled and unioned, openings cut as real gaps, finishes a light band; load-bearing dark. Once anything is not new: Neu red, Bestand grey, Abbruch yellow.
- Windows as three lines, doors with leaf and swing. Three outer dimension chains per side (openings, wall faces, overall) in Rohbau dimensions with a comma (`1,135`). Grid bubbles outside the chains. Room stamps (id, name, finished area); stairs with walking line and risers.
- Title block with Bauvorhaben, Planinhalt, scale, plan number and Stand (date and batch); "ENTWURF – nicht unterzeichnet" and empty signature fields: a human signs.
- `project north=<deg>` adds a north arrow. The roof over the storey is drawn dashed (outline, ridges, hips, valleys).
- DXF in mm with German layers (`A-WAND-TRAG`, `A-TUER`, `A-BEMASSUNG`, ...), dimensions as lines and text, frame at scale in model space. PDF vector, Helvetica.

**Tables:** one workbook, a German sheet per kind (Räume, Wände, Öffnungen, Decken, Dächer, Treppen, Mengen). Rohbau quantities without VOB/C deduction rules (those belong to the LV, 0048). Wall area under the top profile. Fertigfläche is not Wohnfläche. Roof area sloped with overhangs. A status column; sums leave out demolished elements. Values, not formulas, with six decimals so sums agree. Each sheet names its batch and says it is not checked and not signed.

Why: PDF via DXF or SVG would add a renderer or system library; DIMENSION entities render differently in every program; formulas invite edits that break the link to the model; ISO 13567 and AIA layer schemes are licensed or American.

## 0023 Sections

- `section A x=W+5.2 look=w` in `arch.uea`: a name, an anchored position `x=` or `y=`, and the viewing direction (default `e`, `n`). A model element, because the plans show the cut line and it must survive a handoff. W-ARCH-060 warns when it meets no wall. Names share the id space with grids.
- `uea export pdf|dxf|svg|png A`; with no name every plan and section.
- Cut shapes come from cutting the plan polygons and giving the stretches their heights: walls to their top profile, openings sill to head, slabs with their build-up, roof planes as bands, stairs as stepped slabs.
- Behind the cut: thin grey outlines with hidden lines removed by geometry, not white fills, so the DXF has no wipeouts.
- Dimension chains, height marks (`EG ±0,00`, `First +8,099`), ground line at `ground=`, grid lines, room labels with the clear height. Cut lines with arrows on every plan the cut crosses.

Why: a cut as an export argument would vanish from the plans and the handoff; slicing the IFC mesh needs a kernel and loses layers and status; section positions are the architect's choice.

## 0024 Elevations

No model element: the four facades are always there. `uea export pdf south` draws the facade at the plan's −y side; with `north=` the heading names the compass point. Same sheets and hidden-line machinery as sections, nothing cut: walls joined per plane with openings as opaque holes, slab edges, the roof from above as a light fill, the ground hiding what is below, dimensions and height marks. Facades are drawn square to the axes.

Why: an `elevation` element would add four lines to every project for nothing; picking only facade walls would miss roofs, slab edges and set-back storeys.

## 0039 Holes

One kind, `hole` (ho), in `arch.uea`, owned by the architect:

| Host | Position | What |
|---|---|---|
| a wall | `x=`, `y=` or `s=` its edge, `sill=` | Wanddurchbruch |
| a wall face (`w6.e`) | the same, `d=` depth | Schlitz |
| a slab | `at=` its centre, size x and y | Deckendurchbruch |

- `round` makes a core drilling. A hole takes no area off walls in tables or the Heizlast and is no door or window to device checks.
- Handoff: the services ask, the architect answers, the services name it. A vertical riser or stack passes the hole around its point; any other storey change goes through the nearest hole or void named in `via=` on the tank, generator, manifold or ventilation unit, and the detour counts in lengths and the tree.
- Checks per discipline that must ask: `W-PLUMB-006`, `W-HEAT-005`, `W-VENT-007`, `W-VENT-006` (facade terminals). Arch checks treat holes like openings.
- Drawn with outline, cross and label (`KB Ø18 UK +2,31`, `DD 40/25`), dashed in the slab above; table Aussparungen; IFC `IfcOpeningElement` (`RECESS` for a chase); the import maps unfilled openings back.

Why: voids are for stairs and shafts and windows have U-values; the architecture cannot name a plumbing element; code must not decide where a load-bearing slab is cut.

## 0045 Shafts, prewalls, zones

Three `arch.uea` elements every discipline uses:

- **`shaft sh1 EG 0.4x0.6 at=<centre> to=DB`** opens every slab it passes, is not room floor area, and is the way up for any network changing storey (nearest of shafts and named holes wins). A riser in it passes the slabs. `E-ARCH-070`: top not above bottom.
- **`prewall vw1 w9.n 1.6x1.2 y=<edge> d=0.2`**: fixtures and devices on that face within it sit on its front; it is an installation zone along its middle at half height; drawn hatched. Over 1.5 m high on more than 0.1 m² it does not count for the Wohnfläche (WoFlV §3 Abs. 3 Nr. 1).
- **`zone iz1 EG a=<pt> b=<pt> z=2.3`**: an installation zone. Touching zones form a network. On a storey with zones every section of pipes, ducts and cables runs straight to the nearest zone, along the zones and straight on; the path is kept, drawn and counted. Storeys without zones keep the rectilinear lower bound.

Why: DIN 18015-3's zone distances are licensed and practice varies; a void per slab repeats the shaft and does not tell the networks; a pre-wall as a wall would split rooms. Open: sloped or vertical zones, pre-walls in the IFC, clashes within a zone.

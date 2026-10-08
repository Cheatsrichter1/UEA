# 0022: Plans and tables for humans

Status: Accepted (tables and the floor plan sheet built; sections and elevations to follow)
Date: 2026-10-08

## Context

Phase 2 of `ROADMAP.md` makes the exports an architect or Fachplaner can read: floor plans, sections and elevations as DXF and PDF in German drafting conventions, and XLSX tables. Today there is one neutral `Drawing` (polygons, lines, arcs, text) that renders to SVG and PNG for agents (`ARCHITECTURE.md` §9). It has no scale, line weights, hatches, dimensions, sheet or title block, and no table output.

## Decision

**One model, many outputs.** `Drawing` grows what a drawing needs (scale and sheet, pen classes instead of colours, hatches, dimension chains, text styles, layers). SVG, PNG, DXF and PDF all render from it, so they cannot differ. Tables are plain data (`export/tables.py`) written by a thin XLSX writer (`export/xlsx.py`).

**Order of work.** (1) XLSX tables, built. (2) Floor plan per storey as PDF, DXF, SVG and PNG, built. (3) Sections. (4) Elevations. Each step ends with an export a human can open.

**Libraries.** openpyxl (MIT) for XLSX, ezdxf (MIT) for DXF, reportlab (BSD) for PDF: pure Python, vector output, no system packages. The licence of each is checked before it is added.

**Commands.** `uea export pdf|dxf|xlsx [level]`, next to `ifc`, `svg` and `png`. Defaults carry the rest, so the help stays small. `export svg|png` shows the same sheet as the PDF, so an agent can look at what a human gets; `render` stays the working plan with the ids of the elements.

**Drawing conventions** (defaults, for the plan steps):

| | |
|---|---|
| Sheet | A3 landscape, 1:100, title block bottom right. A larger house gets 1:200 or A2. |
| Cut walls | Load-bearing solid dark, non-load-bearing lighter. In Umbau projects Bestand grey, Abbruch yellow, Neu red. |
| Dimensions | Three outer chains per side: overall, wall pieces and axes, openings. |
| Room stamp | Name, number, finished area. |
| Heights | Height marks with ±0.00 at the finished floor of the lowest storey above ground. |
| Title block | Project, storey, scale, date, plan number, revision. The signature field stays empty and the sheet says "Entwurf – nicht unterzeichnet": a human signs. |
| DXF layers | Readable German names per discipline and element, such as `A-WAND-TRAG`. An office-supplied layer table can replace them later. |
| Level of detail | Entwurf. Permit and construction drawings come later (`ROADMAP.md`). |

**The floor plan sheet (built, `export/sheet.py`).** One sheet per storey, the same `Drawing` in all four formats.

- **Sheet and scale.** The first of A3 1:100, A3 1:200, A2 1:100, A2 1:200, A1, A0 (to 1:500) on which the plan with its chains fits, centred in the frame, else above or left of the title block. The frame is 20 mm from the left edge (binding margin) and 10 mm from the others; the title block is 185 x 55 mm at the bottom right.
- **Millimetres on paper.** Pens, text and the chain spacing are written in mm and turned into plan metres by the scale (`Sheet`), so 0.35 mm is 0.35 mm at any scale. Cut walls: 0.35 mm outline; frame 0.7 mm; dimensions 0.13 mm with 0.35 mm slashes; text 2.0 to 2.5 mm, captions 3.5 mm.
- **Walls.** The structural cores are filled shapes, unioned per group (so corners and T-joins have no seams), with the openings and niches cut out as real gaps: the jambs are the outline of the shape, not a white box on top. The finish layers are a light band beside the core. Load-bearing walls are dark, others mid grey. As soon as one element on the storey is Bestand, Abbruch or temporary, the colours of an Umbau apply (Neu red, Bestand grey, Abbruch yellow, dashed).
- **Openings.** Windows as three lines across the opening, doors with the leaf and the swing (`door_swing`, shared with the working plan), doors without a leaf, such as sliding doors, like windows. Every opening is drawn as cut: windows above the cut plane are not yet dashed.
- **Dimension chains** (`side_chains`). Per side: openings and piers along the facade, the faces of the walls that run into that side, and the overall length, nearest chain first. They are Rohbau dimensions (core faces). Numbers in m with two or three decimals and a comma (`1,135`). The numbers stand on the building's side of the line and the extension lines of each chain start at the line before it, so no line crosses another chain's numbers; a number wider than its segment moves up a row. Open: narrow segments (0,115) still touch their slashes; facades in a notch of an L- or U-shaped plan get no chain of openings.
- **Axes.** Grid lines are stubs from the building edge to a bubble outside the chains: x grids at the south, y grids at the west.
- **Room stamps** (id, name, finished area), set where no stair is. Stairs with the walking line, the number of risers and riser and tread in cm, placed beside the stair. Slab openings dashed with a cross; a stair coming from below dashed.
- **Title block.** Bauvorhaben, Planinhalt, Maßstab, Format, Plan-Nr., Stand (date and batch of the model), and empty fields for Bauherr, Planverfasser and Unterschrift. "ENTWURF – nicht unterzeichnet" is printed on every sheet. The project format has no fields for client or author yet.
- **Not yet drawn:** a north arrow (the project has no north direction), roof outlines on the top storey, windows above the cut plane as dashed outlines, height marks (the sheet gives OKFF in the title block; marks come with the sections), furniture and sanitary objects.
- **DXF.** Model space in mm (`$INSUNITS` = millimetre; DXF readers assume mm), items on German layers (`A-WAND-TRAG`, `A-WAND-NICHTTRAG`, `A-WAND-PUTZ`, `A-WAND-BESTAND`, `A-WAND-ABBRUCH`, `A-TUER`, `A-FENSTER`, `A-NISCHE`, `A-TREPPE`, `A-AUSSPARUNG`, `A-RASTER`, `A-BEMASSUNG`, `A-RAUM-TEXT`, `A-RAHMEN`, `A-SCHRIFTFELD`). The frame and title block are items at the scale of the sheet, so the file plots as it is at 1:100. Fills are solid hatches, line weights come from the pens (hundredths of mm), dashes are linetypes. Dimensions are lines and text, not DIMENSION entities, so they look the same in every output. The header extents are set, because programs that read them collapse a drawing that keeps the defaults. LibreOffice's import shows even a trivial ezdxf file without its lines, so the file was checked with ezdxf (audit, read-back, its SVG renderer) and not with LibreOffice.
- **PDF.** One page of the sheet's paper size, vector, Helvetica; the builder keeps to Latin-1 characters.

**Tables (built).** One workbook per export, one sheet per table, in German: Räume, Wände, Öffnungen, Decken, Dächer, Treppen and Mengen. A sheet with no rows is left out. `uea export xlsx [level]` writes `out/<project>.xlsx`, or `out/<project>-<level>.xlsx` for one storey, and every table is then limited to that storey.

- **Rohbaumaße, no deduction rules.** Quantities are taken on the structural sizes: wall length and area between the wall ends in the core layer, openings as built (Maueröffnung), slabs by their net area. The VOB/C deduction rules belong to the Leistungsverzeichnis (`FUTURE.md`), not to a table of the model. Each sheet says so.
- **Wall area** is the area under the wall's top profile (a gable wall is a trapezoid sum, not height times length). Gross minus the doors and windows is net; the core volume is net times the core thickness. A wall without a top (no slab or roof above it) has no area, and the sheet lists it instead of counting zero.
- **Fertigfläche is not Wohnfläche.** The room table gives the shell and the finished area and says that the Wohnfläche is the calculator's job (`uea calc wofl`).
- **Roof area** is the sloped area of the roof planes including the overhangs, from the same planes the IFC export uses (`roof_pieces`), so a hip roof counts its hip planes.
- **Status.** Every table has a status column. Sums leave out demolished elements, and `Mengen` keeps new, existing and demolished apart, so an Umbau lists its Abbruch quantities on their own.
- **Values, not formulas.** The code has calculated them. Cells keep six decimals and the number format shows two or three, so a SUM in the sheet equals the sum row, and the sheets agree with each other.
- **The stamp** in every sheet names the batch it was derived from and says it is not checked and not signed.

## Alternatives

- **PDF by way of DXF** (ezdxf's drawing add-on needs matplotlib): heavy, and the PDF would depend on a second renderer. Drawing both from `Drawing` is simpler.
- **DXF in metres:** the plan units, and what ArchiCAD offices use, but readers assume mm and a drawing in metres collapses in some of them. mm is declared and written.
- **DIMENSION entities in the DXF:** editable in CAD, but they need their own styles and render differently in every program; the PDF would still need its own drawing of them. Lines and text look the same everywhere. They can follow if an office asks.
- **A paper-space layout with a viewport** for the frame and title block: what an experienced CAD operator builds. A frame at scale in model space plots the same and survives every import, so it comes first.
- **PDF from SVG** (cairosvg, LGPL, needs the Cairo system library): an extra system dependency for agents' machines.
- **Formulas in the XLSX** (SUM, product of length and height): they tempt a human to change a cell and break the link to the model, and a viewer that does not calculate shows empty cells. The model is the source of truth, so the sheet shows its values.
- **Rounded cell values:** the sum of rounded cells differs from the rounded sum, and two sheets then disagree in the last digit.
- **One long table of all elements:** each kind has different columns, and a filterable sheet per kind is what an office expects.
- **ISO 13567 or the AIA scheme for layers:** the scheme texts are licensed or American. A readable own scheme that an office table can replace costs less now.

## Consequences

- `opening_type` and `roof_pieces` moved from the IFC writer to `packs/arch/geometry.py`, so tables and IFC share them.
- openpyxl (MIT, with `et-xmlfile`), ezdxf (MIT) and reportlab (BSD, with fonttools, MIT) are core dependencies, all pure Python.
- `export svg|png` now shows the printed sheet; the working plan with element ids is `render`.
- `Drawing` got a `Sheet`, circles and rotated text; the old plan builder (`plan.py`) is unchanged and its output is identical.
- The help grew by eight tokens (`bench/results.md`); the token tasks are unchanged.
- The sum of a table is not a certified quantity take-off. A human who signs a Leistungsverzeichnis checks the numbers.

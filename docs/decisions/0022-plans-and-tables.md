# 0022: Plans and tables for humans

Status: Accepted (tables built; DXF, PDF, sections and elevations to follow)
Date: 2026-10-08

## Context

Phase 2 of `ROADMAP.md` makes the exports an architect or Fachplaner can read: floor plans, sections and elevations as DXF and PDF in German drafting conventions, and XLSX tables. Today there is one neutral `Drawing` (polygons, lines, arcs, text) that renders to SVG and PNG for agents (`ARCHITECTURE.md` §9). It has no scale, line weights, hatches, dimensions, sheet or title block, and no table output.

## Decision

**One model, many outputs.** `Drawing` grows what a drawing needs (scale and sheet, pen classes instead of colours, hatches, dimension chains, text styles, layers). SVG, PNG, DXF and PDF all render from it, so they cannot differ. Tables are plain data (`export/tables.py`) written by a thin XLSX writer (`export/xlsx.py`).

**Order of work.** (1) XLSX tables, built. (2) Floor plan per storey as DXF and PDF. (3) Sections. (4) Elevations. Each step ends with an export a human can open.

**Libraries.** openpyxl (MIT) for XLSX, ezdxf (MIT) for DXF, reportlab (BSD) for PDF: pure Python, vector output, no system packages. The licence of each is checked before it is added.

**Commands.** `uea export xlsx|dxf|pdf [level]`, next to `ifc`, `svg` and `png`. Defaults carry the rest, so the help stays small.

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
- **PDF from SVG** (cairosvg, LGPL, needs the Cairo system library): an extra system dependency for agents' machines.
- **Formulas in the XLSX** (SUM, product of length and height): they tempt a human to change a cell and break the link to the model, and a viewer that does not calculate shows empty cells. The model is the source of truth, so the sheet shows its values.
- **Rounded cell values:** the sum of rounded cells differs from the rounded sum, and two sheets then disagree in the last digit.
- **One long table of all elements:** each kind has different columns, and a filterable sheet per kind is what an office expects.
- **ISO 13567 or the AIA scheme for layers:** the scheme texts are licensed or American. A readable own scheme that an office table can replace costs less now.

## Consequences

- `opening_type` and `roof_pieces` moved from the IFC writer to `packs/arch/geometry.py`, so tables and IFC share them.
- openpyxl is a core dependency (MIT, pure Python). It adds `et-xmlfile` (MIT).
- The help line for `export` grew by three tokens (`bench/results.md`); the token tasks are unchanged.
- The sum of a table is not a certified quantity take-off. A human who signs a Leistungsverzeichnis checks the numbers.

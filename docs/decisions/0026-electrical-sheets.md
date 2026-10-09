# 0026: The electrical sheets, slice 2: installation plan and board diagram

Status: Accepted (slice 2 built; slice 3a in 0027; slice 3b in 0028)
Date: 2026-10-09

## Context

Slice 2 of phase 3 (`0025-electrical-devices.md`) makes the electrical design something an Elektroplaner can read: a plan per storey with the devices on it and a diagram of the distribution board. Haus Müller's draft exports (`docs/prototype/haus-mueller/exports/elektro-EG.png`, `verteilung-b1.png`) showed what an office expects; the sheets follow them and use the same sheet, pens, frame and unsigned title block as the architecture sheets (`0022-plans-and-tables.md`).

## Decision

**Commands.** `uea export pdf|dxf|svg|png elec` writes every electrical sheet, `elec:EG` the installation plan of a storey, `b1` (or `elec:b1`) the diagram of a board. With no name the export now also writes them, after the architecture. Files: `out/elec-EG.pdf`, `out/board-b1.pdf`.

**The installation plan** (`export/install.py`, `export/symbols.py`):

- The floor plan is the background: walls, doors with their swings, windows and stairs in grey, room names small. No dimension chains; they belong to the architecture sheets.
- A symbol for every device, drawn by us and simplified, in the spirit of DIN EN 60617 and not copied from it; the title block says "Symbole vereinfacht, in Anlehnung an DIN EN 60617". A socket is a half circle for each outlet on the room side of the wall face; a connection a circle with a cross; a switch a circle with a stroke for each channel and a stroke on both sides for a two-way switch (a luminaire with two switches), filled for a dimmer; a luminaire a circle with a cross; a smoke alarm a circle with RM; a data outlet a triangle for each port; a board a dark box.
- **Colour by circuit.** Each circuit has a colour (ten, in the order of the circuits, repeating after ten). Its devices and its luminaires, which take the circuit of their switches, have it, and the circuit's id stands beside the device. Luminaires are grey with their own id.
- A dashed line joins each switch to the luminaires it controls on that storey.
- **Scale and sheet.** 1:50 where it fits (A3, then 1:100 and larger sheets). The legend stands left of the title block and is as high as it: the symbols that occur and the circuits on the sheet with breaker, cable and label, in up to three columns. Beyond 36 circuits the legend points to the table.
- DXF layers, German, with `E-` for the electrical sheets: `E-STECKDOSE`, `E-ANSCHLUSS`, `E-SCHALTER`, `E-LEUCHTE`, `E-RAUCHMELDER`, `E-DATEN`, `E-VERTEILER`, `E-SCHALTLINIE`, `E-BESCHRIFTUNG`, `E-LEGENDE` and the background `E-GRUND-WAND`, `-TUER`, `-FENSTER`, `-TREPPE`, `-TEXT`. The frame and title block keep the layers of the other sheets.

**The board diagram** (`export/board.py`): a single-line diagram, not to scale (1:1 sheet, "o. M."). From the top: the supply (Netz/HAK, not in the model), the meter, the SLS (the `main=` of the board), the busbar; the SPD; each RCD with its rating and type; under it its circuits as boxes with breaker and poles, an arrow, the circuit id in its colour, the phase, the cable, the label, and what hangs on it (`3 Dosen / 5 Steckpl.`, switches, luminaires, connections, the target of a feed). A media board has no diagram.

- **Phases are derived** (`share_phases`): the circuits of a board in the order of their RCDs and ids, each single-phase circuit to the phase with the least load so far, L1 first when equal; a circuit counts with its declared load and at least 1000 W, a three-phase circuit a third on each phase. This balances the board without a load calculation and says so on the sheet. The phase is in `uea get c1` and in the circuit table.
- **The occupation of the field is derived** too: rows of 12 TE; an SPD takes 4 TE, each RCD 4 TE and each breaker 1 TE per pole; a row that is full goes on in the next ("fi1 (Forts.)"). The assumptions are written on the sheet; the real widths of a manufacturer replace them later.
- The sheet is A3 where the field at the foot, which is short, fits beside the title block, otherwise a larger sheet.

**Not drawn yet.** Cable routes and lengths (slice 3), the Installationszonen, device heights (the table has them), the installation of heat, vent and plumbing, a separate legend of switch types, several boards fed from each other, an outdoor sheet.

## Alternatives

- **A symbol set copied from DIN EN 60617:** the drawings are the standard's content. Simplified shapes that read the same cost nothing and say so.
- **Wire lines for every circuit:** a circuit's route is slice 3. Colour and the id beside the device show the grouping without inventing a route.
- **Phases by rotation per RCD** (the draft): the board comes out unbalanced when the groups differ in size; the greedy rule balances by the load that is known and treats the rest as equal.
- **The legend above the title block:** it takes height from the plan, and at 1:50 the plan needs it. Beside the title block both fit on A3.

## Consequences

- `Paper.title_block` takes a scale text, `place` and `fit_sheet` take a legend (height or width) and the scales to try; `PlanSheet` and `SectionSheet` are the public bases of the plan sheets.
- The circuit table has the derived phase; the export help names the new scopes (the bench's reading is unchanged).
- A person who signs the installation checks the sheets and the numbers; UEA does not certify them.

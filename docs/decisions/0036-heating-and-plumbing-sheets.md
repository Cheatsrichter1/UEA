# 0036: Heating and plumbing sheets, slice 6e

Status: Accepted (slice 6e built)
Date: 2026-10-11

## Context

Slices 6a to 6d built the Heizlast, the heating elements and the plumbing (`0033` to `0035`). What a Fachplaner hands over is still missing: plans, the Heizungsschema, tables and a calculation report someone can sign. Haus Müller's hand-drawn `exports/heizungsschema.png` shows what an office expects. The electrical sheets (`0026`) set the pattern: the same paper, pens, frame and unsigned title block.

## Decision

**Plans per storey** (`export/tga.py`), drawn like the installation plan, with the floor plan in grey, 1:50 where it fits, and a legend left of the title block:
- **`uea export pdf|dxf|svg|png heat:EG`**:
  - each underfloor heating fills its room in pale red, with its area, loops and output under the room's name, and a dashed line to its manifold;
  - manifolds, radiators (with their output), generators (with kW) and tanks as symbols.
  - Plan numbers H-01, H-02, ….
- **`plumb:EG`**:
  - the fixtures as boxes with their short mark (WT, SP, WC, DU, …);
  - the meter, risers, stacks, the sewer connection and the tank that heats the water;
  - the derived pipes as right-angled lines, first along x, then along y: cold green, hot orange, waste brown and dashed, side by side.
  - Risers and stacks are drawn on every storey they pass. The note says the lines are a derived shortest tree, not a route.
  - Plan numbers S-01, ….
- `heat` and `plumb` write all of them, and an export with no name writes them after the electrical sheets.
- DXF layers start with `H-` and `S-`.

**The Heizungs- und Trinkwasserschema** (`export/schema.py`, `heat:schema`, `out/heat-schema.pdf`, H-00) is a diagram, 1:1, "o. M.", after the prototype:
- generators and tanks on the left;
- supply and return to one row per manifold. Under its header, one zigzag per derived loop of each underfloor heating, and a box per radiator, with room, loop k/n, area and output.
- Radiators fed straight from a tank or generator get a row of their own.
- At the foot: cold water from the meter, hot water from the tanks that heat it, to each fixture.
- What it leaves out is written on it: pumps, valves, safety group, expansion vessel, circulation.

**Tables** (`export/tables_tga.py`, in `uea export xlsx`):
- Heizflächen: each emitter with its room, type, area, loops, loop length, pipe and output.
- Heizkreisverteiler: outlets, used and free.
- Sanitärobjekte: water, outlet height, and the length to the meter, the tank and the sewer.
- Rohrleitungen: every section with its kind, length and bends.
- Rohrmengen: the length of each network and of the underfloor pipe by type.
- Sizes are not in the tables: they need the office's tables (`uea calc water`, `drain`).

**Calculation reports as PDF** (`export/report.py`): `uea export pdf heatload` sets `out/heatload.md` on A4.
- Each page has a header with the calculator, version, kind and batch, and "ENTWURF – nicht unterzeichnet"; a footer has the page number.
- The report ends with an empty block for name, place, date and signature.
- It works for every calculator, `wofl` to `drain`, and is how the Heizlast report reaches the person who signs.
- It refuses a result when the model files have changed since the calculation (the record's file hashes), and names the command that computes it again.
- It needs a font with Greek letters (DejaVu Sans, Liberation Sans, Noto Sans or Arial, where systems keep them). Without one it spells the letters out in Helvetica.

## Alternatives

- **Plumbing and heating on one plan.** At 1:50 the pipes of the bath, the loops' labels and the manifolds crowd each other. Two plans follow the trades that read them.
- **Pipe sizes on the plan.** They depend on the office's tables, so a sheet would change from machine to machine (`0033`). The calculation report carries them.
- **The report rendered from the record (JSON) with its own layout per calculator.** The Markdown is what the calculator already writes for humans; one renderer serves all.
- **Signing the stale result with a warning.** A signature on numbers that no longer match the model is the error to prevent; computing again is one command.
- **A plumbing riser diagram (Strangschema).** The foot of the Heizungsschema shows the drinking water by fixture. A Strangschema with storeys and sizes can follow.

## Consequences

- Haus Müller's heating and plumbing export: H-01 and H-02 (A3 1:50), the Heizungsschema (A3), S-01 and S-02, and five more sheets in the XLSX file. The Heizungsschema has the 8 and 7 loops of the two manifolds, and the seven fixtures, the four with hot water from t1.
- Tested on the box houses (`tests/test_tga_export.py`):
  - the labels and layers of the heating plan;
  - the pipe lines of the plumbing plans; risers and stacks on the upper storey;
  - the schema's loop columns and fixtures;
  - the table rows against the derived lengths;
  - the report's record checks;
  - on the command line: the sheets and the report, refused as a picture and once the model changed.
- The export help names the new scopes; the bench's reading and the token task set are unchanged.
- Open:
  - heating pipe routes and sizing, and the hydraulic balance;
  - a plumbing Strangschema;
  - the sizes on the sheets once a result is fresh;
  - the plumbing and heating in the IFC export;
  - the manifold against its niche's width.

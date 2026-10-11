# UEA roadmap

The order of work, from nothing to the Einfamilienhaus demo. Each phase ends with something an agent can actually do. For what UEA is see `VISION.md`; for how it is built see `ARCHITECTURE.md`; for later ideas see `FUTURE.md`. The order of the packs is `docs/decisions/0006-pack-order.md`.

Status, October 2026: phase 0 is done, phase 1 is nearly done, phase 2 is built, phase 3 is built apart from the leftovers below, phase 4 is built apart from the test with an office's file, phase 5 waits for the choice of the comparison tool, and phase 6 is built: U-values, the Heizlast, the heating elements, the plumbing, the sheets, the heating pipes with the hydraulic balance, and the Strangschema; its review by a licensed person is open. Phase 7 is built: ventilation units, air terminals, ducts, the Lüftungskonzept and the duct sizing.

## Phases

| Phase | Content | Done when |
|---|---|---|
| 0. Foundation | Git repo, Apache-2.0 licence, Python project setup, CI, decision records | An empty `uea` CLI installs and its tests run in CI |
| 1. Core + architecture | File format, operations, batches, history and revert, requests and waivers, validation, read commands; levels, grids, build-ups, walls, slabs, roofs, stairs, openings, rooms; Bestand status; Wohnfläche per WoFlV as the first `norm` calculator; IFC export; a simple plan image for agents; the token task set | An off-the-shelf agent builds the shell of the EFH, roof included, from a brief, and a human can open the IFC in a free viewer |
| 2. Plans and tables | DXF/PDF floor plans per storey and discipline, sections and elevations, in German drafting conventions; XLSX tables (rooms, walls, quantities) | An architect would accept the floor plans, sections and elevations as design drawings (Entwurf) |
| 3. Electrical | Devices (sockets, switches, data), luminaires (kept in the light pack), circuits, distribution board, cable runs, feeds to the powered elements of other packs; first `norm` calculators (cable sizing, voltage drop) on office-supplied tables; electrical plan and socket/circuit tables | The agent plans the EFH electrics from a brief and the exports look like a plan an Elektroplaner would recognize |
| 4. IFC import | Architecture from an architect's IFC into `project.uea` and `arch.uea`; re-import of new versions with stable ids | A real project from an office imports, and the agent plans its electrics on it |
| 5. Benchmark v1 | Fixed task set from phases 1–4, run through UEA, through a conventional tool driven by an agent, and by a human drafter; tokens, time and errors counted | Results published in the repo, method reproducible |
| 6. Plumbing + heating | Pipe networks, fixtures, heat generator and emitters; Heizlast per DIN EN 12831-1 as a `norm` calculator with a validation report | The agent plans plumbing and heating for the EFH, and the Heizlast matches the standard's worked examples, run locally on the office's tables |
| 7. Ventilation | Units, ducts, outlets | The EFH demo is complete apart from structural |
| 8. Structural | Load-bearing elements, loads, frame analysis on an open-source solver | Only together with a licensed engineer who reviews the validation |

### Phase 1: where it stands

Built and tested (`src/uea/`, `tests/`):

- File format, strict parser and canonical writer (`docs/decisions/0013-canonical-line-format.md`).
- Operations, atomic batches, placeholders, history, revert, edits outside UEA (`docs/decisions/0014-operations-and-history.md`).
- Requests and waivers, validation with issue codes, the reference graph between disciplines.
- Read commands: `show`, `get`, `find`, `check`, `log`, layered `help`; every command and kind listed in `docs/reference.md`, generated from the code.
- An English-only format and CLI; exports for humans stay German (`docs/decisions/0017-english-format.md`).
- Levels, grids, build-ups, walls, openings, niches, slabs, voids, gable, half-hip, shed, hip, mansard and flat roofs, separators, rooms with shell and finished areas, heights and volumes (`docs/decisions/0015-rooms-and-finishes.md`, `0016-roofs.md`, `0021-roof-shapes.md`). Bestand status.
- Walls in any direction between two points, with joins to the walls they touch and openings placed along them (`docs/decisions/0018-raw-walls.md`). Straight, quarter-turn, winder and half-turn stairs (`0019-stair-shapes.md`). Roofs over L-, T- and U-shaped outlines, one roof per wing (`0020-roof-parts.md`).
- Wohnfläche per WoFlV as the first `norm` calculator, with a validation report (`docs/validation/wofl.md`); custom calculators from a project's `calc/`.
- Plan images (PNG, SVG) per storey and the IFC4 export, schema-valid by IfcOpenShell's validator.
- The token task set (`bench/`) with reference solutions: the Haus Müller shell, roof included, costs about 2,400 tokens of commands and output.
- The agent test (`bench/agent/`): a brief, a `uea` that logs every call, and a comparison with the reference by geometry.

Still open for phase 1:

- An off-the-shelf agent builds the EFH shell from a brief. First run, 2026-10-07 (`bench/agent/results.md`): Claude Opus matched the reference in all 58 checked facts, Sonnet in 55 (it added eaves walls in the attic), Haiku did not finish. Open: a rerun on the English format, and how to model the attic over the eaves walls.
- A human opens the IFC in a free viewer (it validates and every shape builds in IfcOpenShell).
- Not covered yet: roofs over outlines turned by another angle or trapezoid, curved and spiral stairs, winders in a half turn, and wall joins other than "run to the far face of the wall it touches" (no mitre control, no join order).

### Phase 2: where it stands

The designs are `docs/decisions/0022-plans-and-tables.md`, `0023-sections.md` and `0024-elevations.md`. Built: the XLSX tables (`uea export xlsx [level]`): rooms, walls, openings, slabs, roofs, stairs and quantities per type, in German. The floor plan sheet per storey (`uea export pdf|dxf|svg|png [level]`): A3 1:100 or the first sheet and scale that fit, cut walls with real openings, door swings and window symbols, stairs, room stamps, three dimension chains per side, grid axes, an unsigned title block; DXF in mm on German layers. The sections (`0023-sections.md`; a `section` element in `arch.uea`, `uea export pdf|dxf|svg|png <name>`): cut walls, slabs, roof and stair in profile with their layers, openings, the view behind the cut with hidden lines removed, height marks, dimension chains, room labels with the clear height, the ground line, and the cut lines in the floor plans. The four elevations (`0024-elevations.md`; `uea export pdf|dxf|svg|png north|east|south|west`): walls with openings, slab edges, the roof with its thickness, the ground, height marks and dimension chains. Open on the section: the stair rail, niches behind the cut, a cut that jogs. Open on the elevation: facade materials, demolished walls of an Umbau, opening symbols. Open on the plan: a north arrow (needs a north direction in the project), roof outlines, dashed windows above the cut plane, notches in an L-shaped facade, client and author fields for the title block.

### Phase 3: where it stands

The design is `docs/decisions/0025-electrical-devices.md`; the phase goes in three slices. Slice 1 is built: the electrical pack (`elec.uea`: board, rcd, circ, sock, conn, switch, data, smoke, feed) and the luminaires of the light pack (`light.uea`), devices placed on wall faces and in rooms by anchors, a luminaire wired by the switches that control it (single, two-way, intermediate), the load of each circuit against its breaker, twelve checks (a device in an opening, close to one, outside its wall, a switch behind the open leaf of a door, an overloaded circuit, a luminaire without a switch, ...), and the XLSX sheets Verteiler, Stromkreise, Installationsgeräte and Leuchten. Haus Müller's draft electrics load. Slice 2 is built too (`0026-electrical-sheets.md`): the installation plan per storey (`uea export pdf|dxf|svg|png elec:EG`, A3 1:50, symbols coloured by circuit, switching lines, legend) and the diagram of each board (a board id: single-line, the phases derived, the field in rows of 12 TE). Slice 3a is built too (`0027-cable-routes.md`): the cable of every circuit as the shortest rectilinear tree from its board, with an allowance per run, the home runs of the data outlets, `uea get` lines, and the XLSX sheets Leitungen and Kabelmengen. Slice 3b is built (`0028-norm-tables-and-electrical-calculators.md`): the office's norm tables as CSV files (`uea data add`), the calculators `cable` (cable against its breaker) and `vdrop` (voltage drop) on them with validation reports (`docs/validation/cable.md`, `vdrop.md`, not yet reviewed by a licensed person). Open in phase 3: the minimum equipment of a room (`W-ELEC-010`, as a calculator with its own table), the worked examples of the standards as a private test suite, and what the end-to-end Haus Müller electrics still lack (see the Todo).

### Phase 4: where it stands

The designs are `docs/decisions/0029-ifc-import.md`, `0030-ifc-import-shapes.md`, `0031-ifc-import-files.md` and `0032-bcf-requests.md`; the phase went in three slices. Slice 4a: `uea import ifc <file> --by <who>` reads storeys, walls (an axis through the core with a type from the layers), doors and windows, one floor slab per storey (its finish becomes `fb` and a floor type) and spaces (rooms, with a `sep` where two are open to each other) from an architect's IFC, reports everything it does not map, and updates the model on a newer file by IFC GlobalId without touching what was edited in UEA. Slice 4b: grids along x or y, openings in floor slabs (tied to the stair under them with `over=`, else rectangles), and stairs and roofs. A stair or roof is fitted by building the UEA candidates with UEA's own layout code and keeping the one that lies where the file's faces lie; walls that end under a fitted roof get `top=`; what fits nothing is reported with the reason. Slice 4c: files in any length unit, plans in survey coordinates or turned off the axes (moved and turned, and kept so for later files), one building per import (`--building`), walls in parts, curtain walls as walls with windows over their face, niches, and `uea export bcf`: the requests to the architect as BCF topics that select the elements in the architect's own file. Tested on hand-built IFC files in IFC2X3, IFC4 and IFC4X3, and on UEA's own exports (Haus Müller, seven roof shapes, nine stairs), relabelled as another program's. Open: **the test with an office's file**, which the phase's "done when" needs (the user runs it): it imports, the agent plans its electrics on it, and the BCF opens in the architect's program. What the import reports instead of guessing stays open for later work: curved walls, curtain walls over several storeys, L-shaped roofs in one IfcRoof, dormers, spiral stairs, openings without a fill (the lists are in `0030` and `0031`); reading the architect's BCF replies back (`0032`).

### Phase 6: where it stands

The design is `docs/decisions/0033-u-values-and-heizlast.md`, `0034-heating-elements.md`, `0035-plumbing.md`, `0036-heating-and-plumbing-sheets.md` and `0037-heating-pipes-and-strangschema.md`. The order: the Heizlast first, because emitters are sized to the room loads (6a, 6b); then the heating elements in `heat.uea` with each emitter against its room's load (6c); plumbing with fixtures, pipe runs and pipe sizing for drinking water (DIN 1988-300) and drainage (DIN 1986-100) as `norm` calculators (6d); the Heizungsschema, the Heizlast report and the sheets (6e). Slice 6a: `uea calc uvalue`, the U-value of each build-up as the rooms use it (DIN EN ISO 6946). Slice 6b: `uea calc heatload`, the Heizlast of each room and of the building (DIN EN 12831-1 with DIN/TS 12831-1), from the surfaces around each room and what lies beyond them, with conductivities, design temperatures and coefficients from the office's tables. Both are not yet reviewed; the deviations from the standard (the ground without U_equiv, the infiltration by a room formula) are listed in `docs/validation/heatload.md`. Slice 6c: `heat.uea` with heat generators, storage tanks, manifolds (in niches or on walls), underfloor heating and radiators; the loops of each underfloor heating derived from the type's spacing and longest loop, manifolds checked against their outlets, and `uea calc heatload` sets each room's emitters against its load and the generators against the building's; `feed` cables now reach the heat pump. Haus Müller's heating loads. Slice 6d: `plumb.uea` with fixtures, the meter, risers, stacks and the sewer connection; the cold, hot and waste-water pipes derived as the shortest rectilinear trees, like the cables; hot water from the heating's tank; `uea calc water` (DIN 1988-300) sizes the drinking-water pipes and checks each fixture's pressure, `uea calc drain` (DIN 1986-100) sizes the waste-water pipes and checks the unvented branches. Both are not yet reviewed (`docs/validation/water.md`, `drain.md`). Haus Müller's plumbing loads, with the stack request q3 asked for. Slice 6e: the heating and the plumbing plan of each storey (`uea export pdf heat:EG`, `plumb:EG`), the Heizungs- und Trinkwasserschema (`heat:schema`), the tables Heizflächen, Heizkreisverteiler, Sanitärobjekte, Rohrleitungen and Rohrmengen, and every calculation report, the Heizlast's among them, as an A4 PDF to sign (`uea export pdf heatload`), refused once the model has changed; the reports are set in DejaVu Sans, which ships with UEA. Slice 6f (`0037`): the heating pipes from generator to tank, manifolds and radiators, derived as trees like the plumbing's and drawn on the heating plans; `uea calc hydronic` sizes them on each room's Heizlast and balances the system (valve Δp and kv per circuit, the throttle of each branch, the pump heads); the Strangschema of the plumbing (`uea export pdf plumb:schema`). Open: mixing valves and a spread per circuit, circulation, pipe runs along shafts and installation walls, emitter output per DIN EN 1264 and DIN EN 442, the standard's worked examples as a private test suite, and the review of `uvalue`, `heatload`, `hydronic`, `water` and `drain` by a licensed person (the user arranges it).

### Phase 7: where it stands

The design is `docs/decisions/0038-ventilation.md`. Built: `vent.uea` with central units with heat recovery (`ahu`), decentral units through the facade (`fan`: push-pull pairs, the second half derived, exhaust fans) and air terminals (`air`: supply and extract in the rooms, outdoor and exhaust air on the facade); the ducts of each unit derived as trees like the pipes; five checks; `feed` lines reach the units. `uea calc airflow` (DIN 1946-6 on the office's tables) gives the dwelling's flows at the four levels, whether a ventilation measure is needed, and each room's flow against the units; `uea calc ducts` sizes the ducts and sets each side's fan pressure against the unit. The ventilation plan of each storey (`uea export pdf vent:EG`) and four XLSX tables. Haus Müller's first design, two pairs of decentral units, gave 60 of the 164 m³/h the nominal level needs with synthetic tables, and the wet rooms had no extract; it now has a central unit in the HWR that gives every room its flow, with the ducts sized. Open: overflow openings and outdoor air inlets, heat recovery in the Heizlast, the losses of terminals and silencers, ducts along shafts, ventilation in the IFC export, the worked examples as a private test suite, and the review of `airflow` and `ducts`. The phase's "done when" (the EFH demo complete apart from structural) also needs the agent run end to end, which is open.

The **Einfamilienhaus demo** is v1: the sum of phases 1–8, run end to end by one agent, with the benchmark alongside.

After v1, the light pack grows from luminaires into lighting design and photometric calculation (`docs/decisions/0006-pack-order.md`).

## Todo

To be scheduled into the phases above.

### Model

- **Openings without a fill.** Wall and slab penetrations, chases and core drillings (Durchbrüche, Schlitze, Kernbohrungen; `IfcOpeningElement`). Today only niches and slab voids exist. They are the main handoff from the Fachplaner to the architect: a request asks for a chase, and the architect answers with the element.
- **Shafts and installation walls.** Vertical shafts through several storeys, and pre-wall installations (Vorwandinstallation) in WC and bath. Plumbing and ventilation run through them (phases 6 and 7).
- **More roof elements.** Dormers (Gauben), roof windows, a parapet (Attika) on flat roofs, butterfly and barrel roofs, a steeper pitch for the ends of a half-hip. Roofs over a turned or trapezoid outline are open (`docs/decisions/0020-roof-parts.md`, `0021-roof-shapes.md`).
- **Railings and parapets** (`IfcRailing`) on stairs, galleries and balconies.
- **Sun shading.** Roller shutters and external venetian blinds (`IfcShadingDevice`), standard on German houses. Electrical feeds their motors, and they count for summer heat protection.
- **Suspended ceilings and other coverings** (`IfcCovering`). They set a room's clear height and leave space for services above them.
- **Furniture and the kitchen** (`IfcFurnishingElement`). Design drawings show them, and the electrical design places sockets by them.
- **A generic object:** a box with a footprint and a height (`IfcBuildingElementProxy`), for anything that has no kind of its own yet.
- **Balconies, terraces, and a second building** on the site, such as a garage or carport.
- **Curved walls.** Walls on an arc (bay windows, round stair walls) are still extrusions: the footprint is an arc, kept as a true arc in the IFC and approximated by segments for areas. Builds on walls in any direction (`docs/decisions/0018-raw-walls.md`). Open: how the position grammar places an arc (centre and radius, or two ends and a bulge), how openings are positioned along it, and finished areas with curved finish layers.
- **Facades.** Curtain walls (Pfosten-Riegel, `IfcCurtainWall`): a grid of mullions and transoms with glass or opaque panels, placed like a wall. Render, ETICS (WDVS) and ventilated cladding can already be written as layers of a wall type. Free-form, double-curved facades stay out: they need a general geometry kernel (`VISION.md`), so they would be a separate pack on an existing kernel, like mechanical parts (`FUTURE.md`).

### Larger buildings

- **Apartments as zones** (`IfcZone`), with a Wohnfläche per apartment.
- **Lifts** (`IfcTransportElement`) and stairwells with landings.
- **Split levels.**
- **Timber-frame walls** whose layers mix studs and insulation, which the U-value calculation must handle.

### Services

- **Cable paths along the installation zones** (phase 3). The lengths exist (`0027-cable-routes.md`, rectilinear). Open: the zones themselves (Installationszonen) as the graph the cables run on, shafts and chases, the runs drawn on the plan.
- **Pipe and duct paths** (phases 6 and 7). Plumbing and heating networks and the ducts are derived as rectilinear trees, sized and counted (`docs/decisions/0035-plumbing.md`, `0037-heating-pipes-and-strangschema.md`, `0038-ventilation.md`). Open: runs along shafts and installation zones.

### Calculations

- **Areas and volumes per DIN 277** (BGF, NRF, BRI) as a `norm` calculator. The building application needs them, and they are the basis of a cost estimate per DIN 276 (`FUTURE.md`).
- **U-values of air layers and inhomogeneous layers** per DIN EN ISO 6946 (rafters or studs with insulation between them), and the corrections for fixings and air gaps. Homogeneous layers are built (`uea calc uvalue`, `docs/decisions/0033-u-values-and-heizlast.md`).
- **Setbacks and plot ratios:** Abstandsflächen per Landesbauordnung, GRZ and GFZ per BauNVO. Needs the site plan below; the rules differ per Land.
- **GEG compliance** and the Energieausweis, later.

### Checks

Rule checks of the kind Solibri runs, reported with issue codes like the existing validators:

- **Landesbauordnung:** minimum clear height of habitable rooms (Aufenthaltsräume), window area relative to floor area (1/8 in most Länder), escape routes.
- **Accessibility per DIN 18040-2:** turning circles, door widths.
- **Fire safety:** fire ratings on types (F90, T30) and fire compartments.
- **Sound insulation per DIN 4109.**
- **Clash detection** between disciplines, once pipes and ducts exist.

### Drawings and lists

Phase 2 builds floor plans, sections and elevations. Beyond that:

- **Site plan** (Lageplan) with plot, terrain and georeferencing (EPSG:25832, DHHN2016 heights).
- **Drawing basics:** dimension chains, room stamps, title blocks, a revision index.
- **Door and window schedules and room data sheets** (Raumbuch).
- **Beyond design drawings:** the building permit set (Genehmigungsplanung) and construction drawings with details (Ausführungsplanung).

### openBIM

- **Property sets** in the IFC export (FireRating, ThermalTransmittance, ...).
- **Custom properties** for an office's own attributes. UEA's strict schema rejects unknown fields, so this needs a design.
- **Classification**, for example DIN 276 cost groups.
- **BCF replies.** Requests go out as BCF (`docs/decisions/0032-bcf-requests.md`); reading the answers of people who work outside UEA back is open.
- **IDS:** check the IFC export against a client's information requirements (AIA), as public projects demand.
- **IFC2x3 export** for older tools.
- **DWG and PDF plans as an underlay**, because many Fachplaner still receive plans that way.

### Construction schedule

- **Construction stages and a timeline for the trades.** Elements belong to a construction stage (1, 2, 3, ...) and a trade (masonry, carpentry, roofing, electrical first and second fix, screed, plaster, ...). From the stages, the quantities and the dependencies between trades (screed after the heating pipes, plaster after the electrical first fix), UEA derives a timeline per trade that the Handwerksbetriebe can work to: a Gantt chart (PDF, XLSX) and `IfcWorkSchedule` in the IFC. Open: whether the stage is written on each element or follows from its kind and trade; where durations come from (quantities times the office's productivity rates); and the word in the format, probably `stage`, because "phase" already names the roadmap phases, and what Revit calls phases are UEA's status flags.

## Token task set

From phase 1 on, a fixed set of agent tasks runs against UEA and counts tokens and errors. Every change to the file format or CLI output is measured on it before it lands. Fewer tokens do not count if weaker agents make more mistakes, so the set measures both. The benchmark in phase 5 adds the comparison with a conventional tool and with a human drafter.

## In parallel: feedback from practice

Start now, before phase 1, and talk to German engineering and architecture offices:

- Which tasks eat the most hours, and which would they hand to an agent first?
- Will one office lend an anonymized real project as a test case?
- What exports and formats must the results come in?
- Which architecture formats do Fachplaner receive (IFC, DWG), and in which quality?

The answers can reorder phases 2–7.

## Open questions

- **Benchmark baseline:** which conventional tool to compare against. Revit with an MCP bridge is the most convincing for offices but needs Windows and a licence. Archicad, or Bonsai (BlenderBIM) as an open-source option, are alternatives.
- **Norm tables:** which tables each `norm` calculator needs, and in what form offices supply them from their licensed copies (`docs/decisions/0008-office-supplied-norm-data.md`).
- **Engineer partner:** who reviews the `norm` calculators, at the latest before phase 8.
- **Type catalogues:** where realistic product and build-up data comes from (manufacturer data, BIM libraries) without licence trouble.
- **Parallel branches:** how two git branches of one project merge their histories and the ids each assigned (`docs/decisions/0009-history-revert-ids.md`).

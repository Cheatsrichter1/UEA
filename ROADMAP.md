# UEA roadmap

The order of work, from nothing to the Einfamilienhaus demo. Each phase ends with something an agent can actually do. For what UEA is see `VISION.md`; for how it is built see `ARCHITECTURE.md`; for later ideas see `FUTURE.md`. The order of the packs is `docs/decisions/0006-pack-order.md`.

Status, October 2026: phase 0 is done, phase 1 is nearly done and phase 2 has started (see below).

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

The design is `docs/decisions/0022-plans-and-tables.md`. Built: the XLSX tables (`uea export xlsx [level]`): rooms, walls, openings, slabs, roofs, stairs and quantities per type, in German. Next, in this order: the floor plan per storey as DXF and PDF in German drafting conventions (scale, line weights, hatches, dimension chains, room stamps, title block), then sections, then elevations.

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

- **Cable paths** (phase 3). Cable runs from the distribution board through the building to every device, along the installation zones (Installationszonen), with lengths for voltage drop, quantities and the electrical plan. The prototype only derived them roughly.
- **Pipe paths** (phase 6; ducts in phase 7). Pipe runs and networks for plumbing and heating with dimensions and lengths, for pipe sizing, the heating schematic and quantities.

### Calculations

- **Areas and volumes per DIN 277** (BGF, NRF, BRI) as a `norm` calculator. The building application needs them, and they are the basis of a cost estimate per DIN 276 (`FUTURE.md`).
- **U-values per DIN EN ISO 6946** from the build-ups. This needs a thermal conductivity per material, from the office's tables (the DIN 4108-4 values are licensed). The Heizlast in phase 6 uses them too.
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
- **BCF** for requests to and from people who work outside UEA (`docs/decisions/0011-ifc-import.md`).
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

# Future

What is open for the first version, what comes after it and in which order, and the ideas and backlog behind them. For what UEA is see `VISION.md`; for how it is built see `ARCHITECTURE.md`; for what is built see `CHANGELOG.md` and `docs/decisions/`.

## Versions

| Version | Content | Section |
|---|---|---|
| v1 (0.1.0) | Architecture, electrical, plumbing, heating, ventilation and structure, planned by one agent for an Einfamilienhaus | Open for v1 |
| v2 | Partial views, then from model to tender: cost estimate, Leistungsverzeichnis, GAEB, bids, fees | Partial views, From model to tender |
| v3 | Office workflows: an agent works the business side, a human approves every outgoing step | Office workflows |
| v4 | Plot evaluation and the watching of public tenders (Ausschreibungen) | Plot evaluation, Tender watching |
| v5 | The agent dashboard | Agent dashboard |

The order is fixed; the content of each version is not.

## Open for v1

What 0.1.0 still lacks is people's work, not code (`CHANGELOG.md`, "Not in this release"):

- **Reviews by licensed people** of the `norm` calculators (`docs/validation/`) and of the structure, which needs an engineer partner (`docs/decisions/0040-structure.md`).
- **The test with an office's IFC:** it imports, an agent plans its electrics on it, and the BCF opens in the architect's program (`docs/decisions/0029-ifc-import.md` to `0032-bcf-requests.md`).
- **The agent runs end to end:** a rerun of the shell on the English format, and the services run (`bench/agent/results.md`). Open on the shell run: how to model the attic over the eaves walls.
- **The benchmark:** the fixed task set (`bench/`) through UEA, through a conventional tool driven by an agent, and by a human drafter, with tokens, time and errors counted. Which tool to compare against is open (below).
- **The standards' worked examples** as a private test suite per office.

The decision records and the code comments refer to the work of v1 by phase number: 0 foundation, 1 core and architecture, 2 plans and tables, 3 electrical, 4 IFC import, 5 benchmark, 6 plumbing and heating, 7 ventilation, 8 structure.

## Partial views

Version 2, first in the version: tenders and cost estimates work on bigger buildings than a house, and those only fit in an agent's context a slice at a time.

Big projects do not fit in an agent's context, even in a compact format. A hospital is millions of tokens (`README.md`). `uea show`, `get` and `find` already read a slice, but an agent also has to work on one: take just the heating and ventilation of the OG, or just board `uv2` with its circuits and their loads, change it, and put the edits back. That is what lets UEA scale, and what lets several agents work on one project at once.

Sketch, on the parts that exist (`ARCHITECTURE.md` §2 to §5):

- **A view is a selector and a base.** The selector names the slice: a discipline and a level (`heat:OG`), an element with what hangs on it (a board with its circuits, devices and cables), a room with everything in it. The base is the batch number of the history at the time of reading.
- **What the view shows.** The selected elements in the usual line format, and the upstream elements they reference (host walls, rooms, levels, types) as read-only context lines, marked as such, so every reference resolves and the checks that need only the slice can run. Ids are the project's own, stable and never reused, so an edit names the same elements as the model.
- **Edits are ordinary batches.** The agent writes operations in the same syntax (`ARCHITECTURE.md` §5) with a scope and a base, for example `uea apply --view <selector> --base 41`. A batch that touches an element outside the slice is rejected. A batch whose base is older than the last change to an element it edits is rejected with the batch that changed it, like a revert (§5). New elements get their ids at the merge, through placeholders as today. History, revert and the issues for other disciplines work unchanged, because the merge is a batch.
- **Several agents.** Agents on views that do not overlap cannot conflict, so they can write in parallel. This also narrows the open question on parallel branches (`docs/decisions/0009-history-revert-ids.md`).
- **Cost.** The read costs what the slice costs, not what the project costs, and the same holds for the write. It is measured on a large synthetic project in `bench/` before it lands, like every change to the output (`CLAUDE.md`).

Open:

- The selector grammar, and how much upstream context a view carries (one step, or all that the checks need).
- Derived values that need the whole model, such as a room's area when a wall of it lies outside the slice. The view could carry them as read-only values.
- Incremental validation: checking only what a batch can have changed, so a batch on a big model does not validate all of it (`ARCHITECTURE.md` §5, step 3).
- Whether an agent works on a file extract, which could also be handed to a person, or only on scoped reads and writes against the project folder.

### Agents on several machines

The project lock (`.uea.lock`) covers one filesystem. Agents on several PCs each have their own clone, and git is the only link between them. Tested on two clones of Haus Müller (2026-10-14), one adding a request and the other changing a door, merged through a bare remote:

- Files of different disciplines merge cleanly.
- `log.jsonl` conflicts on every concurrent push, because every batch appends there and both clones take the same next batch number.
- Keeping both lines by hand is accepted without a word: two batch 2 entries, so reverting by number is ambiguous. Elements created on both sides would also get the same ids.
- What works today: pull, apply, commit, push; if the push is rejected, `git reset --hard origin/main` and run the same ops again (they use placeholders, not ids, so a replay is safe). The push is the lock and every agent runs the loop itself.

To solve, probably together with partial views:

- A merge strategy for the history: the batch numbers and the ids each side assigned.
- `uea sync`, which does the loop above (pull, replay, push, retry) so an agent does not.
- A check on load for duplicate batch numbers and ids, which today passes silently.
- Or a host model: one machine holds the project, remote agents reach it through ssh or the MCP server (`ARCHITECTURE.md`, MCP), and GitHub is the mirror and the review trail. The lock keeps working and nothing has to merge.

## More engineering domains

The core is domain-neutral, so new domain packs can be added on top of it:

- **Steel and timber construction:** members, connections, cutting lists.
- **Civil engineering (Tiefbau, Verkehrswegebau):** roads, earthworks, drainage. Alignment-based geometry (axis, gradient line, cross sections) instead of storeys.

**Mechanical parts are not UEA's.** They need real solid geometry (B-rep), which the building model avoids (`VISION.md`). They belong to UMEA, a separate program for mechanical engineering, built on an existing kernel and made for agents in the same way. UEA and UMEA share the idea, not the code.

## Standard library

A catalogue of standard elements that ships with the packs, so an agent writes `NYM-J3x1.5` or a standard door size without first defining the type in the project. It covers common cables (NYM-J, NYY-J), wall, slab and floor build-ups, standard door and window sizes, and pipes. A project type with the same name overrides the library entry. This saves tokens in every project and removes a source of typos. Open: the naming scheme, the licence of each data source (see "Type catalogues" under Open questions), and the line between library data (designations, cross sections, dimensions) and norm tables that offices supply, such as current-carrying capacities (`docs/decisions/0008-office-supplied-norm-data.md`).

Until then, an agent defines every type in the project file.

## From model to tender

Version 2. The model already holds what a tender needs: the quantities, per element and per type (`uea export xlsx`).

- **Cost estimation:** Kostenschätzung and Kostenberechnung structured per DIN 276, with quantities taken from the model. Needs the areas and volumes per DIN 277 (Backlog, Calculations).
- **Leistungsverzeichnis and Ausschreibung:** generate the LV from the model and export it as GAEB, for public Vergabe (VOB/A, VgV) and private tenders. Compare the bids that come back.
- **Fees:** an Honorar calculation per HOAI for the offer.

## Office workflows

Version 3. An agent works the business side, with a human approving every outgoing step:

1. A job comes in, from a client or from the tender watching of version 4. The agent summarizes it for the senior engineer: scope, deadlines, requirements, rough effort.
2. When the senior engineer approves, it prepares the offer, the fee calculation (version 2) and a first draft of the plan.
3. The senior engineer checks it and signs. Nothing goes out without that signature.

## Plot evaluation

Version 4. Given an open plot (for example one a city offers), an agent evaluates what could be built there:

- What the Bebauungsplan, BauNVO (GRZ, GFZ, storeys) or §34 BauGB and the Landesbauordnung allow.
- Building options: social housing, regular apartments, single-family houses, mixed use.
- A first massing model, rough costs (version 2) and a profitability estimate for each option.

The result is a decision basis for a human, not a decision. Needs the site plan and the setbacks and plot ratios (Backlog).

## Tender watching

Version 4. The agent watches public tender platforms (for example TED for the EU and the German Vergabeplattformen) for planning jobs that fit the office, and hands each match to the office workflow (version 3). The Ausschreibungen it reads are the offers of others to the office; the ones the office writes are version 2.

## Existing buildings

- **Survey into a model:** turn point clouds from a laser scanner, or photos, into a model of the existing building (status `existing`) for conversions and refurbishments.

## Agent dashboard

Version 5. A small, friendly dashboard for the senior engineer, a cherry on top. It is not a viewer and does not show the model one-to-one. It shows the state of the work:

- What each agent is doing right now ("planning the electrics on the EG", "running Heizlast"), with a simple animation.
- How far along each project is.
- Open questions from the agents that are waiting for a human answer.
- Drafts that are ready for review, and approvals that are pending.

Much of this UEA records anyway: the history, open issues, requests and waivers. What each agent is doing right now, and the questions waiting for a human, would need status and question events that UEA deliberately does not have today (`docs/decisions/0001-no-own-agent.md`). Building the dashboard means revisiting that decision. Either way, it only reads, so it never slows the agents down.

## Backlog

Work on what exists, to be scheduled into a version.

### Model

- **Shafts and installation walls.** Openings without a fill are built (`docs/decisions/0039-openings-without-a-fill.md`): holes through walls and slabs, chases, core drillings, asked for by the services' checks and named by their networks (`via=`). Shafts through several storeys and pre-wall installations are built too (`0045-shafts-prewalls-zones.md`): every network that changes storey goes through a shaft, and fixtures sit on their pre-wall. Open: pre-walls in the IFC export.
- **More roof elements.** Dormers (Gauben), roof windows, a parapet (Attika) on flat roofs, butterfly and barrel roofs, a steeper pitch for the ends of a half-hip. Roofs over a turned or trapezoid outline are open (`docs/decisions/0020-roof-parts.md`, `0021-roof-shapes.md`).
- **Railings and parapets** (`IfcRailing`) on stairs, galleries and balconies.
- **Sun shading.** Roller shutters and external venetian blinds (`IfcShadingDevice`), standard on German houses. Electrical feeds their motors, and they count for summer heat protection.
- **Suspended ceilings and other coverings** (`IfcCovering`). They set a room's clear height and leave space for services above them.
- **Furniture and the kitchen** (`IfcFurnishingElement`). Design drawings show them, and the electrical design places sockets by them.
- **A generic object:** a box with a footprint and a height (`IfcBuildingElementProxy`), for anything that has no kind of its own yet.
- **Balconies, terraces, and a second building** on the site, such as a garage or carport.
- **Curved walls.** Walls on an arc (bay windows, round stair walls) are still extrusions: the footprint is an arc, kept as a true arc in the IFC and approximated by segments for areas. Builds on walls in any direction (`docs/decisions/0018-raw-walls.md`). Open: how the position grammar places an arc (centre and radius, or two ends and a bulge), how openings are positioned along it, and finished areas with curved finish layers.
- **Facades.** Curtain walls (Pfosten-Riegel, `IfcCurtainWall`): a grid of mullions and transoms with glass or opaque panels, placed like a wall. Render, ETICS (WDVS) and ventilated cladding can already be written as layers of a wall type. Free-form, double-curved facades stay out: they need a general geometry kernel (`VISION.md`).
- **Not covered by the first version:** roofs over outlines turned by another angle or trapezoid, curved and spiral stairs, winders in a half turn, and wall joins other than "run to the far face of the wall it touches" (no mitre control, no join order).

### Larger buildings

- **Apartments as zones** (`IfcZone`), with a Wohnfläche per apartment.
- **Lifts** (`IfcTransportElement`) and stairwells with landings.
- **Split levels.** Built: a tall single-storey hall beside a storeyed wing, on the same storeys. Where the slab above has a void (or no slab) and a roof of the room's own storey or one below covers the room, that roof is its ceiling; such an airspace needs no room and no roof of the storey above (`tests/test_split_level.py`). Open: floors at different heights within one storey (half-storey offsets).
- **Timber-frame walls** whose layers mix studs and insulation, which the U-value calculation must handle.

### Services

- **Cable paths along the installation zones.** The lengths exist (`docs/decisions/0027-cable-routes.md`), and on a storey with installation zones (`zone`, `0045-shafts-prewalls-zones.md`) a cable follows them. Open: zones laid out automatically, the cables drawn on the installation plan.
- **Pipe and duct paths.** Plumbing and heating networks and the ducts are derived as rectilinear trees, sized and counted (`docs/decisions/0035-plumbing.md`, `0037-heating-pipes-and-strangschema.md`, `0038-ventilation.md`); they run through shafts and along installation zones and pre-walls where the model has them (`0045-shafts-prewalls-zones.md`), drawn along their way. Open: the clash of runs in one zone.
- **Structure.** Open: the roof's connections and the roof plane's bracing, torsion of the plan, crack widths, timber columns (listed in the Statische Berechnung, `docs/decisions/0044-structure-completion.md`).
- **Plans and sections.** Open on the section: the stair rail, niches behind the cut, a cut that jogs. Open on the elevation: facade materials, demolished walls of an Umbau, opening symbols. Open on the plan: dashed windows above the cut plane, notches in an L-shaped facade, client and author fields for the title block.
- **IFC import.** What it reports instead of guessing: curved walls, curtain walls over several storeys, L-shaped roofs in one IfcRoof, dormers, spiral stairs (`docs/decisions/0030-ifc-import-shapes.md`, `0031-ifc-import-files.md`); reading the architect's BCF replies back (`0032-bcf-requests.md`).

### Calculations

- **Areas and volumes per DIN 277** (BGF, NRF, BRI) as a `norm` calculator. The building application needs them, and they are the basis of a cost estimate per DIN 276.
- **U-values of air layers and inhomogeneous layers** per DIN EN ISO 6946 (rafters or studs with insulation between them), and the corrections for fixings and air gaps. Homogeneous layers are built (`uea calc uvalue`, `docs/decisions/0033-u-values-and-heizlast.md`).
- **Setbacks and plot ratios:** Abstandsflächen per Landesbauordnung, GRZ and GFZ per BauNVO. Needs the site plan below; the rules differ per Land.
- **GEG compliance** and the Energieausweis, later.
- **Lighting.** The light pack grows from luminaires into lighting design and photometric calculation (`docs/decisions/0006-pack-order.md`).

### Checks

Rule checks of the kind Solibri runs, reported with issue codes like the existing validators:

- **Landesbauordnung:** minimum clear height of habitable rooms (Aufenthaltsräume), window area relative to floor area (1/8 in most Länder), escape routes.
- **Accessibility per DIN 18040-2:** turning circles, door widths.
- **Fire safety:** fire ratings on types (F90, T30) and fire compartments.
- **Sound insulation per DIN 4109.**
- **Clash detection** between disciplines, once pipes and ducts exist.

### Drawings and lists

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

- **Construction stages and a timeline for the trades.** Elements belong to a construction stage (1, 2, 3, ...) and a trade (masonry, carpentry, roofing, electrical first and second fix, screed, plaster, ...). From the stages, the quantities and the dependencies between trades (screed after the heating pipes, plaster after the electrical first fix), UEA derives a timeline per trade that the Handwerksbetriebe can work to: a Gantt chart (PDF, XLSX) and `IfcWorkSchedule` in the IFC. Open: whether the stage is written on each element or follows from its kind and trade; where durations come from (quantities times the office's productivity rates); and the word in the format, probably `stage`, because what Revit calls phases are UEA's status flags.

## In parallel: feedback from practice

Talk to German engineering and architecture offices:

- Which tasks eat the most hours, and which would they hand to an agent first?
- Will one office lend an anonymized real project as a test case?
- What exports and formats must the results come in?
- Which architecture formats do Fachplaner receive (IFC, DWG), and in which quality?

The answers can reorder the versions.

## Open questions

- **Benchmark baseline:** which conventional tool to compare against. Revit with an MCP bridge is the most convincing for offices but needs Windows and a licence. Archicad, or Bonsai (BlenderBIM) as an open-source option, are alternatives.
- **Norm tables:** which tables each `norm` calculator needs, and in what form offices supply them from their licensed copies (`docs/decisions/0008-office-supplied-norm-data.md`).
- **Engineer partner:** who reviews the `norm` calculators and the structure (`docs/decisions/0040-structure.md`).
- **Type catalogues:** where realistic product and build-up data comes from (manufacturer data, BIM libraries) without licence trouble.
- **Parallel branches:** how two git branches of one project merge their histories and the ids each assigned (`docs/decisions/0009-history-revert-ids.md`). What was tested and the options are under Partial views, Agents on several machines.

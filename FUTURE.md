# Future

What comes after the first version and in which order, and the ideas and backlog behind them. For what UEA is see `VISION.md`; for how it is built see `ARCHITECTURE.md`; for what is built see `CHANGELOG.md` and `docs/decisions/`.

## Versions

| Version | Content | Section |
|---|---|---|
| v1 (0.1.0) | Architecture, electrical, plumbing, heating, ventilation and structure, planned by one agent for an Einfamilienhaus | v1 done |
| v2 (0.2.0, 0.3.0) | Partial views, then from model to tender: cost estimate, Leistungsverzeichnis, GAEB, fees; the bids in 0.3.0 | Partial views, From model to tender |
| v3 (0.3.0) | The agent dashboard: what each agent is doing right now, for the engineer | Agent dashboard |
| v4 | Plot evaluation and the watching of public tenders (Ausschreibungen) | Plot evaluation, Tender watching |

The order is fixed; the content of each version is not.

## v1 done

Version 1 is done. What 0.1.0 lacked was people's work, not code (`CHANGELOG.md`, "Not in this release"), and it was done outside this repository; its records are private:

- the reviews by licensed people of the `norm` calculators (`docs/validation/`) and of the structure (`docs/decisions/0040-structure.md`);
- the test with an office's IFC (`docs/decisions/0029-ifc-import.md` to `0032-bcf-requests.md`);
- the agent runs end to end (`bench/agent/results.md` at commit `517c07e`);
- the benchmark against a conventional tool and a human drafter (the task set in `bench/`, removed after commit `517c07e`);
- the standards' worked examples as a private test suite.

The decision records and the code comments refer to the work of v1 by phase number: 0 foundation, 1 core and architecture, 2 plans and tables, 3 electrical, 4 IFC import, 5 benchmark, 6 plumbing and heating, 7 ventilation, 8 structure.

## Partial views

Version 2, first in the version: tenders and cost estimates work on bigger buildings than a house, and those only fit in an agent's context a slice at a time.

Big projects do not fit in an agent's context, even in a compact format. A hospital is millions of tokens (`README.md`). `uea show`, `get` and `find` already read a slice, but an agent also has to work on one: take just the heating and ventilation of the OG, or just board `uv2` with its circuits and their loads, change it, and put the edits back. That is what lets UEA scale, and what lets several agents work on one project at once.

Built (`docs/decisions/0046-partial-views.md`): `uea view <selector>` prints a slice with the lines it references as read-only context and its base batch, and `uea apply --view <selector> --base <n>` writes back only to that slice and is rejected when a later batch touched what it edits. On a generated block of 8 storeys of 6 flats (1,073 elements), `uea view heat:OG3` is about a twelfth of all its files (`bench/large.py` and `bench/results.md` at commit `517c07e`).

Open:

- **Incremental validation:** checking only what a batch can have changed. Every batch still checks the whole model twice, before and after. The check used to grow faster than the model, through four spots that compared everything with everything: the pipe networks' tree (Prim's algorithm rescanned every pair on each step), the finished area of each room (cut by all of its storey's finishes), the wall overlaps and the walls a wall stands on. With those fixed, a batch through a view on the generated block takes 0.5 s at 1,073 elements, 1.6 s at 3,469 and 6.4 s at 10,239 (24 storeys of 20 flats; before: 0.8 s, 6.8 s and 111 s). The rest grows about with the model, at roughly 0.3 ms per element and check. True incremental validation means tracking which derived values each element feeds across the packs; it is worth it once real projects go well past 10,000 elements.
- **Context size:** on `heat:OG3` the context is 63 lines for 18 elements, most of them the walls the storey's walls stand on (`on=`). Context could stop at what a line's position needs.
- **Elements without a level:** a type cannot be added through a level view (`heat:OG`), since it has no level; it is written with the discipline's view (`heat`) or without `--view`.

### Agents on several machines

The project lock (`.uea.lock`) covers one filesystem. Agents on several PCs each have their own clone, and git is the only link between them. Tested on two clones of Haus Müller (2026-10-14), one adding a request and the other changing a door, merged through a bare remote:

- Files of different disciplines merge cleanly.
- `log.jsonl` conflicts on every concurrent push, because every batch appends there and both clones take the same next batch number.
- Keeping both lines by hand gives two batch 2 entries, so reverting by number is ambiguous, and elements created on both sides get the same ids. UEA now stops on such a history and names the lines (`ARCHITECTURE.md` §5).
- What works today: pull, apply, commit, push; if the push is rejected, `git reset --hard origin/main` and run the same ops again (they use placeholders, not ids, so a replay is safe). The push is the lock and every agent runs the loop itself.

To solve, probably together with partial views:

- A merge strategy for the history: the batch numbers and the ids each side assigned.
- `uea sync`, which does the loop above (pull, replay, push, retry) so an agent does not.
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

- **Cost estimation:** built (`uea calc costs`, `docs/decisions/0049-cost-estimate-and-hoai-fee.md`): the Kostenschätzung per DIN 276 on the DIN 277 quantities and the office's reference prices, with the priced LV beside it; and the Kostenberechnung from the priced LV (`stage=calculation`), keeping the estimate for groups the LV does not price yet. The Kostenanschlag from the bids awarded (`stage=offer`, `0051-bids.md`). Open: the Kostenfeststellung.
- **Leistungsverzeichnis and Ausschreibung:** built (`lv.uea`, `uea export gaeb`, `docs/decisions/0048-leistungsverzeichnis.md`): titles and positions in the model, quantities derived, GAEB DA XML 3.3 phase 83 for bidders, the LV and its costs per DIN 276 cost group in the xlsx. The bids: built (`uea import gaeb`, `uea calc bids`, `docs/decisions/0051-bids.md`): GAEB 84 into `bid.uea`, the arithmetic check of VOB/A § 16c Abs. 2, the Preisspiegel, also as sheets in the xlsx. Open: side offers (Nebenangebote); phases 81 and 86; pipe and duct lengths per size; validating the GAEB file against the official schema and importing it into an AVA program; a first real tender.
- **Fees:** built (`uea calc hoai`, `0049`): building, technical equipment and structure, chargeable costs from the estimate, the office's copy of the fee tables. On the cost calculation where there is one (§ 6 Abs. 1), per group of technical systems. Open: shipping a checked copy of the fee tables; special services; the structure's chargeable costs from the costs. The offer is built (Office workflows).

## Agent dashboard

Version 3. A small dashboard that shows the engineer what the agents are doing right now. It is information, not a representation: it does not show the model, is not a viewer, and UEA does not become an agent (`docs/decisions/0001-no-own-agent.md`).

Built (`docs/decisions/0053-agent-dashboard.md`): UEA infers the activity from the commands an agent runs anyway, so no agent reports a status. The CLI writes a line per command to an activity log on the machine, out of git, and `uea dashboard` serves a local page that reads it: per project and agent, its state (plant, rechnet, exportiert, liest, denkt nach, ruht) with an animation, a line such as "plant die Beleuchtung im OG", its last batch and its last commands.

Open:

- **Agents on other machines.** The log is per machine; a dashboard across machines needs the logs shipped to one place, perhaps together with a host model (Partial views, Agents on several machines).
- **Thinking** is the gap since an agent's last command; UEA cannot tell it from an agent that is done or waiting for its human. An optional `uea status "<text>"` stays out unless that falls short.
- **More than the moment:** how far along each project is, drafts ready for review, and the open requests and waivers, which UEA records already (`docs/decisions/0010-requests-in-the-model.md`). Questions waiting for a human answer need question events that UEA does not have.

## Office workflows

Not a version of its own. Most of an office's business side is how its agent behaves, and that belongs in the instructions the office gives its agent (`AGENTS.md`, `CLAUDE.md`), not in UEA (`docs/decisions/0001-no-own-agent.md`): read a request and summarise it for the senior engineer (scope, deadlines, requirements), stop and wait for the approval, prepare the offer and a first draft of the plan, and send nothing that the senior engineer has not checked and signed. The rules are the office's: who approves what, how offers are worded, what the agent may send. Keeping track of jobs is the office's own files or tools.

What UEA adds:

- **An example `AGENTS.md` for an office:** built (`docs/templates/AGENTS.md`): the rules that always hold, how the agent handles a request, when it stops and asks, and the `uea` commands of each step (`uea init` and `apply` for the first draft, `din277`, `costs` and `hoai` for the fee). The office copies it into its own repository and adapts it.
- **The offer as a document to sign** (Honorarangebot): built (`uea export offer`, `docs/decisions/0054-offer-export.md`): the fees of the `uea calc hoai` results with the office's letterhead and terms and the project's client, as a German PDF marked as a draft. Open: special services, hourly fees and lump sums.
- **Maybe the rough effort** from the office's own hours per service phase and its hourly rates, as a calculator on office data (`uea data`), since agents do not calculate.

## Plot evaluation

Version 4. Given an open plot (for example one a city offers), an agent evaluates what could be built there:

- What the Bebauungsplan, BauNVO (GRZ, GFZ, storeys) or §34 BauGB and the Landesbauordnung allow.
- Building options: social housing, regular apartments, single-family houses, mixed use.
- A first massing model, rough costs (version 2) and a profitability estimate for each option.

The result is a decision basis for a human, not a decision. The agent reads the Bebauungsplan and judges § 34; code measures. In slices:

1. **The plot and the measure of use:** built (`site.uea`, `uea calc baunvo`, `docs/decisions/0055-plot-and-baunvo.md`): the plot's outline and the plan's limits, GR and GRZ (also with § 19 Abs. 4), the Vollgeschosse by the Land's rule from the office's table `full-storey`, GF and GFZ, each against the limits. Open: garages, parking and driveways (§ 19 Abs. 4 Nr. 1 and 2), a sloping terrain, building lines and limits (Baulinien, Baugrenzen).
2. **Setbacks:** the Abstandsflächen per Landesbauordnung against the plot's edges; the rules differ per Land.
3. **Options:** a simple massing element (footprint, height, storeys) for sketching variants, each its own project, with `din277` and `costs` working on it.
4. **The comparison** of the options for the human, in German: size, GRZ and GFZ, setbacks, rough costs, maybe a yield from the office's rents or prices; and the site plan.

## Tender watching

Version 4. The agent watches public tender platforms (for example TED for the EU and the German Vergabeplattformen) for planning jobs that fit the office, and puts each match to the senior engineer the way the office's `AGENTS.md` says (Office workflows). Like the office workflows, this is the agent's behaviour: `docs/templates/AGENTS.md` has a section for it (where to look, what fits, what needs approval); UEA adds no code. The Ausschreibungen it reads are the offers of others to the office; the ones the office writes are version 2.

## Existing buildings

- **Survey into a model:** turn point clouds from a laser scanner, or photos, into a model of the existing building (status `existing`) for conversions and refurbishments.

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
- **Split levels.** Built: a tall single-storey hall beside a storeyed wing, on the same storeys. Where the slab above has a void (or no slab) and a roof of the room's own storey or one below covers the room, that roof is its ceiling; such an airspace needs no room and no roof of the storey above (`tests/test_split_level.py` at commit `517c07e`). Open: floors at different heights within one storey (half-storey offsets).
- **Timber-frame walls** whose layers mix studs and insulation, which the U-value calculation must handle.

### Services

- **Cable paths along the installation zones.** The lengths exist (`docs/decisions/0027-cable-routes.md`), and on a storey with installation zones (`zone`, `0045-shafts-prewalls-zones.md`) a cable follows them. Open: zones laid out automatically, the cables drawn on the installation plan.
- **Pipe and duct paths.** Plumbing and heating networks and the ducts are derived as rectilinear trees, sized and counted (`docs/decisions/0035-plumbing.md`, `0037-heating-pipes-and-strangschema.md`, `0038-ventilation.md`); they run through shafts and along installation zones and pre-walls where the model has them (`0045-shafts-prewalls-zones.md`), drawn along their way. Open: the clash of runs in one zone.
- **Structure.** Open: the roof's connections and the roof plane's bracing, torsion of the plan, crack widths, timber columns (listed in the Statische Berechnung, `docs/decisions/0044-structure-completion.md`).
- **Plans and sections.** Open on the section: the stair rail, niches behind the cut, a cut that jogs. Open on the elevation: facade materials, demolished walls of an Umbau, opening symbols. Open on the plan: dashed windows above the cut plane, notches in an L-shaped facade, client and author fields for the title block.
- **IFC import.** What it reports instead of guessing: curved walls, curtain walls over several storeys, L-shaped roofs in one IfcRoof, dormers, spiral stairs (`docs/decisions/0030-ifc-import-shapes.md`, `0031-ifc-import-files.md`); reading the architect's BCF replies back (`0032-bcf-requests.md`).

### Calculations

- **Areas and volumes per DIN 277:** built (`uea calc din277`, `docs/decisions/0047-din277-areas.md`). Open: balconies, loggias and terraces (Sonderfall der Raumumschließung), which need elements of their own.
- **U-values of air layers and inhomogeneous layers** per DIN EN ISO 6946 (rafters or studs with insulation between them), and the corrections for fixings and air gaps. Homogeneous layers are built (`uea calc uvalue`, `docs/decisions/0033-u-values-and-heizlast.md`).
- **Setbacks and plot ratios:** GRZ and GFZ per BauNVO are built (Plot evaluation); the Abstandsflächen per Landesbauordnung are its next slice.
- **GEG compliance** and the Energieausweis, later.
- **Lighting.** Illuminance targets and the average illuminance of a room are built (`uea calc light`, `docs/decisions/0050-illuminance.md`). Open: the point calculation with photometric files (task areas, uniformity), glare (UGR), daylight, emergency lighting, the reflectances from the finishes.

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

- **Norm tables:** which tables each `norm` calculator needs, and in what form offices supply them from their licensed copies (`docs/decisions/0008-office-supplied-norm-data.md`).
- **Type catalogues:** where realistic product and build-up data comes from (manufacturer data, BIM libraries) without licence trouble.
- **Parallel branches:** how two git branches of one project merge their histories and the ids each assigned (`docs/decisions/0009-history-revert-ids.md`). What was tested and the options are under Partial views, Agents on several machines.

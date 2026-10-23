# UEA architecture

How UEA is built. For the why see `VISION.md`; for what comes next see `FUTURE.md`; for the reasoning behind individual choices see `docs/decisions/`.

Status: release 0.4.0 (`CHANGELOG.md`): versions 1 to 4. Everything described here exists in `src/uea/` unless it says planned. Syntax and output may still change.

## 1. Overview

```
  any agent (Claude, OpenAI, Grok, Hermes, OpenClaw, ...)
        │  shell
        ▼
  ┌──────────────────────────────────────────────────────┐
  │ Interfaces    CLI (uea ...)  Python API  MCP (later) │
  ├──────────────────────────────────────────────────────┤
  │ Core          model · operations · validation ·      │
  │               derived geometry · history             │
  ├──────────────────────────────────────────────────────┤
  │ Domain packs  arch · elec · plumb · heat · vent ·    │
  │               light · struct · site · lv · bid       │
  │               (element kinds, types, validators,     │
  │                calculators, export mappings)         │
  ├──────────────────────────────────────────────────────┤
  │ Importers     IFC (architecture)                     │
  │ Exporters     IFC · DXF/DWG · PDF · XLSX · render    │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  project folder in git (canonical text files)
```

- The **core** knows nothing about walls or sockets. It handles elements, references, operations, validation, geometry resolution and the history.
- A **domain pack** adds one discipline: its element kinds, its validators, its calculators and how its elements map to each export.
- **Agents** only ever talk to the interfaces. Humans only ever see exports.

## 2. Project layout

A project is a folder, usually a git repository. Each discipline has its own file (`docs/decisions/0004-one-file-per-discipline.md`).

```
haus-mueller/
  project.uea     project data, site, levels, grids (shared by all disciplines)
  arch.uea        architecture: build-ups, walls, slabs, roofs, stairs, openings, rooms, finishes,
                  shafts, pre-walls and installation zones
  site.uea        the plot and the limits of its plan (GRZ, GFZ, Vollgeschosse)
  struct.uea      structural: beams, columns, rafters and loads; the load path itself is the architecture's (lb walls, slabs)
  elec.uea        electrical: devices, circuits, distribution boards, cables, feeds
  plumb.uea       plumbing: fixtures, meter, risers, stacks, sewer connection, circulation; pipes derived
  heat.uea        heating: heat generators, tanks, manifolds with their mixers, emitters; pipes derived
  vent.uea        ventilation: units, terminals, inlets, overflow openings; ducts derived
  light.uea       Lighting: luminaires, their types and the illuminance targets
  lv.uea          the Leistungsverzeichnis: titles and positions; quantities derived (§9)
  bid.uea         the bids on the LV and their unit prices, read from GAEB 84 (§9)
  issues.uea      requests between disciplines and waivers (shared, §5)
  calc/           project-specific calculators written by agents (custom)
  log.jsonl       history: every batch, revertible; every id ever assigned (§5)
  out/            exports (not canonical, not committed)
```

A discipline file only exists once the discipline has elements. If one file gets too large for a big building, it can be split by storey (`elec/EG.uea`, `elec/OG.uea`) without changing the format. An agent that must not read the whole project works on a partial view (§5).

### Reference direction

References only point upstream. Architecture never references electrical; electrical references architecture. In the graph, an arrow points from a discipline to the disciplines that reference it.

```
project ─▶ arch ─┬─▶ struct
                 ├─▶ heat  ─┤
                 ├─▶ plumb ─┤
                 ├─▶ vent  ─┼─▶ elec
                 ├─▶ light ─┤
                 └──────────┘
```

- Electrical sits below every other building-services pack because it feeds them: a circuit feeds a heat pump in `heat`, a ventilation unit in `vent`, a Durchlauferhitzer in `plumb` and the luminaires in `light`, and switches control those luminaires.
- Between `plumb`, `heat` and `vent`, references are allowed in one fixed direction per pair. So far: `plumb` may reference `heat`, whose storage tank heats the drinking water (`docs/decisions/0035-plumbing.md`).
- `site.uea` sits beside the services, below the architecture: the plot's outline may use the grids and walls, and nothing references the plot (`docs/decisions/0055-plot-and-baunvo.md`).
- `lv.uea` sits below all of them: a position may count the elements of every discipline, and no discipline references the LV (`docs/decisions/0048-leistungsverzeichnis.md`).
- `bid.uea` sits below the LV: a price references its bid and its position, and nothing references a bid (`docs/decisions/0051-bids.md`).
- `issues.uea` is outside the graph: requests and waivers may reference anything, and nothing references them.

The exact graph is fixed per pack and checked by the core. It must stay acyclic.

## 3. Model principles

1. **Intent over coordinates.** Walls run between grid points or relative to other walls (for example at a distance from another wall's face), openings sit at a distance along their host wall, sockets sit on a wall at a height, rooms are bounded by walls. A solver derives the actual geometry. Raw coordinates are the escape hatch for drafted elements and the normal case for imported ones (§9); walls in any direction are placed by their axis from point a to point b (`docs/decisions/0018-raw-walls.md`).
2. **Derived, never stored.** Areas, lengths, volumes, joins and cable lengths are computed on demand. Only decisions are stored.
3. **Datums.** Plan positions are core faces (the faces of a type's core layer, the German Rohbau); finished sizes are derived from the other layers (plaster, screed, linings), and both are available everywhere. Heights count from the storey's FFL, its finished floor level. Windows hang from the storey's head height. See `docs/decisions/0012-datums-and-positions.md`.
4. **Types and instances.** An instance references a type (`AW-365`, `NYM-J3x1.5`). Types are defined in the project file (a shipped standard library is in `FUTURE.md`). Changing a type changes every instance.
5. **IFC vocabulary.** Element kinds and properties follow IFC names and property sets where they exist, so IFC export is near-lossless. The internal format stays far simpler than IFC.
6. **Status.** Every element is new unless it carries the flag `existing` (Bestand), `demolish` or `temp`, matching IFC's status values. Plans, quantities and calculators respect the status (a demolished wall bounds no room), so Umbau projects work in the same model.
7. **Ids** are short, stable and unique across the whole project (`w12`, `s4`, `c3`). UEA assigns them and never reuses one, because the history records every id ever assigned (§5). Each pack registers its id prefixes with the core, so packs cannot collide.
8. **Units.** Lengths in metres, angles in degrees, other quantities in SI or in the unit the norm uses (for example mm² for cable cross sections). Each field's unit is fixed in its schema, never written in the file.

## 4. File format

One element per line. The line starts with the element kind and its id (or, for levels, grids and types, its name), then the fields the kind's schema declares as positional, then the quoted label, then `key=value` fields, then flags. `#` starts a comment. An excerpt from the prototype, where the full house and its conventions are (`docs/prototype/haus-mueller/`):

```
# project.uea
level EG z=0 fb=0.15 head=2.26
grid W x=0
grid S y=0

# arch.uea
type AW-365 wall "Ziegel 36,5 verputzt" layers=putz-kalkgips:0.015,*ziegel-t9:0.365,putz-leicht:0.02
wall w1 EG AW-365 y=S+ x=W..E lb
wall w4 EG AW-365 x=W+ y=w1..w3 lb
wall w5 EG IW-240 y=w1+4.51 x=w4..w2 lb
win f2 w4 1.26x1.135 y=S+1.76
room r1 EG kitchen "Küche" at=w4+1,w1+1 floor=FB-fli

# elec.uea
circ c4 fi1 NYM-J3x2.5 B16 "Küche Steckdosen 2"
sock s4 w4 c4 y=f2+0.3 z=1.15 n=2
```

`y=w1+4.51` places w5 4.51 m clear of w1's inside face, like a dimension chain. f2 has no sill: it hangs from the storey's head height of 2.26 m. `y=f2+0.3` puts the socket 0.30 m past the edge of window f2, so it moves when the window moves.

Rules:

- **Canonical order:** kinds in the order the pack defines, then natural id order (`w2` before `w10`); levels by height, grids by axis and coordinate. Saving always writes canonical order, so one changed element is a one-line diff. Fields at their default are left out; comments are not kept (`docs/decisions/0013-canonical-line-format.md`).
- **Strict parsing:** every line is validated against its schema on load. Unknown kinds, fields or flags are errors, not ignored.
- **The files are canonical.** A project's current state is fully described by its `.uea` files. `log.jsonl` holds its history (§5).

## 5. Operations and batches

Agents change the model through operations, written in the same line syntax:

```
+ wall @a EG IW-115 x=w6+1.385 y=w5..w3     add; UEA assigns the id
+ door _ @a 0.76x2.01 y=w5+0.26 into=r5     add, hosted on the new wall
~ w9 type=IW-175 lb                         set fields and flags; k= resets a field
~ d1 1.51x2.26                              a bare value sets the positional field it fits
- w9 d3                                     remove
> grid E x=10.74                            replace a whole element (everything on the grid follows)
```

A new element gets a placeholder (`@a`) that any operation in the same batch can reference, or `_` if nothing refers to it. UEA assigns the real ids and reports them: `ok batch 42 (arch): +2` and ` @a=w18 d10`. Placeholders use `@`, not `$`, because a shell expands `$a` when an agent forgets to quote its heredoc. The details are in `docs/decisions/0014-operations-and-history.md`.

`uea apply` takes a batch of operations plus who is making the change and why:

```bash
uea apply --by elec-agent -m "Küche: Steckdosen nach Kundenwunsch" < ops.txt
```

A batch is atomic:

1. The project is locked for writing.
2. The operations apply in order to a copy. References are resolved at the end, so a batch may add a room before its walls.
3. The copy is validated.
4. If the batch introduces a new error **in the disciplines it writes**, it is rejected and nothing changes. Existing errors do not block it, so a broken model can be repaired step by step.
5. Otherwise it is written, and one entry goes to the history.

`--dry-run` runs the same checks and writes nothing.

### History and revert

`log.jsonl` is the project's history (`docs/decisions/0009-history-revert-ids.md`). Each entry holds time, `by`, message, the operations with their placeholders resolved, their inverse operations, the ids assigned and a hash of each written file. Replaying it rebuilds the model.

- `uea revert <batch>` applies the inverse operations as a new batch, so the history only ever grows.
- Ids are never reused, because the history records every id ever assigned.
- The history is checked on every read: batches count 1, 2, 3, and a plain batch never assigns an id an earlier batch assigned (a revert or an external batch may bring a removed one back). Both break when two clones' histories are merged by hand; UEA then stops and names the lines.
- An agent with a shell can still edit a `.uea` file directly. The next command notices through the file hashes: a valid edit is recorded as an external batch (the difference to the replayed history, so it can be reverted too), an invalid one stops UEA with the errors.
- A revert is rejected when a later batch changed the same elements; the error names the batch.

### Partial views

A big project does not fit in an agent's context, so an agent reads and writes a slice of it (`docs/decisions/0046-partial-views.md`). `uea view heat:OG` prints the slice's lines after the lines they reference (context, read-only, so every reference resolves) with the base, the batch number it read at. `uea apply --view heat:OG --base 41` then may only change and remove elements of the slice and add elements that fall in it, and is rejected when a batch after 41 touched an element it changes or removes. Otherwise it is an ordinary batch: derived values and validation stay those of the whole model. Selectors are those of `uea show`: a discipline, a discipline on a level or in a room, a level, or an id with everything that references it; terms join with commas. Agents on views that do not overlap cannot conflict.

### Changes that affect other disciplines

An upstream change must stay possible even when downstream elements depend on it. Otherwise architecture could never move a wall once the electrics are in.

So a batch is **not** rejected for errors it causes in other disciplines. Instead the output lists them, and they stay open as issues of that discipline until its agent fixes them:

```
ok  batch 41: 1 changed (w7)
affects elec: s4, s5 host w7 moved; s5 now 0.08 m from door d3 (W-ELEC-004)
```

This is how upstream changes reach downstream disciplines. Requests go the other way.

### Requests between disciplines

A downstream discipline that needs something from upstream (space for a Unterverteilung, a Schlitz, a Durchbruch, a thicker wall) adds a request to `issues.uea` (`docs/decisions/0010-requests-in-the-model.md`):

```
req q1 elec w7 "Schlitz 10x5 cm für Steigleitung"
```

The request is an open issue of `arch` until its agent closes it with the batch that resolved it, or rejects it with a reason. Agents may also talk to each other directly; the request is the record that outlives the session and that the human sees. Planning goes round this way: each discipline drafts, asks and improves, until no errors and no requests are open.

Where the owner works outside UEA (an architect whose IFC was imported), `uea export bcf` hands the requests to their program as BCF topics, the targets selected by their GlobalIds in the architect's own file (`docs/decisions/0032-bcf-requests.md`).

`issues.uea` also holds waivers: issues accepted on purpose, with who accepted them and why. Reports list every waiver for the engineer who signs.

## 6. Agent interface

### CLI

Every agent with a shell can use the CLI, so it is the primary interface. Commands marked *later* belong to later phases:

| Command | Purpose |
|---|---|
| `uea help [topic]` | Short overview; details per topic (`help elec`, `help ops`). Agents load only what they need. |
| `uea init <dir>` | New project |
| `uea show [scope]` | Summary at a scope: `project`, `EG`, `r3`, `elec`, `elec:EG`, any id |
| `uea get <id>...` | Elements with their derived values |
| `uea find <kind> [filters]` | Query, for example `uea find sock room=r3`, `uea find wall ext lb` |
| `uea view <selector>` | A slice as lines to edit, with its context and base (§5, Partial views) |
| `uea apply --by <who> -m <why> [--dry-run] [-f file] [--view <selector> --base <n>]` | Atomic batch from stdin or a file, optionally limited to a view (§5) |
| `uea revert <batch> --by <who>` | Undo a batch as a new batch (§5) |
| `uea check [discipline]` | Open issues, requests and waivers |
| `uea calc <name> [scope] [name=value]` | Run a calculator with its settings (§8) |
| `uea data [show\|add\|remove]` | List, check and install the office's norm tables (§8) |
| `uea import ifc <file>` | Architecture from an architect's IFC (§9) |
| `uea import gaeb <file>` | A bidder's GAEB 84 into `bid.uea` (§9, The Leistungsverzeichnis) |
| `uea export <format> [scope]` | Human-facing exports (§9): `pdf`, `dxf`, `xlsx`, `ifc`, `svg`, `png`, `bcf`, `gaeb`, `offer` |
| `uea render <level>` | A plan image (PNG) for vision models |
| `uea block x=W..E y=S..N storeys=<n>` | A simple building as an ordinary batch, for options on a plot (`0057`) |
| `uea compare <project>...` | Options side by side for a human, from each one's results (`0057`) |
| `uea log [n]` | Recent batches |
| `uea dashboard [--port n]` | For the engineer, not for agents: a local page of what each agent is doing (Dashboard below) |

Output rules:

- Terse text by default, `--json` when a program reads it.
- Ids instead of names, counts instead of lists where possible, numbers rounded to a sensible precision (lengths to the centimetre or millimetre).
- Long results are paged; the output says how to get more.
- Every error message names the element, gives the actual numbers and says how to fix it.
- Exit codes: 0 done, 1 rejected or errors found, 2 wrong call or project files that do not parse.
- `--by` defaults to the environment variable `UEA_BY`; `-C <dir>` runs in another folder, like git.

### Python API

For anything the CLI does not cover, agents write Python against the API: read-only access to the model with typed elements and derived values, plus `apply()` for writes. Writes always go through the same batches and validation as the CLI.

### MCP

Later, a thin MCP server wrapping the CLI for agents that prefer tools over a shell. No features of its own.

### Dashboard

The engineer sees what each agent is doing right now (`docs/decisions/0053-agent-dashboard.md`). Agents report nothing: the CLI writes a line to an activity log on the machine when a command starts and when it ends (`activity.py`, `~/.local/state/uea/activity.jsonl`, out of git; `UEA_ACTIVITY=off` stops it). `uea dashboard` serves a local page that reads it and shows, per project and agent, its state (planning, calculating, exporting, reading, thinking, idle) with an animation, a line such as "plant die Beleuchtung im OG", its last batch and its last commands. Agents name themselves with `UEA_BY`.

## 7. Validation

- Each pack contributes validators. The core runs reference, schema and geometry checks.
- Issues have a code (`E-REF-001`, `E-ARCH-…`, `W-ELEC-…`), a severity (error or warning), the element, the numbers, and a fix hint. `uea help codes` lists every code.
- An issue cites a norm clause in its `rule` field only when the check really implements that clause.
- Open requests count as issues of their target's discipline. A waived issue stays listed as waived; it is never hidden.
- A check that involves two disciplines belongs to the downstream one, which placed the dependent element: a switch on the hinge side of a door is an electrical issue. If the fix lies upstream, the downstream discipline sends a request instead of changing the other discipline's file.
- v1 re-checks the whole model on every batch. Incremental checks come when projects get large enough to need them.

## 8. Calculators

A calculator is a small typed Python module with declared inputs and outputs:

- **`norm` calculators** ship with a pack. Each implements one method of one standard (for example Heizlast per DIN EN 12831-1), cites its clauses, and is tested against hand-computed cases with our own data. Each has a validation report a Prüfingenieur could read.
- **Norm tables** a method needs (for example current-carrying capacities or Norm-Außentemperaturen) are supplied by the office from its own licensed copy (`uea data add`). They stay outside the repo and the project; the standard's worked examples run locally against them (`docs/decisions/0008-office-supplied-norm-data.md`).
- **`custom` calculators** are written by agents for a project (for example "lighting at 1.5 × the norm level") and live in the project's `calc/` folder: a module `calc/<name>.py` that defines `CALCULATOR = Calculator(...)`. UEA runs it as `custom`, whatever it declares.
- Each `norm` calculator has a validation report in `docs/validation/`. The first one is the Wohnfläche per WoFlV (`uea calc wofl`), which needs no norm tables; beside it, `din277` gives BGF, NRF with NUF, TF and VF, KGF and BRI per DIN 277 (`docs/decisions/0047-din277-areas.md`), `costs` the cost estimate per DIN 276 on those quantities and the office's reference prices, and `hoai` the fee per HOAI 2021 on the office's copy of the fee tables (`0049-cost-estimate-and-hoai-fee.md`). The electrical ones are `cable` (cable against its breaker), `vdrop` (voltage drop) and `equip` (the minimum equipment of a room, `0041-minimum-equipment.md`). The lighting one is `light` (each room's average illuminance against its targets by the utilisation factor method, `0050-illuminance.md`). The heating ones are `uvalue` (U-values per DIN EN ISO 6946), `heatload` (Heizlast per DIN EN 12831-1, `docs/decisions/0033-u-values-and-heizlast.md`) and `hydronic` (heating pipes and the hydraulic balance on the Heizlast, `0037-heating-pipes-and-strangschema.md`). The plumbing ones are `water` (drinking-water pipes per DIN 1988-300), `drain` (waste-water pipes per DIN 1986-100, `docs/decisions/0035-plumbing.md`) and `recirc` (the hot-water circulation, `0042-heating-and-hot-water-details.md`). The ventilation ones are `airflow` (the Lüftungskonzept and room flows per DIN 1946-6) and `ducts` (duct sizes and fan pressure, `0038-ventilation.md`). The structural ones are `loads` (actions per DIN EN 1991 with snow and wind, and their takedown to the foundation) and `struct` (the Statische Berechnung: slabs, beams and rafters on the solver PyNite, columns, masonry walls per DIN EN 1996-3 with the bracing against wind, lintels, footings, `0040-structure.md`, `0044-structure-completion.md`).

Every result records the calculator, its kind (`norm` or `custom`), its version, its inputs and settings (`name=value` after the scope), the norm tables it used with edition and file hash, and the model state it ran on. A `custom` result is never presented as norm-compliant. Results are derived, not stored in the model. The norm tables are the office's: it installs each from its own licensed copy as a CSV file with `uea data add`, they live on the machine outside the project, and a calculator without its table stops and names it (`docs/decisions/0028-norm-tables-and-electrical-calculators.md`). `uea calc` writes a report for humans (`out/<name>.md`, in German) and the record (`out/<name>.json`).

## 9. Import, exports and renders

UEA's own exports are views. They are never read back into the model. Humans who want changes tell their agent.

| Export | Library | Notes |
|---|---|---|
| IFC4 | IfcOpenShell (LGPL) | Built. Stable GlobalIds derived from project and element id; walls, openings, slabs, roof planes, stairs, spaces with quantities |
| Plan image | Pillow (MIT-CMU), and SVG | Built. Cheap pictures for agents to check their own layouts, from a neutral 2D drawing |
| DXF | ezdxf (MIT) | Built for the floor plan sheet. From the same 2D drawing; mm, German layers per element (`0022-plans-and-tables.md`) |
| DWG | external converter, run as a separate process | ODA File Converter or LibreDWG (GPL) |
| PDF plans | reportlab (BSD), from the same 2D drawing | Built for the floor plan sheet, the section, the elevation, the electrical, heating and plumbing sheets, the Heizungsschema (`0036-heating-and-plumbing-sheets.md`), the Strangschema (`0037`), the ventilation plans (`0038`) and the Positionsplan (`0040`) |
| PDF reports | reportlab (BSD), DejaVu Sans (free licence, shipped) | Built. A calculation result's report on A4 with an empty signature block, refused when the model has changed since (`0036`) |
| Site plan | reportlab (BSD), from the same 2D drawing | Built. The plot, the footprint with its Vollgeschosse and the Abstandsflächen from the results of `baunvo` and `setback` (`0057-options-on-a-plot.md`) |
| Fee offer | reportlab (BSD), as the PDF reports | Built. The Honorarangebot from the `hoai` results with the office's letterhead and terms (table `offer`) and the project's client, as Markdown and a PDF to sign (`0054-offer-export.md`) |
| XLSX | openpyxl (MIT) | Built. Tables per kind and quantities: rooms, walls, openings, slabs, roofs, stairs (`0022-plans-and-tables.md`); then the electrical tables, and emitters, manifolds, fixtures, pipe sections and pipe quantities (`0036`), ventilation units, air terminals and ducts (`0038`); the LV and its costs per DIN 276 cost group (`0048`) |
| GAEB DA XML 3.3 | Python's standard library (XML) | Built. The LV for bidders, phase 83, without prices (`0048-leistungsverzeichnis.md`); the bids, phase 84, are read back with `uea import gaeb` (`0051-bids.md`); not yet validated against the official schema |
| BCF 2.1 | Python's standard library (zip, XML) | Built. The requests to a discipline as topics for the programs of people outside UEA (`0032-bcf-requests.md`) |
| Render | Blender headless, run as a separate process (GPL) | Pictures for humans and for vision models |

New exports are a good place for outside contributions: each one only needs the read API.

### The Leistungsverzeichnis

The LV is part of the model (`lv.uea`, `docs/decisions/0048-leistungsverzeichnis.md`): agents decide its titles and positions, and code counts. A position names the elements it counts with the selector of `uea find` and a measure whose meaning per kind is fixed in code (a wall's `area` is its net elevation area, a circuit's `len` its cable length, a heat generator's `heat` the heating pipes from it); work no element carries is `fix=` with a unit. Quantities are derived, so they follow every change of the model, and a batch names the positions that follow it. The numbers (OZ) follow the order of the ids and can be pinned with `oz=`. Long texts come from the office's table `lv-texts`, unit prices (`ep=`) and DIN 276 cost groups (`kg=`) from the position.

The bids come back as GAEB 84 and are not UEA's own export, so they are read into the model: `uea import gaeb` writes a `bid` and its `price` lines to `bid.uea` (`docs/decisions/0051-bids.md`). Code checks the arithmetic (VOB/A § 16c Abs. 2: the unit price counts), `uea calc bids` compares the bids, and `uea calc costs stage=offer bid=` takes the prices of the bids awarded into the Kostenanschlag. The award is the client's; UEA ranks and flags.

### IFC import

Fachplaner usually receive the architect's model as IFC. `uea import ifc <file>` maps it into `project.uea` and `arch.uea` (`docs/decisions/0011-ifc-import.md`, `0029-ifc-import.md`, `0030-ifc-import-shapes.md`, `0031-ifc-import-files.md`). Built: storeys, grids along x or y, walls as axes through the core with a type from the layers (a wall in parts is one wall), curtain walls as walls with windows over their face, doors, windows, niches and holes as positions on their wall, one floor slab per storey with its openings (small or round ones as holes, `0039-openings-without-a-fill.md`), spaces as rooms with a separator where they are open to each other, and stairs and roofs. Imported elements carry raw coordinates instead of grid intent, and geometry is read from IfcOpenShell's tessellation, so it does not matter how the exporting program wrote a body.

A file is read in whatever length unit it has, and one building at a time (`--building`). A plan in survey coordinates or turned off the axes is moved to the origin and turned so its walls run along x and y; the history keeps how, so later files land in the same place, and a BCF export can point back into the architect's coordinates.

A stair or a roof is parameters in UEA and only a body in the file. The importer reads the faces (the treads; the planes of the roof's top), builds the UEA stairs and roofs that could have made them with UEA's own layout code, and keeps the one that lies where the file's faces lie: within 6 % of the tread area, within 2 cm of the roof's top. Walls whose tops follow a fitted roof get `top=`. What fits no UEA element is reported with the reason, never approximated.

The IFC GlobalId of each element is kept in the history entry of the import, with a hash of the line as imported, not in the model. A new version from the architect updates what nobody has edited since, adds what is new, removes what the file lost, and lists the rest as `kept:`; ids stay. The errors an import causes are reported like any upstream change, and do not reject it.

## 10. Geometry

- Buildings are mostly extrusions. UEA uses 2D plan geometry (Shapely) plus heights, and builds simple 3D bodies only for export and rendering.
- Wall joins, room boundaries, opening voids and device positions are derived from intent. Rooms are the free regions between walls and separators around their seed point (`docs/decisions/0015-rooms-and-finishes.md`).
- Roofs are where plain extrusion stops: pitched roof planes cut the walls below them (gables, knee walls) and set the clear height of the rooms under them, which the Wohnfläche depends on. UEA handles this with plane cuts on the extruded bodies, still without a general geometry kernel (`docs/decisions/0016-roofs.md`, `0020-roof-parts.md`: one roof per wing for L-, T- and U-shaped houses).
- No general geometry kernel. Anything that needs real solids, such as mechanical parts, is outside UEA (UMEA, a separate program, `FUTURE.md`).

## 11. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.12+, typed throughout, pyright in strict mode |
| Schemas and validation | Pydantic v2 |
| Packaging and tooling | uv, ruff, pyright |
| Geometry | Shapely |
| Exports | IfcOpenShell (optional extra `uea[ifc]`), Pillow, openpyxl, ezdxf, reportlab; Blender and DWG converters as separate processes |
| Structural solver | PyNite (MIT, optional extra `uea[struct]`): plates, continuous beams and plane frames (`0040-structure.md`, `0044-structure-completion.md`) |
| Licence | Apache-2.0 |

Dependency licences follow `docs/decisions/0002-apache-2.0.md`. Rust (or C++) comes in only for measured hot paths, behind the same API (`docs/decisions/0003-python.md`).

## 12. Token efficiency

Token use is a design constraint, measured by the token task set from phase 1 to commit `517c07e` (`bench/` there; removed since, `docs/decisions/0052-no-tests-in-the-repo.md`):

- The file format and the operation syntax are the cheapest readable form we can find.
- `uea help` is layered, so an agent's starting context stays small.
- Read commands default to the smallest useful answer.
- Agents get pictures only when they ask for them.
- A change to the file format or output keeps it as short as it is or shorter. Saving tokens does not count if agents make more mistakes. The task set's last results are in `bench/results.md` at commit `517c07e`.

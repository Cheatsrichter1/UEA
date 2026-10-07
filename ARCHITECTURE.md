# UEA architecture

How UEA is built. For the why see `VISION.md`; for the order of work see `ROADMAP.md`; for the reasoning behind individual choices see `docs/decisions/`.

Status: phase 1 in progress. The core, the Architektur pack, the CLI, the first `norm` calculator, plan images and the IFC export exist in `src/uea/`; the other packs, importers and exports are still plans. Syntax and output may change before the first release.

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
  │               light · struct                         │
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
- A **domain pack** adds one discipline: its element kinds, its type catalogue, its validators, its calculators and how its elements map to each export.
- **Agents** only ever talk to the interfaces. Humans only ever see exports.

## 2. Project layout

A project is a folder, usually a git repository. Each discipline has its own file (`docs/decisions/0004-one-file-per-discipline.md`).

```
haus-mueller/
  project.uea     project data, site, levels, grids (shared by all disciplines)
  arch.uea        Architektur: build-ups, walls, slabs, roofs, stairs, openings, rooms, finishes
  struct.uea      Statik: load-bearing elements, supports, loads
  elec.uea        Elektro: devices, circuits, distribution boards, cables, feeds
  plumb.uea       Sanitär: fixtures, pipe networks
  heat.uea        Heizung: heat generators, emitters, pipe networks
  vent.uea        Lüftung: units, ducts, outlets
  light.uea       Lighting: luminaires; after v1 also lighting design and requirements
  issues.uea      requests between disciplines and waivers (shared, §5)
  calc/           project-specific calculators written by agents (custom)
  log.jsonl       history: every batch, revertible; every id ever assigned (§5)
  out/            exports (not canonical, not committed)
```

A discipline file only exists once the discipline has elements. If one file gets too large for a big building, it can be split by storey (`elec/EG.uea`, `elec/OG.uea`) without changing the format.

### Reference direction

References only point upstream. Architecture never references Elektro; Elektro references architecture. In the graph, an arrow points from a discipline to the disciplines that reference it.

```
project ─▶ arch ─┬─▶ struct
                 ├─▶ plumb ─┐
                 ├─▶ heat  ─┤
                 ├─▶ vent  ─┼─▶ elec
                 ├─▶ light ─┤
                 └──────────┘
```

- Elektro sits below every other building-services pack because it feeds them: a circuit feeds a heat pump in `heat`, a ventilation unit in `vent`, a Durchlauferhitzer in `plumb` and the luminaires in `light`, and switches control those luminaires.
- Between `plumb`, `heat` and `vent`, references are allowed in one fixed direction per pair.
- `issues.uea` is outside the graph: requests and waivers may reference anything, and nothing references them.

The exact graph is fixed per pack and checked by the core. It must stay acyclic.

## 3. Model principles

1. **Intent over coordinates.** Walls run between grid points or relative to other walls (for example at a distance from another wall's face), openings sit at a distance along their host wall, sockets sit on a wall at a height, rooms are bounded by walls. A solver derives the actual geometry. Raw coordinates are the escape hatch for drafted elements and the normal case for imported ones (§9).
2. **Derived, never stored.** Areas, lengths, volumes, joins and cable lengths are computed on demand. Only decisions are stored.
3. **Datums.** Plan positions are Rohbau (the faces of a type's core layer); Fertigmaß is derived from the other layers (Putz, Estrich, Bekleidung), and both are available everywhere. Heights count from the storey's OKFF. Windows hang from the storey's Sturzhöhe. See `docs/decisions/0012-datums-and-positions.md`.
4. **Types and instances.** An instance references a type (`AW-365`, `NYM-J3x1.5`). Types come from the pack's catalogue or are defined in the project file. Changing a type changes every instance.
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

`y=w1+4.51` places w5 4.51 m clear of w1's inside face, like a Maßkette. f2 has no sill: it hangs from the storey's Sturzhöhe of 2,26 m. `y=f2+0.3` puts the socket 0.30 m past the edge of window f2, so it moves when the window moves.

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
- An agent with a shell can still edit a `.uea` file directly. The next command notices through the file hashes: a valid edit is recorded as an external batch (the difference to the replayed history, so it can be reverted too), an invalid one stops UEA with the errors.
- A revert is rejected when a later batch changed the same elements; the error names the batch.

### Changes that affect other disciplines

An upstream change must stay possible even when downstream elements depend on it. Otherwise architecture could never move a wall once the electrics are in.

So a batch is **not** rejected for errors it causes in other disciplines. Instead the output lists them, and they stay open as issues of that discipline until its agent fixes them:

```
ok  batch 41: 1 changed (w7)
affects elec: s4, s5 host w7 moved; s5 now 0.08 m from door d3 (E-ELEC-004)
```

This is how upstream changes reach downstream disciplines. Requests go the other way.

### Requests between disciplines

A downstream discipline that needs something from upstream (space for a Unterverteilung, a Schlitz, a Durchbruch, a thicker wall) adds a request to `issues.uea` (`docs/decisions/0010-requests-in-the-model.md`):

```
req q1 elec w7 "Schlitz 10x5 cm für Steigleitung"
```

The request is an open issue of `arch` until its agent closes it with the batch that resolved it, or rejects it with a reason. Agents may also talk to each other directly; the request is the record that outlives the session and that the human sees. Planning goes round this way: each discipline drafts, asks and improves, until no errors and no requests are open.

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
| `uea apply --by <who> -m <why> [--dry-run] [-f file]` | Atomic batch from stdin or a file (§5) |
| `uea revert <batch> --by <who>` | Undo a batch as a new batch (§5) |
| `uea check [discipline]` | Open issues, requests and waivers |
| `uea calc <name> [scope]` | Run a calculator (§8) |
| `uea data add <file>` | Add office-supplied norm tables (§8). *Later* (phase 3) |
| `uea import ifc <file>` | Architecture from an architect's IFC (§9). *Later* (phase 4) |
| `uea export <format> [scope]` | Human-facing exports (§9): `ifc`, `svg`, `png` |
| `uea render <level>` | A plan image (PNG) for vision models |
| `uea log [n]` | Recent batches |

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

## 7. Validation

- Each pack contributes validators. The core runs reference, schema and geometry checks.
- Issues have a code (`E-REF-001`, `E-ARCH-…`, `W-ELEC-…`), a severity (error or warning), the element, the numbers, and a fix hint. `uea help codes` lists every code.
- An issue cites a norm clause in its `rule` field only when the check really implements that clause.
- Open requests count as issues of their target's discipline. A waived issue stays listed as waived; it is never hidden.
- A check that involves two disciplines belongs to the downstream one, which placed the dependent element: a switch on the hinge side of a door is Elektro's issue. If the fix lies upstream, the downstream discipline sends a request instead of changing the other discipline's file.
- v1 re-checks the whole model on every batch. Incremental checks come when projects get large enough to need them.

## 8. Calculators

A calculator is a small typed Python module with declared inputs and outputs:

- **`norm` calculators** ship with a pack. Each implements one method of one standard (for example Heizlast per DIN EN 12831-1), cites its clauses, and is tested against hand-computed cases with our own data. Each has a validation report a Prüfingenieur could read.
- **Norm tables** a method needs (for example current-carrying capacities or Norm-Außentemperaturen) are supplied by the office from its own licensed copy (`uea data add`). They stay outside the repo and the project; the standard's worked examples run locally against them (`docs/decisions/0008-office-supplied-norm-data.md`).
- **`custom` calculators** are written by agents for a project (for example "lighting at 1.5 × the norm level") and live in the project's `calc/` folder: a module `calc/<name>.py` that defines `CALCULATOR = Calculator(...)`. UEA runs it as `custom`, whatever it declares.
- Each `norm` calculator has a validation report in `docs/validation/`. The first one is the Wohnfläche per WoFlV (`uea calc wofl`), which needs no norm tables.

Every result records the calculator, its kind (`norm` or `custom`), its version, its inputs, the norm tables it used and the model state it ran on. A `custom` result is never presented as norm-compliant. Results are derived, not stored in the model. `uea calc` writes a report for humans (`out/<name>.md`, in German) and the record (`out/<name>.json`).

## 9. Import, exports and renders

UEA's own exports are views. They are never read back into the model. Humans who want changes tell their agent.

| Export | Library | Notes |
|---|---|---|
| IFC4 | IfcOpenShell (LGPL) | Built. Stable GlobalIds derived from project and element id; walls, openings, slabs, roof planes, stairs, spaces with quantities |
| Plan image | Pillow (MIT-CMU), and SVG | Built. Cheap pictures for agents to check their own layouts, from a neutral 2D drawing |
| DXF | ezdxf (MIT) | Phase 2. From the same 2D drawing; layer structure per discipline |
| DWG | external converter, run as a separate process | ODA File Converter or LibreDWG (GPL) |
| PDF plans | from the same 2D drawing | Phase 2. Grundriss per storey and discipline |
| XLSX | openpyxl (MIT) | Phase 2. Tables: rooms, walls, sockets, circuits, quantities |
| Render | Blender headless, run as a separate process (GPL) | Pictures for humans and for vision models |

New exports are a good place for outside contributions: each one only needs the read API.

### IFC import

Fachplaner usually receive the architect's model as IFC. `uea import ifc <file>` maps it into `project.uea` and `arch.uea`. A new version from the architect updates them with stable ids, and its effects on the other disciplines are reported like any upstream change (`docs/decisions/0011-ifc-import.md`). Imported elements carry raw coordinates instead of grid intent.

## 10. Geometry

- Buildings are mostly extrusions. UEA uses 2D plan geometry (Shapely) plus heights, and builds simple 3D bodies only for export and rendering.
- Wall joins, room boundaries, opening voids and device positions are derived from intent. Rooms are the free regions between walls and separators around their seed point (`docs/decisions/0015-rooms-and-finishes.md`).
- Roofs are where plain extrusion stops: pitched roof planes cut the walls below them (gables, Kniestock) and set the clear height of the rooms under them, which the Wohnfläche depends on. UEA handles this with plane cuts on the extruded bodies, still without a general geometry kernel (`docs/decisions/0016-roofs.md`).
- No general geometry kernel. Anything that needs real solids (mechanical parts, see `FUTURE.md`) goes into a separate pack on an existing kernel.

## 11. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.12+, typed throughout, pyright in strict mode |
| Schemas and validation | Pydantic v2 |
| Packaging and tooling | uv, ruff, pytest |
| Geometry | Shapely |
| Exports | IfcOpenShell (optional extra `uea[ifc]`), Pillow; later ezdxf, openpyxl; Blender and DWG converters as separate processes |
| Licence | Apache-2.0 |

Dependency licences follow `docs/decisions/0002-apache-2.0.md`. Rust (or C++) comes in only for measured hot paths, behind the same API (`docs/decisions/0003-python.md`).

## 12. Token efficiency

Token use is a design constraint, measured by the token task set from phase 1 on (`ROADMAP.md`):

- The file format and the operation syntax are the cheapest readable form we can find.
- `uea help` is layered, so an agent's starting context stays small.
- Read commands default to the smallest useful answer.
- Agents get pictures only when they ask for them.
- Every change to the file format or output is checked on the task set for token cost and error rate. Saving tokens does not count if agents make more mistakes. The task set lives in `bench/` (`uv run python -m bench`); its last results are in `bench/results.md`.

# Foundations

What UEA is, its format, its history and how agents work with it. Index in [README.md](README.md).

## 0001 No own agent

UEA builds no agent, agent router or multi-agent framework. It provides the model, the CLI, the Python API, the calculators and the exports; any agent with a shell uses it, and humans talk to their agent, not to UEA.

- Coordination between agents is the agents' job. UEA guarantees atomic, validated batches and reports effects on other disciplines.
- No chat, status or question features. Each batch carries a message saying why. The dashboard's activity log is written by the CLI as a side effect of commands (0053).
- What one discipline needs from another is a request in the model (0010). Agents may still talk directly.
- Error messages and help must be self-explanatory for agents of very different quality.

Why: general agents are built by large teams and improve fast; what they lack is engineering software to work in. An own agent with roles would duplicate their work and tie UEA to one vendor.

## 0002 Apache 2.0

UEA is open source under Apache-2.0. Dependencies must be compatible: permissive and LGPL libraries are fine, GPL programs (Blender, LibreDWG) only as separate processes. Norm texts and tables stay out regardless, because their publishers license them.

Why: UEA does not live on licence sales, offices trust what they can inspect, and an open project draws contributed exports, calculators and packs. MIT lacks the patent grant; GPL or AGPL would scare off offices that build on it.

## 0003 Python

Python 3.12+, fully typed (pyright strict), Pydantic v2, uv and ruff. IfcOpenShell, Shapely, ezdxf and openpyxl are at hand, and agents write their own calculators best in Python. Hot paths can move to Rust later behind the same API, if profiling shows a need.

Why not Rust, TypeScript or C++: thin BIM ecosystems, slower iteration, or a second language for agents.

## 0004 One file per discipline

A project is a folder with `project.uea` (site, levels, grids) and one file per discipline (`arch`, `elec`, `plumb`, `heat`, `vent`, `light`, `struct`, later `lv` and `site`). References only point upstream along an acyclic graph fixed per pack. Requests and waivers live in a shared `issues.uea` (0010). A file that grows too large may be split by storey (`elec/EG.uea`) without changing the format.

- Each discipline writes only its own file and `issues.uea`; git shows who changed what.
- An upstream change that breaks a downstream reference is not rejected: it becomes an open issue of the downstream discipline (`ARCHITECTURE.md` §5).

Why not one file for everything (conflicts), one per storey (stairs, shafts and structure span storeys), a database (no readable diffs) or one per element (thousands of files).

## 0005 Line format

UEA has its own line format: one element per line, kind and id first, positional fields from the schema, then `key=value` fields and flags. Operations use the same syntax behind `+`, `~`, `-` or `>`. Every line is validated against its Pydantic schema. IFC4 is for exchange, not the working format: UEA exports it with IFC names for kinds and properties, and imports the architect's IFC (0011). The details are fixed in 0013.

Why: the format is what agents read and write most. On Haus Müller (225 elements, `tiktoken` o200k_base) JSON costs 1.7× the tokens minified and 2.7× indented, YAML 2.0×; IFC many times more. Python scripts as the model would not be canonical, validatable or diffable.

## 0006 Pack order

Version 1 covers what an Einfamilienhaus needs, in this order: core and architecture; electrical (it shows the design side, and few open tools cover it); IFC import of architecture, so offices can try UEA on real projects; plumbing and heating with the Heizlast; ventilation; structure last, only with a licensed engineer reviewing. Lighting is only the luminaires in v1 and grows into its own design pack later.

Why: structure carries the most Haftung and needs outside review first; Heizlast first would show only calculation.

## 0007 Norm and custom calculators

- A calculator is a small typed Python module with declared inputs and outputs.
- `norm` calculators ship with a pack, implement one method of one standard, cite its clauses and are checked against hand-computed cases; the standard's worked examples run locally against office tables (0008).
- `custom` calculators are written by agents for one project and live in its `calc/` folder.
- Every result records calculator, kind, version, inputs and the model state. A `custom` result is never labelled norm-compliant, and reports show the kind prominently.

Why: agents must be able to cover what the built-in calculators do not, while the signing engineer must always see whether a result is the norm method. Letting agents change built-in calculators would destroy that trust.

## 0008 Office-supplied norm data

- A `norm` calculator declares the tables it needs: standard, edition, table and schema.
- The office enters them once per machine from its own licensed copy (`uea data add`), outside every project and never committed. Storage and format are in 0028.
- Without the data the calculator stops and names the missing table. Every result records the edition of each table it used.
- Public checks use our own hand-computed data; the standards' worked examples run privately against the office's tables.

Why: the tables and worked examples are licensed and cannot be in an open repository, and every office that plans to the standards owns copies. Values derived from first principles would not be norm results.

## 0009 History, revert and ids

- `log.jsonl` is the project's history, committed with it: per batch the time, `by`, message, operations, inverse operations, ids assigned and a hash of each written file.
- `uea revert <batch>` applies the inverse as a new batch; the history only grows. A revert that conflicts with a later batch is rejected.
- UEA assigns ids. A new element gets a placeholder (`@a`) in its batch and the output reports the real id; levels, grids and types are named by the agent. No id is ever reused.
- Edits outside UEA are found through the hashes and recorded as an external batch if they validate (0014).

Why not git as the only history (coarse, needs git skills), agent-chosen ids (two branches both create `w13`) or a counter (no revert). Merging histories of two branches is open (`FUTURE.md`).

## 0010 Requests in the model

- Requests are elements in `issues.uea`. Any discipline may add one, pointing at the element or room it concerns. It is an open issue of the discipline owning its target until that discipline closes it (with the batch that resolved it) or rejects it with a reason.
- Waivers in the same file accept an issue on purpose, with who and why; reports list every waiver for the signing engineer.
- Requests and waivers may reference anything and nothing references them, so the graph stays acyclic. `uea check` lists them with the other issues.

```
req q1 elec w7 "Schlitz 10x5 cm für Steigleitung"
waive wv1 W-ELEC-004 s5 "Steckdose neben Tür auf Kundenwunsch" by=elektroplaner
```

Why: downstream disciplines need things from upstream (a niche, a chase, a thicker wall), and planning goes in circles until nothing is open. Chat between agents is lost with the session and invisible to the human; letting electrical edit `arch.uea` breaks ownership.

## 0013 Canonical line format

- A line is `kind key positional... "label" key=value... flags`. The reader takes the label and `key=value` anywhere after the key; bare tokens fill positionals first, the rest must be flags.
- The writer writes the canonical order: positionals, label, `key=value` in schema order, flags. Walls and separators write their position before their span (`y=S+ x=W..E`). Defaults are left out; numbers have at most four decimals and no trailing zeros.
- Bestand status is a flag (`existing`, `demolish`, `temp`), as in IFC; without one an element is new.
- `#` comments are ignored and lost when UEA rewrites the file. Labels cannot contain `"`.
- Level and grid names are a letter, then letters, digits or `_`; type and project names may also hold `-` and `.` (`AW-365`, `NYM-J3x1.5`). No name may look like an id.
- File order: types (by category, then name), then the pack's kinds in order; levels by `z`, grids by axis and coordinate, the rest in natural id order.

Why: one rule for every kind, comments are not worth keeping while agents write the files, and a flag costs fewer tokens than `status=`.

## 0014 Operations and history

- `+` adds, with a placeholder (`@a`) or `_`, or the name of a level, grid or type. Only revert and replay give explicit ids.
- `~ id k=v flag "label"` sets fields; `k=` resets to the default; a bare value sets the positional it fits. `~ q1 done` records the current batch.
- `-` removes ids. `>` replaces a whole element of the same kind; since positions are relative, replacing a grid moves everything on it.
- The history stores each batch resolved (ids for placeholders, canonical lines), its inverse, the ids assigned and file hashes. Replaying it rebuilds the model.
- An edit outside UEA shows as a differing hash: UEA replays the history, diffs it against the files and records an external batch that can be reverted. Files that do not parse stop UEA with `file:line` errors.
- A revert is rejected if a later batch touched the same ids. A batch is rejected if it adds an error in a discipline it writes; `--dry-run` checks and writes nothing.
- Writes take an OS file lock on `.uea.lock`, which `uea init` puts in the project's `.gitignore`.

Why: agents edit files with their own tools, so UEA must record what they did; a hidden snapshot would drift and is lost on a fresh clone.

## 0017 English format

- Everything UEA defines is English: kinds, fields, values, flags, CLI output, help, issue messages, code and docs. `kn` became `knee`, `din` `hand`, `plz` `postcode`, `typ` `type`; in output `ssl=` (was `rd=`), FFL (was OKFF), `shell`/`fin`, eaves and ridge.
- The help names a German term once where a German brief uses it: `knee: ... (Kniestock)`.
- What people write stays in their language: labels, names, request texts, batch messages.
- Exports for humans stay German. Docs keep German only for legal, norm and role terms without an exact English equivalent, and in names.

Why: in the first agent test agents guessed which words of the mixed vocabulary were German (`din=links`, `terrain=`); German compounds cost more tokens (`Sturzhöhe` 5, "head height" 2); IFC's vocabulary is English. A language setting would mean two vocabularies.

## 0046 Partial views

A view is a selector read at a base: the selector names a slice, the base is the batch number when the agent read it.

| Selector | Selects |
|---|---|
| `heat` | the discipline |
| `heat:OG` | its elements on a level, including those hanging on something with a level |
| `uv2` | the element and everything referencing it, transitively, in any discipline |
| `elec:r3` | what lies in a room, limited to the discipline |
| `heat:OG,plumb:OG` | several, joined |

- `uea view <selector>` prints the slice as lines, after the read-only context it references upstream (levels, grids, types, host walls), marked by one comment line so lines stay copyable. `--json` gives `{"base", "context", "elements"}`.
- Derived values always come from the whole model; a view is a scope, not an extract.
- `uea apply --view <sel> --base <n>` rejects a change outside the slice (`w9 is outside heat:OG`) and a change to an element a batch after the base touched (`batch 43 changed h7 after base 41`). Only edits conflict, not references. `--base` also works alone.
- Two agents on disjoint views cannot conflict. A type has no level, so it is written through the discipline's view.

Why: big projects do not fit in an agent's context. File extracts would drift and need a merge; locks leak when an agent dies; last-write-wins undoes others' work silently. Measured on a generated block of 1,073 elements: a storey's heating view is about a twelfth of all files.

## 0052 No tests in the repo

Up to commit `517c07e` the repository held a pytest suite (577 functions, about 800 cases) and the token task set (`bench/`). Both were removed, with pytest and tiktoken; ruff and pyright stay in CI.

- The validation reports keep their cases as the record of what was verified and say they passed at `517c07e`. A calculator changed after it must say so in its report, and the reviewer checks it by hand.
- The token figures in `README.md` and `ARCHITECTURE.md` §12 stay as measured there.
- Everything comes back with `git checkout 517c07e -- tests bench`.

Why: the owner judged them overhead once versions 1 and 2 were built and checked; the people who sign check the results. The cost: a wrong number now shows only if the reviewer notices, and nothing checks that `docs/reference.md` is current.

## 0053 Agent dashboard

- UEA infers what an agent does from the commands it runs; agents report nothing. The CLI writes a line when a command starts and when it ends: time, who (`--by`, else `UEA_BY`), command and scope, success, and for a batch its number, message, packs and storeys. Help, init, version, data and the dashboard are not recorded.
- The log is per machine, out of every project and out of git: `~/.local/state/uea/activity.jsonl` (`$XDG_STATE_HOME`, `%LOCALAPPDATA%`). `UEA_ACTIVITY=<file>` moves it, `off` stops it; past 1 MB it keeps its last 2,000 lines; a failed write is ignored.
- States from an agent's last command: planning (`apply`, `revert`, `import`), calculating (`calc`), exporting (`export`, `render`) and reading (`show`, `get`, `find`, `view`, `check`, `log`) while running or up to 8 s after; thinking up to 5 min after; idle after that, hidden after 12 h. A command started 15 min ago that never ended counts as ended.
- The line comes from the model's names: "plant die Beleuchtung im OG". Each card shows the agent, state, line, last batch and last six commands.
- `uea dashboard [--port 8770]` serves `dashboard.html` and `/state` on `127.0.0.1` with the standard library; it only reads. The page is German.

Why: a `uea status` command is the status feature 0001 rules out and costs every agent tokens; a log in the project would conflict in git or need one dashboard per project; `log.jsonl` holds only batches. Thinking is a guess, and agents on other machines do not show.

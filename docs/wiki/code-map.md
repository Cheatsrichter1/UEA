# Code map

[Wiki home](README.md)

Where things are in `src/uea/` and around it. Each module's docstring says what it does in one line; this page groups them.

## The way a command runs

```
cli.py ─▶ project.py ─▶ core/ (syntax, schema, model) ─▶ packs/ (kinds, checks)
              │                                              │
              ├─ batch.py   apply, revert, external edits    ├─ derive.py  derived values
              ├─ calc/      calculators, norm tables         └─ export/    plans, tables, IFC, BCF
              └─ importer/  IFC into arch
```

## `src/uea/`

| Path | What it does |
|---|---|
| `cli.py` | The `uea` command line; terse text, `--json` for programs |
| `help.py` | `uea help`, in layers |
| `project.py` | A project folder: the `.uea` files and `log.jsonl` |
| `batch.py` | Atomic batches, revert and the detection of edits made outside UEA |
| `derive.py` | Derived values: geometry and everything computed from the model |
| `geom.py` | Small 2D helpers on top of Shapely |
| `fmt.py` | Number formatting for CLI output |
| `reference.py` | Generates [`docs/reference.md`](../reference.md) |
| `core/syntax.py` | The line syntax shared by files and operations |
| `core/schema.py` | Element schemas; elements to lines and back |
| `core/values.py` | Field values: references, positions, spans, points, sizes, layers |
| `core/model.py` | The in-memory model, keyed by id |
| `core/ops.py` | Operations: the line syntax with a prefix |
| `core/registry.py` | Domain packs and the registry of element kinds |
| `core/issues.py` | Issues: element, numbers and a fix |
| `packs/project.py` | Project data, levels and grids |
| `packs/arch/` | Architecture: kinds, geometry, stairs, checks, views, the Wohnfläche |
| `packs/elec/`, `packs/light/` | Electrical devices, circuits, boards and feeds; luminaires |
| `packs/heat/`, `packs/plumb/`, `packs/vent/` | Heating, plumbing and ventilation |
| `packs/struct/` | The load path, loads and the Statische Berechnung |
| `packs/issues.py` | Requests and waivers (`issues.uea`) |
| `packs/net.py`, `pipes.py`, `hydraulics.py`, `mount.py` | Shared by the services: derived networks, pipe sizes, hydraulics formulas, wall-mounted things |
| `calc/` | The calculator framework and `uea data` for the office's norm tables |
| `export/` | Drawings (`plan`, `sheet`, `section`, `elevation`, `install`, `tga`, `strang`, `schema`, `board`, `positionsplan`), writers (`pdf`, `dxf`, `xlsx`, `ifc`, `bcf`), tables and calculation reports |
| `importer/` | IFC import: reading the file, fitting stairs and roofs, building the batch |

## Around the code

| Path | What it holds |
|---|---|
| `tests/` | pytest, one file per area; expected values computed by hand |
| `bench/` | The token task set (`uv run python -m bench`); `bench/agent/` has the briefs for an agent to build Haus Müller |
| `docs/prototype/haus-mueller/` | The reference house as `.uea` files, with its exports |
| `tools/` | Throwaway prototype scripts, not held to the code rules |

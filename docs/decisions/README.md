# Decision records

One file per major decision: what was decided, what else was considered, and why. Until the first release, a record may be updated in place when a decision changes. After it, write a new record that supersedes the old one instead of rewriting history.

| # | Decision | Status |
|---|---|---|
| 0001 | [No own agent: UEA is the substrate](0001-no-own-agent.md) | Accepted |
| 0002 | [Open source under Apache-2.0](0002-apache-2.0.md) | Accepted |
| 0003 | [Python as the core language](0003-python.md) | Accepted |
| 0004 | [One file per discipline](0004-one-file-per-discipline.md) | Accepted |
| 0005 | [Own compact line format, IFC for exchange](0005-line-format.md) | Accepted |
| 0006 | [v1 scope and order of the domain packs](0006-pack-order.md) | Accepted |
| 0007 | [`norm` and `custom` calculators](0007-norm-and-custom-calculators.md) | Accepted |
| 0008 | [Norm tables are supplied by the office](0008-office-supplied-norm-data.md) | Accepted |
| 0009 | [Project history, revert and ids](0009-history-revert-ids.md) | Accepted |
| 0010 | [Requests between disciplines live in the model](0010-requests-in-the-model.md) | Accepted (syntax still draft) |
| 0011 | [IFC import of architecture](0011-ifc-import.md) | Accepted |
| 0012 | [Datums, positions and openings](0012-datums-and-positions.md) | Accepted (syntax still draft) |
| 0013 | [Canonical line format](0013-canonical-line-format.md) | Accepted |
| 0014 | [Operations, history and edits outside UEA](0014-operations-and-history.md) | Accepted |
| 0015 | [Rooms, finished sizes and slab outlines are derived from walls](0015-rooms-and-finishes.md) | Accepted |
| 0016 | [Roofs as planes over the storey outline](0016-roofs.md) | Accepted |
| 0017 | [The format is English; exports for humans stay German](0017-english-format.md) | Accepted |
| 0018 | [Walls in any direction](0018-raw-walls.md) | Accepted |
| 0019 | [Stairs with a landing or winders](0019-stair-shapes.md) | Accepted |
| 0020 | [Roofs over outlines that are not rectangles](0020-roof-parts.md) | Accepted |
| 0021 | [Half-hip, mansard and flat roofs](0021-roof-shapes.md) | Accepted |
| 0022 | [Plans and tables for humans](0022-plans-and-tables.md) | Accepted (tables and plans built) |
| 0023 | [Sections](0023-sections.md) | Accepted (built) |
| 0024 | [Elevations](0024-elevations.md) | Accepted (built) |
| 0025 | [The electrical pack, slice 1](0025-electrical-devices.md) | Accepted (slice 1 built) |
| 0026 | [The electrical sheets, slice 2](0026-electrical-sheets.md) | Accepted (slice 2 built) |
| 0027 | [Cable routes, slice 3a](0027-cable-routes.md) | Accepted (slice 3a built) |
| 0028 | [Norm tables and the first electrical calculators, slice 3b](0028-norm-tables-and-electrical-calculators.md) | Accepted (slice 3b built) |
| 0029 | [IFC import, slice 4a](0029-ifc-import.md) | Accepted (slice 4a built) |
| 0030 | [IFC import, slice 4b: grids, slab openings, stairs and roofs](0030-ifc-import-shapes.md) | Accepted (slice 4b built) |
| 0031 | [IFC import, slice 4c: how programs write a file](0031-ifc-import-files.md) | Accepted (slice 4c built) |
| 0032 | [Requests as BCF](0032-bcf-requests.md) | Accepted (export built) |
| 0033 | [U-values and the Heizlast, slices 6a and 6b](0033-u-values-and-heizlast.md) | Accepted (slices 6a and 6b built) |
| 0034 | [Heating elements, slice 6c](0034-heating-elements.md) | Accepted (slice 6c built) |
| 0035 | [Plumbing and pipe sizing, slice 6d](0035-plumbing.md) | Accepted (slice 6d built) |
| 0036 | [Heating and plumbing sheets, slice 6e](0036-heating-and-plumbing-sheets.md) | Accepted (slice 6e built) |
| 0037 | [Heating pipes, the hydraulic balance and the Strangschema, slice 6f](0037-heating-pipes-and-strangschema.md) | Accepted (slice 6f built) |
| 0038 | [Ventilation, phase 7](0038-ventilation.md) | Accepted (phase 7 built) |
| 0039 | [Openings without a fill](0039-openings-without-a-fill.md) | Accepted (built) |
| 0040 | [Structure, phase 8](0040-structure.md) | Accepted (slices 8a to 8d built, reviewed) |
| 0041 | [Minimum electrical equipment of a room](0041-minimum-equipment.md) | Accepted |
| 0042 | [Emitter output, mixing circuits and the hot-water circulation](0042-heating-and-hot-water-details.md) | Accepted |
| 0043 | [Inlets, overflow openings, terminal losses, heat recovery and ventilation in the IFC](0043-ventilation-details.md) | Accepted |
| 0044 | [The rest of the structure: slab checks, rafters, columns, bracing](0044-structure-completion.md) | Accepted (built, reviewed) |
| 0045 | [Shafts, pre-wall installations and installation zones](0045-shafts-prewalls-zones.md) | Accepted |
| 0046 | [Partial views](0046-partial-views.md) | Accepted (built) |
| 0047 | [Areas and volumes per DIN 277](0047-din277-areas.md) | Accepted (built) |

Template:

```
# NNNN: Title

Status: Proposed | Accepted | Superseded by NNNN
Date: YYYY-MM-DD

## Context
## Decision
## Alternatives
## Consequences
```

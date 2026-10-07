# 0011: IFC import of architecture

Status: Accepted
Date: 2026-10-07

## Context

Elektro and TGA offices rarely start from nothing. They receive the architect's model, usually as IFC, and plan on it, with a new version every few weeks. Without an import, an agent would have to remodel the architecture from plans before it could do any Fachplanung, and UEA could not be used on these offices' real projects.

## Decision

- `uea import ifc <file>` maps storeys, grids, walls, slabs, roofs, stairs, openings and spaces into `project.uea` and `arch.uea`. The mapping is the inverse of the IFC export.
- Ids stay stable across re-imports through the IFC GlobalId. A new version from the architect updates `arch.uea` and reports its effects on the other disciplines like any upstream change.
- What cannot be mapped is reported, never silently dropped.
- UEA's own exports are still never read back into the model.

## Alternatives

- **No import:** agents remodel the architecture from PDF plans. Slow, expensive in tokens and error-prone.
- **DWG import:** 2D lines without meaning. Maybe later, with an agent interpreting the drawing.
- **Round-trip of UEA's own exports:** humans would start editing outside the model.

## Consequences

- Imported walls do not sit on grids. The model must take raw coordinates as a normal input for imported elements, not only as an escape hatch.
- Imported elements belong to the architect outside UEA. Requests on them are meant for that architect; exporting them as BCF is the natural format.
- The import comes right after Elektro in the roadmap (`docs/decisions/0006-pack-order.md`).

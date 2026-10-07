# 0004: One file per discipline

Status: Accepted
Date: 2026-10-07

## Context

A project must be canonical text in git, readable for humans in a diff, and workable for several agents in parallel. Agents mostly read through the CLI rather than the files, so file layout affects tokens less than it affects diffs, ownership and conflicts.

## Decision

A project is a folder with `project.uea` (shared: site, levels, grids) and one file per discipline (`arch.uea`, `elec.uea`, `plumb.uea`, `heat.uea`, `vent.uea`, `light.uea`, `struct.uea`). References only point upstream (for example `elec` → `arch`), along an acyclic graph fixed per pack. Requests between disciplines and waivers live in a shared `issues.uea` (`0010-requests-in-the-model.md`). A file that grows too large can be split by storey (`elec/EG.uea`) without changing the format.

## Alternatives

| Option | Why not |
|---|---|
| One file for everything | Every change touches the same file; more conflicts in parallel work; unwieldy for large buildings |
| One file per storey | Elements that span storeys (stairs, shafts, risers, structure) fit badly; many files |
| Database (SQLite) as source of truth | Binary in git, no readable diffs, against "text first". May come later as an internal index |
| One file per element | Thousands of tiny files, slow for humans and git |

## Consequences

- Each discipline writes only its own file and `issues.uea`, and git shows clearly which discipline changed what.
- The checker must validate references across files.
- An upstream change (for example moving a wall) may break downstream references. Such a batch is not rejected; the affected elements become open issues of the downstream discipline (see `ARCHITECTURE.md` §5).

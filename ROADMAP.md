# UEA roadmap

The order of work, from nothing to the Einfamilienhaus demo. Each phase ends with something an agent can actually do. For what UEA is see `VISION.md`; for how it is built see `ARCHITECTURE.md`; for later ideas see `FUTURE.md`. The order of the packs is `docs/decisions/0006-pack-order.md`.

Status, October 2026: phase 0 is done and phase 1 is in progress (see below).

## Phases

| Phase | Content | Done when |
|---|---|---|
| 0. Foundation | Git repo, Apache-2.0 licence, Python project setup, CI, decision records | An empty `uea` CLI installs and its tests run in CI |
| 1. Core + Architektur | File format, operations, batches, history and revert, requests and waivers, validation, read commands; levels, grids, build-ups, walls, slabs, roofs, stairs, openings, rooms; Bestand status; Wohnfläche per WoFlV as the first `norm` calculator; IFC export; a simple plan image for agents; the token task set | An off-the-shelf agent builds the shell of the EFH, roof included, from a brief, and a human can open the IFC in a free viewer |
| 2. Plans and tables | DXF/PDF plans per storey and discipline in German drafting conventions; XLSX tables (rooms, walls, quantities) | An architect would accept the Grundrisse as Entwurf plans |
| 3. Elektro | Devices (sockets, switches, data), luminaires (kept in the light pack), circuits, distribution board, cable runs, feeds to the powered elements of other packs; first `norm` calculators (cable sizing, voltage drop) on office-supplied tables; Elektro plan and socket/circuit tables | The agent plans the EFH electrics from a brief and the exports look like a plan an Elektroplaner would recognize |
| 4. IFC import | Architecture from an architect's IFC into `project.uea` and `arch.uea`; re-import of new versions with stable ids | A real project from an office imports, and the agent plans its electrics on it |
| 5. Benchmark v1 | Fixed task set from phases 1–4, run through UEA, through a conventional tool driven by an agent, and by a human drafter; tokens, time and errors counted | Results published in the repo, method reproducible |
| 6. Sanitär + Heizung | Pipe networks, fixtures, heat generator and emitters; Heizlast per DIN EN 12831-1 as a `norm` calculator with a validation report | The agent plans plumbing and heating for the EFH, and the Heizlast matches the standard's worked examples, run locally on the office's tables |
| 7. Lüftung | Units, ducts, outlets | The EFH demo is complete apart from Statik |
| 8. Statik | Load-bearing elements, loads, frame analysis on an open-source solver | Only together with a licensed engineer who reviews the validation |

### Phase 1: where it stands

Built and tested (`src/uea/`, `tests/`):

- File format, strict parser and canonical writer (`docs/decisions/0013-canonical-line-format.md`).
- Operations, atomic batches, placeholders, history, revert, edits outside UEA (`docs/decisions/0014-operations-and-history.md`).
- Requests and waivers, validation with issue codes, the reference graph between disciplines.
- Read commands: `show`, `get`, `find`, `check`, `log`, layered `help`.
- Levels, grids, build-ups, walls, openings, niches, slabs, voids, gable, shed and hip roofs, straight stairs, separators, rooms with Rohbau and Fertig areas, heights and volumes (`docs/decisions/0015-rooms-and-finishes.md`, `0016-roofs.md`). Bestand status.
- Wohnfläche per WoFlV as the first `norm` calculator, with a validation report (`docs/validation/wofl.md`); custom calculators from a project's `calc/`.
- Plan images (PNG, SVG) per storey and the IFC4 export, schema-valid by IfcOpenShell's validator.
- The token task set (`bench/`) with reference solutions: the Haus Müller shell, roof included, costs about 2,400 tokens of commands and output.

Still open for phase 1:

- An off-the-shelf agent builds the EFH shell from a brief, and its errors are counted in the task set. So far only the reference solutions run.
- A human opens the IFC in a free viewer (it validates and every shape builds in IfcOpenShell).
- CI runs on GitHub (the workflow is written).
- Walls in any direction with raw coordinates (needed for the IFC import in phase 4); stairs other than one straight flight; roofs over outlines that are not rectangles.

The **Einfamilienhaus demo** is v1: the sum of phases 1–8, run end to end by one agent, with the benchmark alongside.

After v1, the light pack grows from luminaires into lighting design and photometric calculation (`docs/decisions/0006-pack-order.md`).

## Token task set

From phase 1 on, a fixed set of agent tasks runs against UEA and counts tokens and errors. Every change to the file format or CLI output is measured on it before it lands. Fewer tokens do not count if weaker agents make more mistakes, so the set measures both. The benchmark in phase 5 adds the comparison with a conventional tool and with a human drafter.

## In parallel: feedback from practice

Start now, before phase 1, and talk to German Ingenieurbüros and Architekturbüros:

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

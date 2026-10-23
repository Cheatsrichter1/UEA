# Concepts

[Wiki home](README.md)

The words UEA uses, each with where it is defined.

## The model

| Term | Meaning | Defined in |
|---|---|---|
| Project | A folder, usually a git repository, of `.uea` files plus the history `log.jsonl` | [`ARCHITECTURE.md` §2](../../ARCHITECTURE.md#2-project-layout) |
| Discipline file | One file per discipline: `project`, `arch`, `site`, `struct`, `light`, `elec`, `heat`, `plumb`, `vent`, `lv`, `bid`, `issues` | [0004](../decisions/foundations.md#0004-one-file-per-discipline) |
| Domain pack | The code of one discipline: its element kinds, checks, calculators and export mappings | [`ARCHITECTURE.md` §1](../../ARCHITECTURE.md#1-overview) |
| Reference direction | References only point upstream: architecture never names electrical, electrical names architecture | [`ARCHITECTURE.md` §2](../../ARCHITECTURE.md#reference-direction) |
| Element | One line: kind, id, positional fields, label, `key=value` fields, flags ([the line format](format.md)) | [0005](../decisions/foundations.md#0005-line-format), [0013](../decisions/foundations.md#0013-canonical-line-format) |
| Id | Short, stable, never reused (`w12`, `s4`); UEA assigns it | [0009](../decisions/foundations.md#0009-history-revert-and-ids) |
| Type | A build-up or product an element names (`AW-365`, `NYM-J3x1.5`); changing it changes every instance | [`ARCHITECTURE.md` §3](../../ARCHITECTURE.md#3-model-principles) |
| Intent | Elements are placed relative to grids, walls and openings; a solver derives the coordinates | [0012](../decisions/building.md#0012-datums-and-positions) |
| Datums | Plan positions are core faces (Rohbau); heights count from the storey's finished floor | [0012](../decisions/building.md#0012-datums-and-positions) |
| Derived values | Areas, lengths, volumes and joins are computed on demand, never stored | [`ARCHITECTURE.md` §3](../../ARCHITECTURE.md#3-model-principles) |
| Status flags | `existing` (Bestand), `demolish`, `temp`; plain elements are new | [`ARCHITECTURE.md` §3](../../ARCHITECTURE.md#3-model-principles) |

## Changing the model

| Term | Meaning | Defined in |
|---|---|---|
| Operation | One line with a prefix: `+` add, `~` set, `-` remove, `>` replace | [0014](../decisions/foundations.md#0014-operations-and-history) |
| Placeholder | `@a` names a new element inside a batch; `_` when nothing refers to it | [0014](../decisions/foundations.md#0014-operations-and-history) |
| Batch | `uea apply`: operations applied atomically, with who and why; rejected if it adds an error in a discipline it writes | [`ARCHITECTURE.md` §5](../../ARCHITECTURE.md#5-operations-and-batches) |
| Partial view | A slice of a big model to read and write (`uea view`, `apply --view --base`) | [0046](../decisions/foundations.md#0046-partial-views) |
| History and revert | Every batch is one entry in `log.jsonl`; `uea revert` applies its inverse as a new batch | [0009](../decisions/foundations.md#0009-history-revert-and-ids) |
| External edit | A `.uea` file changed by hand; the next command records it as a batch or stops with the errors | [0014](../decisions/foundations.md#0014-operations-and-history) |

## Between disciplines

| Term | Meaning | Defined in |
|---|---|---|
| Issue | What validation finds: a code (`E-…`, `W-…`), the element, the numbers and a fix | [`ARCHITECTURE.md` §7](../../ARCHITECTURE.md#7-validation), codes in [`reference.md`](../reference.md#issue-codes) |
| Affects | Errors an upstream batch causes downstream; reported, not rejected, and left for that discipline | [`ARCHITECTURE.md` §5](../../ARCHITECTURE.md#changes-that-affect-other-disciplines) |
| Request | `req` in `issues.uea`: a downstream discipline asks upstream for something (a Schlitz, a Durchbruch) | [0010](../decisions/foundations.md#0010-requests-in-the-model) |
| Waiver | An issue accepted on purpose, with who and why; always listed, never hidden | [0010](../decisions/foundations.md#0010-requests-in-the-model) |
| BCF | The requests exported for an architect who works outside UEA | [0032](../decisions/ifc.md#0032-bcf-requests) |

## Calculations and outputs

| Term | Meaning | Defined in |
|---|---|---|
| `norm` calculator | Ships with a pack, implements one method of one standard, has a validation report with cases worked out by hand | [0007](../decisions/foundations.md#0007-norm-and-custom-calculators), reports in [`docs/validation/`](../validation/) |
| `custom` calculator | Written by an agent for one project in its `calc/` folder; never presented as norm-compliant | [0007](../decisions/foundations.md#0007-norm-and-custom-calculators) |
| Office tables | What a method needs from the office: values of a licensed standard, the Land's rules, its own prices and texts; installed with `uea data add`, never in the repo | [0008](../decisions/foundations.md#0008-office-supplied-norm-data), [0028](../decisions/electrical.md#0028-norm-tables-and-electrical-calculators) |
| Export | A view for humans (IFC, PDF, DXF, XLSX, BCF); never read back into the model | [`ARCHITECTURE.md` §9](../../ARCHITECTURE.md#9-import-exports-and-renders) |
| Render | A plan image for an agent to check its own layout | [`ARCHITECTURE.md` §9](../../ARCHITECTURE.md#9-import-exports-and-renders) |
| IFC import | An architect's IFC mapped into `project.uea` and `arch.uea`, re-importable by GlobalId | [0029](../decisions/ifc.md#0029-ifc-import-of-walls-openings-and-rooms) to [0031](../decisions/ifc.md#0031-ifc-import-of-real-files) |

## The office and the plot

| Term | Meaning | Defined in |
|---|---|---|
| Leistungsverzeichnis | Titles and positions in `lv.uea`; code counts the quantities | [0048](../decisions/tender.md#0048-leistungsverzeichnis) |
| Bid | A bidder's prices read from GAEB 84 into `bid.uea` | [0051](../decisions/tender.md#0051-bids) |
| Fee offer | The Honorarangebot from the `hoai` results, a draft to sign | [0054](../decisions/tender.md#0054-offer-export) |
| Plot | The Baugrundstück in `site.uea` with the limits its plan sets | [0055](../decisions/site.md#0055-plot-and-baunvo) |
| Option | A variant of a building on a plot: its own project, often sketched with `uea block` | [0057](../decisions/site.md#0057-options-on-a-plot) |
| Activity log | What the CLI records per command for the dashboard; out of git | [0053](../decisions/foundations.md#0053-agent-dashboard) |
| `AGENTS.md` | What an office tells its agent; the office's rules, not UEA's | [`docs/templates/AGENTS.md`](../templates/AGENTS.md) |

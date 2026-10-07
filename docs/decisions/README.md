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
| 0015 | [Rooms, Fertigmaß and slab outlines are derived from walls](0015-rooms-and-finishes.md) | Accepted |
| 0016 | [Roofs as planes over the storey outline](0016-roofs.md) | Accepted |

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

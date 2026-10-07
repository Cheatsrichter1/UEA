# 0014: Operations, history and edits outside UEA

Status: Accepted
Date: 2026-10-07

## Context

`0009-history-revert-ids.md` decided that `log.jsonl` holds the history and that UEA assigns ids. Building it fixed the meaning of each operation, what the history stores, and how an edit made outside UEA becomes a batch.

## Decision

- `+` adds. An element whose ids UEA assigns gets a placeholder (`@a`) or `_`; a level, grid or type gets its name. An agent cannot give an explicit id; only revert and replay can, to restore an element.
- `~ id k=v flag "label"` sets fields. `k=` resets a field to its default; a required field cannot be reset. A bare value sets the positional field it fits (`~ d1 1.51x2.26`); if it fits several, UEA asks for `k=v`. `~ q1 done` records the current batch number.
- `-` removes one or more ids.
- `>` replaces a whole element and keeps its kind. The draft called it "move a grid". Because every position is relative, replacing a grid already moves everything placed on it, so `>` is the general replace.
- The history stores each batch's operations resolved: placeholders replaced by ids, lines in canonical form. It also stores the inverse operations (`- id`, `+ <old line>`, `> <old line>`), the ids assigned and the hash of each written file. Replaying the history rebuilds the model.
- An edit outside UEA shows up as a file hash that differs from the history. UEA then replays the history and diffs it against the files. The difference is recorded as an external batch, with operations, inverse and new ids, so it can be reverted like any batch and its ids are never reused. Files that do not parse stop UEA with `file:line` errors.
- A revert is rejected if a later batch touched any of the same ids; the error names that batch.
- A batch is rejected if it adds an error, identified by code, element and other elements involved, in a discipline it writes. `--dry-run` runs every check and writes nothing.
- Writes take an operating-system file lock on `.uea.lock`, which `uea init` puts in the project's `.gitignore`.

## Alternatives

- **A hidden snapshot of the last known state** to diff external edits against: simpler, but another artefact to keep in sync, and lost on a fresh clone.
- **Full file copies in the history:** large, and redundant with the operations.
- **Reject external edits:** agents edit files with their own tools, so UEA has to accept and record what they did.

## Consequences

- `log.jsonl` alone rebuilds the project. A project started from hand-written files records them as external batch 1.
- Replaying the history is only needed when a hash differs, so normal commands stay fast.
- An external edit that only reformats records an external batch without operations.

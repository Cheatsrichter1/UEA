# 0009: Project history, revert and ids

Status: Accepted; the details are fixed in `0014-operations-and-history.md`
Date: 2026-10-07

## Context

Every change must be revertible, and ids must never be reused, so that an old reference can never silently point at a new element. The `.uea` files describe the current state only. They cannot say which ids existed before or how to undo a batch.

## Decision

- `log.jsonl` is the project's history and part of the project, committed with it. Each entry holds time, `by`, message, the operations, their inverse operations, the ids assigned and a hash of each written file.
- `uea revert <batch>` applies the inverse operations as a new batch. The history only ever grows.
- UEA assigns ids. Inside a batch, a new element gets a placeholder (`@a`) that later operations in the same batch can reference; the output reports the real id. Levels, grids and types are named by the agent instead. The history records every id ever assigned, so none is reused.
- Edits made outside UEA are detected through the file hashes. If they validate, they are recorded as an external batch; if not, UEA stops and lists the errors.

## Alternatives

- **Git as the only history:** works only in git repositories, commits are coarser than batches, and reverting one batch among many needs git skills. A project can still use git on top.
- **Agents choose ids:** batches read slightly better, but the agent must know every id ever used, and two git branches will both create `w13`.
- **A next-id counter in `project.uea`:** prevents reuse, but gives no revert.

## Consequences

- `log.jsonl` grows with the project. For buildings this stays small.
- Reverting an old batch can conflict with later batches. UEA then rejects the revert and reports why, like any other batch.
- Merging two git branches needs a strategy for the history and for ids assigned on both branches (open question in `ROADMAP.md`).

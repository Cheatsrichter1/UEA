# 0046: Partial views

Status: Accepted (built)
Date: 2026-10-16

## Context

Version 2 starts with partial views (`FUTURE.md`). Tenders and cost estimates work on buildings bigger than a house, and a big project does not fit in an agent's context, even in the compact format. `uea show`, `get` and `find` already read a slice, but an agent cannot work on one: it cannot read all of `heat:OG` as lines, change them and write them back with the guarantee that it changed nothing else and that nobody changed the same elements in between. That guarantee is also what lets several agents work on one project at once.

What exists: one file per discipline (`0004`), a history in which every batch records the elements it touched (`0014`), and a revert that is rejected when a later batch touched the same elements (`0009`). Since 2026-10-16 the history is checked on every read for batch numbers and ids that a hand merge doubled (`ARCHITECTURE.md` §5).

## Decision

**A view is a selector, read at a base.** The selector names the slice, the base is the batch number of the history when the agent read it.

**The selector** reuses the scopes of `uea show`, so an agent learns one grammar:

| Selector | Selects |
|---|---|
| `heat` | the discipline |
| `heat:OG` | the discipline's elements on a level (as `show heat:OG` counts them) |
| `uv2` | the element and everything that references it, transitively, in any discipline: a board with its circuits, devices and cables; a wall with its openings and the devices on it |
| `elec:r3` | a room: what lies in it (as `find ... room=r3`), limited to the discipline |
| `heat:OG,plumb:OG` | several selectors, joined |

**`uea view <selector>`** prints the slice in the usual line format, so a line can be copied, edited and sent back as `> line`:

```
# view heat:OG · base 41 · 37 elements, 12 context
# context, read-only
level OG z=2.9 fb=0.15 head=2.26
wall w14 OG AW y=S+ x=W..E lb
...
# heat:OG
hk h7 OG ...
```

The context is every element outside the slice that the slice references, transitively upstream (host walls, levels, grids, types), so every reference in the view resolves. It is marked by the comment line, not per line, to keep lines copyable. Long views are paged like `find`. `--json` gives `{"base", "context", "elements"}`.

**Derived values come from the whole model.** A view is a scope on the project folder, not an extract: UEA still holds the whole model, so a room's area is right even when one of its walls is outside the slice, and `uea get` on an id in the view works as today. The agent never needs the rest to read a value.

**`uea apply --view <selector> --base <n>`** writes back as an ordinary batch:

1. Every element an operation changes or removes (`~`, `-`, `>`) must be in the slice; every element it adds (`+`) must fall in the slice once added. Otherwise the batch is rejected: `w9 is outside heat:OG`.
2. If a batch after the base touched an element this batch changes or removes, it is rejected with that batch, as a revert is: `batch 43 changed h7 after base 41. Read the view again`. Elements only referenced, not edited, do not conflict; the validation catches what a change upstream broke, as for every batch.
3. Then the batch runs as today: placeholders, ids at the merge, validation of the whole model, history, revert, issues for other disciplines.

`--base` also works without `--view`, for an agent that wants the base check on a whole-model batch. Without either flag `apply` is unchanged.

**Several agents.** Two agents whose views do not overlap cannot conflict: each batch touches only its own slice, and the base check only fails on a real overlap. On one machine the lock serialises the writes; across machines it is still git (below).

**Cost.** Before it lands, a generated large project in `bench/` (an apartment block of several storeys with every discipline) measures the tokens of `uea view` against the whole project and the time of a batch. The read must cost what the slice costs.

## Alternatives

- **File extracts:** `uea extract heat:OG > slice.uea`, edit the file, `uea merge slice.uea`. A person could open the file too. But it is a second copy that drifts, the merge has to diff it, and an agent works with batches anyway. Exports already serve people.
- **One file per discipline and level:** the format would carry the slices. It breaks `0004`, and a board's circuits span levels.
- **Locks per element or per view:** an agent takes a lock for its slice. Locks leak when an agent dies, and they block where the base check only fails on a real conflict.
- **No base, last write wins:** cheapest, but a batch could undo another agent's change without a word.
- **Only one step of upstream context:** smaller views, but a wall's grid or a device's level would not resolve, and the agent would need a second read.

## Consequences

- A new command `uea view`, two flags on `apply`, their help, `docs/reference.md` and a bench task (`view`, on the generated block `bench/large.py`).
- Building it showed that `show heat:OG` and `find ... level=` knew no level for elements that hang on something with one (a manifold in a niche, a loop in a room, a circuit on a board). They now take the level of what they hang on.
- A type has no level, so it cannot be added through a level view; it is written with the discipline's view or without `--view`.
- Measured on the block (`FUTURE.md`, Partial views): the view of a storey's heating is about a twelfth of all files; most of it is context. Whole-model validation takes 0.4 s per check at 1,073 elements and 3.1 s at 3,469.
- Validation stays whole-model for now (`ARCHITECTURE.md` §7). On the large project it may be too slow; incremental validation, checking only what a batch can have changed, is the next decision if the bench says so.
- The selector grammar is shared with `show`; an extension there (a room in every discipline, `r3` alone) extends views too.
- It narrows the open question on parallel branches (`0009`): agents on disjoint views on several machines still merge `log.jsonl` by git, but their element changes cannot conflict. The merge strategy for the history, `uea sync` or a host model stay open (`FUTURE.md`, Agents on several machines).

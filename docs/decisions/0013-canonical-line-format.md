# 0013: Canonical line format

Status: Accepted
Date: 2026-10-07

## Context

`0005-line-format.md` chose a line format and left the exact syntax as a draft. A parser and a writer need every detail fixed: where the label goes, how flags and defaults are written, what happens to comments, which names are allowed. The Haus Müller prototype is the test: it must load unchanged.

## Decision

- A line is `kind key positional... "label" key=value... flags`. The reader accepts the label and `key=value` fields anywhere after the key. Bare tokens fill the positional fields first; the rest must be flags of the kind.
- The writer always writes the canonical order: positionals, label, `key=value` in schema order, flags. A wall and a separator write their position before their span (`y=S+ x=W..E`). Fields at their default are left out. Numbers have at most four decimals (0.1 mm) and no trailing zeros.
- Bestand status is a flag: `existing`, `demolish` or `temp`. Without a flag an element is new. These match IFC's status values.
- `#` comments are read and ignored. When a batch writes a file, UEA rewrites it in canonical form and the comments are gone. Text that must stay goes into the label.
- Labels and quoted values cannot contain `"`.
- Level and grid names are a letter, then letters, digits or `_`. Type and project names may also contain `-` and `.` (`AW-365`, `NYM-J3x1.5`). No name may look like an id: a registered prefix followed by digits.
- File order: types first (by category in the pack's order, then by name), then the pack's kinds in order. Levels sort by `z`, grids by axis and coordinate, everything else in natural id order.

## Alternatives

- **Keep the label where the prototype had it** (`room r1 EG "Küche" kitchen`): reads well for rooms, but every kind would need its own rule for where the label goes.
- **Keep comments:** they would have to attach to elements and survive edits. Not worth it while agents, not humans, write the files.
- **Status as a field** (`status=existing`): more tokens on every Bestand element, and a flag reads just as clearly.

## Consequences

- The prototype loads unchanged. When UEA writes it, room labels move behind the use.
- One changed element is still a one-line diff.
- A hand edit with comments loses them on the next write of that file.

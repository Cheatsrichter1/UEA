# Contributing

[Wiki home](README.md)

The rules are in [`CLAUDE.md`](../../CLAUDE.md); this page is the checklist.

## Before you push

```bash
uv sync --all-extras
uv run ruff format
uv run ruff check
uv run pyright          # strict
uv run pytest
```

And depending on what changed:

| Changed | Also run |
|---|---|
| CLI output or the file format | `uv run python -m bench --write`, then compare with the committed `bench/results.md`: token cost and error rate must not get worse |
| Commands, kinds, fields, help or issue codes | `uv run python -m uea.reference` to regenerate `docs/reference.md` (a test fails otherwise) |
| Behaviour | A test, with expected values computed by hand, not copied from program output |

## Where a change gets written down

| Change | Write it in |
|---|---|
| A major decision, or a changed one | A record in [`docs/decisions/`](../decisions/README.md), then fix the docs that depend on it |
| A `norm` calculator | Its validation report in [`docs/validation/`](../validation/) |
| A release | [`CHANGELOG.md`](../../CHANGELOG.md) |

Each fact lives in one file; the others link to it.

## Things never to do

- Put DIN or VDE texts, tables or worked examples in the repo. Cite the clause; offices supply the tables ([0008](../decisions/0008-office-supplied-norm-data.md)).
- Present a `custom` result as norm-compliant, or word anything as if UEA certifies or replaces a licensed professional.
- Add a dependency without checking its licence: Apache-2.0-compatible, LGPL as a library, GPL only as a separate process ([0002](../decisions/0002-apache-2.0.md)).
- Copy anything from `private/` into tracked files.

## Language

Format, CLI output, help, code and docs are English. Legal, norm and role terms without an exact English equivalent stay German (Wohnfläche, Heizlast, Prüfingenieur …). Exports for humans are German ([0017](../decisions/0017-english-format.md)).

## Good first contributions

New exports only need the read API ([`ARCHITECTURE.md` §9](../../ARCHITECTURE.md#9-import-exports-and-renders)). Open work is listed under Backlog in [`FUTURE.md`](../../FUTURE.md).

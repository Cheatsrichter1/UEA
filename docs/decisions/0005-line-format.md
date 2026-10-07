# 0005: Own compact line format, IFC for exchange

Status: Accepted; the details are fixed in `0013-canonical-line-format.md`
Date: 2026-10-07

## Context

The model format is what agents read and write most, so it largely decides token cost. IFC is the exchange standard but too verbose and convoluted to work in. YAML and JSON are readable but repeat keys and punctuation on every element.

## Decision

UEA uses its own line format: one element per line, kind and id first, positional fields declared by the schema, then `key=value` fields and flags. Operations use the same syntax with a `+`, `~`, `-` or `>` prefix. Every line is strictly validated against its Pydantic schema. IFC4 is used for exchange, not as the working format: UEA exports it, using IFC names for kinds and properties wherever they exist, and imports the architect's IFC (`0011-ifc-import.md`).

## Alternatives

- **IFC (STEP or ifcJSON) as the working format:** lossless exchange, but many times the tokens and deeply nested.
- **YAML or JSON:** familiar and tooling exists, but more tokens for the same elements. Measured on the Haus Müller prototype (225 elements, `tiktoken` o200k_base): JSON 1.7× minified and 2.7× indented, YAML 2.0×. The earlier estimate of 3–4× was too high; the gap grows when the alternative stores coordinates instead of intent.
- **A general-purpose language (Python scripts as the model):** flexible, but not canonical, hard to validate and hard to diff.

## Consequences

- We maintain a parser and a writer, and agents need a short syntax help (`uea help`).
- One changed element is a one-line diff.
- `--json` output stays available for programs.
- The exact syntax was fixed in phase 1 (`0013-canonical-line-format.md`) and is measured on the token task set (`ROADMAP.md`, `bench/`) before the first release.

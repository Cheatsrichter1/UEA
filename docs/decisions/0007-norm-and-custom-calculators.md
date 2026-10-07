# 0007: `norm` and `custom` calculators

Status: Accepted
Date: 2026-10-07

## Context

Agents should be able to write or adapt calculations when a project needs something the built-in ones do not cover, for example more light than the norm requires. In Germany the signing engineer carries the Haftung, so it must always be clear whether a result comes from the norm method or from code an agent wrote.

## Decision

- A calculator is a small typed Python module with declared inputs and outputs.
- `norm` calculators ship with a pack, implement one method of one standard, cite its clauses, and are tested against hand-computed cases. The standard's worked examples run locally against office-supplied tables (`0008-office-supplied-norm-data.md`).
- `custom` calculators are written by agents for one project and live in its `calc/` folder.
- Every result records calculator, kind, version, inputs and the model state it ran on. A `custom` result is never labelled norm-compliant.

## Alternatives

- **Only built-in calculators:** safe, but blocks legitimate project-specific needs and one of UEA's main strengths.
- **Agents change built-in calculators in place:** fast, but destroys the trust in `norm` results.

## Consequences

- The `norm` calculators carry most of the quality work: worked examples, validation reports, clause citations.
- Reports must show the kind prominently, so a reviewer sees immediately what they are signing.
- Agent-written code runs on the user's machine, just like any other code the agent runs. Sandboxing can come later if hosted use needs it.

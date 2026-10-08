# 0010: Requests between disciplines live in the model

Status: Accepted (syntax still draft)
Date: 2026-10-07

## Context

References only point upstream, and validators only find what is already wrong. But a downstream discipline often needs something from upstream: electrical needs space for a sub-distribution board, plumbing needs a chase or a wall opening, structural needs a thicker wall. Planning goes round in a circle: each discipline drafts, asks the others, and improves, until nothing is open.

## Decision

- Requests are elements in a shared `issues.uea`. Any discipline may add one, pointing at the element or room it concerns.
- A request is an open issue of the discipline that owns its target, until that discipline's agent closes it (with the batch that resolved it) or rejects it with a reason.
- Agents may also talk to each other directly, however their framework allows. The request is the record: it survives the session, works across agent vendors, and the human sees it.
- The same file holds waivers: an issue that was accepted on purpose, for example a warning the Bauherr accepts, with who accepted it and why. Reports list every waiver, so the signing engineer sees them.

```
req q1 elec w7 "Schlitz 10x5 cm für Steigleitung"
waive wv1 W-ELEC-004 s5 "Steckdose neben Tür auf Kundenwunsch" by=elektroplaner
```

## Alternatives

- **Only agent-to-agent chat:** lost when the session ends, invisible to the human, and tied to one agent framework.
- **Downstream agents edit upstream files:** fast, but breaks file ownership and lets electrical move walls.

## Consequences

- `issues.uea` is the one file every discipline writes. Requests and waivers may reference any element and nothing references them, so the reference graph stays acyclic.
- `uea check` lists open requests together with the other issues.
- A later dashboard (`FUTURE.md`) can show open requests and waivers without new data.

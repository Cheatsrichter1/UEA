# 0001: No own agent: UEA is the substrate

Status: Accepted
Date: 2026-10-07

## Context

General AI agents (Claude, OpenAI, Grok, Hermes, OpenClaw and others) are built by large teams and improve quickly. A new project cannot compete with them, and does not need to. What these agents lack is engineering software they can work in efficiently.

## Decision

UEA does not build an agent, an agent router or a multi-agent framework. It provides the model, the CLI, the Python API, the calculators and the exports. Any agent with a shell can use it. Humans talk to their agent, not to UEA.

## Alternatives

- **Own agent with roles (Architekt, Statik, TGA, Zeichner):** the earlier plan. Duplicates work others do better and ties UEA to one vendor.
- **Own agent on top of UEA as a product:** possible later, but not part of the open-source core.

## Consequences

- Coordination between several agents (for example a lead agent over discipline agents) is the agents' job. UEA only guarantees atomic, validated changes and reports cross-discipline effects.
- UEA's output must work for agents of very different quality, so error messages and help must be self-explanatory.
- No chat, status or question features in UEA. Each batch carries a message explaining why it was made.
- What one discipline needs from another is a request in the model (`0010-requests-in-the-model.md`), not a message. Agents may still talk to each other directly.

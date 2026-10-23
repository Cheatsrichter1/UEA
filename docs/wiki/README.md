# UEA wiki

A quick way into the repository. The wiki explains and points; the facts live in the files it links to, so when the two disagree, the linked file is right.

UEA is building software for AI agents: agents plan a building in a compact text model through the `uea` CLI or the Python library, tested code does every calculation, and humans get the exports and sign. It is not an agent itself. The why is in [`VISION.md`](../../VISION.md).

## Pages

| Page | For |
|---|---|
| [Getting started](getting-started.md) | Install, a first project, where an agent reads next |
| [The line format](format.md) | How a line, a value, a position and an operation are written |
| [Commands by task](commands.md) | What `uea` does, from starting a project to handing it over |
| [Concepts](concepts.md) | The words UEA uses: elements, batches, requests, calculators, exports |
| [Code map](code-map.md) | Which folder and module does what |
| [Contributing](contributing.md) | The checks, the rules and where a change has to be written down |

## Where to find what

| Question | Answer in |
|---|---|
| What is UEA, and what is it not? | [`VISION.md`](../../VISION.md) |
| How is it built? | [`ARCHITECTURE.md`](../../ARCHITECTURE.md) |
| What is in a release? | [`CHANGELOG.md`](../../CHANGELOG.md) |
| Why was it done this way? | [`docs/decisions/`](../decisions/README.md), one record per decision |
| Every command, kind, field, issue code and calculator | [`docs/reference.md`](../reference.md), generated from the code |
| A complete house in the format | [Haus Müller](../prototype/haus-mueller/README.md) |
| What an office tells its agent | [`docs/templates/AGENTS.md`](../templates/AGENTS.md), a template to adapt |
| How far can a `norm` calculator be trusted? | [`docs/validation/`](../validation/), one report per calculator |
| What does it cost an agent in tokens? | The figures in [`README.md`](../../README.md), measured at commit `517c07e` |
| What comes next, partial views, the backlog | [`FUTURE.md`](../../FUTURE.md) |

## The ground rules in one breath

Built for agents, not humans. A human signs; UEA certifies nothing. Code calculates, agents decide. Text first and token-efficient. No own agent. No Revit clone. Disciplines hand over through the model. The full list is in [`CLAUDE.md`](../../CLAUDE.md).

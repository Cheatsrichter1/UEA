# UEA vision

UEA (Ultimate Engineering Assistant) is open-source engineering and building software made for AI agents, not for humans clicking buttons.

## Built for bots, not for humans

UEA is an AI-first program. Its users are LLMs and AI agents. It is not designed around human habits, human screens or human workflows, and it does not try to be pleasant for a human to operate.

If a human wants to review something, they ask their agent, and the agent renders or exports it. That is the only human-facing part, and it is a by-product.

Why: this is where engineering work is going. A senior engineer who lets agents do the production work on software built for them can take on several times as many projects (our target is five times as many) at lower cost. That holds even with a strong, expensive model as the lead agent, because the lead can hand smaller planning tasks to a cheaper model, and both spend their tokens on the work instead of on operating a GUI.

Every design decision in UEA follows from this. When a choice is between "easier for a human" and "cheaper and clearer for an agent", the agent wins.

## The problem

Engineering software today (Revit, Inventor, ArchiCAD and the rest) is built for humans. It assumes a person who looks at a screen, clicks a tool and drags a wall. Much of that code is decades old.

When an AI agent drives such a program, it has to work the way a human does. It runs a command, takes a screenshot, looks at it, thinks, takes another screenshot, and corrects itself. Even with a CLI or an MCP bridge, the agent fights a program designed around a GUI. Our working assumption is that this costs about ten times the tokens the task actually needs, and it is slow and error-prone. The benchmark (below) is there to measure it.

At the same time, AI agents are getting good enough to do real production work. Claude, OpenAI, Grok, Hermes, OpenClaw and others build general agents, and they will keep getting better. Nobody needs another agent. What the agents need is software they can work in efficiently.

## The idea

Build the engineering model and tools that agents work in natively:

- **Text, not screens.** The building is a compact, typed text model. Agents read it and change it through a CLI and a Python library. They get a rendered picture only when looking at something really helps.
- **Token efficiency is the core metric.** Every format, command and output is designed to say the most in the fewest tokens. We measure it.
- **Our own lean model, IFC for exchange.** IFC is the exchange standard, but it is too convoluted to work in. UEA uses IFC vocabulary inside, exports IFC, and imports the architect's IFC so Fachplaner can plan on it.
- **Code calculates, agents decide.** Agents make design decisions and orchestrate. Deterministic, tested code computes areas, loads, heat load, lighting, cable sizes and quantities.
- **Agents can write code.** When a project needs something the built-in tools don't cover (for example more light than the norm requires), the agent writes or adapts a calculation in typed code against the model API.
- **Design, not just calculation.** Planning is decisions: brick or drywall, tile or wooden floor, where the sockets go, how the circuits branch from the distribution board. The model holds these decisions, not only the numbers.
- **Bring your own agent.** UEA works with any agent that has a shell. It is not tied to one model vendor.

## What humans see

Humans need visuals, and they get them on demand. A senior engineer working with an agent says "show me the draft". The agent then calls UEA's exports: an IFC model, PDF or DWG plans, an Excel table of every socket or wall, or a rendered picture. The human reviews it, asks for changes and signs.

UEA does not build its own viewer or editor. Humans use the tools they already have to look at the exports.

## Who signs

A human signs. In Germany the Tragwerksplaner, the Fachplaner and the Prüfingenieur carry the Haftung, and nothing in UEA certifies or replaces a licensed professional. UEA gives one engineer the leverage of several.

That is why every result records how it was produced: which calculation method, which version, which inputs, and whether it is the norm method or a custom variant an agent wrote. A custom variant is never presented as norm-compliant.

## Scope

UEA starts with buildings and the disciplines of a German planning office:

| Discipline | Examples |
|---|---|
| Architektur | Walls, openings, rooms, floors, roofs, stairs, build-ups and materials, interior design |
| Elektro | Sockets, switches, luminaires, data outlets, circuits, distribution boards, cable sizing |
| Sanitär, Heizung, Lüftung | Pipe and duct networks, Heizlast, sizing |
| Statik | Load-bearing structure and structural calculation |
| Lighting (after v1) | Lighting design: atmosphere, luminaire choice, and calculation |

New buildings and Bestand: every element can be marked as existing or to be demolished, so Umbau projects work in the same model.

The core knows nothing about any one discipline. Each discipline is a domain pack on top of it, so the same approach can later reach steel and timber construction, mechanical parts and civil engineering (see `FUTURE.md`).

## How we prove it

1. **The Einfamilienhaus demo.** An off-the-shelf agent plans a normal single-family house end to end with UEA: architecture, electrical, plumbing, heating and ventilation, the structure (reviewed by a licensed engineer), the calculations, and exports a human can review.
2. **The token benchmark.** The same tasks are done through UEA, through a conventional tool driven by an agent, and by a human drafter, and the tokens, time and errors are counted. The results are published.

## Open source

UEA is fully open source (Apache-2.0). In the age of AI, closed engineering software gets copied or rebuilt anyway, so openness is the better bet: offices can trust what they run, and anyone can contribute an export, a calculator or a domain pack.

## What UEA is not

- Not an agent. Agents use UEA.
- Not a Revit clone. No GUI, no general geometry kernel, no attempt to cover everything Revit does.
- Not a replacement for the engineer who signs.

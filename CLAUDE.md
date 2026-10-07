# UEA: Ultimate Engineering Assistant

Open-source engineering and building software made for AI agents. Agents plan buildings in a compact text model through a CLI and a Python library; tested code does all calculations; humans get exports on demand and sign. UEA is not an agent itself; any agent with a shell can use it.

**Status:** design phase. No UEA code yet (only throwaway prototype scripts in `tools/`). The first work is `ROADMAP.md` phase 0 and phase 1.

## Docs

| File | Content |
|---|---|
| `README.md` | Front page for the open-source repo |
| `VISION.md` | What UEA is, why, what it is not |
| `ARCHITECTURE.md` | How it is built: core, domain packs, file format, CLI, calculators, exports, tech stack |
| `ROADMAP.md` | Phases up to the Einfamilienhaus demo, open questions |
| `FUTURE.md` | Ideas beyond the first scope. Not planned. |
| `docs/decisions/` | One file per major decision, with alternatives and reasons |
| `docs/prototype/` | Hand-written example projects that test the draft format; Haus Müller is the reference EFH |
| `tools/` | Throwaway prototype scripts (checks, exports, token counts); not UEA code and not held to the code rules |

Each fact lives in one file; the others link to it. When a decision changes, add or update its decision record and fix the docs that depend on it.

## Non-negotiables

- **Built for bots, not for humans.** The users are LLMs and AI agents. Humans only see renders and exports that agents produce for them. When a choice is between easier for a human and cheaper or clearer for an agent, the agent wins.
- **A human signs.** The Fachplaner, Tragwerksplaner and Prüfingenieur carry the Haftung. Never build or word anything as if UEA certifies or replaces a licensed professional.
- **Code calculates, agents decide.** Agents never compute areas, loads, heat load, lighting, cable sizes or quantities themselves. They read derived values, call a calculator, or write a calculator.
- **Text first, token-efficient.** Every format, command and output is designed for the fewest tokens that still read clearly. No GUI, no tools that make agents drive human programs.
- **No own agent.** UEA is the substrate. Agent orchestration belongs to the agents.
- **No Revit clone.** Extrusion-based model, IFC vocabulary, no general geometry kernel.
- **Handoffs go through the model.** Disciplines interact through references, issues and requests. Agents may also talk directly, but anything another discipline must act on is a request in the model.

## Working rules

### Code

- Python 3.12+, fully typed, pyright strict, Pydantic v2 for schemas, uv, ruff, pytest.
- Dependencies must be Apache-2.0-compatible: LGPL as a library is fine, GPL only as a separate process. Check the licence before adding anything.
- Add tests with every behaviour change. Prefer hand-computed expected values over values copied from program output.
- Any change to CLI output or the file format must keep or improve token cost and error rate on the token task set (`ROADMAP.md`).

### Calculators and norms

- Every `norm` calculator is a product: hand-computed tests with our own data, the standard's worked examples as a local test suite, clause citations, a validation report a Prüfingenieur could read.
- Results always record calculator, kind (`norm` or `custom`), version, inputs and norm tables used. A `custom` result is never presented as norm-compliant.
- DIN and VDE texts, tables and worked examples are licensed. Never put them in the repo; cite the clause and put only formulas and your own test data in code. Offices supply the tables from their own copies (`docs/decisions/0008-office-supplied-norm-data.md`).
- Catalogue values in examples are illustrative placeholders, not design data.

### Private

- The repository is public. Personal details, team and business plans live only in `private/`, which git ignores. Never copy them into tracked files.

### Language

- Docs and code in English. Keep German domain terms (Leistungsverzeichnis, Heizlast, Bestand, Haftung, Prüfingenieur, Fachplaner) as they are and explain around them.

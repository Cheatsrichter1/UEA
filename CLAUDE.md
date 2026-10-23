# UEA: Ultimate Engineering Assistant

Open-source engineering and building software made for AI agents. Agents plan buildings in a compact text model through a CLI and a Python library; tested code does all calculations; humans get exports on demand and sign. UEA is not an agent itself; any agent with a shell can use it.

**Status:** release 0.4.0, versions 1 to 4 done. What each release holds is in `CHANGELOG.md`; what comes next is in `FUTURE.md`.

## Docs

| File | Content |
|---|---|
| `README.md` | Front page for the open-source repo |
| `VISION.md` | What UEA is, why, what it is not |
| `ARCHITECTURE.md` | How it is built: core, domain packs, file format, CLI, calculators, exports, tech stack |
| `FUTURE.md` | v1 done, the order of the next versions, partial views, the backlog, open questions |
| `CHANGELOG.md` | What each release contains; add an entry with every release |
| `docs/wiki/` | A quick way in: getting started, concepts, code map, contributing; points to the files above |
| `docs/decisions/` | The major decisions with their reasons, one file per topic, one numbered section per decision |
| `docs/prototype/` | Hand-written example projects that test the draft format; Haus Müller is the reference EFH |
| `docs/validation/` | Validation report of each `norm` calculator |
| `docs/templates/` | Templates for offices, such as the example `AGENTS.md` an office gives its agent |
| `src/uea/` | The code: `core/` (syntax, schemas, model, ops), `packs/` (one per discipline), `derive.py`, `batch.py`, `project.py`, `cli.py`, `calc/`, `export/` |
| `docs/reference.md` | Every command, kind, field and issue code, generated from the code (`uv run python -m uea.reference`) |
| `tools/` | Helper scripts (the font subset); not UEA code and not held to the code rules |

Each fact lives in one file; the others link to it. When a decision changes, add or update its section in `docs/decisions/` and fix the docs that depend on it.

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

- Python 3.12+, fully typed, pyright strict, Pydantic v2 for schemas, uv, ruff.
- Before finishing: `uv run ruff format`, `uv run ruff check` and `uv run pyright` must pass. After a change to commands, kinds, fields, help or issue codes, regenerate `docs/reference.md` with `uv run python -m uea.reference`.
- Dependencies must be Apache-2.0-compatible: LGPL as a library is fine, GPL only as a separate process. Check the licence before adding anything.
- There is no test suite and no token bench (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`). Check a change by running it on a project, and keep CLI output and the format as short as they are or shorter.

### Calculators and norms

- Every `norm` calculator is a product: clause citations and a validation report a Prüfingenieur could read, with its cases worked out by hand on our own data. A report says which of its cases were verified by tests (up to commit `517c07e`) and which were not.
- Results always record calculator, kind (`norm` or `custom`), version, inputs and norm tables used. A `custom` result is never presented as norm-compliant.
- DIN and VDE texts, tables and worked examples are licensed. Never put them in the repo; cite the clause and put only formulas and your own test data in code. Offices supply the tables from their own copies (`docs/decisions/foundations.md#0008-office-supplied-norm-data`).
- Catalogue values in examples are illustrative placeholders, not design data.

### Private

- The repository is public. Personal details, team and business plans live only in `private/`, which git ignores. Never copy them into tracked files.

### Language

- The format, the CLI output, the help, code and docs are English (`docs/decisions/foundations.md#0017-english-format`). The help names a German term once where a German brief uses it: `knee: ... (Kniestock)`.
- In docs, German stays only for legal, norm and role terms without an exact English equivalent (Wohnfläche, Leistungsverzeichnis, Heizlast, Bestand, Haftung, Prüfingenieur, Fachplaner, Landesbauordnung) and in names (Haus Müller). Plain building words are English: eaves, ridge, floor plan, electrical.
- What people write stays in their language (labels, request texts), and exports for humans (drawings, calculation reports) are German.

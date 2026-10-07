<p align="center"><img src="docs/assets/logo.webp" alt="UEA logo: the letters U, E and A drawn as a copper pipe, a masonry wall with cables, and a roof with a lamp" width="420"></p>

# UEA: Ultimate Engineering Assistant

Open-source engineering and building software made for AI agents. Not for humans: it is an AI-first program, and humans see its work only through what agents render and export for them.

Agents plan buildings in a compact text model through a CLI and a Python library, instead of driving GUI programs through screenshots. Tested code does the calculations. Humans get IFC, PDF and DWG plans, Excel tables and renders on demand, review them and sign.

**Status:** phase 1 in progress. The core and the Architektur pack work: an agent can build, check and calculate the shell of an Einfamilienhaus and export it as IFC. Elektro, TGA and Statik are still designs. See `ROADMAP.md`.

## Why

Engineering software was built for humans clicking buttons. An AI agent driving it wastes most of its tokens looking at screens. UEA is built the other way round: text first, token-efficient, and usable by any agent with a shell. See `VISION.md`.

## Token cost

What it costs an agent to read one complete Einfamilienhaus, with Architektur, Elektro, Heizung, Sanitär and Lüftung (the [Haus Müller prototype](docs/prototype/haus-mueller/README.md), 226 elements):

| Same house as… | Tokens | vs. UEA |
|---|---|---|
| **UEA line format** (measured) | ~4,500 | 1× |
| Minimal, clean IFC (estimate) | ~50,000–150,000 | ~10–30× |
| IFC exported from Revit (estimate) | ~1–5 million | ~250–1,000× |
| Agent working in Revit via API and screenshots (estimate) | ~0.5–2 million for the whole house | ~100–400× |

Building the Architektur of that house through the CLI, storeys and roof included, takes about 2,400 tokens of commands and UEA output (`bench/results.md`).

The UEA figures are counted with `tiktoken`; the others are rough estimates, not measurements. In UEA a wall is one line; in IFC it takes 20–40 entity lines, and a Revit export adds geometry for every device, quantities and its own property sets. The benchmark in `ROADMAP.md` (phase 5) will measure the comparison properly.

## Try it

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
uv run uea help
```

An agent's first steps look like this:

```bash
uea init haus && cd haus
uea apply --by arch-agent -m "Geschosse, Achsen, Typen" <<'EOF'
+ project haus "EFH"
+ level EG z=0 fb=0.15 head=2.26
+ level OG z=2.875 fb=0.15 head=2.26
+ grid W x=0
+ grid E x=10.49
+ grid S y=0
+ grid N y=8.49
+ type AW-365 wall layers=putz:0.015,*ziegel:0.365,putz:0.02
EOF
uea apply --by arch-agent -m "Außenwände" <<'EOF'
+ wall @s EG AW-365 y=S+ x=W..E lb
+ wall @n EG AW-365 y=N- x=W..E lb
+ wall @w EG AW-365 x=W+ y=@s..@n lb
+ wall @o EG AW-365 x=E- y=@s..@n lb
+ room _ EG living at=@w+1,@s+1
EOF
uea get r1          # Rohbau 9.76x7.76=75.74 | Fertig 9.73x7.73=75.21 | ...
uea render EG       # out/plan-EG.png
uea export ifc      # out/haus.ifc
```

Development: `uv run pytest`, `uv run ruff check`, `uv run pyright`, and `uv run python -m bench` for the token task set.

## Scope

Buildings first: Architektur, Elektro, Sanitär, Heizung, Lüftung, lighting and Statik, each as a domain pack on a shared core. Later directions are in `FUTURE.md`.

## Docs

| File | Content |
|---|---|
| `VISION.md` | What UEA is, why, and what it is not |
| `ARCHITECTURE.md` | How it is built: core, domain packs, file format, CLI, calculators, exports |
| `ROADMAP.md` | Phases up to the Einfamilienhaus demo |
| `FUTURE.md` | Ideas beyond the first scope |
| `docs/decisions/` | Major decisions with alternatives and reasons |
| `docs/prototype/haus-mueller/` | A complete Einfamilienhaus in the draft format, written by hand |
| `docs/validation/` | Validation reports of the `norm` calculators |
| `src/uea/` | The code: core, packs, CLI, calculators, exports |
| `tests/` | Tests with hand-computed expected values |
| `bench/` | The token task set and its last results |
| `tools/` | Throwaway prototype scripts that check the prototype and generate its plans |

## Licence

Apache-2.0.

A human signs. UEA does not certify anything or replace a licensed engineer.

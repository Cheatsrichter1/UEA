<p align="center"><img src="docs/assets/logo.webp" alt="UEA logo: the letters U, E and A drawn as a copper pipe, a masonry wall with cables, and a roof with a lamp" width="420"></p>

# UEA: Ultimate Engineering Assistant

Open-source engineering and building software made for AI agents. Not for humans: it is an AI-first program, and humans see its work only through what agents render and export for them.

Agents plan buildings in a compact text model through a CLI and a Python library, instead of driving GUI programs through screenshots. Tested code does the calculations. Humans get IFC, PDF and DWG plans, Excel tables and renders on demand, review them and sign.

**Status:** design phase. There is no UEA code yet; `tools/` holds throwaway scripts for the prototype.

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

The UEA figure is counted with `tiktoken`; the others are rough estimates, not measurements. In UEA a wall is one line; in IFC it takes 20–40 entity lines, and a Revit export adds geometry for every device, quantities and its own property sets. The benchmark in `ROADMAP.md` (phase 5) will measure the comparison properly.

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
| `tools/` | Throwaway prototype scripts that check the prototype and generate its plans |

## Licence

Apache-2.0.

A human signs. UEA does not certify anything or replace a licensed engineer.

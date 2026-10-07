# UEA: Ultimate Engineering Assistant

Open-source engineering and building software made for AI agents. Not for humans: it is an AI-first program, and humans see its work only through what agents render and export for them.

Agents plan buildings in a compact text model through a CLI and a Python library, instead of driving GUI programs through screenshots. Tested code does the calculations. Humans get IFC, PDF and DWG plans, Excel tables and renders on demand, review them and sign.

**Status:** design phase. There is no UEA code yet; `tools/` holds throwaway scripts for the prototype.

## Why

Engineering software was built for humans clicking buttons. An AI agent driving it wastes most of its tokens looking at screens. UEA is built the other way round: text first, token-efficient, and usable by any agent with a shell. See `VISION.md`.

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

# 0003: Python as the core language

Status: Accepted
Date: 2026-10-07

## Context

UEA is built with AI coding agents. Agents using UEA will also write their own code against it (custom calculators, ad-hoc scripts). The AEC open-source libraries that matter most are Python-first.

## Decision

The core, the packs and the CLI are written in Python 3.12+, fully typed (pyright strict), with Pydantic v2 for schemas and validation, uv for packaging, ruff and pytest.

## Alternatives

- **Rust:** fast and type-safe, but the BIM ecosystem is thin, iteration is slower, and agents writing custom calculators would need a second language.
- **TypeScript:** good for a browser viewer, which UEA does not build. Weaker AEC libraries.
- **C++:** what IfcOpenShell and OpenCascade use, but far too slow to develop in for a small team.

## Consequences

- IfcOpenShell, Shapely, ezdxf and openpyxl are available directly.
- LLMs write Python best, so agent-written calculators are more likely to be correct.
- Hot paths (geometry, clash detection, solvers) can move to Rust later, behind the same API, once profiling shows a need.

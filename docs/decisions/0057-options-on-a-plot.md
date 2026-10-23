# 0057: Options on a plot: blocks, the site plan and the comparison

Status: Accepted (built)
Date: 2026-10-22

## Context

The end of plot evaluation (`FUTURE.md`) is a decision basis for a human: two or three options of what could be built, each with its measure of use, its Abstandsflächen, its areas and its rough costs, side by side. An agent sketches an option fast or not at all: a full model of walls, slabs and roofs per storey is twenty lines for a box. And the comparison must not be the agent's own table of numbers.

## Decision

- **`uea block x=W..E y=S..N storeys=3 [h=3 roof=flat|gable|hip|shed pitch= ridge= up= knee= from= use=]`** writes a simple building as an ordinary batch: per storey four walls of the type MASS (a 0.3 m core, no finish, so the rectangle is the outline at the outer faces), a slab and a room, and a roof on top; a roof other than flat on a storey DG of its own, with `knee=` under it. Storeys the model lacks are added from EG at ±0.00, `h=` apart, without floor build-up; existing storeys are used. The ends of x and y are grids or numbers. Because the result is ordinary model lines, every calculator, check, plan and export works on it, and the agent edits it like any other part of the model.
- **Each option is its own project** (a folder) with the same plot; the agent copies the plot line. No variants inside one model.
- **`uea export pdf site`**, the site plan (Lageplan): the plot with the length of each edge and its streets, the footprint (the storeys above the terrain) with its Vollgeschosse in Roman numerals, the Abstandsflächen and the building's main dimensions, with the legend of plot area, GRZ and GFZ. The Vollgeschosse, GRZ, GFZ and Abstandsflächen are those of the `baunvo` and `setback` results, drawn only while the model is as they computed it.
- **`uea compare <project>...`** writes `options.md` and `options.pdf` (German, A4 landscape): plot area, GR and GRZ, GF and GFZ, Vollgeschosse, each beside the plan's limit and in bold over it, whether the Abstandsflächen are kept, BGF, NRF, BRI, the gross costs and the costs per m² BGF. Every value is a result of the option (`baunvo`, `setback`, `din277`, `costs`); a missing or stale one is a gap in the table, named with the command that fills it, and the exit code is 1. The costs per m² BGF are the only figure it computes.

## Alternatives

- **A massing element** (`mass` in the model) that the calculators read beside the walls. Every calculator, plan and export would have to learn it, and an option could not grow into a design without being rewritten.
- **Variants inside one project** (a variant flag on elements). Every calculator would need to know which elements belong together; separate folders need nothing, and git keeps their histories apart.
- **The comparison recomputing each option.** It would hide which settings each result used, and a comparison would differ from the reports the office signs. Reading the results keeps them the same.
- **A yield estimate** from the office's rents or sale prices. Left for later: it needs office data of another kind (market prices) and a method to agree first.

## Consequences

- New: `src/uea/block.py`, `src/uea/compare.py`, `src/uea/export/siteplan.py`, the commands `uea block` and `uea compare`, the sheet `site`.
- `storey_ceiling` in `packs/arch/geometry.py` gives a storey's clear heights without a room, so `baunvo` works on blocks before they have rooms.
- Open: L- and T-shaped blocks (two blocks on the same storeys meet with two walls), a yield estimate, distances from the building to the plot's edges on the site plan, the site plan in survey coordinates.

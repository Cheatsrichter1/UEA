# 0055: The plot, the limits of its plan, and the measure of use per BauNVO

Status: Accepted (built)
Date: 2026-10-22

## Context

Version 4 starts with plot evaluation (`FUTURE.md`): given a plot, what may be built on it and which option fits. The first question a planner asks is the measure of use (Maß der baulichen Nutzung): how much of the plot the building covers (GRZ), how much floor it has (GFZ), how many full storeys (Vollgeschosse). The Bebauungsplan sets the limits, or, without one, the surroundings do (§ 34 BauGB).

Reading a Bebauungsplan and judging § 34 is the agent's work: plans are PDFs and drawings, and § 34 is a judgement. Measuring the building is code's work. The model had no plot.

The BauNVO is a federal ordinance and the Landesbauordnungen are Land law, both amtliche Werke, free to implement and cite. But the BauNVO leaves the definition of a Vollgeschoss to the Land (§ 20 Abs. 1), and the Länder define it differently: how far the ceiling must rise above the terrain, what clear height, over what share of which floor.

## Decision

- **A new discipline `site`** (`site.uea`), after `arch`, with the kind `plot`. It may reference the project and the architecture, and nothing references it.

```
plot _ "Flst. 123/4" outline=W-3,S-5;E+4,S-5;E+4,N+6;W-3,N+6 grz=0.4 gfz=0.8 storeys=2 plan="B-Plan Nr. 12"
```

  `outline=` is a new value: plan points joined by `;`, in the model's coordinates and relative to grids like any other point. The limits are the plan's: `grz`, `gfz`, `gr`, `gf` (absolute instead of a ratio, § 16 Abs. 2), `storeys` (most Vollgeschosse), `grz2` (the GRZ with § 19 Abs. 4, where the plan sets one) and `plan=` (where they come from). One plot per project; the agent outlines the building land (Bauland) of the Baugrundstück, since that is the plot's area per § 19 Abs. 3.
- **Checks:** E-SITE-001 an outline that crosses itself or encloses nothing; E-SITE-002 a second plot; W-SITE-003 storeys reaching beyond the plot, with how much of which storey.
- **`uea calc baunvo`**, a `norm` calculator:
  - A storey's area is its outline at the outer faces, as for the BGF (`din277.outline`), without the part of its slab that neither a roof of the storey nor the storey above covers: a roof terrace on a setback storey is no floor of it, an attic under its roof is.
  - GR (§ 19 Abs. 2) is the union of the storeys whose ceiling top rises above the terrain; GRZ = GR / plot area. With § 19 Abs. 4 the storeys below the terrain count too (Nr. 3), against `grz2=` or the GRZ plus 50 %, at most 0.8 (Satz 2).
  - A Vollgeschoss: the top of its ceiling (the structural top of the slab above) rises more than `rise` above the terrain, and its clear height is at least `height` over at least `share` of the floor area of the storey below it or of its own. The top storey has no slab above, so only the height test applies to it. Clear heights under a roof come from the roof's planes.
  - GF (§ 20 Abs. 3) is the area of all Vollgeschosse; GFZ = GF / plot area.
  - Each limit the plot gives is checked; any one exceeded makes the result not ok and is named.
- **The Land's Vollgeschoss rule is an office table, `full-storey`**: one row per Land (`land` as the project's `site=`, `rise`, `height`, `share`, `basis` below or own), copied from the current text of the Landesbauordnung, like the HOAI's fee tables (`0049`). Without it, GR and GRZ are still computed and the output names the table.
- **The terrain is the project's `ground=`**, flat; the project's `site=` names the Land.

## Alternatives

- **The limits on a separate kind** (`zoning`), for plans that set different limits on parts of a plot. Rare for one Baugrundstück; one plot with its limits reads in one line. A plot split by a plan's boundary can be split when it is needed.
- **The plot in the project pack.** The project file is shared by all disciplines; the plot is the site planner's, with its own checks and, later, setbacks and the site plan.
- **Vollgeschoss rules typed into the code**, one per Land. Sixteen definitions from memory, each with its own wording, would go unnoticed when wrong or outdated; the office copies the one it needs from the current text and the result cites the copy.
- **The agent marks the Vollgeschosse** (`full` on a level). It is a measurement against a rule, so code does it.
- **Using `din277.outline` as it is.** It widens a storey by its slab, so a setback storey would count its roof terrace.
- **The plot in survey coordinates** (ETRS89/UTM from the Liegenschaftskataster). Needs the georeference of the model, which belongs to the site plan; for now the agent places the plot in the model's coordinates.

## Consequences

- New: `src/uea/packs/site/` (kinds, geometry, `baunvo.py`), the value `Points` in `src/uea/core/values.py`, the discipline `site`, the office table `full-storey`, `uea help site`, the validation report `docs/validation/baunvo.md`.
- Not covered: garages, parking, driveways and Nebenanlagen (§ 19 Abs. 4 Nr. 1 and 2) are not in the model; Aufenthaltsräume in other storeys (§ 20 Abs. 3 Satz 2); § 21a; a sloping terrain; a Land whose rule the table cannot express (a Staffelgeschoss rule set back from the outer walls, a building height).
- Next in version 4: the Abstandsflächen per Landesbauordnung against the plot's edges, then massing options and their comparison (`FUTURE.md`, Plot evaluation).

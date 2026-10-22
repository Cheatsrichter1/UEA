# 0056: The Abstandsflächen per Landesbauordnung

Status: Accepted (built)
Date: 2026-10-22

## Context

After the measure of use (`0055-plot-and-baunvo.md`), the second question on a plot is how close the building may come to its edges. Every Landesbauordnung asks for Abstandsflächen in front of the outer walls, kept free on the plot itself. They follow § 6 of the Musterbauordnung, but each Land sets its own factor of the wall height, its own minimum, its own rule for steep roofs and, in some Länder, a different factor by Baugebiet.

## Decision

- **`uea calc setback`**, a `norm` calculator, in the site pack.
- **The façades are the edges of each storey's outline** (as for `baunvo`: at the outer faces, without slab nothing covers), one edge per straight façade, every storey above the terrain. Measuring per wall would leave the corners out, where one wall runs through.
- **H, the wall height,** runs from the terrain (the project's `ground=`) to where the façade meets the roof's outer skin: along an eaves wall the eaves, along a gable the gable, point by point. A façade under no roof of its storey goes up to the top of the slab above (the storey above stands on it, or a terrace). A steep roof adds `roof45` of its height (ridge minus eaves) over 45° and `roof70` over 70° to H at its eaves walls.
- **The depth** is factor × H, at least the minimum, square to the façade, so the area follows the façade's shape: a trapezoid along a gable, with a break where factor × H reaches the minimum.
- **The allowed area** is the plot and, on each edge the plot names with `street=1:12` (edge 1 from point 1 to 2, 12 m wide), the half of the street next to it. An area reaching beyond by more than 0.01 m² is named with how much; the result is then not ok.
- **The Land's rule is an office table, `setback`**: per Land and group of Baugebiete (`areas`: the plot's `use=` codes joined by space, or `*`) the factor, the minimum and the two roof shares, copied from the current Landesbauordnung like `full-storey`.
- **The plot gets `use=`** (the Baugebiet of the BauNVO: WA, MI, GE ...) and **`street=`**.
- The result keeps each area's outline, so the site plan can draw it (`0057`).

## Alternatives

- **Per wall, from the walls' own faces.** The corners where one wall runs through the other belong to that wall's end, which faces the other way; the façade's area missed them.
- **One rectangle per wall at its highest point.** Simpler, but along a gable it asks for far more than the law; most Länder measure the gable as it is.
- **Factors typed into the code per Land.** As for the Vollgeschoss (`0055`): sixteen rule sets from memory, unnoticed when wrong. The office copies its Land's.
- **The Abstandsflächen as a model check (an issue on every batch).** They need the office's table, which a check should not depend on; a calculator states the rule it used and records it.

## Consequences

- New: `src/uea/packs/site/setback.py`, the office table `setback`, the plot's `use=` and `street=`, the validation report `docs/validation/setback.md`.
- Not covered: two buildings on one plot towards each other, buildings allowed at the boundary without Abstandsfläche (garages), parts that may project (bay windows, balconies, canopies), a sloping terrain, and Land rules the table cannot express (the gable counted by its area, the privilege of the narrow sides, a reduced depth towards public green).

# Validation report: `setback` (Abstandsflächen per Landesbauordnung)

| | |
|---|---|
| Calculator | `setback` 0.1.0, kind `norm` |
| Standard | The Abstandsflächen of the Land's Landesbauordnung, after § 6 of the Musterbauordnung (MBO) |
| Code | `src/uea/packs/site/setback.py`; storey outlines from `src/uea/packs/site/baunvo.py`, roofs from `src/uea/packs/arch/geometry.py` |
| Tests | None in the repository (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`). The cases below were run on a project built for them, with the results given; **not verified by tests** |
| Review | **Not yet reviewed** by a licensed person. |

The Landesbauordnungen are Land law, amtliche Werke: their rules may be implemented and cited freely. The factor, the minimum and the rule for steep roofs differ by Land and sometimes by Baugebiet; the office copies its Land's values into the table `setback` from the current text (`docs/decisions/site.md#0056-setbacks`).

## Clauses and how they are implemented

| Clause (MBO) | Rule | Implementation |
|---|---|---|
| § 6 Abs. 1 | Abstandsflächen in front of the outer walls, kept free | One area in front of each edge of each storey's outline above the terrain |
| § 6 Abs. 4 Satz 2 | Wall height H from the terrain to where the wall meets the roof skin, or to its top | From the project's `ground=` to the top of the roof skin at the façade (the highest roof over the point, each roof the lowest of its planes plus its layers above the rafters); without a roof, the top of the slab above |
| § 6 Abs. 4 Satz 3 | Steep roofs add to H | At an eaves edge of a roof steeper than 45°: `roof45` × (ridge − eaves); steeper than 70°: `roof70` × that |
| § 6 Abs. 5 | Depth factor × H, at least the minimum | `factor` × H at each point along the façade, at least `min`; a break where they meet |
| § 6 Abs. 2 | On the plot itself; on public streets up to their middle | Beyond the plot, and the half of a street on an edge named in `street=`, by more than 0.01 m²: named, not ok |

## Cases

One project built for this report: EG z 0 and DG z 3, 10 × 8 m, walls of a 0.3 m core without finish, fb 0.15, terrain 0. A gable roof on the DG, ridge along x (eaves on the south and north), knee 0.5, rafters 0.2 m and nothing else. Synthetic table DE-HE, `*`: factor 0.4, min 3, roof45 0.3333, roof70 1. The values were worked out by hand and compared with the output at the commit that added the calculator.

**Case 1, 45°.** The rafter underside at the eaves face lies at 2.85 + 0.5 = 3.35; the skin above it is 0.2 × √2 = 0.283 thick vertically.

| Façade | By hand | Output |
|---|---|---|
| DG south and north (eaves) | H 3.633; 0.4 H = 1.45 < 3: depth 3.00 | H 3.63, depth 3.00 |
| DG west and east (gable) | H 3.633 + y up to 7.633 at the ridge (y = 4); depth 3.00, rising to 0.4 × 7.633 = 3.053 between y = 3.867 and 4.133 | H 3.63 to 7.63, depth 3.00 to 3.05 |
| EG all four | H 2.85 (top of the DG's slab); depth 3.00 | H 2.85, depth 3.00 |

**Case 2, a plot edge 2.9 m from the west façade.** Beyond the plot: 0.1 × 8 = 0.80 m² in front of the EG; in front of the DG 0.80 plus the peak, ½ × 0.267 × 0.053 = 0.007: 0.807 m².

| Façade | By hand | Output |
|---|---|---|
| EG west | 0.80 m² | 0.80 m² beyond |
| DG west | 0.81 m² | 0.81 m² beyond |

**Case 3, a street.** The south edge of the plot 2 m from the south façade: 1 × 10 = 10 m² beyond, in front of the EG and of the DG. With `street=1:6` the half of the street, 3 m, is allowed: all on the plot.

| | By hand | Output |
|---|---|---|
| Without `street=` | EG and DG south 10.00 m² each | 10.00 m² each |
| With `street=1:6` | none beyond | all on the plot or the street's half |

**Case 4, 50°.** The skin is 0.2 × 1.5557 = 0.311 thick vertically; the eaves at 3.35 + 0.311 = 3.661; the roof's height tan 50° × 4 = 4.767; the eaves walls get 0.3333 × 4.767 = 1.589.

| Façade | By hand | Output |
|---|---|---|
| DG south | H 3.661 + 1.589 = 5.250 | H 5.25 |
| DG west (gable, nothing added) | H up to 3.35 + 4.767 + 0.311 = 8.428 | H 3.66 to 8.43 |

## Assumptions to check when signing

- The terrain is the project's single height, flat. The Länder measure on the natural or the planned terrain, and some on its mean along the wall.
- The façade includes the exterior finish; insulation added to an existing building is privileged in some Länder.
- A façade without a roof goes up to the top of the slab above; a parapet is not in the model.

## Not implemented

- Two buildings on one plot towards each other; overlapping areas (§ 6 Abs. 3).
- Buildings and parts allowed at the boundary or in the Abstandsfläche (garages, bay windows, balconies, § 6 Abs. 6 to 8).
- A sloping terrain; Land rules the table cannot express (the gable by its area, the privilege of the narrow sides).

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

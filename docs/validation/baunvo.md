# Validation report: `baunvo` (measure of building use per BauNVO)

| | |
|---|---|
| Calculator | `baunvo` 0.1.0, kind `norm` |
| Standard | Baunutzungsverordnung (BauNVO) in the version of 21 November 2017, §§ 16, 19, 20; the definition of the Vollgeschoss of the Land's Landesbauordnung |
| Code | `src/uea/packs/site/baunvo.py`; the plot from `src/uea/packs/site/geometry.py`; storey outlines from `src/uea/packs/arch/din277.py`, clear heights from `src/uea/packs/arch/geometry.py` |
| Tests | None in the repository (`docs/decisions/0052-no-tests-in-the-repo.md`). The cases below were run on projects built for them, with the results given; **not verified by tests** |
| Review | **Not yet reviewed** by a licensed person. |

The BauNVO is a federal ordinance and the Landesbauordnungen are Land law, both amtliche Werke: their rules may be implemented and cited freely. What a Vollgeschoss is, the BauNVO leaves to the Land (§ 20 Abs. 1). The office copies its Land's rule into the table `full-storey` from the current text (`docs/decisions/0055-plot-and-baunvo.md`). Without it, GR and GRZ are still computed, and the output names the table.

## Clauses and how they are implemented

| Clause | Rule | Implementation |
|---|---|---|
| § 19 Abs. 3 | The plot's area is the area of the building land | The area of the plot's outline; the agent outlines the building land |
| § 19 Abs. 2 | Grundfläche: the part of the plot the building covers | The union of the storey outlines at the outer faces of every storey whose ceiling top rises above the terrain |
| § 19 Abs. 4 Nr. 3, Satz 2 | Structures below the terrain count; the GRZ may be exceeded by up to 50 %, at most up to 0.8 | The union of all storey outlines, against `grz2=` or max(GRZ, min(1.5 × GRZ, 0.8)) |
| § 20 Abs. 1 with the LBO | Vollgeschosse are the storeys the Land's law defines as such | Ceiling top (structural top of the slab above) more than `rise` above the terrain, and clear height at least `height` over at least `share` of the floor area of the storey below (`basis=below`) or of its own (`own`); the top storey has no slab above, so only the height test applies |
| § 20 Abs. 3 | Geschossfläche by the outer dimensions in all Vollgeschossen | The sum of the storey outlines at the outer faces of the Vollgeschosse |
| § 16 Abs. 2 | The plan limits GRZ or GR, GFZ or GF, the number of Vollgeschosse | Each limit the plot gives is checked; an exceeded one makes the result not ok |

A storey's outline is `din277.outline` (walls and slab at the outer faces, finishes included), less the part of its slab that neither a roof of the storey nor the slab of the storey above covers.

## Cases

Projects built for this report, with synthetic tables of our own; the values were worked out by hand and compared with the output at the commit that added the calculator.

**Case 1, a setback storey and a basement.** Plot 20 × 25 m = 500 m². Walls of a core 0.3 m without finishes, outer faces on the grids. KG z −2.8 (12 × 8 m), EG z 0, OG z 3 (10 × 8 m each), SG z 6 (6 × 8 m) under a flat roof over the SG alone; fb 0.15 everywhere, terrain −0.1. Table DE-HE: rise 1.4, height 2.3, share 0.6667, basis below. Limits grz 0.15, gfz 0.4, storeys 2.

| Value | By hand | Output |
|---|---|---|
| GR | EG, OG, SG: 10 × 8 = 80 m²; KG's ceiling top −0.15 lies 0.05 m below the terrain | 80.00 |
| GRZ | 80 / 500 = 0.160 > 0.15 | 0.160, over |
| With § 19 Abs. 4 | KG 12 × 8 = 96 m²; 96 / 500 = 0.192 against 1.5 × 0.15 = 0.225 | 0.192, ok |
| KG | ceiling top −0.05 m ≤ 1.4 | no |
| SG | 6 × 8 = 48 m² clear (flat roof 2.7 above the SSL, 2.55 above the FFL); 48 / 80 = 0.6 < 0.6667 | no |
| GF, GFZ | EG + OG = 160 m²; 0.320 | 160.00, 0.320 |

**Case 2, a gable roof storey.** Plot 20 × 18 m = 360 m². EG z 0 and DG z 3, 10 × 8 m, fb 0.15, terrain 0. Gable roof on the DG, ridge along x, 45°, knee 0.5 (rafter underside at the eaves walls' outer faces, above the SSL), rafters only. The underside lies 0.35 + t above the DG's FFL at t m in from an eaves face; 2.30 m clear from t = 1.95 on, from both sides: 10 × (8 − 2 × 1.95) = 41 m².

| Table share | By hand | Output |
|---|---|---|
| 0.6667 | 41 / 80 = 0.5125: DG no; GF 80, GFZ 0.222 | DG no (41.00 of 80.00 m²), GF 80.00 |
| 0.5 | DG yes; GF 160, GFZ 0.444 | DG yes, GF 160.00, GFZ 0.444 |

## Assumptions to check when signing

- The ceiling top is the structural top of the slab above (OK Rohdecke), the terrain the project's single height. Some Länder measure to the finished floor, or on the terrain's mean along the outer walls.
- The outlines include the exterior finish (render, ETICS). Some Länder exclude the insulation of an existing building from the measure.
- A storey's clear-height area is measured over its outline at the outer faces.

## Not implemented

- Garages, parking, driveways and Nebenanlagen (§ 19 Abs. 4 Nr. 1 and 2): not in the model.
- Aufenthaltsräume in storeys that are not Vollgeschosse (§ 20 Abs. 3 Satz 2), § 21a.
- A sloping terrain.
- Vollgeschoss rules the table cannot express: a Staffelgeschoss rule measured from the outer walls of the storey below, a building height instead of storeys.

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

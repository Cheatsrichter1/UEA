# Plot evaluation

The `site` pack: the plot, its measure of use, the Abstandsflächen and options compared for a client. The agent reads the Bebauungsplan and judges § 34 BauGB; code measures. Index in [README.md](README.md).

## 0055 Plot and BauNVO

- **A discipline `site`** (`site.uea`) after `arch`, with one `plot` per project:

```
plot _ "Flst. 123/4" outline=W-3,S-5;E+4,S-5;E+4,N+6;W-3,N+6 grz=0.4 gfz=0.8 storeys=2 plan="B-Plan Nr. 12"
```

  `outline=` is a new value: points joined by `;`, relative like any point. Limits: `grz`, `gfz`, `gr`, `gf` (§ 16 Abs. 2), `storeys` (most Vollgeschosse), `grz2` (§ 19 Abs. 4), `plan=`. The agent outlines the Bauland (§ 19 Abs. 3).
- Checks: E-SITE-001 (outline crosses itself or is empty), E-SITE-002 (second plot), W-SITE-003 (storeys beyond the plot).
- **`uea calc baunvo`** (`norm`): a storey's area is its outline at the outer faces without slab that no roof or storey above covers (a roof terrace is no floor, an attic is). GR (§ 19 Abs. 2) is the union of storeys rising above the terrain, GRZ = GR / plot area; with § 19 Abs. 4 also those below, against `grz2=` or GRZ + 50 % up to 0.8. A Vollgeschoss rises more than `rise` above the terrain and has `height` over `share` of the storey below or its own floor (the top storey: the height test only). GF (§ 20 Abs. 3) sums the Vollgeschosse. Every given limit is checked.
- **The Land's Vollgeschoss rule is an office table, `full-storey`** (per Land as the project's `site=`: `rise`, `height`, `share`, `basis`), copied from the current Landesbauordnung. The terrain is the project's flat `ground=`.

Why: sixteen Land definitions typed from memory would go unnoticed when wrong; Vollgeschosse are a measurement, not the agent's mark; `din277`'s outline would count a setback storey's roof terrace. Not covered: garages and driveways (§ 19 Abs. 4 Nr. 1, 2), sloping terrain, survey coordinates.

## 0056 Setbacks

- **`uea calc setback`** (`norm`): the façades are the straight edges of each storey's outline above the terrain.
- **H** runs from the terrain to where the façade meets the roof's outer skin, point by point (eaves along an eaves wall, the gable along a gable), or to the slab above a façade under no roof. Steep roofs add `roof45` of their height over 45° and `roof70` over 70°.
- **Depth** = factor × H, at least the minimum, square to the façade, so a gable gives a trapezoid.
- **Allowed area:** the plot and, per edge named in `street=1:12` (edge 1, 12 m wide), half the street. An area beyond it by more than 0.01 m² is named and fails.
- **Office table `setback`:** per Land and group of Baugebiete (`areas`: the plot's `use=` codes or `*`) the factor, minimum and roof shares. The plot gets `use=` (WA, MI, GE ...) and `street=`. The result keeps each area's outline for the site plan.

Why: per-wall areas miss the corners; one rectangle per wall at its highest point asks for more than the law along gables; as a model check it would depend on office tables. Not covered: two buildings on one plot, boundary buildings, projecting parts, sloping terrain.

## 0057 Options on a plot

- **`uea block x=W..E y=S..N storeys=3 [h=3 roof=flat|gable|hip|shed pitch= ridge= up= knee= from= use=]`** writes an ordinary batch: per storey four walls of type MASS (0.3 m core, no finish), a slab, a room and a roof (a pitched roof on a storey DG of its own). Missing storeys are added from EG at ±0.00, `h=` apart. Every calculator and export works on it, and it can grow into a design.
- **Each option is its own project** with the same plot line.
- **`uea export pdf site`**, the Lageplan: the plot with edge lengths and streets, the footprint with its Vollgeschosse in Roman numerals, the Abstandsflächen, main dimensions, plot area, GRZ and GFZ, all from the `baunvo` and `setback` results while they are current.
- **`uea compare <project>...`** writes `options.md` and `options.pdf` (German, A4 landscape): plot area, GR/GRZ, GF/GFZ, Vollgeschosse against the limits (bold when over), setbacks kept, BGF, NRF, BRI, gross costs and costs per m² BGF. Every value is a result of the option; a missing or stale one is a named gap and exits 1. Only the cost per m² is computed.

Why: a massing element would have to be taught to every calculator; variant flags would make every calculator track membership; recomputing in the comparison would hide the settings of the reports the office signs. Open: L- and T-shaped blocks, a yield estimate, the site plan in survey coordinates.

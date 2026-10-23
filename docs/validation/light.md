# Validation report: `light` (average illuminance of a room)

| | |
|---|---|
| Calculator | `light` 0.1.0, kind `norm` |
| Method | Utilisation factor method (Wirkungsgradverfahren), LiTG-Publikation 3.5, CIE 40; maintained illuminance per DIN EN 12464-1 |
| Code | `src/uea/packs/light/illuminance.py`; the targets in `src/uea/packs/light/kinds.py`, the luminaires' places from `src/uea/packs/mount.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_light.py` at commit `517c07e` |
| Review | **Not yet reviewed** by a licensed person. |

The utilisation factors are the luminaire maker's data or the LiTG's tables and are not in this repository (`docs/decisions/foundations.md#0008-office-supplied-norm-data`). The office supplies them as the table `light-uf`; the tests use invented values.

## What it computes

For each illuminance target of a whole room (`illum`): the average maintained illuminance on its working plane from the luminaires in the room, against the target. The result per target is `ok`, `low` (with how many luminaires of which type to add) or `without data`. Task areas are listed, not checked. The record is `out/light.json`, the report `out/light.md`.

## Rules as implemented

| Rule | Implementation |
|---|---|
| Average illuminance | Ē = MF · Σ Φ_i · UF_i / A, A the room's finished floor area |
| Room index | k_i = 2 A / (h_i U) per luminaire, U the finished perimeter, h_i the luminaire's height above the working plane; for a rectangle a · b / (h (a + b)) |
| Utilisation factor | The rows of `light-uf` with the type's `dist=` and `refl=`; between two values of k linear, outside the rows none |
| Luminous flux | The type's `flux=`; for LED luminaires the luminaire's flux and the table's room utilance |
| Maintenance factor | `mf=`, stated by the planner, 0 < MF ≤ 1 |
| Which luminaires | Those in the room (`mount.py`): in it, or on a wall face towards it. At or below the working plane: not counted, named |
| To add | n = ⌈(Ēm − Ē) · A / (MF · Φ · UF)⌉ of the type bringing the most flux to the plane, at its height; without luminaires the default type at the ceiling |

## Not implemented

- Point calculation: task areas, uniformity U0, illuminance on walls and ceiling.
- Glare (UGR), colour rendering, daylight, emergency lighting.
- Whether the luminaires are spread evenly enough and the room is rectangular enough for the method.

## Assumptions to check when signing

- The targets and working planes (`illum`), and that a dwelling's targets are the client's.
- The maintenance factor and the reflectances.
- That the table's utilisation factors belong to the luminaires used, with the flux they assume.

## Test cases (passed at commit `517c07e`)

Table cos1, 753: UF 0.60 at k 2, 0.65 at 2.5, 0.70 at 3, 0.75 at 4. Room r1: 9.38 × 7.38 m, A 69.2244 m², U 33.52 m, ceiling 2.54 m.

| Test | Case | Expected |
|---|---|---|
| `test_room_index_and_factor` | k of a 4 × 3 m room at 2 m; UF at a row, between rows, outside | 12 / 14; 0.70, 0.725; none |
| `test_average_illuminance_of_a_room` | two 2000 lm luminaires, at the ceiling (h 1.79, k 2.3074, UF 0.6307) and at 2 m (h 1.25, k 3.3043, UF 0.7152), MF 0.8 | 31.11 lx; low against 100 lx, 5 more; ok against 30 lx; half with MF 0.4 |
| `test_a_room_without_luminaires_takes_the_default_type` | no luminaire, 100 lx | 0 lx, 7 of the default type at the ceiling |
| `test_what_the_calculator_cannot_compute` | a type without `dist=`; reflectances without rows; a pendant below the plane | without data; without data, k named; the pendant named, not counted |
| `test_task_areas_scopes_and_settings` | a task area; scopes room, storey, target; MF 1.2; no table | listed, not checked; one target; stops |
| `test_haus_mueller_dining_room` | Haus Müller r2: a pendant at 1.6 m, a ceiling luminaire and four downlights, 150 lx | 125.83 lx, low, one more DK-18 |

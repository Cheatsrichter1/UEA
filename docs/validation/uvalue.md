# Validation report: `uvalue` (U-values of the build-ups)

| | |
|---|---|
| Calculator | `uvalue` 0.1.0, kind `norm` |
| Standard | DIN EN ISO 6946:2018-03, thermal resistance and U-value of building components |
| Code | `src/uea/packs/heat/uvalue.py`, `thermal.py`; surfaces from `envelope.py`; tables from `src/uea/calc/data.py` |
| Tests | Removed (`docs/decisions/foundations.md#0052-no-tests-in-the-repo`); the cases below passed in `tests/test_heatload.py` at commit `517c07e` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/foundations.md#0008-office-supplied-norm-data`). |

The conductivities and surface resistances are licensed (DIN 4108-4, DIN EN ISO 10456, DIN EN ISO 6946) and are not in this repository (`docs/decisions/foundations.md#0008-office-supplied-norm-data`, `docs/decisions/services.md#0033-u-values-and-heizlast`). The office supplies them in the tables `material` and `surface`; every result names the edition of each table.

## What it computes

The U-value of each build-up the rooms are made of, once for each way it is used. A build-up is a wall, slab or roof type, or a slab with the floor type of the room on it. The way it is used is the direction of the heat flow and what lies beyond it.

## Formula

R = d / λ for each layer; R_T = R_si + Σ R + R_se; U = 1 / R_T.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| d | the layer thicknesses of the types (`layers=`) |
| λ | table `material`, by the material name of the layer |
| R_si | table `surface`, by the direction of the heat flow: horizontal for walls, down for floors, up for ceilings and roofs |
| R_se | table `surface` against outside air; 0 against the ground; R_si of the same direction against a room, heated or not |

## Not implemented

- Air layers (DIN EN ISO 6946 treats unventilated, slightly and well ventilated ones differently).
- Inhomogeneous layers: rafters or studs with insulation between them (upper and lower limit of R_T).
- Corrections ΔU for fixings, air gaps and inverted roofs; tapered layers.

## Assumptions to check when signing

- The material names of the project and of the office's table must mean the same products.
- A slab's build-up includes the floor of the room on it; a finish under the slab is a layer of the slab type.

## Test cases (passed at commit `517c07e`)

Synthetic values of our own: λ gips 0.25, mw 0.05, putz 0.5, ks 0.25, stb 2, xps 0.04, eps 0.04, estrich 1 W/(m·K); R_si 0.10 up, 0.13 horizontal, 0.17 down; R_se 0.04.

| Test | Case | Expected |
|---|---|---|
| `test_u_values_of_the_build_ups` | exterior wall gips 0.01, mw 0.3, putz 0.02 | R = 0.04 + 6 + 0.04 = 6.08; U = 1 / (0.13 + 6.08 + 0.04) = 0.16 |
| | interior wall gips 0.01, ks 0.115, gips 0.01, a room beyond | U = 1 / (0.13 + 0.54 + 0.13) = 1.25 |
| | floor estrich 0.05 on stb 0.2, xps 0.1, the ground beyond | U = 1 / (0.17 + 2.65 + 0) |
| | flat roof stb 0.2, eps 0.2, outside air | U = 1 / (0.10 + 5.1 + 0.04) |
| | scope: one type | only that type's build-ups |
| `test_a_material_without_a_row` | the table lacks six materials | stops and names all six |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

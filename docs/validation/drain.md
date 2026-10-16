# Validation report: `drain` (Schmutzwasser-Rohrbemessung)

| | |
|---|---|
| Calculator | `drain` 0.1.0, kind `norm` |
| Standard | DIN 1986-100:2016-12 with DIN EN 12056-2 |
| Code | `src/uea/packs/plumb/drain.py`; sections from `geometry.py`, the hydraulics in `hydraulics.py` |
| Tests | `tests/test_plumb.py` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

All numbers of the standard come from the office's tables or the planner's settings (`docs/decisions/0035-plumbing.md`). Every result names the edition of each table.

## What it computes

For each section of the waste-water network, which is either a branch (Anschlussleitung), a stack (Fallleitung) or a pipe under the building (Grundleitung):
- the sum of the discharge units of the fixtures it takes water from;
- the waste-water flow;
- the size, and what that size may carry.

For each fixture, the length of its unvented branch against the limit. A branch that is too long, or a section no size can carry, makes the result fail. The record is `out/drain.json`, the report for humans `out/drain.md`.

## Formulas as implemented

- Q_ww = max(K · √ΣDU, DU_max).
- Branch to one fixture: the smallest size of the stack's type with DN ≥ the fixture's DN.
- Collecting branch: the smallest DN ≥ the largest DN upstream whose Q_max (table `drain-branch`) ≥ Q_ww.
- Stack: the smallest DN ≥ the largest DN upstream whose Q_max (table `drain-stack`) ≥ Q_ww.
- Under the building: the smallest size of the sewer's type with DN ≥ the largest DN upstream and Q ≥ Q_ww, where Q is what the pipe carries at the filling h/d by Prandtl-Colebrook with the hydraulic radius R_h of the wetted part:
  - v = −2 lg(2.51 ν / (4R_h √(2g · 4R_h · J)) + k_b / (3.71 · 4R_h)) · √(2g · 4R_h · J);
  - Q = v · A_wetted;
  - water at 10 °C.
- Branch length: the sum of the branch sections from the fixture to its stack or the sewer connection. The limit is single-lmax when every section carries only this fixture; otherwise the lmax of the DN at the stack.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Sections, lengths | the derived network (`geometry.py`): rectilinear, lower bounds, at the storey's FFL |
| DU, DN of the single branch | table `fixture-drain` by fixture |
| K | table `drain-k` by the setting `building` (default residential) |
| Q_max and l_max of unvented collecting branches | table `drain-branch` by DN |
| Q_max of stacks with main vent | table `drain-stack` by DN |
| single-lmax, k_b, h/d | table `drain-factors` |
| J | the setting `slope`, in %, required |
| Sizes | the drain types: the stack's for its branches and itself, the sewer connection's for the pipes under the building, else the default |

## Deviations and not implemented

- Branch heights and bends (the limits on height and on changes of direction), secondary vents and vented branches.
- The minimum slope and minimum velocity of the pipes under the building; the filling outside the building.
- Rainwater, lifting plants, backflow.

## Assumptions to check when signing

- The derived routes, the stack positions and the fixtures' assignment to the stacks.
- The slope given and the building use.

## Test cases

Synthetic tables of our own (`tests/test_plumb.py`):
- DU: sink 1, shower 1, WC 2, basin 0.5, with DN 50 for all but the WC's 100.
- K 0.5.
- Collecting branches: DN 50 holds 1 l/s, DN 100 holds 3 l/s, each up to 10 m.
- Stacks: DN 50 holds 1 l/s, DN 100 holds 4 l/s.
- single-lmax 4 m, k_b 1 mm, h/d 0.5. The drain type has DN 50 (50x2) and DN 100 (110x3).

| Test | Case | Expected |
|---|---|---|
| `test_drain` | the box with an OG, one stack, a basin behind the WC | under the building ΣDU 4.5, Q 2 l/s (the WC's DU), DN 100 holding what Prandtl-Colebrook gives for 104 mm at 1 %; the stack DN 100 for 2 l/s within 4; the branch to the WC and the basin DN 100 (the WC's), holding 3; the sink's 12.7 m and the shower's 7 m single branches too long; the type without DN 100 cannot take the WC; DN 50 suffices for a stack of 1 l/s |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |

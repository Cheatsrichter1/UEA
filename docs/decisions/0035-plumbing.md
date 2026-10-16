# 0035: Plumbing and pipe sizing, slice 6d

Status: Accepted (slice 6d built)
Date: 2026-10-11

## Context

Phase 6 plans the plumbing and the heating of the Einfamilienhaus. Slices 6a to 6c built the Heizlast and the heating elements (`0033`, `0034`). Slice 6d adds the plumbing: sanitary fixtures, the pipes for drinking water and waste water, and their sizing per DIN 1988-300 (drinking water) and DIN 1986-100 (drainage) as `norm` calculators. Haus Müller's draft `plumb.uea` had seven fixtures and nothing else; request q3 asks for a hole in the slab for a stack (Fallleitung) in the HWR.

## Decision

**Kinds** (`uea help plumb`):

| Kind | Id | Where |
|---|---|---|
| `san` | sa | a wall face like a device (`x=`/`y=`/`s=`), or a room (`at=`); the fixture positional: basin, sink, wc, urinal, bidet, shower, bath, wm, dw, tap, floor |
| `meter` | wz | a room, `at=` (default its middle); `p=` the lowest supply pressure (bar), `dp=` the loss of the meter and apparatus (hPa) |
| `riser` | sr | a room, `at=`; cold and hot water from its storey up through the storeys above |
| `stack` | fl | a room, `at=`; a Fallleitung from its storey up, vented through the roof |
| `sewer` | kn | a storey and `at=` a point, inside or outside: where the waste water leaves for the public sewer |

- **A fixture's water:** `water=cold|both|none`; by default basin, sink, bidet, shower and bath take both, the floor drain none, the rest cold. `z=` is its outlet; by default a planning height per fixture (a shower head 2.1 m, a basin 1.0 m), which only enters through the height difference to the meter.
- **Types:**
  - `type … pipe`: the drinking-water pipe system, with `sizes=16x2,20x2,…` (outer diameter × wall, mm), the roughness `k=`, and `bend=` and `tee=`, the loss coefficients ζ, from the manufacturer.
  - `type … drain`: a drain pipe system, with `sizes=100:110x2.7,…` (DN, then outer diameter × wall).
  - The meter takes the default pipe type or its `type=`. A stack's type serves the stack and its branches. The sewer connection's type serves the pipes under the building.
- **Hot water** comes from the heating's storage tanks whose type has `dhw`. Plumbing may now reference heating, but not the other way round (`ARCHITECTURE.md` §2). The tank type gets `dp=`, its loss on the drinking-water side. A tank with `dhw` no longer counts as supplying nothing (W-HEAT-004).

**The pipes are derived, not written**, like the cables (`0027`):
- **Cold water:** the shortest tree over the rectilinear distances from the meter to every fixture that takes water and to every `dhw` tank. On the meter's storey the tree grows from the meter, and a riser carries the water to the other storeys, where the tree grows from the riser. What no riser reaches joins the nearest pipe directly.
- **Hot water:** from each `dhw` tank to the fixtures that take hot water and have it as their nearest such tank, the same way.
- **Waste water:**
  - Each fixture runs to its stack on its storey, or to the sewer connection on the sewer's storey: `to=`, else the nearest in plan.
  - The fixtures on one stack and storey form the tree of branches (Anschlussleitungen), then the stack runs down to its foot, and the feet run to the sewer connection (Grundleitungen).
  - Waste pipes lie at the storey's FFL.
- The lengths are lower bounds. Each section (Teilstrecke) knows its fixtures, its length and its bends (one fewer than the axes it runs along). `uea get` shows each fixture's way to the meter, the tank and the sewer.

**Checks:**
- `W-PLUMB-001`: a fixture that takes water, and there is no meter.
- `W-PLUMB-002`: a fixture that takes hot water, and no tank heats drinking water.
- `W-PLUMB-003`: waste water with nowhere to go: no stack or sewer connection on its storey, `to=` one that does not reach it, or no sewer connection.
- `W-PLUMB-004`: a riser or stack nothing runs through.
- `W-PLUMB-005`: a second meter or sewer connection.
- `E-PLUMB-002`: a wall without a usable face.

**The sizing is not a check.** It needs the office's tables, and `uea check` must read the same on every machine (`0033`). Two `norm` calculators do it:

- **`uea calc water`** (DIN 1988-300) sizes both drinking-water networks:
  - **Peak flow:** ΣV̇_R per section. A tank counts on the cold side with the hot flows of its fixtures. Then V̇_S = a · (ΣV̇_R)^b − c, at most ΣV̇_R and at least the largest single V̇_R.
  - **Size:** the smallest of the pipe system within v_max.
  - **Losses:** Darcy-Weisbach with Colebrook-White, water at 10 °C or 60 °C, and ζ for each bend plus a tee where a section leaves another.
  - **Pressure at each fixture:** p_min,V − Δp_apparatus − Δp_geo − Σ Δp (− Δp_tank) ≥ p_min,Fl. Where a fixture falls short, the section with the largest loss on its way grows one size, until it has its pressure or nothing can grow. A shortfall fails the result.
  - **Inputs:** tables `fixture-flow` (V̇_R cold and hot, p_min,Fl by fixture), `peak-flow` (a, b, c by building use) and `water-factors` (v_max); setting `building=` (default residential).
- **`uea calc drain slope=<%>`** (DIN 1986-100) sizes the waste water:
  - **Flow:** Q_ww = K · √ΣDU per section, at least the largest DU.
  - **Sizes:**
    - a branch to one fixture takes the fixture's DN;
    - a collecting branch takes the smallest DN whose Q_max for an unvented branch holds Q_ww;
    - a stack takes the smallest DN whose Q_max for a stack with main vent holds Q_ww;
    - the pipes under the building take the smallest size that carries Q_ww at the slope, k_b and filling, by Prandtl-Colebrook.
  - No section is smaller than one it takes water from.
  - **Length:** each unvented branch, from the fixture to the stack or the sewer, against its longest length.
  - Too long or no size fails the result.
  - **Inputs:** tables `fixture-drain` (DU, DN), `drain-k`, `drain-branch` (Q_max, l_max by DN), `drain-stack` (Q_max by DN) and `drain-factors` (single-lmax, kb, fill); settings `slope=` (required) and `building=`.
- The formulas (Colebrook-White, Prandtl-Colebrook, the wetted circle) are in the code (`hydraulics.py`). The numbers of the standards come from the office. The validation reports are `docs/validation/water.md` and `drain.md`.

## Alternatives

- **Pipes written as elements, segment by segment.** That costs many lines and coordinates, and the agent would draw what code can derive. Like the cables, the derived tree gives the sizing what it needs: sections, the fixtures behind them, lengths and bends. An agent steers the networks with risers, stacks and `to=`. Pipe runs along installation zones and shafts are open.
- **A pipe node kind (Verteiler, T-piece) for the agent to place.** It would be a decision code can make. It can come with installation walls (Vorwandinstallation) and manifolds for drinking water.
- **Hot water from a plumbing heater kind.** Haus Müller heats its water in the heat pump's indoor unit, which is the heating's tank. A Durchlauferhitzer (fed by `elec`) is open.
- **V̇_R and DU on fixture types from the manufacturer.** The standards give the values per fixture; the office's tables carry them. Product values can override later.
- **The sizing as warnings in `uea check`.** `uea check` would then change with the tables installed on the machine (`0033`).
- **One v_max per kind of pipe and flow duration, as the standard distinguishes.** One value from the office's table for now; the review decides.

## Consequences

- Haus Müller's `plumb.uea` now has:
  - a pipe and two drain types (placeholders);
  - the meter in the HWR;
  - a riser and the stack q3 asked for, at the HWR's outer wall under the bath's WC;
  - the sewer connection outside.

  It loads with no errors and no plumbing warnings. All seven fixtures drain to the stack. The four that take hot water get it from the indoor unit t1, whose type now has `dp=`.
- Tested by hand on the box with an OG (`tests/test_plumb.py`):
  - placement; the three networks, section by section;
  - the checks and `uea get`;
  - the hydraulics against Colebrook's equation, the Moody chart and the full and half circle;
  - the peak flow;
  - the sizing of both networks with synthetic tables: the pressure at each fixture, a section growing for the worst way, a branch too long;
  - the command line.
- The help names `plumb` among the topics (+3 tokens in the bench's reading). The token task set is unchanged.
- Open:
  - circulation (Zirkulation) and its sizing;
  - fittings beyond bends and tees; one v_max for all sections;
  - the height limits of unvented branches, secondary vents, rainwater, lifting plants;
  - pipe runs along shafts and installation walls;
  - a Durchlauferhitzer as a plumbing heater fed by `elec`;
  - the plumbing in the sheets and the IFC export (6e and later);
  - the standards' worked examples as a private test suite, and the review.

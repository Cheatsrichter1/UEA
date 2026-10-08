# 0019: Stairs with a landing or winders

Status: Accepted
Date: 2026-10-08

## Context

A stair was one straight flight. Most German houses have a quarter-turn stair (viertelgewendelt, or with a landing) or a half-turn stair (zweiläufig mit Zwischenpodest). The footprint matters to the Wohnfläche (§3 Abs. 3 Nr. 2 WoFlV takes away stairs and their landings), to the slab opening and to the plan.

## Decision

- `shape=` is `straight` (the default), `l` (quarter turn) or `u` (half turn). `turn=l|r` says which way the second flight turns, seen while climbing. `up=` is the direction of the first flight.
- **Treads are counted once.** A stair of `n` risers has `n−1` treads, as before. `n1` is the number of the first tread in the turn: the first flight has `n1` risers and `n1−1` treads before the turn. At the turn the landing is one tread (a square `w x w` for `l`, `(2w+gap) x w` for `u`). `winders=m` (shape `l` only) replaces the landing with `m` winder treads in the same square, divided by rays from the inner corner at equal angles. The second flight has the `n−n1−m` treads that are left, with `m=1` for a landing.
- **Defaults:** `n1 = (n−m+1)//2`, so both flights are as equal as the risers allow; `gap=0.1` for `u` (the stair well).
- **Position:** `x=` and `y=` place the bounding box of the whole footprint, like the straight stair. The footprint polygon is the union of the flights and the turn; it is what voids (`over=st1`), the Wohnfläche and the room checks use.
- **Derived:** all risers are `rise/n`, the step rule 2h+a is checked on the flights, the landing is as deep as the stair is wide.
- IFC: `IfcStair` with the type `QUARTER_TURN_STAIR`, `QUARTER_WINDING_STAIR` or `HALF_TURN_STAIR`, an `IfcStairFlight` per straight flight, an `IfcSlab` `LANDING` for a landing and an `IfcStairFlight` `WINDER` for winders.

## Alternatives

- **A list of flights with a start point each:** covers any stair, but an agent would write coordinates for each flight and the landing, and the risers would have to be balanced by hand.
- **`n1` as the number of risers in the second flight:** the first flight is the one that sets the position, so it is the one that gets the number.

## Consequences

- Not covered: curved and spiral stairs, winders in a half turn, two landings, and stairs that continue through more than two storeys (each storey gets its own stair).
- The winder treads are straight-edged wedges. The walking line check of DIN 18065 (Lauflinie) is not made.

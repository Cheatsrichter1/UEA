# 0027: Cable routes, slice 3a: the lengths of the circuits

Status: Accepted (slice 3a built; the norm tables and calculators are 0028)
Date: 2026-10-09

## Context

Slice 3 of phase 3 (`0025-electrical-devices.md`) adds cable lengths and the first `norm` calculators (voltage drop, cable sizing). The calculators need a length for every circuit, and the quantity list (Materialliste) needs the metres of each cable type. It splits in two: the lengths first (this record, no norm data involved), then the table storage and the calculators (slice 3b, `0008-office-supplied-norm-data.md`).

The prototype only derived the routes roughly (`docs/prototype/haus-mueller/README.md`). The ROADMAP asked for runs "along the installation zones" (Installationszonen, DIN 18015-3). The zone widths and distances are in the licensed text, and a router that avoids obstacles in bands is a project of its own; the lengths are needed now.

## Decision

**A circuit's cable is a tree from its board.** It reaches every socket, connection and switch of the circuit and every luminaire that the circuit's switches control. The tree is the shortest one over the distances below (Prim's algorithm from the board). Ties go to the lower id, so the same model gives the same tree. It is derived, never stored: it follows when a device, a wall or a storey moves.

**The distance of a run is rectilinear:** the sum of the differences in x, y and z between the two places, in metres. A cable runs along walls and ceilings and vertically beside them, so a run is the sum of its legs, not the straight line. Heights are the absolute heights of the device centres, so a drop from a board at 1.4 m to a socket at 0.3 m counts 1.1 m.

**Every run gets 0.3 m** (`ALLOW` in `packs/elec/routes.py`) for the stripped ends and the loop at both devices. This is a planning allowance, not a norm value; the tables and the circuits view show lengths with it.

**A tree, not a chain.** A real installation branches at junction boxes (Abzweigdosen) and chains sockets. The shortest tree is the length of either to within the allowance, needs no order from the agent, and gives the path from the board to each device, which the voltage drop needs.

**Data outlets** have one run each from the board they are cabled to (`data dt1 w2 b2`), and one cable per port: a two-port outlet counts twice. The cable type is not in the model, so the quantity sheet calls them Datenleitung.

**What has no place is skipped.** A `feed` to an element of another discipline has no position until that discipline exists; it is reported as "not placed" on the circuit and adds no length. A circuit whose devices are all unplaced has no cable.

**Output.**

- `uea get c10`: a second line, `cable 58.1 m in 21 runs | farthest l18 at 25.4 m`, and the ids that were not placed. `uea get dt1` adds the cable length from its board.
- `uea export xlsx` adds the sheets **Leitungen** (every run: circuit, from, to, storey, length, and a sum), **Kabelmengen** (metres per cable type, and data cable) and two columns on **Stromkreise** (cable length, longest path). The notes say what the length is and that nothing is added for waste or for the feeder to the house connection (Hausanschluss).

**Haus Müller:** 19 circuits, 335 m in all (101.6 m NYM-J3x1.5, 155.2 m NYM-J3x2.5, 9.6 m NYM-J5x2.5, 68.7 m of data cable). The longest path is 27 m (c16).

## Alternatives

- **Straight lines between the devices.** Short by a third or more and wrong in the direction that makes a voltage drop look better than it is.
- **A route graph along the installation zones** (bands on the wall faces with their own widths and the obstacles around openings): the zone distances come from DIN 18015-3, whose text is licensed, and the routing needs the same care as pipes in phase 6. The zones can be added later as the graph the tree runs on, with this record's lengths as the lower bound.
- **The agent declares the order of the chain** (`s1 s2 s3`) or the length (`len=`): numbers an agent guesses are what UEA is there to take away. A declared length for a circuit that leaves the model (a garage, a lamp in the garden) will come as a field when the first project needs it.
- **A detour factor in the routes.** It belongs to the calculation that uses the length (the voltage drop adds a reserve and records it), not to the geometry.

## Consequences

- The lengths are a lower bound for the cable on site: the real route follows the zones, switch loops take extra cores, and the slab is crossed at a shaft or the stair. There are no shafts in the model yet (ROADMAP todo); a circuit across storeys crosses at the cheapest place. The sheets say "abgeleitet" and the calculators will add a reserve and record it.
- A switch is fed from the board like any device. A real lighting circuit runs the supply to the luminaire and a switch loop to the switch; the lengths differ by less than a run.
- Boards fed from other boards are still open (several boards, the feeder to the sub-board is not a circuit).
- The cable is not drawn on the installation plan. The derived runs are in the sheets and in `uea get`; drawing them (lightly, behind the symbols) can come with the zones.
- Open: shafts and chases, the declared length of a circuit that leaves the model, the place of a `feed` once the powered element exists, the zones as drawn bands.

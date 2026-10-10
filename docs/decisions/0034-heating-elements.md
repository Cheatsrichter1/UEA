# 0034: Heating elements, slice 6c

Status: Accepted (slice 6c built)
Date: 2026-10-10

## Context

Slices 6a and 6b (`0033-u-values-and-heizlast.md`) compute the Heizlast of each room. Slice 6c adds what covers it: the heating pack `heat.uea` with heat generators, storage tanks, manifolds and emitters, so an agent can plan the heating of the Einfamilienhaus and see whether each room gets its heat. Haus Müller's draft `heat.uea` (an air-to-water heat pump, an indoor unit with a tank, two manifolds in niches, underfloor heating in ten rooms) is the target. Pipe networks (Heizungsrohrnetz, pipe sizing, the hydraulic balance) and the Heizungsschema are later slices.

## Decision

**Kinds** (`uea help heat`):

| Kind | Id | Where | `src=` |
|---|---|---|---|
| `gen` | g | a storey and `at=` a point, inside or outside; `z=` above the FFL | |
| `tank` | t | a room, `at=` (default its middle) | a generator |
| `man` | hv | a niche (`man hv1 ni1 t1`: in the middle of the niche, on its face), or a wall face like a device (`x=`/`y=`/`s=`, `z=` 0.6) | a tank or a generator |
| `ufh` | uh | a room (`area=` the heated part, else the whole finished floor) | a manifold |
| `rad` | hk | a wall face like a device (`z=` 0.45) | a manifold, tank or generator |

**Types** carry the product data, from the manufacturer (placeholders in the examples):
- `gen`: `kw=` (heat output at the design point) and `source=`.
- `tank`: `vol=` and `dhw`.
- `man`: `outlets=` and the cabinet's `w=`.
- `ufh`: `spacing=`, `q=` (W/m² at the system's design temperatures and the floor covering) and `max=` (the longest loop with its connection lines).
- `rad`: `w=` (output at the design temperatures), `length=` and `height=`.

Each element without `type=` takes the type of its kind marked `default`.

**Derived** (`uea get`):
- The loops of each underfloor heating. The pipe in the room is its area over the spacing. Each loop also runs to the manifold and back: the rectilinear distance from the manifold to the room's finished outline, plus the height between them. The loops are as few as keep each within `max=`, all the same length.
- What each generator, tank and manifold supplies; each manifold's loops against its outlets.
- Each emitter's output: q × area, or the radiator's `w`.

**Checks:**
- `W-HEAT-001`: no type and no default type.
- `W-HEAT-002`: more loops than outlets.
- `W-HEAT-003`: a manifold too far for a loop.
- `W-HEAT-004`: a generator, tank or manifold that supplies nothing.
- `E-HEAT-002`: a wall without a usable face.

**The emitters against the Heizlast are not a check.** The Heizlast needs the office's tables, and `uea check` must read the same on every machine (`0033`). `uea calc heatload` checks it instead, once `heat.uea` has emitters:
- Each heated room lists its emitters with their output and how far they fall short of its load. A heated room with no emitter falls short by its whole load.
- The building's load is set against the generators' output.
- A shortfall makes the result fail (exit 1), as `vdrop` does over its limit.

**Feeds.** `feed fd1 g1 c7` in `elec.uea` now reaches the generator, tank or manifold it powers. The circuit's cable runs to it like to a device (`0027-cable-routes.md`). Packs now derive after the packs they may refer to, so electrical comes after heating.

## Alternatives

- **Emitter output from DIN EN 1264 (underfloor) and DIN EN 442 (radiators).** These are norm calculations with their own licensed tables and validation, and they need the system temperatures and the floor coverings. The manufacturer's declared output at the design temperatures is what planners take from the data sheet. A calculator can replace it later.
- **The number of loops as an input.** The agent would compute it. It is derived like cable lengths, and a type's `max=` is the manufacturer's rule.
- **Connection lines along a route through the rooms.** The rectilinear distance is a lower bound, like the cable lengths. A route needs the installation zones, as for cables.
- **Coverage as a warning in `uea check`.** `uea check` would then change with the tables installed on the machine.
- **A manifold as a device on a wall only.** Manifolds sit in niches (the request q1 asked for one), and a niche already says where.

## Consequences

- Haus Müller's `heat.uea` loads. It now has its types, and `rad` is new. There are no errors and no heating warnings. The EG manifold has 8 loops of 10 outlets and the OG manifold 7. The feeds to the heat pump and the indoor unit get their cables, so only the ventilation's circuit still feeds nothing. With the tests' synthetic tables, the WC and the bath are short of underfloor heating.
- Tested by hand on the box house (`tests/test_heat.py`):
  - placement outside, in a room, on a wall and in a niche;
  - five loops of 461.5 m of pipe within 100 m, 0.61 m from the manifold;
  - the checks, `uea get`, a feed's cable to the heat pump;
  - the emitters and the generator against the Heizlast.
- The help names `heat` among the topics (+2 tokens in the bench's reading). The token task set is unchanged.
- Open:
  - pipe networks and sizing, hydraulic balancing, flow temperatures;
  - output per DIN EN 1264 and DIN EN 442;
  - the Heizungsschema and heating sheets (6e);
  - IFC export of the heating elements;
  - whether a manifold fits its niche (its width against the niche's).

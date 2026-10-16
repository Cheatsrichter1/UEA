# 0037: Heating pipes, the hydraulic balance and the Strangschema, slice 6f

Status: Accepted (slice 6f built)
Date: 2026-10-11

## Context

Slice 6e (`0036-heating-and-plumbing-sheets.md`) left three things of phase 6 open: the heating pipes between generator, tanks, manifolds and radiators and their sizing; the hydraulic balance (hydraulischer Abgleich), which every new heating system in Germany needs; and a riser diagram (Strangschema) of the plumbing. The plumbing's pipes are already derived as trees (`0035-plumbing.md`); the heating's can follow the same pattern. The review by a licensed person stays with the user.

## Decision

**The heating pipes are derived, not written**, like the plumbing's:
- From each generator and tank: the shortest rectilinear tree over what it supplies directly (`src=`): tanks, manifolds, radiators. One section stands for a flow and a return pipe side by side.
- From each manifold: a home run (Anbindeleitung) to each radiator on it.
- The underfloor loops are the manifold's own circuits (`0034`).
- `uea get` shows each element's pipe from its source and the pipes it feeds.
- The tree code, the pipe sizes and the hydraulics moved to `packs/net.py`, `packs/pipes.py` and `packs/hydraulics.py`, which plumbing, heating and the ducts of phase 7 share.

**New type data** (from the manufacturer; placeholders in the examples):
- `type CU hpipe sizes=15x1,18x1,22x1,28x1.5 k=0.0015 bend=0.5 tee=1.3 default`: the heating pipe system. The default one serves every heating pipe.
- The underfloor type's loop pipe and roughness: `pipe=16x2 k=0.007`.
- The generator's loss on the heating side: `dp=` (hPa).

**`uea calc hydronic tb= n50= shielding= spread= vmax=`**, a `norm` calculator (`docs/validation/hydronic.md`). It follows Verfahren B of the hydraulic balance:
- **Load:** each room's Heizlast from `heatload`, with its settings and tables, shared among the room's emitters by their output.
- **Flow:** V̇ = Φ / (ρ c_p Δθ), with the spread `spread=` (the planner's, no default) and water at 40 °C.
- **Loops:** an underfloor heating's flow is shared equally by its loops; each loses R · l over its whole length.
- **Pipes:** each section and home run carries the flows behind it, takes the smallest size within `vmax=` and loses 2 · (R · l + Σζ ρv²/2) for its flow and return; ζ for each bend and a tee where it branches.
- **The manifold:** its worst circuit sets its loss; every other circuit's valve takes the difference, with the kv value (m³/h at 1 bar) to look up the presetting in the manufacturer's diagram.
- **The network:** from each generator or tank, the end with the largest loss sets the pump head; every other end is throttled by the difference. A tank separates the generator's circuit from the heating circuits; each has its pump. The generator's `dp=` adds to its pump's head.
- A section too fast in the largest size fails the result. Emitters in rooms the office's table `room-temp` does not heat get no flow, and the result says so.

**The heating sheets** draw the pipes: flow red, return blue and dashed, side by side, first along x, then along y, on the storey of their upper end, with a ring where a pipe changes storey. The tables Rohrleitungen and Rohrmengen list them (Heizung ab g1, Anbindeleitung; the quantities count flow and return).

**The Strangschema** (`uea export pdf plumb:schema`, `out/plumb-schema.pdf`, S-00, "o. M."):
- the storeys as bands, the highest on top, each over its FFL with its height;
- the meter and the tanks that heat drinking water on their storeys; the risers (cold and hot) and the stacks as verticals through the storeys they serve, the stacks up through the roof and down to the pipes under the building and the sewer connection;
- on each storey, the cold and hot distribution from the meter, a tank or a riser to the fixtures, and each fixture's waste water to its stack or the sewer connection.

Sizes are not on it, for the reason in `0036`. `plumb` and an export with no name write it after the storey plans.

## Alternatives

- **Heating pipes written as elements.** As for the plumbing (`0035`): many lines for what code can derive, and the sizing needs only sections, lengths, bends and what they serve.
- **The flow from the emitter's output instead of the room's Heizlast.** It needs no tables, but a balance gives each room the flow its load needs; an emitter larger than the load would get too much. Verfahren B starts from the room-by-room load.
- **A spread per emitter type** (5 K for underfloor heating, 10 K for radiators). Real systems mix them behind a mixing valve, which UEA does not model yet. One spread per calculation is the honest first step; mixers can follow.
- **The pump and the valves as elements with their curves.** The result gives the head and the kv; the planner picks the products.
- **One calculator for pipes and balance.** The sizing needs the flows, and the flows need the Heizlast: they belong together. `heatload` stays the calculator for the load alone.
- **The Strangschema to scale, with storey heights.** A riser diagram is read as a principle; the FFL heights are written on it.
- **Sizes on the Strangschema.** Decided against in `0036`.

## Consequences

- Haus Müller's `heat.uea` has the copper pipe type, the loop pipe on the underfloor type and the heat pump's loss. Its pipes: 3.9 m from the heat pump to the indoor unit, 12.7 m from there to both manifolds. With synthetic tables, `uea calc hydronic` finds the bath's loop the index circuit at hv2, and the head of the heating circuit's pump.
- Tested by hand (`tests/test_hydronic.py`): the derived sections on the box, the shares and flows, the sizes against v_max, the loss of a section, a loop and a home run, the valve and its kv, the throttle and the pump heads, a pipe system too small, a storage room, missing data, the sheets and the tables, the command line. The Strangschema in `tests/test_tga_export.py`.
- `uea get` shows a line of pipes on generators, tanks, manifolds and radiators. The token task set is unchanged.
- Open:
  - mixing valves and a spread per circuit; the flow temperature;
  - the losses of the manifold, the radiators and the valves themselves, and valve authority;
  - output per DIN EN 1264 and DIN EN 442;
  - the sizes on the sheets once a result is fresh;
  - heating and plumbing in the IFC export;
  - the review (the user).

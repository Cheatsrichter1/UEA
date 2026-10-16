# 0042: Emitter output, mixing circuits and the hot-water circulation

Status: Accepted
Date: 2026-10-12

## Context

Phase 6 left open: emitter output per DIN EN 442 and DIN EN 1264, a spread and mixing valves per circuit, and the circulation of the hot water. Until now an emitter's output was the type's number at the system's design temperatures, every circuit had the system's spread, and the hot water ran to its fixtures with no circulation.

## Decision

**Emitter output** (`packs/heat/emitters.py`). A type keeps its output at the design temperatures (`w=`, `q=`), or gives the manufacturer's test values instead:

- Radiator: `wn=` (the standard output at 75/65/20 °C) and `n=` (the exponent); Φ = Φ_n · (Δθ/Δθ_n)^n with the logarithmic excess temperature (DIN EN 442-2).
- Underfloor heating: `kh=`, the equivalent heat transmission coefficient K_H for the floor covering; q = K_H · Δθ_H (DIN EN 1264-2). The mean floor surface temperature follows from the basic characteristic curve, and `uea calc heatload floor=<°C>` (and `bathfloor=`) fails a floor that is warmer.

The temperatures of an emitter are its manifold's (`man ... flow= spread=`), else the system's, given to `heatload` and `hydronic` as `flow=` and `spread=`. The room temperature is the Heizlast's. Without temperatures a type of test values has no output, and the room is short.

**Mixing circuits.** A manifold with `mix` has a mixing valve and its own pump: its circuits run at its `flow=` and spread, and it draws V̇ = Φ / (ρ c_p (θ_V,system − θ_R,circuit)) from the system, which needs the system's `flow=`. In the balance it is an end with nothing behind it; its throttle is what the mixing valve takes, with kv; its pump lifts its worst circuit.

**Circulation** (`recirc zk1 t1` in `plumb.uea`, `packs/plumb/recirc.py`).

- The circulation pipe runs back beside the tank's hot-water pipes, all but the branches that end at a fixture and serve only it (Einzelzuleitungen). It is derived, drawn dashed beside the hot water on the plumbing plans and in the Strangschema.
- `uea calc recirc loss=<W/m> dt=<K> dead=<l>` follows the short method of DIN 1988-300. Each circulated section's flow carries the heat it and everything beyond it lose, at the allowed temperature drop. The circulation pipe is sized within v_max. The pump head is the worst end's loss through the hot and the circulation pipe, and the other ends' regulating valves throttle the difference.
- The branches without circulation are checked against `dead=`, the most water they may hold. DVGW W 551's 3 litres are the planner's to set.
- `W-PLUMB-007`: a circulation of a tank with nothing to circulate.

## Alternatives

- **Output tables in the code** (radiator exponents, K_H by covering): catalogue and norm data, the manufacturer's and the office's.
- **Circulation along every hot-water pipe:** the branches to single fixtures are short in a house, and circulating them costs heat for nothing; the 3-litre check says when one is too long.
- **The differential method of DIN 1988-300:** more exact for large systems; the short method is the standard's for buildings like the Einfamilienhaus.

## Consequences

- `heatload` 0.3.0 and `hydronic` 0.2.0: `spread=` moves to the Heizlast's settings, optional there and required by `hydronic`.
- New calculator `recirc` 0.1.0 with its validation report (`docs/validation/recirc.md`).
- Not done: edge zones and downward losses of heated floors, the mixing valve's authority, thermostatic circulation valves, the loss of the circulation pipe itself.

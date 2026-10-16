# Validation report: `hydronic` (Rohrnetz und hydraulischer Abgleich)

| | |
|---|---|
| Calculator | `hydronic` 0.2.0, kind `norm` |
| Method | Verfahren B of the hydraulic balance, on the Heizlast per DIN EN 12831-1:2017-09 |
| Code | `src/uea/packs/heat/hydronic.py`; the pipes from `geometry.py`, the hydraulics in `src/uea/packs/hydraulics.py`, the Heizlast in `heatload.py` |
| Tests | `tests/test_hydronic.py` |
| Review | Reviewed by a licensed person, outside this repository. The review record and the run of the standards' worked examples are private, since the standards are licensed (`docs/decisions/0008-office-supplied-norm-data.md`). |

The settings `spread`, `vmax` and `flow` are the planner's, and so are a manifold's own `flow=`, `spread=` and `mix`; the Heizlast's settings and tables are those of `heatload`. The pipe sizes, roughness and ζ come from the model's types (`docs/decisions/0037-heating-pipes-and-strangschema.md`). Every result names the edition of each table.

## What it computes

For each emitter: its design heat flow and water flow. For each section of the heating pipes from a generator or tank: the flow, the size, the velocity, the loss per metre and the loss of flow and return. For each circuit of a manifold (an underfloor heating's loops, a radiator's home run): the flow, the loss and what its valve must take, with its kv. For each end of a generator's or tank's pipes: the loss of its way and how much to throttle it. For each generator and tank with pipes: the pump's flow and head. For each mixing manifold: the flow it draws from the system and the flow of its circuits, what its mixing valve takes and its kv, and the head of its own pump. A section faster than v_max in the largest size makes the result fail. The record is `out/hydronic.json`, the report `out/hydronic.md`.

## Formulas as implemented

- Φ_e = Φ_HL,room · P_e / Σ P (P: the output of each emitter of the room at its circuit's temperatures, as `heatload` gives it; equal shares if none has one).
- V̇_e = Φ_e / (ρ c_p Δθ), ρ = 992.2 kg/m³, c_p = 4.179 kJ/(kg·K) (water at 40 °C), Δθ its manifold's `spread=`, else the setting.
- Mixing manifold (`mix`): from the system V̇_primary = Σ Φ_e / (ρ c_p (θ_V,system − θ_R,circuit)), θ_R,circuit = its `flow=` − its spread; its circuits carry Σ V̇_e. On the system's side it is an end with no loss behind it; its throttle is what the mixing valve takes, kv at V̇_primary. Its own pump: Δp of its worst circuit.
- Loops: V̇_loop = V̇_e / n; Δp_loop = R · l_loop over the loop's whole length with its connection lines, the loop pipe and k of the underfloor type; no ζ.
- Size: the smallest of the heating pipe type with v = V̇ / (π d_i² / 4) ≤ v_max; the largest if none.
- R = λ / d_i · ρv²/2, λ by Colebrook-White (λ = 64/Re below Re 2320), ν = 0.658 · 10⁻⁶ m²/s.
- Section and home run: Δp = 2 · (R · l + Σζ · ρv²/2), Σζ = bends · ζ_bend (+ ζ_tee where the section does not start at the generator or tank).
- Manifold: Δp_man = max Δp_circuit; Δp_valve = Δp_man − Δp_circuit; kv = V̇ [m³/h] / √(Δp_valve [bar]); "open" below 1 hPa.
- Network: need_end = Σ Δp of its way + Δp_man (0 for a radiator or a tank); throttle = max need − need_end; head = max need + Δp_generator.

## Inputs and how they are chosen

| Input | Source |
|---|---|
| Φ_HL per room | `heatload` with the settings `tb`, `n50`, `shielding`, `groundwater`, `te`, `tme` and its tables |
| Δθ | the manifold's `spread=`, else the setting `spread` |
| θ_V of the system | setting `flow` (needed with a mixing manifold) |
| v_max | setting `vmax` |
| Sections, lengths, bends | the derived heating pipes (`geometry.py`): rectilinear, lower bounds; between storeys through the hole of `via=` (`docs/decisions/0039-openings-without-a-fill.md`) |
| Loops and their length | the derived loops of each underfloor heating (`0034`) |
| Sizes, k, ζ_bend, ζ_tee | the heating pipe type marked default (`type … hpipe`) |
| Loop pipe and k | the underfloor type's `pipe=` and `k=` |
| Δp_generator | the generator type's `dp=` |

## Deviations and not implemented

- The mixing valve's authority and its characteristic are not checked; no bypass, no injection circuit.
- No loss of the manifold, the radiators, the valves or the fittings of the loops; no valve authority. The presetting comes from kv and the manufacturer's diagram.
- Emitter output as `heatload` gives it (type values, or DIN EN 442-2 and 1264-2); no edge zones, no downward losses of a heated floor.
- A tank separates circuits hydraulically; a heat pump's indoor unit without a buffer is modelled as one.
- No pump curve; the head is the requirement at the design flow.

## Assumptions to check when signing

- The derived pipe routes and their lengths, which are lower bounds.
- The spread against the emitters' design temperatures.
- The Heizlast and its assumptions (`heatload.md`).

## Test cases

The box of `tests/test_heatload.py` with its synthetic tables: r1 (living) with underfloor heating from a manifold on w5, r2 (bedroom) with two radiators of 800 W, one from the tank, one from the manifold. Copper 15x1, 18x1, 22x1 with k 0.0015 mm, ζ 0.5 for a bend and 1.3 for a tee; the loop pipe 16x2 with k 0.007 mm; the heat pump's dp 100 hPa; Δθ 5 K, v_max 0.5 m/s.

| Test | Case | Expected |
|---|---|---|
| `test_the_pipes_are_derived` | g1 (11, 1), t1 (1, 7), hk1 on w3, hv1 on w5's west face, hk2 on its east face | g1>t1 16 m; t1>hk1 7 + 0.7 + 0.45 m; hk1>hv1 3 + 6.7 + 0.15 m; hv1>hk2 0.115 + 6 + 0.15 m |
| `test_flows_sizes_and_the_balance` | the whole balance | uh1 carries r1's load, hk1 and hk2 half of r2's; V̇ = Φ / (992.2 · 4.179 · 5); t1>hk1 in 22x1 (18x1 over 0.5 m/s); its Δp with ζ 1, hk1>hv1 with ζ 2.3; the loop's and the home run's Δp; hk2's valve and kv; hk1 throttled by the rest of hv1's way; the pump heads, g1's with its 100 hPa |
| `test_too_fast_and_unheated` | a pipe system of 10x1 only; r2 a storage room | fails; hk1 and hk2 get no flow |
| `test_what_it_needs` | no default hpipe, no loop pipe, spread 0 | stops and names it |
| `test_a_mixing_circuit` (`tests/test_emitters.py`) | hv1 at 35/30 °C with mix, system 55/45 | hv1's emitters at 5 K, hk1 at 10 K; primary Σ Φ / (ρc · 25); t1>hk1 carries hk1 and hv1's primary flow; hv1's pump the worst circuit; the mixing valve takes hv1's throttle; no flow= or a warmer circuit stops |
| `test_on_the_sheets` | the heating plan and the tables | flow and return lines, the sections and their quantities |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.1.1 | Pipes that change storey run through the hole their network names (`via=`, decision 0039), with the detour; the report says so |
| 0.2.0 | A spread and a flow temperature per manifold, mixing circuits with their own pump, emitter shares at the circuit's temperatures (decision 0042) |

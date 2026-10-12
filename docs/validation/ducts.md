# Validation report: `ducts` (Luftleitungen)

| | |
|---|---|
| Calculator | `ducts` 0.2.0, kind `norm` |
| Method | Flows per DIN 1946-6:2019-12 (`airflow`); pressure loss by Darcy-Weisbach with Colebrook-White |
| Code | `src/uea/packs/vent/ducts.py`; the ducts from `geometry.py`, the hydraulics in `src/uea/packs/hydraulics.py` |
| Tests | `tests/test_vent.py` |
| Review | **Not yet reviewed** by a licensed person. |

`vmax` is the planner's; the flows come from `airflow` with its settings and tables; the diameters, roughness and ζ from the default duct type (`docs/decisions/0038-ventilation.md`).

## What it computes

For each section of each central unit's ducts: the flow, the diameter, the velocity, the loss per metre and the section's loss. For each terminal: the loss of its way and how much to throttle it. For each unit and side: the flow and the pressure it must deliver, against its type's external pressure. The record is `out/ducts.json`, the report `out/ducts.md`.

## Formulas as implemented

- Terminal flows from `airflow`; a section carries the flows of the terminals beyond it.
- Section lengths and bends from the derived ducts: rectilinear, lower bounds; a section that changes storey runs through the hole the unit names in `via=`, with the detour (`docs/decisions/0039-openings-without-a-fill.md`).
- Diameter: the smallest with v = V̇ / (π d² / 4) ≤ v_max; the largest if none.
- R = λ / d · ρv²/2, λ by Colebrook-White (λ = 64/Re below Re 2320), air at 20 °C: ρ = 1.204 kg/m³, ν = 15.11 · 10⁻⁶ m²/s.
- Δp = R · l + Σζ · ρv²/2, Σζ = bends · ζ_bend (+ ζ_tee where the section does not start at the unit).
- A terminal's way ends with its own loss `dp=` (the manufacturer's at its design flow).
- Supply side: the worst outdoor air way + the worst supply way + the unit's silencers `sil=`; extract side: the worst extract way + the worst exhaust way + `sil=`. Every other terminal of a kind: throttle = worst − its way.
- Fails if a duct is too fast in the largest size, or a side needs more than the type's `dp=`.

## Deviations and not implemented

- No losses of filters in the ducts or fire dampers; the terminals' and silencers' losses are the manufacturer's at the design flow, not scaled to the computed flow.
- Round ducts only; no rectangular ducts, no routes along shafts.
- Air at one temperature for all four kinds of air.

## Test cases

The box with a central unit in r1 (`tests/test_vent.py`), ducts of Ø80, 100, 125, 160 with k 0.15 mm, ζ 0.3 for a bend and 0.6 for a tee, v_max 3 m/s.

| Test | Case | Expected |
|---|---|---|
| `test_terminal_and_silencer_losses` (`tests/test_vent_more.py`) | ld1 dp=20, lg1 sil=15 | the supply side 20 + 15 Pa more, the extract side 15 more; ld1's way 20 more |
| `test_ducts` | the supply duct to ld1 | Ø125 (Ø100 would run over 3 m/s); Δp = R · l + 2 · 0.3 · ρv²/2; the supply side = the outdoor air way + the supply way, against 100 Pa; with 0.5 Pa: fails; no default duct type: stops |

## Changes

| Version | Change |
|---|---|
| 0.1.0 | First version |
| 0.1.1 | Ducts that change storey run through the hole their network names (`via=`, decision 0039), with the detour; the report says so |
| 0.2.0 | Terminal and silencer losses (decision 0043) |

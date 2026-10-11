# 0038: Ventilation, phase 7

Status: Accepted (phase 7 built; for the user's veto)
Date: 2026-10-11

## Context

Phase 7 (`ROADMAP.md`) is ventilation: units, ducts, outlets. Its "done when" is that the Einfamilienhaus demo is complete apart from structural. A German house needs a Lüftungskonzept per DIN 1946-6: whether infiltration alone keeps the dwelling dry (Feuchteschutz) or a ventilation measure is needed, and, for a system, the flows of each room. Systems in an EFH are a central unit with heat recovery and ducts (KWL), decentral units through the facade (push-pull pairs, Pendellüfter), or exhaust fans. Haus Müller's hand-written `vent.uea` has two pairs of decentral units, `feed` lines in `elec.uea` that wait for them, and request q4 for their core drillings. The plumbing and heating pipes set the pattern: elements placed, networks derived, sizing as `norm` calculators on the office's tables (`0035`, `0037`).

## Decision

**Kinds** (`uea help vent`):

| Kind | Id | Where |
|---|---|---|
| `ahu` | lg | a central unit with heat recovery in a room, `at=` (default its middle), `z=` its duct connections (1.8) |
| `fan` | vl | a decentral unit on an exterior wall like a device (`x=`/`y=`/`s=`, `z=` 2.2); `mode=alt` (push-pull, the default), `ext` (exhaust fan), `both`; `pair=` the other unit of a push-pull pair |
| `air` | ld | an air terminal of a central unit: `sup` or `ext` in a room (`at=`, under the ceiling), `oda` or `eha` on an exterior wall; `src=` its unit, else the only or nearest |

**Types** from the manufacturer (placeholders in the examples): `type … ahu flow= dp= hr=` (largest flow, external pressure at it, heat recovery), `type … fan flow= hr=`, and `type … duct sizes=80,100,125,160 k= bend= tee=` for round ducts (inner diameters; the default one serves all ducts).

**Derived** (`uea get`):
- The second half of each pair.
- The ducts of each central unit: for each kind of air, the shortest rectilinear tree from the unit over its terminals of that kind. They are lower bounds, like the pipes.
- What each room has of each kind of air: terminals and decentral units.
- `feed` lines reach the units, so their circuit's cable runs to them.

**Checks:**
- `W-VENT-001`: no type and no default.
- `W-VENT-002`: a push-pull unit without a matching pair.
- `W-VENT-003`: a decentral unit, or an outdoor or exhaust air terminal, on a wall that is not exterior.
- `W-VENT-004`: a terminal with no unit.
- `W-VENT-005`: a central unit missing outdoor, exhaust, supply or extract air.
- `E-VENT-002`: a wall without a usable face, or outdoor or exhaust air in a room.

**The flows are not a check:** they need the office's tables, and `uea check` reads the same on every machine (`0033`). Two `norm` calculators, not yet reviewed:

- **`uea calc airflow n50= insulation=high|low`** (DIN 1946-6), the Lüftungskonzept:
  - **The dwelling:** every room whose use the table `vent-room` does not mark `none`; A_NE and V_NE from the finished sizes.
  - **Totals:** q_v,ges = f · (a · A_NE² + b · A_NE + c) for FL (by the insulation), RL, NL and IL (table `vent-total`).
  - **Infiltration:** q_v,inf = komp · V_NE · n_50 · (lage · Δp / 50)^n (table `vent-infiltration`). A measure is needed if q_v,inf < q_v,ges,FL.
  - **Rooms:** the design flow is max(q_NL, Σ q_extract). Each extract room gets its flow from `vent-room`, raised in proportion to the design flow; each supply room a share by its factor f_R.
  - **Against the system:** a room with a terminal of its unit gets its flow; a decentral unit gives its room its type's flow, half each way for a push-pull unit. A room short at the nominal level fails the result, as does a unit smaller than its rooms' flows, or a dwelling that needs a measure and has no system.
- **`uea calc ducts n50= insulation= vmax=`**: the duct sizes.
  - **Flows:** from `airflow`; outdoor and exhaust air carry what their unit supplies and extracts.
  - **Size and loss:** the smallest diameter within `vmax=`, Δp = R · l + Σζ ρv²/2 with air at 20 °C.
  - **Fans:** each side's worst way (outdoor + supply, extract + exhaust) against the unit's `dp=`; every other terminal is throttled by the difference. Too fast in the largest size, or more than the unit delivers, fails the result.

**Sheets and tables:**
- The ventilation plan of each storey (`uea export pdf vent:EG`, L-01, 1:50): units, the dashed line of each pair, the terminals (ZU, AB, AU, FO), the ducts side by side (outdoor air green, supply blue, extract yellow, exhaust brown), a ring where a duct changes storey.
- The XLSX tables Lüftungsgeräte, Luftdurchlässe, Luftleitungen and Luftmengen.
- The reports `airflow` and `ducts` as A4 PDFs to sign, like every calculator's (`0036`).

## Alternatives

- **Ducts written as elements.** The same reasons as for the pipes (`0035`, `0037`): many lines for what code derives.
- **Room flows written on the terminals (`flow=`).** The agent would compute them; DIN 1946-6 derives them from the dwelling's area and the room uses, so the calculator does.
- **The Lüftungskonzept as a check.** It needs the office's tables (`0033`).
- **The standard's numbers in the code** (the coefficients of q_v,ges, the extract flows of a kitchen or bath, the infiltration factors). They are licensed; the office's tables carry them, like the Heizlast's (`0008`).
- **A push-pull unit counted with its full flow both ways.** It alternates: over time it supplies half and extracts half. The manufacturer's flow is per unit.
- **Overflow openings (Überströmöffnungen) and outdoor air inlets of exhaust systems now.** They need door undercuts and facade elements the model does not have; they come with the Todo's openings without a fill.
- **Heat recovery in the Heizlast now.** DIN EN 12831-1 has its own treatment of mechanical ventilation; it waits for the Heizlast's review.

## Consequences

- Haus Müller's `vent.uea` has its fan type (a placeholder) and loads with no errors and no ventilation warnings. The two pairs are vl1–vl2 (Schlafen, Kind 1) and vl3–vl4 (Kind 2, Wohnen/Essen). The feeds to the four units now reach them, so c18 feeds them and no circuit feeds nothing.
- With synthetic tables, `uea calc airflow` finds that infiltration covers moisture protection, but the pairs give 60 of the 164 m³/h of the nominal level, and kitchen, HWR, WC and bath have no extract. That is the designer's next step, as the WC and the bath were for the heating (`0034`): exhaust fans in the wet rooms, or a central unit.
- Done the same day: Haus Müller now has a central unit lg1 (type KWL-250, a placeholder) in the HWR with eleven terminals, and c18 feeds it. With the synthetic tables every room gets its flow (164 m³/h each way of the unit's 250), and `uea calc ducts` at 3 m/s gives Ø80 to Ø160 and 28 Pa supply, 22 Pa extract of the unit's 150. Exhaust fans alone would not have done it: the supply rooms need outdoor air inlets, which the model does not have yet.
- Tested by hand (`tests/test_vent.py`): placement, ducts and pairs; the checks; the totals, infiltration, the measure and the room flows without a system, with a pair and with a central unit; a unit too small; the duct sizes (Ø125 where Ø100 runs over 3 m/s), a duct's loss, the fan pressure against the unit; the sheets and tables; a feed to a fan; the command line; Haus Müller.
- The help names `vent` among the topics (about 3 tokens more in the bench's reading of the help; the bench could not be rerun in this environment, whose network blocks tiktoken's download). The token task set is unchanged: its tasks do not touch ventilation.
- The validation reports are `docs/validation/airflow.md` and `ducts.md`.
- Open:
  - overflow openings and outdoor air inlets; several dwellings;
  - heat recovery in the Heizlast;
  - the losses of terminals, silencers and filters;
  - ducts along shafts and installation zones; ventilation in the IFC export;
  - the standard's worked examples as a private test suite, and the review.

# 0041: Minimum electrical equipment of a room

Status: Proposed
Date: 2026-10-12

## Context

DIN 18015-2 sets how many socket outlets, lighting outlets, communication outlets and dedicated connections a room of a dwelling needs, by the room's use and, for most uses, its area, at the equipment grade the client chooses. `W-ELEC-010` was reserved for it (`0025-electrical-devices.md`), and `0028-norm-tables-and-electrical-calculators.md` decided it would be a calculator with its own table rather than a check, so `uea check` gives the same result on every machine.

## Decision

**`uea calc equip grade=<g> [scope] [combos=one|each]`**, a `norm` calculator (`packs/elec/equip.py`).

- **The table** `elec-minimum`, from the office: use (as UEA names room uses), grade, area up to (m², finished), and the number of sockets, lighting outlets, communication outlets and dedicated connections. A room takes the first row of its use and grade whose area is at least its finished area. A room larger than the last row takes the last row, and the result says so. A use with no rows is reported, not guessed.
- **What counts** is what the model mounts in the room (`mount.py`): a wall device belongs to the room in front of its face, a luminaire to the room it hangs in or faces. Sockets (`sock`), luminaires (`lum`), data outlets (`data`) and connections (`conn`).
- **Combinations.** Whether a frame with several outlets counts once or per outlet is the office's reading of the standard: `combos=one` (the default) or `each`.
- **Waivers.** A `waive _ W-ELEC-010 <room> "reason"` accepts what the room lacks: the room is `waived`, the result stays ok, and the report lists the reason and who accepted it. Haus Müller's waiver for the Diele (one socket, the client's wish) was written for this.
- **Scope:** a storey or a room; all rooms if none.

## Alternatives

- **A check in `uea check`** that runs when the table is installed: rejected in 0028, the check's result would depend on the machine.
- **Counting a luminaire's switch as the lighting outlet.** The model has the luminaire, which is the outlet the standard counts; the switch is not.
- **Numbers in the code** for the common grades: they are the standard's values and licensed (`0008`).

## Consequences

- `W-ELEC-010` is the code on the result's lines and the code a waiver names; it is not an issue of `uea check`.
- Validation report: `docs/validation/equip.md`. Not reviewed.
- Not checked: the number of circuits per dwelling and where in the room the outlets are.

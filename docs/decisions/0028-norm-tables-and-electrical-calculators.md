# 0028: Norm tables and the first electrical calculators, slice 3b

Status: Accepted (slice 3b built)
Date: 2026-10-09

## Context

`0008-office-supplied-norm-data.md` decided that the office supplies the tables of a `norm` calculator from its own licensed copy, but left the storage and the format open. Slice 3b of phase 3 (`0025-electrical-devices.md`) builds both, and the first two calculators on them: whether a cable carries its breaker (`cable`), and the voltage drop of a circuit (`vdrop`). Slice 3a (`0027-cable-routes.md`) gave them the lengths.

## Decision

**Storage.** `uea data` manages the tables; it needs no project. They live on the machine, in the folder named by `UEA_DATA`, else `$XDG_DATA_HOME/uea`, else `~/.local/share/uea`, one `tables/<id>.json` for each. They are never inside a project and never committed, so a project passed to another office carries no licensed text.

| Command | |
|---|---|
| `uea data` | every table the calculators need and which are installed, with edition |
| `uea data show <id>` | its columns, what to copy into them, and what is installed |
| `uea data add <id> <file.csv> --edition <e> [--source <s>]` | check and install; a second add replaces the first |
| `uea data remove <id>` | |

**Format.** One CSV file for each table, the first line the header. The columns are named in any order; the delimiter is a comma or a semicolon, and with a semicolon a decimal comma is read (what a German spreadsheet exports). Lines starting with `#` and blank lines are skipped. Numbers must be more than 0, text columns may list the values they allow, and no two rows may share the key of the table. Every fault is reported with the line of the file, ten at most, and nothing is installed unless the whole file is valid. The edition is required: it goes in the record of every result. The stored file keeps the SHA-256 of the CSV, so a result can be tied to the file it used.

**A calculator declares what it needs.** `Calculator.tables` lists `Spec`s (id, title, standard, columns, key) and `Calculator.params` its settings (`name=value` after the scope, typed, with a default or required). The same declarations feed `uea data show`, the error messages and `docs/reference.md`, so the schema an office or its agent must fill cannot drift from the code. The required tables are loaded before the first circuit, so a missing table stops the calculator even if no circuit would have needed it, and the message says the command to add it.

**Records.** A result carries its settings (`inputs.settings`) and for each table its id, standard, edition, source and hash (`tables`), in the JSON and in the German report.

**`cable`: the cable against its breaker.** For each circuit: In ≤ Iz, where Iz is the row of the table `ampacity` for the installation method (a setting, no default: it is the office's table and the planner's decision), the insulation (setting, PVC), the loaded conductors (2 for one phase, 3 for three) and the cross-section, times the factors of `temp-factor` (only with `temp=`) and `group-factor` (only with `group=` above 1). For a breaker B, C or D, I2 = 1.45 In follows from In ≤ Iz; for other characteristics the circuit is reported "not checked". The current of the declared load is shown, and a circuit whose declared load exceeds In fails. The result names the smallest cross-section of the table that carries In. A cross-section the table does not list is "no table data", never interpolated. Copper only.

**`vdrop`: the voltage drop.** ΔU = b · (ρ · L / S · cos φ + λ · L · sin φ) · I with b = 2 (one phase) or 1 (three), as a percentage of 230 V (IEC 60364-5-52 Annex G). ρ and λ come from the table `conductor`, so no number of the standard is in the code. L is the derived cable length to the farthest device (`0027-cable-routes.md`) times `reserve` (1.2 unless given: the derived length is a minimum). I is the declared load for a circuit without sockets, else In times `demand` (1 unless given), and the whole current is taken over the whole length. `limit` has no default: the permissible drop is the office's rule, and DIN 18015-1 sets it for the route from the meter, of which a circuit is only a part. Aluminium is a cable starting NA.

**Not built: `W-ELEC-010`.** The minimum equipment of a room as a check would make `uea check` differ from machine to machine, depending on the tables installed. It will be a calculator with its own table (a later slice), so the result names the table it used.

## Alternatives

- **Tables in the repository, or in the project folder:** the publishers' licences forbid the first, and the second puts licensed text into every copy of the project.
- **The office enters the tables as JSON, Excel or PDF:** an agent that reads a table in a PDF writes CSV without trouble, a person can open it in a spreadsheet, and the checks above catch typing mistakes.
- **Interpolating a missing temperature, group size or cross-section:** it would invent a value the standard does not give; the office adds the row.
- **ρ, λ and a default limit in the code:** they are the standard's numbers; the code keeps the formulas only.
- **The demand of socket circuits from a table:** the Gleichzeitigkeit of a norm is licensed too; `demand` is the planner's stated assumption and is recorded.
- **Two calculators in one:** each has its own clauses, tables and validation report (`docs/validation/cable.md`, `vdrop.md`).

## Consequences

- Each office, on each machine, installs its tables once. Public CI cannot run the standards' worked examples; a private run with the licensed data can.
- The tests and the demonstration use synthetic tables of our own that are not any standard's values (the CSV says so in its first line).
- Both calculators are `norm` calculators that are **not yet reviewed** by a licensed person (see the validation reports). Their lengths are a lower bound, hence the reserve.
- `Calculator.fn` takes `(d, scope)`, or `(d, scope, env)` when it declares settings or tables; the calculators in a project's `calc/` keep working unchanged.
- The help grew by 8 tokens in the bench's reading (`uea data` named in the command list); the task set is unchanged at 3,403.
- Open: the worked examples of the standards as a private test suite, short-circuit protection and the fault loop, the minimum cross-section by use, aluminium ampacity, the grouping and temperature derived from the model instead of settings, the feeder from the house connection, `W-ELEC-010`.

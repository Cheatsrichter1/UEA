# 0050: Illuminance targets and the average illuminance of a room

Status: Accepted
Date: 2026-10-20

## Context

The light pack held only the luminaires (`0025-electrical-devices.md`); lighting design and photometric calculation were left for after v1 (`0006-pack-order.md`). Agents placing luminaires had no tested way to know whether a room is lit enough, so they either guessed or computed illuminance themselves, which `CLAUDE.md` forbids. The Haus Müller prototype had already drafted the targets (`illum`) and a `custom` point-by-point calculation for one room.

## Decision

**`illum`: the target, in the model.** `illum il1 r2 em=150 h=0.75 "label"` in `light.uea`: the maintained illuminance (Wartungswert, lx) the working plane at `h=` above the FFL must reach. With `at=` and `area=` (x by y) it is a task area centred there. The target is the planner's: from DIN EN 12464-1 for a workplace, the client's wish in a dwelling, which no standard binds. It is in the model, so the agent that sets it and the agent that places luminaires read the same number.

**`uea calc light refl=<r> mf=<f> [scope]`**, a `norm` calculator (`packs/light/illuminance.py`), by the utilisation factor method (Wirkungsgradverfahren, LiTG-Publikation 3.5, CIE 40):

- Ē = MF · Σ Φ_i · UF_i / A for each target of a whole room. A and U are the room's finished floor area and perimeter; each luminaire has its own room index k_i = 2 A / (h_i U), h_i its height above the working plane, so pendants and ceiling luminaires mix.
- **The table** `light-uf`, from the office: the utilisation factor by distribution (the type's `dist=`), reflectances (`refl=`, named as the table names them, e.g. 753) and room index. It comes from the luminaire maker's data or the LiTG tables; neither is in the repository. Between two rows of k the factor is interpolated linearly, as the method does with its own tables; outside the table, or without a row for the distribution and reflectances, the room is "without data", never guessed.
- **`mf`** has no default: the maintenance factor depends on the luminaire, the room and the maintenance plan, and DIN EN 12464-1 asks the planner to state it. **`refl`** has no default: it is the planner's assumption about the finishes.
- **A low room** names how many more luminaires of its main type (the one bringing the most flux to the plane) reach the target at the same height; a room without luminaires, of the default type at the ceiling. The agent decides whether to add them, choose another type or lower the target.
- A luminaire at or below the working plane adds nothing and is named. A luminaire without `flux=` or `dist=` makes the room "without data".
- **Task areas** are listed, not checked: the method gives a room's average, a task area needs a point calculation.
- **Scope:** a storey, a room or a target; all targets if none.

## Alternatives

- **A point-by-point calculation** (as the prototype's `custom` one): it gives uniformity and task areas, but needs the luminaires' intensity distributions (LDT/IES files) and an interreflection model to be a method a Prüfingenieur would accept. It comes later, beside this one.
- **Targets as a table by room use**, like `equip`: the target in a dwelling is a design decision, not a norm value, and a task area has no use to look up.
- **Utilisation factors in the code** from an analytic model of cos^n distributions: they would be our invention, not the maker's or the LiTG's data.
- **A default maintenance factor of 0.8:** common for LED in clean rooms, but it would hide an assumption the signing person must make.

## Consequences

- The light pack is a design pack now: luminaires, targets and a calculator. The illuminance targets of Haus Müller load; the tests no longer strip them.
- Validation report: `docs/validation/light.md`. Not yet reviewed by a licensed person.
- Open: the point calculation with photometric files (task areas, uniformity U0), glare (UGR), daylight, emergency lighting, the reflectances from the finishes in the model.

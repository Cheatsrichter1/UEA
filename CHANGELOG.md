# Changelog

What each release contains. What comes next is in `FUTURE.md`; the reasons are in `docs/decisions/`.

## Unreleased

- **Partial views** (`docs/decisions/0046-partial-views.md`): `uea view <selector>` prints a slice of the model as lines to edit, after the lines it references (read-only context), with its base batch. `uea apply --view <selector> --base <n>` writes back only to that slice and is rejected when a batch after the base touched an element it changes or removes; `--base` also works alone. Selectors: `heat`, `heat:OG`, `elec:r3`, `OG`, an id with everything that references it, joined by commas.
- **Levels of hanging elements:** a manifold, a loop, a tank, a circuit or an RCD has the level of what it hangs on, so `show heat:OG` and `find ... level=OG` count them. Before, they had none.
- **Bench:** a generated apartment block (`bench/large.py`, 8 storeys of 6 flats, 1,073 elements) and the task `view` on it.
- **History check:** every command checks `log.jsonl` on read. A batch number twice or out of order, or an id a plain batch assigned twice, stops UEA with the lines and a hint; both happen when two clones' histories are merged by hand. Before, such a history passed silently and the next batch could take a used number again.
- **v1 done:** the reviews by licensed people of the `norm` calculators and the structure, the test with an office's IFC, the agent runs end to end, the benchmark and the standards' worked examples were done outside this repository; their records are private. The validation reports and decision records 0040 to 0045 say so. The norm tables in the repo stay synthetic test data, and every result still needs the signature of the Fachplaner, Tragwerksplaner or Prüfingenieur responsible.
- **Docs:** `ROADMAP.md` is gone; the order of the next versions (v2 partial views and model to tender, v3 office workflows, v4 plot evaluation and tender watching, v5 agent dashboard), the backlog and the plan for partial views are in `FUTURE.md`. Mechanical parts are left to UMEA, a separate program.
- **Split levels:** a hall beside a storeyed wing reaches up to its own roof where the slab above has a void; its height and volume follow, and the airspace over it raises no W-ARCH-022 or W-ARCH-042.
- **Fix:** the ventilation plan failed on outdoor-air inlets (`'Inlet' object has no attribute 'role'`); it now draws them as ALD with a legend entry.

## 0.1.0 (2026-10-12): first preview

The first version's packs, from the shell to the structure, for agents and developers to try. **A preview:** no calculator has been reviewed by a licensed person yet, and the norm tables in the repo are synthetic test data. Nothing UEA produces is fit for a real project until the Fachplaner, Tragwerksplaner or Prüfingenieur responsible has checked and signed it.

### What an agent can do

- **Model a building in text.** A project is a folder of `.uea` files, one line per element and one file per discipline. The `uea` CLI reads it (`show`, `get`, `find`, `check`) and changes it in atomic batches with history and revert (`apply`, `revert`, `log`). Code derives the geometry, areas, heights and volumes; the agent never computes them.
- **Architecture:** storeys, grids, build-ups, walls, openings, niches and holes, slabs, roofs (gable, half-hip, hip, shed, mansard, flat), stairs, rooms, Bestand status; shafts, pre-wall installations and installation zones shared by the services.
- **Electrical and lighting:** boards, RCDs, circuits, sockets, switches, data outlets and luminaires on wall faces; cable routes and lengths.
- **Heating:** heat generators, tanks, manifolds with mixing circuits, underfloor heating and radiators, the pipe network.
- **Plumbing:** fixtures, drinking-water, hot-water circulation and waste-water pipes.
- **Ventilation:** central and decentral units, air terminals, outdoor-air inlets, overflow openings and ducts.
- **Structure:** the load path from the architecture through beams, columns, walls and rafters to the footings.
- **Hand over between disciplines** through requests and waivers in the model, exported as BCF to the architect.
- **Import an architect's IFC** and update it from newer versions by GlobalId.

### Calculators

Fourteen `norm` calculators on tables the office supplies from its own copies of the standards (`docs/decisions/0008-office-supplied-norm-data.md`), each with hand-computed tests and a validation report in `docs/validation/`:

| Discipline | Calculators |
|---|---|
| Architecture | `wofl` Wohnfläche (WoFlV) |
| Electrical | `cable` cable against breaker, `vdrop` voltage drop, `equip` minimum equipment (DIN 18015-2) |
| Heating | `uvalue` (DIN EN ISO 6946), `heatload` Heizlast (DIN EN 12831-1) with emitter output per DIN EN 442 and DIN EN 1264, `hydronic` pipe sizing and hydraulic balance |
| Plumbing | `water` (DIN 1988-300), `drain` (DIN 1986-100), `recirc` hot-water circulation |
| Ventilation | `airflow` (DIN 1946-6), `ducts` duct sizing and fan pressure |
| Structure | `loads` (DIN EN 1991), `struct` Statische Berechnung: slabs and beams on the open-source solver PyNite, masonry walls, lintels, rafters, columns, footings and bracing against wind |

### Exports for humans, in German

- **IFC4:** the architecture and the ventilation.
- **PDF, DXF, SVG and PNG drawings:**
  - floor plans, sections and elevations;
  - electrical, heating, plumbing and ventilation plans;
  - board diagrams, Heizungsschema and Strangschema;
  - the Positionsplan.
- **XLSX tables:** rooms, quantities, circuits, pipes, ducts and more.
- **Calculation reports on A4:** ready for the responsible person to sign. A report is refused once the model has changed since its calculation.

### Reference project

Haus Müller (`docs/prototype/haus-mueller/`) is a complete Einfamilienhaus with all disciplines. Its exports are in `exports/`. The whole house costs an agent about 4,500 tokens to read (`README.md`).

### Not in this release

- Any review by a licensed engineer.
- The standards' worked examples as a test suite. Those are licensed, so they will stay private to each office.
- A test with an office's real IFC.
- A complete house built by an agent end to end. So far an agent has built only the shell and roof from a brief, in one run (`bench/agent/results.md`).
- The benchmark against conventional tools (phase 5).

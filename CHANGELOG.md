# Changelog

What each release contains. What is built and what is open in detail is in `ROADMAP.md`; the reasons are in `docs/decisions/`.

## Unreleased

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

# Changelog

What each release contains. What comes next is in `FUTURE.md`; the reasons are in `docs/decisions/`.

## Unreleased

- **The plot and the measure of use per BauNVO** (`docs/decisions/0055-plot-and-baunvo.md`), the first slice of plot evaluation: a new discipline `site` (`site.uea`) with the kind `plot`, its outline as plan points (`outline=W-3,S-5;E+4,S-5;...`) and the limits the agent read from the Bebauungsplan (`grz`, `gfz`, `gr`, `gf`, `storeys`, `grz2`, `plan`). Checks E-SITE-001 to W-SITE-003. `uea calc baunvo` (`norm`) measures GR and GRZ (§ 19, also with Abs. 4), the Vollgeschosse by the Land's rule from the office table `full-storey`, GF and GFZ (§ 20), each against the plot's limits. **Not yet reviewed** by a licensed person; its cases were run, not tested.
- **The Abstandsflächen** (`docs/decisions/0056-setbacks.md`): `uea calc setback` (`norm`) puts an Abstandsfläche in front of each façade of each storey: H from the terrain to the roof skin (along a gable, point by point; steep roofs add a share of their height), depth factor × H, at least the minimum, by the Land's rule from the office table `setback`. Checked against the plot and half of each street on it; the plot gets `use=` (the Baugebiet) and `street=`.
- **Options on a plot** (`docs/decisions/0057-options-on-a-plot.md`): `uea block x=W..E y=S..N storeys=3 [roof=...]` writes a simple building as an ordinary batch, so every calculator and export works on it. `uea compare <project>...` sets the options side by side for the client (`options.md`, `options.pdf`): GRZ, GFZ, Vollgeschosse against the plan, Abstandsflächen, BGF, NRF, BRI and costs, all from each option's results, refused when stale. `uea export pdf site` is the site plan. `baunvo` and `setback` are **not yet reviewed** by a licensed person; their cases were run, not tested.
- **Tender watching in the `AGENTS.md` template:** where the agent looks, what fits the office, how a match is recorded and summarised, and what needs approval (registering, downloading, asking the contracting authority, submitting).
- **The fee offer** (`docs/decisions/0054-offer-export.md`): `uea export offer [results]` sets the fees of the `uea calc hoai` results into a German Honorarangebot: letterhead, client, per service the zone, rate, chargeable costs and the service phases with their fees, the sum with VAT, the office's terms and a signature line. It writes `out/offer.md` and a PDF marked as a draft, and is refused when the model has changed since a fee was computed. The office's texts are the office table `offer`; the client is `client=` on the project.
- **`hoai` 0.2.1:** one result per service and group of systems (`out/hoai-building.md`, `out/hoai-services-410-420.md`), so the runs no longer replace each other; `uea export pdf hoai` names them. The basis of the chargeable costs is German in the report. The fee is unchanged.
- **`uea help calc`** lists `din277`, `costs` and `hoai`.
- **`uea data` and `docs/reference.md`** list the exports' office tables too (`lv-texts`, `offer`).
- **Office workflows are the agent's instructions, not a version** (`FUTURE.md`): an office's business side is how its agent behaves, so it belongs in the instructions the office gives it. `docs/templates/AGENTS.md` is an example to copy and adapt: nothing leaves the office without the senior engineer's approval, a request is summarised and then waits, the fee comes from `uea calc din277`, `costs` and `hoai`, the offer is a draft until it is signed. Plot evaluation and tender watching move up to v4.

## 0.3.0 (2026-10-21): the bids and the agent dashboard

Version 2 is complete with the bids, and version 3 is the agent dashboard. The calculators new in this release (`bids`, `light`) are **not yet reviewed** by a licensed person, nor are those of 0.2.0 (`din277`, `costs`, `hoai`), and the norm tables, prices and factors in the repo are synthetic test data. Nothing UEA produces is fit for a real project until the person responsible has checked and signed it.

### From the tender to the award

- **The bids** (`docs/decisions/0051-bids.md`): `uea import gaeb <file.x84>` reads a bidder's GAEB DA XML, phase 84, into a new discipline file `bid.uea`: a `bid` line per bidder and a `price` line per priced position, matched by the ids UEA wrote into the phase 83 file, else by number. Checks E-BID-001 to W-BID-005: incomplete bids, quantities the LV no longer has, a total price that is not quantity times unit price, a stated total that is not the sum. `uea calc bids` (`norm`, the arithmetic check of VOB/A § 16c Abs. 2) compares them: checked sums, discount, rank among the complete bids on the same titles, sums per title beside the office's own prices, unit prices far from the median; its report is the Preisspiegel. `uea calc costs stage=offer bid=<ids>` is the Kostenanschlag from the bids awarded. `uea export xlsx` gets the sheets Angebote and Preisspiegel. **Not yet reviewed** by a licensed person; the GAEB reader is tested on files made from UEA's own export, not on an AVA program's.

### Lighting

- **Illuminance targets and the average illuminance of a room** (`docs/decisions/0050-illuminance.md`): `illum il1 r2 em=150 h=0.75` in `light.uea` (with `at=` and `area=` a task area), and `uea calc light refl=<r> mf=<f> [scope]`, a `norm` calculator by the utilisation factor method: each luminaire's room index from its height over the working plane, the utilisation factor from the office's table `light-uf` (the maker's data or the LiTG's), how many luminaires to add in a low room. Task areas are listed, not checked. **Not yet reviewed** by a licensed person; the factors in the tests are synthetic.

### The agent dashboard

- **The agent dashboard** (`docs/decisions/0053-agent-dashboard.md`): `uea dashboard` serves a local page that shows the engineer, per project and agent, what it is doing right now ("plant die Beleuchtung im OG", "berechnet die Heizlast · OG") with an animation for its state (planning, calculating, exporting, reading, thinking, idle), its last batch and its last commands. UEA infers it from the commands: the CLI writes a line per command to an activity log on the machine, out of git (`~/.local/state/uea/activity.jsonl`, `UEA_ACTIVITY=off` stops it). Agents set `UEA_BY` once to be named on every command.

### Code

- **No test suite and no token bench** (`docs/decisions/0052-no-tests-in-the-repo.md`): `tests/` and `bench/` are removed, and CI runs ruff and pyright only. Everything passed at commit `517c07e`; the validation reports keep their cases as the record of what was verified there.
- The stale references to `bench/` and `tests/` in `FUTURE.md` and `tools/README.md` point to commit `517c07e`.

### Not in this release

- Any review of `din277`, `costs`, `hoai`, `bids` and `light` by a licensed person.
- Side offers (Nebenangebote), GAEB phases 81 and 86, a check of the GAEB files against the official schema or in an AVA program, and a first real tender.
- The Kostenfeststellung.
- The point calculation of lighting with photometric files, glare (UGR), daylight and emergency lighting.
- A dashboard across machines, and questions from agents waiting for a human.
- Incremental validation (`FUTURE.md`, Partial views).

## 0.2.0 (2026-10-16): from the model to the tender

Version 2 without the bids: big projects a slice at a time, and the way from the model to the tender and the offer. Version 1 is done; its reviews, the test with an office's IFC, the agent runs and the benchmark were done outside this repository, and their records are private. The calculators new in this release (`din277`, `costs`, `hoai`) are **not yet reviewed** by a licensed person, and the norm tables, prices and fee tables in the repo are synthetic test data. Nothing UEA produces is fit for a real project until the person responsible has checked and signed it.

### Big projects

- **Partial views** (`docs/decisions/0046-partial-views.md`): `uea view <selector>` prints a slice of the model as lines to edit, after the lines it references (read-only context), with its base batch. `uea apply --view <selector> --base <n>` writes back only to that slice and is rejected when a batch after the base touched an element it changes or removes; `--base` also works alone. Selectors: `heat`, `heat:OG`, `elec:r3`, `OG`, an id with everything that references it, joined by commas. Agents on views that do not overlap cannot conflict.
- **Faster checks:** the pipe networks' tree, the finished area of rooms, the wall overlaps and the walls a wall stands on no longer compare everything with everything. A batch on a generated block of 10,239 elements takes 6.4 s instead of 111 s, on 3,469 elements 1.6 s instead of 6.8 s. Results are unchanged.
- **History check:** every command checks `log.jsonl` on read. A batch number twice or out of order, or an id a plain batch assigned twice, stops UEA with the lines and a hint; both happen when two clones' histories are merged by hand.

### From the model to the tender

- **Areas and volumes per DIN 277** (`uea calc din277 [level]`, `0047-din277-areas.md`): BGF, NRF, KGF and BRI per storey and in total, the NRF split into NUF 1 to 7, TF and VF by the office's table `din277-uses`. Stairs count as VF, voids are no floor, the top storey's volume goes up to the top of the roof covering.
- **Leistungsverzeichnis** (`0048-leistungsverzeichnis.md`): a new discipline file `lv.uea` with titles and positions. A position counts the elements a `uea find` selector names with a measure whose meaning per kind is fixed in code (`n`, `len`, `area`, `vol`, and the networks `heat`, `water`, `drain`, `duct`), or a fixed quantity with a unit. Numbers (OZ) are derived and can be pinned; `uea get` shows a position's number, quantity, price and what it counts; a batch names the positions whose quantity it changed. Checks E-LV-001 to W-LV-005. Long texts from the office's table `lv-texts`, unit prices `ep=`, DIN 276 cost groups `kg=`.
- **GAEB:** `uea export gaeb` writes the LV for bidders as GAEB DA XML 3.3, phase 83, without prices. `uea export xlsx` gets the sheets LV and Kosten.
- **Costs per DIN 276** (`uea calc costs`, `0049-cost-estimate-and-hoai-fee.md`): the Kostenschätzung from the office's reference prices per cost group (table `cost-ref`) on the DIN 277 quantities, with the priced LV beside it; the Kostenberechnung (`stage=calculation`) from the priced LV, keeping the estimate for groups the LV does not price yet. Sums per first level, net, VAT and gross.
- **Fee per HOAI 2021** (`uea calc hoai service= zone= rate= lph= ...`): building, technical equipment (also per group of systems, `groups=`), structure. The chargeable costs come from the cost calculation where there is one, else from the estimate (§ 6 Abs. 1), for a building per § 33 Abs. 2; linear interpolation in the office's copy of the fee tables (`hoai-fees`), the phases' shares, conversion surcharge, incidental costs, VAT.

### Fixes

- A manifold, a loop, a tank, a circuit or an RCD has the level of what it hangs on, so `show heat:OG` and `find ... level=OG` count them; before, they had none.

### Bench and code

- A generated apartment block (`bench/large.py`, 8 storeys of 6 flats, 1,073 elements) with the task `view`; the task `lv` on Haus Müller. `bench/results.md` was not regenerated for this release: its tokenizer could not be downloaded where it was built.
- The selection of `uea find` is shared (`query.py`); wall and roof quantities moved to `packs/arch/quantities.py`.
- `ROADMAP.md` is gone; the order of the next versions, the backlog and the open questions are in `FUTURE.md`. Mechanical parts are left to UMEA, a separate program.

### Not in this release

- Reading the bids (GAEB 84), comparing them and the Kostenanschlag; deferred.
- GAEB phases 81 and 86, and a check of the GAEB file against the official schema or in an AVA program.
- Pipe and duct lengths per size in the LV.
- A checked copy of the HOAI's fee tables; special services; the structure's chargeable costs from the costs.
- Incremental validation (`FUTURE.md`, Partial views).
- Any review of `din277`, `costs` and `hoai` by a licensed person.

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

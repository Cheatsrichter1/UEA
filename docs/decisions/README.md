# Decision records

What was decided and why, grouped by topic. Each record is a section headed by its number; other docs link to `<file>.md#<number>-...`. When a decision changes, update its section, or add a new numbered section that says which one it supersedes, and fix the docs that depend on it.

| File | Topic |
|---|---|
| [foundations.md](foundations.md) | Foundations: what UEA is, the format, history, requests, calculators, views, the dashboard |
| [building.md](building.md) | Building: datums, rooms, roofs, walls, stairs, holes, shafts, plans, sections, elevations |
| [ifc.md](ifc.md) | IFC import and BCF requests |
| [electrical.md](electrical.md) | Electrical and lighting: devices, sheets, cable routes, norm tables, calculators |
| [services.md](services.md) | Heating, plumbing and ventilation |
| [structure.md](structure.md) | Structure: load path, loads, the Statische Berechnung |
| [tender.md](tender.md) | Areas, the Leistungsverzeichnis, costs, HOAI fee, bids, the offer |
| [site.md](site.md) | Plot evaluation: BauNVO, Abstandsflächen, options |

| # | Decision |
|---|---|
| 0001 | [No own agent](foundations.md#0001-no-own-agent) |
| 0002 | [Apache 2.0](foundations.md#0002-apache-20) |
| 0003 | [Python](foundations.md#0003-python) |
| 0004 | [One file per discipline](foundations.md#0004-one-file-per-discipline) |
| 0005 | [Line format](foundations.md#0005-line-format) |
| 0006 | [Pack order](foundations.md#0006-pack-order) |
| 0007 | [Norm and custom calculators](foundations.md#0007-norm-and-custom-calculators) |
| 0008 | [Office-supplied norm data](foundations.md#0008-office-supplied-norm-data) |
| 0009 | [History, revert and ids](foundations.md#0009-history-revert-and-ids) |
| 0010 | [Requests in the model](foundations.md#0010-requests-in-the-model) |
| 0011 | [IFC import](ifc.md#0011-ifc-import) |
| 0012 | [Datums and positions](building.md#0012-datums-and-positions) |
| 0013 | [Canonical line format](foundations.md#0013-canonical-line-format) |
| 0014 | [Operations and history](foundations.md#0014-operations-and-history) |
| 0015 | [Rooms and finishes](building.md#0015-rooms-and-finishes) |
| 0016 | [Roofs](building.md#0016-roofs) |
| 0017 | [English format](foundations.md#0017-english-format) |
| 0018 | [Raw walls](building.md#0018-raw-walls) |
| 0019 | [Stair shapes](building.md#0019-stair-shapes) |
| 0020 | [Roof parts](building.md#0020-roof-parts) |
| 0021 | [Roof shapes](building.md#0021-roof-shapes) |
| 0022 | [Plans and tables](building.md#0022-plans-and-tables) |
| 0023 | [Sections](building.md#0023-sections) |
| 0024 | [Elevations](building.md#0024-elevations) |
| 0025 | [Electrical devices](electrical.md#0025-electrical-devices) |
| 0026 | [Electrical sheets](electrical.md#0026-electrical-sheets) |
| 0027 | [Cable routes](electrical.md#0027-cable-routes) |
| 0028 | [Norm tables and electrical calculators](electrical.md#0028-norm-tables-and-electrical-calculators) |
| 0029 | [IFC import of walls, openings and rooms](ifc.md#0029-ifc-import-of-walls-openings-and-rooms) |
| 0030 | [IFC import of grids, voids, stairs and roofs](ifc.md#0030-ifc-import-of-grids-voids-stairs-and-roofs) |
| 0031 | [IFC import of real files](ifc.md#0031-ifc-import-of-real-files) |
| 0032 | [BCF requests](ifc.md#0032-bcf-requests) |
| 0033 | [U-values and Heizlast](services.md#0033-u-values-and-heizlast) |
| 0034 | [Heating elements](services.md#0034-heating-elements) |
| 0035 | [Plumbing](services.md#0035-plumbing) |
| 0036 | [Heating and plumbing sheets](services.md#0036-heating-and-plumbing-sheets) |
| 0037 | [Heating pipes and Strangschema](services.md#0037-heating-pipes-and-strangschema) |
| 0038 | [Ventilation](services.md#0038-ventilation) |
| 0039 | [Holes](building.md#0039-holes) |
| 0040 | [Structure](structure.md#0040-structure) |
| 0041 | [Minimum equipment](electrical.md#0041-minimum-equipment) |
| 0042 | [Emitters, mixing and circulation](services.md#0042-emitters-mixing-and-circulation) |
| 0043 | [Ventilation details](services.md#0043-ventilation-details) |
| 0044 | [Structure completion](structure.md#0044-structure-completion) |
| 0045 | [Shafts, prewalls, zones](building.md#0045-shafts-prewalls-zones) |
| 0046 | [Partial views](foundations.md#0046-partial-views) |
| 0047 | [DIN 277 areas](tender.md#0047-din-277-areas) |
| 0048 | [Leistungsverzeichnis](tender.md#0048-leistungsverzeichnis) |
| 0049 | [Costs and HOAI fee](tender.md#0049-costs-and-hoai-fee) |
| 0050 | [Illuminance](electrical.md#0050-illuminance) |
| 0051 | [Bids](tender.md#0051-bids) |
| 0052 | [No tests in the repo](foundations.md#0052-no-tests-in-the-repo) |
| 0053 | [Agent dashboard](foundations.md#0053-agent-dashboard) |
| 0054 | [Offer export](tender.md#0054-offer-export) |
| 0055 | [Plot and BauNVO](site.md#0055-plot-and-baunvo) |
| 0056 | [Setbacks](site.md#0056-setbacks) |
| 0057 | [Options on a plot](site.md#0057-options-on-a-plot) |

A new record: the next free number, a section `## NNNN Title` in the file of its topic, the decision as short bullets, then one paragraph `Why:` with the alternatives that lost.

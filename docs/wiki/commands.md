# Commands by task

[Wiki home](README.md)

What `uea` does, in the order a project needs it. Every command with all its options is in [`docs/reference.md`](../reference.md#commands), and `uea help <topic>` gives the same in the terminal. `-C <dir>` runs any command in another folder; `--json` gives machine-readable output. Set `UEA_BY=<who>` once, and every command is named after you.

## Start

| Command | Does |
|---|---|
| `uea init <dir>` | A new, empty project folder |
| `uea import ifc <file> --by <who>` | The architecture from an architect's IFC, re-importable ([0029](../decisions/0029-ifc-import.md)) |

## Read

| Command | Does | Example |
|---|---|---|
| `uea show [scope]` | A summary: the project, a storey, a discipline, an id | `uea show elec:OG` |
| `uea get <id>...` | Elements with their derived values | `uea get r1` |
| `uea find <kind> [filters]` | Elements by kind and fields | `uea find door room=r3` |
| `uea view <selector>` | A slice as lines to edit, with its context and base | `uea view heat:OG` |
| `uea check [discipline]` | Open issues, requests and waivers | `uea check elec` |
| `uea log [n]` | The last batches: who, why, what | `uea log 5` |
| `uea render <level>` | A plan image to look at | `uea render EG` |

## Change

| Command | Does |
|---|---|
| `uea apply --by <who> -m <why>` | A batch of operations from stdin ([the line format](format.md#operations)); `--view <sel> --base <n>` writes only a slice |
| `uea block x=W..E y=S..N storeys=3` | A simple building as an ordinary batch, for options on a plot ([0057](../decisions/0057-options-on-a-plot.md)) |
| `uea revert <batch> --by <who>` | Undo a batch, as a new batch |
| `uea import gaeb <file.x84> --by <who>` | A bidder's prices into `bid.uea` ([0051](../decisions/0051-bids.md)) |

## Calculate

`uea calc` lists the calculators; `uea calc <name> [scope] [name=value...]` runs one. Each writes `out/<name>.md` (the report for people) and `out/<name>.json` (the record: calculator, version, settings, model state, tables used). `uea data` lists the office's tables, `uea data add <id> <file.csv> --edition <e>` installs one ([0008](../decisions/0008-office-supplied-norm-data.md)).

| Question | Calculator |
|---|---|
| How big is it? | `wofl` (Wohnfläche), `din277` (BGF, NRF, BRI) |
| What may be built on the plot? | `baunvo` (GRZ, GFZ, Vollgeschosse), `setback` (Abstandsflächen) |
| What does it cost, what is the fee? | `costs` (DIN 276: estimate, calculation, Kostenanschlag), `hoai`, `bids` (Preisspiegel) |
| Electrical | `cable`, `vdrop`, `equip` |
| Lighting | `light` |
| Heating | `uvalue`, `heatload`, `hydronic` |
| Plumbing | `water`, `drain`, `recirc` |
| Ventilation | `airflow`, `ducts` |
| Structure | `loads`, `struct` |

How far each one can be trusted is in its validation report in [`docs/validation/`](../validation/).

## Hand over to people

| Command | Gives |
|---|---|
| `uea export pdf [sheet]` | Plans to print: floor plans, sections, elevations, the services' sheets, the Positionsplan, the site plan (`site`) |
| `uea export pdf <result>` | A calculation report to sign, refused if the model changed since: `uea export pdf heatload` |
| `uea export dxf\|svg\|png [sheet]` | The same sheets for CAD or to look at |
| `uea export xlsx [level]` | Tables: rooms, walls, quantities, the services, the LV, the bids |
| `uea export ifc` | The model as IFC4 |
| `uea export gaeb` | The LV for bidders (GAEB 83) |
| `uea export bcf [discipline]` | Requests for someone working outside UEA |
| `uea export offer [results]` | The fee offer (Honorarangebot) from the `hoai` results |
| `uea compare <project>...` | Options side by side, from each one's results |
| `uea dashboard` | A local page for the engineer: what each agent is doing ([0053](../decisions/0053-agent-dashboard.md)) |

Everything goes to `out/` unless `-o` says otherwise. Every export is a draft until a person has checked and signed it.

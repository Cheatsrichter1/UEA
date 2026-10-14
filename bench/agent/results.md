# Agent test: results

Two runs. The shell run: an off-the-shelf agent builds the Haus Müller shell, roof included, from the written brief in `haus-mueller.md`, the phase 1 "done when". The services run: it plans electrical, heating, plumbing and ventilation into the finished shell from `haus-mueller-services.md`, the end-to-end run phase 7's "done when" needs (see below). How they run is in the docstring of `__init__.py`:

```bash
uv run python -m bench.agent setup RUN [--services]   # prints the prompt to give the agent
uv run python -m bench.agent compare RUN              # after the agent is done
```

The comparison checks 58 facts against the reference (`docs/prototype/haus-mueller/`): 3 storeys, 17 walls, 22 doors and windows with handing and the room they open into, the stair, 3 slabs, the roof's eaves and ridge, and 11 room names and finished areas. On the reference solution it gives 58/58 (`tests/test_bench_agent.py`).

## Run 1: 2026-10-07

Three Claude models as Claude Code subagents, in parallel, each with its own empty folder. UEA at commit 389e656, before the English format (`docs/decisions/0017-english-format.md`); the brief is unchanged, so the run can be repeated.

| Agent | Facts | `uea check` | Wohnfläche (ref. 134.89) | `uea` calls | Nonzero exits | Tokens | Time |
|---|---|---|---|---|---|---|---|
| Claude Opus 5.5 | **58/58** | clean | 134.89 | 69 (12 batches) | 4 | 107k | 4.6 min |
| Claude Sonnet 5.5 | **55/58** | clean | 134.89 | 75 (14 batches) | 7 | 113k | 5.6 min |
| Claude Haiku 4.5 | 31/58 | 1 warning | 130.42 | 81 (49 batches) | 32 | – | stopped |

- **Opus** built exactly the reference. All four rejections were dry runs while it found the syntax of the project line and of `layers=`.
- **Sonnet** added eaves walls on the attic storey, stacked on the OG walls and cut by the roof. That changes the gable walls' span and makes the attic 75.21 m² instead of 82.61 m². The brief does not rule it out, and it is arguably the more physical model; how to model the attic over the eaves walls is open.
- **Haiku** was stopped at the export step. Its doors had no `into=` or handing, its rooms no names; two OG walls were missing, the stair sat 0.365 m off, and the OG 24 cm wall was not load-bearing.
- All three IFC exports pass IfcOpenShell's schema validation, and every shape builds. None of the agents read the repository.

## What the run changed

Fixed in the help after this run (and checked by `tests/test_cli.py`):

- The `layers=` syntax had no example anywhere. All three agents guessed (pipes, spaces) first; Haiku needed nine tries.
- `uea help project` showed the pack, not the project line's fields, so `ground=` and the project's name were found by trial.
- `uea help export` did not exist, and the help never said where the eaves height is measured.
- Positions measured from the outside corner (`x=W+1.51`) and the minus side (`x=w6-0.135`) had no example.
- `uea get` called the default window and door types unused.

Open: the Hebeschiebetür is drawn as a plain gap (doors need an operation type, like IFC's `OperationType`), and a window label can cover a wall label in the plan image.

## The services run (prepared 2026-10-11, not yet run)

The end-to-end run of phase 7: the agent gets the Haus Müller shell (the reference `project.uea` and `arch.uea` without their niches and holes, so it has to ask for them), the brief `haus-mueller-services.md` and the CLI. The brief reads like a Fachplaner's: the board and its circuits with what each serves, per room the number of outlets, lights, switches, data ports and smoke alarms, the heat pump, indoor unit, manifolds and towel radiator, the fixtures, meter, riser, stack and sewer connection, the central ventilation unit and its terminals, the product data, and the settings of four calculators. Where each device goes is left to the agent, as it would be to the Fachplaner; the checks (switches on the lock side, devices clear of openings, a hole for each pipe through a slab) hold it to the rules.

`setup --services` installs synthetic norm tables of our own for the run (`tables/`; they are not a standard's values) so that `heatload`, `hydronic`, `airflow` and `ducts` work. The agent works as each Fachplaner in turn and as the architect only to answer its own requests.

`compare` checks 116 facts against the reference (`docs/prototype/haus-mueller/`), all of them independent of ids and exact positions:

| Group | Facts | What is compared |
|---|---|---|
| Electrical | 70 | boards and their room, RCD types, each circuit's breaker, phases, RCD type and the rooms it serves; per room the outlets, connections, switches, luminaires, data ports and smoke alarms; what each feed powers |
| Heating | 15 | generator, tank, manifolds (in a niche, in which room), underfloor heating per room, radiators |
| Plumbing | 11 | meter, riser, stack, sewer connection, each fixture in its room |
| Ventilation | 12 | the central unit, each terminal by room and kind of air |
| Niches and holes | 8 | the two niches for the manifolds, and each hole by what passes it |

It also runs the four calculators with the brief's settings, on the agent's model and on the reference, and lists the open requests. On the reference solution it gives 116/116, every calculation met, and one open request (the housings for the downlights, which the model has no kind for); on the empty shell 0/116 (`tests/test_bench_agent.py`).

The run itself needs an agent with a shell and the network to install UEA; the run of 2026-10-07 used Claude Code subagents. It is left to the user, like the bench's token counts, which this environment could not download the tokenizer for.

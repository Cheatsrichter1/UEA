# Agent test: results

An off-the-shelf agent builds the Haus Müller shell, roof included, from the written brief in `haus-mueller.md`: the phase 1 "done when" in `ROADMAP.md`. How it runs is in the docstring of `__init__.py`:

```bash
uv run python -m bench.agent setup RUN     # prints the prompt to give the agent
uv run python -m bench.agent compare RUN   # after the agent is done
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

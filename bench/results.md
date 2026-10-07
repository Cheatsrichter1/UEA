# Token task set: results

Reference solutions run through the real CLI (`uv run python -m bench --write`). Tokens counted with tiktoken o200k_base: commands and operations typed (in), UEA's output read (out). Agent runs, which add the error rate, are not wired up yet.

| Task | Steps | Tokens in | Tokens out | Total | Check |
|---|---:|---:|---:|---:|---|
| eg-shell | 4 | 1,204 | 285 | 1,489 | ok |
| og-roof | 4 | 652 | 233 | 885 | ok |
| move-wall | 3 | 43 | 230 | 273 | ok |
| request | 3 | 73 | 191 | 264 | ok |
| revert | 3 | 63 | 87 | 150 | ok |
| wohnflaeche | 1 | 6 | 208 | 214 | ok |
| query | 3 | 25 | 111 | 136 | ok |
| **all** | | | | **3,411** | |

Reading the help once (`help`, `help start`, `help ops`, `help positions`, `help arch`): 1,898 tokens.

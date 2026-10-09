# Token task set: results

Reference solutions run through the real CLI (`uv run python -m bench --write`). Tokens counted with tiktoken o200k_base: commands and operations typed (in), UEA's output read (out). Agent runs, which add the error rate, are not wired up yet.

| Task | Steps | Tokens in | Tokens out | Total | Check |
|---|---:|---:|---:|---:|---|
| eg-shell | 4 | 1,203 | 283 | 1,486 | ok |
| og-roof | 4 | 652 | 232 | 884 | ok |
| move-wall | 3 | 43 | 228 | 271 | ok |
| request | 3 | 73 | 191 | 264 | ok |
| revert | 3 | 63 | 87 | 150 | ok |
| wohnflaeche | 1 | 6 | 208 | 214 | ok |
| query | 3 | 25 | 109 | 134 | ok |
| **all** | | | | **3,403** | |

Reading the help once (`help`, `help start`, `help ops`, `help positions`, `help arch`): 2,509 tokens.

# 0053: The agent dashboard: what each agent is doing, from the commands it runs

Status: Accepted (built)
Date: 2026-10-21

## Context

Version 3 (`FUTURE.md`) is a small dashboard for the engineer: per agent, one line of what it is working on ("plant die Beleuchtung im OG") and an animation for its state (planning, calculating, exporting, reading, thinking). It is information, not a representation: it does not show the model and is not a viewer.

UEA knows nothing about what an agent is doing between two commands, and `0001-no-own-agent.md` rules out status features in UEA. But every command an agent runs passes through the CLI, and a batch already names its author (`--by`), its reason (`-m`), the packs it writes and, through the elements it touches, the storeys.

## Decision

- **UEA infers the activity from the commands. Agents report nothing.** The CLI writes two lines per command to an activity log, one when it starts and one when it ends. They hold the time, who runs it (`--by`, else `UEA_BY`), the command and its scope, whether it succeeded, and for a batch its number, its message, its packs and its storeys. Help, init, version, data and the dashboard itself are not recorded, and nor is a command outside a project.
- **The log is per machine, outside every project and out of git:** `~/.local/state/uea/activity.jsonl` (`$XDG_STATE_HOME`, `%LOCALAPPDATA%` on Windows). One dashboard shows every project on the machine, no project's `.gitignore` changes, and concurrent agents cannot conflict over it the way they do over `log.jsonl`. `UEA_ACTIVITY=<file>` moves it, and `UEA_ACTIVITY=off` stops it. Past 1 MB it keeps its last 2,000 lines. A failed write is ignored: the history is `log.jsonl`, and this log is a view of the moment.
- **States** follow from an agent's last command:

| State | When |
|---|---|
| plant (planning) | `apply`, `revert`, `import` running or ended less than 8 s ago |
| rechnet (calculating) | `calc`, likewise |
| exportiert (exporting) | `export`, `render`, likewise |
| liest (reading) | `show`, `get`, `find`, `view`, `check`, `log`, likewise |
| denkt nach (thinking) | its last command ended 8 s to 5 min ago |
| ruht (idle) | quiet for 5 min or more; hidden after 12 h |

  A command that started 15 min ago and never ended (killed) counts as ended.
- **The words come from the model's own names:** a batch writing `light.uea` on the OG reads "plant die Beleuchtung im OG", `uea calc heatload OG` reads "berechnet die Heizlast · OG". Each card shows the agent, its state with an animation, that line, the agent's last batch with its message, and its last six commands. A rejected batch or a failed command is marked.
- **`uea dashboard [--port 8770]`** serves the page on `127.0.0.1` with Python's standard library: the page (`dashboard.html`), which polls `/state` every 2 s, and `/state`, the JSON it draws. It only reads the log and each project's `project.uea` for its name, and never writes anything. The page is German, because people read it.
- **Agents set `UEA_BY` once.** The root help says so in one line, since only `apply`, `revert` and `import` take `--by`. Commands without a name group under "ohne Namen".

## Alternatives

- **`uea status "<text>"`, called by the agent.** It would show what the agent says it is doing, thinking included. But it is the status feature `0001` rules out, it costs every agent tokens and calls on every step, and an agent that forgets it shows nothing. Not built; it stays open in case the inference falls short.
- **The log in the project, in git.** Agents on other machines would show up after a pull, but every command would change a tracked file, so concurrent agents conflict on it like `log.jsonl`, and the history fills with reads. Rejected.
- **The log in the project, git-ignored.** Agents on the same machine, but one dashboard per project, and UEA would have to edit the `.gitignore` of projects created before. Rejected.
- **Deriving everything from `log.jsonl`.** It holds the batches only: no calculations, exports or reads, and nothing while a command runs. Too little for the states.
- **A desktop program or a dependency such as a web framework.** The standard library's HTTP server and one HTML file are enough for a page that polls JSON.

## Consequences

- `0001`'s rule "no chat, status or question features" holds: the log is written by the CLI as a side effect of commands, and no agent calls anything for it. Questions waiting for a human would still need events UEA does not have.
- Every recorded command writes two small lines to a file in the user's home directory. Each start line names the project folder.
- The dashboard is the second thing in UEA made for people to use directly, after the exports. Agents never use it, and it changes nothing in the model.
- Thinking is a guess: the gap since the last command, which UEA cannot tell apart from an agent that is done or waiting for its human.
- Agents on other machines do not show up. A dashboard across machines would need the log shipped somewhere, which is open (`FUTURE.md`, Agent dashboard).
- New: `src/uea/activity.py` (the log), `src/uea/dashboard.py` and `dashboard.html` (the page), the command `uea dashboard`.

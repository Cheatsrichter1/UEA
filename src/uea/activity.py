"""What the agents do through UEA, for the dashboard (decision 0053).

The CLI appends two lines per command to a log on this machine, outside every project and out of
git: one when it starts and one when it ends. They say who runs it (--by or UEA_BY), the command,
its scope and, for a batch, the packs and storeys it wrote and its message. An agent calls nothing
for it. A failed write is ignored: the log is a view of the moment, the history is `log.jsonl`.
"""

import json
import os
import sys
import time
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any

from uea.project import NotAProject, Project

COMMANDS = frozenset(
    [
        "show",
        "get",
        "find",
        "view",
        "check",
        "log",
        "apply",
        "block",
        "revert",
        "calc",
        "export",
        "render",
        "import",
    ]
)
"""The commands the log records; help, init, version, data and dashboard are left out."""
MAX_BYTES = 1_000_000
KEEP = 2000
"""Past MAX_BYTES, the log keeps its last KEEP lines."""


def log_path() -> Path | None:
    """UEA_ACTIVITY names the file, or turns the log off with `off`."""
    env = os.environ.get("UEA_ACTIVITY")
    if env == "off":
        return None
    if env:
        return Path(env)
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "uea" / "activity.jsonl"


def _write(ev: dict[str, Any]) -> None:
    path = log_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")
        if path.stat().st_size > MAX_BYTES:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(lines[-KEEP:]), encoding="utf-8")
            tmp.replace(path)
    except OSError:
        pass


def _arg(args: Namespace) -> str | None:
    """The command's scope, as the dashboard names it."""
    cmd: str = args.cmd
    parts: list[str] = []
    if cmd in ("show", "check"):
        parts = [getattr(args, "scope", None) or getattr(args, "discipline", None) or ""]
    elif cmd == "get":
        parts = list(args.ids[:4]) + (["..."] if len(args.ids) > 4 else [])
    elif cmd == "find":
        parts = [args.kind, *args.filters]
    elif cmd == "view":
        parts = [args.selector]
    elif cmd == "block":
        parts = list(args.rest[:3])
    elif cmd == "apply":
        parts = [args.view or ""]
    elif cmd == "revert":
        parts = [str(args.batch)]
    elif cmd == "calc":
        parts = [args.name or "", *(r for r in args.rest if "=" not in r)]
    elif cmd == "export":
        parts = [args.format, args.scope or ""]
    elif cmd == "render":
        parts = [args.scope, args.view or ""]
    elif cmd == "import":
        parts = [args.format, Path(args.file).name]
    text = " ".join(p for p in parts if p)
    return text or None


class Run:
    """One command in the log: started now, ended by `end`."""

    def __init__(self, args: Namespace, root: Path) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.t0 = time.time()
        self.info: dict[str, Any] = {}
        """What the command adds for its end line: packs, levels, batch, msg."""
        by = getattr(args, "by", None) or os.environ.get("UEA_BY") or None
        _write(
            {
                "ev": "start",
                "id": self.id,
                "t": round(self.t0, 1),
                "by": by,
                "cmd": args.cmd,
                "arg": _arg(args),
                "root": str(root),
            }
        )

    def end(self, code: int) -> None:
        t = time.time()
        _write(
            {
                "ev": "end",
                "id": self.id,
                "t": round(t, 1),
                "ok": code == 0,
                **{k: v for k, v in self.info.items() if v is not None},
            }
        )


def start(args: Namespace, start_dir: Path) -> Run | None:
    """A run for a command the log records, inside a project; None otherwise."""
    if args.cmd not in COMMANDS or log_path() is None:
        return None
    try:
        root = Project.find(start_dir).root
    except NotAProject:
        return None
    return Run(args, root)

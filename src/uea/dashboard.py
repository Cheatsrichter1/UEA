"""`uea dashboard`: a local page that shows the engineer what each agent is doing (decision 0053).

It reads the activity log (`activity.py`) and nothing else, and never writes. Each agent's state
follows from its last command: while one runs, and for a few seconds after, what the command does
(planning, calculating, exporting, reading); then thinking until it goes quiet, then idle. UEA
cannot tell an agent thinking from one that is done; the gap since its last command is all it
sees. The page is for people, so it is German.
"""

import json
import re
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from uea.activity import log_path

HOLD = 8.0
"""Seconds a finished command still shows as what it did."""
IDLE = 300.0
"""Seconds without a command after which an agent is idle, no longer thinking."""
HIDE = 12 * 3600.0
"""Agents quiet longer than this are left out."""
STALE = 900.0
"""A command that started this long ago and never ended (killed) counts as ended."""
RECENT = 6

STATE_OF = {
    "apply": "plan",
    "revert": "plan",
    "import": "plan",
    "calc": "calc",
    "export": "export",
    "render": "export",
}
"""Every other command reads."""
LABEL = {
    "plan": "plant",
    "calc": "rechnet",
    "export": "exportiert",
    "read": "liest",
    "think": "denkt nach",
    "idle": "ruht",
}
PACK_DE = {
    "project": "das Projekt",
    "arch": "die Architektur",
    "struct": "das Tragwerk",
    "light": "die Beleuchtung",
    "elec": "die Elektroinstallation",
    "heat": "die Heizung",
    "plumb": "die Sanitärinstallation",
    "vent": "die Lüftung",
    "lv": "das Leistungsverzeichnis",
    "bid": "die Angebote",
    "issues": "die Anfragen",
}
CALC_DE = {
    "wofl": "die Wohnfläche",
    "din277": "die Flächen nach DIN 277",
    "costs": "die Kosten",
    "bids": "den Preisspiegel",
    "hoai": "das Honorar",
    "cable": "die Leitungsquerschnitte",
    "vdrop": "den Spannungsfall",
    "equip": "die Mindestausstattung",
    "light": "die Beleuchtungsstärke",
    "uvalue": "die U-Werte",
    "heatload": "die Heizlast",
    "hydronic": "den hydraulischen Abgleich",
    "water": "die Trinkwasserleitungen",
    "drain": "die Schmutzwasserleitungen",
    "recirc": "die Zirkulation",
    "airflow": "die Luftvolumenströme",
    "ducts": "die Luftleitungen",
    "loads": "die Lasten",
    "struct": "die Statik",
}
EXPORT_DE = {
    "pdf": "Pläne als PDF",
    "dxf": "Pläne als DXF",
    "svg": "eine Planvorschau",
    "png": "eine Planvorschau",
    "xlsx": "die Tabellen",
    "ifc": "das IFC-Modell",
    "bcf": "die Anfragen als BCF",
    "gaeb": "das LV als GAEB",
}
PROJECT_RE = re.compile(r'^project\s+\S+\s+"([^"]*)"', re.M)


@dataclass
class Cmd:
    id: str
    t: float
    by: str
    cmd: str
    arg: str | None
    root: str
    end: float | None = None
    ok: bool = True
    info: dict[str, Any] = field(default_factory=dict[str, Any])


def read(path: Path) -> list[Cmd]:
    """The commands in the log, oldest first, each with its end if it has one."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    cmds: dict[str, Cmd] = {}
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        e: dict[str, Any] = ev  # pyright: ignore[reportUnknownVariableType]
        if e.get("ev") == "start":
            cmds[str(e["id"])] = Cmd(
                str(e["id"]),
                float(e["t"]),
                str(e.get("by") or "ohne Namen"),
                str(e["cmd"]),
                e.get("arg"),
                str(e["root"]),
            )
        elif e.get("ev") == "end" and (c := cmds.get(str(e.get("id")))) is not None:
            c.end = float(e["t"])
            c.ok = bool(e.get("ok", True))
            c.info = {k: v for k, v in e.items() if k not in ("ev", "id", "t", "ok")}
    return list(cmds.values())


def _strs(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    items: list[Any] = v  # pyright: ignore[reportUnknownVariableType]
    return [str(x) for x in items]


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " und " + items[-1]


def _levels(levels: list[str]) -> str:
    if not levels:
        return ""
    if len(levels) > 3:
        return f" auf {len(levels)} Geschossen"
    return f" im {_and(levels)}"


def describe(c: Cmd) -> str:
    """What the command does, in a few German words."""
    arg = c.arg or ""
    head = arg.split()[0] if arg else ""
    rest = " ".join(arg.split()[1:])
    at = f" · {rest}" if rest else ""
    if c.cmd == "apply":
        packs = [PACK_DE.get(p, p) for p in _strs(c.info.get("packs")) if p != "issues"]
        if not packs:
            return "versucht eine Änderung"
        text = f"plant {_and(packs)}{_levels(_strs(c.info.get('levels')))}"
        if c.info.get("dry"):
            text += " (Probelauf)"
        return text
    if c.cmd == "revert":
        return f"nimmt Batch {arg} zurück"
    if c.cmd == "import":
        return f"importiert {rest or head}"
    if c.cmd == "calc":
        if not head:
            return "sieht die Rechenverfahren durch"
        return f"berechnet {CALC_DE.get(head, head)}{at}"
    if c.cmd == "export" and head == "pdf" and rest in CALC_DE:
        return f"exportiert den Rechenbericht über {CALC_DE[rest]}"
    if c.cmd == "export":
        return f"exportiert {EXPORT_DE.get(head, head)}{at}"
    if c.cmd == "render":
        return f"zeichnet einen Plan · {arg}"
    if c.cmd == "show":
        return f"sieht sich {arg} an" if arg else "sieht sich das Projekt an"
    if c.cmd == "get":
        return f"liest {arg}"
    if c.cmd == "find":
        return f"sucht {arg}"
    if c.cmd == "view":
        return f"liest den Ausschnitt {arg}"
    if c.cmd == "check":
        return f"prüft {PACK_DE.get(arg, arg)}" if arg else "prüft das Modell"
    if c.cmd == "log":
        return "liest den Verlauf"
    return c.cmd


def _state(c: Cmd, now: float) -> str:
    end = c.end if c.end is not None else (c.t + STALE if now - c.t > STALE else None)
    if end is None or now - end < HOLD:
        return STATE_OF.get(c.cmd, "read")
    return "think" if now - end < IDLE else "idle"


def _project_name(root: str, cache: dict[str, str]) -> str:
    if root not in cache:
        name = Path(root).name
        try:
            m = PROJECT_RE.search((Path(root) / "project.uea").read_text(encoding="utf-8"))
            if m and m.group(1):
                name = m.group(1)
        except OSError:
            pass
        cache[root] = name
    return cache[root]


def _ago(s: float) -> str:
    if s < 60:
        return "gerade eben"
    if s < 3600:
        return f"vor {int(s // 60)} min"
    return f"vor {int(s // 3600)} h"


def state(cmds: list[Cmd], now: float, names: dict[str, str] | None = None) -> dict[str, Any]:
    """The projects and their agents, as the page shows them."""
    names = {} if names is None else names
    by_agent: dict[tuple[str, str], list[Cmd]] = {}
    for c in cmds:
        by_agent.setdefault((c.root, c.by), []).append(c)
    projects: dict[str, list[dict[str, Any]]] = {}
    for (root, by), cs in by_agent.items():
        last = cs[-1]
        quiet = now - (last.end or last.t)
        if quiet > HIDE:
            continue
        st = _state(last, now)
        batches = [c for c in cs if c.cmd in ("apply", "revert", "import") and c.info.get("batch")]
        batch = None
        if batches:
            b = batches[-1]
            batch = {"n": b.info["batch"], "msg": b.info.get("msg"), "ago": _ago(now - b.t)}
        recent = [
            {"time": time.strftime("%H:%M", time.localtime(c.t)), "text": describe(c), "ok": c.ok}
            for c in reversed(cs[-RECENT:])
        ]
        projects.setdefault(root, []).append(
            {
                "by": by,
                "state": st,
                "label": LABEL[st],
                "text": describe(last)
                if st not in ("think", "idle")
                else f"zuletzt: {describe(last)}",
                "ok": last.ok,
                "ago": _ago(quiet) if st in ("think", "idle") else None,
                "batch": batch,
                "recent": recent,
                "t": last.t,
            }
        )
    out: list[dict[str, Any]] = []
    for root, agents in projects.items():
        agents.sort(key=lambda a: -a["t"])
        out.append({"name": _project_name(root, names), "root": root, "agents": agents})
    out.sort(key=lambda p: -max(a["t"] for a in p["agents"]))
    return {"projects": out}


PAGE = Path(__file__).with_name("dashboard.html")
"""The page: it polls /state and draws a card per agent."""


def serve(port: int) -> int:
    path = log_path()
    names: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?")[0] == "/state":
                cmds = read(path) if path is not None else []
                body = json.dumps(state(cmds, time.time(), names), ensure_ascii=False).encode()
                kind = "application/json; charset=utf-8"
            elif self.path.split("?")[0] in ("/", "/index.html"):
                body, kind = PAGE.read_bytes(), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"uea: cannot serve on port {port} ({e.strerror}); try uea dashboard --port <n>")
        return 2
    where = path if path is not None else "off (UEA_ACTIVITY=off)"
    print(f"dashboard: http://127.0.0.1:{port} · log: {where} · Ctrl+C stops", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

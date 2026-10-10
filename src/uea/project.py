"""A project folder: the canonical `.uea` files and the history in `log.jsonl`.

See ARCHITECTURE.md §2 and docs/decisions/0009-history-revert-ids.md.
"""

import hashlib
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from uea.core.model import Model, element_from_raw
from uea.core.registry import DISCIPLINES, Registry
from uea.core.schema import ID_RE
from uea.core.syntax import LineError, parse_line
from uea.packs import default_registry

LOG = "log.jsonl"
GITIGNORE = "out/\n.uea.lock\n"


class LoadError(Exception):
    """The project files cannot be read. Each error names file and line."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class NotAProject(Exception):
    pass


@dataclass
class Entry:
    batch: int
    time: str
    by: str
    msg: str
    ops: list[str]
    inverse: list[str]
    ids: list[str] = field(default_factory=list[str])
    files: dict[str, str] = field(default_factory=dict[str, str])
    revert: int | None = None
    external: bool = False
    ifc: dict[str, Any] | None = None
    """For an import: the file, and which IFC element became which UEA element (0029)."""

    def to_json(self) -> str:
        d = asdict(self)
        if d["revert"] is None:
            del d["revert"]
        if not d["external"]:
            del d["external"]
        if d["ifc"] is None:
            del d["ifc"]
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "Entry":
        d = json.loads(s)
        return cls(
            batch=int(d["batch"]),
            time=str(d["time"]),
            by=str(d["by"]),
            msg=str(d["msg"]),
            ops=[str(x) for x in d["ops"]],
            inverse=[str(x) for x in d["inverse"]],
            ids=[str(x) for x in d.get("ids", [])],
            files={str(k): str(v) for k, v in d.get("files", {}).items()},
            revert=d.get("revert"),
            external=bool(d.get("external", False)),
            ifc=d.get("ifc"),
        )

    def touched(self) -> set[str]:
        """Ids of the elements this batch added, changed or removed."""
        out: set[str] = set()
        for op in self.ops:
            parts = op.split()
            if len(parts) < 2:
                continue
            if parts[0] in ("+", ">") and len(parts) >= 3:
                out.add(parts[2])
            elif parts[0] == "~":
                out.add(parts[1])
            elif parts[0] == "-":
                out.update(parts[1:])
        return out


def file_hash(data: bytes) -> str:
    """Hash of a file's bytes; an empty file counts as no file."""
    return "sha256:" + hashlib.sha256(data).hexdigest() if data else ""


class History:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: list[Entry] | None = None

    def entries(self) -> list[Entry]:
        if self._entries is None:
            out: list[Entry] = []
            if self.path.exists():
                for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        out.append(Entry.from_json(line))
                    except (ValueError, KeyError, TypeError) as e:
                        raise LoadError([f"{LOG}:{n}: cannot read history entry: {e}"]) from None
            self._entries = out
        return self._entries

    def last(self) -> int:
        es = self.entries()
        return es[-1].batch if es else 0

    def get(self, batch: int) -> Entry | None:
        return next((e for e in self.entries() if e.batch == batch), None)

    def append(self, entry: Entry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")
        self.entries().append(entry)

    def known_hashes(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for e in self.entries():
            out.update(e.files)
        return out

    def ifc_state(self) -> dict[str, tuple[str, str]]:
        """What the imports of IFC files brought: IFC key to (element id, hash of its line).

        An import that was reverted counts for nothing, unless the revert was reverted.
        """
        undone: set[int] = set()
        for e in self.entries():
            if e.revert is not None:
                undone.symmetric_difference_update({e.revert})
        out: dict[str, tuple[str, str]] = {}
        for e in self.entries():
            if e.ifc is None or e.batch in undone:
                continue
            for key in e.ifc.get("gone", []):
                out.pop(str(key), None)
            lines: dict[str, str] = e.ifc.get("lines", {})
            for key, ident in e.ifc.get("ids", {}).items():
                out[str(key)] = (str(ident), str(lines.get(ident, "")))
        return out

    def max_ids(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries():
            for i in e.ids:
                m = ID_RE.match(i)
                if m:
                    out[m.group(1)] = max(out.get(m.group(1), 0), int(m.group(2)))
        return out


class Project:
    def __init__(self, root: Path, reg: Registry | None = None) -> None:
        self.root = root
        self.reg = reg or default_registry()
        self.history = History(root / LOG)

    @classmethod
    def find(cls, start: Path) -> "Project":
        p = start.resolve()
        for d in (p, *p.parents):
            if (d / "project.uea").exists():
                return cls(d)
        raise NotAProject(f"no project.uea in {p} or above. Start one: uea init <dir>")

    @classmethod
    def init(cls, root: Path) -> "Project":
        if (root / "project.uea").exists():
            raise FileExistsError(f"{root} is already a project")
        root.mkdir(parents=True, exist_ok=True)
        (root / "project.uea").write_text("", encoding="utf-8")
        (root / LOG).touch()
        gi = root / ".gitignore"
        if not gi.exists():
            gi.write_text(GITIGNORE, encoding="utf-8")
        return cls(root)

    @property
    def out(self) -> Path:
        return self.root / "out"

    def file_of(self, pack: str) -> Path:
        return self.root / f"{pack}.uea"

    def read_texts(self) -> dict[str, str]:
        """Text of every `.uea` file, keyed by file name."""
        out: dict[str, str] = {}
        for p in sorted(self.root.glob("*.uea")):
            out[p.name] = p.read_text(encoding="utf-8")
        return out

    def hashes(self) -> dict[str, str]:
        return {p.name: file_hash(p.read_bytes()) for p in sorted(self.root.glob("*.uea"))}

    def parse(self, texts: dict[str, str]) -> Model:
        model = Model(self.reg)
        errors: list[str] = []
        where: dict[str, str] = {}
        for name, text in texts.items():
            pack = name.removesuffix(".uea")
            if pack not in self.reg.packs:
                if pack in DISCIPLINES:
                    errors.append(f"{name}: the {pack} pack is not available in this UEA version")
                else:
                    errors.append(
                        f"{name}: unknown file; discipline files are {', '.join(self.reg.packs)}"
                    )
                continue
            for n, line in enumerate(text.splitlines(), 1):
                try:
                    raw = parse_line(line)
                    if raw is None:
                        continue
                    el = element_from_raw(self.reg, raw)
                except LineError as e:
                    errors.append(f"{name}:{n}: {e}")
                    continue
                if type(el).pack != pack:
                    errors.append(f"{name}:{n}: {el.kind} {el.id} belongs in {type(el).pack}.uea")
                    continue
                if el.id in model:
                    errors.append(f"{name}:{n}: {el.id} is already defined in {where[el.id]}")
                    continue
                where[el.id] = f"{name}:{n}"
                model.put(el)
        if errors:
            raise LoadError(errors)
        return model

    def load(self) -> Model:
        return self.parse(self.read_texts())

    def write(self, model: Model, packs: set[str]) -> dict[str, str]:
        """Write the files of the given packs in canonical form; returns their new hashes."""
        out: dict[str, str] = {}
        for pack in sorted(packs, key=DISCIPLINES.index):
            path = self.file_of(pack)
            text = model.pack_text(pack)
            if not text and pack != "project":
                if path.exists():
                    path.unlink()
                out[path.name] = ""
                continue
            data = text.encode("utf-8")
            tmp = path.with_suffix(".uea.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            out[path.name] = file_hash(data)
        return out

    @contextmanager
    def lock(self) -> Generator[None]:
        path = self.root / ".uea.lock"
        with path.open("a+") as f:
            if os.name == "nt":  # pragma: no cover
                import msvcrt

                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
                try:
                    yield
                finally:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

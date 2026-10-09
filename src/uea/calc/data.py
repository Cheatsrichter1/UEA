"""The norm tables an office supplies from its own licensed copies (decision 0008, 0028).

A `norm` calculator declares the tables it needs as `Spec`s. The office, or its agent, writes
each table as a CSV file and stores it with `uea data add`; it lives on the machine, outside
every project, and is never committed. Without a table the calculator stops and says which one
is missing. Every result records the edition of each table it used.
"""

import csv
import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ENV = "UEA_DATA"
"""Names the folder of the tables; otherwise `$XDG_DATA_HOME/uea` or `~/.local/share/uea`."""
MAX_ERRORS = 10


@dataclass(frozen=True)
class Col:
    name: str
    kind: Literal["text", "num"] = "num"
    doc: str = ""
    choices: tuple[str, ...] = ()
    """For text: the allowed values, compared without regard to case."""


@dataclass(frozen=True)
class Spec:
    id: str
    title: str
    standard: str
    """Where the office finds the values."""
    cols: tuple[Col, ...]
    key: tuple[str, ...]
    """The columns that identify a row; no two rows may have the same key."""
    doc: str = ""

    def header(self) -> str:
        return ",".join(c.name for c in self.cols)


class MissingTable(ValueError):
    def __init__(self, spec: Spec) -> None:
        super().__init__(
            f"the table {spec.id!r} ({spec.title}, {spec.standard}) is not installed on this"
            f" machine; add it from your own copy: uea data add {spec.id} <file.csv>"
            f" --edition <edition>. Columns: {spec.header()} (uea data show {spec.id})"
        )
        self.spec = spec


@dataclass
class Table:
    spec: Spec
    edition: str
    source: str
    added: str
    sha: str
    rows: list[dict[str, str | float]] = field(default_factory=list[dict[str, str | float]])

    def find(self, **where: str | float) -> dict[str, str | float] | None:
        """The row whose columns equal the given values; text without regard to case."""
        for row in self.rows:
            if all(_same(row[k], v) for k, v in where.items()):
                return row
        return None

    def cite(self) -> str:
        """For the record of a result: which table, which edition, which file."""
        src = f", {self.source}" if self.source else ""
        head = f"{self.spec.id} ({self.spec.standard})"
        return f"{head}, Ausgabe {self.edition}{src}, sha256 {self.sha[:8]}"


def _same(a: str | float, b: str | float) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.casefold() == b.casefold()
    return a == b


def root() -> Path:
    env = os.environ.get(ENV)
    if env:
        return Path(env)
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "uea"


def _path(spec: Spec) -> Path:
    return root() / "tables" / f"{spec.id}.json"


def parse_csv(spec: Spec, text: str) -> tuple[list[dict[str, str | float]], list[str]]:
    """The rows of a CSV file and what is wrong with it. Comma or semicolon separated; with a
    semicolon, numbers may use a decimal comma. Blank lines and lines starting with # are skipped.
    """
    numbered = [
        (i, x)
        for i, x in enumerate(text.lstrip("\ufeff").splitlines(), start=1)
        if x.strip() and not x.lstrip().startswith("#")
    ]
    lines = [x for _, x in numbered]
    if not lines:
        return [], ["the file is empty; the first line must be the header: " + spec.header()]
    delim = ";" if lines[0].count(";") > lines[0].count(",") else ","
    rows = list(csv.reader(lines, delimiter=delim))
    head = [h.strip().lower() for h in rows[0]]
    want = [c.name for c in spec.cols]
    if sorted(head) != sorted(want) or len(set(head)) != len(head):
        return [], [f"the header must name the columns {', '.join(want)}; it has {', '.join(head)}"]
    errors: list[str] = []
    out: list[dict[str, str | float]] = []
    seen: dict[tuple[Any, ...], int] = {}
    for (n, _), raw in zip(numbered[1:], rows[1:], strict=True):
        if len(raw) != len(head):
            errors.append(f"line {n}: {len(raw)} values, the header has {len(head)}")
            continue
        row: dict[str, str | float] = {}
        for name, value in zip(head, raw, strict=True):
            col = next(c for c in spec.cols if c.name == name)
            cell, err = _cell(col, value.strip(), delim == ";")
            if err:
                errors.append(f"line {n}: {name} {err}")
            else:
                row[name] = cell
        if len(row) != len(head):
            continue
        k = tuple(str(row[c]).casefold() for c in spec.key)
        if k in seen:
            errors.append(f"line {n}: the same {'/'.join(spec.key)} as line {seen[k]}")
        seen[k] = n
        out.append(row)
    if not errors and not out:
        errors.append("no rows below the header")
    return out, errors


def _cell(col: Col, value: str, comma: bool) -> tuple[str | float, str | None]:
    if col.kind == "num":
        try:
            num = float(value.replace(",", ".") if comma else value)
        except ValueError:
            return 0.0, f"{value!r} is not a number"
        if num <= 0:
            return 0.0, f"{value!r} must be more than 0"
        return num, None
    if not value:
        return "", "is empty"
    if col.choices:
        for c in col.choices:
            if c.casefold() == value.casefold():
                return c, None
        return "", f"{value!r} is not one of {', '.join(col.choices)}"
    return value, None


def add(spec: Spec, path: Path, edition: str, source: str = "") -> tuple[Table | None, list[str]]:
    """Check a CSV file against the spec and store it, replacing an earlier version."""
    try:
        data = path.read_bytes()
    except OSError as e:
        return None, [f"cannot read {path}: {e.strerror}"]
    rows, errors = parse_csv(spec, data.decode("utf-8", errors="replace"))
    if errors:
        more = len(errors) - MAX_ERRORS
        return None, [*errors[:MAX_ERRORS], *([f"... and {more} more"] if more > 0 else [])]
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    table = Table(spec, edition, source, now, hashlib.sha256(data).hexdigest(), rows)
    target = _path(spec)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "id": spec.id,
                "edition": edition,
                "source": source,
                "added": now,
                "sha256": table.sha,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return table, []


def load(spec: Spec) -> Table | None:
    path = _path(spec)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Table(
        spec, raw["edition"], raw.get("source", ""), raw["added"], raw["sha256"], raw["rows"]
    )


def need(spec: Spec) -> Table:
    table = load(spec)
    if table is None:
        raise MissingTable(spec)
    return table


def remove(spec: Spec) -> bool:
    path = _path(spec)
    if not path.is_file():
        return False
    path.unlink()
    return True


def specs_of(calcs: Iterable[Any]) -> dict[str, Spec]:
    """The tables the given calculators declare, by id."""
    out: dict[str, Spec] = {}
    for c in calcs:
        for s in c.tables:
            out.setdefault(s.id, s)
    return out

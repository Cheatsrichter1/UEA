"""The line syntax shared by `.uea` files and operations.

A line is `kind key bare... "label" key=value...`. Bare tokens are the positional fields
followed by flags. `#` outside quotes starts a comment.
"""

import re
from dataclasses import dataclass

_TOKEN = re.compile(r'(?:[^\s"=]+=)?"[^"]*"|[^\s"]+|"')
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LineError(ValueError):
    """A line that cannot be read. The message says what is wrong and how to fix it."""


@dataclass(frozen=True, slots=True)
class RawLine:
    kind: str
    key: str
    bare: tuple[str, ...]
    label: str | None
    kv: tuple[tuple[str, str], ...]


def strip_comment(text: str) -> str:
    """Remove a `#` comment that starts at the line start or after whitespace, outside quotes."""
    quoted = False
    for i, ch in enumerate(text):
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted and (i == 0 or text[i - 1].isspace()):
            return text[:i]
    return text


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN.findall(text)
    if '"' in tokens:
        raise LineError('unterminated quote: close the label with "')
    return tokens


def parse_tokens(tokens: list[str]) -> RawLine:
    if len(tokens) < 2:
        raise LineError("a line needs at least a kind and a key, e.g. `level EG z=0`")
    kind, key = tokens[0], tokens[1]
    if kind.startswith('"') or "=" in kind:
        raise LineError(f"line must start with a kind, not {kind}")
    if key.startswith('"') or "=" in key:
        raise LineError(f"{kind}: the second token must be its id or name, not {key}")
    bare: list[str] = []
    label: str | None = None
    kv: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tok in tokens[2:]:
        if tok.startswith('"'):
            if label is not None:
                raise LineError(f"{key}: two labels; an element has one quoted label")
            label = tok[1:-1]
        elif "=" in tok:
            k, v = tok.split("=", 1)
            if not _KEY.match(k):
                raise LineError(f"{key}: bad field name {k!r}")
            if k in seen:
                raise LineError(f"{key}: field {k} given twice")
            seen.add(k)
            if v.startswith('"'):
                v = v[1:-1]
            kv.append((k, v))
        else:
            bare.append(tok)
    return RawLine(kind, key, tuple(bare), label, tuple(kv))


def parse_line(text: str) -> RawLine | None:
    """Parse one line; None for blank and comment lines."""
    body = strip_comment(text).strip()
    if not body:
        return None
    return parse_tokens(tokenize(body))


def fmt_num(v: float) -> str:
    """Shortest decimal form, at most 4 decimals (0.1 mm in metres): 0.15, 2, -0.3."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in {"-0", ""} else s


def quote(s: str) -> str:
    return f'"{s}"'


def needs_quotes(s: str) -> bool:
    return s == "" or any(ch.isspace() for ch in s) or s.startswith("#")

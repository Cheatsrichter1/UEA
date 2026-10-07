"""Number formatting for CLI output: lengths to the millimetre, areas to 0.01 m²."""

from collections.abc import Iterable


def ln(v: float) -> str:
    """A length or coordinate: 2.515, 10, -0.15."""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in {"-0", ""} else s


def zz(v: float) -> str:
    """An absolute height with sign: +6.12, -0.15, ±0."""
    s = ln(v)
    if s == "0":
        return "±0"
    return s if s.startswith("-") else "+" + s


def ar(v: float) -> str:
    return f"{v:.2f}"


def iv(a: float, b: float) -> str:
    return f"{ln(a)}..{ln(b)}"


def ids(items: Iterable[str], limit: int = 12) -> str:
    """Ids, with runs compressed: d1-d5 f1 f3. Long lists are cut."""
    xs = list(items)
    out: list[str] = []
    i = 0
    while i < len(xs):
        j = i
        p, n = split_id(xs[i])
        while j + 1 < len(xs):
            q, m = split_id(xs[j + 1])
            prev = split_id(xs[j])[1]
            if q != p or n is None or m is None or prev is None or m != prev + 1:
                break
            j += 1
        out.append(xs[i] if j - i < 2 else f"{xs[i]}-{xs[j]}")
        if j - i == 1:
            out.append(xs[j])
        i = j + 1
    if len(out) > limit:
        return " ".join(out[:limit]) + f" +{len(out) - limit} more"
    return " ".join(out)


def split_id(s: str) -> tuple[str, int | None]:
    k = len(s)
    while k > 0 and s[k - 1].isdigit():
        k -= 1
    if k == len(s) or k == 0:
        return s, None
    return s[:k], int(s[k:])

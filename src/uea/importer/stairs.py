"""Fitting a stair to what its treads show (decision 0030).

A file writes a stair as an extrusion, a clipped solid or a mesh; what survives every way of writing
it is the treads, the horizontal faces that look up, one height per tread. UEA wants the stair by
its parameters (n, tread, w, shape) and its layout follows from them (`packs/arch/stairs.py`). So
the importer reads the direction, the tread depth and the width off the first treads, builds the
layouts that could fit, and keeps the one whose treads lie closest to the file's. A stair that fits
none is reported, never guessed.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

from shapely.affinity import affine_transform
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from uea.importer.common import Lv, num
from uea.importer.ifc import Stair
from uea.packs.arch.stairs import LFlight, layout, to_plan

RISER = (0.08, 0.30)
"""Riser heights (m) a stair can have."""
LEVEL = 0.02
"""A tread lies within 2 cm of a whole number of risers above the floor."""
FIT = 0.06
"""A layout fits if the treads differ from the file's by less than this share of their area."""
DEVIATES = 0.9
"""A tread is straight if it overlaps the one a straight stair would have by this share."""
GAPS = (0.0, 1.0)
"""The well between the flights of a U stair."""


@dataclass(frozen=True)
class Cand:
    shape: str
    turn: str | None = None
    n1: int | None = None
    winders: int | None = None
    gap: float | None = None


@dataclass
class StairFit:
    low: Lv
    high: Lv
    tail: str
    """The line after kind and id."""
    poly: Polygon
    """Its footprint in the plan."""
    error: float
    """Share of the treads' area that lies elsewhere than in the file."""


def fit_stair(st: Stair, levels: Sequence[Lv]) -> StairFit | str:
    """The stair as UEA would have it, or why it cannot be."""
    zs = [z for z, _ in st.treads]
    riser0 = median(b - a for a, b in pairwise(zs))
    if not RISER[0] <= riser0 <= RISER[1]:
        return "its steps are not between 8 and 30 cm high"
    found = _storeys(zs, riser0, levels)
    if found is None:
        return "no two storeys of the model have a whole number of its risers between them"
    low, high, n, riser = found
    seen: dict[int, BaseGeometry] = {}
    for z, region in st.treads:
        k = round((z - low.storey.z) / riser)
        if 1 <= k <= n - 1:
            seen[k] = seen[k].union(region) if k in seen else region
    if 1 not in seen or 2 not in seen:
        return "its first two treads are missing"
    up, t, w = _first(seen[1], seen[2])
    if not (0.15 <= t <= 0.6 and 0.4 <= w <= 3.5):
        return f"its treads are {num(t)} deep and {num(w)} wide"
    best: tuple[float, Cand, Polygon] | None = None
    for cand in _cands(seen, n, t, w, up):
        made = _predict(cand, n, t, w, up, seen[1])
        if made is None:
            continue
        pred, poly = made
        err = _error(pred, seen, n)
        if best is None or err < best[0]:
            best = (err, cand, poly)
    if best is None or best[0] > FIT:
        return "its treads match no straight, L or U stair of UEA"
    err, cand, poly = best
    x0, y0, _x1, _y1 = poly.bounds
    tail = f"{low.name} {high.name} x={num(x0)}+ y={num(y0)}+ up={up} w={num(w)} n={n}"
    tail += f" tread={num(t)}"
    if cand.shape != "straight":
        m = cand.winders or 1
        tail += f" shape={cand.shape} turn={cand.turn}"
        if cand.n1 != (n - m + 1) // 2:
            tail += f" n1={cand.n1}"
        if cand.winders:
            tail += f" winders={cand.winders}"
        if cand.shape == "u" and cand.gap is not None and abs(cand.gap - 0.1) > 1e-9:
            tail += f" gap={num(cand.gap)}"
    return StairFit(low, high, tail, poly, err)


def _storeys(
    zs: list[float], riser0: float, levels: Sequence[Lv]
) -> tuple[Lv, Lv, int, float] | None:
    """The storeys the stair joins: a whole number of its risers apart, its treads on the steps."""
    ordered = sorted(levels, key=lambda lv: lv.storey.z)
    for i, low in enumerate(ordered):
        for high in ordered[i + 1 :]:
            rise = high.storey.z - low.storey.z
            n = round(rise / riser0)
            if n < 3:
                continue
            riser = rise / n
            if abs(riser - riser0) > 0.015:
                continue
            ks = [(z - low.storey.z) / riser for z in zs]
            if all(1 <= round(k) <= n and abs(k - round(k)) * riser <= LEVEL for k in ks):
                return low, high, n, riser
    return None


def _first(one: BaseGeometry, two: BaseGeometry) -> tuple[str, float, float]:
    """Direction of the first flight, tread depth and width from the first two treads."""
    c1, c2 = one.centroid, two.centroid
    dx, dy = c2.x - c1.x, c2.y - c1.y
    up = ("e" if dx > 0 else "w") if abs(dx) >= abs(dy) else ("n" if dy > 0 else "s")
    along = 0 if up in "ew" else 1
    x0, y0, x1, y1 = one.bounds
    a0, a1 = (x0, x1) if along == 0 else (y0, y1)
    across = (y1 - y0) if along == 0 else (x1 - x0)
    t = a1 - a0
    u0, u1, u2, u3 = two.bounds
    if abs((u2 - u0 if along == 0 else u3 - u1) - t) < 0.01:
        step = abs(c2.x - c1.x) if along == 0 else abs(c2.y - c1.y)
        if abs(step - t) < 0.03:
            t = step
    return up, round(t, 3), round(across, 3)


def _cands(seen: dict[int, BaseGeometry], n: int, t: float, w: float, up: str) -> list[Cand]:
    out = [Cand("straight")]
    straight = _predict(out[0], n, t, w, up, seen[1])
    if straight is None:
        return out
    pred, _ = straight
    dev = next((k for k in range(1, n) if _iou(pred.get(k), seen.get(k)) < DEVIATES), None)
    if dev is None:
        return out
    q = _across(seen, up)
    for turn in ("l", "r"):
        for first in (dev, dev - 1):
            if first < 2 or n - first - 1 < 1:
                continue
            out.append(Cand("l", turn, first))
            gap = round(q - 2 * w, 3) + 0.0  # + 0.0: no minus sign in front of a zero
            if GAPS[0] <= gap <= GAPS[1]:
                out.append(Cand("u", turn, first, None, gap))
            out += [Cand("l", turn, first, m) for m in range(2, 7) if n - first - m >= 1]
    return out


def _across(seen: dict[int, BaseGeometry], up: str) -> float:
    """How far the treads reach across the first flight's direction."""
    x0, y0, x1, y1 = _union(seen).bounds
    return (y1 - y0) if up in "ew" else (x1 - x0)


def _union(parts: dict[int, BaseGeometry]) -> BaseGeometry:
    out: BaseGeometry | None = None
    for g in parts.values():
        out = g if out is None else out.union(g)
    assert out is not None
    return out


def _iou(a: BaseGeometry | None, b: BaseGeometry | None) -> float:
    if a is None or b is None:
        return 0.0
    both = a.union(b).area
    return float(a.intersection(b).area / both) if both > 0 else 1.0


def _strip(fl: LFlight, i: int, t: float, w: float) -> Polygon:
    """The i-th regular tread of a flight in the stair's own frame."""
    (sx, sy), (cx, cy) = fl.start, fl.climb
    px, py = -cy, cx
    a, b = (i - 1) * t, i * t
    return Polygon(
        [
            (sx + cx * a - px * w / 2, sy + cy * a - py * w / 2),
            (sx + cx * b - px * w / 2, sy + cy * b - py * w / 2),
            (sx + cx * b + px * w / 2, sy + cy * b + py * w / 2),
            (sx + cx * a + px * w / 2, sy + cy * a + py * w / 2),
        ]
    )


def _predict(
    cand: Cand, n: int, t: float, w: float, up: str, tread1: BaseGeometry
) -> tuple[dict[int, BaseGeometry], Polygon] | None:
    """The treads this layout would have, placed so that its first tread is the file's first, and
    the footprint of the whole stair."""
    try:
        lay = layout(
            cand.shape, n, t, w, cand.n1, cand.winders, 0.1 if cand.gap is None else cand.gap
        )
    except (AssertionError, ValueError):
        return None
    local: dict[int, BaseGeometry] = {}
    for fl in lay.flights:
        for i in range(1, fl.risers):
            local[fl.tread0 + i] = _strip(fl, i, t, w)
    for poly, number in lay.turn:
        local[number] = poly
    if 1 not in local:
        return None
    m = to_plan(up, cand.turn)
    fx, fy, _, _ = affine_transform(local[1], m).bounds
    ox, oy, _, _ = tread1.bounds
    m[4], m[5] = ox - fx, oy - fy
    placed = {k: affine_transform(g, m) for k, g in local.items()}
    foot = affine_transform(lay.poly, m)
    assert isinstance(foot, Polygon)
    return placed, foot


def _error(pred: dict[int, BaseGeometry], seen: dict[int, BaseGeometry], n: int) -> float:
    total = sum(g.area for g in seen.values())
    if total <= 0:
        return 1.0
    miss = 0.0
    for k in range(1, n):
        p, s = pred.get(k), seen.get(k)
        if p is not None and s is not None:
            miss += p.symmetric_difference(s).area
        elif p is not None:
            miss += p.area
        elif s is not None:
            miss += s.area
    return miss / total

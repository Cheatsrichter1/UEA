"""A slab as a plate on the solver PyNite (decision 0040): rectangular plate elements on a grid
that runs through every support line, line supports along the axes of the load-bearing walls
and beams under it, the loads of the rooms on it, linear-elastic.

The grid's lines are the slab's edges, the axes of its supports and the edges of its voids and
holes, divided into steps of at most MESH; an element whose middle lies outside the slab (or in
a void or a hole) is left out. A node on a support's axis is held vertically; the plate ends at
the axes of the exterior walls (`region`).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

import shapely
from shapely.geometry import Point as SPoint
from shapely.geometry.base import BaseGeometry

from uea.packs.arch.geometry import ArchGeo
from uea.packs.struct.frame import solver
from uea.packs.struct.model import Support

MESH = 0.5
"""The largest side of a plate element (m)."""
ON_AXIS = 1e-6
MERGE = 0.1
"""Grid lines closer than this are one line (m)."""
NU = 0.2
"""Poisson's ratio of uncracked concrete, DIN EN 1992-1-1, 3.1.3(4)."""


@dataclass
class Moments:
    """Design moments per metre, from the elements' middles (Wood-Armer: m ± |m_xy|)."""

    bottom_x: float = 0.0
    bottom_y: float = 0.0
    top_x: float = 0.0
    top_y: float = 0.0
    at: dict[str, tuple[float, float]] = field(default_factory=dict[str, tuple[float, float]])
    """Where each largest value is."""
    elements: int = 0
    held: int = 0
    """Nodes held on a support."""


def lines(lo: float, hi: float, marks: list[tuple[float, int]]) -> list[float]:
    """Grid lines from lo to hi through the marks, no step longer than MESH. Marks closer than
    MERGE are one line: the one of higher rank (a support's axis over an edge)."""
    pts = sorted([(lo, 1), (hi, 1), *((x, k) for x, k in marks if lo - 1e-9 <= x <= hi + 1e-9)])
    kept: list[tuple[float, int]] = []
    for x, k in pts:
        if kept and x - kept[-1][0] < MERGE:
            if k > kept[-1][1]:
                kept[-1] = (x, k)
            continue
        kept.append((x, k))
    xs = [x for x, _ in kept]
    out: list[float] = [xs[0]]
    for a, b in pairwise(xs):
        n = max(1, math.ceil((b - a) / MESH - 1e-9))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return out


def _marks(
    g: ArchGeo, net: BaseGeometry, supports: list[Support]
) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    """Where the grid must have lines: the axes of the supports (rank 2) and the corners of the
    slab, its voids and its holes (rank 1)."""
    xs: list[tuple[float, int]] = []
    ys: list[tuple[float, int]] = []
    for s in supports:
        (ax, ay), (bx, by) = _ends(g, s)
        if abs(ax - bx) < ON_AXIS:
            xs.append((ax, 2))
        elif abs(ay - by) < ON_AXIS:
            ys.append((ay, 2))
        else:
            xs += [(ax, 1), (bx, 1)]
            ys += [(ay, 1), (by, 1)]
    for x, y in shapely.get_coordinates(net.boundary):
        xs.append((float(x), 1))
        ys.append((float(y), 1))
    return xs, ys


def _ends(g: ArchGeo, s: Support) -> tuple[tuple[float, float], tuple[float, float]]:
    if s.kind == "wall":
        return g.walls[s.id].end_points()
    c = shapely.get_coordinates(s.shape)
    return (float(c[0][0]), float(c[0][1])), (float(c[-1][0]), float(c[-1][1]))


def region(g: ArchGeo, net: BaseGeometry, supports: list[Support]) -> BaseGeometry:
    """The plate: the slab without the outer half of its exterior walls. The slab over them
    bears on them directly; left on, the strip would stiffen the plate's edge in twisting and
    lower the field moments (on the safe side to leave it off)."""
    out = net
    for s in supports:
        if s.kind != "wall":
            continue
        w = g.walls[s.id]
        if w.ext is None:
            continue
        outer = w.box(w.mid, w.lo - 1.0) if w.ext == "lo" else w.box(w.mid, w.hi + 1.0)
        out = out.difference(outer)
    return out


def _axis(g: ArchGeo, s: Support) -> BaseGeometry:
    return shapely.LineString(_ends(g, s))


def analyse(
    g: ArchGeo,
    net: BaseGeometry,
    supports: list[Support],
    t: float,
    e: float,
    load: Callable[[float, float], float],
    points: list[tuple[float, float, float]],
) -> Moments:
    """The design moments of a slab of thickness t (m) and modulus e (kN/m²) under the design
    area load `load(x, y)` (kN/m², downward) and point loads (x, y, kN)."""
    net = region(g, net, supports)
    x0, y0, x1, y1 = net.bounds
    mx, my = _marks(g, net, supports)
    gx = lines(x0, x1, mx)
    gy = lines(y0, y1, my)
    axes = [_axis(g, s) for s in supports]
    model = solver()()
    model.add_material("c", e, e / (2 * (1 + NU)), NU, 0.0)
    used: dict[tuple[int, int], str] = {}

    def node(i: int, j: int) -> str:
        k = (i, j)
        if k not in used:
            used[k] = f"N{i}_{j}"
            model.add_node(used[k], gx[i], gy[j], 0.0)
        return used[k]

    quads: dict[str, tuple[float, float]] = {}
    for i in range(len(gx) - 1):
        for j in range(len(gy) - 1):
            cx, cy = (gx[i] + gx[i + 1]) / 2, (gy[j] + gy[j + 1]) / 2
            if not net.contains(SPoint(cx, cy)):
                continue
            name = f"Q{i}_{j}"
            model.add_quad(
                name, node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1), t, "c"
            )
            model.add_quad_surface_pressure(name, -load(cx, cy), "D")
            quads[name] = (cx, cy)
    if not quads:
        raise ValueError("the slab has no area to analyse")
    held = [
        (i, j) for (i, j) in used if any(a.distance(SPoint(gx[i], gy[j])) <= ON_AXIS for a in axes)
    ]
    if len(held) < 3:
        raise ValueError("fewer than three points of the slab rest on a support")
    # out of its plane on the supports; in its plane only as much as a rigid body needs, so the
    # solver works out reactions at the supports alone
    first = held[0]
    other = next((k for k in held if gx[k[0]] != gx[first[0]]), held[1])
    for k in held:
        model.def_support(used[k], k == first, k in (first, other), True, False, False, False)
    for x, y, f in points:
        best = min(used, key=lambda k: (gx[k[0]] - x) ** 2 + (gy[k[1]] - y) ** 2)
        model.add_node_load(used[best], "FZ", -f, "D")
    model.add_load_combo("ULS", {"D": 1.0})
    try:
        model.analyze_linear(check_stability=False, check_statics=False)
    except Exception as ex:  # a singular plate: it is not held
        raise ValueError(f"the plate cannot be solved ({type(ex).__name__}): is it held?") from None
    out = Moments(elements=len(quads), held=len(held))
    for name, (cx, cy) in quads.items():
        m = model.quads[name].moment(0.0, 0.0, True, "ULS")
        mxx, myy, mxy = -float(m[0][0]), -float(m[1][0]), abs(float(m[2][0]))
        for key, v in (
            ("bottom_x", mxx + mxy),
            ("bottom_y", myy + mxy),
            ("top_x", -mxx + mxy),
            ("top_y", -myy + mxy),
        ):
            if v > getattr(out, key):
                setattr(out, key, v)
                out.at[key] = (cx, cy)
    return out

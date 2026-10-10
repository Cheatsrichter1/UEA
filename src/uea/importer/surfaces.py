"""Surfaces of a tessellated body: the treads of a stair, the planes of a roof (decision 0030).

A program writes a stair or a roof as an extrusion, a clipped solid or a mesh. Tessellated, they all
have the same faces: the treads are the horizontal faces that look up, the roof planes are the
sloped faces that look up. Lengths are metres in the world of the file.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

GRADIENT_TOL = 0.004
"""Faces whose slope in x and y differs by less than this are one plane."""
HEIGHT_TOL = 0.01
"""... and lie within 1 cm of it."""
LEVEL_TOL = 0.004
"""Horizontal faces within 4 mm of each other in height are one tread."""
MIN_AREA = 0.02


@dataclass
class Shape:
    """Vertices and triangles of one or several products, in world coordinates."""

    verts: np.ndarray
    faces: np.ndarray

    def z(self) -> tuple[float, float]:
        return float(self.verts[:, 2].min()), float(self.verts[:, 2].max())


def merge(shapes: Iterable[Shape]) -> Shape | None:
    parts = list(shapes)
    if not parts:
        return None
    offset = np.cumsum([0, *[len(p.verts) for p in parts[:-1]]])
    return Shape(
        np.vstack([p.verts for p in parts]),
        np.vstack([p.faces + int(o) for p, o in zip(parts, offset, strict=True)]),
    )


@dataclass(frozen=True)
class Plane:
    """z = a x + b y + c over a region of the plan."""

    a: float
    b: float
    c: float
    region: BaseGeometry

    @property
    def area(self) -> float:
        """Plan area."""
        return float(self.region.area)

    @property
    def slope(self) -> float:
        return math.hypot(self.a, self.b)

    def __call__(self, x: float, y: float) -> float:
        return self.a * x + self.b * y + self.c


def _triangles(shape: Shape) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tri = np.round(shape.verts[shape.faces], 5)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return tri, normal, np.linalg.norm(normal, axis=1)


def _union(tri: np.ndarray) -> BaseGeometry:
    parts = [Polygon(t[:, :2]) for t in tri]
    return unary_union([p for p in parts if p.area > 1e-9])


def planes(shape: Shape, *, up: bool = True, steepest: float = 75.0) -> list[Plane]:
    """The planes the faces that look up (or down) lie in, the largest first.

    Faces steeper than `steepest` degrees (the edges of a roof) are left out.
    """
    tri, normal, size = _triangles(shape)
    nz = normal[:, 2] if up else -normal[:, 2]
    keep = np.flatnonzero((size > 1e-9) & (nz > math.cos(math.radians(steepest)) * size))
    if not len(keep):
        return []
    a = -normal[keep, 0] / normal[keep, 2]
    b = -normal[keep, 1] / normal[keep, 2]
    centre = tri[keep].mean(axis=1)
    c = centre[:, 2] - a * centre[:, 0] - b * centre[:, 1]
    members: list[list[int]] = []
    params: list[tuple[float, float, float]] = []
    for k in np.argsort(-np.abs(normal[keep, 2])):
        for i, (pa, pb, pc) in enumerate(params):
            at = pa * centre[k, 0] + pb * centre[k, 1] + pc
            if (
                abs(a[k] - pa) <= GRADIENT_TOL
                and abs(b[k] - pb) <= GRADIENT_TOL
                and abs(at - centre[k, 2]) <= HEIGHT_TOL
            ):
                members[i].append(int(k))
                break
        else:
            members.append([int(k)])
            params.append((float(a[k]), float(b[k]), float(c[k])))
    out: list[Plane] = []
    for ks in members:
        pts = tri[keep[ks]].reshape(-1, 3)
        design = np.column_stack([pts[:, 0], pts[:, 1], np.ones(len(pts))])
        try:
            fit = np.linalg.lstsq(design, pts[:, 2], rcond=None)[0]
        except np.linalg.LinAlgError:
            fit = np.array(params[members.index(ks)])
        region = _union(tri[keep[ks]])
        if not region.is_empty:
            out.append(Plane(float(fit[0]), float(fit[1]), float(fit[2]), region))
    return sorted(out, key=lambda p: -p.area)


def flat_tops(shape: Shape, min_area: float = MIN_AREA) -> list[tuple[float, BaseGeometry]]:
    """The horizontal faces that look up, grouped by height: (z, plan region), lowest first."""
    tri, normal, size = _triangles(shape)
    flat = (size > 1e-9) & (normal[:, 2] > 0.98 * size) & (np.ptp(tri[:, :, 2], axis=1) < 0.002)
    idx = np.flatnonzero(flat)
    if not len(idx):
        return []
    z = tri[idx].mean(axis=1)[:, 2]
    order = np.argsort(z)
    groups: list[list[int]] = [[int(order[0])]]
    for prev, k in pairwise(order):
        if z[k] - z[prev] > LEVEL_TOL:
            groups.append([])
        groups[-1].append(int(k))
    out: list[tuple[float, BaseGeometry]] = []
    for g in groups:
        region = _union(tri[idx[g]])
        if region.is_empty or region.area < min_area:
            continue
        out.append((float(np.mean(z[g])), region))
    return out


def top_z(shape: Shape, points: Sequence[tuple[float, float]]) -> list[float | None]:
    """For each plan point, the height of the highest face that looks up above it, if any."""
    tri, normal, size = _triangles(shape)
    keep = np.flatnonzero((size > 1e-9) & (normal[:, 2] > 1e-6 * size))
    t = tri[keep]
    x0, y0, z0 = t[:, 0, 0], t[:, 0, 1], t[:, 0, 2]
    x1, y1, z1 = t[:, 1, 0], t[:, 1, 1], t[:, 1, 2]
    x2, y2, z2 = t[:, 2, 0], t[:, 2, 1], t[:, 2, 2]
    det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    ok = np.abs(det) > 1e-12
    det = np.where(ok, det, 1.0)
    out: list[float | None] = []
    for x, y in points:
        l0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / det
        l1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / det
        l2 = 1.0 - l0 - l1
        hit = ok & (np.minimum(np.minimum(l0, l1), l2) >= -1e-6)
        out.append(float((l0 * z0 + l1 * z1 + l2 * z2)[hit].max()) if hit.any() else None)
    return out

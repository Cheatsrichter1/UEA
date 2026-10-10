"""Fitting a roof to the planes of its top (decision 0030).

A file writes a roof as a body; what every program agrees on is its surface, the planes its top
faces lie in. UEA wants a roof by its shape (gable, hip, shed, flat, mansard), its pitch and the
knee, the height of the rafters at the eaves. The planes of a UEA roof follow from those
(`make_roof`), so the importer reads shape, pitch and heights off the planes, builds the roof with
UEA's own code, and keeps it if its top lies where the file's top lies. A roof that fits none is
reported, never guessed. Walls whose tops follow a roof get `top=` the same way: UEA's profile of
the wall under the fitted roofs is compared with the top the file gives.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np
import shapely
from pydantic import ValidationError
from shapely.geometry.base import BaseGeometry

from uea.core.model import element_from_raw
from uea.core.registry import Registry
from uea.core.syntax import RawLine, parse_line
from uea.derive import GeoError
from uea.importer.common import ROOF_CORE, Lv, core_index, layers_text, num
from uea.importer.ifc import Layer, Roof
from uea.importer.surfaces import Plane
from uea.packs.arch.geometry import ArchGeo, RoofGeo, WallGeo, make_roof, roof_profile
from uea.packs.arch.kinds import Roof as RoofEl
from uea.packs.arch.kinds import RoofType

MIN_PLANE = 0.1
"""Planes of the top smaller than this (m²) are details, left out."""
FLAT = 0.004
"""A plane flatter than this (0.23°) is horizontal."""
TOL = 0.02
"""The fitted roof may lie this far (m) from the top the file gives."""
SAME = 0.01
"""Heights this close (m) are one height."""
OVERHANG = 2.0
"""The walls' outline is the foot of the roof if the roof reaches at most this far (m) past it."""
TOP_TOL = 0.03
"""A wall top follows a roof if it lies this far (m) from the roof's profile at every sample."""
NOTE = 0.01
"""A fit that lies further than this (m) from the file's top is reported."""
BELOW = 0.05
"""The eaves may lie this far (m) below the slab of the storey; further is no UEA roof."""
EDGE = 0.03
"""Points this close to the border of a plane are left out of the comparison."""
OPPOSITE = {"s": "n", "n": "s", "w": "e", "e": "w"}


@dataclass
class RoofFit:
    level: Lv
    layers: tuple[Layer, ...]
    """Outside to inside."""
    core: int
    body: str
    """The line after kind, id, level and type: shape and what the shape takes."""
    geo: RoofGeo
    error: float
    """Largest distance (m) between the top of the fitted roof and the file's."""
    notes: list[str] = field(default_factory=list[str])


@dataclass
class Pl:
    """One plane of the top, in UEA's heights (relative to ±0.00), and the underside below it."""

    edge: str | None
    """The side it falls to: s, n, w, e. None for a flat plane."""
    t: float
    a: float
    b: float
    c_top: float
    c: float
    """Of the underside of the rafters."""
    area: float
    region: BaseGeometry

    def at(self, x: float, y: float) -> float:
        """Height of the rafter underside."""
        return self.a * x + self.b * y + self.c

    def top(self, x: float, y: float) -> float:
        return self.a * x + self.b * y + self.c_top


def fit_roof(
    r: Roof, levels: Sequence[Lv], geo: ArchGeo, reg: Registry, home: Lv | None
) -> RoofFit | str:
    """The roof as UEA would have it, or why it cannot be."""
    if not levels:
        return "the model has no storey to put it on"
    prep = _prepare(r, levels[0].off)
    if isinstance(prep, str):
        return prep
    return _Fitter(r, prep, geo, reg).run(levels, home)


@dataclass
class _Prep:
    planes: list[Pl]
    layers: tuple[Layer, ...]
    core: int
    notes: list[str]


def _prepare(r: Roof, off: float) -> _Prep | str:
    total = sum(p.area for p in r.top)
    tops = [p for p in r.top if p.area >= max(MIN_PLANE, 0.01 * total)]
    if not tops:
        return "its top has no plane of any size"
    notes: list[str] = []
    layers, core = _build_up(r, tops[0], notes)
    skin = sum(lay.t for lay in layers[: core + 1])
    planes: list[Pl] = []
    for p in tops:
        main, side = max(abs(p.a), abs(p.b)), min(abs(p.a), abs(p.b))
        if main < FLAT:
            a = b = 0.0
        elif side > 0.01 + 0.02 * main:
            return "a plane of its top is not parallel to the x or y axis"
        elif abs(p.b) >= abs(p.a):
            a, b = 0.0, p.b
        else:
            a, b = p.a, 0.0
        centre = p.region.centroid
        z = p(centre.x, centre.y)
        c_top = z - a * centre.x - b * centre.y - off
        h = math.hypot(1.0, a, b)
        edge = None if main < FLAT else ("s" if b > 0 else "n") if b else ("w" if a > 0 else "e")
        planes.append(Pl(edge, math.hypot(a, b), a, b, c_top, c_top - skin * h, p.area, p.region))
    return _Prep(planes, layers, core, notes)


def _build_up(r: Roof, big: Plane, notes: list[str]) -> tuple[tuple[Layer, ...], int]:
    """The layers of the roof, and which of them is the rafters."""
    h = math.hypot(1.0, big.a, big.b)
    centre = big.region.centroid
    under = next(
        (q for q in r.under if abs(q.a - big.a) <= 0.01 and abs(q.b - big.b) <= 0.01), None
    )
    measured = (big(centre.x, centre.y) - under(centre.x, centre.y)) / h if under else None
    layers = r.layers
    if layers and (measured is None or abs(sum(lay.t for lay in layers) - measured) <= SAME):
        return layers, core_index(layers, ROOF_CORE)
    if layers:
        notes.append(
            f"its layers add up to {num(sum(lay.t for lay in layers))} m, its body is"
            f" {num(measured or 0)} m thick; the body counts"
        )
    elif measured is None or measured < 0.01:
        notes.append("its body has no thickness in the file; 2 cm taken")
    thick = measured if measured is not None and measured >= 0.01 else 0.02
    name = r.material or (max(layers, key=lambda lay: lay.t).material if layers else "roof")
    return (Layer(name, round(thick, 3)),), 0


class _Fitter:
    def __init__(self, r: Roof, prep: _Prep, geo: ArchGeo, reg: Registry) -> None:
        self.r, self.prep, self.geo, self.reg = r, prep, geo, reg
        self.region = shapely.union_all([p.region for p in prep.planes])
        self.lower: dict[str, Pl] = {}
        self.upper: dict[str, Pl] = {}
        self.t1 = self.t2 = 0.0
        self.shape = ""
        self.failed = ""
        self.worst = math.inf
        self.nearest = ""

    def run(self, levels: Sequence[Lv], home: Lv | None) -> RoofFit | str:
        reason = self._classify()
        if reason:
            return reason
        low = min(p.at(x, y) for p in self.prep.planes for x, y in _corners(p.region))
        cands = sorted((lv for lv in levels if lv.ssl <= low + 1.0), key=lambda lv: -lv.z)
        if home is not None and home in cands:
            cands.remove(home)
            cands.insert(0, home)
        if not cands:
            return "no storey lies below its eaves"
        for lv in cands[:3]:
            for foot, explicit in self._feet(lv):
                got = self._try(lv, foot, explicit)
                if isinstance(got, RoofFit):
                    got.notes = [*self.prep.notes, *got.notes]
                    return got
        if self.failed:
            return self.failed
        no = "its top matches no single gable, hip, shed, flat or mansard roof of UEA"
        if self.nearest:
            return f"{no} (nearest: {self.nearest}, up to {num(self.worst)} m off)"
        return no

    # --- what kind of roof

    def _classify(self) -> str:
        planes = self.prep.planes
        t1 = max(p.t for p in planes)
        if t1 < FLAT:
            self.shape = "flat"
            self.t1 = 0.0
            self.lower = {}
            return ""
        sloped = [p for p in planes if p.t >= FLAT]
        near = [p for p in sloped if abs(p.t - t1) <= 0.01 + 0.015 * t1]
        rest = [p for p in sloped if p not in near]
        self.t1 = sum(p.t for p in near) / len(near)
        if rest:
            t2 = max(p.t for p in rest)
            if any(abs(p.t - t2) > 0.01 + 0.015 * t2 for p in rest):
                return "its top has planes of more than two slopes"
            self.t2 = sum(p.t for p in rest) / len(rest)
        for group, into in ((near, self.lower), (rest, self.upper)):
            for p in sorted(group, key=lambda q: -q.area):
                assert p.edge is not None
                if p.edge in into:
                    return f"its top has two planes falling to the {p.edge} side"
                into[p.edge] = p
        edges = set(self.lower)
        if self.upper and set(self.upper) != edges:
            return "its top has a steeper and a flatter plane on different sides"
        if any(p.t < FLAT for p in planes):
            return "its top has flat and sloped planes together"
        if self.upper:
            if edges not in ({"s", "n"}, {"w", "e"}, {"s", "n", "w", "e"}):
                return "its top matches no mansard roof of UEA"
            self.shape = "mansard"
        elif len(edges) == 1:
            self.shape = "shed"
        elif edges in ({"s", "n"}, {"w", "e"}):
            self.shape = "gable"
        elif edges == {"s", "n", "w", "e"}:
            self.shape = "hip"
        else:
            return "its top matches no gable, hip or shed roof of UEA"
        return ""

    # --- where it stands

    def _feet(self, lv: Lv) -> list[tuple[tuple[float, float, float, float], bool]]:
        """The rectangles the roof can stand on: the outline of the storey, if the roof fits it,
        and the extent of the roof itself."""
        x0, y0, x1, y1 = self.region.bounds
        feet: list[tuple[tuple[float, float, float, float], bool]] = []
        dom = self.geo.domains.get(lv.name)
        if dom is not None and not dom.is_empty:
            dx0, dy0, dx1, dy1 = dom.bounds
            if abs((dx1 - dx0) * (dy1 - dy0) - dom.area) <= 1e-3:
                over = (dx0 - x0, x1 - dx1, dy0 - y0, y1 - dy1)
                if min(over) >= -SAME and max(over) <= OVERHANG:
                    feet.append(((dx0, dx1, dy0, dy1), False))
        feet.append(((x0, x1, y0, y1), True))
        return feet

    def _try(
        self, lv: Lv, foot: tuple[float, float, float, float], explicit: bool
    ) -> RoofFit | None:
        for fields, base, eaves in self._fields(foot):
            got = self._build(lv, foot, explicit, fields, base, eaves)
            if got is not None:
                return got
        return None

    def _build(
        self,
        lv: Lv,
        foot: tuple[float, float, float, float],
        explicit: bool,
        fields: str,
        base: float,
        eaves: str,
    ) -> RoofFit | None:
        x0, x1, y0, y1 = foot
        knee = nice(base - lv.ssl)
        if self.shape == "flat" and knee <= 0:
            self.failed = "its underside is not above the storey it would stand on"
            return None
        if knee < -BELOW:
            self.failed = "its eaves lie below the slab of the storey it would stand on"
            return None
        bx0, by0, bx1, by1 = self.region.bounds
        notes: list[str] = []
        spans = ""
        over = ""
        if explicit:
            spans = f" x={num(nice(x0))}..{num(nice(x1))} y={num(nice(y0))}..{num(nice(y1))}"
            notes.append(
                "its extent is given by x= y=, the outline of the storey does not fit it; no"
                " overhang is set"
            )
        else:
            sides = {"w": x0 - bx0, "e": bx1 - x1, "s": y0 - by0, "n": by1 - y1}
            eave = [sides[k] for k in "snwe" if k in eaves]
            verge = [sides[k] for k in "snwe" if k not in eaves]
            for name, group in (("eave", eave), ("verge", verge)):
                if group and max(group) - min(group) > TOL:
                    notes.append(
                        f"{name} overhang differs by side ({num(min(group))} to"
                        f" {num(max(group))} m); the mean is taken"
                    )
            if eave and sum(eave) / len(eave) > 0.0005:
                over += f" eave={num(nice(sum(eave) / len(eave)))}"
            if verge and sum(verge) / len(verge) > 0.0005:
                over += f" verge={num(nice(sum(verge) / len(verge)))}"
        body = f"{fields} knee={num(knee)}{over}{spans}"
        layers = layers_text(self.prep.layers, self.prep.core)
        try:
            el = element_from_raw(self.reg, _raw(f"roof rf1 {lv.name} RT {body}"))
            rt = element_from_raw(self.reg, _raw(f"type RT roof layers={layers}"))
            assert isinstance(el, RoofEl) and isinstance(rt, RoofType)
            lvgeo = self.geo.levels[lv.name]
            rg = make_roof(el, rt, lvgeo, x0, x1, y0, y1)
        except (GeoError, ValidationError, ValueError, KeyError, AssertionError):
            return None
        err = self._error(rg)
        if err < self.worst:
            self.worst, self.nearest = err, self.shape
        if err > TOL:
            return None
        if err > NOTE:
            notes.append(f"its top lies up to {num(err)} m from the file's")
        return RoofFit(lv, self.prep.layers, self.prep.core, body, rg, err, notes)

    def _fields(self, foot: tuple[float, float, float, float]) -> list[tuple[str, float, str]]:
        """What the planes could make: shape and pitch, the height of the rafters at the eaves, and
        which sides are eaves. Several if the shape does not say which way the ridge runs."""
        x0, x1, y0, y1 = foot
        at = {"s": (x0, y0), "n": (x0, y1), "w": (x0, y0), "e": (x1, y0)}
        shape, t = self.shape, self.t1
        if shape == "flat":
            return [("flat", self.prep.planes[0].c, "snwe")]
        pitch = pitch_degrees(t)
        base_of = {e: p.at(*at[e]) for e, p in self.lower.items()}
        edges = "".join(e for e in "snwe" if e in self.lower)
        if shape == "shed":
            (e,) = self.lower
            return [(f"shed up={OPPOSITE[e]} pitch={num(pitch)}", base_of[e], e)]
        if shape in ("gable", "mansard") and len(self.lower) == 2:
            e1, e2 = self.lower
            if abs(base_of[e1] - base_of[e2]) > SAME:
                return []
            base = (base_of[e1] + base_of[e2]) / 2
            ridge = f" ridge={'x' if set(self.lower) == {'s', 'n'} else 'y'}"
            if shape == "gable":
                return [(f"gable{ridge} pitch={num(pitch)}", base, edges)]
            return self._mansard(f"mansard{ridge} pitch={num(pitch)}", base, at, edges)
        # four sides: hip, halfhip, or a mansard with hips; the larger planes tell the ridge first
        area = {e: p.area for e, p in self.lower.items()}
        first = "x" if area["s"] + area["n"] >= area["w"] + area["e"] else "y"
        out: list[tuple[str, float, str]] = []
        for ridge in (first, "y" if first == "x" else "x"):
            for got in self._four(ridge, pitch, base_of, at, foot):
                if got not in out:
                    out.append(got)
        return out

    def _four(
        self,
        ridge: str,
        pitch: float,
        base_of: dict[str, float],
        at: dict[str, tuple[float, float]],
        foot: tuple[float, float, float, float],
    ) -> list[tuple[str, float, str]]:
        """A roof with eaves on four sides and the ridge running along x or y."""
        x0, x1, y0, y1 = foot
        main, ends = ("sn", "we") if ridge == "x" else ("we", "sn")
        if abs(base_of[main[0]] - base_of[main[1]]) > SAME:
            return []
        base = (base_of[main[0]] + base_of[main[1]]) / 2
        lifts = [base_of[e] - base for e in ends]
        if abs(lifts[0] - lifts[1]) > SAME:
            return []
        lift = sum(lifts) / 2
        if self.shape == "mansard":
            if abs(lift) > SAME:
                return []
            return self._mansard(f"mansard pitch={num(pitch)}", base, at, "snwe")
        if lift < -SAME:
            return []
        if lift <= SAME:
            return [(f"hip pitch={num(pitch)}", base, "snwe")]
        d_max = (y1 - y0) / 2 if ridge == "x" else (x1 - x0) / 2
        hip = d_max - lift / self.t1
        if hip <= 0:
            return []
        return [(f"gable ridge={ridge} pitch={num(pitch)} halfhip={num(nice(hip))}", base, "snwe")]

    def _mansard(
        self, head: str, base: float, at: dict[str, tuple[float, float]], eaves: str
    ) -> list[tuple[str, float, str]]:
        ratio = 1.0 - self.t2 / self.t1
        rises = [(self.upper[e].at(*at[e]) - base) / ratio for e in self.lower]
        if max(rises) - min(rises) > SAME or min(rises) <= 0:
            return []
        rise = nice(sum(rises) / len(rises))
        upper = pitch_degrees(self.t2)
        return [(f"{head} upper={num(upper)} rise={num(rise)}", base, eaves)]

    # --- does it fit

    def _error(self, rg: RoofGeo) -> float:
        """The largest distance between the top of the fitted roof and the file's top, away from
        the borders between planes."""
        x0, y0, x1, y1 = self.region.bounds
        step = max(0.15, math.sqrt(max(self.region.area, 1.0) / 3000))
        gx, gy = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
        xs, ys = gx.ravel(), gy.ravel()
        planes = rg.planes
        a = np.array([q.a for q in planes])[:, None]
        b = np.array([q.b for q in planes])[:, None]
        c = np.array([q.c for q in planes])[:, None]
        skin = np.array([rg.skin_of(q) for q in planes])
        vals = a * xs + b * ys + c
        pick = vals.argmin(axis=0)
        pred = vals[pick, np.arange(len(xs))] + skin[pick]
        worst = 0.0
        seen = False
        for p in self.prep.planes:
            inner = p.region.buffer(-EDGE)
            if inner.is_empty:
                continue
            mask = shapely.contains_xy(inner, xs, ys)
            if not mask.any():
                continue
            seen = True
            obs = p.a * xs[mask] + p.b * ys[mask] + p.c_top
            worst = max(worst, float(np.abs(pred[mask] - obs).max()))
        return worst if seen else math.inf


def nice(v: float) -> float:
    """A length to the nearest 5 mm: the numbers of the file are good to a few millimetres, and
    0.495 reads better than 0.4949."""
    return round(round(v / 0.005) * 0.005, 3)


def pitch_degrees(slope: float) -> float:
    """A pitch to 0.01°, or to the nearest half degree where it is within 0.05° of that."""
    deg = math.degrees(math.atan(slope))
    r = round(deg * 2) / 2
    return r if abs(deg - r) <= 0.05 else round(deg, 2)


def _raw(line: str) -> RawLine:
    raw = parse_line(line)
    assert raw is not None
    return raw


def _corners(region: BaseGeometry) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in shapely.get_coordinates(region)]


def follows(
    wall: WallGeo,
    profile: Sequence[tuple[float, float, float]],
    parts: Sequence[RoofGeo],
    off: float,
) -> bool:
    """Whether the top the file gives for a wall is the profile UEA cuts it to under the roofs."""
    if not profile or not parts:
        return False
    probe = replace(wall, top=roof_profile(wall, parts))
    for x, y, z in profile:
        pred = probe.top_at(probe.s_of(x, y))
        if pred is None or abs(pred - (z - off)) > TOP_TOL:
            return False
    return True

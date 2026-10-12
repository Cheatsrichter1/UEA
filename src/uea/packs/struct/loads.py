"""Loads and their takedown to the foundation (decision 0040).

A `norm` calculator, not yet reviewed. Characteristic actions per DIN EN 1991-1-1 (weights,
imposed loads, partitions), DIN EN 1991-1-3 (snow) and DIN EN 1991-1-4 (wind) with the values
from the office's tables, combined per DIN EN 1990 with the office's factors:

    slab      G = A · Σ t·γ (its layers) + Σ_rooms A_room · Σ t·γ (their floor build-up)
              Q = Σ_rooms A_room · (q_k(use) + q_partition)
    shares    each point of the slab to its nearest support below, a load-bearing wall or a
              beam (the bisectors of the field, 45° in a rectangle), on a grid of GRID
    roof      per roof plane, on plan: g = Σ t·γ / cos α, s = μ1(α) · s_k, w = c_pe(α) · q_p;
              each plane rests on its eaves (a couple roof: the rafters bear at the eaves), on
              the load-bearing walls under the eaves line
    loads     point and line loads (struct.uea), and partitions heavier than the table: to the
              nearest support of their slab
    wall      G_own = Σ t·γ (its layers) · its net elevation area
    beam      on its bearings, a continuous beam on the solver; its reactions to the walls
    takedown  from the top storey down: a wall passes what it carries to what it stands on, in
              proportion to the overlap
    footing   n_k = (G + Q + S + W) / L; n_d = E_d / L with E_d = γ_G·G + γ_Q·(Q_1 + Σ ψ0·Q_i);
              b ≥ n_d / σ_R,d
"""

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.geometry import Point as SPoint
from shapely.geometry.base import BaseGeometry

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Table
from uea.core.registry import natural
from uea.core.values import Layers
from uea.derive import Derived
from uea.export.tables import wall_qty
from uea.packs.arch.geometry import ArchGeo, RoofGeo, WallGeo
from uea.packs.arch.kinds import FloorType, Roof, RoofType, Room
from uea.packs.struct.actions import Act, Factors
from uea.packs.struct.frame import Case, beam
from uea.packs.struct.geometry import SAMPLE, BeamGeo, LoadGeo, StructGeo
from uea.packs.struct.model import (
    Support,
    beam_bearings,
    lowest,
    on_beam,
    slab_supports,
    stands_on,
)
from uea.packs.struct.tables import (
    FACTORS,
    IMPOSED,
    PARTITION,
    PSI,
    SECTION,
    SNOW,
    UNIT_WEIGHT,
    WIND,
)

__all__ = ["FACTORS", "IMPOSED", "LOADS", "PARTITION", "PSI", "SNOW", "UNIT_WEIGHT", "WIND"]

VERSION = "0.2.0"
NORM = (
    "DIN EN 1991-1-1:2010-12, DIN EN 1991-1-3:2010-12, DIN EN 1991-1-4:2010-12, je mit NA;"
    " DIN EN 1990:2010-12 mit NA"
)
GRID = 0.05
"""The side of the cells a slab or a roof is shared out in (m)."""
EAVES = 0.6
"""A wall carries an eaves if its core lies within this strip inside the eaves line (m)."""
PARAMS = (
    Param(
        "soil",
        float,
        None,
        "design resistance of the soil σ_R,d under strip footings, kN/m², from the"
        " geotechnical report",
        optional=True,
    ),
    Param(
        "sk",
        float,
        None,
        "characteristic snow load on the ground s_k at the site, kN/m² (DIN EN 1991-1-3/NA, the"
        " snow load zone and the altitude); needed with a roof",
        optional=True,
    ),
    Param(
        "qp",
        float,
        None,
        "peak velocity pressure q_p at the roof's height, kN/m² (DIN EN 1991-1-4/NA, the wind"
        " zone and the terrain); needed with a roof",
        optional=True,
    ),
)


@dataclass
class RoomLoad:
    id: str
    poly: BaseGeometry
    """Its finished outline."""
    g: float
    """kN/m², its floor build-up."""
    q: float
    """kN/m², its imposed load."""


@dataclass
class SlabLoad:
    id: str
    level: str
    area: float
    g_slab: float
    """kN/m² of its own layers."""
    floors: float
    """kN, the floor build-ups of the rooms on it."""
    imposed: float
    """kN, the rooms' imposed loads."""
    partition: float
    """kN/m², the surcharge for its partitions."""
    rooms: float
    """m², the rooms on it."""
    shares: dict[str, float] = field(default_factory=dict[str, float])
    """m² of it each support carries (walls and beams)."""
    room_loads: list[RoomLoad] = field(default_factory=list[RoomLoad])
    points: list[tuple[float, float, Act]] = field(default_factory=list[tuple[float, float, Act]])
    """Point loads on it, and the points of its line loads."""

    @property
    def g(self) -> float:
        return self.area * self.g_slab + self.floors

    @property
    def q(self) -> float:
        return self.imposed + self.partition * self.rooms


@dataclass
class WallLoad:
    id: str
    level: str
    length: float
    own: float
    """kN, its own weight."""
    gk: float
    """kN/m², the weight of its build-up."""
    top: Act = field(default_factory=Act)
    """What arrives at its top: slab shares, roofs, walls and beams above, loads."""
    on: list[tuple[str, float]] = field(default_factory=list[tuple[str, float]])
    """What it stands on and the share each takes."""

    @property
    def base(self) -> Act:
        return Act(self.top.g + self.own, self.top.q, self.top.s, self.top.w)


@dataclass
class BeamLoad:
    id: str
    level: str
    section: str
    length: float
    g_own: float
    """kN/m."""
    bearings: list[tuple[str, float]]
    """The walls it rests on, at s along it."""
    cases: dict[str, Case] = field(default_factory=lambda: {k: Case() for k in "gqsw"})
    reactions: dict[str, Act] = field(default_factory=dict[str, Act])


@dataclass
class EdgeLoad:
    edge: str
    length: float
    act: Act
    """kN, all of the planes that drain to it."""
    up: float
    """kN, the characteristic wind suction on those planes (0 or less)."""
    g_roof: float
    """kN, the roof's own weight on it (= act.g)."""
    to: dict[str, float] = field(default_factory=dict[str, float])
    """The walls under it and the share each takes."""


@dataclass
class RoofLoad:
    id: str
    level: str
    g_surface: float
    """kN/m² of the roof's build-up, along its slope."""
    planes: list[tuple[str, float, float, float, float, float, float]] = field(
        default_factory=list[tuple[str, float, float, float, float, float, float]]
    )
    """(edge, pitch °, plan m², g, s, w+, w−) per plane, the loads in kN/m² on plan."""
    edges: list[EdgeLoad] = field(default_factory=list[EdgeLoad])
    flat: dict[str, float] = field(default_factory=dict[str, float])
    """A flat roof: m² each wall under it carries."""
    flat_act: Act = field(default_factory=Act)


@dataclass
class Result:
    slabs: list[SlabLoad] = field(default_factory=list[SlabLoad])
    walls: dict[str, WallLoad] = field(default_factory=dict[str, WallLoad])
    beams: dict[str, BeamLoad] = field(default_factory=dict[str, BeamLoad])
    roofs: list[RoofLoad] = field(default_factory=list[RoofLoad])
    partitions: dict[str, float] = field(default_factory=dict[str, float])
    """kN/m of each light partition."""
    heavy: list[str] = field(default_factory=list[str])
    """Partitions heavier than the table: line loads on their slab."""
    points: list[tuple[str, str, Act, str]] = field(default_factory=list[tuple[str, str, Act, str]])
    """(load, storey, its total, what carries it) of the point and line loads."""
    floating: list[str] = field(default_factory=list[str])
    """Load-bearing walls on nothing below: their loads are not passed on."""
    unsupported: list[str] = field(default_factory=list[str])
    """Beams on fewer than two walls, roofs with no wall under an eaves: loads not passed on."""
    ground: list[str] = field(default_factory=list[str])
    """Slabs on the ground: their loads go to the soil, not to the walls."""
    on_ground: list[str] = field(default_factory=list[str])
    """Loads on the ground slab: to the soil."""
    soil: float | None = None
    sk: float | None = None
    qp: float | None = None
    first: str = ""
    f: Factors | None = None

    @property
    def factors(self) -> Factors:
        assert self.f is not None
        return self.f

    def ed(self, a: Act) -> float:
        return self.factors.design(a)


def weight(layers: Layers, gamma: Table, what: str) -> float:
    """kN/m² of a build-up."""
    total = 0.0
    for x in layers.items:
        row = gamma.find(material=x.material)
        if row is None:
            raise ValueError(
                f"unit-weight has no row for {x.material} ({what}): add it to the table"
            )
        total += x.t * float(row["gamma"])
    return total


def interp(t: Table, col: str, pitch: float, what: str) -> float:
    """A column of a table by pitch, interpolated between its rows."""
    rows = sorted(t.rows, key=lambda r: float(r["pitch"]))
    xs = [float(r["pitch"]) for r in rows]
    if not rows or pitch < xs[0] - 1e-6 or pitch > xs[-1] + 1e-6:
        span = f"{xs[0]:g}° to {xs[-1]:g}°" if rows else "no rows"
        raise ValueError(f"{t.spec.id} covers {span}, not {pitch:.1f}° ({what})")
    return float(np.interp(pitch, xs, [float(r[col]) for r in rows]))


def shares(net: BaseGeometry, supports: list[Support]) -> dict[str, float]:
    """The area of the slab nearest to each support, on a grid (the supports in their order,
    ties to the first)."""
    x0, y0, x1, y1 = net.bounds
    xs = np.arange(x0 + GRID / 2, x1, GRID)
    ys = np.arange(y0 + GRID / 2, y1, GRID)
    gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(net, gx, gy)
    pts = shapely.points(gx[inside], gy[inside])
    dist = np.stack([shapely.distance(s.shape, pts) for s in supports])  # pyright: ignore[reportUnknownMemberType]
    near = np.argmin(dist, axis=0)
    cell = GRID * GRID
    return {s.id: float(np.count_nonzero(near == i)) * cell for i, s in enumerate(supports)}


def nearest(supports: list[Support], x: float, y: float) -> Support:
    p = SPoint(x, y)
    return min(supports, key=lambda s: s.shape.distance(p))


def eave_walls(g: ArchGeo, rg: RoofGeo, edge: str) -> dict[str, float]:
    """The load-bearing walls under an eaves line, each with its share of the line's length:
    walls along the line on the roof's storey, else on the storey below (the slab's edge)."""
    x0, x1, y0, y1 = rg.x0, rg.x1, rg.y0, rg.y1
    strip = {
        "s": shapely.box(x0, y0, x1, y0 + EAVES),
        "n": shapely.box(x0, y1 - EAVES, x1, y1),
        "w": shapely.box(x0, y0, x0 + EAVES, y1),
        "e": shapely.box(x1 - EAVES, y0, x1, y1),
    }[edge]
    o = "h" if edge in "sn" else "v"
    lv = g.levels[rg.level]
    for level in (lv.id, lv.below):
        if level is None:
            continue
        hits: dict[str, float] = {}
        for w in g.walls_on(level):
            if not w.lb or w.o != o:
                continue
            cut = w.core.intersection(strip)
            if cut.area > 1e-4:
                hits[w.id] = cut.area / w.t
        if hits:
            total = sum(hits.values())
            return {k: v / total for k, v in hits.items()}
    return {}


def _edge_of(a: float, b: float) -> str:
    """The eaves a plane z = a·x + b·y + c drains to: the side it falls toward."""
    if abs(b) >= abs(a):
        return "s" if b > 0 else "n"
    return "w" if a > 0 else "e"


def roof_loads(d: Derived, rg: RoofGeo, gamma: Table, env: Env, sk: float, qp: float) -> RoofLoad:
    el = d.model[rg.id]
    assert isinstance(el, Roof)
    rt = d.model[el.type.id]
    assert isinstance(rt, RoofType)
    gs = weight(rt.layers, gamma, rg.id)
    out = RoofLoad(rg.id, rg.level, gs)
    x0, y0, x1, y1 = rg.over.bounds
    xs = np.arange(x0 + GRID / 2, x1, GRID)
    ys = np.arange(y0 + GRID / 2, y1, GRID)
    gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(rg.over, gx, gy)
    px, py = gx[inside], gy[inside]
    z = np.stack([p.a * px + p.b * py + p.c for p in rg.planes])
    which = np.argmin(z, axis=0)
    cell = GRID * GRID
    snow, wind = env.table(SNOW), env.table(WIND)
    edges: dict[str, EdgeLoad] = {}
    for i, p in enumerate(rg.planes):
        area = float(np.count_nonzero(which == i)) * cell
        if area <= 0:
            continue
        slope = math.hypot(p.a, p.b)
        pitch = math.degrees(math.atan(slope))
        what = f"{rg.id} at {pitch:.1f}°"
        g = gs * math.hypot(1.0, slope)
        s = interp(snow, "mu1", pitch, what) * sk
        wp = interp(wind, "pressure", pitch, what) * qp
        wm = min(0.0, interp(wind, "suction", pitch, what)) * qp
        act = Act(g * area, 0.0, s * area, wp * area)
        if slope < 1e-9:
            out.flat_act.add(act)
            out.planes.append(("", pitch, area, g, s, wp, wm))
            continue
        edge = _edge_of(p.a, p.b)
        out.planes.append((edge, pitch, area, g, s, wp, wm))
        length = (rg.x1 - rg.x0) if edge in "sn" else (rg.y1 - rg.y0)
        e = edges.setdefault(edge, EdgeLoad(edge, length, Act(), 0.0, 0.0))
        e.act.add(act)
        e.up += wm * area
        e.g_roof += g * area
    out.edges = [edges[k] for k in "snwe" if k in edges]
    return out


def calculate(d: Derived, env: Env) -> Result:
    g = d.arch
    m = d.model
    sg: StructGeo | None = getattr(d, "struct", None)
    gamma = env.table(UNIT_WEIGHT)
    imposed = env.table(IMPOSED)
    part = env.table(PARTITION)
    res = Result(f=Factors(env))
    res.factors.value("gamma-g")
    res.factors.value("gamma-q")
    res.soil = env.param("soil")
    res.sk = env.param("sk")
    res.qp = env.param("qp")
    first = lowest(g)
    if first is None:
        raise ValueError("there are no storeys")
    res.first = first
    rows = sorted(part.rows, key=lambda r: float(r["upto"]))
    # the walls: their own weight; the light partitions: their surcharge on their storey, or a
    # line load if they are heavier than the table
    surcharge: dict[str, float] = {}
    lines: list[LoadGeo] = []
    for w in sorted(g.walls.values(), key=lambda w: natural(w.id)):
        if not w.active:
            continue
        qty = wall_qty(g, w)
        if qty.net is None:
            raise ValueError(f"{w.id} has no height yet (no slab or roof above it)")
        gk = weight(w.layers, gamma, w.id)
        own = gk * qty.net
        if w.lb:
            res.walls[w.id] = WallLoad(w.id, w.level, w.length, own, gk)
            continue
        if w.level == first:
            continue  # on the ground slab
        per_m = own / w.length
        res.partitions[w.id] = per_m
        row = next((r for r in rows if per_m <= float(r["upto"]) + 1e-9), None)
        if row is None:
            res.heavy.append(w.id)
            lines.append(_partition_line(w, per_m))
            continue
        surcharge[w.level] = max(surcharge.get(w.level, 0.0), float(row["qk"]))
    # the beams
    for b in sorted(sg.beams.values() if sg else [], key=lambda b: natural(b.id)):
        res.beams[b.id] = _beam_load(g, b, env)
    # the slabs: their loads and who carries them
    supports: dict[str, list[Support]] = {}
    for sl in sorted(g.slabs.values(), key=lambda s: natural(s.id)):
        if sl.status == "demolish":
            continue
        rooms = [r for r in g.rooms.values() if r.level == sl.level]
        floors = q = 0.0
        room_loads: list[RoomLoad] = []
        for rg in sorted(rooms, key=lambda r: natural(r.id)):
            el = m[rg.id]
            assert isinstance(el, Room)
            ft = m.get(el.floor.id) if el.floor is not None else None
            gf = weight(ft.layers, gamma, f"floor of {rg.id}") if isinstance(ft, FloorType) else 0
            row = imposed.find(use=el.use)
            if row is None:
                raise ValueError(f"imposed-load has no row for {el.use} ({rg.id})")
            floors += rg.area_fin * gf
            q += rg.area_fin * float(row["qk"])
            room_loads.append(RoomLoad(rg.id, rg.fin, gf, float(row["qk"])))
        load = SlabLoad(
            sl.id,
            sl.level,
            sl.net.area,
            weight(sl.layers, gamma, sl.id),
            floors,
            q,
            surcharge.get(sl.level, 0.0),
            sum(r.area_fin for r in rooms),
            room_loads=room_loads,
        )
        res.slabs.append(load)
        if sl.level == first:
            res.ground.append(sl.id)
            continue
        sup = slab_supports(g, sl, sg)
        if not sup:
            raise ValueError(f"{sl.id} rests on no load-bearing wall")
        supports[sl.level] = sup
        load.shares = shares(sl.net, sup)
        total = sum(load.shares.values())
        for k, a in load.shares.items():
            part_act = Act(load.g * a / total, load.q * a / total)
            _to_support(res, k, part_act)
    # the roofs
    for rg in sorted(g.roofs.values(), key=lambda r: natural(r.id)):
        if rg.status == "demolish":
            continue
        if res.sk is None or res.qp is None:
            raise ValueError(
                f"{rg.id} needs the snow load and the wind pressure of the site: give sk= and"
                " qp= (kN/m²)"
            )
        rl = roof_loads(d, rg, gamma, env, res.sk, res.qp)
        res.roofs.append(rl)
        for e in rl.edges:
            e.to = eave_walls(g, rg, e.edge)
            if not e.to:
                res.unsupported.append(f"{rg.id}.{e.edge}")
            for k, f in e.to.items():
                res.walls[k].top.add(e.act, f)
        if rl.flat_act.total > 0:
            sup = [Support(w.id, "wall", w.core) for w in g.walls_on(rg.level) if w.lb]
            if not sup:
                res.unsupported.append(rg.id)
                continue
            rl.flat = shares(rg.foot, sup)
            total = sum(rl.flat.values())
            for k, a in rl.flat.items():
                res.walls[k].top.add(rl.flat_act, a / total)
    # point and line loads, and the heavy partitions
    for lg in [*sorted(sg.loads.values() if sg else [], key=lambda x: natural(x.id)), *lines]:
        gp, qq = lg.share()
        total = Act(lg.g * (lg.length or 1.0), lg.q * (lg.length or 1.0))
        if lg.level == first:
            res.on_ground.append(lg.id)
            res.points.append((lg.id, lg.level, total, "Baugrund"))
            continue
        sup = supports.get(lg.level)
        sl = next((s for s in res.slabs if s.level == lg.level), None)
        if not sup or sl is None:
            raise ValueError(f"{lg.id}: there is no slab on {lg.level} to carry it")
        to: set[str] = set()
        for x, y in lg.pts:
            s = nearest(sup, x, y)
            act = Act(gp, qq)
            sl.points.append((x, y, act))
            to.add(s.id)
            if s.kind == "wall":
                res.walls[s.id].top.add(act)
            else:
                bl = res.beams[s.id]
                at = g_beam(sg, s.id).s_of(x, y)
                bl.cases["g"].points.append((at, gp))
                bl.cases["q"].points.append((at, qq))
        res.points.append((lg.id, lg.level, total, ", ".join(sorted(to, key=natural))))
    # the takedown, from the top storey down
    for lv in reversed(g.level_order()):
        for wl in [x for x in res.walls.values() if x.level == lv]:
            if lv == first:
                continue
            wl.on = stands_on(g, g.walls[wl.id], sg)
            if not wl.on:
                res.floating.append(wl.id)
            base = wl.base
            for k, f in wl.on:
                if k in res.walls:
                    res.walls[k].top.add(base, f)
                    continue
                b = g_beam(sg, k)
                s0, s1 = on_beam(g, g.walls[wl.id], b)
                per_m = base.times(f / max(s1 - s0, 1e-6))
                for a in "gqsw":
                    res.beams[k].cases[a].uniform.append((s0, s1, per_m.get(a)))
        for bl in [x for x in res.beams.values() if x.level == lv]:
            _solve(res, bl)
    return res


def g_beam(sg: StructGeo | None, key: str) -> BeamGeo:
    assert sg is not None
    return sg.beams[key]


def _to_support(res: Result, key: str, act: Act) -> None:
    """A slab's share: onto a wall's top, or along a beam."""
    if key in res.walls:
        res.walls[key].top.add(act)
        return
    bl = res.beams[key]
    for a in "gq":
        bl.cases[a].uniform.append((0.0, bl.length, act.get(a) / bl.length))


def _partition_line(w: WallGeo, per_m: float) -> LoadGeo:
    a, b = w.end_points()
    line = LineString([a, b])
    n = max(1, round(line.length / SAMPLE))
    pts = [line.interpolate((i + 0.5) / n, normalized=True) for i in range(n)]
    return LoadGeo(w.id, w.level, per_m, 0.0, [(p.x, p.y) for p in pts], line.length)


def _beam_load(g: ArchGeo, b: BeamGeo, env: Env) -> BeamLoad:
    row = env.table(SECTION).find(name=b.section)
    if row is None:
        raise ValueError(f"beam-section has no row for {b.section} ({b.id}): add it to the table")
    bl = BeamLoad(b.id, b.level, b.section, b.length, float(row["g"]), beam_bearings(g, b))
    bl.cases["g"].uniform.append((0.0, b.length, bl.g_own))
    return bl


def _solve(res: Result, bl: BeamLoad) -> None:
    """The beam's reactions on its walls, per action; EI does not change them for a beam of
    one section."""
    if len(bl.bearings) < 2:
        res.unsupported.append(bl.id)
        return
    cases = {k: c for k, c in bl.cases.items() if not c.empty()}
    eff = beam(bl.length, [s for _, s in bl.bearings], 1.0, cases, {k: {k: 1.0} for k in cases})
    for i, (wid, _) in enumerate(bl.bearings):
        act = Act(*(eff[k].reactions[i] if k in eff else 0.0 for k in "gqsw"))
        bl.reactions[wid] = act
        res.walls[wid].top.add(act)


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("loads takes the whole building: leave out the scope")
    res = calculate(d, env)
    f = res.factors
    head = f"γ_G {f.value('gamma-g'):g}, γ_Q {f.value('gamma-q'):g}"
    if res.soil:
        head += f", σ_R,d {res.soil:g} kN/m²"
    if res.roofs:
        head += f", s_k {res.sk:g}, q_p {res.qp:g} kN/m²"
    lines = [head]
    for s in res.slabs:
        h = (
            f"{s.id} {s.level}: {s.area:.1f} m², slab {s.g_slab:.2f} kN/m², floors {s.floors:.1f}"
            f" kN, imposed {s.imposed:.1f} kN"
            + (f" + partitions {s.partition:g} kN/m²" if s.partition else "")
            + f" → G {s.g:.1f} kN, Q {s.q:.1f} kN"
        )
        if s.id in res.ground:
            h += " (on the ground)"
        else:
            total = sum(s.shares.values())
            h += " on " + ", ".join(
                f"{k} {a:.1f} m² ({a / total:.0%})" for k, a in s.shares.items()
            )
        lines.append(h)
    for rl in res.roofs:
        lines += roof_lines(res, rl)
    for k, lv, act, to in res.points:
        lines.append(f"{k} {lv}: G {act.g:.1f} kN, Q {act.q:.1f} kN on {to}")
    for bl in res.beams.values():
        if bl.id in res.unsupported:
            lines.append(f"{bl.id}: rests on fewer than two walls, its load not passed on (not ok)")
            continue
        on = ", ".join(f"{k} {a.total:.1f} kN" for k, a in bl.reactions.items())
        lines.append(f"{bl.id} {bl.level} {bl.section} {bl.length:.2f} m on {on}")
    for k in res.unsupported:
        if "." in k or k not in res.beams:
            lines.append(f"{k}: no load-bearing wall under it, its load not passed on (not ok)")
    for k in res.floating:
        lines.append(f"{k}: on no load-bearing wall below, its load not passed on (not ok)")
    for wl in sorted(res.walls.values(), key=lambda x: natural(x.id)):
        if wl.level != res.first:
            continue
        lines.append(footing_line(res, wl))
    data = {
        "slabs": {
            s.id: {
                "area": round(s.area, 3),
                "g_slab": round(s.g_slab, 4),
                "G": round(s.g, 3),
                "Q": round(s.q, 3),
                "shares": {k: round(a, 3) for k, a in s.shares.items()},
            }
            for s in res.slabs
        },
        "walls": {
            w.id: {
                "level": w.level,
                "own": round(w.own, 3),
                **w.base.data(),
                "top": w.top.data(),
                "on": [k for k, _ in w.on],
            }
            for w in res.walls.values()
        },
        "roofs": {
            rl.id: {
                "g": round(rl.g_surface, 4),
                "edges": {
                    e.edge: {**e.act.data(), "up": round(e.up, 3), "to": e.to} for e in rl.edges
                },
            }
            for rl in res.roofs
        },
        "beams": {
            bl.id: {k: a.data() for k, a in bl.reactions.items()} for bl in res.beams.values()
        },
        "partitions": {k: round(v, 3) for k, v in res.partitions.items()},
        "heavy": res.heavy,
    }
    return Output(
        lines=lines,
        report=report(d, res),
        data=data,
        inputs={"soil": res.soil, "sk": res.sk, "qp": res.qp},
        ok=not (res.floating or res.unsupported),
    )


def uplift(res: Result, e: EdgeLoad) -> float:
    """kN/m at the eaves with the roof's weight favourable and the suction leading."""
    f = res.factors
    return (f.value("gamma-g-inf") * e.g_roof + f.value("gamma-q") * e.up) / e.length


def roof_lines(res: Result, rl: RoofLoad) -> list[str]:
    out: list[str] = []
    for edge, pitch, area, g, s, wp, wm in rl.planes:
        where = f"to eaves {edge}" if edge else "flat"
        out.append(
            f"{rl.id} plane {pitch:.1f}° {area:.1f} m² {where}: g {g:.2f}, s {s:.2f}, w {wp:.2f}"
            f"/{wm:.2f} kN/m² on plan"
        )
    for e in rl.edges:
        to = ", ".join(f"{k} {v:.0%}" for k, v in e.to.items()) or "nothing"
        up = uplift(res, e)
        anchor = ": anchor the rafters" if up < 0 else ""
        out.append(
            f"{rl.id} eaves {e.edge}: G {e.act.g:.1f}, S {e.act.s:.1f}, W {e.act.w:.1f} kN on {to};"
            f" uplift n_d {up:.2f} kN/m{anchor}"
        )
    return out


def footing_line(res: Result, wl: WallLoad) -> str:
    b = wl.base
    nk = b.total / wl.length
    nd = res.ed(b) / wl.length
    w = f", b ≥ {nd / res.soil:.2f} m" if res.soil else ""
    acts = f"G {b.g:.1f} kN, Q {b.q:.1f} kN"
    if b.s or b.w:
        acts += f", S {b.s:.1f} kN, W {b.w:.1f} kN"
    return (
        f"{wl.id} {wl.level} base: {acts} over {wl.length:.2f} m: n_k {nk:.1f} kN/m,"
        f" n_d {nd:.1f} kN/m{w}"
    )


def report(d: Derived, res: Result) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    out = [
        f"# Lastannahmen und Lastabtrag: {title}",
        "",
        *report_body(res),
        "",
        "Berechnet aus dem Modell. Die Tragwerksplanung, ihre Prüfung und die Verantwortung liegen"
        " bei der unterzeichnenden Tragwerksplanerin oder dem unterzeichnenden Tragwerksplaner.",
        "",
    ]
    return "\n".join(out)


def report_body(res: Result, level: int = 2) -> list[str]:
    """The loads and the takedown in German, for the report and the Statische Berechnung."""
    f = res.factors
    h = "#" * level
    out = [
        "Charakteristische Einwirkungen nach DIN EN 1991-1-1, -1-3 und -1-4 mit den Werten aus den"
        " Tabellen des Büros; Kombination nach DIN EN 1990, Gl. 6.10:"
        f" γ_G = {de(f.value('gamma-g'), 2)}, γ_Q = {de(f.value('gamma-q'), 2)}"
        + (
            f"; Schnee s_k = {de(res.sk or 0, 2)} kN/m², Böengeschwindigkeitsdruck"
            f" q_p = {de(res.qp or 0, 2)} kN/m²."
            if res.roofs
            else "."
        ),
        "",
    ]
    if res.roofs:
        out += [f"{h} Dach", ""]
        for rl in res.roofs:
            out.append(
                f"{rl.id}: Eigengewicht des Aufbaus {de(rl.g_surface, 2)} kN/m² Dachfläche."
                " Lasten je m² Grundfläche:"
            )
            out += [
                "",
                md_table(
                    ["Dachfläche", "Neigung", "Grundfl. m²", "g", "s", "w Druck", "w Sog"],
                    [
                        [
                            f"Traufe {edge}" if edge else "flach",
                            f"{de(pitch, 1)}°",
                            de(area, 1),
                            de(g, 2),
                            de(s, 2),
                            de(wp, 2),
                            de(wm, 2),
                        ]
                        for edge, pitch, area, g, s, wp, wm in rl.planes
                    ],
                    right=(1, 2, 3, 4, 5, 6),
                ),
                "",
            ]
            for e in rl.edges:
                to = ", ".join(f"{k} {de(v * 100, 0)} %" for k, v in e.to.items()) or "–"
                up = uplift(res, e)
                note = " Verankerung der Sparren erforderlich." if up < 0 else ""
                out.append(
                    f"- Traufe {e.edge} ({de(e.length, 2)} m): G {de(e.act.g, 1)} kN, S"
                    f" {de(e.act.s, 1)} kN, W {de(e.act.w, 1)} kN auf {to}. Abhebend:"
                    f" {de(f.value('gamma-g-inf'), 2)} · G + {de(f.value('gamma-q'), 2)} · W_Sog"
                    f" = {de(up, 2)} kN/m.{note}"
                )
            out.append("")
    out += [
        f"{h} Decken",
        "",
        md_table(
            [
                "Decke",
                "Geschoss",
                "A m²",
                "g Decke kN/m²",
                "Fußböden kN",
                "Nutzlast kN",
                "Trennw. kN/m²",
                "G kN",
                "Q kN",
                "Auflager",
            ],
            [
                [
                    s.id,
                    s.level,
                    de(s.area, 2),
                    de(s.g_slab, 2),
                    de(s.floors, 1),
                    de(s.imposed, 1),
                    de(s.partition, 2) if s.partition else "–",
                    de(s.g, 1),
                    de(s.q, 1),
                    "Baugrund"
                    if s.id in res.ground
                    else ", ".join(f"{k} {de(a, 1)} m²" for k, a in s.shares.items()),
                ]
                for s in res.slabs
            ],
            right=(2, 3, 4, 5, 6, 7, 8),
        ),
        "",
    ]
    if res.points:
        out += [f"{h} Einzel- und Linienlasten", ""]
        for k, lv, act, to in res.points:
            kind = "schwere Trennwand" if k in res.heavy else "Last"
            out.append(f"- {k} ({kind}, {lv}): G {de(act.g, 1)} kN, Q {de(act.q, 1)} kN auf {to}")
        out.append("")
    if res.beams:
        out += [f"{h} Unterzüge", ""]
        for bl in res.beams.values():
            on = ", ".join(f"{k} {de(a.total, 1)} kN" for k, a in bl.reactions.items()) or (
                "nicht aufgelagert"
            )
            out.append(f"- {bl.id} ({bl.section}, {de(bl.length, 2)} m): Auflager {on}")
        out.append("")
    out += [
        f"{h} Tragende Wände",
        "",
        md_table(
            ["Wand", "Geschoss", "L m", "Eigengewicht kN", "G kN", "Q kN", "S kN", "W kN", "auf"],
            [
                [
                    w.id,
                    w.level,
                    de(w.length, 2),
                    de(w.own, 1),
                    de(w.base.g, 1),
                    de(w.base.q, 1),
                    de(w.base.s, 1),
                    de(w.base.w, 1),
                    "Fundament" if w.level == res.first else ", ".join(k for k, _ in w.on) or "–",
                ]
                for w in sorted(res.walls.values(), key=lambda x: natural(x.id))
            ],
            right=(2, 3, 4, 5, 6, 7),
        ),
        "",
        f"{h} Streifenfundamente",
        "",
    ]
    for w in sorted(res.walls.values(), key=lambda x: natural(x.id)):
        if w.level != res.first:
            continue
        b = w.base
        nk = b.total / w.length
        nd = res.ed(b) / w.length
        width = f", erforderliche Breite b ≥ {de(nd / res.soil, 2)} m" if res.soil else ""
        out.append(f"- **{w.id}:** n_k = {de(nk, 1)} kN/m, n_d = {de(nd, 1)} kN/m{width}.")
    if res.partitions:
        out += ["", f"{h} Leichte Trennwände", ""]
        for k, v in res.partitions.items():
            note = " (schwerer als die Tabelle: Linienlast auf der Decke)" if k in res.heavy else ""
            out.append(f"- {k}: {de(v, 2)} kN/m{note}")
    out += [
        "",
        f"{h} Verfahren",
        "",
        "- Decken: Eigengewicht aus dem Schichtaufbau, Fußbodenaufbau und Nutzlast der Räume nach"
        " ihrer Nutzung; leichte Trennwände als Zuschlag zur Nutzlast, schwerere als Linienlast.",
        "- Lastabtrag: jeder Punkt einer Decke auf das nächste Auflager darunter, eine tragende"
        " Wand oder einen Unterzug (Winkelhalbierende, im Rechteckfeld 45°), auf einem Raster von"
        f" {de(GRID * 100, 0)} cm; Einzel- und Linienlasten auf das nächste Auflager.",
        "- Dach: jede Dachfläche auf ihre Traufe (Sparrendach), Eigengewicht auf die Dachfläche,"
        " Schnee μ1(α)·s_k und Wind c_pe·q_p auf die Grundfläche; die Traufe auf die tragenden"
        " Wände unter ihr, im Dachgeschoss oder darunter.",
        "- Unterzüge: Durchlaufträger auf den Wänden, die sie kreuzen, mit dem Programm PyNite.",
        "- Wände: Eigengewicht aus dem Schichtaufbau und der Ansichtsfläche abzüglich Öffnungen;"
        " Weitergabe an die tragenden Wände und Unterzüge darunter nach der Überdeckung.",
        "- Kombination: γ_G·G + γ_Q·(Q_k,1 + Σ ψ0,i·Q_k,i) mit der Leiteinwirkung, die den größten"
        " Wert ergibt.",
        "",
        f"{h} Abweichungen und nicht abgebildet",
        "",
        "- Wind nur als Last des Daches auf die Wände; keine Horizontallasten, keine Aussteifung.",
        "- Schnee ohne Verwehungen und Anhäufungen, je Dachfläche voll.",
        "- Lasten der Decken je Auflager gleichmäßig über seine Länge; Durchlaufwirkung,"
        " Einspannung und Lasten aus Stürzen am Wandende nicht berücksichtigt.",
    ]
    return out


LOADS = Calculator(
    "loads",
    "Lastannahmen und Lastabtrag",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (UNIT_WEIGHT, IMPOSED, PARTITION, FACTORS, PSI, SNOW, WIND, SECTION),
)

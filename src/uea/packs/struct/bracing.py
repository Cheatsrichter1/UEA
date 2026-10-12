"""The bracing of the building against horizontal wind (decision 0044): the walls that stand
along the wind take it storey by storey, as shear walls of masonry.

For each direction of the wind, x and y:

    band      each storey's facade from its SSL (the lowest from the terrain) to the next SSL,
              the top storey up to the highest point of the building (ridge or wall top); its
              width across the wind
    force     F = q_p · (c_pe,D − c_pe,E) · A, with c_pe of the zones D and E by h/d from the
              office's table (DIN EN 1991-1-4, 7.2.2), at the top of the band
    storey    V_k = Σ F above its base; M_k = Σ F · (z_F − z_base,k)
    piers     the load-bearing walls of the storey along the wind, each stretch between its
              openings a pier; V and M shared by stiffness t · l³ (cantilevers of equal height,
              the slabs rigid in their plane, no torsion)
    pier      N_d = γ_G,inf · G (its share of the wall's permanent load at the base), e = M/N;
              the resultant in the inner third l_c = 3 · (l/2 − e) ≥ l/2 (the joint open at most
              to the middle); v_Ed = V / (t · l_c) ≤ f_vd = min(f_vk0 + 0.4 · σ_d, f_vlt) / γ_M,
              σ_d = N / (t · l_c) (DIN EN 1996-1-1, 6.2 and 3.6.2)
"""

from dataclasses import dataclass, field

from shapely.ops import unary_union

from uea.calc import Env
from uea.derive import Derived
from uea.packs.arch.geometry import WallGeo
from uea.packs.struct.loads import Result
from uea.packs.struct.model import bearing
from uea.packs.struct.tables import MASONRY_SHEAR, WIND_WALL


@dataclass
class Pier:
    wall: str
    lo: float
    hi: float
    t: float
    share: float = 0.0
    v: float = 0.0
    m: float = 0.0
    n: float = 0.0
    e: float = 0.0
    lc: float = 0.0
    v_ed: float = 0.0
    f_vd: float = 0.0
    ok: bool = True
    why: str = ""

    @property
    def length(self) -> float:
        return self.hi - self.lo

    @property
    def eta(self) -> float:
        return self.v_ed / self.f_vd if self.f_vd > 0 else float("inf")


@dataclass
class Direction:
    axis: str
    """x or y: the way the wind blows."""
    cd: float
    ce: float
    hd: float
    forces: list[tuple[str, float, float]] = field(default_factory=list[tuple[str, float, float]])
    """(storey, F kN, z of F) of each band."""
    v: float = 0.0
    m: float = 0.0
    piers: list[Pier] = field(default_factory=list[Pier])


def piers_of(d: Derived, w: WallGeo) -> list[tuple[float, float]]:
    """The stretches of a wall between its doors, windows and holes through it."""
    cuts = sorted(
        [(o.lo, o.hi) for o in d.arch.openings.values() if o.host == w.id and o.kind != "niche"]
        + [
            (h.wall.lo, h.wall.hi)
            for h in d.arch.holes.values()
            if h.wall is not None and h.host == w.id and h.wall.face is None
        ]
    )
    out: list[tuple[float, float]] = []
    at = w.s0
    for lo, hi in cuts:
        if lo - at > 1e-6:
            out.append((at, lo))
        at = max(at, hi)
    if w.s1 - at > 1e-6:
        out.append((at, w.s1))
    return out


def bracing(d: Derived, res: Result, env: Env, level: str) -> list[Direction]:
    """The shear walls of one storey, for the wind in x and in y."""
    g = d.arch
    f = res.factors
    qp = res.qp
    if qp is None:
        raise ValueError("the bracing needs the wind pressure of the site: give qp= (kN/m²)")
    order = g.level_order()
    proj = d.model.of_kind("project")
    ground = float(getattr(proj[0], "ground", None) or 0.0) if proj else 0.0
    tops = [z for w in g.walls.values() if w.active for _, z in w.top]
    top = max([r.ridge_z for r in g.roofs.values()] + tops + [g.levels[order[-1]].ssl])
    cores = unary_union([w.core for w in g.walls.values() if w.active])
    x0, y0, x1, y1 = cores.bounds
    height = top - ground
    gm = f.value("gamma-m")
    gi = f.value("gamma-g-inf")
    rows = sorted(env.table(WIND_WALL).rows, key=lambda r: float(r["upto"]))
    shear = env.table(MASONRY_SHEAR)
    out: list[Direction] = []
    k = order.index(level)
    base = max(g.levels[level].ssl, ground) if k == 0 else g.levels[level].ssl
    for axis in ("x", "y"):
        depth, width = (x1 - x0, y1 - y0) if axis == "x" else (y1 - y0, x1 - x0)
        hd = height / depth
        row = next((r for r in rows if hd <= float(r["upto"]) + 1e-9), None)
        if row is None:
            raise ValueError(f"wind-wall has no row for h/d {hd:.2f}: add it to the table")
        cd, ce = float(row["d"]), float(row["e"])
        dr = Direction(axis, cd, ce, hd)
        for j, lv in enumerate(order):
            lo = max(g.levels[lv].ssl, ground) if j == 0 else g.levels[lv].ssl
            hi = g.levels[order[j + 1]].ssl if j + 1 < len(order) else top
            if hi <= lo:
                continue
            force = qp * (cd - ce) * width * (hi - lo)
            dr.forces.append((lv, force, hi))
        above = [(fz, z) for lv, fz, z in dr.forces if order.index(lv) >= k]
        dr.v = sum(fz for fz, _ in above)
        dr.m = sum(fz * (z - base) for fz, z in above)
        o = "h" if axis == "x" else "v"
        piers: list[Pier] = []
        for w in bearing(g, level):
            if w.o != o:
                continue
            for lo, hi in piers_of(d, w):
                piers.append(Pier(w.id, lo, hi, w.layers.core))
        stiff = sum(p.t * p.length**3 for p in piers)
        for p in piers:
            w = g.walls[p.wall]
            wl = res.walls[p.wall]
            total = sum(x.length for x in piers if x.wall == p.wall)
            p.share = p.t * p.length**3 / stiff if stiff > 0 else 0.0
            p.v, p.m = dr.v * p.share, dr.m * p.share
            p.n = gi * wl.base.g * p.length / total
            p.e = p.m / p.n if p.n > 0 else float("inf")
            p.lc = min(p.length, 3 * (p.length / 2 - p.e))
            if p.lc < p.length / 2 - 1e-9:
                p.ok, p.why = False, "joint open past the middle"
                continue
            row = shear.find(material=_core(w))
            if row is None:
                raise ValueError(f"masonry-shear has no row for {_core(w)} ({w.id}): add it")
            sigma = p.n / (p.t * p.lc) / 1000
            fvk = min(float(row["fvk0"]) + 0.4 * sigma, float(row["fvlt"]))
            p.f_vd = fvk / gm
            p.v_ed = p.v / (p.t * p.lc) / 1000
            p.ok = p.v_ed <= p.f_vd + 1e-9
            if not p.ok:
                p.why = "shear"
        dr.piers = piers
        out.append(dr)
    return out


def _core(w: WallGeo) -> str:
    for x in w.layers.items:
        if x.core:
            return x.material
    raise ValueError(f"{w.id} has no core layer")

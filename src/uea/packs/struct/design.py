"""The Statische Berechnung (decision 0040): the loads, the design of every position, the
strip footings and the holes in load-bearing members, as one calculation to sign.

A `norm` calculator. The positions (`positions.py`) are proved as follows:

    roof     the loads on the walls under its eaves and the uplift at the eaves (loads)
    slab     a plate on the solver (plate.py) under γ_G·g + γ_Q·q of the rooms on it, all rooms
             and alternate rooms loaded; design moments m ± |m_xy| (Wood-Armer) at the
             elements' middles; per direction and face μ = m / (d²·f_cd), ω = 1 − √(1 − 2μ),
             a_s = ω·d·f_cd / f_yd, x/d = ω / λ ≤ xi (rectangular stress block, λ = 0.8, η = 1,
             DIN EN 1992-1-1, 3.1.7(3)), at least a_s,min (9.2.1.1); shear v_Ed ≤ v_Rd,c
             (6.2.2); slenderness l/d ≤ min(ld, ld-span / l) (7.4.2 with NA)
    beam     a continuous beam on the solver: M_Ed ≤ W·k_mod·f_k/γ_M, V_Ed ≤ A_v·k_mod·f_v,k/γ_M,
             the deflection under the characteristic loads ≤ L/n
    wall     DIN EN 1996-3, 4.2.2: N_Ed ≤ N_Rd = Φ·f_d·t per metre of the wall without its
             openings; f_d = ζ·f_k/γ_M; Φ1 = 0.85 − 0.0011·(h_ef/t)², h_ef = ρ2·h under a slab
             and h under a roof; at the end support of a slab Φ = min(Φ1, Φ2(l_f)) from the
             office's table; the conditions of the simplified method from the office's limits
    lintel   q_d of the wall's load at its top per metre and of the masonry over the opening
             (no arching), against the manufacturer's table
    rafter   a pair of rafters of a gable roof, with its collar beam, as a plane frame on the
             solver: bending with compression or tension (k_c), shear and deflection
             (DIN EN 1995-1-1, 6.2.3, 6.2.4, 6.3.2)
    column   N_Ed ≤ N_b,Rd = χ·A·f_k/γ_M, χ by the section's buckling curve (DIN EN 1993-1-1,
             6.3.1.2), pinned at both ends
    bracing  the wind on the facades per storey, shared by the masonry piers along it
             (bracing.py)
    footing  b ≥ n_d / σ_R,d (loads); a column's pad a ≥ √(N_d / σ_R,d)
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import shapely
from shapely.geometry import LineString
from shapely.geometry import Point as SPoint
from shapely.geometry.base import BaseGeometry

from uea.calc import Calculator, Env, Output, de, md_table
from uea.core.registry import natural
from uea.core.values import Layers
from uea.derive import Derived
from uea.export.tables import wall_profile
from uea.packs.arch.geometry import ArchGeo, OpeningGeo, RoofGeo, WallGeo
from uea.packs.struct.actions import Factors
from uea.packs.struct.bracing import bracing
from uea.packs.struct.frame import Bar, Case, Push, beam, plane_frame, solver_version
from uea.packs.struct.kinds import Rafter
from uea.packs.struct.loads import (
    NORM as LOADS_NORM,
)
from uea.packs.struct.loads import (
    PARAMS,
    Result,
    RoofLoad,
    SlabLoad,
    calculate,
    footing_line,
    interp,
    report_body,
    uplift,
)
from uea.packs.struct.loads import (
    VERSION as LOADS_VERSION,
)
from uea.packs.struct.model import Support, slab_supports
from uea.packs.struct.plate import MESH, Moments, solve
from uea.packs.struct.positions import Pos, positions
from uea.packs.struct.tables import (
    BEAM_MATERIAL,
    COLUMN_SECTION,
    CONCRETE,
    FACTORS,
    IMPOSED,
    LIMITS,
    LINTEL,
    MASONRY,
    MASONRY_END,
    MASONRY_SHEAR,
    PARTITION,
    PSI,
    SECTION,
    SNOW,
    TIMBER,
    UNIT_WEIGHT,
    WIND,
    WIND_WALL,
)

VERSION = "0.2.0"
NORM = (
    "DIN EN 1996-3:2010-12 mit NA (Mauerwerk, vereinfachtes Verfahren); DIN EN 1992-1-1:2011-01"
    " mit NA (Biegebemessung der Decken); DIN EN 1993-1-1, DIN EN 1995-1-1 mit NA (Unterzüge);"
    f" Lasten: {LOADS_NORM}"
)
LAMBDA = 0.8
"""Depth of the rectangular stress block over x, DIN EN 1992-1-1, 3.1.7(3), f_ck ≤ 50."""
RAY = 50.0
"""How far a span is searched for (m)."""


@dataclass
class Proof:
    pos: Pos
    ok: bool
    eta: float | None
    line: str
    """For the agent."""
    md: list[str] = field(default_factory=list[str])
    """For the Statische Berechnung."""


def core_material(layers: Layers, what: str) -> str:
    for x in layers.items:
        if x.core:
            return x.material
    raise ValueError(f"{what} has no core layer")


# ---------- formulas ----------


def bending(m: float, d: float, fcd: float, fyd: float) -> tuple[float, tuple[float, float] | None]:
    """A slab strip 1 m wide in bending, rectangular stress block: μ, and x/d and a_s (cm²/m),
    or None when the section cannot take the moment (2μ ≥ 1). m kNm/m, d m, f kN/m²."""
    mu = m / (d * d * fcd)
    if 2 * mu >= 1:
        return mu, None
    omega = 1 - math.sqrt(1 - 2 * mu)
    return mu, (omega / LAMBDA, omega * d * fcd / fyd * 1e4)


def slenderness(lam: float) -> float:
    """Φ1 = 0.85 − 0.0011·(h_ef/t)², DIN EN 1996-3, 4.2.2.3."""
    return 0.85 - 0.0011 * lam * lam


# ---------- spans ----------


def _axis(g: ArchGeo, s: Support) -> LineString:
    if s.kind == "wall":
        return LineString(g.walls[s.id].end_points())
    assert isinstance(s.shape, LineString)
    return s.shape


def _ray(axes: list[LineString], p: tuple[float, float], u: tuple[float, float]) -> float | None:
    """The distance from p along u to the nearest axis it meets."""
    ray = LineString([p, (p[0] + u[0] * RAY, p[1] + u[1] * RAY)])
    best: float | None = None
    o = SPoint(p)
    for a in axes:
        hit = ray.intersection(a)
        if hit.is_empty:
            continue
        dist = o.distance(hit)
        if dist > 1e-6 and (best is None or dist < best):
            best = dist
    return best


def span(g: ArchGeo, net: BaseGeometry, supports: list[Support], w: WallGeo) -> float:
    """l_f of the slab on a wall: on each side the slab lies, the shorter of its span across the
    wall and its span along it in the middle of that field; the longer of the sides."""
    others = [_axis(g, s) for s in supports if s.id != w.id]
    p = w.plan_point((w.s0 + w.s1) / 2, w.mid)
    out = 0.0
    for side in (1.0, -1.0):
        n = (w.n[0] * side, w.n[1] * side)
        probe = SPoint(p[0] + n[0] * (w.t / 2 + 0.1), p[1] + n[1] * (w.t / 2 + 0.1))
        if not net.contains(probe):
            continue
        across = _ray(others, p, n)
        if across is None:
            continue
        q = (p[0] + n[0] * across / 2, p[1] + n[1] * across / 2)
        a = _ray(others, q, w.u)
        b = _ray(others, q, (-w.u[0], -w.u[1]))
        along = a + b if a is not None and b is not None else math.inf
        out = max(out, min(across, along))
    return out


# ---------- the members ----------


class Design:
    def __init__(self, d: Derived, env: Env) -> None:
        self.d = d
        self.g = d.arch
        self.sg = getattr(d, "struct", None)
        self.env = env
        self.res: Result = calculate(d, env)
        self.f: Factors = self.res.factors
        self.pos = positions(d)
        self.no = {(p.kind, p.id): p.no for p in self.pos}
        self.proofs: list[Proof] = []

    def run(self) -> list[Proof]:
        for p in self.pos:
            fn = getattr(self, p.kind)
            self.proofs.append(fn(p))
        return self.proofs

    # ---------- roof ----------

    def roof(self, p: Pos) -> Proof:
        rl = next(r for r in self.res.roofs if r.id == p.id)
        parts: list[str] = []
        md: list[str] = []
        ok = True
        for e in rl.edges:
            to = ", ".join(e.to) or "nothing"
            up = uplift(self.res, e)
            anchor = " anchor" if up < 0 else ""
            parts.append(f"eaves {e.edge} {e.act.total / e.length:.1f} kN/m on {to}{anchor}")
            md.append(
                f"- Traufe {e.edge}: {de(e.act.g / e.length, 2)} kN/m aus g,"
                f" {de(e.act.s / e.length, 2)} aus s, {de(e.act.w / e.length, 2)} aus w auf"
                f" {to}; abhebend n_d = {de(up, 2)} kN/m"
                + (": Sparren an der Traufe verankern." if up < 0 else ".")
            )
            ok = ok and bool(e.to)
        if rl.flat:
            parts.append("flat on " + ", ".join(rl.flat))
        return Proof(p, ok, None, f"{p.no} {p.id} roof: " + "; ".join(parts), md)

    # ---------- rafters ----------

    def rafter(self, p: Pos) -> Proof:
        el = self.d.model[p.id]
        assert isinstance(el, Rafter)
        rg = self.g.roofs.get(el.roof.id)
        roof = self.d.model.get(el.roof.id)
        ridge = getattr(roof, "ridge", None)
        if rg is None or getattr(roof, "shape", "") != "gable" or ridge is None:
            return Proof(
                p,
                False,
                None,
                f"{p.no} {p.id} rafters: only the rafters of a gable roof are proved NOT OK",
                ["Nur Sparren eines Satteldachs werden nachgewiesen: nicht nachgewiesen."],
            )
        rl = next(r for r in self.res.roofs if r.id == rg.id)
        tim = self.env.table(TIMBER).find(material=el.material)
        if tim is None:
            raise ValueError(f"timber has no row for {el.material} ({el.id}): add it to the table")
        fr = rafter_frame(self.g, rg, rl, el, ridge, float(tim["e0mean"]) * 1000)
        if isinstance(fr, str):
            return Proof(p, False, None, f"{p.no} {p.id} rafters: {fr} NOT OK", [fr])
        f = self.f
        sk, qp = self.res.sk or 0.0, self.res.qp or 0.0
        pitch = rg.pitch
        mu = interp(self.env.table(SNOW), "mu1", pitch, el.id)
        cp = interp(self.env.table(WIND), "pressure", pitch, el.id)
        cs = min(0.0, interp(self.env.table(WIND), "suction", pitch, el.id))
        a = math.radians(pitch)
        sa, ca = math.sin(a), math.cos(a)
        g_m = rl.g_surface * el.e
        s_m = mu * sk * el.e * ca
        cases: dict[str, list[Push]] = {"g": [], "s": [], "w": []}
        for name, side in fr.sides.items():
            cases["g"].append((name, 0.0, -g_m))
            cases["s"].append((name, 0.0, -s_m))
            c = cp if side == "l" else cs
            nx = -sa if side == "l" else sa
            cases["w"].append((name, -c * qp * el.e * nx, -c * qp * el.e * ca))
        gg, gq = f.value("gamma-g"), f.value("gamma-q")
        combos = {
            "ULS-g": {"g": gg},
            "ULS-s": {"g": gg, "s": gq, "w": gq * f.psi("w")},
            "ULS-w": {"g": gg, "w": gq, "s": gq * f.psi("s")},
            "SLS": {"g": 1.0, "s": 1.0, "w": 1.0},
        }
        eff, rx = plane_frame(fr.nodes, fr.bars, ["FL", "FR"], cases, combos)
        kmod, gm = float(tim["kmod"]), float(tim["gamma"])

        def fd(col: str) -> float:
            return kmod * float(tim[col]) / gm * 1000

        e005 = float(tim["e005"])
        rows: list[list[str]] = []
        etas: list[float] = []
        n_def = f.limit("deflection")
        for group, names in fr.groups.items():
            bw, bh = fr.section[group]
            area, wsec = bw * bh, bw * bh * bh / 6
            length = max(_bar_length(fr, n) for n in names)
            i_r = min(bw, bh) / math.sqrt(12) if group == "collar" else bh / math.sqrt(12)
            kc = buckling(length / i_r, float(tim["fc0k"]), e005, float(tim["betac"]))
            uls = [eff[k][n] for k in combos if k != "SLS" for n in names]
            m_ed = max(x.moment for x in uls)
            n_c = max(x.compression for x in uls)
            n_t = max(x.tension for x in uls)
            v_ed = max(x.shear for x in uls)
            eta_n = (n_c / area) / (kc * fd("fc0k")) + (m_ed / wsec) / fd("fmk")
            eta_t = (n_t / area) / fd("ft0k") + (m_ed / wsec) / fd("fmk")
            eta_v = 1.5 * v_ed / (float(tim["kcr"]) * area) / fd("fvk")
            w = max(eff["SLS"][n].deflection for n in names)
            eta_w = w / (length / n_def) if group != "overhang" else w / (2 * length / n_def)
            eta = max(eta_n, eta_t, eta_v, eta_w)
            etas.append(eta)
            rows.append(
                [
                    GROUP_DE[group],
                    f"{de(bw * 100, 0)}/{de(bh * 100, 0)}",
                    de(length, 2),
                    de(m_ed, 2),
                    de(n_c, 1),
                    de(n_t, 1),
                    de(kc, 3),
                    de(max(eta_n, eta_t), 2),
                    de(eta_v, 2),
                    de(w * 1000, 1),
                    de(eta, 2),
                ]
            )
        eta = max(etas)
        ok = eta <= 1 + 1e-9
        h_foot = max(abs(rx[k]["FL"][0]) for k in combos if k != "SLS")
        kind = "Kehlbalkendach" if el.collar is not None else "Sparrendach"
        line = (
            f"{p.no} {p.id} rafters {el.material} {el.b * 100:g}/{el.h * 100:g} e {el.e:g}"
            + (f", collar at {el.collar:g}" if el.collar is not None else "")
            + f": η {eta:.2f}, thrust {h_foot / el.e:.1f} kN/m at the feet"
            f" {'ok' if ok else 'NOT OK'}"
        )
        md = [
            f"{kind}, Neigung {de(pitch, 1)}°, Sparren {el.material} b/h = {de(el.b * 100, 0)}/"
            f"{de(el.h * 100, 0)} cm im Abstand e = {de(el.e, 2)} m; Auflager auf"
            f" {', '.join(fr.walls)} im Abstand {de(fr.span, 2)} m"
            + (f", Kehlbalken {de(el.collar, 2)} m über den Fußpunkten" if el.collar else "")
            + f". Ebenes Stabwerk mit {solver_version()}, Firstgelenk, Fußpunkte gelenkig und"
            " horizontal gehalten.",
            f"Lasten je Sparren: g = {de(rl.g_surface, 2)} kN/m² · e entlang der Dachfläche,"
            f" s = μ1 · s_k · e = {de(mu, 2)} · {de(sk, 2)} · e im Grundriss, w = c_pe · q_p · e"
            f" senkrecht zur Dachfläche (Luv {de(cp, 2)}, Lee {de(cs, 2)}); Kombinationen mit"
            " Schnee oder Wind als Leiteinwirkung.",
            "",
            md_table(
                [
                    "Stab",
                    "b/h cm",
                    "l m",
                    "M_Ed kNm",
                    "N_c,Ed kN",
                    "N_t,Ed kN",
                    "k_c",
                    "η σ",
                    "η τ",
                    "w mm",
                    "η",
                ],
                rows,
                right=(2, 3, 4, 5, 6, 7, 8, 9, 10),
            ),
            "",
            f"f_d = k_mod · f_k / γ_M mit k_mod = {de(kmod, 2)}, γ_M = {de(gm, 2)}. Biegung mit"
            " Druck σ_c/(k_c · f_c,0,d) + σ_m/f_m,d ≤ 1, mit Zug σ_t/f_t,0,d + σ_m/f_m,d ≤ 1"
            " (DIN EN 1995-1-1, 6.2.3, 6.2.4, 6.3.2), Schub 1,5 · V/(k_cr · b · h) ≤ f_v,d,"
            f" Durchbiegung unter den charakteristischen Lasten ≤ l/{n_def:g} (Überstand"
            f" 2l/{n_def:g}).",
            f"Horizontalschub am Fußpunkt H = {de(h_foot, 1)} kN je Sparren,"
            f" {de(h_foot / el.e, 1)} kN/m entlang der Traufe: von der Decke aufzunehmen.",
        ]
        return Proof(p, ok, eta, line, md)

    # ---------- slab ----------

    def slab(self, p: Pos) -> Proof:
        f = self.f
        sl = self.g.slabs[p.id]
        load = next(s for s in self.res.slabs if s.id == p.id)
        sup = slab_supports(self.g, sl, self.sg)
        mat = core_material(sl.layers, sl.id)
        row = self.env.table(CONCRETE).find(material=mat)
        if row is None:
            raise ValueError(f"concrete has no row for {mat} ({sl.id}): add it to the table")
        fck, ecm = float(row["fck"]), float(row["ecm"])
        t = sl.layers.core
        dd = t - f.value("d1")
        fcd = f.value("alpha-cc") * fck / f.value("gamma-c") * 1000
        fyd = f.value("fyk") / f.value("gamma-s") * 1000
        xi_max = f.limit("xi")
        points = [(x, y, f.design(a)) for x, y, a in load.points]
        cases = {
            name: (_area_load(f, load, rooms), points) for name, rooms in _patterns(load).items()
        }
        each = solve(self.g, sl.net, sup, t, ecm * 1000, cases)
        m = Moments()
        for got in each.values():
            m.envelope(got)
            m.elements, m.held = got.elements, got.held
        # the minimum reinforcement, DIN EN 1992-1-1, 9.3.1.1 with 9.2.1.1 (9.1N); f_ctm by
        # Tabelle 3.1 for f_ck ≤ 50
        fctm = 0.30 * fck ** (2 / 3)
        as_min = max(f.value("rho-min-ft") * fctm / f.value("fyk"), f.value("rho-min")) * dd * 1e4
        rows: list[list[str]] = []
        ok = True
        worst = 0.0
        need: dict[str, float] = {}
        for key, name in (
            ("bottom_x", "unten x"),
            ("bottom_y", "unten y"),
            ("top_x", "oben x"),
            ("top_y", "oben y"),
        ):
            med = float(getattr(m, key))
            mu, got = bending(med, dd, fcd, fyd)
            if got is None:
                ok = False
                rows.append([name, de(med, 1), de(mu, 3), "–", "–", "nicht bemessbar"])
                need[key] = math.inf
                continue
            xi, a_s = got
            if key.startswith("bottom"):
                a_s = max(a_s, as_min)
            good = xi <= xi_max + 1e-9
            ok = ok and good
            worst = max(worst, xi / xi_max)
            need[key] = a_s
            at = m.at.get(key)
            where = f" bei x {de(at[0], 2)}, y {de(at[1], 2)}" if at else ""
            rows.append(
                [
                    name,
                    de(med, 1),
                    de(mu, 3),
                    de(xi, 3),
                    de(a_s, 2),
                    ("ok" if good else "zu groß") + where,
                ]
            )
        # shear without shear reinforcement, DIN EN 1992-1-1, 6.2.2 (6.2a, 6.2b), with ρ_l of
        # the minimum reinforcement (on the safe side)
        k = min(1 + math.sqrt(0.2 / dd), 2.0)
        rho_l = min(as_min / (dd * 1e4), 0.02)
        v_c = f.value("crdc") * k * (100 * rho_l * fck) ** (1 / 3)
        v_min = f.value("vmin") * k**1.5 * math.sqrt(fck)
        v_rd = max(v_c, v_min) * dd * 1000
        eta_v = m.shear / v_rd
        ok = ok and eta_v <= 1 + 1e-9
        # the slenderness instead of a deflection calculation, DIN EN 1992-1-1/NA, 7.4.2
        l_i = field_span(self.g, sl.net, sup)
        lim = min(f.limit("ld"), f.limit("ld-span") / l_i) if l_i > 0 else math.inf
        eta_l = (l_i / dd) / lim if l_i > 0 else 0.0
        ok = ok and eta_l <= 1 + 1e-9
        eta = max(worst, eta_v, eta_l)
        line = (
            f"{p.no} {p.id} slab h {t:.2f}: a_s bottom x {need['bottom_x']:.2f} y"
            f" {need['bottom_y']:.2f}, top x {need['top_x']:.2f} y {need['top_y']:.2f} cm²/m,"
            f" x/d {worst * xi_max:.2f} ≤ {xi_max:g}, v_Ed {m.shear:.1f}/v_Rd,c {v_rd:.1f} kN/m,"
            f" l/d {l_i / dd:.1f} ≤ {lim:.1f} {'ok' if ok else 'NOT OK'}"
        )
        md = [
            *_slab_md(sl.id, t, dd, mat, fck, fcd, fyd, m, sup),
            f"Lastfälle: {', '.join(PATTERN_DE.get(k, k) for k in cases)}; je Wert der"
            " ungünstigste.",
            "",
            md_table(
                ["Bewehrung", "m_Ed kNm/m", "μ_Ed", "x/d", "erf. a_s cm²/m", ""],
                rows,
                right=(1, 2, 3, 4),
            ),
            "",
            f"Mindestbewehrung unten: a_s,min = max({de(f.value('rho-min-ft'), 2)} · f_ctm / f_yk,"
            f" {de(f.value('rho-min'), 4)}) · b · d = {de(as_min, 2)} cm²/m (f_ctm ="
            f" {de(fctm, 2)} N/mm²).",
            f"Querkraft ohne Querkraftbewehrung: v_Ed = {de(m.shear, 1)} kN/m"
            + (f" bei x {de(m.at_shear[0], 2)}, y {de(m.at_shear[1], 2)}" if m.at_shear else "")
            + f"; k = {de(k, 3)}, ρ_l = {de(rho_l, 4)}, v_Rd,c = max({de(v_c, 3)}, v_min ="
            f" {de(v_min, 3)}) N/mm² · d = {de(v_rd, 1)} kN/m; η = {de(eta_v, 2)}.",
            f"Biegeschlankheit: größte kürzere Stützweite eines Feldes l = {de(l_i, 2)} m,"
            f" l/d = {de(l_i / dd, 1)} ≤ min({de(f.limit('ld'), 0)},"
            f" {de(f.limit('ld-span'), 0)}/l) = {de(lim, 1)}; η = {de(eta_l, 2)}.",
        ]
        return Proof(p, ok, eta, line, md)

    # ---------- beam ----------

    def beam(self, p: Pos) -> Proof:
        f = self.f
        bl = self.res.beams[p.id]
        if bl.id in self.res.unsupported:
            return Proof(
                p,
                False,
                None,
                f"{p.no} {p.id} beam: rests on fewer than two walls NOT OK",
                ["Liegt auf weniger als zwei Wänden auf: nicht nachgewiesen."],
            )
        sec = self.env.table(SECTION).find(name=bl.section)
        assert sec is not None
        mat = self.env.table(BEAM_MATERIAL).find(material=str(sec["material"]))
        if mat is None:
            raise ValueError(f"beam-material has no row for {sec['material']} ({bl.id})")
        e = float(mat["e"]) * 1000
        ei = e * float(sec["i"]) * 1e-8
        kmod, gm = float(mat["kmod"]), float(mat["gamma"])
        m_rd = float(sec["w"]) * 1e-6 * kmod * float(mat["fk"]) * 1000 / gm
        v_rd = float(sec["av"]) * 1e-4 * kmod * float(mat["fvk"]) * 1000 / gm
        cases = {k: c for k, c in bl.cases.items() if not c.empty()}
        combos = _combos(f, cases)
        combos["SLS"] = dict.fromkeys(cases, 1.0)
        eff = beam(bl.length, [s for _, s in bl.bearings], ei, cases, combos)
        uls = [v for k, v in eff.items() if k != "SLS"]
        m_ed = max(max(x.sag, x.hog) for x in uls)
        v_ed = max(x.shear for x in uls)
        w = eff["SLS"].deflection
        spans = [b - a for (_, a), (_, b) in zip(bl.bearings, bl.bearings[1:], strict=False)]
        ends = [bl.bearings[0][1], bl.length - bl.bearings[-1][1]]
        ref = max([*spans, *(2 * x for x in ends)])
        n = f.limit("deflection")
        w_lim = ref / n
        etas = [m_ed / m_rd, v_ed / v_rd, w / w_lim]
        eta = max(etas)
        ok = eta <= 1 + 1e-9
        line = (
            f"{p.no} {p.id} beam {bl.section}: M_Ed {m_ed:.1f}/M_Rd {m_rd:.1f} kNm, V_Ed"
            f" {v_ed:.1f}/V_Rd {v_rd:.1f} kN, w {w * 1000:.1f}/{w_lim * 1000:.1f} mm, η {eta:.2f}"
            f" {'ok' if ok else 'NOT OK'}"
        )
        md = [
            f"Querschnitt {bl.section} ({sec['material']}), Länge {de(bl.length, 2)} m, Auflager "
            + ", ".join(f"{k} bei {de(s, 2)} m" for k, s in bl.bearings)
            + f"; Durchlaufträger, berechnet mit {solver_version()}.",
            "",
            md_table(
                ["Nachweis", "Einwirkung", "Widerstand", "η"],
                [
                    [
                        "Biegung",
                        f"M_Ed = {de(m_ed, 1)} kNm",
                        f"M_Rd = {de(m_rd, 1)} kNm",
                        de(etas[0], 2),
                    ],
                    [
                        "Querkraft",
                        f"V_Ed = {de(v_ed, 1)} kN",
                        f"V_Rd = {de(v_rd, 1)} kN",
                        de(etas[1], 2),
                    ],
                    [
                        "Durchbiegung",
                        f"w = {de(w * 1000, 1)} mm",
                        f"L/{n:g} = {de(w_lim * 1000, 1)} mm",
                        de(etas[2], 2),
                    ],
                ],
                right=(3,),
            ),
        ]
        return Proof(p, ok, eta, line, md)

    # ---------- wall ----------

    def wall(self, p: Pos) -> Proof:
        f = self.f
        g = self.g
        w = g.walls[p.id]
        wl = self.res.walls[p.id]
        mat = core_material(w.layers, w.id)
        row = self.env.table(MASONRY).find(material=mat)
        if row is None:
            raise ValueError(f"masonry has no row for {mat} ({w.id}): add it to the table")
        fk = float(row["fk"])
        fd = f.value("zeta") * fk / f.value("gamma-m") * 1000
        t = w.layers.core
        holes = _wall_openings(g, w.id)
        net = w.length - sum(o.width for o in holes)
        if net <= 0:
            raise ValueError(f"{w.id} has no masonry left between its openings")
        n_ed = f.design(wl.base) / net
        prof = wall_profile(w)
        h = max(z for _, z in prof) if prof else 0.0
        above = g.levels[w.level].above
        sl = g.slab_on(above) if above is not None else None
        sup = slab_supports(g, sl, self.sg) if sl is not None else []
        held = any(s.id == w.id for s in sup)
        rho = f.value("rho2") if held else 1.0
        h_ef = rho * h
        lam = h_ef / t
        phi1 = slenderness(lam)
        phi, why = phi1, "Φ1 (Schlankheit)"
        l_f = span(g, sl.net, sup, w) if sl is not None and held else 0.0
        notes: list[str] = []
        ok = True
        if held and w.ext is not None and l_f > 0:
            rows = sorted(self.env.table(MASONRY_END).rows, key=lambda r: float(r["upto"]))
            r2 = next((r for r in rows if l_f <= float(r["upto"]) + 1e-9), None)
            if r2 is None:
                ok = False
                notes.append(f"Stützweite {de(l_f, 2)} m über der Tabelle masonry-end")
            elif float(r2["phi"]) < phi:
                phi, why = float(r2["phi"]), f"Φ2 (Endauflager, l_f = {de(l_f, 2)} m)"
        if phi <= 0:
            ok = False
            notes.append("Φ ≤ 0: zu schlank")
            phi = 1e-9
        n_rd = phi * fd * t
        eta = n_ed / n_rd
        ok = ok and eta <= 1 + 1e-9
        # the conditions of the simplified method
        cond = self._conditions(w, h, l_f, sl.level if sl is not None else None)
        bad = [c for c, good in cond if not good]
        ok = ok and not bad
        line = (
            f"{p.no} {p.id} wall t {t:.3f}: n_Ed {n_ed:.1f}/n_Rd {n_rd:.1f} kN/m, Φ {phi:.2f},"
            f" η {eta:.2f} {'ok' if ok else 'NOT OK'}"
            + (f" (outside the method: {', '.join(bad)})" if bad else "")
        )
        md = [
            f"{mat}, f_k = {de(fk, 1)} N/mm², f_d = ζ·f_k/γ_M = {de(fd / 1000, 2)} N/mm²; t ="
            f" {de(t, 3)} m; lichte Höhe h = {de(h, 2)} m, h_ef = {de(rho, 2)} · h ="
            f" {de(h_ef, 2)} m, h_ef/t = {de(lam, 1)}; Φ1 = 0,85 − 0,0011 · ({de(lam, 1)})² ="
            f" {de(phi1, 3)}; maßgebend {why}: Φ = {de(phi, 3)}.",
            f"Länge {de(w.length, 2)} m, ohne Öffnungen {de(net, 2)} m; N_Ed ="
            f" {de(f.design(wl.base), 1)} kN, n_Ed = {de(n_ed, 1)} kN/m ≤ n_Rd = Φ·f_d·t ="
            f" {de(n_rd, 1)} kN/m, η = {de(eta, 2)}.",
        ]
        if cond:
            md.append(
                "Anwendungsgrenzen: "
                + ", ".join(f"{c} {'eingehalten' if good else 'überschritten'}" for c, good in cond)
                + "."
            )
        md += notes
        return Proof(p, ok, eta, line, md)

    def _conditions(
        self, w: WallGeo, h: float, l_f: float, slab_level: str | None
    ) -> list[tuple[str, bool]]:
        f = self.f
        out = [("lichte Höhe", h <= f.limit("clear-height") + 1e-9)]
        if l_f > 0:
            out.append(("Stützweite", l_f <= f.limit("span") + 1e-9))
        if slab_level is not None:
            q = max(
                (r.q for s in self.res.slabs if s.level == slab_level for r in s.room_loads),
                default=0.0,
            )
            out.append(("Nutzlast", q <= f.limit("qk") + 1e-9))
        out.append(("Gebäudehöhe", _height(self.d) <= f.limit("building-height") + 1e-9))
        return out

    # ---------- lintel ----------

    def lintel(self, p: Pos) -> Proof:
        g = self.g
        o = _opening(g, p.id)
        w = g.walls[o.host]
        wl = self.res.walls[o.host]
        top = w.top_at(o.mid)
        lv = g.levels[w.level]
        h_above = max(0.0, (top if top is not None else lv.z + o.top) - (lv.z + o.top))
        per_m = wl.top.times(1 / w.length)
        per_m.g += wl.gk * h_above
        q_d = self.f.design(per_m)
        t = w.layers.core
        rows = [r for r in self.env.table(LINTEL).rows if abs(float(r["t"]) - t) < 1e-3]
        choice: tuple[str, float] | None = None
        types: list[str] = []
        for r in rows:
            if str(r["type"]) not in types:
                types.append(str(r["type"]))
        for name in types:
            fits = sorted(
                (r for r in rows if str(r["type"]) == name and float(r["span"]) >= o.width - 1e-9),
                key=lambda r: float(r["span"]),
            )
            if fits and float(fits[0]["qrd"]) >= q_d - 1e-9:
                choice = (name, float(fits[0]["qrd"]))
                break
        ok = choice is not None
        eta = q_d / choice[1] if choice else None
        got = (
            f"{choice[0]} (q_Rd {choice[1]:.1f}) η {eta:.2f} ok"
            if choice and eta
            else "none in the lintel table NOT OK"
        )
        line = f"{p.no} {p.id} lintel {o.width:.2f} m in {w.id}: q_d {q_d:.1f} kN/m → {got}"
        md = [
            f"Lichte Weite {de(o.width, 2)} m in {w.id} (t = {de(t, 3)} m). Last je m: aus der Wand"
            f" darüber G {de(wl.top.g / w.length, 2)}, Q {de(wl.top.q / w.length, 2)}, S"
            f" {de(wl.top.s / w.length, 2)}, W {de(wl.top.w / w.length, 2)} kN/m; Mauerwerk über"
            f" der Öffnung {de(wl.gk, 2)} kN/m² · {de(h_above, 2)} m; q_d = {de(q_d, 1)} kN/m.",
            (
                f"Gewählt: {choice[0]}, q_Rd = {de(choice[1], 1)} kN/m, η = {de(eta, 2)}."
                if choice and eta
                else "Kein Sturz der Tabelle trägt diese Last über diese Weite."
            ),
        ]
        return Proof(p, ok, eta, line, md)

    # ---------- column ----------

    def column(self, p: Pos) -> Proof:
        cl = self.res.columns[p.id]
        if p.id in self.res.unsupported:
            return Proof(
                p,
                False,
                None,
                f"{p.no} {p.id} column: stands on nothing NOT OK",
                ["Steht auf keinem Auflager: nicht nachgewiesen."],
            )
        sec = self.env.table(COLUMN_SECTION).find(name=cl.section)
        assert sec is not None
        mat = self.env.table(BEAM_MATERIAL).find(material=str(sec["material"]))
        if mat is None:
            raise ValueError(f"beam-material has no row for {sec['material']} ({cl.id})")
        area = float(sec["a"]) * 1e-4
        radius = math.sqrt(float(sec["imin"]) * 1e-8 / area)
        fk, e = float(mat["fk"]), float(mat["e"])
        chi, rel = buckling_chi(cl.height / radius, fk, e, float(sec["alpha"]))
        n_rd = chi * area * float(mat["kmod"]) * fk / float(mat["gamma"]) * 1000
        n_ed = self.f.design(cl.base)
        eta = n_ed / n_rd
        ok = eta <= 1 + 1e-9
        line = (
            f"{p.no} {p.id} column {cl.section} {cl.height:.2f} m: N_Ed {n_ed:.1f}/N_b,Rd"
            f" {n_rd:.1f} kN, χ {chi:.3f}, η {eta:.2f} {'ok' if ok else 'NOT OK'}"
        )
        md = [
            f"Querschnitt {cl.section} ({sec['material']}), A = {de(area * 1e4, 1)} cm², i ="
            f" {de(radius * 100, 2)} cm, Knicklänge = Stützenlänge {de(cl.height, 2)} m (beidseits"
            f" gelenkig); λ̄ = {de(rel, 3)}, α = {de(float(sec['alpha']), 2)}, χ = {de(chi, 3)}"
            " (DIN EN 1993-1-1, 6.3.1.2).",
            f"N_Ed = {de(n_ed, 1)} kN (aus G {de(cl.base.g, 1)}, Q {de(cl.base.q, 1)}, S"
            f" {de(cl.base.s, 1)}, W {de(cl.base.w, 1)} kN) ≤ N_b,Rd = χ · A · f_k / γ_M ="
            f" {de(n_rd, 1)} kN, η = {de(eta, 2)}. Steht auf {cl.to}.",
        ]
        return Proof(p, ok, eta, line, md)

    def pad(self, p: Pos) -> Proof:
        cl = self.res.columns[p.id]
        nd = self.f.design(cl.base)
        soil = self.res.soil
        a = math.sqrt(nd / soil) if soil else None
        line = f"{p.no} {p.id} pad: N_d {nd:.1f} kN" + (f", a ≥ {a:.2f} m" if a else "")
        md = [
            f"Unter {p.id}: N_d = {de(nd, 1)} kN"
            + (
                f"; mit σ_R,d = {de(soil, 0)} kN/m²: a ≥ √(N_d/σ_R,d) = {de(a, 2)} m (quadratisch)."
                if soil and a
                else "; die Größe folgt aus dem Bodengutachten (σ_R,d nicht angegeben)."
            )
        ]
        return Proof(p, True, None, line, md)

    # ---------- bracing ----------

    def bracing(self, p: Pos) -> Proof:
        if self.res.qp is None:
            return Proof(
                p,
                False,
                None,
                f"{p.no} bracing {p.id}: needs the wind pressure qp= NOT OK",
                ["Ohne Böengeschwindigkeitsdruck q_p nicht nachgewiesen."],
            )
        dirs = bracing(self.d, self.res, self.env, p.id)
        parts: list[str] = []
        md: list[str] = []
        ok = True
        eta = 0.0
        roofed = bool(self.g.roofs_on(p.id))
        for dr in dirs:
            piers = dr.piers
            if not piers and roofed:
                parts.append(f"wind in {dr.axis}: through the roof's bracing to the storey below")
                md.append(
                    f"Wind in {dr.axis}-Richtung: keine Wand in dieser Richtung; die Last geht über"
                    " die Aussteifung der Dachfläche (Windrispen) in die Decke darunter und ist"
                    " in den Geschossen darunter enthalten. Die Windrispen sind nicht nachgewiesen."
                )
                continue
            if not piers:
                ok = False
                parts.append(f"wind in {dr.axis}: no wall along it NOT OK")
                md.append(f"Wind in {dr.axis}-Richtung: keine tragende Wand in dieser Richtung.")
                continue
            worst = max(piers, key=lambda x: (not x.ok, x.eta))
            ok = ok and all(x.ok for x in piers)
            eta = max([eta, *(x.eta for x in piers if x.ok)])
            bad = [f"{x.wall} ({x.why})" for x in piers if not x.ok]
            parts.append(
                f"wind in {dr.axis}: V {dr.v:.1f} kN, M {dr.m:.1f} kNm on {len(piers)} piers,"
                f" worst {worst.wall} η {worst.eta:.2f}"
                + (f", NOT OK: {', '.join(bad)}" if bad else "")
            )
            md += [
                f"**Wind in {dr.axis}-Richtung:** h/d = {de(dr.hd, 2)}, c_pe,D = {de(dr.cd, 2)},"
                f" c_pe,E = {de(dr.ce, 2)}; Lasten der Geschosse "
                + ", ".join(f"{lv} {de(fz, 1)} kN in {de(z, 2)} m" for lv, fz, z in dr.forces)
                + f"; im Geschoss V = {de(dr.v, 1)} kN, M = {de(dr.m, 1)} kNm.",
                "",
                md_table(
                    [
                        "Wand",
                        "Pfeiler m",
                        "Anteil",
                        "V kN",
                        "M kNm",
                        "N_d kN",
                        "e m",
                        "l_c m",
                        "v_Ed N/mm²",
                        "f_vd N/mm²",
                        "",
                    ],
                    [
                        [
                            x.wall,
                            f"{de(x.lo, 2)}–{de(x.hi, 2)}",
                            de(x.share, 3),
                            de(x.v, 1),
                            de(x.m, 1),
                            de(x.n, 1),
                            de(x.e, 2) if x.e != float("inf") else "∞",
                            de(x.lc, 2) if x.lc > 0 else "–",
                            de(x.v_ed, 3),
                            de(x.f_vd, 3),
                            "ok" if x.ok else f"**{x.why}**",
                        ]
                        for x in piers
                    ],
                    right=(2, 3, 4, 5, 6, 7, 8, 9),
                ),
                "",
            ]
        line = f"{p.no} bracing {p.id}: " + "; ".join(parts) + (" ok" if ok else "")
        md.append(
            "Windlast q_p · (c_pe,D − c_pe,E) auf die Fassade je Geschoss, an der Oberkante;"
            " Verteilung auf die Pfeiler der tragenden Wände in Windrichtung nach t · l³ (Decken"
            " als starre Scheiben, ohne Torsion); je Pfeiler N_d = γ_G,inf · G, Ausmitte e = M/N,"
            " überdrückte Länge l_c = 3 · (l/2 − e) ≥ l/2, Schub v_Ed = V/(t · l_c) ≤ f_vd ="
            " min(f_vk0 + 0,4 · σ_d, f_vlt)/γ_M (DIN EN 1996-1-1, 6.2, 3.6.2)."
        )
        return Proof(p, ok, eta or None, line, md)

    # ---------- footing ----------

    def footing(self, p: Pos) -> Proof:
        wl = self.res.walls[p.id]
        b = wl.base
        nd = self.res.ed(b) / wl.length
        line = f"{p.no} " + footing_line(self.res, wl)
        md = [
            f"Unter {p.id}: G {de(b.g, 1)}, Q {de(b.q, 1)}, S {de(b.s, 1)}, W {de(b.w, 1)} kN auf"
            f" {de(wl.length, 2)} m; n_k = {de(b.total / wl.length, 1)} kN/m, n_d ="
            f" {de(nd, 1)} kN/m"
            + (
                f"; mit σ_R,d = {de(self.res.soil, 0)} kN/m²: b ≥ {de(nd / self.res.soil, 2)} m."
                if self.res.soil
                else "; die Breite folgt aus dem Bodengutachten (σ_R,d nicht angegeben)."
            )
        ]
        return Proof(p, True, None, line, md)


GROUP_DE = {
    "foot": "Sparren Fuß – Kehlbalken",
    "top": "Sparren Kehlbalken – First",
    "rafter": "Sparren Fuß – First",
    "overhang": "Sparren Überstand",
    "collar": "Kehlbalken",
}


@dataclass
class RafterFrame:
    nodes: dict[str, tuple[float, float]]
    bars: list[Bar]
    sides: dict[str, str]
    """The roof plane of each rafter bar: l (windward) or r."""
    groups: dict[str, list[str]]
    section: dict[str, tuple[float, float]]
    walls: list[str]
    span: float


def rafter_frame(
    g: ArchGeo, rg: RoofGeo, rl: RoofLoad, el: Rafter, ridge: str, e: float
) -> RafterFrame | str:
    """A pair of rafters across a gable roof as a plane frame: from the eaves' tip over the
    bearing on the eaves wall to the ridge (a hinge), and the collar beam between them."""
    lo_edge, hi_edge = ("s", "n") if ridge == "x" else ("w", "e")
    edges = {e.edge: e for e in rl.edges}
    if lo_edge not in edges or hi_edge not in edges or not edges[lo_edge].to:
        return "the roof does not rest on walls under both eaves"
    if not edges[hi_edge].to:
        return "the roof does not rest on walls under both eaves"

    def axis(edge: str) -> float:
        to = edges[edge].to
        return sum(g.walls[k].mid * f for k, f in to.items())

    c_l, c_r = axis(lo_edge), axis(hi_edge)
    ox0, oy0, ox1, oy1 = rg.over.bounds
    if ridge == "x":
        along = (rg.x0 + rg.x1) / 2
        o_lo, o_hi, c_ridge = oy0, oy1, (rg.y0 + rg.y1) / 2

        def z(c: float) -> float:
            return rg.underside(along, c)
    else:
        along = (rg.y0 + rg.y1) / 2
        o_lo, o_hi, c_ridge = ox0, ox1, (rg.x0 + rg.x1) / 2

        def z(c: float) -> float:
            return rg.underside(c, along)

    z0 = z(c_l)
    nodes = {
        "TL": (o_lo - c_l, z(o_lo) - z0),
        "FL": (0.0, 0.0),
        "R": (c_ridge - c_l, z(c_ridge) - z0),
        "FR": (c_r - c_l, z(c_r) - z0),
        "TR": (o_hi - c_l, z(o_hi) - z0),
    }
    walls = [*edges[lo_edge].to, *edges[hi_edge].to]
    return _rafter_bars(nodes, el, rg.slope, walls, c_r - c_l, e)


def _rafter_bars(
    nodes: dict[str, tuple[float, float]],
    el: Rafter,
    slope: float,
    walls: list[str],
    span: float,
    e: float,
) -> RafterFrame | str:
    """The bars of the frame; e: the timber's E_0,mean, kN/m²."""
    a, ih = el.b * el.h, el.b * el.h**3 / 12
    sides: dict[str, str] = {}
    groups: dict[str, list[str]] = {"overhang": []}
    bars: list[Bar] = []
    for side, tip, foot in (("l", "TL", "FL"), ("r", "TR", "FR")):
        if abs(nodes[tip][0] - nodes[foot][0]) > 1e-6:
            name = f"O{side}"
            bars.append(Bar(name, tip, foot, a, ih, e))
            sides[name] = side
            groups["overhang"].append(name)
    if not groups["overhang"]:
        del groups["overhang"]
    if el.collar is None:
        bars += [Bar("Rl", "FL", "R", a, ih, e, hinge_j=True), Bar("Rr", "FR", "R", a, ih, e)]
        sides.update({"Rl": "l", "Rr": "r"})
        groups["rafter"] = ["Rl", "Rr"]
        section = dict.fromkeys(groups, (el.b, el.h))
    else:
        if el.collar >= nodes["R"][1] - 0.1:
            return f"the collar at {el.collar:g} m is not below the ridge"
        u = el.collar / slope
        nodes["KL"] = (u, el.collar)
        nodes["KR"] = (nodes["FR"][0] - u, nodes["FR"][1] + el.collar)
        cb, ch = el.cb or el.b, el.ch or el.h
        bars += [
            Bar("Fl", "FL", "KL", a, ih, e),
            Bar("Tl", "KL", "R", a, ih, e, hinge_j=True),
            Bar("Fr", "FR", "KR", a, ih, e),
            Bar("Tr", "KR", "R", a, ih, e),
            Bar("K", "KL", "KR", cb * ch, cb * ch**3 / 12, e, hinge_i=True, hinge_j=True),
        ]
        sides.update({"Fl": "l", "Tl": "l", "Fr": "r", "Tr": "r"})
        groups.update({"foot": ["Fl", "Fr"], "top": ["Tl", "Tr"], "collar": ["K"]})
        section = dict.fromkeys(groups, (el.b, el.h))
        section["collar"] = (cb, ch)
    used = {k for b in bars for k in (b.i, b.j)}
    nodes = {k: v for k, v in nodes.items() if k in used}
    return RafterFrame(nodes, bars, sides, groups, section, walls, span)


def _bar_length(fr: RafterFrame, name: str) -> float:
    b = next(x for x in fr.bars if x.name == name)
    (xi, yi), (xj, yj) = fr.nodes[b.i], fr.nodes[b.j]
    return math.hypot(xj - xi, yj - yi)


def buckling_chi(lam: float, fk: float, e: float, alpha: float) -> tuple[float, float]:
    """χ and λ̄ of a member in compression with slenderness λ = l / i and the imperfection
    factor α of its buckling curve, DIN EN 1993-1-1, 6.3.1.2."""
    rel = lam / math.pi * math.sqrt(fk / e)
    phi = 0.5 * (1 + alpha * (rel - 0.2) + rel * rel)
    return min(1.0, 1 / (phi + math.sqrt(phi * phi - rel * rel))), rel


def buckling(lam: float, fc0k: float, e005: float, beta_c: float) -> float:
    """k_c of a member in compression with slenderness λ = l / i, DIN EN 1995-1-1, 6.3.2."""
    rel = lam / math.pi * math.sqrt(fc0k / e005)
    if rel <= 0.3:
        return 1.0
    k = 0.5 * (1 + beta_c * (rel - 0.3) + rel * rel)
    return 1 / (k + math.sqrt(k * k - rel * rel))


def _combos(f: Factors, cases: dict[str, Case]) -> dict[str, dict[str, float]]:
    """The design combinations: γ_G·G with each variable action leading."""
    var = [k for k in ("q", "s", "w") if k in cases]
    gg, gq = f.value("gamma-g"), f.value("gamma-q")
    if not var:
        return {"ULS": {"g": gg}}
    out: dict[str, dict[str, float]] = {}
    for lead in var:
        c = {"g": gg, lead: gq}
        for k in var:
            if k != lead:
                c[k] = gq * f.psi(k)
        out[f"ULS-{lead}"] = c
    return out


PATTERN_DE = {
    "all": "Nutzlast überall",
    "odd": "Nutzlast feldweise (Räume der einen Gruppe)",
    "even": "Nutzlast feldweise (Räume der anderen Gruppe)",
}


def _patterns(s: SlabLoad) -> dict[str, set[str] | None]:
    """The load cases of a slab: the imposed load on every room, and on alternate rooms (two
    groups of rooms, neighbours across a wall in different groups as far as two groups allow;
    rooms that meet at a corner are not neighbours)."""
    rooms = sorted(s.room_loads, key=lambda r: natural(r.id))
    group: dict[str, int] = {}
    for r in rooms:
        near = {
            group[o.id]
            for o in rooms
            if o.id in group and r.poly.buffer(0.6).intersection(o.poly).area > 0.1
        }
        group[r.id] = 0 if 0 not in near else (1 if 1 not in near else 0)
    odd = {k for k, v in group.items() if v == 0}
    even = {k for k, v in group.items() if v == 1}
    out: dict[str, set[str] | None] = {"all": None}
    if odd and even:
        out["odd"], out["even"] = odd, even
    return out


def _area_load(
    f: Factors, s: SlabLoad, loaded: set[str] | None = None
) -> Callable[[float, float], float]:
    """γ_G·g everywhere and γ_Q·q on the rooms loaded (all if None)."""
    gg, gq = f.value("gamma-g"), f.value("gamma-q")
    rooms = s.room_loads

    def load(x: float, y: float) -> float:
        p = SPoint(x, y)
        q = gg * s.g_slab
        for r in rooms:
            if r.poly.contains(p):
                on = loaded is None or r.id in loaded
                return q + gg * r.g + (gq * (r.q + s.partition) if on else 0.0)
        return q

    return load


def field_span(g: ArchGeo, net: BaseGeometry, supports: list[Support]) -> float:
    """The largest of the fields' shorter spans: from points 0.5 m apart in the fields (not over
    a wall that carries the slab), the distance between the support axes on either side, across
    x and across y, the shorter of the two."""
    axes = [_axis(g, s) for s in supports]
    over = shapely.union_all([s.shape for s in supports if s.kind == "wall"])  # pyright: ignore[reportUnknownMemberType]
    net = net.difference(over)
    x0, y0, x1, y1 = net.bounds
    out = 0.0
    x = x0 + 0.25
    while x < x1:
        y = y0 + 0.25
        while y < y1:
            if net.contains(SPoint(x, y)):
                spans: list[float] = []
                for u in ((1.0, 0.0), (0.0, 1.0)):
                    a = _ray(axes, (x, y), u)
                    b = _ray(axes, (x, y), (-u[0], -u[1]))
                    if a is not None and b is not None:
                        spans.append(a + b)
                if spans:
                    out = max(out, min(spans))
            y += 0.5
        x += 0.5
    return out


def _wall_openings(g: ArchGeo, wall: str) -> list[OpeningGeo]:
    """Doors, windows and holes through the wall: the masonry the wall has not."""
    out = [o for o in g.openings.values() if o.host == wall and o.kind in ("door", "win")]
    out += [
        h.wall
        for h in g.holes.values()
        if h.wall is not None and h.host == wall and h.wall.face is None
    ]
    return out


def _opening(g: ArchGeo, key: str) -> OpeningGeo:
    if key in g.openings:
        return g.openings[key]
    h = g.holes[key]
    assert h.wall is not None
    return h.wall


def _height(d: Derived) -> float:
    """From the terrain to the highest point of the building."""
    g = d.arch
    proj = d.model.of_kind("project")
    ground = float(getattr(proj[0], "ground", None) or 0.0) if proj else 0.0
    tops = [r.ridge_z for r in g.roofs.values()]
    order = g.level_order()
    if order:
        tops.append(g.levels[order[-1]].z)
    return max(tops, default=0.0) - ground


def _slab_md(
    key: str,
    t: float,
    dd: float,
    mat: str,
    fck: float,
    fcd: float,
    fyd: float,
    m: Moments,
    sup: list[Support],
) -> list[str]:
    return [
        f"{mat}, f_ck = {de(fck, 0)} N/mm², f_cd = {de(fcd / 1000, 2)} N/mm², f_yd ="
        f" {de(fyd / 1000, 1)} N/mm²; h = {de(t, 3)} m, d = {de(dd, 3)} m. Plattenberechnung mit"
        f" {solver_version()}: {m.elements} Elemente bis {de(MESH, 2)} m, gelagert auf"
        f" {', '.join(s.id for s in sup)} ({m.held} Knoten); Bemessungsmomente m ± |m_xy| in den"
        " Elementmitten.",
    ]


# ---------- the calculator ----------


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("struct takes the whole building: leave out the scope")
    des = Design(d, env)
    proofs = des.run()
    res = des.res
    f = des.f
    head = f"γ_G {f.value('gamma-g'):g}, γ_Q {f.value('gamma-q'):g}"
    if res.roofs:
        head += f", s_k {res.sk:g}, q_p {res.qp:g} kN/m²"
    if res.soil:
        head += f", σ_R,d {res.soil:g} kN/m²"
    lines = [head, *(pr.line for pr in proofs)]
    lost = [*res.floating, *res.unsupported]
    if lost:
        lines.append("not carried: " + ", ".join(lost) + " (see uea calc loads)")
    ok = all(pr.ok for pr in proofs) and not lost
    data = {
        "positions": {
            pr.pos.no: {
                "kind": pr.pos.kind,
                "id": pr.pos.id,
                "sheet": pr.pos.sheet,
                "ok": pr.ok,
                "eta": None if pr.eta is None else round(pr.eta, 3),
            }
            for pr in proofs
        },
        "holes": [h for h, _ in _holes(des)],
    }
    return Output(
        lines=lines,
        report=report(d, des),
        data=data,
        inputs={"soil": res.soil, "sk": res.sk, "qp": res.qp, "mesh": MESH},
        ok=ok,
    )


def _holes(des: Design) -> list[tuple[str, str]]:
    """The holes in load-bearing members and how the calculation takes them."""
    g = des.g
    out: list[tuple[str, str]] = []
    for h in sorted(g.holes.values(), key=lambda h: natural(h.id)):
        if h.status == "demolish":
            continue
        if h.wall is not None:
            w = g.walls.get(h.host)
            if w is None or not w.lb:
                continue
            no = des.no.get(("wall", w.id), "")
            if h.chase:
                how = f"Schlitz in {w.id} (Pos. {no}): nicht nachgewiesen, Tiefe prüfen"
            elif h.round:
                how = f"Kernbohrung in {w.id} (Pos. {no}): Wandlänge um ihren Durchmesser gemindert"
            else:
                how = (
                    f"Durchbruch in {w.id} (Pos. {no}): Wandlänge gemindert, Sturz Pos."
                    f" {des.no.get(('lintel', h.id), '')}"
                )
            out.append((h.id, how))
            continue
        sl = g.slabs.get(h.host)
        if sl is None:
            continue
        x0, y0, x1, y1 = h.poly.bounds
        out.append(
            (
                h.id,
                f"in {sl.id} (Pos. {des.no.get(('slab', sl.id), '')}),"
                f" {de((x1 - x0) * 100, 0)} × {de((y1 - y0) * 100, 0)} cm: im Plattenmodell"
                " ausgespart; Zulagebewehrung an den Rändern nach Bewehrungsplan",
            )
        )
    return out


def report(d: Derived, des: Design) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    res = des.res
    out = [
        f"# Statische Berechnung: {title}",
        "",
        "Nachweise der Positionen des Positionsplans (`uea export pdf struct:<Geschoss>`) mit den"
        f" Lasten nach `loads` {LOADS_VERSION}. Rechenprogramm UEA, Platten und Durchlaufträger"
        f" mit {solver_version()}. Normtabellen und Festigkeiten aus den Tabellen des Büros (siehe"
        " Kopf). Nicht geprüft und nicht unterzeichnet.",
        "",
        "## Positionsliste",
        "",
        md_table(
            ["Pos.", "Bauteil", "Geschoss", "Ausnutzung", ""],
            [
                [
                    pr.pos.no,
                    pr.pos.title,
                    pr.pos.sheet,
                    de(pr.eta, 2) if pr.eta is not None else "–",
                    "ok" if pr.ok else "**nicht erfüllt**",
                ]
                for pr in des.proofs
            ],
            right=(3,),
        ),
        "",
        "## Lastannahmen und Lastabtrag",
        "",
        *report_body(res, 3),
        "",
        "## Nachweise",
        "",
    ]
    for pr in des.proofs:
        out += [f"### Pos. {pr.pos.no}: {pr.pos.title}", "", *pr.md, ""]
    holes = _holes(des)
    out += ["## Aussparungen in tragenden Bauteilen", ""]
    if holes:
        out += [f"- {k}: {how}" for k, how in holes]
    else:
        out.append("Keine.")
    out += [
        "",
        "## Nicht nachgewiesen",
        "",
        "- Dachtragwerk (Sparren, Pfetten, Kehlbalken) und seine Verankerung im Einzelnen.",
        "- Aussteifung: Torsion des Grundrisses, Decken als Scheiben, Schub aus Imperfektionen.",
        "- Decken: Robustheitsbewehrung, Begrenzung der Rissbreite, Verformung über die"
        " Biegeschlankheit hinaus; Durchstanzen entfällt, die Decken sind linienförmig gelagert;"
        " Bodenplatte.",
        "- Wände: Teilflächenpressung unter Sturz- und Trägerauflagern, Wände unter der obersten"
        " Decke (Φ3), Kellerwände mit Erddruck.",
        "- Fundamente: Grundbruch, Setzungen und Bemessung des Betons; Frosttiefe.",
        "",
        "Berechnet aus dem Modell. Die Tragwerksplanung, ihre Prüfung und die Verantwortung liegen"
        " bei der unterzeichnenden Tragwerksplanerin oder dem unterzeichnenden Tragwerksplaner.",
        "",
        "| | |",
        "|---|---|",
        "| Aufgestellt | |",
        "| Datum, Unterschrift | |",
        "| Geprüft | |",
        "",
    ]
    return "\n".join(out)


STRUCT = Calculator(
    "struct",
    "Statische Berechnung",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (
        UNIT_WEIGHT,
        IMPOSED,
        PARTITION,
        FACTORS,
        PSI,
        SNOW,
        WIND,
        LIMITS,
        MASONRY,
        MASONRY_END,
        CONCRETE,
        LINTEL,
        SECTION,
        BEAM_MATERIAL,
        TIMBER,
        COLUMN_SECTION,
        WIND_WALL,
        MASONRY_SHEAR,
    ),
)

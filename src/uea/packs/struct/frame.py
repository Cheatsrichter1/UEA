"""Beams on the open-source solver PyNite (MIT; decision 0040): a straight beam on supports
along its axis, loaded in the plane, analysed linear-elastically.

PyNite is an optional dependency (`uea[struct]`); it is imported only when a beam or a slab is
analysed, and a missing install stops the calculator with a message that names it.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

SOLVER = "PyNite"


def solver() -> Any:
    """The PyNite model class, or a ValueError that says how to install it."""
    try:
        from Pynite import FEModel3D  # pyright: ignore[reportMissingTypeStubs]
    except ImportError:
        raise ValueError(
            "the structural solver PyNite is not installed: pip install 'uea[struct]'"
        ) from None
    return FEModel3D


def solver_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return f"{SOLVER} {version('PyNiteFEA')}"
    except PackageNotFoundError:
        return SOLVER


@dataclass
class Case:
    """The loads of one action on a beam, downward positive."""

    uniform: list[tuple[float, float, float]] = field(
        default_factory=list[tuple[float, float, float]]
    )
    """(s0, s1, kN/m)."""
    points: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])
    """(s, kN)."""

    def empty(self) -> bool:
        return not any(abs(q) > 0 for _, _, q in self.uniform) and not any(
            abs(p) > 0 for _, p in self.points
        )


@dataclass
class Effects:
    """What a combination does to the beam."""

    reactions: list[float]
    """kN at each support, upward positive."""
    sag: float
    """Largest sagging moment, kNm (bottom in tension), 0 or more."""
    hog: float
    """Largest hogging moment, kNm (top in tension), 0 or more."""
    shear: float
    """Largest shear force, kN, 0 or more."""
    deflection: float
    """Largest deflection, m, 0 or more."""


def beam(
    length: float,
    supports: list[float],
    ei: float,
    cases: dict[str, Case],
    combos: dict[str, dict[str, float]],
) -> dict[str, Effects]:
    """A beam from 0 to `length` on pinned supports at the points `supports` (from its start),
    with flexural stiffness `ei` (kNm²). Each combination is a sum of factored cases."""
    if len(supports) < 2:
        raise ValueError("a beam needs at least two supports")
    model = solver()()
    big = 1e3
    # E·I as given, with the section's other stiffnesses made rigid
    model.add_material("m", ei, ei / 2.4, 0.2, 0.0)
    model.add_section("s", big, big, 1.0, big)
    xs = sorted({0.0, length, *supports, *_stations(cases.values())})
    names: dict[float, str] = {}
    for i, x in enumerate(xs):
        names[x] = f"N{i}"
        model.add_node(names[x], x, 0.0, 0.0)
    model.add_member("B", names[xs[0]], names[xs[-1]], "m", "s")
    for i, x in enumerate(sorted(supports)):
        model.def_support(names[x], i == 0, True, True, True, False, False)
    for case, loads in cases.items():
        for s0, s1, q in loads.uniform:
            if abs(q) > 0 and s1 > s0:
                model.add_member_dist_load("B", "FY", -q, -q, s0, s1, case)
        for s, p in loads.points:
            if abs(p) > 0:
                model.add_member_pt_load("B", "FY", -p, s, case)
    for name, factors in combos.items():
        model.add_load_combo(name, {k: v for k, v in factors.items() if k in cases})
    model.analyze_linear(check_statics=False)
    member = model.members["B"]
    out: dict[str, Effects] = {}
    for name in combos:
        reactions = [float(model.nodes[names[x]].RxnFY[name]) for x in sorted(supports)]
        mmax = float(member.max_moment("Mz", name))
        mmin = float(member.min_moment("Mz", name))
        vmax = float(member.max_shear("Fy", name))
        vmin = float(member.min_shear("Fy", name))
        dmax = float(member.max_deflection("dy", name))
        dmin = float(member.min_deflection("dy", name))
        out[name] = Effects(
            reactions,
            max(0.0, -mmin) if SAGGING_NEGATIVE else max(0.0, mmax),
            max(0.0, mmax) if SAGGING_NEGATIVE else max(0.0, -mmin),
            max(abs(vmax), abs(vmin)),
            max(abs(dmax), abs(dmin)),
        )
    return out


SAGGING_NEGATIVE = True
"""PyNite's sign of Mz for a beam along x loaded in -y: sagging is negative (tested)."""


def _stations(cases: Iterable[Case]) -> set[float]:
    out: set[float] = set()
    for c in cases:
        for s0, s1, _ in c.uniform:
            out |= {s0, s1}
        out |= {s for s, _ in c.points}
    return out


# ---------- plane frames ----------


@dataclass(frozen=True)
class Bar:
    """A straight member of a plane frame from node i to node j."""

    name: str
    i: str
    j: str
    area: float
    """m²."""
    inertia: float
    """Second moment of area for bending in the frame's plane, m⁴."""
    e: float
    """kN/m²."""
    hinge_i: bool = False
    hinge_j: bool = False


@dataclass
class BarEffects:
    moment: float
    """Largest |M|, kNm."""
    compression: float
    """Largest axial compression, kN (0 if it is in tension throughout)."""
    tension: float
    """Largest axial tension, kN, 0 or more."""
    shear: float
    """Largest |V|, kN."""
    deflection: float
    """Largest deflection across the bar relative to its ends' line, m."""


Push = tuple[str, float, float]
"""A uniform load on a bar: (bar, global x, global y per metre of the bar), kN/m."""


def plane_frame(
    nodes: dict[str, tuple[float, float]],
    bars: list[Bar],
    pinned: list[str],
    cases: dict[str, list[Push]],
    combos: dict[str, dict[str, float]],
) -> tuple[dict[str, dict[str, BarEffects]], dict[str, dict[str, tuple[float, float]]]]:
    """A frame in the x-y plane (y up) on pinned supports, linear-elastic: each combination's
    effects per bar, and the reactions (Rx, Ry) at each support, kN."""
    model = solver()()
    for b in bars:
        model.add_material(f"m-{b.name}", b.e, b.e / 2.4, 0.2, 0.0)
        model.add_section(f"s-{b.name}", b.area, b.inertia, b.inertia, b.inertia)
    for k, (x, y) in nodes.items():
        model.add_node(k, x, y, 0.0)
        held = k in pinned
        model.def_support(k, held, held, True, True, True, False)
    for b in bars:
        model.add_member(b.name, b.i, b.j, f"m-{b.name}", f"s-{b.name}")
        if b.hinge_i or b.hinge_j:
            model.def_releases(b.name, Rzi=b.hinge_i, Rzj=b.hinge_j)
    for case, pushes in cases.items():
        for name, fx, fy in pushes:
            if abs(fx) > 0:
                model.add_member_dist_load(name, "FX", fx, fx, None, None, case)
            if abs(fy) > 0:
                model.add_member_dist_load(name, "FY", fy, fy, None, None, case)
    for name, factors in combos.items():
        model.add_load_combo(name, {k: v for k, v in factors.items() if k in cases})
    model.analyze_linear(check_statics=False)
    effects: dict[str, dict[str, BarEffects]] = {}
    reactions: dict[str, dict[str, tuple[float, float]]] = {}
    for name in combos:
        per: dict[str, BarEffects] = {}
        for b in bars:
            mb = model.members[b.name]
            per[b.name] = BarEffects(
                max(abs(float(mb.max_moment("Mz", name))), abs(float(mb.min_moment("Mz", name)))),
                max(0.0, float(mb.max_axial(name))),
                max(0.0, -float(mb.min_axial(name))),
                max(abs(float(mb.max_shear("Fy", name))), abs(float(mb.min_shear("Fy", name)))),
                _relative(mb, name),
            )
        effects[name] = per
        reactions[name] = {
            k: (float(model.nodes[k].RxnFX[name]), float(model.nodes[k].RxnFY[name]))
            for k in pinned
        }
    return effects, reactions


def _relative(mb: Any, combo: str) -> float:
    """The largest deflection of a bar across its axis, from the line between its ends."""
    try:
        arr = mb.rel_deflection_array("dy", 11, combo)
    except Exception:  # an older PyNite without relative deflections
        arr = mb.deflection_array("dy", 11, combo)
    return float(max(abs(float(v)) for v in arr[1]))

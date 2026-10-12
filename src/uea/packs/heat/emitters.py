"""The heat output of an emitter at its circuit's temperatures (decision 0042).

A type gives its output either at the system's design temperatures (radiator `w=`, underfloor
heating `q=`), taken as it is, or as the standards' characteristic:

- Radiator, DIN EN 442-2: Φ = Φ_n · (Δθ / Δθ_n)^n, with the logarithmic temperature difference
  Δθ = (θ_V − θ_R) / ln((θ_V − θ_i) / (θ_R − θ_i)) and Δθ_n of the standard conditions 75/65/20 °C.
  Φ_n and n are the manufacturer's test values (`wn=`, `n=`).
- Underfloor heating, DIN EN 1264-2: q = K_H · Δθ_H, with Δθ_H the same logarithmic difference
  and K_H the system's equivalent heat transmission coefficient for the floor covering, from the
  manufacturer (`kh=`). The mean floor surface temperature follows from the basic characteristic
  curve q = 8.92 · (θ_F,m − θ_i)^1.1 (W/m², K), DIN EN 1264-2.

The temperatures of a circuit are its manifold's (`flow=`, `spread=`), else the system's (the
calculators' settings `flow=`, `spread=`). The room temperature θ_i is the Heizlast's.
"""

import math
from dataclasses import dataclass

from uea.derive import Derived
from uea.packs.heat.geometry import heat_type
from uea.packs.heat.kinds import Man, RadType, UfhType

STANDARD = (75.0, 65.0, 20.0)
"""θ_V, θ_R and θ_i of the standard output of a radiator, °C (DIN EN 442-2)."""
CURVE = (8.92, 1.1)
"""The basic characteristic curve q = 8.92 · Δθ^1.1 of a heated floor (DIN EN 1264-2)."""


@dataclass(frozen=True)
class Temps:
    flow: float
    spread: float

    @property
    def ret(self) -> float:
        return self.flow - self.spread


def lmtd(flow: float, ret: float, ti: float) -> float | None:
    """The logarithmic temperature difference of an emitter; none if the water is not warmer
    than the room at the return."""
    a, b = flow - ti, ret - ti
    if a <= 0 or b <= 0:
        return None
    if abs(a - b) < 1e-9:
        return a
    return (a - b) / math.log(a / b)


def temps_of(d: Derived, e: str, flow: float | None, spread: float | None) -> Temps | None:
    """The design temperatures of an emitter's circuit: its manifold's, else the system's."""
    el = d.model[e]
    src = getattr(el, "src", None)
    man = d.model.get(src.id) if src is not None else None
    f, s = flow, spread
    if isinstance(man, Man):
        f = man.flow if man.flow is not None else f
        s = man.spread if man.spread is not None else s
    if f is None or s is None:
        return None
    return Temps(f, s)


@dataclass(frozen=True)
class Out:
    w: float
    """Heat output, W; 0 if it cannot be known."""
    how: str
    """type (the type's output at design temperatures), EN 442, EN 1264, or none."""
    floor: float | None = None
    """The mean floor surface temperature of an underfloor heating, °C."""


def output(d: Derived, e: str, ti: float, flow: float | None, spread: float | None) -> Out:
    """The output of an emitter in a room at θ_i."""
    el = d.model[e]
    t = temps_of(d, e, flow, spread)
    if el.kind == "rad":
        rt = heat_type(d.model, el, RadType, "rad")
        if rt is None:
            return Out(0.0, "none")
        if rt.wn is not None and rt.n is not None and t is not None:
            dt = lmtd(t.flow, t.ret, ti)
            dn = lmtd(*STANDARD)
            assert dn is not None
            return Out(0.0 if dt is None else rt.wn * (dt / dn) ** rt.n, "EN 442")
        return Out(rt.w or 0.0, "type" if rt.w is not None else "none")
    ut = heat_type(d.model, el, UfhType, "ufh")
    lp = d.heat.loops.get(e)
    if ut is None or lp is None:
        return Out(0.0, "none")
    if ut.kh is not None and t is not None:
        dt = lmtd(t.flow, t.ret, ti)
        q = 0.0 if dt is None else ut.kh * dt
        return Out(q * lp.area, "EN 1264", floor_temp(q, ti))
    if ut.q is None:
        return Out(0.0, "none")
    return Out(ut.q * lp.area, "type", floor_temp(ut.q, ti))


def floor_temp(q: float, ti: float) -> float:
    """The mean floor surface temperature at a heat flux q (W/m²) and θ_i."""
    a, b = CURVE
    return ti + (q / a) ** (1 / b) if q > 0 else ti

"""Pipe hydraulics: the formulas, no norm values (decision 0035).

Full pipes under pressure (drinking water): Darcy-Weisbach with the friction factor of
Colebrook-White,

    R = λ / d_i · ρ v² / 2,   1/√λ = −2 lg(2.51 / (Re √λ) + k / (3.71 d_i)),   λ = 64/Re below 2320

and the losses of fittings Z = Σζ · ρ v² / 2. Gravity pipes partly full (drainage):
Prandtl-Colebrook with the hydraulic radius R_h of the wetted part,

    v = −2 lg(2.51 ν / (4R_h √(2g · 4R_h · J)) + k_b / (3.71 · 4R_h)) · √(2g · 4R_h · J)

Water: density and kinematic viscosity at 10 °C (cold), 60 °C (hot) and 40 °C (heating, the
middle of the usual flow and return temperatures), and its specific heat; air at 20 °C for the
ducts (decision 0038); physical constants.
"""

import math
from dataclasses import dataclass
from typing import Literal

G = 9.81
Temp = Literal["cold", "hot", "heating", "air"]
RHO: dict[Temp, float] = {"cold": 999.7, "hot": 983.2, "heating": 992.2, "air": 1.204}
"""Density of water, kg/m³, at 10 °C, 60 °C and 40 °C; of air at 20 °C."""
NU: dict[Temp, float] = {"cold": 1.306e-6, "hot": 0.474e-6, "heating": 0.658e-6, "air": 15.11e-6}
"""Kinematic viscosity of water, m²/s, at 10 °C, 60 °C and 40 °C; of air at 20 °C."""
CP = 4.179
"""Specific heat of water at 40 °C, kJ/(kg·K)."""
LAMINAR = 2320.0


def friction(re: float, rough: float) -> float:
    """The friction factor λ for a Reynolds number and a relative roughness k/d_i."""
    if re <= 0:
        return 0.0
    if re < LAMINAR:
        return 64 / re
    lam = 0.02
    for _ in range(50):
        nxt = (-2 * math.log10(2.51 / (re * math.sqrt(lam)) + rough / 3.71)) ** -2
        if abs(nxt - lam) < 1e-12:
            return nxt
        lam = nxt
    return lam


@dataclass(frozen=True)
class Flow:
    """A full pipe at one flow."""

    v: float
    """Velocity, m/s."""
    r: float
    """Pressure loss of the pipe per metre, hPa/m."""
    dyn: float
    """Dynamic pressure ρv²/2, hPa: times Σζ it is the loss of the fittings."""


def full(q: float, di: float, k: float, temp: Temp) -> Flow:
    """Flow q (l/s) in a full pipe of inner diameter di (mm) and roughness k (mm)."""
    d = di / 1000
    v = q / 1000 / (math.pi * d * d / 4)
    lam = friction(v * d / NU[temp], k / di)
    dyn = RHO[temp] * v * v / 2 / 100
    return Flow(v, lam / d * dyn, dyn)


def geodetic(dz: float, temp: Temp = "cold") -> float:
    """The pressure a height difference dz (m) takes, hPa."""
    return RHO[temp] * G * dz / 100


def wetted(fill: float) -> tuple[float, float]:
    """The wetted area over d² and the hydraulic radius over d of a circle filled to h/d."""
    if not 0 < fill <= 1:
        raise ValueError(f"filling h/d {fill} must be more than 0 and at most 1")
    th = 2 * math.acos(1 - 2 * fill)
    area = (th - math.sin(th)) / 8
    return area, area / (th / 2)


def gravity(di: float, slope: float, kb: float, fill: float, nu: float = NU["cold"]) -> float:
    """What a drain pipe of inner diameter di (mm) carries at a slope (m/m), a roughness kb
    (mm) and a filling h/d, l/s."""
    d = di / 1000
    a, rh = wetted(fill)
    d4 = 4 * rh * d
    root = math.sqrt(2 * G * d4 * slope)
    v = -2 * math.log10(2.51 * nu / (d4 * root) + kb / 1000 / (3.71 * d4)) * root
    return v * a * d * d * 1000


def heat_flow(phi: float, spread: float, temp: Temp = "heating") -> float:
    """The water flow (l/s) that carries phi (W) at a temperature spread (K)."""
    return phi / (RHO[temp] * CP * spread)

"""Thermal resistance and U-value of a build-up of homogeneous layers (DIN EN ISO 6946).

    R = d / λ for each layer,  R_T = R_si + Σ R + R_se,  U = 1 / R_T

λ comes from the office's table `material`, by the material name written in the layers of the
types; R_si and R_se from its table `surface`, by the direction of the heat flow. Where the far
side is the ground, R_se is 0; where it is another room or an unheated space, it is R_si of the
same direction (decision 0033). No number of a standard is in the code.

Not covered: air layers, inhomogeneous layers (rafters with insulation between them), the
corrections for fixings, air gaps and inverted roofs, tapered layers.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from uea.calc import Env
from uea.calc.data import Col, Spec
from uea.core.values import Layer

Flow = Literal["up", "horizontal", "down"]
Far = Literal["outside", "ground", "inside"]
"""What lies beyond the build-up: outside air, the ground, or a room (heated or not)."""

FLOW_DE = {"up": "aufwärts", "horizontal": "horizontal", "down": "abwärts"}
FAR_DE = {"outside": "Außenluft", "ground": "Erdreich", "inside": "Raum"}

MATERIAL = Spec(
    "material",
    "Thermal conductivity of building materials",
    "DIN 4108-4, DIN EN ISO 10456, or the manufacturer's declared design value",
    (
        Col("material", "text", "the material name as the layers of the types write it"),
        Col("lambda", "num", "design thermal conductivity λ, W/(m·K)"),
    ),
    ("material",),
    "One row for each material in layers= of the types, e.g. ziegel-t9 for *ziegel-t9:0.365.",
)
SURFACE = Spec(
    "surface",
    "Surface resistances",
    "DIN EN ISO 6946",
    (
        Col("flow", "text", "direction of the heat flow", ("up", "horizontal", "down")),
        Col("rsi", "num", "internal surface resistance R_si, m²·K/W"),
        Col("rse", "num", "external surface resistance R_se, m²·K/W"),
    ),
    ("flow",),
    "Three rows: up, horizontal, down.",
)


@dataclass(frozen=True)
class UValue:
    u: float
    rsi: float
    rse: float
    r_layers: float

    @property
    def r_total(self) -> float:
        return self.rsi + self.r_layers + self.rse


class Thermal:
    """U-values from the office's tables; every material is checked before the first."""

    def __init__(self, env: Env, materials: Iterable[str]) -> None:
        self.mat = env.table(MATERIAL)
        self.surf = env.table(SURFACE)
        missing = sorted({m for m in materials if self.mat.find(material=m) is None})
        if missing:
            raise ValueError(
                f"the table material has no row for {', '.join(missing)}: add them"
                " (uea data show material)"
            )
        for flow in ("up", "horizontal", "down"):
            if self.surf.find(flow=flow) is None:
                raise ValueError(f"the table surface has no row for flow {flow}")

    def lam(self, material: str) -> float:
        row = self.mat.find(material=material)
        assert row is not None
        return float(row["lambda"])

    def r_layers(self, layers: Iterable[Layer]) -> float:
        return sum(x.t / self.lam(x.material) for x in layers)

    def u(self, layers: Iterable[Layer], flow: Flow, far: Far) -> UValue:
        row = self.surf.find(flow=flow)
        assert row is not None
        rsi = float(row["rsi"])
        rse = {"outside": float(row["rse"]), "ground": 0.0, "inside": rsi}[far]
        r = self.r_layers(layers)
        return UValue(1 / (rsi + r + rse), rsi, rse, r)

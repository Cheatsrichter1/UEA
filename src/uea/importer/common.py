"""Small things the importer's modules share: names, numbers, build-ups and the level record."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from uea.core.syntax import fmt_num
from uea.importer.ifc import Layer, Storey

STRUCTURAL = (
    "beton",
    "concrete",
    "stahlbeton",
    "stb",
    "ziegel",
    "brick",
    "mauerwerk",
    "masonry",
    "kalksandstein",
    "porenbeton",
    "ytong",
    "holz",
    "timber",
    "clt",
    "stahl",
    "steel",
    "block",
)
ROOF_CORE = (
    "sparren",
    "rafter",
    "balken",
    "beam",
    "binder",
    "truss",
    "holz",
    "timber",
    "clt",
    "stahl",
    "steel",
    "beton",
    "concrete",
    "stb",
)
"""... of a roof: the rafters. Tiles (Ziegel) are not structural there."""


def slug(text: str, limit: int = 20) -> str:
    """ASCII letters, digits and hyphens: the form a name takes in the model."""
    s = text.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:limit].strip("-")


def num(v: float) -> str:
    return fmt_num(round(v, 4))


def layers_text(layers: Sequence[Layer], core: int | None = None) -> str:
    """Layers as the model writes them: material:thickness, the core marked with a star."""
    return ",".join(
        f"{'*' if i == core else ''}{slug(lay.material, 16).lower() or 'layer'}:{num(lay.t)}"
        for i, lay in enumerate(layers)
    )


def core_index(layers: tuple[Layer, ...], words: tuple[str, ...] = STRUCTURAL) -> int:
    """The load-bearing layer: the thickest with a structural material name, else the thickest."""
    structural = [
        i for i, lay in enumerate(layers) if any(w in lay.material.lower() for w in words)
    ]
    pool = structural or list(range(len(layers)))
    return max(pool, key=lambda i: (round(layers[i].t, 4), -i))


@dataclass
class Lv:
    storey: Storey
    name: str
    z: float
    """FFL relative to the ground storey."""
    off: float = 0.0
    """Elevation of the ground storey in the file: absolute height = off + UEA height."""
    fb: float = 0.0
    head: float | None = None

    @property
    def ssl(self) -> float:
        return self.z - self.fb

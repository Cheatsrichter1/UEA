"""The light pack: luminaires (placed and wired by the electrical design)."""

from uea.core.registry import Pack
from uea.packs.light.geometry import derive_light, light_signatures
from uea.packs.light.kinds import KINDS
from uea.packs.light.views import describe

CODES: dict[str, str] = {
    "E-LIGHT-002": "luminaire on a wall without a usable face",
}

PACK = Pack(
    name="light",
    title="Luminaires",
    kinds=KINDS,
    derive=derive_light,
    codes=CODES,
    signatures=light_signatures,
    describe=describe,
)

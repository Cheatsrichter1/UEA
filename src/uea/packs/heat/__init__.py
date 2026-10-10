"""The heating pack (`heat.uea`): generators, tanks, manifolds, underfloor heating and radiators
(decision 0034); with the U-values and the Heizlast as calculators (decision 0033)."""

from uea.core.registry import Pack
from uea.packs.heat.checks import CODES, heat_checks
from uea.packs.heat.geometry import derive_heat, heat_signatures
from uea.packs.heat.kinds import KINDS
from uea.packs.heat.views import describe

PACK = Pack(
    name="heat",
    title="Heating",
    kinds=KINDS,
    derive=derive_heat,
    checks=(heat_checks,),
    codes=CODES,
    signatures=heat_signatures,
    describe=describe,
)

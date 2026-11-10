"""The med pack: medical and hospital systems. Medical gases with their derived pipes, the fire
alarm system, the nurse call system, and the medical locations with their IT systems and safety
power (decision 0058)."""

from uea.core.registry import Pack
from uea.packs.med.checks import CODES, med_checks
from uea.packs.med.geometry import derive_med, med_signatures
from uea.packs.med.kinds import KINDS
from uea.packs.med.views import describe

PACK = Pack(
    name="med",
    title="Medical and hospital systems",
    kinds=KINDS,
    derive=derive_med,
    checks=(med_checks,),
    codes=CODES,
    signatures=med_signatures,
    describe=describe,
)

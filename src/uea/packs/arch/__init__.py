"""The architecture pack."""

from uea.core.registry import Pack
from uea.packs.arch.checks import CODES, arch_checks
from uea.packs.arch.geometry import arch_signatures, derive_arch
from uea.packs.arch.kinds import KINDS
from uea.packs.arch.views import describe

PACK = Pack(
    name="arch",
    title="Architecture",
    kinds=KINDS,
    derive=derive_arch,
    checks=(arch_checks,),
    codes=CODES,
    signatures=arch_signatures,
    describe=describe,
)

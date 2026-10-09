"""The electrical pack: boards, RCDs, circuits, devices, luminaire switching and feeds."""

from uea.core.registry import Pack
from uea.packs.elec.checks import CODES, elec_checks
from uea.packs.elec.geometry import derive_elec, elec_signatures
from uea.packs.elec.kinds import KINDS
from uea.packs.elec.views import describe

PACK = Pack(
    name="elec",
    title="Electrical",
    kinds=KINDS,
    derive=derive_elec,
    checks=(elec_checks,),
    codes=CODES,
    signatures=elec_signatures,
    describe=describe,
    also=("lum",),
)

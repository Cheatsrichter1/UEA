"""The ventilation pack (`vent.uea`): central units, decentral units and air terminals, with the
ducts derived (decision 0038); the air flows per DIN 1946-6 and the duct sizing as
calculators."""

from uea.core.registry import Pack
from uea.packs.vent.checks import CODES, vent_checks
from uea.packs.vent.geometry import derive_vent, vent_signatures
from uea.packs.vent.kinds import KINDS
from uea.packs.vent.views import describe

PACK = Pack(
    name="vent",
    title="Ventilation",
    kinds=KINDS,
    derive=derive_vent,
    checks=(vent_checks,),
    codes=CODES,
    signatures=vent_signatures,
    describe=describe,
)

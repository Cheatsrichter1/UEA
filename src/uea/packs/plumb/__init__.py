"""The plumbing pack (`plumb.uea`): sanitary fixtures, the meter, risers, stacks and the sewer
connection, with the pipes between them derived (decision 0035); the pipe sizing for drinking
water and drainage as calculators."""

from uea.core.registry import Pack
from uea.packs.plumb.checks import CODES, plumb_checks
from uea.packs.plumb.geometry import derive_plumb, plumb_signatures
from uea.packs.plumb.kinds import KINDS
from uea.packs.plumb.views import describe

PACK = Pack(
    name="plumb",
    title="Plumbing",
    kinds=KINDS,
    derive=derive_plumb,
    checks=(plumb_checks,),
    codes=CODES,
    signatures=plumb_signatures,
    describe=describe,
    also=("tank",),
)

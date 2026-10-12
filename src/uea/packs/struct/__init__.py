"""Structure (decision 0040): the load path from the architecture, beams and loads of its own
(`struct.uea`), its checks, and the calculators `loads` and `struct`. The load-bearing walls and
the slabs are the architect's."""

from uea.core.registry import Pack
from uea.packs.struct.checks import CODES, struct_checks
from uea.packs.struct.geometry import derive_struct
from uea.packs.struct.kinds import KINDS

PACK = Pack(
    name="struct",
    title="Structure",
    kinds=KINDS,
    derive=derive_struct,
    checks=(struct_checks,),
    codes=CODES,
)

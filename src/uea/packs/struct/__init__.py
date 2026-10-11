"""Structure (decision 0040): the load path from the architecture, its checks, and `uea calc
loads`. No elements of its own yet: the load-bearing walls and the slabs are the architect's."""

from uea.core.registry import Pack
from uea.packs.struct.checks import CODES, struct_checks

PACK = Pack(
    name="struct",
    title="Structure",
    kinds=(),
    checks=(struct_checks,),
    codes=CODES,
)

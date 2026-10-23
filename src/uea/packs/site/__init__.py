"""The site pack: the plot and the limits its plan sets on the building (decision 0055)."""

from uea.core.registry import Pack
from uea.packs.site.geometry import derive_site, describe, site_checks
from uea.packs.site.kinds import KINDS

CODES: dict[str, str] = {
    "E-SITE-001": "plot outline crosses itself or encloses no area",
    "E-SITE-002": "more than one plot",
    "W-SITE-003": "part of a storey lies outside the plot",
}

PACK = Pack(
    name="site",
    title="The plot and the limits of its plan",
    kinds=KINDS,
    derive=derive_site,
    checks=(site_checks,),
    codes=CODES,
    describe=describe,
)

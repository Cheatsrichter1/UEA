"""Domain packs."""

from functools import cache

from uea.core.registry import Registry


@cache
def default_registry() -> Registry:
    from uea.packs import arch, bid, elec, heat, issues, light, lv, plumb, project, struct, vent

    return Registry(
        [
            project.PACK,
            arch.PACK,
            struct.PACK,
            light.PACK,
            elec.PACK,
            heat.PACK,
            plumb.PACK,
            vent.PACK,
            lv.PACK,
            bid.PACK,
            issues.PACK,
        ]
    )

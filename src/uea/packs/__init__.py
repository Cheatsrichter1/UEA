"""Domain packs."""

from functools import cache

from uea.core.registry import Registry


@cache
def default_registry() -> Registry:
    from uea.packs import arch, elec, heat, issues, light, project

    return Registry([project.PACK, arch.PACK, light.PACK, elec.PACK, heat.PACK, issues.PACK])

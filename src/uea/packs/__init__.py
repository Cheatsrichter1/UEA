"""Domain packs."""

from functools import cache

from uea.core.registry import Registry


@cache
def default_registry() -> Registry:
    from uea.packs import arch, issues, project

    return Registry([project.PACK, arch.PACK, issues.PACK])

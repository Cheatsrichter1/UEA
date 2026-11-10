"""Where the medical and hospital systems are, and the gas pipes between (decision 0058).

The pipes of each medical gas are derived like the ventilation ducts (decisions 0035, 0038): from
each source the shortest rectilinear tree over the outlets of its gas that are nearer to it than
to another source of that gas, along the installation zones, through the slab holes of its via=.
The rest is placement and bookkeeping for the checks: the detectors and calls of each room, the
room each door lamp signals, the medical location of each room.
"""

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived, Unresolved
from uea.packs.med.kinds import ROLE_Z, Call, GasOutlet, GasSrc, MedLoc, Safety
from uea.packs.mount import Mounted, Mounts
from uea.packs.net import Crossing, Net, Zoned, finish, gap, grow, node_of, routed, through

PLACED = ("gsrc", "gas", "fpanel", "fdet", "mcp", "cpanel", "call", "itsys", "safety")


@dataclass
class MedGeo:
    at: dict[str, Mounted] = field(default_factory=dict[str, Mounted])
    nets: dict[tuple[str, str], Net] = field(default_factory=dict[tuple[str, str], Net])
    """By (source, gas)."""
    source_of: dict[tuple[str, str], str] = field(default_factory=dict[tuple[str, str], str])
    """(outlet, gas) -> the source it is supplied from."""
    crossings: list[Crossing] = field(default_factory=list[Crossing])
    """Where the gas pipes pass the slabs (decision 0039)."""
    detectors: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """By room: its automatic fire detectors."""
    calls: dict[str, dict[str, list[str]]] = field(default_factory=dict[str, dict[str, list[str]]])
    """By room, then role: the nurse call devices in it."""
    signalled: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """By room: the door lamps that signal it."""
    loc: dict[str, str] = field(default_factory=dict[str, str])
    """By room: its medical location."""

    def pipe_to(self, outlet: str, gas: str) -> tuple[str, float] | None:
        src = self.source_of.get((outlet, gas))
        net = self.nets.get((src, gas)) if src is not None else None
        if src is None or net is None or not net.has(outlet):
            return None
        return src, net.reach(outlet)


def derive_med(d: Derived) -> None:
    m = d.model
    g = d.med = MedGeo()
    mounts = Mounts(d)
    for kind in PLACED:
        for el in m.of_kind(kind):
            with suppress(Unresolved):
                d.resolve(el.id, g.at, lambda el=el: _place(d, mounts, el))
    _gas(d)
    for el in m.of_kind("fdet"):
        mt = g.at.get(el.id)
        if mt is not None and mt.room is not None:
            g.detectors.setdefault(mt.room, []).append(el.id)
    for el in m.of_kind("call"):
        assert isinstance(el, Call)
        mt = g.at.get(el.id)
        if mt is not None and mt.room is not None and el.role != "lamp":
            g.calls.setdefault(mt.room, {}).setdefault(el.role, []).append(el.id)
        if el.role == "lamp" and el.door is not None:
            door: Any = m.get(el.door.id)
            if door is not None and door.into is not None:
                g.signalled.setdefault(door.into.id, []).append(el.id)
    for el in m.of_kind("medloc"):
        assert isinstance(el, MedLoc)
        g.loc.setdefault(el.room.id, el.id)


def _place(d: Derived, mounts: Mounts, el: Element) -> Mounted:
    host = d.model.get(getattr(el, "host").id)  # noqa: B009
    if host is None:
        raise Unresolved(getattr(el, "host").id, missing=True)  # noqa: B009
    if host.kind == "room":
        if isinstance(el, GasSrc | Safety):
            mt: Mounted = mounts._in_room(el.id, el)  # pyright: ignore[reportPrivateUsage]
            mt.z = d.arch.levels[mt.level].z + el.z
            mt.width = 0.6
            return mt
        return mounts._in_room(el.id, el)  # pyright: ignore[reportPrivateUsage]
    mt = mounts._on_wall(el.id, el)  # pyright: ignore[reportPrivateUsage]
    if isinstance(el, Call) and el.z is None:
        mt.z = d.arch.levels[mt.level].z + ROLE_Z[el.role]
    return mt


def _gas(d: Derived) -> None:
    m, g = d.model, d.med
    sources: dict[str, list[str]] = {}
    for el in m.of_kind("gsrc"):
        assert isinstance(el, GasSrc)
        if el.id in g.at:
            sources.setdefault(el.gas, []).append(el.id)
    ends: dict[tuple[str, str], list[str]] = {}
    for el in m.of_kind("gas"):
        assert isinstance(el, GasOutlet)
        if el.id not in g.at:
            continue
        here = node_of(g.at[el.id])
        for gas in el.gas_list:
            if gas not in sources:
                continue
            src = min(sources[gas], key=lambda s: (gap(here, node_of(g.at[s]))[0], natural(s)))
            g.source_of[(el.id, gas)] = src
            ends.setdefault((src, gas), []).append(el.id)
    for (src, gas), outlets in sorted(ends.items(), key=lambda kv: (natural(kv[0][0]), kv[0][1])):
        el = m[src]
        assert isinstance(el, GasSrc)
        net = Net(src, {src: node_of(g.at[src])})
        for k in outlets:
            net.nodes[k] = node_of(g.at[k])
        via = el.via.refs() if el.via else ()
        dist = Zoned(d, routed(d, via))
        own = g.at[src].level
        by_level: dict[str, list[str]] = {}
        for k in sorted(outlets, key=natural):
            by_level.setdefault(g.at[k].level, []).append(k)
        # the source's storey first; then one riser per storey from the source, through via=,
        # and that storey's outlets from there (gas pipes do not hop between outlets' storeys)
        grow(net, {src}, [src], by_level.pop(own, []), "gas", dist)
        for lv in d.arch.level_order():
            on = by_level.get(lv)
            if not on:
                continue
            first = min(on, key=lambda k: (dist(net.nodes[src], net.nodes[k])[0], natural(k)))
            grow(net, {src}, [src], [first], "riser", dist)
            grow(net, {first}, [first], [k for k in on if k != first], "gas", dist)
        finish(net, set(outlets))
        g.crossings += through(d, net, via)
        g.nets[(src, gas)] = net


def med_signatures(d: Derived) -> dict[str, tuple[float | str, ...]]:
    g = d.med
    out: dict[str, tuple[float | str, ...]] = {
        k: (round(x.point[0], 4), round(x.point[1], 4), round(x.z, 4)) for k, x in g.at.items()
    }
    for (_, gas), net in g.nets.items():
        for s in net.sections:
            out[f"{gas}:{s.name}"] = (round(s.length, 3),)
    return out

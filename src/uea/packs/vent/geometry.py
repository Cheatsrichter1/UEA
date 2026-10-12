"""Where the ventilation is and the ducts between (decision 0038).

The ducts of a central unit are derived like the pipes (decisions 0035, 0037): for each of its
four kinds of air, the shortest rectilinear tree from the unit over its terminals of that kind,
so a duct runs along x, y and z and its length is a lower bound. A decentral unit has no ducts;
a push-pull pair is the unit with pair= and the unit it names, both ways.
"""

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived, GeoError, Unresolved
from uea.packs.arch.geometry import Resolver
from uea.packs.heat.geometry import heat_type
from uea.packs.mount import Mounted, Mounts
from uea.packs.net import Crossing, Net, Zoned, finish, gap, grow, node_of, routed, through
from uea.packs.vent.kinds import (
    ROLES,
    Ahu,
    AhuType,
    Air,
    DuctType,
    Fan,
    FanType,
    Inlet,
    InletType,
    Over,
)

PLACED = ("ahu", "fan", "air", "inlet")


@dataclass
class VentGeo:
    at: dict[str, Mounted] = field(default_factory=dict[str, Mounted])
    pairs: dict[str, str] = field(default_factory=dict[str, str])
    """Each unit of a push-pull pair and its partner, both ways."""
    bad_pairs: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    """(unit, why) for pairs that do not match."""
    unit_of: dict[str, str] = field(default_factory=dict[str, str])
    """The central unit of each air terminal."""
    ducts: dict[tuple[str, str], Net] = field(default_factory=dict[tuple[str, str], Net])
    """By (unit, role)."""
    terminals: dict[str, dict[str, list[str]]] = field(
        default_factory=dict[str, dict[str, list[str]]]
    )
    """By room, then role: the terminals and decentral units in it."""
    crossings: list[Crossing] = field(default_factory=list[Crossing])
    """Where the ducts pass the slabs (decision 0039)."""
    holes: dict[str, str | None] = field(default_factory=dict[str, str | None])
    """Each unit and terminal on an exterior wall: the hole it goes through, if any."""
    overflow: dict[str, float] = field(default_factory=dict[str, float])
    """The free area of each overflow opening, cm²."""
    over_rooms: dict[str, tuple[str | None, str | None]] = field(
        default_factory=dict[str, tuple[str | None, str | None]]
    )
    """The rooms on either side of each overflow opening's door."""

    def duct_from(self, end: str) -> tuple[str, float] | None:
        for (unit, _), net in self.ducts.items():
            if end in net.nodes and end != unit:
                return unit, net.reach(end)
        return None


def vent_type[T: Element](d: Derived, el: Element, cls: type[T], category: str) -> T | None:
    return heat_type(d.model, el, cls, category)


def duct_type(d: Derived) -> DuctType | None:
    for t in d.model.of_kind("type", "duct"):
        if isinstance(t, DuctType) and t.default:
            return t
    return None


def derive_vent(d: Derived) -> None:
    m = d.model
    v = d.vent = VentGeo()
    place = Placer(d)
    for kind in PLACED:
        for el in m.of_kind(kind):
            with suppress(Unresolved):
                d.resolve(el.id, v.at, lambda el=el: place.place(el))
    _pairs(d)
    units = [el.id for el in m.of_kind("ahu") if el.id in v.at]
    for el in m.of_kind("air"):
        assert isinstance(el, Air)
        if el.id not in v.at:
            continue
        if el.src is not None:
            if el.src.id in v.at:
                v.unit_of[el.id] = el.src.id
        elif units:
            here = node_of(v.at[el.id])
            v.unit_of[el.id] = min(
                units, key=lambda u: (gap(here, node_of(v.at[u]))[0], natural(u))
            )
    for u in units:
        for role in ROLES:
            ends = sorted(
                (k for k, x in v.unit_of.items() if x == u and _role(m[k]) == role), key=natural
            )
            if not ends:
                continue
            net = Net(u, {u: node_of(v.at[u])})
            for k in ends:
                net.nodes[k] = node_of(v.at[k])
            unit = m[u]
            assert isinstance(unit, Ahu)
            via = unit.via.refs() if unit.via else ()
            grow(net, {u}, [u], ends, "duct", Zoned(d, routed(d, via)))
            finish(net, set(ends))
            v.crossings += through(d, net, via)
            v.ducts[(u, role)] = net
    for kind in ("fan", "air", "inlet"):
        for el in m.of_kind(kind):
            mt = v.at.get(el.id)
            if mt is None or mt.wall is None or d.arch.walls[mt.wall].ext is None:
                continue
            if isinstance(el, Air) and el.role not in ("oda", "eha"):
                continue
            v.holes[el.id] = next(
                (
                    h.id
                    for h in sorted(d.arch.holes.values(), key=lambda h: natural(h.id))
                    if h.wall is not None
                    and h.host == mt.wall
                    and not h.chase
                    and h.status != "demolish"
                    and h.wall.lo - 1e-6 <= mt.s <= h.wall.hi + 1e-6
                    and h.z0 - 1e-6 <= mt.z <= h.z1 + 1e-6
                ),
                None,
            )
    for el in m.of_kind("air"):
        mt = v.at.get(el.id)
        if mt is not None and mt.room is not None and _role(el) in ("sup", "ext"):
            v.terminals.setdefault(mt.room, {}).setdefault(_role(el), []).append(el.id)
    for el in m.of_kind("fan"):
        assert isinstance(el, Fan)
        mt = v.at.get(el.id)
        if mt is None or mt.room is None:
            continue
        roles = {"alt": ("sup", "ext"), "both": ("sup", "ext"), "ext": ("ext",)}[el.mode]
        for role in roles:
            v.terminals.setdefault(mt.room, {}).setdefault(role, []).append(el.id)
    for el in m.of_kind("inlet"):
        mt = v.at.get(el.id)
        if mt is not None and mt.room is not None:
            v.terminals.setdefault(mt.room, {}).setdefault("sup", []).append(el.id)
    for el in m.of_kind("over"):
        assert isinstance(el, Over)
        o = d.arch.openings.get(el.host.id)
        if o is None:
            continue
        width = o.hi - o.lo
        v.overflow[el.id] = el.area if el.area is not None else width * (el.cut or 0.0) * 1e4
        v.over_rooms[el.id] = (o.sides[0], o.sides[1])


def _role(el: Element) -> str:
    return el.role if isinstance(el, Air) else ""


def _pairs(d: Derived) -> None:
    m, v = d.model, d.vent
    for el in m.of_kind("fan"):
        assert isinstance(el, Fan)
        if el.pair is None:
            continue
        other = m.get(el.pair.id)
        if not isinstance(other, Fan):
            continue
        if other.mode != "alt":
            v.bad_pairs.append((el.id, f"its pair {other.id} is not a push-pull unit"))
        elif other.pair is not None and other.pair.id != el.id:
            v.bad_pairs.append((el.id, f"its pair {other.id} names {other.pair.id} as its pair"))
        elif el.pair.id in v.pairs and v.pairs[el.pair.id] != el.id:
            v.bad_pairs.append((el.id, f"{other.id} is already paired with {v.pairs[other.id]}"))
        else:
            v.pairs[el.id], v.pairs[other.id] = other.id, el.id


class Placer:
    def __init__(self, d: Derived) -> None:
        self.d = d
        self.mounts = Mounts(d)
        self.arch: Resolver = self.mounts.arch

    def place(self, el: Element) -> Mounted:
        g = self.d.arch
        if isinstance(el, Ahu):
            rg = g.rooms.get(el.host.id)
            if rg is None:
                raise Unresolved(el.host.id, missing=True)
            if el.at is not None:
                x, y = self.arch.point(el.at.x, "x"), self.arch.point(el.at.y, "y")
            else:
                c = rg.fin.centroid
                p = c if rg.fin.contains(c) else rg.fin.representative_point()
                x, y = p.x, p.y
            lv = g.levels[rg.level]
            return Mounted(el.id, el.kind, rg.level, (x, y), lv.z + el.z, rg.id, width=0.6)
        host = self.d.model.get(el.host.id) if isinstance(el, Air | Fan | Inlet) else None
        if isinstance(el, Air) and host is not None and host.kind == "room":
            if el.role in ("oda", "eha"):
                raise GeoError(
                    f"{el.id} takes {el.role} air: put it on an exterior wall, not in a room",
                    f"~ {el.id} host=<wall> y=<anchor> z=<height>",
                    "E-VENT-002",
                )
            return self._in_room(el)
        mt: Any = self.mounts._on_wall(el.id, el)  # pyright: ignore[reportPrivateUsage]
        return mt

    def _in_room(self, el: Air) -> Mounted:
        mt: Mounted = self.mounts._in_room(el.id, el)  # pyright: ignore[reportPrivateUsage]
        return mt


def vent_signatures(d: Derived) -> dict[str, tuple[float | str, ...]]:
    v = d.vent
    out: dict[str, tuple[float | str, ...]] = {
        k: (round(x.point[0], 4), round(x.point[1], 4), round(x.z, 4)) for k, x in v.at.items()
    }
    for (_, role), net in v.ducts.items():
        for s in net.sections:
            out[f"{role}:{s.name}"] = (round(s.length, 3),)
    return out


def fan_flow(d: Derived, el: Element) -> float | None:
    t = vent_type(d, el, FanType, "fan")
    return t.flow if t is not None else None


def ahu_type(d: Derived, el: Element) -> AhuType | None:
    return vent_type(d, el, AhuType, "ahu")


def inlet_flow(d: Derived, el: Element) -> float | None:
    t = vent_type(d, el, InletType, "inlet")
    return t.flow if t is not None else None

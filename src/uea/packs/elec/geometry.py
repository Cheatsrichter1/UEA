"""What the electrical elements add up to: circuits with their load, and what switches what.

Positions come from `uea.packs.mount`. A luminaire belongs to the circuit of the switches that
control it; the connected load of a circuit is its luminaires, connections and feeds
(sockets draw no declared load).
"""

from contextlib import suppress
from dataclasses import dataclass, field

from uea.derive import Derived, Unresolved
from uea.packs.elec.kinds import Circ, Conn, Feed, Rcd, Switch
from uea.packs.elec.values import Breaker
from uea.packs.light.geometry import lum_type
from uea.packs.mount import Mounts

VOLT = 230.0
"""Phase voltage, V."""
MOUNTED = ("board", "sock", "conn", "switch", "data", "smoke")


@dataclass
class CircGeo:
    id: str
    rcd: str
    board: str | None
    breaker: Breaker
    phases: int
    devices: list[str] = field(default_factory=list[str])
    """Sockets, connections, switches and feeds on it."""
    lums: list[str] = field(default_factory=list[str])
    """Luminaires, from the switches that control them."""
    load_w: float = 0.0

    @property
    def capacity_w(self) -> float:
        """What its breaker carries: rated current times 230 V, per phase."""
        return self.breaker.amps * VOLT * self.phases


@dataclass
class ElecGeo:
    circuits: dict[str, CircGeo] = field(default_factory=dict[str, CircGeo])
    controls: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """Luminaire id: the switches that control it."""
    lum_circuits: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """Luminaire id: the circuits of those switches."""


def switching(n: int) -> str:
    """The circuit of a luminaire by the number of switches that control it."""
    return "single" if n == 1 else "two-way" if n == 2 else "intermediate"


def derive_elec(d: Derived) -> None:
    m = d.model
    e = d.elec = ElecGeo()
    mounts = Mounts(d)
    for kind in MOUNTED:
        for el in m.of_kind(kind):
            with suppress(Unresolved):
                mounts.place(el.id)
    for el in m.of_kind("circ"):
        assert isinstance(el, Circ)
        rcd = m.get(el.rcd.id)
        board = rcd.board.id if isinstance(rcd, Rcd) else None
        e.circuits[el.id] = CircGeo(el.id, el.rcd.id, board, el.breaker, el.p)
    for kind in ("sock", "conn", "switch", "feed"):
        for el in m.of_kind(kind):
            cg = e.circuits.get(getattr(el, "circuit").id)  # noqa: B009
            if cg is None:
                continue
            cg.devices.append(el.id)
            if isinstance(el, Conn | Feed) and el.w:
                cg.load_w += el.w
    for sw in m.of_kind("switch"):
        assert isinstance(sw, Switch)
        for ref in (r for g in sw.ctl.groups for r in g):
            lst = e.controls.setdefault(ref.id, [])
            if sw.id not in lst:
                lst.append(sw.id)
            cs = e.lum_circuits.setdefault(ref.id, [])
            if sw.circuit.id not in cs:
                cs.append(sw.circuit.id)
    for lum_id, circuits in e.lum_circuits.items():
        el = m.get(lum_id)
        if el is None or el.kind != "lum" or len(circuits) != 1:
            continue
        cg = e.circuits.get(circuits[0])
        if cg is None:
            continue
        cg.lums.append(lum_id)
        t = lum_type(m, el)
        if t is not None and t.w:
            cg.load_w += t.w


def elec_signatures(d: Derived) -> dict[str, tuple[float, ...]]:
    """Where each device is, to report what follows a change."""
    return {
        k: (round(v.point[0], 4), round(v.point[1], 4), round(v.z, 4), round(v.s, 4))
        for k, v in d.mounts.items()
        if v.kind != "lum"
    }

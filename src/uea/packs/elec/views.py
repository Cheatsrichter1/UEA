"""Derived values of electrical elements, for `uea get`."""

from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ids, ln
from uea.packs.elec.geometry import switching
from uea.packs.elec.kinds import Circ, Rcd, Switch
from uea.packs.light.views import where


def circuit_text(d: Derived, circuit: str) -> str:
    cg = d.elec.circuits.get(circuit)
    if cg is None:
        return circuit
    return f"{circuit} {cg.rcd} {cg.board or '?'}"


def describe(d: Derived, el: Element) -> list[str]:
    e = d.elec
    mt = d.mounts.get(el.id)
    if el.kind == "lum":
        sws = e.controls.get(el.id, [])
        if not sws:
            return ["not controlled by a switch"]
        cs = " ".join(e.lum_circuits[el.id])
        return [f"switched by {ids(sws)} ({cs}): {switching(len(sws))}"]
    if el.kind in ("sock", "conn", "switch") and mt is not None:
        text = f"{where(mt)} | {circuit_text(d, getattr(el, 'circuit').id)}"  # noqa: B009
        if isinstance(el, Switch):
            n = len(el.ctl.groups)
            text += f" | {n} channel{'s' if n > 1 else ''}{' dimmer' if el.dim else ''}"
        elif el.kind == "sock":
            text += f" | {getattr(el, 'n')} outlet(s)"  # noqa: B009
        return [text]
    if el.kind in ("board", "data", "smoke") and mt is not None:
        return [where(mt)]
    if isinstance(el, Circ):
        cg = e.circuits.get(el.id)
        if cg is None:
            return []
        kinds: dict[str, int] = {}
        for k in cg.devices:
            kinds[d.model[k].kind] = kinds.get(d.model[k].kind, 0) + 1
        what = " ".join(f"{n} {k}" for k, n in kinds.items())
        if cg.lums:
            what += f" {len(cg.lums)} lum"
        return [
            f"{cg.rcd} {cg.board or '?'} | {el.cable.fmt()} {el.breaker.fmt()}"
            f" {cg.phases}P {cg.phase} | {what.strip() or 'nothing'}"
            f" | load {cg.load_w:.0f} W of {cg.capacity_w:.0f} W"
        ]
    if isinstance(el, Rcd):
        cs = [c.id for c in d.elec.circuits.values() if c.rcd == el.id]
        return [
            f"{el.board.id} | {ln(el.rating.amps)} A {el.rating.idn * 1000:g} mA type {el.type}"
            f" | circuits {ids(cs) or 'none'}"
        ]
    return []

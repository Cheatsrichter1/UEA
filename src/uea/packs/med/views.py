"""Derived values of the medical and hospital systems, for `uea get`."""

from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ids, ln
from uea.packs.light.views import where
from uea.packs.med.kinds import Call, Detector, GasOutlet, GasSrc, ItSys, MedLoc, Safety


def describe(d: Derived, el: Element) -> list[str]:
    g = d.med
    out: list[str] = []
    mt = g.at.get(el.id)
    if mt is not None:
        out.append(where(mt))
    if isinstance(el, GasOutlet):
        parts: list[str] = []
        for gas in el.gas_list:
            up = g.pipe_to(el.id, gas)
            parts.append(f"{gas} from {up[0]} {up[1]:.1f} m" if up else f"{gas} no source")
        out.append(" | ".join(parts))
    elif isinstance(el, GasSrc):
        net = g.nets.get((el.id, el.gas))
        if net is None:
            out.append(f"{el.gas}: no outlets")
        else:
            ends = [k for k in net.nodes if k != el.id]
            out.append(f"{el.gas} {ids(ends)} | pipes {net.total:.1f} m")
    elif isinstance(el, Detector):
        out.append(el.sensor)
    elif isinstance(el, Call):
        line = el.role
        if el.door is not None:
            room = next((r for r, ls in g.signalled.items() if el.id in ls), None)
            line += f" for {room or '?'} (door {el.door.id})"
        out.append(line)
    elif isinstance(el, MedLoc):
        it = f" | IT system {el.it.id}" if el.it is not None else ""
        out.append(f"{el.room.id} group {el.group}{it}")
    elif isinstance(el, ItSys):
        locs = [
            x.id
            for x in d.model.of_kind("medloc")
            if isinstance(x, MedLoc) and x.it is not None and x.it.id == el.id
        ]
        kva = f"{ln(el.kva)} kVA | " if el.kva is not None else ""
        sv = f" | behind {el.sv.id}" if el.sv is not None else " | no safety source"
        out.append(f"{kva}supplies {ids(locs) or 'nothing'}{sv}")
    elif isinstance(el, Safety):
        kw = f" {ln(el.kw)} kW" if el.kw is not None else ""
        behind = [
            x.id
            for x in d.model.of_kind("itsys")
            if isinstance(x, ItSys) and x.sv is not None and x.sv.id == el.id
        ]
        out.append(f"{el.source}{kw}" + (f" | feeds {ids(behind)}" if behind else ""))
    return out

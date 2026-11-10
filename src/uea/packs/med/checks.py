"""Validators of the medical and hospital systems (decision 0058).

They are planning rules and cite no norm: what a fire alarm, a nurse call system and a group 2
location need is fixed by the Brandschutzkonzept, the clinic and the standards the planner applies
(DIN VDE 0100-710, DIN VDE 0833-2, DIN VDE 0834, DIN EN ISO 7396-1), not by UEA. Where a rule does
not fit a room, waive it there with a reason. The fire alarm and nurse call rules apply only once
the project has a panel of that system: a building without one has not planned it yet.
"""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.packs.med.kinds import GASES, Call, GasOutlet, GasSrc, ItSys, MedLoc, Safety
from uea.packs.net import missing_holes

CODES: dict[str, str] = {
    "E-MED-002": "device on a wall without a usable face",
    "W-MED-001": "gas outlet whose gas has no source",
    "W-MED-003": "gas pipes that change storey through a slab with no hole for them",
    "W-MED-004": "gas source that supplies no outlet",
    "W-MED-010": "room without an automatic fire detector, in a building with a fire alarm panel",
    "W-MED-011": "storey with fire detectors but no manual call point",
    "W-MED-012": "fire detectors or manual call points, and no fire alarm panel",
    "W-MED-020": "bedroom without a bed call, in a building with a nurse call panel",
    "W-MED-021": "bath or WC without a pull call, in a building with a nurse call panel",
    "W-MED-022": "room with bed calls that no door lamp signals",
    "W-MED-023": "nurse call devices, and no nurse call panel",
    "W-MED-030": "group 2 medical location without an IT system",
    "W-MED-031": "group 1 or 2 medical locations, and no safety power source",
    "W-MED-032": "medical IT system without a safety power source",
    "W-MED-033": "group 2 medical location whose IT system is not behind a ups or battery",
    "W-MED-034": "medical IT system that supplies no medical location",
    "W-MED-035": "two medical locations for one room",
    "W-MED-040": "panel, IT system or gas plant that no circuit feeds",
}
NO_DETECTOR = frozenset({"bath", "wc"})
"""Room uses without a detector by default: wet rooms without fire load (waive others)."""
FED = ("fpanel", "cpanel", "itsys")
"""Kinds that need power from the electrical design; plus the gas plants in POWERED."""
POWERED = frozenset({"air", "air8", "vac", "agss"})
"""Gases made by a machine (compressor, vacuum pump, extraction), not stored in cylinders."""


def med_checks(d: Derived) -> Iterable[Issue]:
    m, g = d.model, d.med
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, others))

    rooms = {el.id: el for el in m.of_kind("room")}

    # ---------- medical gases ----------
    have = {el.gas for el in m.of_kind("gsrc") if isinstance(el, GasSrc)}
    for el in m.of_kind("gas"):
        assert isinstance(el, GasOutlet)
        missing = [x for x in el.gas_list if x not in have]
        if missing and el.id in g.at:
            add(
                "W-MED-001",
                el.id,
                f"takes {', '.join(missing)}, and no source supplies"
                f" {'it' if len(missing) == 1 else 'them'}",
                f"+ gsrc _ <room> {missing[0]} at=<x,y>  ({GASES[missing[0]]})",
            )
    supplying = {src for (src, _) in g.nets}
    for el in m.of_kind("gsrc"):
        if el.id in g.at and el.id not in supplying:
            add(
                "W-MED-004",
                el.id,
                f"supplies no outlet: no gas outlet takes {getattr(el, 'gas')}",  # noqa: B009
                f"add outlets: gas <wall> {getattr(el, 'gas')} x=<anchor>, or - {el.id}",  # noqa: B009
            )
    out += missing_holes(g.crossings, "W-MED-003", "med")

    # ---------- fire alarm ----------
    panels = [el.id for el in m.of_kind("fpanel")]
    dets = [el.id for el in m.of_kind("fdet")]
    mcps = [el.id for el in m.of_kind("mcp")]
    if (dets or mcps) and not panels:
        first = (dets or mcps)[0]
        add(
            "W-MED-012",
            first,
            f"{len(dets)} detectors and {len(mcps)} manual call points, and no fire alarm panel",
            "+ fpanel _ <wall> y=<anchor>",
        )
    if panels:
        for rid, room in rooms.items():
            use = getattr(room, "use")  # noqa: B009
            if rid in d.arch.rooms and use not in NO_DETECTOR and rid not in g.detectors:
                add(
                    "W-MED-010",
                    rid,
                    f"has no automatic fire detector ({use}), and the building has a fire alarm"
                    " system",
                    f"+ fdet _ {rid}, or waive it with the Brandschutzkonzept's reason",
                )
    with_det = {g.at[k].level for k in dets if k in g.at}
    with_mcp = {g.at[k].level for k in mcps if k in g.at}
    for lv in d.arch.level_order():
        if lv in with_det and lv not in with_mcp:
            first = next(k for k in dets if k in g.at and g.at[k].level == lv)
            add(
                "W-MED-011",
                first,
                f"{lv} has fire detectors but no manual call point",
                "+ mcp _ <wall> x=<anchor>, at the exits and stair doors",
            )

    # ---------- nurse call ----------
    cpanels = [el.id for el in m.of_kind("cpanel")]
    calls = [el for el in m.of_kind("call") if isinstance(el, Call)]
    if calls and not cpanels:
        add(
            "W-MED-023",
            calls[0].id,
            f"{len(calls)} nurse call devices, and no nurse call panel",
            "+ cpanel _ <wall> x=<anchor>, at the nurses' station",
        )
    if cpanels:
        for rid, room in rooms.items():
            if rid not in d.arch.rooms:
                continue
            use = getattr(room, "use")  # noqa: B009
            has = g.calls.get(rid, {})
            if use == "bedroom" and "bed" not in has:
                add(
                    "W-MED-020",
                    rid,
                    "is a bedroom without a bed call, and the building has a nurse call system",
                    f"+ call _ <wall face of {rid}> bed y=<anchor>, one per bed",
                )
            if use in ("bath", "wc") and "pull" not in has:
                add(
                    "W-MED-021",
                    rid,
                    f"is a {use} without a pull call, and the building has a nurse call system",
                    f"+ call _ <wall face of {rid}> pull y=<anchor>",
                )
    for rid, has in g.calls.items():
        if "bed" in has and rid not in g.signalled:
            add(
                "W-MED-022",
                rid,
                "has bed calls, and no door lamp signals it in the corridor",
                f"+ call _ <corridor wall face> lamp x=<door>.c door=<door into {rid}>",
            )

    # ---------- medical locations, IT systems, safety power ----------
    locs = [el for el in m.of_kind("medloc") if isinstance(el, MedLoc)]
    sources = {el.id: el for el in m.of_kind("safety") if isinstance(el, Safety)}
    its = {el.id: el for el in m.of_kind("itsys") if isinstance(el, ItSys)}
    seen: dict[str, str] = {}
    for el in locs:
        if el.room.id in seen:
            add(
                "W-MED-035",
                el.id,
                f"{el.room.id} is already the medical location {seen[el.room.id]}",
                f"- {el.id}",
                seen[el.room.id],
            )
            continue
        seen[el.room.id] = el.id
        if el.group == 2 and el.it is None:
            add(
                "W-MED-030",
                el.id,
                f"{el.room.id} is group 2 and no medical IT system supplies it",
                f"+ itsys @it <wall> y=<anchor> sv=<safety>, then ~ {el.id} it=@it",
            )
        if el.group == 2 and el.it is not None:
            it = its.get(el.it.id)
            sv = sources.get(it.sv.id) if it is not None and it.sv is not None else None
            if it is not None and sv is not None and sv.source == "genset":
                add(
                    "W-MED-033",
                    el.id,
                    f"{el.room.id} is group 2, and its IT system {it.id} is behind {sv.id}, a"
                    " genset only: it needs a source without a break",
                    f"+ safety @u <room> ups kw=<kW>, then ~ {it.id} sv=@u",
                    it.id,
                )
    if any(el.group >= 1 for el in locs) and not sources:
        first = next(el for el in locs if el.group >= 1)
        add(
            "W-MED-031",
            first.id,
            "the building has group 1 or 2 medical locations, and no safety power source",
            "+ safety _ <room> genset kw=<kW>, and a ups for the group 2 locations",
        )
    used = {el.it.id for el in locs if el.it is not None}
    for k, it in its.items():
        if it.sv is None:
            add(
                "W-MED-032",
                k,
                "has no safety power source behind it",
                f"~ {k} sv=<safety>",
            )
        if k not in used:
            add(
                "W-MED-034",
                k,
                "supplies no medical location",
                f"~ <medloc> it={k}, or - {k}",
            )

    # ---------- power from the electrical design ----------
    fed = {getattr(el, "target").id for el in m.of_kind("feed")}  # noqa: B009
    need = [el.id for kind in FED for el in m.of_kind(kind)]
    need += [el.id for el in m.of_kind("gsrc") if isinstance(el, GasSrc) and el.gas in POWERED]
    for k in need:
        if k in g.at and k not in fed:
            add(
                "W-MED-040",
                k,
                f"is a {m[k].kind} that no circuit feeds",
                f"in elec.uea: + feed _ {k} <circuit> w=<W>",
            )
    return out

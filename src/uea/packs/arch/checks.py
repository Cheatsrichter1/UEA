"""Architektur validators."""

from collections.abc import Iterable

from uea.core.issues import Issue
from uea.derive import Derived
from uea.fmt import ar, ln
from uea.packs.arch.geometry import ArchGeo
from uea.packs.arch.kinds import Door, FloorType, Room, Win

CODES: dict[str, str] = {
    "E-ARCH-001": "opening outside its wall",
    "E-ARCH-002": "openings overlap in one wall",
    "E-ARCH-003": "opening higher than its wall",
    "E-ARCH-004": "door opens into a room that is not next to it",
    "W-ARCH-005": "door handing incomplete (into= without din= or the other way round)",
    "E-ARCH-006": "window sill below OKFF",
    "E-ARCH-007": "niche as deep as its wall or deeper",
    "E-ARCH-008": "new opening in a demolished wall",
    "W-ARCH-010": "wall without a height yet (no storey or roof above)",
    "E-ARCH-011": "walls overlap",
    "E-ARCH-020": "room seed not in a free region",
    "E-ARCH-021": "two rooms in one region",
    "W-ARCH-022": "region without a room",
    "W-ARCH-023": "room floor build-up differs from the storey's fb",
    "E-ARCH-030": "slab without an outline",
    "W-ARCH-031": "two slabs on one storey",
    "W-ARCH-032": "void outside its slab",
    "W-ARCH-033": "stair runs into a slab without a void",
    "W-ARCH-034": "stair outside the Schrittmaßregel 2h+a = 0.59-0.65 m",
    "W-ARCH-035": "stair not inside a room",
    "E-ARCH-040": "roof without an outline",
    "W-ARCH-041": "roof outline is not a rectangle",
    "W-ARCH-050": "two default types in one category",
    "W-ARCH-051": "door or window without type and no default type",
}


def arch_checks(d: Derived) -> Iterable[Issue]:
    g: ArchGeo = d.arch
    m = d.model
    out: list[Issue] = []

    def add(code: str, el: str, msg: str, fix: str | None = None, *others: str) -> None:
        out.append(Issue(code, el, msg, fix, tuple(others)))

    # openings
    by_host: dict[str, list[str]] = {}
    for o in g.openings.values():
        by_host.setdefault(o.host, []).append(o.id)
        w = g.walls[o.host]
        a = o.axis
        if o.lo < w.s0 - 1e-6 or o.hi > w.s1 + 1e-6:
            add(
                "E-ARCH-001",
                o.id,
                f"{a} {ln(o.lo)}..{ln(o.hi)} lies outside {w.id} ({a} {ln(w.s0)}..{ln(w.s1)})",
                f"move it along {w.id}",
                w.id,
            )
        lv = g.levels[w.level]
        top = w.top_min(o.lo, o.hi)
        if top is not None and lv.z + o.top > top + 1e-6:
            add(
                "E-ARCH-003",
                o.id,
                f"top at +{ln(lv.z + o.top)} is above the top of {w.id} (+{ln(top)})",
                "lower it or make it smaller",
                w.id,
            )
        if o.kind == "niche" and o.depth >= w.t - 1e-6:
            add(
                "E-ARCH-007",
                o.id,
                f"d={ln(o.depth)} but {w.id} is only {ln(w.t)} thick",
                "make it shallower, or use a door or window for a hole through the wall",
                w.id,
            )
        if o.status != "demolish" and w.status == "demolish":
            add(
                "E-ARCH-008",
                o.id,
                f"is {o.status} but its wall {w.id} is demolished",
                f"~ {o.id} demolish",
                w.id,
            )
        el = m[o.id]
        if isinstance(el, Win) and o.sill < -1e-6:
            add(
                "E-ARCH-006",
                o.id,
                f"sill at {ln(o.sill)} is below OKFF",
                "make it lower or set sill=",
            )
        if isinstance(el, Door):
            if el.into is not None and el.into.id in m and el.into.id not in o.sides:
                sides = " and ".join(s or "outside" for s in o.sides)
                add(
                    "E-ARCH-004",
                    o.id,
                    f"into={el.into.id}, but it connects {sides}",
                    "point into= at one of them",
                    el.into.id,
                )
            if (el.into is None) != (el.din is None):
                add(
                    "W-ARCH-005",
                    o.id,
                    "has into= without din= or din= without into=",
                    "give both: into=<room> din=l|r",
                )
    for host, ids in by_host.items():
        ids = sorted(ids, key=lambda k: g.openings[k].lo)
        for i, a in enumerate(ids):
            oa = g.openings[a]
            for b in ids[i + 1 :]:
                ob = g.openings[b]
                if ob.lo >= oa.hi - 1e-6:
                    break
                vert = oa.sill < ob.top - 1e-6 and ob.sill < oa.top - 1e-6
                same_face = oa.face is None or ob.face is None or oa.face == ob.face
                if vert and same_face:
                    add(
                        "E-ARCH-002",
                        b,
                        f"{ob.axis} {ln(ob.lo)}..{ln(ob.hi)} overlaps {a}"
                        f" ({ln(oa.lo)}..{ln(oa.hi)}) in {host}",
                        f"move {b} or {a}",
                        a,
                    )

    # walls
    ws = sorted(g.walls.values(), key=lambda w: w.id)
    for i, a in enumerate(ws):
        if not a.active:
            continue
        for b in ws[i + 1 :]:
            if b.level != a.level or not b.active:
                continue
            ov = a.poly.intersection(b.poly).area
            if ov > 1e-4:
                add(
                    "E-ARCH-011",
                    b.id,
                    f"overlaps {a.id} by {ln(ov)} m²",
                    "let one wall span to the other's face, e.g. y=w1..w3",
                    a.id,
                )

    # rooms
    for rg in g.rooms.values():
        el = m[rg.id]
        assert isinstance(el, Room)
        if el.floor is None:
            continue
        ft = m.get(el.floor.id)
        lv = g.levels[rg.level]
        if isinstance(ft, FloorType) and abs(ft.layers.total - lv.fb) > 1e-6:
            add(
                "W-ARCH-023",
                rg.id,
                f"floor {ft.id} is {ln(ft.layers.total)} thick, {lv.id} has fb={ln(lv.fb)}",
                "use a floor type of the storey's build-up height, or change fb",
                ft.id,
            )

    # slabs and voids
    seen: dict[str, str] = {}
    for s in g.slabs.values():
        if s.status == "demolish":
            continue
        if s.level in seen:
            add(
                "W-ARCH-031",
                s.id,
                f"is the second slab on {s.level} ({seen[s.level]})",
                None,
                seen[s.level],
            )
        seen.setdefault(s.level, s.id)
    for v in g.voids.values():
        s = g.slabs[v.slab]
        outside = v.poly.difference(s.outline).area
        if outside > 1e-4:
            add("W-ARCH-032", v.id, f"{ar(outside)} m² of it lie outside {s.id}", None, s.id)

    # stairs
    for st in g.stairs.values():
        if not 0.59 <= st.step <= 0.65:
            add(
                "W-ARCH-034",
                st.id,
                f"2h+a = 2x{ln(st.riser)}+{ln(st.tread)} = {ln(st.step)}, outside 0.59-0.65",
                "change n or tread",
            )
        slab = g.slab_on(st.to)
        if slab is not None:
            hole = sum(
                v.poly.intersection(st.poly).area for v in g.voids.values() if v.slab == slab.id
            )
            if st.poly.intersection(slab.outline).area > 1e-4 and hole < st.poly.area * 0.5:
                add(
                    "W-ARCH-033",
                    st.id,
                    f"runs into {slab.id} on {st.to}, which has no void over it",
                    f"+ void _ {slab.id} over={st.id}",
                    slab.id,
                )
        rooms = [
            rg.id for rg in g.rooms.values() if rg.level == st.level and rg.poly.intersects(st.poly)
        ]
        inside = sum(g.rooms[k].poly.intersection(st.poly).area for k in rooms)
        if inside < st.poly.area - 1e-3:
            add(
                "W-ARCH-035",
                st.id,
                f"only {ar(inside)} of {ar(st.poly.area)} m² lie in rooms on {st.level}",
            )

    # types
    defaults: dict[str, list[str]] = {}
    for t in m.of_kind("type"):
        if getattr(t, "default", False):
            defaults.setdefault(t.category or "", []).append(t.id)
    for cat, ids in defaults.items():
        if len(ids) > 1:
            add("W-ARCH-050", ids[1], f"is a second default {cat} type ({ids[0]})", None, ids[0])
    for kind, cat in (("door", "door"), ("win", "win")):
        if cat in defaults:
            continue
        for el in m.of_kind(kind):
            if getattr(el, "typ", None) is None:
                add(
                    "W-ARCH-051",
                    el.id,
                    f"has no typ= and there is no default {cat} type",
                    f"give typ= or mark a {cat} type default",
                )
    return out

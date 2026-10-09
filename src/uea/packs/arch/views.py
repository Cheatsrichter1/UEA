"""Short text views of derived architecture values, for `uea get` and `uea show`."""

import math
from typing import Literal

from uea.core.registry import natural
from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ar, ids, iv, ln, zz
from uea.packs.arch.geometry import ArchGeo, RoomGeo, WallGeo
from uea.packs.arch.kinds import Room


def _wall_height(w: WallGeo) -> str:
    if not w.top:
        return "h ?"
    hs = [z - w.bottom for _, z in w.top]
    lo, hi = min(hs), max(hs)
    return f"h {ln(lo)}" if abs(hi - lo) < 1e-6 else f"h {ln(lo)}..{ln(hi)}"


def _faces(g: ArchGeo, w: WallGeo) -> str:
    parts: list[str] = []
    for side, name in zip(("lo", "hi"), w.faces, strict=True):
        if w.ext == side:
            parts.append(f"{name}: outside")
            continue
        rooms = [rg.id for rg in g.rooms.values() if w.id in rg.bounds and _on_side(w, rg, side)]
        if rooms:
            parts.append(f"{name}: {' '.join(rooms)}")
    return " · ".join(parts)


def _on_side(w: WallGeo, rg: RoomGeo, side: str) -> bool:
    c = rg.poly.centroid
    v = w.c_of(c.x, c.y)
    return v < w.lo if side == "lo" else v > w.hi


def room_line(g: ArchGeo, rg: RoomGeo, el: Room) -> str:
    name = el.label or el.use
    return f"{rg.id} {name} {ar(rg.area_fin)}"


def describe_room(d: Derived, rg: RoomGeo) -> list[str]:
    g = d.arch
    out: list[str] = []
    parts: list[str] = []
    sizes: tuple[Literal["shell", "fin"], ...] = ("shell", "fin")
    for which in sizes:
        label = which
        dims = rg.dims(which)
        area = rg.area if which == "shell" else rg.area_fin
        parts.append(
            f"{label} {ln(dims[0])}x{ln(dims[1])}={ar(area)}" if dims else f"{label} {ar(area)}"
        )
    hr = rg.height_range()
    if hr is None:
        parts.append("h ? (no ceiling)")
    elif abs(hr[1] - hr[0]) < 1e-6:
        parts.append(f"h {ln(hr[0])}")
    else:
        parts.append(f"h {ln(hr[0])}..{ln(hr[1])}")
    vol = rg.volume
    if vol is not None:
        parts.append(f"V {ar(vol)}")
    out.append(" | ".join(parts))
    ops: list[str] = []
    for o in g.openings.values():
        if rg.id not in o.sides:
            continue
        if o.kind == "door":
            other = o.sides[1] if o.sides[0] == rg.id else o.sides[0]
            ops.append(f"{o.id}→{other or 'out'}")
        elif o.kind == "niche":
            if (o.face == "lo") == (o.sides[0] == rg.id):
                ops.append(o.id)
        else:
            ops.append(o.id)
    line = f"bounds {' '.join(rg.bounds)}"
    if ops:
        line += f" | openings {' '.join(ops)}"
    opens: list[str] = []
    for sid in rg.bounds:
        s = g.seps.get(sid)
        if s is None:
            continue
        for other in g.rooms.values():
            if other.id != rg.id and sid in other.bounds:
                opens.append(f"{other.id} over {sid}")
    if opens:
        line += f" | open to {', '.join(opens)}"
    out.append(line)
    stairs = [s.id for s in g.stairs.values() if s.level == rg.level and s.poly.intersects(rg.poly)]
    lv = g.levels[rg.level]
    floor = g.slab_on(rg.level)
    ceiling = g.slab_on(lv.above) if lv.above else None

    def holes(slab_id: str | None) -> list[str]:
        return [
            v.id
            for v in g.voids.values()
            if v.slab == slab_id and v.poly.intersection(rg.fin).area > 1e-4
        ]

    extra: list[str] = []
    if stairs:
        extra.append(f"stair {' '.join(stairs)}")
    if floor is not None and holes(floor.id):
        extra.append(f"floor opening {' '.join(holes(floor.id))}")
    if ceiling is not None and holes(ceiling.id):
        extra.append(f"ceiling opening {' '.join(holes(ceiling.id))}")
    if extra:
        out.append(" | ".join(extra))
    return out


def describe(d: Derived, el: Element) -> list[str]:
    g = d.arch
    m = d.model
    if el.kind == "wall" and el.id in g.walls:
        w = g.walls[el.id]
        if w.o == "d":
            (ax, ay), (bx, by) = w.end_points()
            angle = math.degrees(math.atan2(w.udir[1], w.udir[0]))
            pos = f"a {ln(ax)},{ln(ay)} b {ln(bx)},{ln(by)} ({ln(round(angle, 1))}°)"
        else:
            pos = f"{w.across} {iv(w.lo, w.hi)} {w.along} {iv(w.s0, w.s1)}"
        fin = w.t + w.layers.before_core() + w.layers.after_core()
        kind = "ext" if w.ext else "int"
        out = [f"{pos} | L {ln(w.length)} t {ln(w.t)} (fin {ln(fin)}) | {_wall_height(w)} | {kind}"]
        faces = _faces(g, w)
        hosts = [o.id for o in g.openings.values() if o.host == w.id]
        line = faces
        if hosts:
            line += (" | " if line else "") + f"hosts {ids(hosts)}"
        if line:
            out.append(line)
        return out
    if el.kind in ("door", "win", "niche") and el.id in g.openings:
        o = g.openings[el.id]
        sides = " | ".join(s or "outside" for s in o.sides)
        if o.kind == "niche":
            room = o.sides[0] if o.face == "lo" else o.sides[1]
            sides = room or "outside"
        z = (
            f"sill {ln(o.sill)} head {ln(o.top)}"
            if o.kind != "door" or o.sill
            else f"z 0..{ln(o.top)}"
        )
        return [f"{o.axis} {iv(o.lo, o.hi)} in {o.host} | {z} | {sides}"]
    if el.kind == "room" and el.id in g.rooms:
        return describe_room(d, g.rooms[el.id])
    if el.kind == "stair" and el.id in g.stairs:
        s = g.stairs[el.id]
        head = f"{s.n} risers {ln(s.riser)}, tread {ln(s.tread)}, 2h+a {ln(s.step)}"
        where = f"x {iv(s.x0, s.x1)} y {iv(s.y0, s.y1)}"
        if s.shape == "straight":
            return [f"{head} | run {ln(s.run)} w {ln(s.w)} | {where}"]
        turn = f"{s.winders} winders" if s.winders else "landing"
        flights = "+".join(str(p.risers) for p in s.parts if p.kind == "flight")
        return [
            f"{head} | {s.shape} turn {s.turn}, {flights} risers, {turn} | w {ln(s.w)}"
            f" | {where} = {ar(s.poly.area)} m²"
        ]
    if el.kind == "slab" and el.id in g.slabs:
        s = g.slabs[el.id]
        x0, y0, x1, y1 = s.outline.bounds
        voids = [v.id for v in g.voids.values() if v.slab == s.id]
        net = f", net {ar(s.net.area)} (voids {' '.join(voids)})" if voids else ""
        return [
            f"outline {ln(x1 - x0)}x{ln(y1 - y0)} = {ar(s.outline.area)} m²{net} | top {zz(s.top)}"
            f" core {ln(s.layers.core)} underside {zz(s.underside)}"
        ]
    if el.kind == "void" and el.id in g.voids:
        v = g.voids[el.id]
        x0, y0, x1, y1 = v.poly.bounds
        return [f"x {iv(x0, x1)} y {iv(y0, y1)} = {ar(v.poly.area)} m² in {v.slab}"]
    if el.kind == "roof" and el.id in g.roofs:
        rf = g.roofs[el.id]
        return [
            f"outline x {iv(rf.x0, rf.x1)} y {iv(rf.y0, rf.y1)}"
            f" | eaves on {' '.join(rf.eave_edges)}"
            f" | eaves {zz(rf.eaves_z)} ridge {zz(rf.ridge_z)} | rafter underside at eaves"
            f" {zz(rf.base)}"
        ]
    if el.kind == "sep" and el.id in g.seps:
        s = g.seps[el.id]
        axis = "y" if s.o == "h" else "x"
        other = "x" if s.o == "h" else "y"
        return [f"{axis} {ln(s.pos)} {other} {iv(s.s0, s.s1)}"]
    if el.kind == "section" and el.id in g.sections:
        sc = g.sections[el.id]
        return [f"cut {sc.axis} {ln(sc.coord)} looking {sc.look}"]
    if el.kind == "level" and el.id in g.levels:
        return level_summary(d, el.id)
    if el.kind == "type":
        users = m.referrers(el.id)
        if getattr(el, "default", False) and el.category is not None:
            implicit = [o.id for o in m.of_kind(el.category) if getattr(o, "type", None) is None]
            users = sorted({*users, *implicit}, key=natural)
        layers = getattr(el, "layers", None)
        out: list[str] = []
        if layers is not None:
            out.append(f"core {ln(layers.core)} total {ln(layers.total)}")
        out.append(f"used by {ids(users)}" if users else "unused")
        return [" | ".join(out)]
    if el.kind == "grid":
        users = m.referrers(el.id)
        return [f"used by {ids(users)}" if users else "unused"]
    return []


def level_summary(d: Derived, level: str) -> list[str]:
    g = d.arch
    m = d.model
    lv = g.levels[level]
    head = f" head={ln(lv.head)}" if lv.head is not None else ""
    counts: dict[str, int] = {}
    for kind in ("wall", "door", "win", "niche", "stair", "slab", "roof", "sep"):
        n = 0
        for el in m.of_kind(kind):
            lvl = _level_of(d, el)
            if lvl == level:
                n += 1
        if n:
            counts[kind] = n
    rooms = [rg for rg in g.rooms.values() if rg.level == level]
    total = sum(rg.area_fin for rg in rooms)
    hs = {round(rg.height, 3) for rg in rooms if rg.height is not None}
    h = f" h={ln(next(iter(hs)))}" if len(hs) == 1 else ""
    head_line = f"{level} z={ln(lv.z)} fb={ln(lv.fb)} ssl={ln(lv.ssl)}{head}{h}"
    parts = " ".join(f"{n} {k}" for k, n in counts.items())
    out = [f"{head_line} | {parts or 'empty'} | {len(rooms)} room {ar(total)} m² fin"]
    if rooms:
        items: list[str] = []
        for rg in rooms:
            el = m[rg.id]
            assert isinstance(el, Room)
            items.append(room_line(g, rg, el))
        out.append(" · ".join(items))
    return out


def _level_of(d: Derived, el: Element) -> str | None:
    g = d.arch
    lvl = getattr(el, "level", None)
    if lvl is not None:
        return lvl.id
    host = getattr(el, "host", None)
    if host is not None and host.id in g.walls:
        return g.walls[host.id].level
    slab = getattr(el, "slab", None)
    if slab is not None and slab.id in g.slabs:
        return g.slabs[slab.id].level
    return None


def level_of(d: Derived, el: Element) -> str | None:
    return _level_of(d, el)


def in_room(d: Derived, el: Element, room: str) -> bool:
    g = d.arch
    rg = g.rooms.get(room)
    if rg is None:
        return False
    if el.kind == "wall":
        return el.id in rg.bounds
    if el.kind in ("door", "win", "niche"):
        o = g.openings.get(el.id)
        return o is not None and room in o.sides
    if el.kind == "sep":
        return el.id in rg.bounds
    if el.kind == "stair":
        s = g.stairs.get(el.id)
        return s is not None and s.level == rg.level and s.poly.intersects(rg.poly)
    return el.id == room

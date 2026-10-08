"""Floor plan of one storey as a Drawing: rooms, walls, openings with door swings, stairs.

A working plan for agents and a preview for humans. Plans in German drafting conventions
(dimensions, hatches, symbols) are ROADMAP phase 2.
"""

import math

from shapely.geometry import Polygon

from uea.derive import Derived
from uea.export.drawing import Arc, Drawing, Line, Pen, Poly, Pt, Text
from uea.fmt import ar, zz
from uea.geom import polys
from uea.packs.arch.geometry import OpeningGeo, WallGeo
from uea.packs.arch.kinds import Door, Room
from uea.packs.project import Grid

THIN = Pen("#555555", 0.012)
GRID = Pen("#3366aa", 0.012, (0.4, 0.1, 0.05, 0.1))
SEP = Pen("#777777", 0.015, (0.15, 0.1))
DEMO = Pen("#d4a017", 0.025, (0.12, 0.08))
DOOR = Pen("#a04000", 0.015)
GLASS = Pen("#2266cc", 0.015)
UPPER = Pen("#777777", 0.012, (0.1, 0.07))

WALL_FILL = {"lb": "#333333", "nlb": "#808080", "existing": "#a8a8a8"}


def _ring(p: Polygon) -> tuple[list[Pt], list[list[Pt]]]:
    return (
        [(x, y) for x, y in list(p.exterior.coords)[:-1]],
        [[(x, y) for x, y in list(h.coords)[:-1]] for h in p.interiors],
    )


def _wall(dw: Drawing, w: WallGeo) -> None:
    pts, _ = _ring(w.poly)
    if w.status == "demolish":
        dw.add(Poly(pts, None, DEMO, "demolish"))
        return
    if w.status == "existing":
        fill = WALL_FILL["existing"]
    else:
        fill = WALL_FILL["lb"] if w.lb else WALL_FILL["nlb"]
    dw.add(Poly(pts, fill, None, "walls"))
    for side in ("lo", "hi"):
        f = w.finish(side)
        if f > 0:
            band = w.box(w.lo - f, w.lo) if side == "lo" else w.box(w.hi, w.hi + f)
            bp, _ = _ring(band)
            dw.add(Poly(bp, "#d8d8d0", None, "finish"))


def _opening(dw: Drawing, d: Derived, o: OpeningGeo) -> None:
    w = d.arch.walls[o.host]
    el = d.model[o.id]
    if o.kind == "niche":
        f = o.depth
        band = (w.hi - f, w.hi) if o.face == "hi" else (w.lo, w.lo + f)
        p = (
            [(o.lo, band[0]), (o.hi, band[0]), (o.hi, band[1]), (o.lo, band[1])]
            if w.o == "h"
            else [(band[0], o.lo), (band[1], o.lo), (band[1], o.hi), (band[0], o.hi)]
        )
        dw.add(Poly(p, "#ffffff", Pen("#2266cc", 0.012, (0.05, 0.05)), "openings"))
        return
    lo_f = w.lo - w.finish("lo")
    hi_f = w.hi + w.finish("hi")
    corners = [
        w.plan_point(o.lo, lo_f),
        w.plan_point(o.hi, lo_f),
        w.plan_point(o.hi, hi_f),
        w.plan_point(o.lo, hi_f),
    ]
    pen = DEMO if o.status == "demolish" else None
    dw.add(Poly(corners, "#ffffff", pen, "openings"))
    if o.kind == "win":
        for c in (w.lo, w.mid, w.hi):
            dw.add(Line(w.plan_point(o.lo, c), w.plan_point(o.hi, c), GLASS, "openings"))
        return
    assert isinstance(el, Door)
    for s in (o.lo, o.hi):
        dw.add(Line(w.plan_point(s, w.lo), w.plan_point(s, w.hi), THIN, "openings"))
    if el.into is None or el.hand is None:
        return
    into = el.into.id
    if o.sides[1] == into:
        side = "hi"
    elif o.sides[0] == into:
        side = "lo"
    else:
        return
    face = w.hi if side == "hi" else w.lo
    sgn = 1.0 if side == "hi" else -1.0
    if w.o == "h":
        hinge_hi = (el.hand == "l") == (side == "hi")
    else:
        hinge_hi = (el.hand == "l") == (side == "lo")
    hs, free = (o.hi, o.lo) if hinge_hi else (o.lo, o.hi)
    h = w.plan_point(hs, face)
    e = w.plan_point(hs, face + sgn * o.width)
    f = w.plan_point(free, face)
    dw.add(Line(h, e, DOOR, "openings"))
    ae = math.degrees(math.atan2(e[1] - h[1], e[0] - h[0]))
    af = math.degrees(math.atan2(f[1] - h[1], f[0] - h[0]))
    if (ae - af) % 360 <= 180:
        dw.add(Arc(h, o.width, af, ae, Pen("#a04000", 0.01), "openings"))
    else:
        dw.add(Arc(h, o.width, ae, af, Pen("#a04000", 0.01), "openings"))


def plan(d: Derived, level: str, batch: int | None = None) -> Drawing:
    g = d.arch
    m = d.model
    lv = g.levels[level]
    proj = m.of_kind("project")
    name = (proj[0].label or proj[0].id) if proj else "UEA"
    state = f", Stand Batch {batch}" if batch is not None else ""
    dw = Drawing(f"{name}: {level} {zz(lv.z)} · Rohbaumaße in m · UEA{state}")
    walls = [w for w in g.walls.values() if w.level == level]
    # grids
    x0, y0, x1, y1 = (0.0, 0.0, 1.0, 1.0)
    dom = g.domains.get(level)
    if dom is not None and not dom.is_empty:
        x0, y0, x1, y1 = dom.bounds
    for el in m.of_kind("grid"):
        assert isinstance(el, Grid)
        c = el.coord
        if el.axis == "x":
            a, b = (c, y0 - 0.8), (c, y1 + 0.8)
            dw.add(Line(a, b, GRID, "grids"))
            dw.add(Text((c, y0 - 1.1), el.label or el.id, 0.22, "#3366aa", layer="grids"))
        else:
            a, b = (x0 - 0.8, c), (x1 + 0.8, c)
            dw.add(Line(a, b, GRID, "grids"))
            dw.add(Text((x0 - 1.1, c - 0.08), el.label or el.id, 0.22, "#3366aa", layer="grids"))
    # rooms
    for rg in g.rooms.values():
        if rg.level != level:
            continue
        for p in polys(rg.fin):
            pts, holes = _ring(p)
            dw.add(Poly(pts, "#f5f5ee", THIN, "rooms", holes))
    # slab voids in this storey's floor, stairs arriving from below
    slab = g.slab_on(level)
    for v in g.voids.values():
        if slab is not None and v.slab == slab.id:
            vx0, vy0, vx1, vy1 = v.poly.bounds
            dw.add(Line((vx0, vy0), (vx1, vy1), UPPER, "voids"))
            dw.add(Line((vx0, vy1), (vx1, vy0), UPPER, "voids"))
    for s in g.stairs.values():
        if s.to == level:
            pts, _ = _ring(s.poly)
            dw.add(Poly(pts, None, UPPER, "stairs"))
        if s.level != level:
            continue
        pts, _ = _ring(s.poly)
        dw.add(Poly(pts, "#ffffff", Pen("#333333", 0.015), "stairs"))
        along_x = s.up in ("w", "e")
        lo, hi = (s.x0, s.x1) if along_x else (s.y0, s.y1)
        for i in range(1, s.n - 1):
            t = lo + i * s.tread
            a, b = ((t, s.y0), (t, s.y1)) if along_x else ((s.x0, t), (s.x1, t))
            dw.add(Line(a, b, Pen("#999999", 0.008), "stairs"))
        mid = (s.y0 + s.y1) / 2 if along_x else (s.x0 + s.x1) / 2
        start, end = (hi, lo) if s.up in ("w", "s") else (lo, hi)
        p0 = (start, mid) if along_x else (mid, start)
        p1 = (end, mid) if along_x else (mid, end)
        red = Pen("#cc0000", 0.015)
        dw.add(Line(p0, p1, red, "stairs"))
        sgn = 1 if end > start else -1
        for k in (-1, 1):
            tip = (
                (end - sgn * 0.2, mid + k * 0.12) if along_x else (mid + k * 0.12, end - sgn * 0.2)
            )
            dw.add(Line(p1, tip, red, "stairs"))
        dw.add(Text(p0, s.id, 0.13, "#cc0000", layer="labels"))
    # walls and openings
    for w in walls:
        _wall(dw, w)
    for o in g.openings.values():
        if o.level == level:
            _opening(dw, d, o)
    for sp in g.seps.values():
        if sp.level == level:
            (ax, ay), (bx, by) = sp.line.coords
            dw.add(Line((ax, ay), (bx, by), SEP, "rooms"))
    # labels
    for rg in g.rooms.values():
        if rg.level != level:
            continue
        el = m[rg.id]
        assert isinstance(el, Room)
        at = rg.fin.centroid
        if not rg.fin.contains(at):
            at = rg.fin.representative_point()
        dw.add(
            Text(
                (at.x, at.y + 0.1), f"{rg.id} {el.label or el.use}", 0.2, bold=True, layer="labels"
            )
        )
        dw.add(Text((at.x, at.y - 0.2), f"{ar(rg.area_fin)} m²", 0.17, layer="labels"))
    for w in walls:
        mid_s = (w.s0 + w.s1) / 2
        p = w.plan_point(mid_s, w.mid)
        dw.add(
            Text(
                (p[0], p[1] - 0.05),
                w.id,
                0.12,
                "#ffffff" if w.t > 0.2 else "#000000",
                layer="labels",
            )
        )
    for o in g.openings.values():
        if o.level != level:
            continue
        w = g.walls[o.host]
        off = w.hi + 0.25 if w.ext != "hi" else w.lo - 0.35
        p = w.plan_point(o.mid, off)
        dw.add(Text(p, o.id, 0.12, "#a04000", layer="labels"))
    return dw

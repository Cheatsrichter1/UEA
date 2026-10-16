"""The LV derived from the model: numbers (OZ) and quantities of the positions (decision 0048).

Each position counts the elements its selector names (`uea find` grammar) with a measure whose
meaning per kind is fixed here, so agents never compute a quantity themselves.
"""

import shlex
from collections.abc import Callable
from dataclasses import dataclass, field

from uea.core.issues import Issue
from uea.core.schema import Element
from uea.derive import Derived
from uea.fmt import ar, ids
from uea.packs.arch.quantities import roof_areas, wall_qty
from uea.packs.lv.kinds import Pos, Title
from uea.query import matches

UNITS: dict[str, str] = {
    "n": "St",
    "len": "m",
    "area": "m2",
    "vol": "m3",
    "heat": "m",
    "water": "m",
    "drain": "m",
    "duct": "m",
}

Measure = Callable[[Derived, Element], float | None]
"""A measure of one element; None where the model cannot give it yet (a wall with no top)."""


def _wall_len(d: Derived, el: Element) -> float | None:
    w = d.arch.walls.get(el.id)
    return w.length if w is not None else None


def _wall_area(d: Derived, el: Element) -> float | None:
    w = d.arch.walls.get(el.id)
    return wall_qty(d.arch, w).net if w is not None else None


def _wall_vol(d: Derived, el: Element) -> float | None:
    w = d.arch.walls.get(el.id)
    return wall_qty(d.arch, w).volume if w is not None else None


def _slab_area(d: Derived, el: Element) -> float | None:
    s = d.arch.slabs.get(el.id)
    return s.net.area if s is not None else None


def _slab_vol(d: Derived, el: Element) -> float | None:
    s = d.arch.slabs.get(el.id)
    return s.net.area * s.layers.core if s is not None else None


def _room_area(d: Derived, el: Element) -> float | None:
    r = d.arch.rooms.get(el.id)
    return r.area_fin if r is not None else None


def _room_vol(d: Derived, el: Element) -> float | None:
    r = d.arch.rooms.get(el.id)
    return r.volume if r is not None else None


def _roof_area(d: Derived, el: Element) -> float | None:
    rf = d.arch.roofs.get(el.id)
    return roof_areas(d.arch, [rf.level]).get(el.id) if rf is not None else None


def _opening_area(d: Derived, el: Element) -> float | None:
    o = d.arch.openings.get(el.id)
    return (o.hi - o.lo) * (o.top - o.sill) if o is not None else None


def _cable(d: Derived, el: Element) -> float | None:
    r = d.elec.routes.get(el.id)
    return r.total if r is not None else None


def _data(d: Derived, el: Element) -> float | None:
    r = d.elec.homeruns.get(el.id)
    return r.length * int(getattr(el, "n", 1)) if r is not None else None


def _loop(d: Derived, el: Element) -> float | None:
    lp = d.heat.loops.get(el.id)
    return lp.pipe if lp is not None else None


def _heat(d: Derived, el: Element) -> float | None:
    net = d.heat.nets.get(el.id)
    return 2 * net.total if net is not None else None


def _water(d: Derived, el: Element) -> float | None:
    p = d.plumb
    nets = [n for n in (p.cold, p.hot.get(el.id)) if n is not None and n.root == el.id]
    return sum(n.total for n in nets) if nets else None


def _drain(d: Derived, el: Element) -> float | None:
    net = d.plumb.drain
    return net.total if net is not None and net.root == el.id else None


def _duct(d: Derived, el: Element) -> float | None:
    nets = [n for (unit, _), n in d.vent.ducts.items() if unit == el.id]
    return sum(n.total for n in nets) if nets else None


MEASURES: dict[str, dict[str, Measure]] = {
    "len": {"wall": _wall_len, "circ": _cable, "data": _data, "ufh": _loop},
    "area": {
        "wall": _wall_area,
        "slab": _slab_area,
        "room": _room_area,
        "roof": _roof_area,
        "door": _opening_area,
        "win": _opening_area,
    },
    "vol": {"wall": _wall_vol, "slab": _slab_vol, "room": _room_vol},
    "heat": {"gen": _heat, "tank": _heat, "man": _heat},
    "water": {"meter": _water, "tank": _water},
    "drain": {"sewer": _drain},
    "duct": {"ahu": _duct, "fan": _duct},
}
"""What each measure means per kind; `n` counts any kind."""

MEANING = {
    "n": "count of the elements",
    "len": "wall: length · circ: cable length · data: cable length times ports · ufh: pipe",
    "area": "wall: net elevation area · slab: net area · room: finished floor area · roof:"
    " sloped area · door, win: structural opening area",
    "vol": "wall: core volume · slab: core volume · room: volume",
    "heat": "gen, tank, man: heating pipes from it, flow and return",
    "water": "meter: cold drinking-water pipes · tank: hot drinking-water pipes",
    "drain": "sewer: waste-water pipes",
    "duct": "ahu, fan: its ducts",
}


@dataclass
class Qty:
    value: float
    unit: str
    counted: list[str] = field(default_factory=list[str])
    """The elements it counts."""
    missing: list[str] = field(default_factory=list[str])
    """Selected elements the measure gives nothing for yet."""


@dataclass
class LvGeo:
    oz: dict[str, str] = field(default_factory=dict[str, str])
    """Number of each title (01) and position (01.0010)."""
    qty: dict[str, Qty] = field(default_factory=dict[str, Qty])
    positions: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    """The positions of each title, in order."""
    issues: list[Issue] = field(default_factory=list[Issue])

    def total(self, pos: Pos) -> float | None:
        q = self.qty.get(pos.id)
        return q.value * pos.ep if q is not None and pos.ep is not None else None


def parse_sel(d: Derived, sel: str) -> tuple[str, list[str]]:
    """The kind and the filters of a selector; ValueError says what is wrong."""
    try:
        parts = shlex.split(sel)
    except ValueError as e:
        raise ValueError(f"sel={sel!r} cannot be read: {e}") from None
    if not parts:
        raise ValueError('sel= is empty: give a kind and filters, e.g. sel="wall type=AW-365"')
    kind, filters = parts[0], parts[1:]
    if kind not in d.model.reg.kinds and kind != "type":
        raise ValueError(f"sel={sel!r}: unknown kind {kind!r}")
    return kind, filters


def _quantity(d: Derived, pos: Pos) -> Qty:
    if pos.fix is not None:
        assert pos.unit is not None
        return Qty(pos.fix, pos.unit)
    assert pos.measure is not None and pos.sel is not None
    kind, filters = parse_sel(d, pos.sel)
    fn: Measure | None = None
    if pos.measure != "n":
        fn = MEASURES[pos.measure].get(kind)
        if fn is None:
            has = ["n", *(k for k, v in MEASURES.items() if kind in v)]
            raise ValueError(f"a {kind} has no measure {pos.measure}; it has {' '.join(has)}")
    els = [e for e in d.model.of_kind(kind) if matches(d, e, filters)]
    q = Qty(0.0, UNITS[pos.measure])
    for e in els:
        v = 1.0 if fn is None else fn(d, e)
        if v is None:
            q.missing.append(e.id)
        else:
            q.value += v
            q.counted.append(e.id)
    return q


def _numbers(d: Derived, lv: LvGeo) -> None:
    m = d.model
    # of_kind gives natural id order: T2 before T10, p2 before p10
    titles = [t for t in m.of_kind("title") if isinstance(t, Title)]
    for i, t in enumerate(titles, 1):
        lv.oz[t.id] = t.oz or f"{i:02d}"
        lv.positions[t.id] = []
    for p in m.of_kind("pos"):
        assert isinstance(p, Pos)
        if p.title.id in lv.positions:
            lv.positions[p.title.id].append(p.id)
    for tid, pids in lv.positions.items():
        for k, pid in enumerate(pids, 1):
            p = m[pid]
            assert isinstance(p, Pos)
            lv.oz[pid] = f"{lv.oz[tid]}.{p.oz or f'{k * 10:04d}'}"
    seen: dict[str, str] = {}
    for k in [*lv.positions, *(p for ps in lv.positions.values() for p in ps)]:
        if lv.oz[k] in seen:
            lv.issues.append(
                Issue(
                    "E-LV-004",
                    k,
                    f"has the number {lv.oz[k]}, as {seen[lv.oz[k]]} has",
                    f"pin another one with oz=, or ~ {k} oz=",
                    (seen[lv.oz[k]],),
                )
            )
        else:
            seen[lv.oz[k]] = k


def derive_lv(d: Derived) -> None:
    lv = LvGeo()
    d.lv = lv
    _numbers(d, lv)
    counted_by: dict[tuple[str, str], str] = {}
    for p in d.model.of_kind("pos"):
        assert isinstance(p, Pos)
        try:
            q = _quantity(d, p)
        except ValueError as e:
            lv.issues.append(
                Issue("E-LV-001", p.id, str(e), "uea help lv lists the measures per kind")
            )
            continue
        lv.qty[p.id] = q
        if p.fix is not None:
            continue
        if not q.counted and not q.missing:
            lv.issues.append(
                Issue(
                    "W-LV-002",
                    p.id,
                    f"sel={p.sel!r} counts nothing",
                    f"check it with uea find {p.sel}",
                )
            )
        if q.missing:
            lv.issues.append(
                Issue(
                    "W-LV-005",
                    p.id,
                    f"{ids(q.missing)}: no {p.measure} yet, so they are not in the quantity",
                    "give them what the measure needs (a wall its height), then check again",
                    tuple(q.missing),
                )
            )
        assert p.measure is not None
        for e in q.counted:
            other = counted_by.get((p.measure, e))
            if other is not None:
                lv.issues.append(
                    Issue(
                        "W-LV-003",
                        p.id,
                        f"counts {e} with measure {p.measure}, as {other} does",
                        "narrow one of the selectors, or waive it if both are meant",
                        (other,),
                    )
                )
                break
            counted_by[(p.measure, e)] = p.id


def lv_checks(d: Derived) -> list[Issue]:
    return list(d.lv.issues)


def lv_signatures(d: Derived) -> dict[str, tuple[float, ...]]:
    """The quantity of each position: a batch reports which positions follow its change."""
    return {k: (round(q.value, 3),) for k, q in d.lv.qty.items()}


def describe(d: Derived, el: Element) -> list[str]:
    lv = d.lv
    if isinstance(el, Title):
        pids = lv.positions.get(el.id, [])
        out = f"{lv.oz.get(el.id, '?')} · {len(pids)} positions"
        prices = [t for p in pids if (t := lv.total(_pos(d, p))) is not None]
        if prices:
            out += f" · {ar(sum(prices))} € for {len(prices)} priced"
        return [out]
    if isinstance(el, Pos):
        q = lv.qty.get(el.id)
        if q is None:
            return [lv.oz.get(el.id, "?")]
        out = f"{lv.oz.get(el.id, '?')} · {_num(q.value)} {q.unit}"
        total = lv.total(el)
        if total is not None:
            out += f" · {ar(total)} €"
        lines = [out]
        if q.counted:
            lines.append(f"counts {len(q.counted)}: {ids(q.counted)}")
        return lines
    return []


def _pos(d: Derived, k: str) -> Pos:
    p = d.model[k]
    assert isinstance(p, Pos)
    return p


def _num(v: float) -> str:
    """A quantity: 3 decimals for measured values, none for whole numbers."""
    return f"{v:g}" if v == int(v) else f"{v:.3f}"

"""Loads and their takedown to the foundation (decision 0040), the first calculator of phase 8.

A `norm` calculator, not yet reviewed. Characteristic actions per DIN EN 1991-1-1 with the unit
weights, imposed loads and partition surcharges from the office's tables, the partial factors of
DIN EN 1990 from the office's table:

    slab      G = A · Σ t·γ (its layers) + Σ_rooms A_room · Σ t·γ (their floor build-up)
              Q = Σ_rooms A_room · (q_k(use) + q_partition)
    shares    each point of the slab to its nearest load-bearing wall below (the bisectors of
              the field, 45° in a rectangle), on a grid of GRID; a wall takes G and Q in
              proportion to its area
    wall      G_own = Σ t·γ (its layers) · its net elevation area
    takedown  from the top storey down: a wall passes what it carries to the load-bearing walls
              under it, in proportion to the overlap of the cores
    footing   n_k = (G + Q) / L, n_d = (γ_G · G + γ_Q · Q) / L, b ≥ n_d / σ_R,d

A light partition (not load-bearing) is not carried by a wall: its weight per metre selects the
surcharge from the table, which is added to the imposed load of the slab it stands on.
"""

from dataclasses import dataclass, field

import numpy as np
import shapely

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec, Table
from uea.core.registry import natural
from uea.core.values import Layers
from uea.derive import Derived
from uea.export.tables import wall_qty
from uea.packs.arch.geometry import SlabGeo, WallGeo
from uea.packs.arch.kinds import FloorType, Room, RoomUse
from uea.packs.struct.model import lowest, slab_supports, stands_on

VERSION = "0.1.0"
NORM = "DIN EN 1991-1-1:2010-12 mit NA; DIN EN 1990:2010-12 mit NA"
USES: tuple[str, ...] = RoomUse.__args__  # type: ignore[attr-defined]
GRID = 0.05
"""The side of the cells a slab is shared out in (m)."""

UNIT_WEIGHT = Spec(
    "unit-weight",
    "Unit weights of building materials",
    "DIN EN 1991-1-1, Anhang A, or the manufacturer",
    (
        Col("material", "text", "material, as the layers name it"),
        Col("gamma", "num", "unit weight γ, kN/m³"),
    ),
    ("material",),
    "One row for each material the load-bearing walls, slabs, floors and partitions name.",
)
IMPOSED = Spec(
    "imposed-load",
    "Imposed loads on floors by room use",
    "DIN EN 1991-1-1/NA, Tabelle 6.1DE",
    (
        Col("use", "text", "room use, as UEA names it", USES),
        Col("qk", "num", "imposed load q_k, kN/m²", sign="zero"),
    ),
    ("use",),
    "One row for each use the rooms of the project have.",
)
PARTITION = Spec(
    "partition-load",
    "Surcharge for light partitions",
    "DIN EN 1991-1-1, 6.3.1.2(8), with NA",
    (
        Col("upto", "num", "weight of the partition up to, kN/m"),
        Col("qk", "num", "surcharge on the imposed load, kN/m²"),
    ),
    ("upto",),
    "A partition heavier than the last row is a line load, which this calculator does not take.",
)
FACTORS = Spec(
    "struct-factors",
    "Partial factors",
    "DIN EN 1990/NA, Tabelle NA.A.1.2(B)",
    (
        Col("name", "text", "which factor", ("gamma-g", "gamma-q")),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "γ_G for the permanent, γ_Q for the imposed actions.",
)
PARAMS = (
    Param(
        "soil",
        float,
        None,
        "design resistance of the soil σ_R,d under strip footings, kN/m², from the"
        " geotechnical report",
        optional=True,
    ),
)


@dataclass
class SlabLoad:
    id: str
    level: str
    area: float
    g_slab: float
    """kN/m² of its own layers."""
    floors: float
    """kN, the floor build-ups of the rooms on it."""
    imposed: float
    """kN, the rooms' imposed loads."""
    partition: float
    """kN/m², the surcharge for its partitions."""
    rooms: float
    """m², the rooms on it."""
    shares: dict[str, float] = field(default_factory=dict[str, float])
    """m² of it each load-bearing wall carries."""

    @property
    def g(self) -> float:
        return self.area * self.g_slab + self.floors

    @property
    def q(self) -> float:
        return self.imposed + self.partition * self.rooms


@dataclass
class WallLoad:
    id: str
    level: str
    length: float
    own: float
    """kN, its own weight."""
    g: float = 0.0
    q: float = 0.0
    """kN at its base: what it carries and its own weight."""
    on: list[tuple[str, float]] = field(default_factory=list[tuple[str, float]])
    """The walls it stands on and the share each takes."""


@dataclass
class Result:
    slabs: list[SlabLoad] = field(default_factory=list[SlabLoad])
    walls: dict[str, WallLoad] = field(default_factory=dict[str, WallLoad])
    partitions: dict[str, float] = field(default_factory=dict[str, float])
    """kN/m of each light partition."""
    heavy: list[str] = field(default_factory=list[str])
    """Partitions heavier than the table: line loads, not taken."""
    floating: list[str] = field(default_factory=list[str])
    """Load-bearing walls on no load-bearing wall below: their loads are not passed on."""
    ground: list[str] = field(default_factory=list[str])
    """Slabs on the ground: their loads go to the soil, not to the walls."""
    gamma_g: float = 0.0
    gamma_q: float = 0.0
    soil: float | None = None
    first: str = ""


def weight(layers: Layers, gamma: Table, what: str) -> float:
    """kN/m² of a build-up."""
    total = 0.0
    for x in layers.items:
        row = gamma.find(material=x.material)
        if row is None:
            raise ValueError(
                f"unit-weight has no row for {x.material} ({what}): add it to the table"
            )
        total += x.t * float(row["gamma"])
    return total


def shares(sl: SlabGeo, walls: list[WallGeo]) -> dict[str, float]:
    """The area of the slab nearest to each wall, on a grid (the walls by id, ties to the lower)."""
    x0, y0, x1, y1 = sl.net.bounds
    xs = np.arange(x0 + GRID / 2, x1, GRID)
    ys = np.arange(y0 + GRID / 2, y1, GRID)
    gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(sl.net, gx, gy)
    pts = shapely.points(gx[inside], gy[inside])
    dist = np.stack([shapely.distance(w.core, pts) for w in walls])  # pyright: ignore[reportUnknownMemberType]
    near = np.argmin(dist, axis=0)
    cell = GRID * GRID
    return {w.id: float(np.count_nonzero(near == i)) * cell for i, w in enumerate(walls)}


def calculate(d: Derived, env: Env) -> Result:
    g = d.arch
    m = d.model
    gamma = env.table(UNIT_WEIGHT)
    imposed = env.table(IMPOSED)
    part = env.table(PARTITION)
    fac = env.table(FACTORS)

    def factor(name: str) -> float:
        row = fac.find(name=name)
        if row is None:
            raise ValueError(f"struct-factors has no row for {name}")
        return float(row["value"])

    res = Result(gamma_g=factor("gamma-g"), gamma_q=factor("gamma-q"))
    res.soil = env.param("soil")
    first = lowest(g)
    if first is None:
        raise ValueError("there are no storeys")
    res.first = first
    rows = sorted(part.rows, key=lambda r: float(r["upto"]))
    # the walls: their own weight; the light partitions: their surcharge on their storey
    surcharge: dict[str, float] = {}
    for w in sorted(g.walls.values(), key=lambda w: natural(w.id)):
        if not w.active:
            continue
        qty = wall_qty(g, w)
        if qty.net is None:
            raise ValueError(f"{w.id} has no height yet (no slab or roof above it)")
        own = weight(w.layers, gamma, w.id) * qty.net
        if w.lb:
            res.walls[w.id] = WallLoad(w.id, w.level, w.length, own)
            continue
        if w.level == first:
            continue  # on the ground slab
        per_m = own / w.length
        res.partitions[w.id] = per_m
        row = next((r for r in rows if per_m <= float(r["upto"]) + 1e-9), None)
        if row is None:
            res.heavy.append(w.id)
            continue
        surcharge[w.level] = max(surcharge.get(w.level, 0.0), float(row["qk"]))
    # the slabs: their loads and who carries them
    for sl in sorted(g.slabs.values(), key=lambda s: natural(s.id)):
        if sl.status == "demolish":
            continue
        rooms = [r for r in g.rooms.values() if r.level == sl.level]
        floors = q = 0.0
        for rg in rooms:
            el = m[rg.id]
            assert isinstance(el, Room)
            ft = m.get(el.floor.id) if el.floor is not None else None
            if isinstance(ft, FloorType):
                floors += rg.area_fin * weight(ft.layers, gamma, f"floor of {rg.id}")
            row = imposed.find(use=el.use)
            if row is None:
                raise ValueError(f"imposed-load has no row for {el.use} ({rg.id})")
            q += rg.area_fin * float(row["qk"])
        g_slab = weight(sl.layers, gamma, sl.id)
        load = SlabLoad(
            sl.id,
            sl.level,
            sl.net.area,
            g_slab,
            floors,
            q,
            surcharge.get(sl.level, 0.0),
            sum(r.area_fin for r in rooms),
        )
        res.slabs.append(load)
        if sl.level == first:
            res.ground.append(sl.id)
            continue
        walls = slab_supports(g, sl)
        if not walls:
            raise ValueError(f"{sl.id} rests on no load-bearing wall")
        load.shares = shares(sl, walls)
        total = sum(load.shares.values())
        for k, a in load.shares.items():
            res.walls[k].g += load.g * a / total
            res.walls[k].q += load.q * a / total
    # the takedown, from the top storey down
    for lv in reversed(g.level_order()):
        for wl in [x for x in res.walls.values() if x.level == lv]:
            wl.g += wl.own
            if lv == first:
                continue
            wl.on = [(o.id, f) for o, f in stands_on(g, g.walls[wl.id])]
            if not wl.on:
                res.floating.append(wl.id)
            for k, f in wl.on:
                res.walls[k].g += wl.g * f
                res.walls[k].q += wl.q * f
    return res


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("loads takes the whole building: leave out the scope")
    res = calculate(d, env)
    lines = [
        f"γ_G {res.gamma_g:g}, γ_Q {res.gamma_q:g}"
        + (f", σ_R,d {res.soil:g} kN/m²" if res.soil else "")
    ]
    for s in res.slabs:
        head = (
            f"{s.id} {s.level}: {s.area:.1f} m², slab {s.g_slab:.2f} kN/m², floors {s.floors:.1f}"
            f" kN, imposed {s.imposed:.1f} kN"
            + (f" + partitions {s.partition:g} kN/m²" if s.partition else "")
            + f" → G {s.g:.1f} kN, Q {s.q:.1f} kN"
        )
        if s.id in res.ground:
            head += " (on the ground)"
        else:
            total = sum(s.shares.values())
            head += " on " + ", ".join(
                f"{k} {a:.1f} m² ({a / total:.0%})" for k, a in s.shares.items()
            )
        lines.append(head)
    for k in res.heavy:
        lines.append(
            f"{k}: {res.partitions[k]:.2f} kN/m, heavier than partition-load: a line load,"
            " not taken (not ok)"
        )
    for k in res.floating:
        lines.append(f"{k}: on no load-bearing wall below, its load not passed on (not ok)")
    for wl in sorted(res.walls.values(), key=lambda x: natural(x.id)):
        if wl.level != res.first:
            continue
        nk = (wl.g + wl.q) / wl.length
        nd = (res.gamma_g * wl.g + res.gamma_q * wl.q) / wl.length
        b = f", b ≥ {nd / res.soil:.2f} m" if res.soil else ""
        lines.append(
            f"{wl.id} {wl.level} base: G {wl.g:.1f} kN, Q {wl.q:.1f} kN over {wl.length:.2f} m:"
            f" n_k {nk:.1f} kN/m, n_d {nd:.1f} kN/m{b}"
        )
    data = {
        "slabs": {
            s.id: {
                "area": round(s.area, 3),
                "g_slab": round(s.g_slab, 4),
                "G": round(s.g, 3),
                "Q": round(s.q, 3),
                "shares": {k: round(a, 3) for k, a in s.shares.items()},
            }
            for s in res.slabs
        },
        "walls": {
            w.id: {
                "level": w.level,
                "own": round(w.own, 3),
                "G": round(w.g, 3),
                "Q": round(w.q, 3),
                "on": [k for k, _ in w.on],
            }
            for w in res.walls.values()
        },
        "partitions": {k: round(v, 3) for k, v in res.partitions.items()},
    }
    return Output(
        lines=lines,
        report=report(d, res),
        data=data,
        inputs={"soil": res.soil},
        ok=not (res.heavy or res.floating),
    )


def report(d: Derived, res: Result) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    out = [
        f"# Lastannahmen und Lastabtrag: {title}",
        "",
        "Charakteristische Einwirkungen nach DIN EN 1991-1-1 mit den Wichten, Nutzlasten und"
        " Trennwandzuschlägen aus den Tabellen des Büros; Teilsicherheitsbeiwerte nach"
        f" DIN EN 1990: γ_G = {de(res.gamma_g, 2)}, γ_Q = {de(res.gamma_q, 2)}.",
        "",
        "## Decken",
        "",
        md_table(
            [
                "Decke",
                "Geschoss",
                "A m²",
                "g Decke kN/m²",
                "Fußböden kN",
                "Nutzlast kN",
                "Trennw. kN/m²",
                "G kN",
                "Q kN",
                "Auflager",
            ],
            [
                [
                    s.id,
                    s.level,
                    de(s.area, 2),
                    de(s.g_slab, 2),
                    de(s.floors, 1),
                    de(s.imposed, 1),
                    de(s.partition, 2) if s.partition else "–",
                    de(s.g, 1),
                    de(s.q, 1),
                    "Baugrund"
                    if s.id in res.ground
                    else ", ".join(f"{k} {de(a, 1)} m²" for k, a in s.shares.items()),
                ]
                for s in res.slabs
            ],
            right=(2, 3, 4, 5, 6, 7, 8),
        ),
        "",
        "## Tragende Wände",
        "",
        md_table(
            ["Wand", "Geschoss", "L m", "Eigengewicht kN", "G kN", "Q kN", "steht auf"],
            [
                [
                    w.id,
                    w.level,
                    de(w.length, 2),
                    de(w.own, 1),
                    de(w.g, 1),
                    de(w.q, 1),
                    "Fundament" if w.level == res.first else ", ".join(k for k, _ in w.on) or "–",
                ]
                for w in sorted(res.walls.values(), key=lambda x: natural(x.id))
            ],
            right=(2, 3, 4, 5),
        ),
        "",
        "## Streifenfundamente",
        "",
    ]
    for w in sorted(res.walls.values(), key=lambda x: natural(x.id)):
        if w.level != res.first:
            continue
        nk = (w.g + w.q) / w.length
        nd = (res.gamma_g * w.g + res.gamma_q * w.q) / w.length
        b = f", erforderliche Breite b ≥ {de(nd / res.soil, 2)} m" if res.soil else ""
        out.append(
            f"- **{w.id}:** n_k = {de(nk, 1)} kN/m, n_d = {de(res.gamma_g, 2)} · G + "
            f"{de(res.gamma_q, 2)} · Q = {de(nd, 1)} kN/m{b}."
        )
    if res.partitions:
        out += ["", "## Leichte Trennwände", ""]
        for k, v in res.partitions.items():
            note = (
                " (schwerer als die Tabelle: Linienlast, nicht erfasst)" if k in res.heavy else ""
            )
            out.append(f"- {k}: {de(v, 2)} kN/m{note}")
    out += [
        "",
        "## Verfahren",
        "",
        "- Decken: Eigengewicht aus dem Schichtaufbau, Fußbodenaufbau und Nutzlast der Räume nach"
        " ihrer Nutzung; leichte Trennwände als Zuschlag zur Nutzlast.",
        "- Lastabtrag: jeder Punkt einer Decke auf die nächste tragende Wand darunter"
        f" (Winkelhalbierende, im Rechteckfeld 45°), auf einem Raster von {de(GRID * 100, 0)} cm.",
        "- Wände: Eigengewicht aus dem Schichtaufbau und der Ansichtsfläche abzüglich Öffnungen;"
        " Weitergabe an die tragenden Wände darunter nach der Überdeckung der Kerne.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Kein Dach, kein Schnee, kein Wind; keine Einzel- und Linienlasten, keine Unterzüge.",
        "- Lasten je Decke gleichmäßig verteilt; Durchlaufwirkung und Einspannung nicht"
        " berücksichtigt; Lasten je Wand gleichmäßig über die Länge.",
        "- Keine Kombinationsbeiwerte ψ, keine Bemessung von Wänden, Decken und Fundamenten.",
        "",
        "Berechnet aus dem Modell. Die Tragwerksplanung, ihre Prüfung und die Verantwortung liegen"
        " bei der unterzeichnenden Tragwerksplanerin oder dem unterzeichnenden Tragwerksplaner.",
        "",
    ]
    return "\n".join(out)


LOADS = Calculator(
    "loads",
    "Lastannahmen und Lastabtrag",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (UNIT_WEIGHT, IMPOSED, PARTITION, FACTORS),
)

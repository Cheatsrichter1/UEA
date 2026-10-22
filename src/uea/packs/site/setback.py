"""The Abstandsflächen per Landesbauordnung, against the plot (decision 0056).

A `norm` calculator. The Landesbauordnungen are Land law (amtliche Werke) and differ by Land in
the factor, the minimum and how steep roofs count, so the office copies its Land's values into
the table `setback` (like `full-storey`). What is implemented, after § 6 of the Musterbauordnung
that the Länder follow:

- In front of every exterior wall above the terrain lies its Abstandsfläche, as deep as factor
  × H, at least the minimum (§ 6 Abs. 5 MBO).
- H, the wall height, runs from the terrain to where the wall's outer face meets the roof's
  outer skin, or to the top of the wall (§ 6 Abs. 4 Satz 2). Along a gable it follows the gable,
  so the area follows the wall's shape.
- Steep roofs over an eaves wall add to H: `roof45` of the roof's height when it is steeper than
  45°, `roof70` of it when steeper than 70° (§ 6 Abs. 4 Satz 3).
- The Abstandsflächen lie on the plot itself; on a street they may reach to its middle
  (§ 6 Abs. 2).

Not covered: Abstandsflächen of two buildings on one plot towards each other, buildings that may
stand at the boundary without one (garages, § 6 Abs. 7 and 8), parts that project (§ 6 Abs. 6),
a sloping terrain, Land rules the table cannot express (the gable counted by its area, the
16-m privilege).
"""

import math
from dataclasses import dataclass, field
from itertools import pairwise

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from uea.calc import Calculator, Env, Output, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.fmt import ar
from uea.geom import clean, polys, union
from uea.packs.arch.geometry import RoofGeo
from uea.packs.project import Project
from uea.packs.site.kinds import Plot, streets

VERSION = "0.1.0"
NORM = "Abstandsflächen nach Landesbauordnung (§ 6 MBO)"
BEYOND = 0.01
"""m² of an Abstandsfläche beyond the allowed area that count, above rounding."""

SETBACK = Spec(
    "setback",
    "Abstandsflächen per Landesbauordnung",
    "the Landesbauordnung of the Land",
    (
        Col("land", "text", "the Land as the project's site= names it: DE-HE"),
        Col(
            "areas",
            "text",
            "the Baugebiete the row is for, as the plot's use= names them, joined by space; *"
            " for all others",
        ),
        Col("factor", "num", "depth as a share of the wall height H"),
        Col("min", "num", "least depth, m"),
        Col("roof45", "num", "share of a roof's height added to H above 45°", sign="zero"),
        Col("roof70", "num", "share of a roof's height added to H above 70°", sign="zero"),
    ),
    ("land", "areas"),
    "One row per Land and group of Baugebiete, from the current text of the Landesbauordnung"
    " (Abstandsflächen). A plot without use= takes the row with *.",
)


@dataclass
class Rule:
    land: str
    areas: str
    factor: float
    least: float
    roof45: float
    roof70: float


@dataclass
class Face:
    name: str
    """Storey and the direction the façade faces: OG-s, or OG-s2 for the second one."""
    level: str
    side: str
    """The direction it faces: n, e, s, w, or the angle."""
    length: float
    heights: list[float] = field(default_factory=list[float])
    depths: list[float] = field(default_factory=list[float])
    area: BaseGeometry = field(default_factory=Polygon)
    beyond: float = 0.0


def _rule(env: Env, site: str | None, use: str | None) -> Rule:
    if site is None:
        raise ValueError("the Abstandsflächen need the project's Land: ~ <project> site=DE-HE")
    table = env.table(SETBACK)
    rows = [r for r in table.rows if str(r["land"]).casefold() == site.casefold()]
    exact = [r for r in rows if use is not None and use in str(r["areas"]).split()]
    star = [r for r in rows if str(r["areas"]).strip() == "*"]
    pick = exact or star
    if not pick:
        what = f" and Baugebiet {use}" if use else " (a row with areas=*)"
        raise ValueError(f"setback has no row for {site}{what}")
    r = pick[0]
    nums = [r[k] for k in ("factor", "min", "roof45", "roof70")]
    assert all(isinstance(v, float) for v in nums)
    factor, least, r45, r70 = (float(v) for v in nums)
    return Rule(site, str(r["areas"]), factor, least, r45, r70)


def _skin(roofs: list[RoofGeo], x: float, y: float) -> float | None:
    """Top of the roof skin at a plan point: the highest roof over it, each the lowest plane."""
    at = Point(x, y)
    tops = [
        min(p(x, y) + rf.skin_of(p) for p in rf.planes)
        for rf in roofs
        if rf.over.distance(at) < 1e-3
    ]
    return max(tops) if tops else None


def _side(n: tuple[float, float]) -> str:
    deg = math.degrees(math.atan2(n[0], n[1])) % 360
    for name, a in (("n", 0), ("e", 90), ("s", 180), ("w", 270), ("n", 360)):
        if abs(deg - a) < 1:
            return name
    return f"{deg:.0f}°"


def _steep(rf: RoofGeo, a: tuple[float, float], b: tuple[float, float], rule: Rule) -> float:
    """What a steep roof adds to H over the façade edge a-b, if it is one of its eaves."""
    if rf.pitch <= 45:
        return 0.0
    eaves = {
        "s": ((rf.x0, rf.y0), (rf.x1, rf.y0)),
        "n": ((rf.x0, rf.y1), (rf.x1, rf.y1)),
        "w": ((rf.x0, rf.y0), (rf.x0, rf.y1)),
        "e": ((rf.x1, rf.y0), (rf.x1, rf.y1)),
    }
    edge = LineString([a, b])
    for side in rf.eave_edges:
        line = LineString(eaves[side])
        if edge.hausdorff_distance(line) < 0.5 or line.buffer(0.5).contains(edge):
            share = rule.roof70 if rf.pitch > 70 else rule.roof45
            return share * (rf.ridge_z - rf.eaves_z)
    return 0.0


def _breaks(roofs: list[RoofGeo], a: tuple[float, float], b: tuple[float, float]) -> list[float]:
    """Where along a-b (0 to 1) the roof skin bends: planes meeting, a roof's edge."""
    ts = {0.0, 1.0}
    planes = [(rf, p) for rf in roofs for p in rf.planes]
    for i, (ra, pa) in enumerate(planes):
        for rb, pb in planes[i + 1 :]:
            fa = pa(*a) + ra.skin_of(pa) - pb(*a) - rb.skin_of(pb)
            fb = pa(*b) + ra.skin_of(pa) - pb(*b) - rb.skin_of(pb)
            if (fa > 0) != (fb > 0) and fa != fb:
                ts.add(fa / (fa - fb))
    edge = LineString([a, b])
    for rf in roofs:
        cut = edge.intersection(rf.over.boundary)
        for g in [cut] if isinstance(cut, Point) else list(getattr(cut, "geoms", [])):
            if isinstance(g, Point):
                ts.add(edge.project(g, normalized=True))
    return sorted(t for t in ts if 0.0 <= t <= 1.0)


def faces(d: Derived, rule: Rule, terrain: float) -> list[Face]:
    """The Abstandsfläche in front of each edge of each storey's outline above the terrain."""
    from uea.packs.site.baunvo import storey_outline

    g = d.arch
    out: list[Face] = []
    for k in g.level_order():
        lv = g.levels[k]
        roofs = [rf for rf in g.roofs.values() if rf.level == k and rf.status != "demolish"]
        tops = [z for w in g.walls_on(k) if w.ext is not None for _, z in w.top]
        flat = g.levels[lv.above].ssl if lv.above is not None else max(tops, default=None)
        shape = storey_outline(g, k)
        for poly in polys(shape):
            # one edge per façade: the corners where walls join lie on its line
            simple = poly.simplify(0.001)
            ring = orient(simple if isinstance(simple, Polygon) else poly).exterior.coords[:-1]
            pts2 = [(float(x), float(y)) for x, y, *_ in ring]
            for a, b in zip(pts2, [*pts2[1:], pts2[0]], strict=True):
                length = math.dist(a, b)
                if length < 0.01:
                    continue
                n = ((b[1] - a[1]) / length, -(b[0] - a[0]) / length)
                add = max((_steep(rf, a, b, rule) for rf in roofs), default=0.0)
                prof: list[tuple[tuple[float, float], float]] = []
                for t in _breaks(roofs, a, b):
                    x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                    top = _skin(roofs, x, y)
                    if top is None:
                        top = flat
                    if top is not None:
                        prof.append(((x, y), top - terrain + add))
                if len(prof) < 2 or max(h for _, h in prof) <= 1e-9:
                    continue
                # a break where factor × H reaches the minimum
                lim = rule.least / rule.factor
                full: list[tuple[tuple[float, float], float]] = []
                for (p0, h0), (p1, h1) in pairwise(prof):
                    full.append((p0, h0))
                    if (h0 - lim) * (h1 - lim) < 0:
                        k_ = (lim - h0) / (h1 - h0)
                        full.append(
                            ((p0[0] + (p1[0] - p0[0]) * k_, p0[1] + (p1[1] - p0[1]) * k_), lim)
                        )
                full.append(prof[-1])
                f = Face("", k, _side(n), length)
                f.heights = [h for _, h in full]
                f.depths = [max(rule.factor * h, rule.least) for h in f.heights]
                near = [p for p, _ in full]
                far = [
                    (x + n[0] * dd, y + n[1] * dd)
                    for (x, y), dd in zip(near, f.depths, strict=True)
                ]
                f.area = clean(Polygon([*near, *reversed(far)]).buffer(0))
                out.append(f)
    seen: dict[str, int] = {}
    for f in out:
        key = f"{f.level}-{f.side}"
        seen[key] = seen.get(key, 0) + 1
        f.name = key if seen[key] == 1 else f"{key}{seen[key]}"
    return out


def allowed(pl: Plot, poly: Polygon) -> BaseGeometry:
    """The plot, and on each street edge the half of the street next to it."""
    pts = list(poly.exterior.coords)[:-1]
    strips: list[BaseGeometry] = [poly]
    for n, width in streets(pl.street).items():
        a, b = pts[n - 1], pts[n % len(pts)]
        band = LineString([a, b]).buffer(width / 2, cap_style="flat")
        strips.append(clean(band.difference(poly)))
    return union(strips)


def setback(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("the Abstandsflächen are for the whole building; give no scope")
    pg = d.site.plot
    if pg is None:
        raise ValueError("no plot: + plot _ outline=<x,y;x,y;...> (uea help plot)")
    pl = d.model[pg.id]
    assert isinstance(pl, Plot)
    projs = [p for p in d.model.of_kind("project") if isinstance(p, Project)]
    proj = projs[0] if projs else None
    if proj is None or proj.ground is None:
        raise ValueError("the terrain is needed: ~ <project> ground=<m relative to ±0.00>")
    rule = _rule(env, proj.site, pl.use)
    fs = faces(d, rule, proj.ground)
    ok_area = allowed(pl, pg.poly)
    over: list[Face] = []
    for f in fs:
        f.beyond = clean(f.area.difference(ok_area)).area
        if f.beyond > BEYOND:
            over.append(f)
    total = union(f.area for f in fs)
    lines = [
        f"{rule.land} ({rule.areas}): depth {rule.factor:g} H, at least {ar(rule.least)} m"
        + (
            f"; roofs over 45° add {rule.roof45:g}, over 70° {rule.roof70:g} of their height"
            if rule.roof45 or rule.roof70
            else ""
        ),
        f"{len(fs)} wall faces: depth {ar(min(min(f.depths) for f in fs))} to"
        f" {ar(max(max(f.depths) for f in fs))} m"
        if fs
        else "no exterior walls above the terrain",
    ]
    for f in over:
        lines.append(
            f"{f.name} ({ar(f.length)} m): H up to {ar(max(f.heights))} m, depth up to"
            f" {ar(max(f.depths))} m, {ar(f.beyond)} m² beyond the plot"
        )
    lines.append(
        "all on the plot" + (" or the street's half" if pl.street else "")
        if not over
        else f"{len(over)} of {len(fs)} reach beyond the plot"
    )
    return Output(
        lines=lines,
        report=_report(d, pl, rule, fs, over),
        data={
            "rule": {
                "land": rule.land,
                "areas": rule.areas,
                "factor": rule.factor,
                "min": rule.least,
                "roof45": rule.roof45,
                "roof70": rule.roof70,
            },
            "faces": [
                {
                    "face": f.name,
                    "level": f.level,
                    "side": f.side,
                    "length": round(f.length, 4),
                    "h": round(max(f.heights), 4),
                    "depth": round(max(f.depths), 4),
                    "beyond": round(f.beyond, 4),
                    "area": [[round(x, 4), round(y, 4)] for x, y in _coords(f.area)],
                }
                for f in fs
            ],
            "area": round(total.area, 4),
            "over": [f.name for f in over],
        },
        inputs={"terrain": proj.ground, "use": pl.use, "street": pl.street},
        ok=not over,
    )


def _coords(g: BaseGeometry) -> list[tuple[float, float]]:
    if isinstance(g, Polygon) and not g.is_empty:
        return [(float(x), float(y)) for x, y, *_ in g.exterior.coords][:-1]
    return []


def _report(d: Derived, pl: Plot, rule: Rule, fs: list[Face], over: list[Face]) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    areas = "alle Baugebiete" if rule.areas.strip() == "*" else rule.areas
    out = [
        f"# Abstandsflächen nach Landesbauordnung: {title}",
        "",
        f"Grundstück {pl.label or pl.id}"
        + (f", Baugebiet {pl.use}" if pl.use else "")
        + f". Regel {rule.land} ({areas}, Tabelle setback): Tiefe {de(rule.factor, 2)} H,"
        f" mindestens {de(rule.least)} m"
        + (
            f"; Dächer über 45° mit {de(rule.roof45, 2)}, über 70° mit {de(rule.roof70, 2)}"
            " ihrer Höhe zur Wandhöhe"
            if rule.roof45 or rule.roof70
            else ""
        )
        + ".",
        "",
    ]
    rows = [
        [
            f.level,
            f.side,
            de(f.length),
            f"{de(min(f.heights))} bis {de(max(f.heights))}"
            if max(f.heights) - min(f.heights) > 0.005
            else de(max(f.heights)),
            f"{de(min(f.depths))} bis {de(max(f.depths))}"
            if max(f.depths) - min(f.depths) > 0.005
            else de(max(f.depths)),
            de(f.beyond) if f.beyond > BEYOND else "–",
        ]
        for f in fs
    ]
    out += [
        md_table(
            ["Geschoss", "Richtung", "Länge m", "Wandhöhe H m", "Tiefe m", "außerhalb m²"],
            rows,
            (2, 3, 4, 5),
        ),
        "",
    ]
    if over:
        out += [
            "**Nicht auf dem Grundstück:** "
            + "; ".join(f"{f.level} {f.side} {de(f.beyond)} m²" for f in over),
            "",
        ]
    else:
        street = " oder bis zur Mitte der angrenzenden Straße" if pl.street else ""
        out += [f"Alle Abstandsflächen liegen auf dem Grundstück{street}.", ""]
    out += [
        "## Verfahren",
        "",
        "- Wandhöhe H: von der Geländeoberfläche (im Projekt angegeben, eben) bis zum Schnitt der"
        " Außenwandfläche mit der Dachhaut oder bis zum oberen Abschluss der Wand; an Giebeln"
        " entlang des Giebels.",
        "- Tiefe: Faktor × H, mindestens das Mindestmaß, senkrecht vor der Außenfläche der Wand"
        " (einschließlich Putz und Bekleidung).",
        "- Die Abstandsflächen müssen auf dem Grundstück liegen; an Straßen bis zu deren Mitte.",
        "",
        "## Nicht abgedeckt",
        "",
        "- Abstandsflächen mehrerer Gebäude auf einem Grundstück zueinander; Grenzbebauung"
        " (Garagen, Nebengebäude); vortretende Bauteile; geneigtes Gelände.",
        "- Landesregeln, die die Tabelle nicht ausdrückt (Giebelflächen nach Fläche,"
        " Schmalseitenprivileg).",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


SETBACK_CALC = Calculator(
    name="setback",
    title="Abstandsflächen per Landesbauordnung",
    kind="norm",
    version=VERSION,
    fn=setback,
    norm=NORM,
    tables=(SETBACK,),
)

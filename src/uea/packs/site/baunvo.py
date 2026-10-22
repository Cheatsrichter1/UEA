"""The measure of building use (Maß der baulichen Nutzung) per BauNVO, against the plot's limits.

A `norm` calculator. The BauNVO is a federal ordinance and the Landesbauordnungen are Land law,
both amtliche Werke, so their rules can be implemented and cited freely. What a Vollgeschoss is,
the BauNVO leaves to the Land (§ 20 Abs. 1), and the Länder define it differently; the office
copies its Land's values once into the table `full-storey` (decision 0055).

- § 19 Abs. 3: the plot's area is the area of its outline; the agent outlines the part of the
  plot that is building land (Bauland).
- § 19 Abs. 2: the Grundfläche (GR) is the area the building covers: the union of the outlines of
  its storeys at their outer faces, as for the BGF (`din277.outline`), of every storey whose top
  rises above the terrain. GRZ = GR / plot area.
- § 19 Abs. 4: storeys below the terrain count too (Nr. 3); the GRZ may be exceeded by them by up
  to 50 %, at most up to 0.8 (Satz 2), unless the plan says otherwise (grz2=).
- § 20 Abs. 1 with the Landesbauordnung: a storey is a Vollgeschoss when the top of its ceiling
  (the structural top of the slab above) rises more than `rise` above the terrain and its clear
  height is at least `height` over at least `share` of the floor area of the storey below it
  (`basis=below`) or of its own (`own`). The top storey has no slab above; the first test does not
  apply to it. Clear heights under a roof come from the roof's planes.
- § 20 Abs. 3: the Geschossfläche (GF) is the area of all Vollgeschosse at their outer faces.
  GFZ = GF / plot area.
- § 16 Abs. 2: the plan limits the GRZ or the GR, the GFZ or the GF, and the number of
  Vollgeschosse; each limit the plot gives is checked.

Not covered: garages, parking, driveways and Nebenanlagen (§ 19 Abs. 4 Nr. 1 and 2, not in the
model), Aufenthaltsräume in other storeys counted into the GF (§ 20 Abs. 3 Satz 2), § 21a, a
terrain that is not flat (the project's ground= is the terrain everywhere).
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from uea.calc import Calculator, Env, Output, data, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.fmt import ar
from uea.geom import clean, union
from uea.packs.arch.din277 import outline
from uea.packs.arch.geometry import ArchGeo
from uea.packs.project import Project
from uea.packs.site.kinds import Plot

VERSION = "0.1.0"
NORM = "BauNVO 2017, §§ 16, 19, 20; Vollgeschoss nach Landesbauordnung"
CAP = 0.8
"""§ 19 Abs. 4 Satz 2: the GRZ with Abs. 4 goes at most up to 0.8."""

FULL = Spec(
    "full-storey",
    "Vollgeschoss per Landesbauordnung",
    "the Landesbauordnung of the Land",
    (
        Col("land", "text", "the Land as the project's site= names it: DE-HE"),
        Col(
            "rise",
            "num",
            "the top of a storey's ceiling must rise more than this above the terrain, m",
            sign="zero",
        ),
        Col("height", "num", "clear height, m"),
        Col("share", "num", "over at least this share of the floor area, 0 to 1"),
        Col("basis", "text", "the floor area of the storey below or its own", ("below", "own")),
    ),
    ("land",),
    "One row per Land, from the current text of its Landesbauordnung (the definition of the"
    " Vollgeschoss). A Land with a rule this does not express (a Staffelgeschoss rule on the"
    " outer walls, a height in metres for the whole building) is not covered.",
)


@dataclass
class Storey:
    id: str
    area: float
    """Outline at the outer faces, m²."""
    rise: float | None
    """Top of its ceiling above the terrain; None for the top storey."""
    clear: float | None = None
    """Area with the clear height or more; None if unknown (no room on the storey)."""
    basis: float = 0.0
    full: bool | None = None


@dataclass
class Rule:
    land: str
    rise: float
    height: float
    share: float
    basis: str

    def text(self) -> str:
        of = "the storey below" if self.basis == "below" else "its floor"
        return (
            f"{self.land}: ceiling top > {ar(self.rise)} m above terrain, {ar(self.height)} m"
            f" clear over {self.share:.0%} of {of}"
        )


def _rule(env: Env, site: str | None) -> Rule | str:
    """The Land's Vollgeschoss rule, or why there is none."""
    if data.load(FULL) is None:
        return "Vollgeschosse, GF and GFZ need the table full-storey: uea data show full-storey"
    if site is None:
        return "Vollgeschosse need the project's Land: ~ <project> site=DE-HE"
    row = env.table(FULL).find(land=site)
    if row is None:
        return f"full-storey has no row for {site}: add the Land's Vollgeschoss rule"
    rise, height, share = row["rise"], row["height"], row["share"]
    assert isinstance(rise, float) and isinstance(height, float) and isinstance(share, float)
    if share > 1:
        raise ValueError(f"full-storey: share {share:g} for {site} is more than 1")
    return Rule(site, rise, height, share, str(row["basis"]))


def baunvo(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("the measure of use is for the whole plot; give no scope")
    pg = d.site.plot
    plots = d.model.of_kind("plot")
    if pg is None:
        raise ValueError(
            "no plot to measure: + plot _ outline=<x,y;x,y;...> (uea help plot)"
            if not plots
            else "the plot's outline has an error: uea check site"
        )
    pl = d.model[pg.id]
    assert isinstance(pl, Plot)
    projs = [p for p in d.model.of_kind("project") if isinstance(p, Project)]
    proj = projs[0] if projs else None
    if proj is None or proj.ground is None:
        raise ValueError("the terrain is needed: ~ <project> ground=<m relative to ±0.00>")
    terrain = proj.ground
    g = d.arch
    storeys: list[Storey] = []
    shapes: dict[str, BaseGeometry] = {}
    for k in g.level_order():
        lv = g.levels[k]
        shapes[k] = storey_outline(g, k)
        rise = g.levels[lv.above].ssl - terrain if lv.above is not None else None
        storeys.append(Storey(k, shapes[k].area, rise))
    above = [s.id for s in storeys if s.rise is None or s.rise > 1e-9]
    gr = union(shapes[k] for k in above).area
    gr2 = union(shapes.values()).area
    area = pg.area
    grz, grz2 = gr / area, gr2 / area
    rule = _rule(env, proj.site)
    lines = [f"plot {pg.id} {ar(area)} m²" + (f" ({pl.plan})" if pl.plan else "")]
    over: list[str] = []
    lines.append(f"GR {ar(gr)} m² · GRZ {grz:.3f}" + _limit(grz, pl.grz, "GRZ", over, 3))
    if pl.gr is not None:
        lines[-1] += f" · GR{_limit(gr, pl.gr, 'GR', over, 2)}"
    cap = pl.grz2 if pl.grz2 is not None else _cap(pl.grz)
    lines.append(
        f"with § 19 Abs. 4 (below ground) {ar(gr2)} m² · GRZ {grz2:.3f}"
        + _limit(grz2, cap, "GRZ with § 19 Abs. 4", over, 3)
        + "; garages, parking and driveways are not in the model"
    )
    gf: float | None = None
    n_full: int | None = None
    if isinstance(rule, str):
        lines.append(rule)
    else:
        unknown = _full(d, rule, storeys, shapes)
        marks: list[str] = []
        for s in storeys:
            if s.full is None:
                marks.append(f"{s.id} ?")
            elif s.full:
                marks.append(f"{s.id} yes")
            else:
                marks.append(f"{s.id} no ({_why(s, rule)})")
        lines.append(f"Vollgeschosse ({rule.text()}): {', '.join(marks)}")
        if unknown:
            lines.append(f"no room on {' '.join(unknown)}: its clear height is unknown")
        else:
            fulls = [s for s in storeys if s.full]
            gf, n_full = sum(s.area for s in fulls), len(fulls)
            gfz = gf / area
            line = f"GF {ar(gf)} m² · GFZ {gfz:.3f}" + _limit(gfz, pl.gfz, "GFZ", over, 3)
            if pl.gf is not None:
                line += f" · GF{_limit(gf, pl.gf, 'GF', over, 2)}"
            word = "Vollgeschoss" if n_full == 1 else "Vollgeschosse"
            line += f" · {n_full} {word}" + _limit(n_full, pl.storeys, "Vollgeschosse", over, 0)
            lines.append(line)
    if over:
        lines.append(f"over the plan's limits: {', '.join(over)}")
    complete = gf is not None
    return Output(
        lines=lines,
        report=_report(d, pl, area, storeys, gr, gr2, cap, rule, gf, n_full, over),
        data={
            "plot": pg.id,
            "area": round(area, 4),
            "gr": round(gr, 4),
            "grz": round(grz, 4),
            "gr2": round(gr2, 4),
            "grz2": round(grz2, 4),
            "gf": round(gf, 4) if gf is not None else None,
            "gfz": round(gf / area, 4) if gf is not None else None,
            "full": n_full,
            "storeys": [
                {
                    "id": s.id,
                    "area": round(s.area, 4),
                    "rise": round(s.rise, 4) if s.rise is not None else None,
                    "clear": round(s.clear, 4) if s.clear is not None else None,
                    "basis": round(s.basis, 4),
                    "full": s.full,
                }
                for s in storeys
            ],
            "over": over,
        },
        inputs={
            "terrain": terrain,
            "limits": {
                k: getattr(pl, k)
                for k in ("grz", "grz2", "gfz", "gr", "gf", "storeys")
                if getattr(pl, k) is not None
            },
        },
        ok=complete and not over,
    )


def storey_outline(g: ArchGeo, level: str) -> BaseGeometry:
    """The storey at its outer faces (`din277.outline`), without the part of its slab that
    nothing covers: a roof terrace on a setback storey is no floor of it, an attic under its
    roof is."""
    full = outline(g, level)
    lv = g.levels[level]
    cover = [rf.foot for rf in g.roofs.values() if rf.level == level and rf.status != "demolish"]
    if lv.above is not None:
        cover += [s.outline for s in g.slabs.values() if s.level == lv.above]
    slab = union(s.outline for s in g.slabs.values() if s.level == level)
    open_ = clean(slab.difference(union(cover)))
    return clean(full.difference(open_)) if open_.area > 1e-6 else full


def _cap(grz: float | None) -> float | None:
    """§ 19 Abs. 4 Satz 2: the GRZ plus 50 %, at most 0.8 (a GRZ of 0.8 or more stays)."""
    if grz is None:
        return None
    return max(grz, min(grz * 1.5, CAP))


def _limit(v: float, limit: float | None, name: str, over: list[str], places: int) -> str:
    if limit is None:
        return ""
    shown = f"{limit:.{places}f}" if places else f"{limit:g}"
    if v > limit + 1e-9:
        over.append(f"{name} {v:.{places}f} > {shown}" if places else f"{name} {v:g} > {shown}")
        return f" (max {shown}: over)"
    return f" (max {shown}: ok)"


def _full(
    d: Derived, rule: Rule, storeys: list[Storey], shapes: dict[str, BaseGeometry]
) -> list[str]:
    """Decide each storey; returns the storeys whose clear height is unknown."""
    g = d.arch
    unknown: list[str] = []
    for s in storeys:
        lv = g.levels[s.id]
        base = lv.below if rule.basis == "below" and lv.below is not None else s.id
        s.basis = shapes[base].area
        if s.rise is not None and s.rise <= rule.rise + 1e-9:
            s.full = False
            continue
        rooms = [rg for rg in g.rooms.values() if rg.level == s.id and rg.ceiling]
        if not rooms:
            unknown.append(s.id)
            continue
        s.clear = rooms[0].ceiling.at_least(shapes[s.id], rule.height).area
        s.full = s.clear >= rule.share * s.basis - 1e-6
    return unknown


def _why(s: Storey, rule: Rule) -> str:
    if s.rise is not None and s.rise <= rule.rise + 1e-9:
        return f"ceiling top {ar(s.rise)} m above terrain"
    assert s.clear is not None
    return f"{ar(s.clear)} of {ar(s.basis)} m² at {ar(rule.height)} m"


def _report(
    d: Derived,
    pl: Plot,
    area: float,
    storeys: list[Storey],
    gr: float,
    gr2: float,
    cap: float | None,
    rule: Rule | str,
    gf: float | None,
    n_full: int | None,
    over: list[str],
) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"

    def lim(v: float | None, places: int = 2) -> str:
        if v is None:
            return "–"
        return de(v, places) if places else f"{v:g}"

    out = [
        f"# Maß der baulichen Nutzung nach BauNVO: {title}",
        "",
        f"Grundstück {pl.label or pl.id}: {de(area)} m²"
        + (f". Festsetzungen: {pl.plan}." if pl.plan else "."),
        "",
    ]
    yes = {True: "ja", False: "nein", None: "–"}
    rows = [
        [
            s.id,
            de(s.area),
            de(s.rise) if s.rise is not None else "oberstes Geschoss",
            de(s.clear) if s.clear is not None else "–",
            de(s.basis) if s.basis else "–",
            yes[s.full],
        ]
        for s in storeys
    ]
    if isinstance(rule, Rule):
        of = "des darunter liegenden Geschosses" if rule.basis == "below" else "des Geschosses"
        out += [
            f"Vollgeschoss nach Landesbauordnung ({rule.land}, Tabelle full-storey):"
            f" Deckenoberkante im Mittel mehr als {de(rule.rise)} m über der Geländeoberfläche"
            f" und eine lichte Höhe von mindestens {de(rule.height)} m über mindestens"
            f" {de(rule.share * 100, 0)} % der Grundfläche {of}.",
            "",
            md_table(
                [
                    "Geschoss",
                    "Fläche (Außenmaße) m²",
                    "Deckenoberkante über Gelände m",
                    f"Fläche mit lichter Höhe ≥ {de(rule.height)} m m²",
                    "Bezugsfläche m²",
                    "Vollgeschoss",
                ],
                rows,
                (1, 2, 3, 4),
            ),
            "",
        ]
    rows2 = [
        ["Grundfläche GR (§ 19 Abs. 2)", de(gr), lim(pl.gr)],
        ["GRZ", de(gr / area, 3), lim(pl.grz, 3)],
        ["GRZ mit § 19 Abs. 4", de(gr2 / area, 3), lim(cap, 3)],
    ]
    if gf is not None and n_full is not None:
        rows2 += [
            ["Geschossfläche GF (§ 20 Abs. 3)", de(gf), lim(pl.gf)],
            ["GFZ", de(gf / area, 3), lim(pl.gfz, 3)],
            ["Zahl der Vollgeschosse", str(n_full), lim(pl.storeys, 0)],
        ]
    out += [
        "## Ergebnis",
        "",
        md_table(["Maß", "vorhanden", "zulässig"], rows2, (1, 2)),
        "",
    ]
    if isinstance(rule, str):
        out += ["Vollgeschosse, GF und GFZ fehlen: die Tabelle full-storey ist nicht installiert"
                " oder hat keine Zeile für das Land.", ""]  # fmt: skip
    if over:
        out += ["**Überschritten:** " + "; ".join(over), ""]
    out += [
        "## Verfahren",
        "",
        "- Grundstücksfläche (§ 19 Abs. 3): Fläche des im Modell angegebenen Grundstücksumrisses.",
        "- Grundfläche (§ 19 Abs. 2): Vereinigung der Geschossumrisse in den Außenmaßen"
        " (einschließlich Putz und Bekleidung) aller Geschosse, deren Deckenoberkante über der"
        " Geländeoberfläche liegt.",
        "- § 19 Abs. 4: zusätzlich die Geschosse unter der Geländeoberfläche (Nr. 3); zulässig"
        " die festgesetzte GRZ zuzüglich 50 %, höchstens 0,8, soweit der Plan nichts anderes"
        " festsetzt.",
        "- Vollgeschoss: Deckenoberkante ist die Oberkante der Rohdecke des darüber liegenden"
        " Geschosses; Geländeoberfläche ist die im Projekt angegebene Höhe. Lichte Höhen unter"
        " Dächern aus den Dachebenen.",
        "- Geschossfläche (§ 20 Abs. 3): Summe der Geschossumrisse in den Außenmaßen aller"
        " Vollgeschosse.",
        "",
        "## Nicht abgedeckt",
        "",
        "- Garagen, Stellplätze, Zufahrten und Nebenanlagen (§ 19 Abs. 4 Nr. 1 und 2): nicht im"
        " Modell.",
        "- Aufenthaltsräume in anderen Geschossen (§ 20 Abs. 3 Satz 2), § 21a BauNVO.",
        "- Geneigtes Gelände: die Geländeoberfläche ist überall die angegebene Höhe.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


BAUNVO = Calculator(
    name="baunvo",
    title="Measure of building use per BauNVO (GRZ, GFZ, Vollgeschosse)",
    kind="norm",
    version=VERSION,
    fn=baunvo,
    norm=NORM,
    tables=(FULL,),
)

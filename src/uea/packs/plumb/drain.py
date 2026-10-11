"""Waste-water pipe sizing (DIN 1986-100), decision 0035.

A `norm` calculator, not yet reviewed. For each section of the waste-water network derived from
the model (`geometry.py`), with the fixtures whose waste water it carries:

    Q_ww = K · √ΣDU, at least the largest single DU

    branch, one fixture   the fixture's DN
    branch, several       the smallest DN whose Q_max of an unvented collecting branch holds Q_ww
    stack                 the smallest DN whose Q_max of a stack with main vent holds Q_ww
    under the building    the smallest size that carries Q_ww at the slope and the filling h/d,
                          by Prandtl-Colebrook (hydraulics.py)

No section is smaller than one it takes water from. A fixture's branch, from the fixture to its
stack or the sewer, must stay within the length an unvented branch may have. DU and DN by
fixture, K by building use, the Q_max and lengths, k_b and the filling come from the office's
tables; the slope is the planner's.
"""

from dataclasses import dataclass, field
from math import sqrt

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec, Table
from uea.core.model import Model
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.hydraulics import gravity
from uea.packs.net import Net, Section
from uea.packs.pipes import Bore
from uea.packs.plumb.geometry import plumb_type
from uea.packs.plumb.kinds import FIXTURES, DrainType, San

VERSION = "0.1.0"
NORM = "DIN 1986-100:2016-12 mit DIN EN 12056-2"

FIXTURE_DRAIN = Spec(
    "fixture-drain",
    "Discharge unit and branch size by fixture",
    "DIN 1986-100",
    (
        Col("fixture", "text", "fixture, as UEA names it", FIXTURES),
        Col("du", "num", "discharge unit DU, l/s"),
        Col("dn", "num", "DN of its single branch"),
    ),
    ("fixture",),
    "One row for each fixture the project has.",
)
DRAIN_K = Spec(
    "drain-k",
    "Frequency factor K by building use",
    "DIN 1986-100",
    (
        Col("building", "text", "building use, as building= of the calculator names it"),
        Col("k", "num", "frequency factor K"),
    ),
    ("building",),
)
DRAIN_BRANCH = Spec(
    "drain-branch",
    "Unvented collecting branches",
    "DIN 1986-100",
    (
        Col("dn", "num", "DN"),
        Col("qmax", "num", "the highest Q_ww it may carry, l/s"),
        Col("lmax", "num", "the longest it may be, m"),
    ),
    ("dn",),
)
DRAIN_STACK = Spec(
    "drain-stack",
    "Stacks with main vent",
    "DIN 1986-100",
    (
        Col("dn", "num", "DN"),
        Col("qmax", "num", "the highest Q_ww it may carry, l/s"),
    ),
    ("dn",),
)
DRAIN_FACTORS = Spec(
    "drain-factors",
    "Values of the drainage sizing",
    "DIN 1986-100",
    (
        Col("name", "text", "which value", ("single-lmax", "kb", "fill")),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "single-lmax: the longest unvented branch to one fixture, m; kb: the roughness of the pipes"
    " under the building, mm; fill: the highest filling h/d they may run at.",
)
PARAMS = (
    Param("slope", float, None, "slope of the pipes under the building, %"),
    Param("building", str, "residential", "building use, a row of the table drain-k"),
)


@dataclass
class Sized:
    s: Section
    du: float
    q: float
    bore: Bore | None = None
    holds: float | None = None
    """What the chosen size may carry, l/s."""
    note: str = ""


@dataclass
class Branch:
    """A fixture's branch from the fixture to its stack or the sewer."""

    fixture: str
    length: float
    lmax: float
    single: bool


@dataclass
class Result:
    sized: list[Sized] = field(default_factory=list[Sized])
    branches: list[Branch] = field(default_factory=list[Branch])
    k: float = 0.0
    kb: float = 0.0
    fill: float = 0.0
    slope: float = 0.0


class Values:
    """The office's tables, read once."""

    def __init__(self, env: Env, fixtures: set[str]) -> None:
        self.env = env
        self.fixtures = env.table(FIXTURE_DRAIN)
        missing = sorted(x for x in fixtures if self.fixtures.find(fixture=x) is None)
        if missing:
            raise ValueError(f"the table fixture-drain has no row for {', '.join(missing)}: add it")
        building = env.param("building")
        row = env.table(DRAIN_K).find(building=building)
        if row is None:
            raise ValueError(f"the table drain-k has no row for the building use {building}")
        self.k = float(row["k"])
        self.branch = env.table(DRAIN_BRANCH)
        self.stack = env.table(DRAIN_STACK)
        f = env.table(DRAIN_FACTORS)
        got: dict[str, float] = {}
        for name in ("single-lmax", "kb", "fill"):
            r = f.find(name=name)
            if r is None:
                raise ValueError(f"the table drain-factors has no row for {name}")
            got[name] = float(r["value"])
        self.single_lmax, self.kb, self.fill = got["single-lmax"], got["kb"], got["fill"]
        if self.fill > 1:
            raise ValueError("fill in drain-factors is h/d and at most 1")

    def du(self, fixture: str) -> float:
        r = self.fixtures.find(fixture=fixture)
        assert r is not None
        return float(r["du"])

    def dn(self, fixture: str) -> int:
        r = self.fixtures.find(fixture=fixture)
        assert r is not None
        return int(float(r["dn"]))


def qmax(t: Table, dn: int) -> float | None:
    r = t.find(dn=float(dn))
    return float(r["qmax"]) if r is not None else None


def calculate(d: Derived, env: Env) -> Result:
    p, m = d.plumb, d.model
    net = p.drain
    if net is None:
        raise ValueError("there is no sewer connection, or nothing drains")
    slope: float = env.param("slope")
    if slope <= 0:
        raise ValueError("slope must be more than 0 (in %)")
    fixtures: dict[str, San] = {k: el for k in p.drains_to if isinstance(el := m[k], San)}
    vals = Values(env, {f.fixture for f in fixtures.values()})
    res = Result(k=vals.k, kb=vals.kb, fill=vals.fill, slope=slope)
    sewer_type = plumb_type(m, m[net.root], DrainType, "drain")
    min_dn: dict[str, int] = {}
    sized: dict[str, Sized] = {}
    for s in reversed(net.sections):  # from the fixtures down to the sewer
        dus = [vals.du(fixtures[k].fixture) for k in s.serves]
        q = max(vals.k * sqrt(sum(dus)), max(dus, default=0.0))
        x = Sized(s, sum(dus), q)
        sized[s.b] = x
        least = max(
            [vals.dn(fixtures[k].fixture) for k in s.serves if k == s.b]
            + [min_dn[c.b] for c in net.sections if c.a == s.b and c.b in min_dn]
            + [0]
        )
        system = sewer_type if s.kind == "ground" else _stack_type(m, net, s, sewer_type)
        if system is None:
            raise ValueError("no drain type: mark one default, or give the stack or sewer type=")
        options = [b for b in system.sizes.items if b.dn is not None and b.dn >= least]
        _choose(x, options, vals, res, len(s.serves) == 1 and s.b in fixtures)
        if not options:
            x.note = f"{system.id} has no size of DN {least} or more"
        min_dn[s.b] = x.bore.dn if x.bore is not None and x.bore.dn is not None else least
    res.sized = [sized[s.b] for s in net.sections]
    for k in sorted(fixtures, key=natural):
        way = [s for s in net.path(k) if s.kind == "branch"]
        single = all(len(s.serves) == 1 for s in way)
        if single:
            lmax = vals.single_lmax
        else:
            top = sized[way[0].b].bore if way else None
            lim = vals.branch.find(dn=float(top.dn)) if top is not None and top.dn else None
            lmax = float(lim["lmax"]) if lim is not None else 0.0
        res.branches.append(Branch(k, sum(s.length for s in way), lmax, single))
    return res


def _stack_type(m: Model, net: Net, s: Section, fallback: DrainType | None) -> DrainType | None:
    """The drain type of the stack a branch or stack section belongs to; the default, else the
    sewer's, for branches straight to the sewer."""
    for k in (s.a, s.b):
        sid = k.partition(":")[0]
        if ":" in k and sid in m:
            return plumb_type(m, m[sid], DrainType, "drain")
    return plumb_type(m, None, DrainType, "drain") or fallback


def _choose(x: Sized, options: list[Bore], vals: Values, res: Result, single: bool) -> None:
    kind = x.s.kind
    for b in options:
        assert b.dn is not None
        if kind == "branch" and single:
            x.bore = b
            return
        if kind == "ground":
            cap = gravity(b.di, res.slope / 100, vals.kb, vals.fill)
        else:
            cap = qmax(vals.branch if kind == "branch" else vals.stack, b.dn)
        if cap is not None and cap >= x.q - 1e-9:
            x.bore, x.holds = b, cap
            return
    if options:
        x.note = f"no size carries {x.q:.2f} l/s"


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("drain sizes the whole building: leave out the scope")
    res = calculate(d, env)
    lines = [
        f"K {res.k:g} ({env.param('building')}) · slope {res.slope:g} % · h/d {res.fill:g}"
        f" · kb {res.kb:g} mm"
    ]
    ok = True
    for x in res.sized:
        size = x.bore.name if x.bore is not None else "none"
        if x.bore is None:
            ok = False
        how = (
            f"single {_fixture(d, x.s.b)}"
            if x.s.kind == "branch" and len(x.s.serves) == 1 and x.s.b in d.plumb.drains_to
            else f"ΣDU {x.du:.1f}, Qww {x.q:.2f} l/s"
            + (f", holds {x.holds:.2f}" if x.holds is not None else "")
        )
        length = f" {x.s.length:.1f} m" if x.s.kind != "stack" else ""
        lines.append(
            f"{x.s.name} {x.s.kind}{length} {size}: {how}" + (f" ({x.note})" if x.note else "")
        )
    for b in res.branches:
        if b.length > b.lmax + 1e-9:
            ok = False
            lines.append(
                f"{b.fixture} branch {b.length:.1f} m, unvented at most {b.lmax:g} m: too long"
            )
    data = {
        "sections": [
            {
                "a": x.s.a,
                "b": x.s.b,
                "kind": x.s.kind,
                "length": round(x.s.length, 3),
                "serves": x.s.serves,
                "du": round(x.du, 3),
                "q": round(x.q, 4),
                "dn": x.bore.dn if x.bore is not None else None,
                "di": round(x.bore.di, 3) if x.bore is not None else None,
                "holds": round(x.holds, 4) if x.holds is not None else None,
            }
            for x in res.sized
        ],
        "branches": [
            {"fixture": b.fixture, "length": round(b.length, 3), "lmax": b.lmax}
            for b in res.branches
        ],
    }
    return Output(
        lines=lines,
        report=report(d, res, env),
        data=data,
        inputs={"sewer": d.plumb.drain.root if d.plumb.drain else None},
        ok=ok,
    )


def _fixture(d: Derived, k: str) -> str:
    el = d.model[k]
    return el.fixture if isinstance(el, San) else k


KIND_DE = {
    "branch": "Anschlussleitung",
    "stack": "Fallleitung",
    "ground": "Grundleitung",
}


def report(d: Derived, res: Result, env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    rows = [
        [
            x.s.name.replace(">", " → "),
            KIND_DE.get(x.s.kind, x.s.kind),
            de(x.s.length, 1) if x.s.kind != "stack" else "–",
            de(x.du, 1),
            de(x.q, 2),
            x.bore.name if x.bore is not None else "**keine**",
            de(x.holds, 2) if x.holds is not None else "–",
        ]
        for x in res.sized
    ]
    branches = [
        [
            b.fixture,
            "Einzel" if b.single else "Sammel",
            de(b.length, 1),
            de(b.lmax, 1),
            "**zu lang**" if b.length > b.lmax + 1e-9 else "ja",
        ]
        for b in res.branches
    ]
    out = [
        f"# Schmutzwasser-Rohrbemessung: {title}",
        "",
        f"Abflusskennzahl K = {de(res.k, 2)} (Gebäudeart {env.param('building')}); Grundleitungen"
        f" mit Gefälle {de(res.slope, 1)} %, Füllungsgrad h/d = {de(res.fill, 2)},"
        f" k_b = {de(res.kb, 2)} mm.",
        "",
        md_table(
            ["Teilstrecke", "Art", "l m", "ΣDU l/s", "Q_ww l/s", "Rohr", "Q_max l/s"],
            rows,
            right=(2, 3, 4, 6),
        ),
        "",
        "## Unbelüftete Anschlussleitungen",
        "",
        md_table(
            ["Entwässerungsgegenstand", "Leitung", "l m", "l_max m", "eingehalten"],
            branches,
            right=(2, 3),
        ),
        "",
        "## Verfahren",
        "",
        "- Teilstrecken aus dem Modell: Anschlussleitungen je Fallleitung und Geschoss als"
        " kürzester Baum über die rechtwinkligen Abstände, Fallleitungen bis zum Fußpunkt,"
        " Grundleitungen von den Fußpunkten zum Anschluss an den Kanal. Längen sind Untergrenzen.",
        "- Q_ww = K · √ΣDU, mindestens der größte einzelne Anschlusswert (Tabellen"
        " `fixture-drain`, `drain-k`).",
        "- Einzelanschlussleitung: DN des Entwässerungsgegenstands. Sammelanschlussleitung"
        " (unbelüftet): kleinste DN mit Q_max ≥ Q_ww (`drain-branch`). Fallleitung mit"
        " Hauptlüftung: kleinste DN mit Q_max ≥ Q_ww (`drain-stack`). Grundleitung: kleinste"
        " Nennweite, deren Abflussvermögen nach Prandtl-Colebrook bei Gefälle, k_b und"
        " Füllungsgrad (`drain-factors`) Q_ww aufnimmt. Keine Verringerung der Nennweite in"
        " Fließrichtung.",
        "- Länge jeder unbelüfteten Anschlussleitung vom Entwässerungsgegenstand bis zur Fall-"
        " oder Grundleitung gegen l_max.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Keine Höhenunterschiede und Umlenkungen der Anschlussleitungen, keine Lüftung außer"
        " der Hauptlüftung, keine Mindestgeschwindigkeit und kein Mindestgefälle der"
        " Grundleitungen, kein Regenwasser, keine Hebeanlage.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


DRAIN = Calculator(
    "drain",
    "Schmutzwasser-Rohrbemessung",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    (FIXTURE_DRAIN, DRAIN_K, DRAIN_BRANCH, DRAIN_STACK, DRAIN_FACTORS),
)

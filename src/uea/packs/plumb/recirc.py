"""The hot-water circulation (DIN 1988-300), decision 0042.

A `norm` calculator. It follows the short method of the standard: the
circulation flow carries the heat the hot-water pipes lose, at the temperature drop the hot water
may have on its way.

    Q̇_s   = q_loss · l_s                 the loss of each circulated hot-water section, W
    V̇_s   = ΣQ̇ / (ρ · c_p · Δθ)          its circulation flow: the losses of it and of all
                                          circulated sections beyond it
    size  the smallest of the circulation pipe system within v_max (water-factors)
    Δp    = R · l + Σζ · ρv²/2           in the hot-water section at V̇_s and in the
                                          circulation pipe beside it (hydraulics.py)

The end of each circulated branch has its regulating valve: the end with the largest loss sets
the pump head, the others are throttled by the difference. Where the hot-water pipe leaves the
circulated part, the branch to a single fixture holds water that cools: its volume is checked
against the limit `dead=` (the 3-litre rule of DVGW W 551 is the planner's to set). The loss per
metre, the temperature drop and that limit are the planner's settings; the hot-water sizes come
from `uea calc water`.
"""

import math
from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.hydraulics import CP, RHO, full
from uea.packs.net import Net, Section
from uea.packs.pipes import Bore
from uea.packs.plumb import water
from uea.packs.plumb.geometry import plumb_type
from uea.packs.plumb.kinds import PipeType, Recirc, San

VERSION = "0.1.0"
NORM = "DIN 1988-300:2012-05, Kurzverfahren der Zirkulation"
PARAMS = (
    *water.PARAMS,
    Param("loss", float, None, "heat loss of the insulated hot-water pipes, W/m"),
    Param("dt", float, None, "the temperature drop the hot water may have to the far end, K"),
    Param("dead", float, None, "the most water a pipe without circulation may hold, l"),
)


@dataclass
class Leg:
    """A circulated hot-water section and the circulation pipe beside it."""

    s: Section
    loss: float
    """The heat lost by it and every circulated section beyond it, W."""
    q: float
    """The circulation flow, l/s."""
    hot: Bore
    circ: Bore
    dp_hot: float = 0.0
    dp_circ: float = 0.0
    v: float = 0.0


@dataclass
class End:
    """The far end of a circulated branch, with its regulating valve."""

    node: str
    loss: float
    """Through the hot-water pipes and back, hPa."""
    throttle: float = 0.0


@dataclass
class Dead:
    """A branch to a single fixture: the water in it."""

    fixture: str
    length: float
    litres: float


@dataclass
class Loop:
    id: str
    tank: str
    pipe: str
    legs: list[Leg] = field(default_factory=list[Leg])
    ends: list[End] = field(default_factory=list[End])
    dead: list[Dead] = field(default_factory=list[Dead])
    flow: float = 0.0
    head: float = 0.0
    index: str = ""
    vmax: float = 0.0


def litres(b: Bore, length: float) -> float:
    return math.pi * (b.di / 1000) ** 2 / 4 * length * 1000


def calculate(d: Derived, env: Env) -> list[Loop]:
    m, p = d.model, d.plumb
    recs = sorted((el for el in m.of_kind("recirc") if isinstance(el, Recirc)), key=_nat)
    if not recs:
        raise ValueError("there is no circulation: add recirc <tank> to plumb.uea")
    loss_m, dt = float(env.param("loss")), float(env.param("dt"))
    if loss_m <= 0 or dt <= 0:
        raise ValueError("loss and dt must be more than 0")
    sized = water.calculate(d, env)
    hot_size = {(x.net, x.s.b): x.bore for x in sized.sized if x.temp == "hot"}
    vmax = sized.vmax
    out: list[Loop] = []
    for el in recs:
        tank = el.tank.id
        net = p.recirc.get(tank)
        if net is None or not net.sections:
            raise ValueError(f"{el.id}: {tank} has no hot-water pipes to circulate (W-PLUMB-007)")
        pipe = plumb_type(m, el, PipeType, "pipe")
        if pipe is None:
            raise ValueError(f"{el.id} has no pipe type, and none is marked default")
        loop = Loop(el.id, tank, pipe.id, vmax=vmax)
        beyond = _beyond(net)
        rho_c = RHO["hot"] * CP
        for s in net.sections:
            w = loss_m * sum(x.length for x in beyond[s.b]) + loss_m * s.length
            q = w / (rho_c * dt)
            circ = _fit(q, pipe.sizes.items, pipe.k, vmax)
            leg = Leg(s, w, q, hot_size[(tank, s.b)], circ)
            zeta = s.bends * pipe.bend + (pipe.tee if s.a != net.root else 0.0)
            fh = full(q, leg.hot.di, pipe.k, "hot")
            fc = full(q, circ.di, pipe.k, "hot")
            leg.dp_hot = fh.r * s.length + zeta * fh.dyn
            leg.dp_circ = fc.r * s.length + zeta * fc.dyn
            leg.v = fc.v
            loop.legs.append(leg)
        loop.flow = sum(x.q for x in loop.legs if x.s.a == net.root)
        by_b = {x.s.b: x for x in loop.legs}
        tips = sorted({s.b for s in net.sections} - {s.a for s in net.sections}, key=natural)
        for k in tips:
            way = [by_b[s.b] for s in net.path(k)]
            loop.ends.append(End(k, sum(x.dp_hot + x.dp_circ for x in way)))
        worst = max(loop.ends, key=lambda e: (e.loss, natural(e.node)))
        for e in loop.ends:
            e.throttle = worst.loss - e.loss
        loop.head, loop.index = worst.loss, worst.node
        loop.dead = _dead(d, p.hot[tank], net, hot_size, tank)
        out.append(loop)
    return out


def _nat(el: Recirc) -> tuple[object, ...]:
    return natural(el.id)


def _beyond(net: Net) -> dict[str, list[Section]]:
    """For each node, the circulated sections beyond it."""
    kids: dict[str, list[Section]] = {}
    for s in net.sections:
        kids.setdefault(s.a, []).append(s)

    def under(k: str) -> list[Section]:
        got: list[Section] = []
        for s in kids.get(k, []):
            got += [s, *under(s.b)]
        return got

    return {k: under(k) for k in net.nodes}


def _fit(q: float, sizes: tuple[Bore, ...], k: float, vmax: float) -> Bore:
    for b in sizes:
        if full(q, b.di, k, "hot").v <= vmax:
            return b
    return sizes[-1]


def _dead(
    d: Derived, hot: Net, circ: Net, size: dict[tuple[str, str], Bore], tank: str
) -> list[Dead]:
    """The water between each fixture and the circulated part."""
    done = {s.b for s in circ.sections} | {circ.root}
    out: list[Dead] = []
    for k in sorted(hot.nodes, key=natural):
        el = d.model.get(k)
        if not isinstance(el, San) or not hot.has(k):
            continue
        length = vol = 0.0
        for s in reversed(hot.path(k)):
            if s.b in done:
                break
            length += s.length
            vol += litres(size[(tank, s.b)], s.length)
        out.append(Dead(k, length, vol))
    return out


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("recirc takes the whole building: leave out the scope")
    loops = calculate(d, env)
    limit = float(env.param("dead"))
    lines: list[str] = []
    bad = False
    for lp in loops:
        lines.append(
            f"{lp.id} from {lp.tank}: {lp.flow * 3600:.0f} l/h, pump head {lp.head:.0f} hPa"
            f" (index {lp.index}) · pipe {lp.pipe} · loss {env.param('loss'):g} W/m,"
            f" Δθ {env.param('dt'):g} K"
        )
        for x in lp.legs:
            fast = " (too fast: the largest size)" if x.v > lp.vmax + 1e-9 else ""
            bad = bad or bool(fast)
            lines.append(
                f"{x.s.name} {x.s.length:.1f} m: {x.loss:.0f} W, {x.q * 3600:.1f} l/h, hot"
                f" {x.hot.name} Δp {x.dp_hot:.1f} hPa, circulation {x.circ.name} v {x.v:.2f}"
                f" m/s Δp {x.dp_circ:.1f} hPa{fast}"
            )
        for e in lp.ends:
            if e.throttle >= 0.5:
                lines.append(f"{e.node}: valve throttles {e.throttle:.0f} hPa")
        for dd in lp.dead:
            if dd.litres > limit + 1e-9:
                bad = True
                lines.append(
                    f"{dd.fixture}: {dd.litres:.2f} l in {dd.length:.1f} m without circulation"
                    f" > {limit:g} l"
                )
    data = {
        "loops": {
            lp.id: {
                "tank": lp.tank,
                "flow": round(lp.flow, 9),
                "head": round(lp.head, 2),
                "index": lp.index,
                "legs": [
                    {
                        "a": x.s.a,
                        "b": x.s.b,
                        "length": round(x.s.length, 3),
                        "loss": round(x.loss, 2),
                        "q": round(x.q, 9),
                        "hot": x.hot.name,
                        "circ": x.circ.name,
                        "v": round(x.v, 4),
                        "dp_hot": round(x.dp_hot, 3),
                        "dp_circ": round(x.dp_circ, 3),
                    }
                    for x in lp.legs
                ],
                "ends": {e.node: {"loss": round(e.loss, 3), "throttle": round(e.throttle, 3)}
                         for e in lp.ends},
                "dead": {x.fixture: {"length": round(x.length, 3), "litres": round(x.litres, 4)}
                         for x in lp.dead},
            }
            for lp in loops
        }
    }  # fmt: skip
    return Output(
        lines=lines,
        report=report(d, loops, env),
        data=data,
        inputs={"loss": env.param("loss"), "dt": env.param("dt"), "dead": limit},
        ok=not bad,
    )


def report(d: Derived, loops: list[Loop], env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    limit = float(env.param("dead"))
    out = [
        f"# Zirkulation: {title}",
        "",
        f"Wärmeverlust der gedämmten Warmwasserleitungen {de(env.param('loss'), 1)} W/m,"
        f" zulässige Abkühlung Δθ = {de(env.param('dt'), 1)} K, Wasserinhalt ohne Zirkulation"
        f" höchstens {de(limit, 1)} l.",
        "",
    ]
    for lp in loops:
        rows = [
            [
                x.s.name.replace(">", " → "),
                de(x.s.length, 1),
                de(x.loss, 0),
                de(x.q * 3600, 1),
                x.hot.name,
                de(x.dp_hot, 1),
                x.circ.name,
                de(x.v, 2),
                de(x.dp_circ, 1),
            ]
            for x in lp.legs
        ]
        out += [
            f"## {lp.id} am Speicher {lp.tank}",
            "",
            md_table(
                [
                    "Teilstrecke",
                    "l m",
                    "Q̇ W",
                    "V̇ l/h",
                    "PWH",
                    "Δp PWH hPa",
                    "PWH-C",
                    "v m/s",
                    "Δp PWH-C hPa",
                ],
                rows,
                right=(1, 2, 3, 5, 7, 8),
            ),
            "",
            f"- **Zirkulationspumpe:** V̇ = {de(lp.flow * 3600, 0)} l/h, Förderhöhe"
            f" {de(lp.head, 0)} hPa; ungünstigster Strang bis {lp.index}.",
        ]
        for e in lp.ends:
            if e.throttle >= 0.5:
                out.append(f"- Regulierventil am Ende {e.node}: drosselt {de(e.throttle, 0)} hPa.")
        rows = [
            [
                x.fixture,
                de(x.length, 1),
                de(x.litres, 2),
                "**zu viel**" if x.litres > limit + 1e-9 else "ok",
            ]
            for x in lp.dead
        ]
        out += [
            "",
            "Leitungen ohne Zirkulation (Einzelzuleitungen):",
            "",
            md_table(["Entnahmestelle", "l m", "Inhalt l", ""], rows, right=(1, 2)),
            "",
        ]
    out += [
        "## Verfahren",
        "",
        "- Zirkulation entlang der Warmwasserleitungen bis an die Einzelzuleitungen; diese"
        " (Teilstrecken, die an einer Entnahmestelle enden und nur sie versorgen) bleiben ohne"
        " Zirkulation.",
        "- Kurzverfahren nach DIN 1988-300: Wärmeverlust je Teilstrecke Q̇ = q · l, Volumenstrom"
        " V̇ = ΣQ̇ / (ρ · c_p · Δθ) aus den Verlusten der Teilstrecke und aller zirkulierten"
        " Teilstrecken dahinter. Nennweiten der Warmwasserleitungen aus der Bemessung `water`,"
        " der Zirkulationsleitungen die kleinste mit v ≤ v_max.",
        "- Druckverlust in Warmwasser- und Zirkulationsleitung bei V̇, Rohrreibung nach"
        " Darcy-Weisbach und Colebrook-White, ζ je Bogen und T-Stück. Der Strang mit dem"
        " größten Verlust bestimmt die Förderhöhe, die anderen Regulierventile drosseln.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Wärmeverlust der Zirkulationsleitung selbst und der Armaturen nicht angesetzt;"
        " ein Wert je Meter für alle Leitungen.",
        "- Kein Differenzverfahren, keine thermostatischen Ventile mit Kennlinie, keine"
        " Begleitheizung.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


RECIRC = Calculator(
    "recirc",
    "Zirkulation",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    water.WATER.tables,
)

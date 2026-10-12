"""Heating pipe sizing and the hydraulic balance (decision 0037).

A `norm` calculator, not yet reviewed. It follows Verfahren B of the hydraulic balance as German
practice knows it: the room-by-room Heizlast, the flow each emitter needs, the pipe network, the
valve settings and the pump head.

    Φ_e   the room's Heizlast (`heatload.py`), shared among its emitters by their output
    V̇_e   = Φ_e / (ρ · c_p · Δθ)          the design flow at the spread Δθ (`spread=`)
    loop  an underfloor heating's loops share V̇_e; each loses R · l over its whole length
    home  a radiator's home run from its manifold, sized like a section; flow and return
    size  the smallest of the pipe system whose velocity stays within v_max (`vmax=`)
    Δp    = 2 · (R · l + Σζ · ρv²/2)       a section's flow and return pipe (hydraulics.py)

At each manifold, the circuit with the largest loss sets the manifold's loss; each other
circuit's valve takes the difference. From each generator or tank, the end with the largest loss
of its way (the sections, then its manifold's circuits) sets the pump head; every other end is
throttled by the difference before it. A tank separates the generator's circuit from the
heating circuits behind it: each has its pump. The generator's own loss comes from its type.

ρ, c_p and ν of water at 40 °C are physical constants in the code; the spread and v_max are the
planner's; the pipes, roughness and ζ come from the types; the Heizlast from the office's tables.
"""

import math
from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.core.registry import natural
from uea.derive import Derived
from uea.packs.heat import emitters, heatload
from uea.packs.heat.geometry import heat_type
from uea.packs.heat.kinds import GenType, HpipeType, Man, UfhType
from uea.packs.hydraulics import full, heat_flow
from uea.packs.net import Section
from uea.packs.pipes import Bore

VERSION = "0.2.0"
NORM = "Verfahren B des hydraulischen Abgleichs; Heizlast nach DIN EN 12831-1:2017-09"
PARAMS = (
    *heatload.PARAMS,
    Param("vmax", float, None, "the highest velocity in the heating pipes, m/s"),
)


@dataclass
class Sized:
    """A pipe at one flow: its size, velocity and losses."""

    q: float
    """Flow, l/s."""
    length: float
    zeta: float
    sizes: tuple[Bore, ...]
    k: float
    pair: bool
    """Flow and return pipe: the loss counts twice."""
    i: int = 0
    v: float = 0.0
    r: float = 0.0
    dp: float = 0.0

    @property
    def bore(self) -> Bore:
        return self.sizes[self.i]

    def compute(self) -> None:
        f = full(self.q, self.bore.di, self.k, "heating")
        self.v, self.r = f.v, f.r
        self.dp = (f.r * self.length + self.zeta * f.dyn) * (2 if self.pair else 1)

    def fit(self, vmax: float) -> None:
        """The smallest size within vmax, else the largest."""
        self.i = 0
        while (
            self.i < len(self.sizes) - 1 and full(self.q, self.bore.di, self.k, "heating").v > vmax
        ):
            self.i += 1
        self.compute()


@dataclass
class Circuit:
    """A circuit of a manifold: the loops of an underfloor heating, or a radiator's home run."""

    man: str
    el: str
    room: str
    phi: float
    n: int
    """Loops; a home run is one."""
    pipe: Sized
    """One loop, or the home run."""
    valve: float = 0.0
    """What its valve must take, hPa."""


@dataclass
class Pipe:
    net: str
    s: Section
    phi: float
    pipe: Sized


@dataclass
class End:
    """Something a generator's or tank's pipes lead to."""

    el: str
    net: str
    way: float
    """The loss of the sections on its way, hPa."""
    own: float
    """The loss behind it: its manifold's worst circuit, else 0."""
    index: str
    throttle: float = 0.0

    @property
    def need(self) -> float:
        return self.way + self.own


@dataclass
class Pump:
    root: str
    q: float
    head: float
    index: str
    gen: float | None
    """The generator's own loss, if the pump drives one."""
    mix: bool = False
    """The pump of a mixing circuit, behind its mixing valve."""


@dataclass
class Mixer:
    """A manifold with a mixing valve: colder circuits behind it, a smaller flow in front."""

    man: str
    flow: float
    ret: float
    primary: float
    """The flow it draws from the system, l/s: Φ / (ρ c_p (θ_V,system − θ_R,circuit))."""
    secondary: float
    """The flow of its circuits, l/s."""
    valve: float = 0.0
    """What the mixing valve takes at the primary flow, hPa: the throttle of its branch."""


@dataclass
class Result:
    phi: dict[str, float] = field(default_factory=dict[str, float])
    """The design heat flow of each emitter, W."""
    q: dict[str, float] = field(default_factory=dict[str, float])
    """Its flow, l/s."""
    circuits: list[Circuit] = field(default_factory=list[Circuit])
    pipes: list[Pipe] = field(default_factory=list[Pipe])
    ends: list[End] = field(default_factory=list[End])
    pumps: list[Pump] = field(default_factory=list[Pump])
    mixers: list[Mixer] = field(default_factory=list[Mixer])
    hpipe: str = ""
    spread: float = 0.0
    vmax: float = 0.0
    unheated: list[str] = field(default_factory=list[str])
    """Emitters in rooms the Heizlast does not heat: no flow."""


def kv(q: float, dp: float) -> float | None:
    """The kv value (m³/h at 1 bar) of a valve that takes dp (hPa) at q (l/s); None if open."""
    if dp < 1.0 or q <= 0:
        return None
    return q * 3.6 / math.sqrt(dp / 1000)


def calculate(d: Derived, env: Env) -> Result:
    m, h = d.model, d.heat
    if env.param("spread") is None:
        raise ValueError("hydronic needs spread=<K>: the system's design spread")
    spread, vmax = float(env.param("spread")), float(env.param("vmax"))
    system = env.param("flow")
    if spread <= 0 or vmax <= 0:
        raise ValueError("spread and vmax must be more than 0")
    if not any(h.emitters.values()):
        raise ValueError("there are no emitters: add ufh or rad to heat.uea")
    loads, _, _ = heatload.calculate(d, env)
    by_room = {r.id: r for r in loads}
    res = Result(spread=spread, vmax=vmax)
    for room, ems in sorted(h.emitters.items(), key=lambda kv: natural(kv[0])):
        if room not in by_room:
            res.unheated += ems
            for e in ems:
                res.phi[e], res.q[e] = 0.0, 0.0
            continue
        out = {k: o.w for k, o in heatload.outputs(d, by_room[room], env).items()}
        total = sum(out.values())
        for e in ems:
            share = out[e] / total if total > 0 else 1 / len(ems)
            res.phi[e] = by_room[room].phi * share
            t = emitters.temps_of(d, e, system, spread)
            res.q[e] = heat_flow(res.phi[e], t.spread if t is not None else spread)
    for el in sorted(m.of_kind("man"), key=lambda el: natural(el.id)):
        if not isinstance(el, Man) or not el.mix:
            continue
        assert el.flow is not None
        if system is None:
            raise ValueError(f"{el.id} mixes: give flow=<°C>, the system's flow temperature")
        ret = el.flow - (el.spread if el.spread is not None else spread)
        if el.flow > system + 1e-9 or ret >= system:
            raise ValueError(
                f"{el.id} mixes to {el.flow:g} °C: it must be colder than the system's {system:g}"
            )
        phi = _phi(h.supplies, res.phi, el.id)
        res.mixers.append(
            Mixer(
                el.id,
                el.flow,
                ret,
                heat_flow(phi, system - ret),
                sum(res.q.get(x, 0.0) for x in h.supplies.get(el.id, [])),
            )
        )
    mixing = {x.man: x for x in res.mixers}
    hp = _hpipe(d) if h.nets else None
    if hp is not None:
        res.hpipe = hp.id
    # the circuits of each manifold
    for man in sorted((k for k in h.supplies if m[k].kind == "man"), key=natural):
        mine: list[Circuit] = []
        for e in h.supplies[man]:
            el = m[e]
            if el.kind == "ufh":
                mine.append(_loops(d, man, e, res))
            elif el.kind == "rad" and hp is not None and man in h.nets:
                sec = next(s for s in h.nets[man].sections if s.b == e)
                p = Sized(res.q[e], sec.length, sec.bends * hp.bend, hp.sizes.items, hp.k, True)
                p.fit(vmax)
                room = h.at[e].room or ""
                mine.append(Circuit(man, e, room, res.phi[e], 1, p))
        worst = max((c.pipe.dp for c in mine), default=0.0)
        for c in mine:
            c.valve = worst - c.pipe.dp
        res.circuits += mine

    def flow(k: str) -> float:
        if k in res.q:
            return res.q[k]
        if k in mixing:
            return mixing[k].primary
        return sum(flow(x) for x in h.supplies.get(k, []))

    def own(k: str) -> tuple[float, str]:
        mine = [c for c in res.circuits if c.man == k]
        if k in mixing:
            # its circuits are behind the mixing valve and its own pump
            mine = []
        if not mine:
            return 0.0, k
        c = max(mine, key=lambda c: (c.pipe.dp, natural(c.el)))
        return c.pipe.dp, f"{k} {c.el}"

    for root, net in sorted(h.nets.items(), key=lambda kv: natural(kv[0])):
        if m[root].kind == "man" or hp is None:
            continue
        sized: dict[str, Pipe] = {}
        for s in net.sections:
            q = sum(flow(x) for x in s.serves)
            zeta = s.bends * hp.bend + (hp.tee if s.a != root else 0.0)
            p = Sized(q, s.length, zeta, hp.sizes.items, hp.k, True)
            p.fit(vmax)
            phi = sum(_phi(h.supplies, res.phi, x) for x in s.serves)
            sized[s.b] = Pipe(root, s, phi, p)
            res.pipes.append(sized[s.b])
        ends: list[End] = []
        for k in sorted((k for k in net.nodes if k != root), key=natural):
            if k not in {s.b for s in net.sections}:
                continue
            way = sum(sized[s.b].pipe.dp for s in net.path(k))
            loss, index = own(k)
            ends.append(End(k, root, way, loss, index))
        if not ends:
            continue
        worst = max(ends, key=lambda e: (e.need, natural(e.el)))
        for e in ends:
            e.throttle = worst.need - e.need
        res.ends += ends
        gt = heat_type(m, m[root], GenType, "gen") if m[root].kind == "gen" else None
        gdp = gt.dp if gt is not None else None
        res.pumps.append(Pump(root, flow(root), worst.need + (gdp or 0.0), worst.index, gdp))
    for x in res.mixers:
        end = next((e for e in res.ends if e.el == x.man), None)
        x.valve = end.throttle if end is not None else 0.0
        mine = [c for c in res.circuits if c.man == x.man]
        if mine:
            c = max(mine, key=lambda c: (c.pipe.dp, natural(c.el)))
            res.pumps.append(Pump(x.man, x.secondary, c.pipe.dp, f"{x.man} {c.el}", None, True))
    return res


def _phi(supplies: dict[str, list[str]], phi: dict[str, float], k: str) -> float:
    if k in phi:
        return phi[k]
    return sum(_phi(supplies, phi, x) for x in supplies.get(k, []))


def _hpipe(d: Derived) -> HpipeType:
    for t in d.model.of_kind("type", "hpipe"):
        if isinstance(t, HpipeType) and t.default:
            return t
    raise ValueError(
        "no heating pipe type is marked default: add type <name> hpipe sizes=... k= bend= tee="
        " default"
    )


def _loops(d: Derived, man: str, e: str, res: Result) -> Circuit:
    el = d.model[e]
    t = heat_type(d.model, el, UfhType, "ufh")
    lp = d.heat.loops.get(e)
    if t is None or lp is None:
        raise ValueError(f"{e} has no type, and no ufh type is marked default")
    if t.pipe is None or t.k is None:
        raise ValueError(f"the type {t.id} of {e} needs pipe= (e.g. 16x2) and k= (its roughness)")
    if lp.n == 0:
        raise ValueError(f"{e} is too far from {man} for a loop (W-HEAT-003)")
    p = Sized(res.q[e] / lp.n, lp.each, 0.0, t.pipe.items, t.k, False)
    p.compute()
    room = getattr(el, "room").id  # noqa: B009
    return Circuit(man, e, room, res.phi[e], lp.n, p)


def run(d: Derived, scope: str | None, env: Env) -> Output:
    if scope is not None:
        raise ValueError("hydronic balances the whole building: leave out the scope")
    res = calculate(d, env)
    lines = [
        f"spread {res.spread:g} K · vmax {res.vmax:g} m/s"
        + (f" · pipes {res.hpipe}" if res.hpipe else "")
        + " · water 40 °C"
    ]
    fast = False
    for x in res.pipes:
        p = x.pipe
        flag = ""
        if p.v > res.vmax + 1e-9:
            flag, fast = " (too fast: the largest size)", True
        lines.append(
            f"{x.s.name} {x.s.length:.1f} m {p.bore.name}: {x.phi / 1000:.2f} kW {p.q * 3600:.0f}"
            f" l/h, v {p.v:.2f} m/s, R {p.r:.1f} hPa/m, ζ {p.zeta:g}, Δp {p.dp:.0f} hPa{flag}"
        )
    for c in res.circuits:
        p = c.pipe
        if c.n > 1 or d.model[c.el].kind == "ufh":
            what = f"{c.n}x{p.length:.1f} m {p.bore.name}, {p.q * 3600:.0f} l/h each"
        else:
            what = f"{p.length:.1f} m {p.bore.name}, {p.q * 3600:.0f} l/h"
            if p.v > res.vmax + 1e-9:
                what, fast = what + " (too fast)", True
        k = kv(p.q, c.valve)
        valve = "open (index)" if k is None else f"valve {c.valve:.0f} hPa kv {k:.2f}"
        lines.append(f"{c.man} {c.el} {c.room} {c.phi:.0f} W: {what}, Δp {p.dp:.0f} hPa, {valve}")
    for e in res.ends:
        if e.throttle >= 1.0:
            lines.append(f"{e.el} on {e.net}: throttle {e.throttle:.0f} hPa")
    for x in res.mixers:
        k = kv(x.primary, x.valve)
        valve = "valve open (index)" if k is None else f"valve {x.valve:.0f} hPa kv {k:.2f}"
        lines.append(
            f"mixer {x.man} {x.flow:g}/{x.ret:g} °C: {x.primary * 3600:.0f} l/h from the system,"
            f" {x.secondary * 3600:.0f} l/h in its circuits, {valve}"
        )
    for pu in res.pumps:
        gen = f", {pu.root} {pu.gen:.0f}" if pu.gen is not None else ""
        lines.append(
            f"pump {pu.root}: {pu.q * 3600:.0f} l/h, head {pu.head:.0f} hPa (index {pu.index}{gen})"
        )
    if res.unheated:
        lines.append(f"no flow (unheated rooms): {' '.join(res.unheated)}")
    data = {
        "emitters": {k: {"phi": round(v, 1), "q": round(res.q[k], 6)} for k, v in res.phi.items()},
        "pipes": [
            {
                "net": x.net,
                "a": x.s.a,
                "b": x.s.b,
                "length": round(x.s.length, 3),
                "phi": round(x.phi, 1),
                "q": round(x.pipe.q, 6),
                "size": x.pipe.bore.name,
                "v": round(x.pipe.v, 3),
                "r": round(x.pipe.r, 3),
                "zeta": x.pipe.zeta,
                "dp": round(x.pipe.dp, 2),
            }
            for x in res.pipes
        ],
        "circuits": [
            {
                "man": c.man,
                "el": c.el,
                "room": c.room,
                "phi": round(c.phi, 1),
                "loops": c.n,
                "length": round(c.pipe.length, 3),
                "size": c.pipe.bore.name,
                "q": round(c.pipe.q, 6),
                "dp": round(c.pipe.dp, 2),
                "valve": round(c.valve, 2),
                "kv": None if (k := kv(c.pipe.q, c.valve)) is None else round(k, 3),
            }
            for c in res.circuits
        ],
        "ends": [
            {
                "el": e.el,
                "net": e.net,
                "way": round(e.way, 2),
                "own": round(e.own, 2),
                "throttle": round(e.throttle, 2),
            }
            for e in res.ends
        ],
        "pumps": [
            {
                "root": p.root,
                "q": round(p.q, 6),
                "head": round(p.head, 2),
                "index": p.index,
                "mix": p.mix,
            }
            for p in res.pumps
        ],
        "mixers": [
            {
                "man": x.man,
                "flow": x.flow,
                "ret": x.ret,
                "primary": round(x.primary, 6),
                "secondary": round(x.secondary, 6),
                "valve": round(x.valve, 2),
                "kv": None if (k := kv(x.primary, x.valve)) is None else round(k, 3),
            }
            for x in res.mixers
        ],
    }
    return Output(
        lines=lines,
        report=report(d, res, env),
        data=data,
        inputs={"hpipe": res.hpipe},
        ok=not fast,
    )


def report(d: Derived, res: Result, env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    out = [
        f"# Rohrnetz und hydraulischer Abgleich: {title}",
        "",
        f"Spreizung Δθ = {de(res.spread, 1)} K, v_max = {de(res.vmax, 2)} m/s, Heizungswasser"
        f" 40 °C. Rohrsystem {res.hpipe or '–'}. Raumheizlast nach DIN EN 12831-1 (ΔU_WB ="
        f" {de(env.param('tb'), 3)} W/(m²K), n_50 = {de(env.param('n50'), 1)} 1/h).",
        "",
    ]
    if res.pipes:
        rows = [
            [
                x.s.name.replace(">", " → "),
                de(x.s.length, 1),
                de(x.phi, 0),
                de(x.pipe.q * 3600, 0),
                x.pipe.bore.name,
                de(x.pipe.v, 2),
                de(x.pipe.r, 1),
                de(x.pipe.zeta, 1),
                de(x.pipe.dp, 0),
            ]
            for x in res.pipes
        ]
        out += [
            "## Rohrnetz",
            "",
            md_table(
                [
                    "Teilstrecke",
                    "l m",
                    "Φ W",
                    "V̇ l/h",
                    "Rohr",
                    "v m/s",
                    "R hPa/m",
                    "Σζ",
                    "Δp VL+RL hPa",
                ],
                rows,
                right=(1, 2, 3, 5, 6, 7, 8),
            ),
            "",
        ]
    if res.circuits:
        rows: list[list[str]] = []
        for c in res.circuits:
            k = kv(c.pipe.q, c.valve)
            rows.append(
                [
                    c.man,
                    c.el,
                    c.room,
                    de(c.phi, 0),
                    str(c.n),
                    de(c.pipe.length, 1),
                    c.pipe.bore.name,
                    de(c.pipe.q * 3600, 0),
                    de(c.pipe.dp, 0),
                    de(c.valve, 0),
                    "offen" if k is None else de(k, 2),
                ]
            )
        out += [
            "## Heizkreise an den Verteilern",
            "",
            md_table(
                [
                    "Verteiler",
                    "Kreis",
                    "Raum",
                    "Φ W",
                    "Kreise",
                    "l je Kreis m",
                    "Rohr",
                    "V̇ je Kreis l/h",
                    "Δp hPa",
                    "Ventil Δp hPa",
                    "kv m³/h",
                ],
                rows,
                right=(3, 4, 5, 7, 8, 9, 10),
            ),
            "",
        ]
    if res.pumps:
        rows = [
            [
                e.el,
                e.net,
                de(e.way, 0),
                de(e.own, 0),
                "–" if e.throttle < 1 else de(e.throttle, 0),
            ]
            for e in res.ends
        ]
        out += [
            "## Abgleich der Stränge",
            "",
            md_table(
                ["Abnehmer", "ab", "Δp Rohrnetz hPa", "Δp dahinter hPa", "Drosseln hPa"],
                rows,
                right=(2, 3, 4),
            ),
            "",
        ]
        for x in res.mixers:
            k = kv(x.primary, x.valve)
            out.append(
                f"- **Mischer {x.man}:** {de(x.flow, 0)}/{de(x.ret, 0)} °C; aus dem System"
                f" {de(x.primary * 3600, 0)} l/h, in den Heizkreisen {de(x.secondary * 3600, 0)}"
                f" l/h; Mischventil "
                + ("offen (ungünstigster Abnehmer)." if k is None else f"{de(x.valve, 0)} hPa,"
                   f" kv {de(k, 2)} m³/h.")
            )  # fmt: skip
        for p in res.pumps:
            gen = (
                f", davon Wärmeerzeuger {de(p.gen, 0)} hPa"
                if p.gen is not None
                else (
                    ", ohne Wärmeerzeuger (kein dp im Typ)" if d.model[p.root].kind == "gen" else ""
                )
            )
            out.append(
                f"- **{'Mischerpumpe' if p.mix else 'Pumpe'} {p.root}:** V̇ = {de(p.q * 3600, 0)}"
                " l/h, Förderhöhe"
                f" {de(p.head, 0)} hPa ({de(p.head / 98.1, 2)} m){gen}; ungünstigster Kreis"
                f" {p.index}."
            )
        out.append("")
    if res.unheated:
        out += [
            "Ohne Durchfluss (Raum laut Tabelle `room-temp` unbeheizt):"
            f" {', '.join(res.unheated)}.",
            "",
        ]
    out += [
        "## Verfahren",
        "",
        "- Raumheizlast Φ_HL nach DIN EN 12831-1 (Rechenverfahren `heatload`), auf die"
        " Heizflächen eines Raums im Verhältnis ihrer Leistung aufgeteilt.",
        "- Auslegungsvolumenstrom V̇ = Φ / (ρ · c_p · Δθ) mit Wasser bei 40 °C.",
        "- Rohrnetz aus dem Modell: von jedem Wärmeerzeuger und Speicher der kürzeste Baum über"
        " die rechtwinkligen Abstände zu Speichern, Verteilern und Heizkörpern, Vor- und"
        " Rücklauf nebeneinander; Heizkörper an einem Verteiler mit eigener Anbindeleitung."
        " Zwischen den Geschossen durch den Deckendurchbruch, den das Netz nennt. Längen sind"
        " Untergrenzen.",
        "- Nennweite: die kleinste des Rohrsystems mit v ≤ v_max. Rohrreibung nach"
        " Darcy-Weisbach mit λ nach Colebrook-White; Einzelwiderstände: ζ des Rohrsystems je"
        " Bogen des rechtwinkligen Laufs und ein T-Stück am Abzweig.",
        "- Fußbodenheizung: V̇ des Raums gleich auf die Kreise verteilt, Δp = R · l über die"
        " ganze Kreislänge mit Rohr und Rauheit des Typs.",
        "- Abgleich: am Verteiler bestimmt der Kreis mit dem größten Δp den Verteiler, die"
        " Ventile der anderen nehmen die Differenz (kv = V̇ / √Δp). Im Rohrnetz bestimmt der"
        " Abnehmer mit dem größten Δp die Förderhöhe, vor den anderen wird die Differenz"
        " gedrosselt. Ein Speicher trennt Erzeuger- und Heizkreis.",
        "",
        "## Abweichungen und nicht abgebildet",
        "",
        "- Spreizung und Vorlauftemperatur des Systems, oder des Heizkreisverteilers, wenn er"
        " eigene angibt. Ein Mischerkreis bezieht aus dem System V̇ = Φ / (ρ · c_p · (θ_V,System"
        " − θ_R,Kreis)); seine Kreise hinter dem Mischventil fördert eine eigene Pumpe, das"
        " Mischventil nimmt den Drosselanteil seines Strangs.",
        "- Ohne Druckverlust von Verteiler, Heizkörper, Armaturen und Bögen der Heizkreise;"
        " ohne Mindest-Ventilautorität. Die Voreinstellung eines Ventils folgt aus kv und dem"
        " Diagramm des Herstellers.",
        "- Aufteilung der Raumheizlast auf die Heizflächen nach ihrer Leistung bei den"
        " Temperaturen des Kreises (Typwert, DIN EN 442 oder DIN EN 1264, siehe Heizlast).",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


HYDRONIC = Calculator(
    "hydronic",
    "Rohrnetz und hydraulischer Abgleich",
    "norm",
    VERSION,
    run,
    NORM,
    PARAMS,
    heatload.HEATLOAD.tables,
)

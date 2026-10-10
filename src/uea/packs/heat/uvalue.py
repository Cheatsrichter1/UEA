"""U-values of the build-ups as the model uses them (DIN EN ISO 6946), decision 0033.

A `norm` calculator. A build-up is a wall, slab or roof type, or a slab with the floor type of
the room on it; it is listed once for each way it is used: the direction of the heat flow
(horizontal through walls, down through floors, up through ceilings and roofs) and what lies
beyond (outside air, the ground, a room). Windows and doors carry their U-value in their type.
"""

from dataclasses import dataclass

from uea.calc import Calculator, Env, Output, de, md_table
from uea.core.values import Layer
from uea.derive import Derived
from uea.packs.heat.envelope import envelope
from uea.packs.heat.thermal import FAR_DE, FLOW_DE, MATERIAL, SURFACE, Far, Flow, Thermal

VERSION = "0.1.0"
NORM = "DIN EN ISO 6946:2018-03"


@dataclass(frozen=True)
class Use:
    build: str
    layers: tuple[Layer, ...]
    flow: Flow
    far: Far


def uses(d: Derived, scope: str | None) -> list[Use]:
    """The build-ups the rooms are made of, each way they are used; scope: a room or a type."""
    if scope is not None and scope not in d.model:
        raise ValueError(f"unknown {scope}: give a room or a type")
    env = envelope(d)
    seen: dict[tuple[str, Flow, Far], Use] = {}
    for rid, surfaces in env.rooms.items():
        for s in surfaces:
            if not s.layers:
                continue
            if scope is not None and scope != rid and scope not in s.build.split(" + "):
                continue
            seen.setdefault((s.build, s.flow, s.far), Use(s.build, s.layers, s.flow, s.far))
    order = {"horizontal": 0, "down": 1, "up": 2}
    return sorted(seen.values(), key=lambda u: (order[u.flow], u.build, u.far))


def run(d: Derived, scope: str | None, env: Env) -> Output:
    found = uses(d, scope)
    if not found:
        raise ValueError(
            "no walls, slabs or roofs around rooms" + (f" in {scope}" if scope else "")
        )
    th = Thermal(env, (x.material for u in found for x in u.layers))
    rows: list[tuple[Use, float, float, float, float]] = []
    lines: list[str] = []
    for u in found:
        uv = th.u(u.layers, u.flow, u.far)
        rows.append((u, uv.rsi, uv.r_layers, uv.rse, uv.u))
        lines.append(f"{u.build} {u.flow} to {u.far}: U {uv.u:.3f} W/(m²K), R {uv.r_layers:.3f}")
    return Output(
        lines=lines,
        report=report(d, rows, th),
        data={
            "buildups": [
                {
                    "build": u.build,
                    "flow": u.flow,
                    "beyond": u.far,
                    "rsi": rsi,
                    "r_layers": round(r, 5),
                    "rse": rse,
                    "u": round(uv, 5),
                }
                for u, rsi, r, rse, uv in rows
            ]
        },
        inputs={"scope": scope},
    )


def report(d: Derived, rows: list[tuple[Use, float, float, float, float]], th: Thermal) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    head = ["Aufbau", "Wärmestrom", "angrenzend", "R_si", "Σ d/λ", "R_se", "U W/(m²K)"]
    body = [
        [u.build, FLOW_DE[u.flow], FAR_DE[u.far], de(rsi), de(r, 3), de(rse), de(uv, 3)]
        for u, rsi, r, rse, uv in rows
    ]
    out = [
        f"# U-Werte der Bauteile: {title}",
        "",
        md_table(head, body, right=(3, 4, 5, 6)),
        "",
        "## Schichten",
        "",
    ]
    done: set[str] = set()
    for u, *_ in rows:
        if u.build in done:
            continue
        done.add(u.build)
        layer_rows = [
            [x.material, de(x.t, 3), de(th.lam(x.material), 3), de(x.t / th.lam(x.material), 3)]
            for x in u.layers
        ]
        out += [
            f"**{u.build}**",
            "",
            md_table(["Schicht", "d m", "λ W/(m·K)", "R m²K/W"], layer_rows, right=(1, 2, 3)),
            "",
        ]
    out += [
        "## Verfahren",
        "",
        "- DIN EN ISO 6946: R = d / λ je Schicht, R_T = R_si + Σ R + R_se, U = 1 / R_T. Nur"
        " homogene Schichten.",
        "- λ aus der Tabelle `material` des Büros (Bemessungswerte), R_si und R_se aus der"
        " Tabelle `surface` nach Richtung des Wärmestroms. Gegen Erdreich R_se = 0; gegen einen"
        " Raum (beheizt oder nicht) R_se = R_si derselben Richtung.",
        "- Aufbau einer Decke: Rohdecke mit dem Fußbodenaufbau des Raums darüber.",
        "",
        "## Nicht abgebildet",
        "",
        "- Luftschichten, inhomogene Schichten (Sparren mit Dämmung dazwischen), Korrekturen für"
        " Befestigungsteile, Luftspalte und Umkehrdächer, keilförmige Schichten.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


UVALUE = Calculator(
    "uvalue",
    "U-Werte der Bauteile",
    "norm",
    VERSION,
    run,
    NORM,
    (),
    (MATERIAL, SURFACE),
)

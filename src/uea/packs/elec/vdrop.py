"""Voltage drop of a circuit from its board to its farthest device (decision 0028).

A `norm` calculator. The formula is that of IEC 60364-5-52 Annex G, DIN VDE 0100-520:

    dU = b * (rho1 * L / S * cos(phi) + lambda * L * sin(phi)) * Ib,   dU% = 100 * dU / U0

with b = 2 for a single-phase and b = 1 for a three-phase circuit (U0 is the voltage between
phase and neutral), rho1 the resistivity of the conductor in service, lambda its reactance per
length, L the one-way length and S the cross-section. The resistivity and the reactance come from
the office's table `conductor`; the limit is a setting the caller must give, since the
permissible drop depends on the rule the office designs to (DIN 18015-1 gives one for the whole
route from the meter, of which this circuit is only a part).

The length is the derived cable length to the farthest device (`0027-cable-routes.md`) times a
reserve; the whole current is taken to flow over the whole length, which is the safe side.
Not covered: the drop in the feeder from the house connection to the board, motor starting.
"""

import math
from dataclasses import dataclass, field

from uea.calc import Calculator, Env, Output, Param, de, md_table
from uea.calc.data import Col, Spec
from uea.derive import Derived
from uea.packs.elec.geometry import VOLT, CircGeo, circuits_in, declared_amps
from uea.packs.elec.kinds import Circ

VERSION = "0.1.0"
NORM = "DIN VDE 0100-520 (IEC 60364-5-52, Anhang G)"

CONDUCTOR = Spec(
    "conductor",
    "Conductor data for the voltage drop",
    "DIN VDE 0100-520 (IEC 60364-5-52, Annex G)",
    (
        Col("material", "text", "conductor material", ("Cu", "Al")),
        Col("rho", "num", "resistivity of the conductor in service, Ω·mm²/m"),
        Col("lambda", "num", "reactance of the cable per length, mΩ/m"),
    ),
    ("material",),
    "One row for copper (cables NYM, NYY, ...) and one for aluminium (cables starting NA) if used.",
)

PARAMS = (
    Param("limit", float, None, "the permissible voltage drop of the circuit, in % of 230 V"),
    Param("reserve", float, 1.2, "factor on the derived length, for the route on site"),
    Param("cos", float, 1.0, "power factor of the load, more than 0 and at most 1"),
    Param(
        "demand",
        float,
        1.0,
        "share of In taken as the current of a circuit with sockets, more than 0 and at most 1",
    ),
    Param(
        "current",
        str,
        "auto",
        "auto: declared load if the circuit has no socket, else In times demand; in: always In",
        ("auto", "in"),
    ),
)


@dataclass
class Row:
    id: str
    cable: str
    material: str
    phases: int
    status: str = "ok"
    """ok, fail, or nolength (nothing on the circuit has a place)."""
    basis: str = ""
    amps: float = 0.0
    far: str = ""
    derived_m: float = 0.0
    length_m: float = 0.0
    volts: float = 0.0
    percent: float = 0.0
    notes: list[str] = field(default_factory=list[str])


def material_of(el: Circ) -> str:
    """Aluminium cables have designations starting NA (NAYY); all others are copper."""
    return "Al" if el.cable.kind.startswith("NA") else "Cu"


def drop(env: Env, cg: CircGeo, el: Circ, d: Derived) -> Row:
    row = Row(cg.id, el.cable.fmt(), material_of(el), cg.phases)
    route = d.elec.routes.get(cg.id)
    far = route.far if route else None
    if far is None:
        row.status = "nolength"
        row.notes.append("nothing on it has a place, so there is no length")
        return row
    cos = env.param("cos")
    has_socket = any(d.model[k].kind == "sock" for k in cg.devices)
    load = declared_amps(cg, cos)
    if env.param("current") == "in":
        row.basis, row.amps = "In", el.breaker.amps
    elif has_socket or load is None:
        demand = env.param("demand")
        row.basis, row.amps = ("In" if demand == 1 else "share"), el.breaker.amps * demand
    else:
        row.basis, row.amps = "Last", load
    conductor = env.table(CONDUCTOR).find(material=row.material)
    if conductor is None:
        raise ValueError(
            f"the table conductor has no row for {row.material} ({row.cable} on {cg.id})"
        )
    row.far, row.derived_m = far
    row.length_m = row.derived_m * env.param("reserve")
    sin = math.sqrt(1 - cos * cos)
    b = 2 if cg.phases == 1 else 1
    ohm = float(conductor["rho"]) / el.cable.mm2 * cos + float(conductor["lambda"]) * 1e-3 * sin
    row.volts = b * row.amps * row.length_m * ohm
    row.percent = 100 * row.volts / VOLT
    row.status = "ok" if row.percent <= env.param("limit") else "fail"
    return row


def run(d: Derived, scope: str | None, env: Env) -> Output:
    limit, cos = env.param("limit"), env.param("cos")
    if limit <= 0:
        raise ValueError("limit must be more than 0 (percent)")
    if not 0 < cos <= 1:
        raise ValueError("cos must be more than 0 and at most 1")
    if not 0 < env.param("demand") <= 1:
        raise ValueError("demand must be more than 0 and at most 1")
    if env.param("reserve") < 1:
        raise ValueError("reserve must be at least 1: the derived length is a minimum")
    env.table(CONDUCTOR)
    circuits = circuits_in(d, scope)
    if not circuits:
        raise ValueError("there are no circuits")
    rows: list[Row] = []
    for cg in circuits:
        el = d.model[cg.id]
        assert isinstance(el, Circ)
        rows.append(drop(env, cg, el, d))
    done = [r for r in rows if r.status != "nolength"]
    bad = [r for r in done if r.status == "fail"]
    lines = [
        f"{len(done)} circuits: {len(done) - len(bad)} within {limit:g} %, {len(bad)} over"
        + (f", {len(rows) - len(done)} without a length" if len(rows) > len(done) else "")
    ]
    if done:
        worst = max(done, key=lambda r: r.percent)
        lines.append(f"largest: {worst.id} {worst.percent:.2f} % ({worst.volts:.2f} V)")
    for r in bad:
        lines.append(
            f"{r.id} {r.cable}: {r.percent:.2f} % > {limit:g} % ({r.volts:.2f} V,"
            f" {r.amps:.1f} A over {r.length_m:.1f} m to {r.far})"
        )
    return Output(
        lines=lines,
        report=report(d, rows, env),
        data={"circuits": {r.id: _data(r) for r in rows}},
        inputs={"circuits": [r.id for r in rows]},
        ok=not bad,
    )


def _data(r: Row) -> dict[str, object]:
    return {
        "cable": r.cable,
        "status": r.status,
        "material": r.material,
        "phases": r.phases,
        "current_basis": r.basis,
        "amps": round(r.amps, 4),
        "farthest": r.far,
        "length_derived_m": round(r.derived_m, 4),
        "length_m": round(r.length_m, 4),
        "volts": round(r.volts, 4),
        "percent": round(r.percent, 4),
        "notes": r.notes,
    }


STATUS_DE = {"ok": "eingehalten", "fail": "**überschritten**", "nolength": "ohne Länge"}


def report(d: Derived, rows: list[Row], env: Env) -> str:
    proj = d.model.of_kind("project")
    title = proj[0].label or proj[0].id if proj else "Projekt"
    head = ["Stromkreis", "Leitung", "Phasen", "Strom", "I A", "bis", "Länge m", "ΔU V", "ΔU %"]
    head.append("Ergebnis")
    body: list[list[str]] = []
    for r in rows:
        if r.status == "nolength":
            body.append(
                [r.id, r.cable, str(r.phases), "–", "–", "–", "–", "–", "–", STATUS_DE[r.status]]
            )
            continue
        basis = {
            "In": "Nennstrom der Sicherung",
            "Last": "angegebene Last",
            "share": f"{de(env.param('demand') * 100, 0)} % des Nennstroms",
        }[r.basis]
        body.append(
            [
                r.id,
                r.cable,
                str(r.phases),
                basis,
                de(r.amps, 1),
                r.far,
                de(r.length_m, 1),
                de(r.volts),
                de(r.percent),
                STATUS_DE[r.status],
            ]
        )
    cos, reserve = env.param("cos"), env.param("reserve")
    out = [
        f"# Spannungsfall der Stromkreise: {title}",
        "",
        md_table(head, body, right=(4, 6, 7, 8)),
        "",
        "## Verfahren",
        "",
        "- Formel nach DIN VDE 0100-520 (IEC 60364-5-52, Anhang G):"
        " ΔU = b · (ρ · L / S · cos φ + λ · L · sin φ) · I, ΔU % = 100 · ΔU / U₀ mit U₀ = 230 V;"
        " b = 2 einphasig, b = 1 dreiphasig. ρ und λ aus der Tabelle `conductor` des Büros.",
        f"- Grenzwert: {de(env.param('limit'), 2)} % je Stromkreis (Vorgabe des Aufrufs)."
        f" cos φ = {de(cos)}.",
        f"- Länge L: abgeleitete Leitungslänge vom Verteiler bis zum entferntesten Gerät mal"
        f" Zuschlag {de(reserve)} (Leitungsführung vor Ort). Der gesamte Strom wird auf der"
        " gesamten Länge angesetzt (auf der sicheren Seite).",
        "- Strom: bei Stromkreisen mit Steckdosen oder ohne angegebene Anschlussleistung der"
        f" Nennstrom der Sicherung, davon der Anteil {de(env.param('demand'))} (Vorgabe des"
        " Aufrufs, eine planerische Annahme); sonst der Strom der angegebenen Anschlussleistung."
        " Mit `current=in` immer der Nennstrom.",
        "",
        "## Nicht geprüft",
        "",
        "- Spannungsfall der Zuleitung vom Hausanschluss zum Verteiler (nicht im Modell), Anlauf"
        " von Motoren, Oberschwingungen.",
        "",
        "Berechnet aus dem Modell. Prüfung und Verantwortung liegen bei der unterzeichnenden"
        " fachkundigen Person.",
        "",
    ]
    return "\n".join(out)


VDROP = Calculator(
    "vdrop", "Spannungsfall der Stromkreise", "norm", VERSION, run, NORM, PARAMS, (CONDUCTOR,)
)

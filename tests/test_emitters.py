"""Emitter output at the circuit's temperatures (DIN EN 442, DIN EN 1264) and mixing circuits
(decision 0042), by hand on the box of test_hydronic: r1 living at 20 °C with uh1 on hv1, r2
bedroom at 18 °C with hk1 from the tank and hk2 from hv1."""

import math
from pathlib import Path

import pytest

from tests.conftest import derive_text, model_from
from tests.test_calc_elec import run
from tests.test_heatload import HOUSE, SETTINGS, tables
from tests.test_hydronic import HEAT, RHO_CP, TYPES, box
from uea.derive import Derived
from uea.packs.heat.emitters import floor_temp, lmtd
from uea.packs.heat.heatload import HEATLOAD
from uea.packs.heat.hydronic import HYDRONIC

EN = TYPES.replace("type HK rad w=800 default", "type HK rad wn=1000 n=1.3 default").replace(
    "type FBH ufh spacing=0.15 q=60 max=100", "type FBH ufh spacing=0.15 kh=6 max=100"
)


def test_lmtd() -> None:
    assert lmtd(75, 65, 20) == pytest.approx(10 / math.log(55 / 45))
    assert lmtd(40, 40, 20) == 20
    assert lmtd(30, 18, 20) is None
    # the basic characteristic curve: 8.92 · 9^1.1 W/m² at 9 K
    assert floor_temp(8.92 * 9**1.1, 20) == pytest.approx(29)


def test_radiator_and_floor_at_their_temperatures(tmp_path: Path) -> None:
    tables(tmp_path)
    d = box(types=EN)
    o = run(HEATLOAD, d, None, **SETTINGS, flow=55, spread=10)
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict)
    # hk1 in r2 at 18 °C, 55/45: Φ = 1000 · (Δθ / Δθ_n)^1.3
    dt = 10 / math.log(37 / 27)
    dn = 10 / math.log(55 / 45)
    assert rooms["r2"]["emitters"]["hk1"] == pytest.approx(1000 * (dt / dn) ** 1.3, abs=0.1)
    # uh1 in r1 at 20 °C, on the system's 55/45 too: q = 6 · Δθ_H
    area = d.heat.loops["uh1"].area
    dth = 10 / math.log(35 / 25)
    assert rooms["r1"]["emitters"]["uh1"] == pytest.approx(6 * dth * area, abs=0.1)
    tf = 20 + (6 * dth / 8.92) ** (1 / 1.1)
    assert rooms["r1"]["floor"]["uh1"] == pytest.approx(tf, abs=0.01)
    # a limit of 29 °C: the floor is too warm, the result fails
    o = run(HEATLOAD, d, None, **SETTINGS, flow=55, spread=10, floor=29)
    assert not o.ok
    assert any(f"uh1 floor {tf:.1f} °C > 29" in x for x in o.lines)
    # without the temperatures a type of DIN EN values has no output
    o = run(HEATLOAD, d, None, **SETTINGS)
    rooms = o.data["rooms"]
    assert isinstance(rooms, dict)
    assert rooms["r2"]["emitters"]["hk1"] == 0


def test_the_manifold_fields() -> None:
    with pytest.raises(ValueError, match="a mixing circuit needs its flow= temperature"):
        model_from("man hv1 w5.w t1 y=1 mix\n")
    with pytest.raises(ValueError, match=r"give w= .* or wn= and n="):
        model_from("type HK rad length=1\n")
    with pytest.raises(ValueError, match="wn= and n= go together"):
        model_from("type HK rad wn=1000\n")
    with pytest.raises(ValueError, match=r"give q= .* or kh="):
        model_from("type F ufh spacing=0.15 max=100\n")


def mixed(tmp_path: Path) -> Derived:
    tables(tmp_path)
    heat = HEAT.replace("man hv1 w5.w t1 y=S+1", "man hv1 w5.w t1 y=S+1 flow=35 spread=5 mix")
    text = HOUSE.replace("type TI door default\n", "type TI door default\n" + EN)
    d, rep = derive_text(text + heat)
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-HEAT"))] == []
    return d


def test_a_mixing_circuit(tmp_path: Path) -> None:
    d = mixed(tmp_path)
    o = run(HYDRONIC, d, None, **{**SETTINGS, "flow": 55, "spread": 10, "vmax": 0.5})
    em = o.data["emitters"]
    assert isinstance(em, dict)
    # behind hv1 the spread is 5 K, hk1 on the tank has the system's 10 K
    assert em["uh1"]["q"] == pytest.approx(em["uh1"]["phi"] / (RHO_CP * 5), rel=1e-3)
    assert em["hk2"]["q"] == pytest.approx(em["hk2"]["phi"] / (RHO_CP * 5), rel=1e-3)
    assert em["hk1"]["q"] == pytest.approx(em["hk1"]["phi"] / (RHO_CP * 10), rel=1e-3)
    mx = o.data["mixers"][0]  # type: ignore[index]
    phi: float = em["uh1"]["phi"] + em["hk2"]["phi"]  # type: ignore[index]
    # from the system at 55 °C down to the circuits' return of 30 °C
    assert (mx["man"], mx["flow"], mx["ret"]) == ("hv1", 35, 30)
    assert mx["primary"] == pytest.approx(phi / (RHO_CP * 25), rel=1e-3)
    assert mx["secondary"] == pytest.approx(em["uh1"]["q"] + em["hk2"]["q"], rel=1e-4)
    pipes = {p["b"]: p for p in o.data["pipes"]}  # type: ignore[union-attr]
    # the pipe from t1 to hk1 carries hk1 and hv1's primary flow, not its circuits'
    assert pipes["hk1"]["q"] == pytest.approx(em["hk1"]["q"] + mx["primary"], rel=1e-4)
    pumps = {p["root"]: p for p in o.data["pumps"]}  # type: ignore[union-attr]
    circ = {c["el"]: c for c in o.data["circuits"]}  # type: ignore[union-attr]
    # hv1's own pump lifts its worst circuit; t1's pump ends at the mixing valve
    assert pumps["hv1"]["mix"] is True
    assert pumps["hv1"]["head"] == pytest.approx(
        max(circ["uh1"]["dp"], circ["hk2"]["dp"]), abs=0.01
    )
    ends = {e["el"]: e for e in o.data["ends"]}  # type: ignore[union-attr]
    assert ends["hv1"]["own"] == 0
    assert mx["valve"] == pytest.approx(ends["hv1"]["throttle"], abs=0.01)
    assert any(x.startswith("mixer hv1 35/30 °C:") for x in o.lines)
    # mixing needs the system's flow temperature, and a colder circuit
    with pytest.raises(ValueError, match="hv1 mixes: give flow=<°C>"):
        run(HYDRONIC, d, None, **{**SETTINGS, "spread": 10, "vmax": 0.5})
    with pytest.raises(ValueError, match="it must be colder than the system's 30"):
        run(HYDRONIC, d, None, **{**SETTINGS, "flow": 30, "spread": 10, "vmax": 0.5})

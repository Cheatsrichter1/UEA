"""Heating pipes and the hydraulic balance (decision 0037), by hand on the box of test_heatload:
r1 (living, west of w5) with underfloor heating, r2 (bedroom, east of w5) with two radiators of
the same output, one fed from the tank, one from the manifold on w5."""

import math
from pathlib import Path

import pytest

from tests.conftest import Shell, derive_text
from tests.test_calc_elec import run
from tests.test_heatload import HOUSE, SETTINGS, tables
from uea.calc import Output
from uea.derive import Derived
from uea.packs.heat.heatload import HEATLOAD
from uea.packs.heat.hydronic import HYDRONIC, kv
from uea.packs.heat.views import describe
from uea.packs.hydraulics import full

TYPES = (
    "type CU hpipe sizes=15x1,18x1,22x1 k=0.0015 bend=0.5 tee=1.3 default\n"
    "type FBH ufh spacing=0.15 q=60 max=100 pipe=16x2 k=0.007 default\n"
    "type HK rad w=800 default\n"
    "type WP gen kw=8 dp=100 default\n"
    "type SP tank vol=200 default\n"
    "type HKV man outlets=8 default\n"
)
HEAT = (
    "room r2 EG bedroom at=E-1,S+1 floor=FB\n"
    "gen g1 EG at=E+1,S+1\n"
    "tank t1 r1 at=W+1,N-1 src=g1\n"
    "man hv1 w5.w t1 y=S+1\n"
    "ufh uh1 r1 hv1\n"
    "rad hk1 w3 t1 x=E-2\n"
    "rad hk2 w5.e hv1 y=N-1\n"
)
RHO_CP = 992.2 * 4.179
"""Water at 40 °C, kJ/(m³·K)."""


def box(extra: str = "", types: str = TYPES) -> Derived:
    text = HOUSE.replace("type TI door default\n", "type TI door default\n" + types)
    d, rep = derive_text(text + HEAT + extra)
    assert [i for i in rep.issues if i.code.startswith(("E-", "W-HEAT"))] == []
    return d


def balance(d: Derived, **given: str | float) -> Output:
    return run(HYDRONIC, d, None, **{**SETTINGS, "spread": 5, "vmax": 0.5, **given})


def test_the_pipes_are_derived() -> None:
    d = box()
    nets = d.heat.nets
    # g1 (11, 1, z 0) to t1 (1, 7, z 0): 10 + 6
    assert [(s.name, s.length, s.legs) for s in nets["g1"].sections] == [("g1>t1", 16.0, 2)]
    # t1 to hk1 on w3's inner face (8, 7.7, z 0.45): 7 + 0.7 + 0.45, then on to hv1 on w5's
    # west face (5, 1, z 0.6): 3 + 6.7 + 0.15, the shortest tree
    t1 = [(s.name, round(s.length, 3), s.legs) for s in nets["t1"].sections]
    assert t1 == [("t1>hk1", 8.15, 3), ("hk1>hv1", 9.85, 3)]
    assert nets["t1"].sections[0].serves == ["hk1", "hv1"]
    # the manifold's home run to hk2 on w5's east face (5.115, 7): 0.115 + 6 + 0.15
    assert [(s.name, round(s.length, 3), s.kind) for s in nets["hv1"].sections] == [
        ("hv1>hk2", 6.265, "home")
    ]
    assert describe(d, d.model["hv1"])[-1] == (
        "pipes 18.0 m from t1, 6.3 m to hk2 (flow and return each)"
    )


def test_flows_sizes_and_the_balance(tmp_path: Path) -> None:
    tables(tmp_path)
    d = box()
    loads = run(HEATLOAD, d, None, **SETTINGS).data["rooms"]
    assert isinstance(loads, dict)
    o = balance(d)
    assert o.ok
    em = o.data["emitters"]
    assert isinstance(em, dict)
    r1, r2 = loads["r1"]["phi"], loads["r2"]["phi"]  # type: ignore[index]
    # the room's load, shared by output: hk1 and hk2 have the same
    assert em["uh1"]["phi"] == pytest.approx(r1, abs=0.1)  # type: ignore[index]
    assert em["hk1"]["phi"] == pytest.approx(r2 / 2, abs=0.1)  # type: ignore[index]
    q: dict[str, float] = {k: v["phi"] / (RHO_CP * 5) for k, v in em.items()}  # type: ignore[index]
    assert em["uh1"]["q"] == pytest.approx(q["uh1"], rel=1e-4)  # type: ignore[index]

    pipes = {p["b"]: p for p in o.data["pipes"]}  # type: ignore[union-attr]
    # all the flow through t1>hk1: 18x1 (16 mm) would run faster than 0.5 m/s, 22x1 (20 mm)
    total = q["uh1"] + q["hk1"] + q["hk2"]
    v20 = total / 1000 / (math.pi * 0.02**2 / 4)
    v16 = total / 1000 / (math.pi * 0.016**2 / 4)
    assert v16 > 0.5 > v20
    assert (pipes["hk1"]["size"], pipes["hk1"]["v"]) == ("22x1", pytest.approx(v20, abs=1e-3))
    # flow and return: 2 · (R · l + ζ · ρv²/2), ζ two bends, and at hk1>hv1 a tee
    f = full(total, 20, 0.0015, "heating")
    assert pipes["hk1"]["dp"] == pytest.approx(2 * (f.r * 8.15 + 1.0 * f.dyn), abs=0.01)
    assert pipes["hv1"]["zeta"] == pytest.approx(2 * 0.5 + 1.3)
    assert pipes["t1"]["q"] == pytest.approx(total, rel=1e-4)  # g1>t1 carries all of it

    # the manifold: uh1's loops share its flow
    lp = d.heat.loops["uh1"]
    circ = {c["el"]: c for c in o.data["circuits"]}  # type: ignore[union-attr]
    loop = full(q["uh1"] / lp.n, 12, 0.007, "heating")
    assert circ["uh1"]["loops"] == lp.n
    assert circ["uh1"]["dp"] == pytest.approx(loop.r * lp.each, abs=0.01)
    home = full(q["hk2"], 13, 0.0015, "heating")  # 15x1, within 0.5 m/s
    assert circ["hk2"]["size"] == "15x1"
    assert circ["hk2"]["dp"] == pytest.approx(2 * (home.r * 6.265 + 1.0 * home.dyn), abs=0.01)
    # the loops are the index circuit; hk2's valve takes the difference
    assert circ["uh1"]["valve"] == 0 and circ["uh1"]["kv"] is None
    valve = circ["uh1"]["dp"] - circ["hk2"]["dp"]
    assert circ["hk2"]["valve"] == pytest.approx(valve, abs=0.01)
    assert circ["hk2"]["kv"] == pytest.approx(q["hk2"] * 3.6 / math.sqrt(valve / 1000), rel=1e-3)

    # the ways from t1: hv1 is the index; hk1 is throttled by the rest of hv1's way
    ends = {(e["net"], e["el"]): e for e in o.data["ends"]}  # type: ignore[union-attr]
    assert ends[("t1", "hk1")]["throttle"] == pytest.approx(
        pipes["hv1"]["dp"] + circ["uh1"]["dp"], abs=0.02
    )
    pumps = {p["root"]: p for p in o.data["pumps"]}  # type: ignore[union-attr]
    assert pumps["t1"]["head"] == pytest.approx(
        pipes["hk1"]["dp"] + pipes["hv1"]["dp"] + circ["uh1"]["dp"], abs=0.02
    )
    assert pumps["t1"]["index"] == "hv1 uh1"
    # the generator's circuit: its pipe and its own loss from the type
    assert pumps["g1"]["head"] == pytest.approx(pipes["t1"]["dp"] + 100, abs=0.01)
    assert "pump g1: " in o.lines[-2] and "(index t1, g1 100)" in o.lines[-2]
    assert "# Rohrnetz und hydraulischer Abgleich" in o.report
    assert "| hv1 | hk2 | r2 |" in o.report


def test_too_fast_and_unheated(tmp_path: Path) -> None:
    tables(tmp_path)
    # a pipe system too small for the flow: the largest size, and the result fails
    d = box(types=TYPES.replace("sizes=15x1,18x1,22x1", "sizes=10x1"))
    o = balance(d)
    assert not o.ok and "(too fast: the largest size)" in "\n".join(o.lines)
    # r2 a storage room, which the table room-temp does not heat: its radiators get no flow
    d, _ = derive_text(
        HOUSE.replace("type TI door default\n", "type TI door default\n" + TYPES)
        + HEAT.replace("r2 EG bedroom", "r2 EG storage")
    )
    o = balance(d)
    assert o.lines[-1] == "no flow (unheated rooms): hk1 hk2"
    circ = {c["el"]: c for c in o.data["circuits"]}  # type: ignore[union-attr]
    assert circ["hk2"]["q"] == 0


def test_what_it_needs(tmp_path: Path) -> None:
    tables(tmp_path)
    with pytest.raises(ValueError, match="no heating pipe type is marked default"):
        balance(box(types=TYPES.replace(" tee=1.3 default", " tee=1.3")))
    with pytest.raises(ValueError, match="FBH of uh1 needs pipe="):
        balance(box(types=TYPES.replace(" pipe=16x2 k=0.007", "")))
    with pytest.raises(ValueError, match="spread and vmax must be more than 0"):
        balance(box(), spread=0)
    assert kv(0.1, 0.5) is None and kv(0.1, 1000) == pytest.approx(0.36)


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    tables(tmp_path)
    text = HOUSE.replace("type TI door default\n", "type TI door default\n" + TYPES) + HEAT
    code, out = sh(
        "apply", "--by", "t", "-m", "heat", stdin="".join(f"+ {x}\n" for x in _ops(text))
    )
    assert code == 0, out
    code, out = sh("calc", "hydronic", "tb=0.05", "n50=3", "shielding=moderate", "spread=5",
                   "vmax=0.5")  # fmt: skip
    assert code == 0 and "pump t1: " in out and "report: out/hydronic.md" in out, out
    code, out = sh("export", "pdf", "hydronic")
    assert code == 0 and "hydronic.pdf A4" in out, out


def _ops(text: str) -> list[str]:
    import re

    return re.sub(r"\b((?:w|sl|f|r|g|t|hv|uh|hk)\d)\b", r"@\1", text).splitlines()


def test_on_the_sheets() -> None:
    from uea.export.drawing import Line
    from uea.export.tables_tga import tga_tables
    from uea.export.tga import H_FLOW, H_RETURN, sheet_tga

    d = box()
    dw = sheet_tga(d, "EG", "heat")
    assert dw is not None
    flow = [it for it in dw.items if isinstance(it, Line) and it.layer == H_FLOW]
    ret = [it for it in dw.items if isinstance(it, Line) and it.layer == H_RETURN]
    # four sections (g1>t1, t1>hk1, hk1>hv1, hv1>hk2), x then y: two lines each; flow and return
    assert len(flow) == len(ret) == 8
    got = {t.name: t for t in tga_tables(d)}
    rows = [r for r in got["Rohrleitungen"].rows if str(r[0]).startswith("Heizung")]
    assert [(r[0], r[1], r[2], r[4]) for r in rows] == [
        ("Heizung ab g1", "g1", "t1", "Leitung"),
        ("Heizung ab t1", "t1", "hk1", "Leitung"),
        ("Heizung ab t1", "hk1", "hv1", "Leitung"),
        ("Heizung ab hv1", "hv1", "hk2", "Anbindeleitung"),
    ]
    q = {r[0]: r[2] for r in got["Rohrmengen"].rows}
    assert q["Heizung Vor- und Rücklauf ab t1"] == pytest.approx(2 * (8.15 + 9.85))

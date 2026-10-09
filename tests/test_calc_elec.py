"""The electrical calculators `cable` and `vdrop` (decision 0028), hand-computed on the 10 x 8 box
house of test_elec with our own synthetic tables (they are not a standard's values)."""

from pathlib import Path

import pytest

from tests.conftest import Shell, derive_text
from tests.test_cli import build
from tests.test_elec import BOARD, HOUSE
from uea.calc import Calculator, Env, Output, split_args
from uea.calc import data as norm_data
from uea.derive import Derived
from uea.packs.elec.cable import AMPACITY, CABLE, GROUPING, TEMPERATURE
from uea.packs.elec.vdrop import CONDUCTOR, VDROP, material_of

AMP = """\
method,insulation,loaded,mm2,amps
B2,PVC,2,1.5,12
B2,PVC,2,2.5,16
B2,PVC,2,4,22
B2,PVC,3,2.5,14
C,PVC,2,1.5,15
"""
TEMP = "insulation,celsius,factor\nPVC,40,0.8\n"
GROUP = "arrangement,circuits,factor\nbundled,3,0.7\n"
COND = "material,rho,lambda\nCu,0.02,0.1\nAl,0.036,0.1\n"

CIRCUITS = (
    'circ c3 fi1 NYM-J3x1.5 B16 "too small"\n'
    "circ c4 fi1 NYM-J5x2.5 B16 p=3\n"
    "circ c5 fi1 NYM-J3x6 B25\n"
    "circ c6 fi1 NYM-J3x2.5 K10\n"
)


def install(name: str, spec: norm_data.Spec, text: str, tmp_path: Path) -> None:
    f = tmp_path / f"{name}.csv"
    f.write_text(text)
    table, errors = norm_data.add(spec, f, "synthetic test values")
    assert table is not None, errors


def run(calc: Calculator, d: Derived, scope: str | None = None, **given: str | float) -> Output:
    env = Env(calc, {k: str(v) for k, v in given.items()})
    o: Output = calc.fn(d, scope, env)
    o.tables = [*o.tables, *env.cites]  # what `uea calc` adds
    return o


def circuits(extra: str = "") -> Derived:
    d, rep = derive_text(HOUSE + BOARD + CIRCUITS + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d


# ---------- settings ----------


def test_split_args() -> None:
    assert split_args([]) == (None, {})
    assert split_args(["c3", "limit=3", "cos=0.9"]) == ("c3", {"limit": "3", "cos": "0.9"})
    assert split_args(["limit=3"]) == (None, {"limit": "3"})
    with pytest.raises(ValueError, match="one scope at most"):
        split_args(["c1", "c2"])


def test_settings_are_checked() -> None:
    with pytest.raises(ValueError, match=r"vdrop needs limit=<value>: the permissible"):
        Env(VDROP, {})
    with pytest.raises(ValueError, match=r"unknown setting nope=\. vdrop takes: limit, reserve"):
        Env(VDROP, {"limit": "3", "nope": "1"})
    with pytest.raises(ValueError, match="limit=x is not a float"):
        Env(VDROP, {"limit": "x"})
    with pytest.raises(ValueError, match="current=zzz is not one of auto, in"):
        Env(VDROP, {"limit": "3", "current": "zzz"})
    e = Env(CABLE, {"method": "B2", "insulation": "pvc", "group": "3"})
    assert e.values == {
        "method": "B2",
        "insulation": "PVC",
        "temp": None,
        "group": 3,
        "arrangement": "",
    }


def test_a_calculator_without_its_table_stops(tmp_path: Path) -> None:
    d = circuits()
    with pytest.raises(norm_data.MissingTable, match="uea data add ampacity"):
        run(CABLE, d, method="B2")
    install("a", AMPACITY, AMP, tmp_path)
    with pytest.raises(norm_data.MissingTable, match="uea data add temp-factor"):
        run(CABLE, d, method="B2", temp=40)
    with pytest.raises(norm_data.MissingTable, match="uea data add conductor"):
        run(VDROP, d, limit=3)


# ---------- cable ----------


def test_cable_at_reference_conditions(tmp_path: Path) -> None:
    install("a", AMPACITY, AMP, tmp_path)
    d = circuits("sock s1 w4 c2 y=w1+2\n")
    o = run(CABLE, d, method="B2")
    got = o.data["circuits"]
    # c1 NYM-J3x1.5 B10: Iz 12 A >= 10 A. c2 NYM-J3x2.5 B16: Iz 16 A = In, allowed
    assert (got["c1"]["status"], got["c1"]["iz"]) == ("ok", 12.0)
    assert (got["c2"]["status"], got["c2"]["iz"]) == ("ok", 16.0)
    # c3 NYM-J3x1.5 B16: 16 A > 12 A; 2.5 mm² is the smallest row that carries 16 A
    assert (got["c3"]["status"], got["c3"]["smallest_mm2"]) == ("fail", 2.5)
    # c4 three-phase: three loaded conductors, 14 A < 16 A, and no larger row
    assert (got["c4"]["status"], got["c4"]["iz"], got["c4"]["smallest_mm2"]) == (
        "fail",
        14.0,
        None,
    )
    assert got["c4"]["loaded"] == 3
    # c5 6 mm²: the table has no such row. c6 characteristic K: I2 not known
    assert (
        got["c5"]["status"] == "nodata"
        and "no row for B2 PVC 2 loaded 6 mm²" in got["c5"]["notes"][0]
    )
    assert got["c6"]["status"] == "open"
    assert o.lines[0] == "6 circuits: 2 ok, 2 fail, 1 without table data, 1 not checked"
    assert o.lines[1] == "c3 NYM-J3x1.5 B16: In 16 A > Iz 12.0 A; smallest in table 2.5 mm²"
    assert o.lines[2] == "c4 NYM-J5x2.5 B16: In 16 A > Iz 14.0 A; none in table"
    assert not o.ok
    assert o.tables[0].startswith("ampacity (DIN VDE 0298-4), Ausgabe synthetic test values")


def test_cable_other_installation_method(tmp_path: Path) -> None:
    install("a", AMPACITY, AMP, tmp_path)
    got = run(CABLE, circuits(), "c1", method="C").data["circuits"]
    assert got["c1"]["iz"] == 15.0
    got = run(CABLE, circuits(), "c2", method="C").data["circuits"]
    assert got["c2"]["status"] == "nodata"


def test_cable_corrections_for_temperature_and_grouping(tmp_path: Path) -> None:
    install("a", AMPACITY, AMP, tmp_path)
    install("t", TEMPERATURE, TEMP, tmp_path)
    install("g", GROUPING, GROUP, tmp_path)
    d = circuits()
    # 40 °C: factor 0.8. c1: 12 * 0.8 = 9.6 A < 10 A. c2: 16 * 0.8 = 12.8 A < 16 A and 4 mm²
    # carries it: 22 * 0.8 = 17.6 A
    got = run(CABLE, d, method="B2", temp=40).data["circuits"]
    assert (got["c1"]["status"], got["c1"]["iz"], got["c1"]["k_temp"]) == ("fail", 9.6, 0.8)
    assert (got["c2"]["status"], got["c2"]["smallest_mm2"]) == ("fail", 4.0)
    # three grouped circuits, bundled: 0.7. c1: 12 * 0.7 = 8.4 A
    got = run(CABLE, d, "c1", method="B2", group=3, arrangement="Bundled").data["circuits"]
    assert (got["c1"]["iz"], got["c1"]["k_group"]) == (pytest.approx(8.4), 0.7)
    # both: 12 * 0.8 * 0.7 = 6.72 A
    got = run(CABLE, d, "c1", method="B2", temp=40, group=3, arrangement="bundled")
    assert got.data["circuits"]["c1"]["iz"] == pytest.approx(6.72)
    assert len(got.tables) == 3
    # a temperature or a group the table does not list
    bad = run(CABLE, d, "c1", method="B2", temp=35).data["circuits"]["c1"]
    assert bad["status"] == "nodata" and "no row for PVC at 35 °C" in bad["notes"][0]
    bad = run(CABLE, d, "c1", method="B2", group=4, arrangement="bundled").data["circuits"]["c1"]
    assert bad["status"] == "nodata" and "'bundled' with 4" in bad["notes"][0]


def test_cable_declared_load_above_the_breaker(tmp_path: Path) -> None:
    install("a", AMPACITY, AMP, tmp_path)
    # 3680 W on c2 (16 A at 230 V) is fine; 4600 W is 20 A on a B16
    ok = circuits("conn a1 w4 c2 y=w1+2 w=3680\n")
    got = run(CABLE, ok, "c2", method="B2").data["circuits"]["c2"]
    assert (got["status"], got["ib_declared"]) == ("ok", 16.0)
    over = circuits("conn a1 w4 c2 y=w1+2 w=4600\n")
    got = run(CABLE, over, "c2", method="B2").data["circuits"]["c2"]
    assert got["status"] == "fail" and got["ib_declared"] == 20.0
    assert "the declared load needs 20.0 A, more than In" in got["notes"]


def test_scopes() -> None:
    d = circuits()
    assert [
        c.id for c in __import__("uea.packs.elec.geometry", fromlist=["x"]).circuits_in(d, "fi1")
    ] == [
        "c1",
        "c2",
        "c3",
        "c4",
        "c5",
        "c6",
    ]
    with pytest.raises(ValueError, match="'zz' is not a circuit, an RCD or a board"):
        __import__("uea.packs.elec.geometry", fromlist=["x"]).circuits_in(d, "zz")


# ---------- vdrop ----------


def test_voltage_drop_single_phase_on_sockets(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    d = circuits("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3\n")
    o = run(VDROP, d, "c2", limit=0.4)
    r = o.data["circuits"]["c2"]
    # the cable reaches s2 at 3.7 m; times the reserve 1.2 is 4.44 m. The circuit has sockets,
    # so the current is In = 16 A. dU = 2 * 16 * 4.44 * (0.02 / 2.5) = 1.13664 V = 0.49419 %
    assert (r["farthest"], r["current_basis"], r["amps"]) == ("s2", "In", 16.0)
    assert r["length_derived_m"] == pytest.approx(3.7) and r["length_m"] == pytest.approx(4.44)
    assert r["volts"] == pytest.approx(1.13664, abs=1e-4)
    assert r["percent"] == pytest.approx(0.49419, abs=1e-4)
    assert r["status"] == "fail" and not o.ok
    assert o.lines[0] == "1 circuits: 0 within 0.4 %, 1 over"
    assert o.lines[2] == "c2 NYM-J3x2.5: 0.49 % > 0.4 % (1.14 V, 16.0 A over 4.4 m to s2)"
    ok = run(VDROP, d, "c2", limit=0.5)
    assert ok.ok and ok.data["circuits"]["c2"]["status"] == "ok"


def test_voltage_drop_with_a_power_factor_and_a_reserve(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    d = circuits("sock s1 w4 c2 y=w1+2\nsock s2 w4 c2 y=w1+3\n")
    # cos 0.8, sin 0.6: dU = 2 * 16 * 4.44 * (0.008 * 0.8 + 0.0001 * 0.6) = 142.08 * 0.00646
    r = run(VDROP, d, "c2", limit=3, cos=0.8).data["circuits"]["c2"]
    assert r["volts"] == pytest.approx(0.917837, abs=1e-4)
    # half of In on the sockets: 8 A, so half the drop: 0.56832 V
    r = run(VDROP, d, "c2", limit=3, demand=0.5).data["circuits"]["c2"]
    assert (r["current_basis"], r["amps"]) == ("share", 8.0)
    assert r["volts"] == pytest.approx(0.56832, abs=1e-4)
    # current=in ignores the share
    r = run(VDROP, d, "c2", limit=3, demand=0.5, current="in").data["circuits"]["c2"]
    assert (r["current_basis"], r["amps"]) == ("In", 16.0)
    # no reserve: 3.7 m, dU = 2 * 16 * 3.7 * 0.008
    r = run(VDROP, d, "c2", limit=3, reserve=1).data["circuits"]["c2"]
    assert r["volts"] == pytest.approx(0.94720, abs=1e-4)


def test_voltage_drop_three_phase_on_a_declared_load(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    d = circuits("conn a1 w4 c4 y=w1+3 w=9000\n")
    r = run(VDROP, d, "c4", limit=3).data["circuits"]["c4"]
    # the cable: board (0.3, 1.3, 1.4) to a1 (0.3, 3.3, 0.3) is 2.0 + 1.1 + 0.3 = 3.4 m, times 1.2
    # is 4.08 m. No socket: the declared load, 9000 W / (3 * 230 V) = 13.0435 A. b = 1:
    # dU = 13.0435 * 4.08 * 0.02 / 2.5 = 0.42574 V = 0.18510 %
    assert (r["current_basis"], r["phases"]) == ("Last", 3)
    assert r["amps"] == pytest.approx(13.0435, abs=1e-4)
    assert r["volts"] == pytest.approx(0.42574, abs=1e-4)
    assert r["percent"] == pytest.approx(0.18510, abs=1e-4)
    # current=in takes the breaker instead: 16 A
    r = run(VDROP, d, "c4", limit=3, current="in").data["circuits"]["c4"]
    assert (r["current_basis"], r["amps"]) == ("In", 16.0)
    assert r["volts"] == pytest.approx(16 * 4.08 * 0.008, abs=1e-4)


def test_voltage_drop_aluminium(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    d = circuits('circ c7 fi1 NAYY-J3x16 B25 "garage"\nsock s3 w4 c7 y=w1+5\n')
    assert material_of(d.model["c7"]) == "Al"  # type: ignore[arg-type]
    assert material_of(d.model["c1"]) == "Cu"  # type: ignore[arg-type]
    r = run(VDROP, d, "c7", limit=3).data["circuits"]["c7"]
    # board to s3 (0.3, 5.3, 0.3): 4.0 + 1.1 + 0.3 = 5.4 m, times 1.2 is 6.48 m; B25 on a socket:
    # dU = 2 * 25 * 6.48 * 0.036 / 16 = 0.729 V
    assert r["material"] == "Al" and r["volts"] == pytest.approx(0.729, abs=1e-4)


def test_voltage_drop_circuit_without_a_place(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    o = run(VDROP, circuits(), "c1", limit=3)
    assert o.data["circuits"]["c1"]["status"] == "nolength"
    assert o.lines == ["0 circuits: 0 within 3 %, 0 over, 1 without a length"]
    assert o.ok


def test_voltage_drop_settings_are_checked(tmp_path: Path) -> None:
    install("c", CONDUCTOR, COND, tmp_path)
    d = circuits()
    for given, message in (
        ({"limit": 0}, "limit must be more than 0"),
        ({"limit": 3, "cos": 1.5}, "cos must be more than 0"),
        ({"limit": 3, "reserve": 0.9}, "reserve must be at least 1"),
        ({"limit": 3, "demand": 0}, "demand must be more than 0"),
        ({"limit": 3, "demand": 1.2}, "demand must be more than 0"),
    ):
        with pytest.raises(ValueError, match=message):
            run(VDROP, d, **{k: str(v) for k, v in given.items()})


def test_voltage_drop_needs_a_conductor_row(tmp_path: Path) -> None:
    install("c", CONDUCTOR, "material,rho,lambda\nCu,0.02,0.1\n", tmp_path)
    d = circuits("circ c7 fi1 NAYY-J3x16 B25\nsock s3 w4 c7 y=w1+5\n")
    with pytest.raises(ValueError, match="no row for Al"):
        run(VDROP, d, "c7", limit=3)


# ---------- the command ----------


def test_the_commands(sh: Shell, tmp_path: Path) -> None:
    from tests.test_cli import ELEC

    build(sh)
    assert sh("apply", "--by", "t", "-m", "Elektro", stdin=ELEC)[0] == 0
    code, out = sh("calc")
    assert "cable  norm 0.1.0  Leitungsquerschnitt (Überlastschutz)" in out
    assert "vdrop  norm 0.1.0  Spannungsfall der Stromkreise" in out
    # without the table, the calculator says which one to add
    code, out = sh("calc", "cable", "method=B2")
    assert code == 1 and out.startswith("cable: the table 'ampacity'")
    code, out = sh("calc", "vdrop")
    assert code == 1 and out.startswith("vdrop: vdrop needs limit=<value>")
    code, out = sh("calc", "cable", "nope=1")
    assert code == 1 and "unknown setting nope=" in out
    code, out = sh("calc", "wofl", "limit=3")
    assert code == 1 and "wofl takes no settings (got limit)" in out
    a, c = tmp_path / "a.csv", tmp_path / "c.csv"
    a.write_text(AMP)
    c.write_text(COND)
    assert sh("data", "add", "ampacity", str(a), "--edition", "synthetic")[0] == 0
    assert sh("data", "add", "conductor", str(c), "--edition", "synthetic")[0] == 0
    code, out = sh("calc", "cable", "method=B2")
    assert code == 0
    assert out.splitlines()[0].startswith(
        "norm cable 0.1.0 · Leitungsquerschnitt (Überlastschutz) · all"
    )
    assert out.splitlines()[1] == "2 circuits: 2 ok, 0 fail"
    # the record has the settings and the table with its edition
    rec = __import__("json").loads((sh.root / "out" / "cable.json").read_text())
    assert rec["kind"] == "norm" and rec["inputs"]["settings"]["method"] == "B2"
    assert rec["tables"][0].startswith("ampacity (DIN VDE 0298-4), Ausgabe synthetic")
    assert "Normtabellen | ampacity" in (sh.root / "out" / "cable.md").read_text()
    code, out = sh("calc", "vdrop", "c2", "limit=3", "reserve=1.5")
    assert code == 0 and out.splitlines()[1] == "1 circuits: 1 within 3 %, 0 over"
    assert (sh.root / "out" / "vdrop-c2.json").exists()

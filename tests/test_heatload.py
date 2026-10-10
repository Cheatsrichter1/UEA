"""U-values (DIN EN ISO 6946) and the Heizlast (DIN EN 12831-1), decision 0033, computed by hand
on a 10 x 8 box of two rooms with synthetic tables of our own (they are not a standard's values).

The box: exterior walls with a 0.3 m core, the shell of r1 is 4.7 x 7.4 m, of r2 4.585 x 7.4 m,
the storey 3 m from FFL to FFL, the slab above with nothing on it (a flat roof).
"""

import re
from pathlib import Path

import pytest

from tests.conftest import Shell, derive_text
from tests.test_calc_elec import install, run
from uea.calc import Output
from uea.calc import data as norm_data
from uea.derive import Derived
from uea.packs.heat.envelope import envelope
from uea.packs.heat.heatload import (
    FACTORS,
    HEATLOAD,
    HEIGHT,
    INFILTRATION,
    OUTDOOR,
    ROOM_TEMP,
)
from uea.packs.heat.thermal import MATERIAL, SURFACE
from uea.packs.heat.uvalue import UVALUE
from uea.project import Project

HOUSE = """\
project box "Box" postcode=12345
level EG z=0 fb=0.15 head=2.26
level OG z=3 fb=0.15
grid W x=0
grid E x=10
grid S y=0
grid N y=8
type AW wall layers=gips:0.01,*mw:0.3,putz:0.02
type IW wall layers=gips:0.01,*ks:0.115,gips:0.01
type BP slab layers=*stb:0.2,xps:0.1
type DE slab layers=*stb:0.2,eps:0.2
type FB floor layers=estrich:0.05
type FE win uw=1 default
type TI door default
wall w1 EG AW y=S+ x=W..E lb
wall w2 EG AW x=E- y=w1..w3 lb
wall w3 EG AW y=N- x=W..E lb
wall w4 EG AW x=W+ y=w1..w3 lb
wall w5 EG IW x=W+5 y=w1..w3
slab sl1 EG BP
slab sl2 OG DE
win f1 w1 1.2x1.2 x=W+1
room r1 EG living at=W+1,S+1 floor=FB
"""
R2 = "room r2 EG bedroom at=E-1,S+1 floor=FB\n"

# R = d / λ: gips 0.01/0.25 = 0.04, mw 0.3/0.05 = 6, putz 0.02/0.5 = 0.04, ks 0.115/0.25 = 0.46,
# stb 0.2/2 = 0.1, xps 0.1/0.04 = 2.5, eps 0.2/0.04 = 5, estrich 0.05/1 = 0.05
MAT = (
    "# synthetic\nmaterial,lambda\ngips,0.25\nmw,0.05\nputz,0.5\nks,0.25\nstb,2\nxps,0.04\n"
    "eps,0.04\nestrich,1\n"
)
SURF = "flow,rsi,rse\nup,0.10,0.04\nhorizontal,0.13,0.04\ndown,0.17,0.04\n"
OUT = "postcode,te,tme\n12345,-10,10\n"
TEMP = (
    "use,heated,ti,nmin\nliving,yes,20,0.5\nbedroom,yes,18,0.5\nstorage,no,5,0\nkitchen,yes,20,1\n"
)
INF = "openings,shielding,e\n0,moderate,0\n1,moderate,0.02\n2+,moderate,0.03\n"
EPS = "upto,eps\n10,1\n30,1.2\n"
FAC = "name,value\nfg1,1.45\ngw-deep,1\ngw-shallow,1.15\nrho-cp,0.34\n"

U_AW = 1 / (0.13 + 0.04 + 6 + 0.04 + 0.04)  # 0.16
U_IW = 1 / (0.13 + 0.04 + 0.46 + 0.04 + 0.13)  # 1.25
U_FLOOR = 1 / (0.17 + 0.05 + 0.1 + 2.5 + 0)  # to the ground: R_se = 0
U_ROOF = 1 / (0.10 + 0.1 + 5 + 0.04)
SETTINGS: dict[str, str | float] = {"tb": 0.05, "n50": 3, "shielding": "moderate"}


def heat(d: Derived, scope: str | None = None, **given: str | float) -> Output:
    """The Heizlast with the settings above, some replaced."""
    return run(HEATLOAD, d, scope, **{**SETTINGS, **given})


def tables(tmp_path: Path, skip: tuple[str, ...] = ()) -> None:
    for spec, text in (
        (MATERIAL, MAT),
        (SURFACE, SURF),
        (OUTDOOR, OUT),
        (ROOM_TEMP, TEMP),
        (INFILTRATION, INF),
        (HEIGHT, EPS),
        (FACTORS, FAC),
    ):
        if spec.id not in skip:
            install(spec.id, spec, text, tmp_path)


def house(extra: str = R2, text: str = HOUSE) -> Derived:
    d, rep = derive_text(text + extra)
    assert [i for i in rep.issues if i.code.startswith("E-")] == []
    return d


def surfaces(o: dict[str, object], room: str) -> dict[tuple[str, str], dict[str, float]]:
    rooms = o["rooms"]
    assert isinstance(rooms, dict)
    out: dict[tuple[str, str], dict[str, float]] = {}
    for s in rooms[room]["surfaces"]:  # type: ignore[index]
        out[(s["el"], s["beyond"])] = s
    return out


def test_u_values_of_the_build_ups(tmp_path: Path) -> None:
    tables(tmp_path)
    o = run(UVALUE, house())
    assert abs(U_AW - 0.16) < 1e-12 and abs(U_IW - 1.25) < 1e-12
    got = {(b["build"], b["flow"], b["beyond"]): b["u"] for b in o.data["buildups"]}
    assert got == pytest.approx(
        {
            ("AW", "horizontal", "outside"): U_AW,
            ("IW", "horizontal", "inside"): U_IW,
            ("BP + FB", "down", "ground"): U_FLOOR,
            ("DE", "up", "outside"): U_ROOF,
        },
        abs=1e-5,
    )
    assert o.lines[0] == "AW horizontal to outside: U 0.160 W/(m²K), R 6.080"
    assert any("material" in t and "synthetic" in t for t in o.tables)
    # a scope: the build-ups of one type
    assert [b["build"] for b in run(UVALUE, house(), "IW").data["buildups"]] == ["IW"]
    with pytest.raises(ValueError, match="unknown nope"):
        run(UVALUE, house(), "nope")


def test_a_material_without_a_row(tmp_path: Path) -> None:
    install("material", MATERIAL, "material,lambda\ngips,0.25\nmw,0.05\n", tmp_path)
    install("surface", SURFACE, SURF, tmp_path)
    with pytest.raises(ValueError, match="no row for eps, estrich, ks, putz, stb, xps"):
        run(UVALUE, house())


def test_heat_load_of_two_rooms(tmp_path: Path) -> None:
    tables(tmp_path)
    o = heat(house())
    dt = 20 - -10
    s = surfaces(o.data, "r1")
    # the outside walls: 22.2 + 14.1 + 14.1 - 1.44 m² (the window), U + 0.05
    assert s[("w4", "outside")]["area"] == pytest.approx(7.4 * 3)
    walls = (22.2 + 14.1 + 14.1 - 1.44) * (U_AW + 0.05)
    window = 1.44 * (1 + 0.05)
    # to the bedroom at 18 °C: no thermal bridge, f = (20 - 18) / 30
    inner = 22.2 * U_IW * (20 - 18) / dt
    assert s[("w5", "r2")]["f"] == pytest.approx(2 / 30, abs=1e-5)
    # the ground: f = 1.45 * (20 - 10) / 30 * 1
    floor = 34.78 * (U_FLOOR + 0.05) * 1.45 * 10 / dt
    roof = 34.78 * (U_ROOF + 0.05)
    phi_t = (walls + window + inner + floor + roof) * dt
    # air: V = 4.68 x 7.38 x 2.45 (finished floor area, FFL to the slab's underside); one outside
    # wall with a window: e = 0.02; V_inf = 2 * V * 3 * 0.02 < V_min = 0.5 V
    v = 4.68 * 7.38 * 2.45
    r1 = o.data["rooms"]["r1"]  # type: ignore[index]
    assert r1["volume"] == pytest.approx(v, abs=1e-3)
    assert r1["v_inf"] == pytest.approx(2 * v * 3 * 0.02, abs=1e-3)
    phi_v = 0.5 * v * 0.34 * dt
    assert r1["phi_t"] == pytest.approx(phi_t, abs=0.1)
    assert r1["phi_v"] == pytest.approx(phi_v, abs=0.1)
    assert o.lines[1] == f"r1 20 °C: {phi_t + phi_v:.0f} W (T {phi_t:.0f}, V {phi_v:.0f})"

    # the bedroom at 18 °C: the living room is warmer, f < 0; no window, e = 0
    dt2 = 18 - -10
    walls2 = (13.755 + 13.755 + 22.2) * (U_AW + 0.05)
    inner2 = 22.2 * U_IW * (18 - 20) / dt2
    floor2 = 33.929 * (U_FLOOR + 0.05) * 1.45 * (18 - 10) / dt2
    roof2 = 33.929 * (U_ROOF + 0.05)
    r2 = o.data["rooms"]["r2"]  # type: ignore[index]
    assert r2["phi_t"] == pytest.approx((walls2 + inner2 + floor2 + roof2) * dt2, abs=0.1)
    assert r2["v_inf"] == 0
    # the building: without the flows between the two rooms
    b = o.data["building"]
    assert b["phi_t"] == pytest.approx(  # type: ignore[index]
        phi_t - inner * dt + (walls2 + floor2 + roof2) * dt2, abs=0.2
    )
    assert o.lines[0] == "θe -10 °C, θme 10 °C (postcode 12345) · 2 heated rooms"
    assert o.lines[-1].startswith("building: ")
    assert "Erdreich mit dem U-Wert des Bauteils statt U_equiv" in o.report


def test_an_unheated_room_and_the_terrain(tmp_path: Path) -> None:
    tables(tmp_path)
    text = HOUSE.replace("postcode=12345", "postcode=12345 ground=0.5")
    o = heat(house("room r2 EG storage at=E-1,S+1\n", text))
    s = surfaces(o.data, "r1")
    # the storage room at 5 °C is unheated: the thermal bridge counts, f = (20 - 5) / 30
    assert s[("w5", "r2")]["uc"] == pytest.approx(U_IW + 0.05, abs=1e-5)
    assert s[("w5", "r2")]["f"] == pytest.approx(0.5)
    # the lowest 0.5 m of the outside walls is in the ground: the west wall 7.4 x 0.5
    assert s[("w4", "ground")]["area"] == pytest.approx(7.4 * 0.5)
    assert s[("w4", "outside")]["area"] == pytest.approx(7.4 * 2.5)
    assert s[("w4", "ground")]["f"] == pytest.approx(1.45 * 10 / 30, abs=1e-5)
    assert list(o.data["rooms"]) == ["r1"]  # type: ignore[arg-type]
    # in the building's load the wall to the storage room counts
    assert o.data["building"]["phi_t"] == pytest.approx(  # type: ignore[index]
        o.data["rooms"]["r1"]["phi_t"],
        abs=0.1,  # type: ignore[index]
    )


def test_settings_and_tables_are_checked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="heatload needs tb=<value>"):
        run(HEATLOAD, house())
    with pytest.raises(ValueError, match="the table 'outdoor'"):
        heat(house())
    tables(tmp_path, skip=("outdoor", "material"))
    with pytest.raises(ValueError, match="the table 'material'"):
        heat(house(), te=-10, tme=10)
    install("material", MATERIAL, MAT, tmp_path)
    with pytest.raises(ValueError, match="the table 'outdoor'"):
        heat(house())
    # θ_e and θ_m,e given: the table outdoor is not needed
    o = heat(house(), te=-10, tme=10)
    assert o.lines[0].startswith("θe -10 °C, θme 10 °C (Vorgabe des Aufrufs)")
    assert not any(t.startswith("outdoor") for t in o.tables)
    install("outdoor", OUTDOOR, "postcode,te,tme\n99999,-14,8\n", tmp_path)
    with pytest.raises(ValueError, match="no row for the postcode 12345"):
        heat(house())
    with pytest.raises(ValueError, match="no row for the use office"):
        heat(house("room r2 EG office at=E-1,S+1\n"), te=-10, tme=10)
    with pytest.raises(ValueError, match="n50 must be more than 0"):
        heat(house(), n50=0)
    with pytest.raises(ValueError, match="shielding=open is not one of none, moderate, heavy"):
        heat(house(), shielding="open")


def test_a_window_without_a_u_value(tmp_path: Path) -> None:
    tables(tmp_path)
    d = house(text=HOUSE.replace("type FE win uw=1 default", "type FE win default"))
    with pytest.raises(ValueError, match=r"f1 \(Fenster\) has no U-value in its type FE"):
        heat(d)


def test_temperatures_may_be_below_zero(tmp_path: Path) -> None:
    f = tmp_path / "o.csv"
    f.write_text("postcode,te,tme\n12345,-12.5,0\n")
    table, errors = norm_data.add(OUTDOOR, f, "synthetic")
    assert table is not None, errors
    assert table.rows[0]["te"] == -12.5
    f.write_text("material,lambda\nmw,-0.04\n")
    assert norm_data.add(MATERIAL, f, "synthetic")[1] == [
        "line 2: lambda '-0.04' must be more than 0"
    ]
    f.write_text("use,heated,ti,nmin\nattic,no,-2,-1\n")
    assert norm_data.add(ROOM_TEMP, f, "synthetic")[1] == ["line 2: nmin '-1' must be 0 or more"]


def test_the_envelope_of_haus_mueller(prototype: Project) -> None:
    from uea.derive import report

    d, _ = report(prototype.load())
    env = envelope(d)
    assert env.notes == []
    for rid, ss in env.rooms.items():
        parts = {s.part for s in ss}
        assert {"wall", "floor"} <= parts and parts & {"ceiling", "roof"}, rid
        # floor and ceiling cover the room
        floor = sum(s.area for s in ss if s.part == "floor")
        assert floor == pytest.approx(d.arch.rooms[rid].area, rel=1e-6), rid
    # the kitchen: the windows f1 and f2 and the two outside walls, 2.875 m high
    k = env.rooms["r1"]
    assert sorted(s.el for s in k if s.part == "window") == ["f1", "f2"]
    outside = sum(s.area for s in k if s.beyond == "outside")
    shell = d.arch.rooms["r1"].poly.bounds
    assert outside == pytest.approx((shell[2] - shell[0] + shell[3] - shell[1]) * 2.875)


def test_heatload_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    tables(tmp_path)
    ops = re.sub(r"\b(w\d|sl\d|f\d|r\d)\b", r"@\1", HOUSE + R2)
    code, out = sh(
        "apply", "--by", "t", "-m", "box", stdin="".join(f"+ {x}\n" for x in ops.splitlines())
    )
    assert code == 0, out
    code, out = sh("calc", "heatload", "tb=0.05", "n50=3", "shielding=moderate")
    assert code == 0, out
    assert out.splitlines()[0].startswith("norm heatload 0.2.0 · Heizlast raumweise · all")
    assert "report: out/heatload.md" in out
    md = (sh.root / "out" / "heatload.md").read_text()
    assert "# Heizlast: Box" in md and "| Normtabellen |" in md
    code, out = sh("calc", "heatload", "r2", "tb=0.05", "n50=3", "shielding=moderate")
    assert code == 0 and "building" not in out and "r2 18 °C" in out
    code, out = sh("calc", "uvalue")
    assert code == 0 and "AW horizontal to outside: U 0.160" in out

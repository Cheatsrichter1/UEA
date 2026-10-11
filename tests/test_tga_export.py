"""The heating and plumbing sheets, tables and calculation reports (decision 0036), on the box
houses of test_heat and test_plumb."""

import re
from pathlib import Path

import pytest

from tests.conftest import Shell, derive_text
from tests.test_heat import HEAT
from tests.test_plumb import HOUSE as HOUSE2
from tests.test_plumb import PLUMB, plumb, tables
from uea.export.drawing import Drawing, Line, Text
from uea.export.report import rerun, stale
from uea.export.schema import sheet_schema
from uea.export.tables_tga import tga_tables
from uea.export.tga import S_COLD, S_HOT, sheet_tga

FIN = 9.38 * 7.38


def texts(dw: Drawing) -> list[str]:
    return [it.text for it in dw.items if isinstance(it, Text)]


def lines(dw: Drawing, layer: str) -> list[Line]:
    return [it for it in dw.items if isinstance(it, Line) and it.layer == layer]


def heated() -> tuple[str, str]:
    from tests.test_elec import HOUSE

    return HOUSE, HEAT


def test_heating_plan() -> None:
    house, heat = heated()
    d, _ = derive_text(house + heat)
    dw = sheet_tga(d, "EG", "heat")
    assert dw is not None and dw.sheet is not None
    found = texts(dw)
    # the underfloor heating of r1: 69.2 m², 5 loops, 60 W/m²
    assert f"uh1 · 69,2 m² · 5 Kreise · {60 * FIN:.0f} W" in found
    assert "g1 8,0 kW" in found and "Heizung Erdgeschoss" in found
    assert {it.layer for it in dw.items} >= {"H-FUSSBODENHEIZUNG", "H-VERTEILER", "H-ERZEUGER"}
    assert sheet_tga(d, "OG", "heat") is None


def test_plumbing_plans() -> None:
    d, _ = plumb()
    dw = sheet_tga(d, "EG", "plumb")
    assert dw is not None
    # cold on the EG: wz1 to t1 along x, wz1 to the riser along y, t1 to the sink along x and y
    assert len(lines(dw, S_COLD)) == 4
    assert len(lines(dw, S_HOT)) == 4  # t1 to the riser and t1 to the sink, along x and y
    assert {"sa1", "wz1", "sr1", "fl1", "kn1", "t1"} <= set(texts(dw))
    og = sheet_tga(d, "OG", "plumb")
    assert og is not None
    # the riser and the stack pass through the OG and are drawn there too
    assert {"sa2", "sa3", "sr1", "fl1"} <= set(texts(og))
    assert "kn1" not in texts(og)


def test_schema() -> None:
    house, heat = heated()
    d, _ = derive_text(house + heat)
    dw = sheet_schema(d)
    assert dw is not None and dw.sheet is not None and dw.sheet.scale == 1
    found = texts(dw)
    assert any(t.startswith("EG: hv1 Heizkreisverteiler HKV") for t in found)
    # one column for each of the five loops
    assert [t for t in found if t.startswith("Kreis ")] == [f"Kreis {k}/5" for k in range(1, 6)]
    assert "Trinkwasser-Entnahmestellen" not in found
    # with plumbing: the fixtures that take water, cold from the meter
    d, _ = plumb()
    dw = sheet_schema(d)
    assert dw is not None
    found = texts(dw)
    assert {"sa1 Spüle", "sa2 Dusche", "sa3 WC", "wz1 Hausanschluss"} <= set(found)


def test_tables() -> None:
    d, _ = plumb("ufh uh1 r1 hv1\nman hv1 w2 t1 y=S+1\ntype FBH ufh spacing=0.15 q=60 max=100 "
                 "default\ntype HKV man outlets=10 default\n")  # fmt: skip
    got = {t.name: t for t in tga_tables(d)}
    assert list(got) == [
        "Heizflächen",
        "Heizkreisverteiler",
        "Sanitärobjekte",
        "Rohrleitungen",
        "Rohrmengen",
    ]
    uh1 = got["Heizflächen"].rows[0]
    assert uh1[:6] == ["uh1", "EG", "r1", "Hauswirtschaftsraum", "Fußbodenheizung", "FBH"]
    hv1 = got["Heizkreisverteiler"].rows[0]
    assert hv1[5:8] == [10, uh1[7], 10 - uh1[7]]  # type: ignore[operator]
    sa2 = next(r for r in got["Sanitärobjekte"].rows if r[0] == "sa2")
    assert sa2[4:6] == ["Dusche", "kalt + warm"]
    assert sa2[8] == pytest.approx(6.5 + 2.9 + 10.1)
    assert sa2[11:] == ["fl1", pytest.approx(3.0 + 2.9 + 7.0)]
    q = {r[0]: r[2] for r in got["Rohrmengen"].rows}
    assert q["Trinkwasser kalt"] == pytest.approx(2.5 + 6.5 + 8.7 + 2.9 + 2.7 + 10.1)
    assert q["Schmutzwasser"] == pytest.approx(3.0 + 2.9 + 12.7 + 2.7 + 7.0)
    # one storey
    og = {t.name: t for t in tga_tables(d, "OG")}
    assert [r[0] for r in og["Sanitärobjekte"].rows] == ["sa2", "sa3"]


def test_report_records() -> None:
    record = {
        "calculator": "heatload",
        "scope": "EG",
        "inputs": {"settings": {"tb": 0.05, "te": None}},
        "state": {"batch": 3, "files": {"a.uea": "x"}},
    }
    assert rerun(record) == "uea calc heatload EG tb=0.05"
    assert stale(record, {"a.uea": "y"}) and not stale(record, {"a.uea": "x"})


def test_on_the_command_line(sh: Shell, tmp_path: Path) -> None:
    tables(tmp_path)
    ops = re.sub(r"\b((?:w|sl|r|t|wz|sr|fl|kn|sa)\d)\b", r"@\1", HOUSE2 + PLUMB)
    code, out = sh(
        "apply", "--by", "t", "-m", "plumb", stdin="".join(f"+ {x}\n" for x in ops.splitlines())
    )
    assert code == 0, out
    code, out = sh("export", "svg", "plumb")
    assert code == 0 and "plumb-EG.svg" in out and "plumb-OG.svg" in out, out
    code, out = sh("export", "dxf", "heat:schema")
    assert code == 0 and "heat-schema.dxf" in out and "o. M." in out, out
    code, out = sh("export", "png", "heat:OG")
    assert code == 1 and "nothing of heat on OG" in out
    # a calculation report: written, refused as a picture, refused once the model changes
    code, out = sh("calc", "water")
    assert code == 0, out
    code, out = sh("export", "pdf", "water")
    assert code == 0 and re.search(r"water\.pdf A4 \d+ pages?", out), out
    assert (sh.root / "out" / "water.pdf").read_bytes().startswith(b"%PDF")
    code, out = sh("export", "png", "water")
    assert code == 1 and "export it as pdf" in out
    code, out = sh("apply", "--by", "t", "-m", "move", stdin="~ sa1 y=S+3\n")
    assert code == 0, out
    code, out = sh("export", "pdf", "water")
    assert code == 1 and "run uea calc water building=residential again" in out
    code, out = sh("export", "xlsx")
    assert code == 0 and "Rohrleitungen(" in out and "Sanitärobjekte(3)" in out

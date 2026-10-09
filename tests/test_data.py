"""The office's norm tables: checking a CSV file, storing it, and what a calculator is told when
a table is missing (decisions 0008 and 0028). All values are our own, not a standard's."""

from pathlib import Path

import pytest

from tests.conftest import Shell
from uea.calc import data
from uea.packs.elec.cable import AMPACITY, GROUPING
from uea.packs.elec.vdrop import CONDUCTOR

AMP = """\
method,insulation,loaded,mm2,amps
B2,PVC,2,1.5,12
B2,PVC,2,2.5,16
c,pvc,3,2.5,14
"""


def test_a_csv_file_is_read_by_header() -> None:
    rows, errors = data.parse_csv(AMPACITY, AMP)
    assert errors == []
    assert rows[0] == {"method": "B2", "insulation": "PVC", "loaded": 2.0, "mm2": 1.5, "amps": 12.0}
    # the choice is stored as the spec spells it
    assert rows[2]["insulation"] == "PVC"
    # columns in any order
    reordered = "amps;mm2;loaded;insulation;method\n12;1,5;2;PVC;B2\n"
    rows, errors = data.parse_csv(AMPACITY, reordered)
    assert errors == [] and rows[0]["mm2"] == 1.5 and rows[0]["method"] == "B2"


def test_semicolons_and_decimal_commas_a_bom_and_comments() -> None:
    text = "﻿# from the office copy\nmethod;insulation;loaded;mm2;amps\nB2;PVC;2;1,5;16,5\n\n"
    rows, errors = data.parse_csv(AMPACITY, text)
    assert errors == [] and rows[0]["amps"] == 16.5


def test_errors_name_the_line_of_the_file() -> None:
    text = "# office copy\n\nmethod,insulation,loaded,mm2,amps\n# row\nB2,PVC,2,x,12\n"
    _, errors = data.parse_csv(AMPACITY, text)
    assert errors == ["line 5: mm2 'x' is not a number"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "the file is empty"),
        ("method,insulation,loaded,mm2\nB2,PVC,2,1.5\n", "the header must name the columns"),
        ("method,insulation,loaded,mm2,amps\n", "no rows below the header"),
        ("method,insulation,loaded,mm2,amps\nB2,PVC,2,x,12\n", "line 2: mm2 'x' is not a number"),
        ("method,insulation,loaded,mm2,amps\nB2,PVC,2,1.5,0\n", "line 2: amps '0' must be more"),
        ("method,insulation,loaded,mm2,amps\nB2,PE,2,1.5,12\n", "insulation 'PE' is not one of"),
        ("method,insulation,loaded,mm2,amps\n,PVC,2,1.5,12\n", "line 2: method is empty"),
        ("method,insulation,loaded,mm2,amps\nB2,PVC,2,1.5\n", "line 2: 4 values, the header has 5"),
        (AMP + "B2,pvc,2,1.5,13\n", "line 5: the same method/insulation/loaded/mm2 as line 2"),
    ],
)
def test_what_is_wrong_with_a_file(text: str, message: str) -> None:
    rows, errors = data.parse_csv(AMPACITY, text)
    assert any(message in e for e in errors), errors
    assert rows == [] or errors  # nothing counts as read when there are errors


def test_add_stores_the_table_with_edition_and_hash(tmp_path: Path) -> None:
    f = tmp_path / "amp.csv"
    f.write_text(AMP)
    assert data.load(AMPACITY) is None
    table, errors = data.add(AMPACITY, f, "2099 test", "own test values")
    assert errors == [] and table is not None
    again = data.load(AMPACITY)
    assert again is not None
    assert (again.edition, again.source, len(again.rows)) == ("2099 test", "own test values", 3)
    assert again.sha == table.sha and len(again.sha) == 64
    assert again.cite().startswith("ampacity (DIN VDE 0298-4), Ausgabe 2099 test, own test values")
    # text is found without regard to case, numbers exactly
    assert again.find(method="b2", insulation="pvc", loaded=2, mm2=1.5) is not None
    assert again.find(method="B2", insulation="PVC", loaded=3, mm2=1.5) is None
    # a second add replaces the first
    f.write_text(AMP.replace("12", "11"))
    data.add(AMPACITY, f, "2099 second")
    after = data.load(AMPACITY)
    assert after is not None and after.edition == "2099 second" and after.rows[0]["amps"] == 11


def test_a_bad_file_installs_nothing(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    f.write_text("method,insulation,loaded,mm2,amps\nB2,PVC,2,x,12\n")
    table, errors = data.add(AMPACITY, f, "e")
    assert table is None and errors and data.load(AMPACITY) is None
    table, errors = data.add(AMPACITY, tmp_path / "nothing.csv", "e")
    assert table is None and errors[0].startswith("cannot read")


def test_many_errors_are_cut_short(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    f.write_text("method,insulation,loaded,mm2,amps\n" + "B2,PVC,2,x,12\n" * 15)
    _, errors = data.add(AMPACITY, f, "e")
    assert len(errors) == data.MAX_ERRORS + 1 and errors[-1] == "... and 5 more"


def test_a_missing_table_says_what_to_do() -> None:
    with pytest.raises(data.MissingTable) as e:
        data.need(GROUPING)
    msg = str(e.value)
    assert "group-factor" in msg and "uea data add group-factor <file.csv> --edition" in msg
    assert "Columns: arrangement,circuits,factor" in msg


def test_the_folder_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(data.ENV, str(tmp_path / "x"))
    assert data.root() == tmp_path / "x"
    monkeypatch.delenv(data.ENV)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert data.root() == tmp_path / "xdg" / "uea"


# ---------- the command ----------


def test_uea_data_lists_shows_adds_and_removes(sh: Shell, tmp_path: Path) -> None:
    code, out = sh("data")
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("ampacity  missing  Current-carrying capacity Iz (DIN VDE 0298-4)")
    assert [x.split()[0] for x in lines[:5]] == [
        "ampacity",
        "temp-factor",
        "group-factor",
        "conductor",
        "folder:",
    ]
    code, out = sh("data", "show", "conductor")
    assert code == 0 and "material  text one of Cu, Al" in out and "not installed" in out
    assert "one row per material" in out
    f = tmp_path / "cond.csv"
    f.write_text("material,rho,lambda\nCu,0.02,0.1\n")
    code, out = sh("data", "add", "conductor", str(f), "--edition", "test")
    assert code == 0 and out.startswith("ok conductor: 1 rows, edition test (sha256 ")
    assert "conductor  edition test, 1 rows" in sh("data")[1]
    code, out = sh("data", "show", "conductor")
    assert "installed: edition test, 1 rows" in out and "material=Cu rho=0.02 lambda=0.1" in out
    code, out = sh("data", "remove", "conductor")
    assert out.strip() == "ok conductor: removed" and data.load(CONDUCTOR) is None
    assert sh("data", "remove", "conductor")[1].strip() == "conductor is not installed"


def test_uea_data_errors(sh: Shell, tmp_path: Path) -> None:
    assert sh("data", "show", "nonsense")[0] == 2
    assert sh("data", "frob")[0] == 2
    f = tmp_path / "c.csv"
    f.write_text("material,rho,lambda\nCu,x,0.1\n")
    code, out = sh("data", "add", "conductor", str(f))
    assert code == 2 and "needs a file and the edition" in out
    code, out = sh("data", "add", "conductor", str(f), "--edition", "e")
    assert code == 1
    assert out.splitlines()[:2] == [
        f"conductor: {f} is not valid. Nothing was installed.",
        "line 2: rho 'x' is not a number",
    ]

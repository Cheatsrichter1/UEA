"""The hand-written Haus Müller prototype (docs/prototype/haus-mueller) through real UEA code.

The expected room areas are the ones computed by hand for the prototype's README.
"""

import pytest

from tests.conftest import PROTOTYPE
from uea.derive import report
from uea.packs.arch.wofl import wofl
from uea.project import Project

FERTIG = {
    "r1": 15.66,
    "r2": 27.93,
    "r3": 6.65,
    "r4": 4.04,
    "r5": 17.45,
    "r6": 17.83,
    "r7": 12.79,
    "r8": 11.67,
    "r9": 8.14,
    "r10": 20.43,
}


def test_room_areas(prototype: Project) -> None:
    d, _ = report(prototype.load())
    got = {k: round(r.area_fin, 2) for k, r in d.arch.rooms.items() if k in FERTIG}
    assert got == FERTIG
    eg = sum(r.area_fin for r in d.arch.rooms.values() if r.level == "EG")
    og = sum(r.area_fin for r in d.arch.rooms.values() if r.level == "OG")
    assert round(eg, 2) == 71.72
    assert round(og, 2) == 70.85


def test_clean_model(prototype: Project) -> None:
    _, rep = report(prototype.load())
    # the elec pack is not built yet, so the Elektro waiver matches nothing
    assert [(i.code, i.el) for i in rep.issues] == [("W-ISSUE-001", "wv1")]
    assert [r.id for r in rep.requests] == ["q3", "q4", "q6"]


def test_roof_heights(prototype: Project) -> None:
    d, _ = report(prototype.load())
    rf = d.arch.roofs["rf1"]
    # README: First +8,10, Traufe +6,12
    assert round(rf.ridge_z, 2) == 8.10
    assert round(rf.eaves_z, 2) == 6.12


def test_stair(prototype: Project) -> None:
    d, _ = report(prototype.load())
    s = d.arch.stairs["st1"]
    # README: 16 risers of 18.0 cm, tread 26 cm, 2h+a = 61.9 cm
    assert round(s.riser, 3) == 0.180
    assert round(s.step, 3) == 0.619


def test_wohnflaeche(prototype: Project) -> None:
    d, _ = report(prototype.load())
    # EG 71.7216 minus stair 3.9 x 0.985; OG 70.8545 minus the same stair hole
    deduct = 3.9 * 0.985
    o = wofl(d, None)
    assert o.data["levels"]["EG"] == pytest.approx(71.7216 - deduct, abs=1e-4)
    assert o.data["levels"]["OG"] == pytest.approx(70.8545 - deduct, abs=1e-4)
    assert o.data["total"] == pytest.approx(142.5761 - 2 * deduct, abs=1e-4)


def test_files_parse_and_stay_canonical(prototype: Project) -> None:
    m = prototype.load()
    assert len(m) == 87
    for pack in ("project", "arch", "issues"):
        again = prototype.parse({f"{pack}.uea": m.pack_text(pack)})
        assert again.pack_text(pack) == m.pack_text(pack)


def test_prototype_files_unchanged() -> None:
    """The fixture copies; the prototype folder itself never gets a log or out/."""
    assert not (PROTOTYPE / "log.jsonl").exists()

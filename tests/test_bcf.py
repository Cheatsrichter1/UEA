"""`uea export bcf`: requests to a discipline as BCF 2.1 topics (decision 0032)."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import math
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tests.conftest import BOX, Shell
from uea.export.guid import compress, ifc_guid


def box(sh: Shell) -> None:
    """The box of conftest (its walls become w1 to w4 in order), and two requests of the
    electrical planner to the architect."""
    ops = "\n".join("+ " + re.sub(r"\bw(\d)\b", r"@w\1", x) for x in BOX.splitlines())
    code, out = sh("apply", "--by", "t", "-m", "box", stdin=ops)
    assert code == 0, out
    asks = '+ req _ elec w1 "Schlitz 10x5 cm"\n+ req _ elec w2,w3 "Durchbruch 15 cm"\n'
    code, out = sh("apply", "--by", "elektro", "-m", "Anfragen", stdin=asks)
    assert code == 0, out


def read(path: Path) -> dict[str, ET.Element]:
    with zipfile.ZipFile(path) as z:
        return {n: ET.fromstring(z.read(n)) for n in z.namelist()}


def topic_of(files: dict[str, ET.Element], title: str) -> tuple[ET.Element, ET.Element]:
    """The markup and the viewpoint of the topic with this title."""
    for name, root in files.items():
        if name.endswith("markup.bcf") and root.findtext("Topic/Title") == title:
            return root, files[name.replace("markup.bcf", "viewpoint.bcfv")]
    raise AssertionError(title)


def test_compress_is_ifcs_base64() -> None:
    # the all-zero and the all-one UUID, worked out by hand: 22 characters of 6 bits, the first
    # carrying 2; IFC's alphabet runs 0-9, A-Z, a-z, _, $
    assert compress("0" * 32) == "0" * 22
    assert compress("f" * 32) == "3" + "$" * 21
    pytest.importorskip("ifcopenshell")
    import ifcopenshell.guid

    for i in range(50):
        h = uuid.uuid5(uuid.NAMESPACE_DNS, str(i)).hex
        assert compress(h) == ifcopenshell.guid.compress(h)


def test_requests_to_the_architect_as_topics(sh: Shell) -> None:
    box(sh)
    code, out = sh("apply", "--by", "architekt", "-m", "nein", stdin='~ q2 rejected="tragend"\n')
    assert code == 0, out
    code, out = sh("export", "bcf")
    assert code == 0, out
    assert out.strip() == "p/out/box-arch.bcf BCF 2.1: 2 topics, open: q1"
    files = read(sh.root / "out" / "box-arch.bcf")
    assert files["bcf.version"].get("VersionId") == "2.1"
    assert files["project.bcfp"].findtext("Project/Name") == "Box"
    markup, view = topic_of(files, "Schlitz 10x5 cm")
    topic = markup.find("Topic")
    assert topic is not None
    assert (topic.get("TopicType"), topic.get("TopicStatus")) == ("Request", "Open")
    assert topic.findtext("CreationAuthor") == "elektro"
    assert topic.findtext("Labels") == "Elektroplanung"
    assert topic.findtext("Description") == (
        "Anfrage q1 der Elektroplanung an die Architektur. Betrifft: w1 (Wand). Aus UEA (box,"
        " Stand 3)."
    )
    # the element is UEA's own (nothing was imported): the GlobalId of UEA's IFC export
    assert [c.get("IfcGuid") for c in view.iter("Component")] == [ifc_guid("box", "w1")]
    # the topic's Guid stays the same in every export: a program updates what it holds
    assert topic.get("Guid") == str(
        uuid.uuid5(uuid.UUID("0b5c3f1e-7d2a-5e4f-9c8b-1a2d3e4f5a6b"), "box/q1")
    )
    # rejected: closed, with the reason as a comment by who rejected it
    markup, view = topic_of(files, "Durchbruch 15 cm")
    assert markup.find("Topic").get("TopicStatus") == "Closed"  # type: ignore[union-attr]
    assert markup.findtext("Topic/ModifiedAuthor") == "architekt"
    assert (markup.findtext("Comment/Author"), markup.findtext("Comment/Comment")) == (
        "architekt",
        "Abgelehnt: tragend",
    )
    assert len(list(view.iter("Component"))) == 2


def test_a_done_request_and_no_requests(sh: Shell) -> None:
    code, out = sh("export", "bcf")
    assert (code, out.strip()) == (1, "no requests to arch")
    box(sh)
    code, out = sh("apply", "--by", "architekt", "-m", "ja", stdin="~ q1 done\n")
    assert code == 0, out
    sh("export", "bcf")
    markup, _ = topic_of(read(sh.root / "out" / "box-arch.bcf"), "Schlitz 10x5 cm")
    assert markup.findtext("Comment/Comment") == "Erledigt (Stand 3)."
    assert sh("export", "bcf", "light")[1].strip() == "no requests to light"
    assert sh("export", "bcf", "garden")[0] == 1


def test_the_camera_and_the_ids_of_an_imported_file(sh: Shell, tmp_path: Path) -> None:
    """The house of the import tests in survey coordinates: its site 485 km east and 5520 km north,
    112.5 m high, turned by 30°. The topic must point at the wall in the architect's file, where
    the file has it."""
    pytest.importorskip("ifcopenshell")
    from tests.ifc_make import write
    from tests.test_import import do_import
    from tests.test_import_files import far

    guids = write(far(), tmp_path / "far.ifc")
    do_import(sh, far(), tmp_path)
    code, out = sh("apply", "--by", "elektro", "-m", "q", stdin='+ req _ elec w1 "Schlitz"\n')
    assert code == 0, out
    sh("export", "bcf")
    _, view = topic_of(read(next((sh.root / "out").glob("*-arch.bcf"))), "Schlitz")
    assert [c.get("IfcGuid") for c in view.iter("Component")] == [guids["EG-south"]]

    # the camera looks at the middle of the south wall, 1.25 m above the FFL: in the file that
    # is 3 m along the wall's axis from the site's origin, turned by 30°, at 112.5 + 1.25
    def xyz(tag: str) -> tuple[float, ...]:
        e = view.find(f"PerspectiveCamera/{tag}")
        assert e is not None
        return tuple(float(e.findtext(c) or "nan") for c in "XYZ")

    eye, look = xyz("CameraViewPoint"), xyz("CameraDirection")
    reach = math.sqrt(6**2 + 6**2 + 4**2)
    seen = tuple(eye[i] + look[i] * reach for i in range(3))
    want = (
        485000 + 3 * math.cos(math.radians(30)),
        5520000 + 3 * math.sin(math.radians(30)),
        113.75,
    )
    assert seen == pytest.approx(want, abs=0.002)

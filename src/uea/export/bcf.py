"""Requests to a discipline as BCF 2.1, for the people who answer them outside UEA (decision 0032).

An architect whose IFC was imported answers in their own program; Archicad, Revit, BIMcollab and
Solibri read BCF. Each request is a topic: its text the title, its targets selected in a viewpoint
by their GlobalIds (in the architect's file for what was imported, in UEA's own export for the
rest), a camera looking at them in the coordinates of that file. A topic keeps its Guid across
exports, so a newer export updates the topics a program already holds; a request that is done or
rejected is a closed topic with a comment that says so. The texts are German, for the people who
read them; the request's own text stays as it was written.
"""

import math
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from uea.derive import Derived, Report
from uea.export.guid import ifc_guid
from uea.packs.issues import Req
from uea.project import Entry, History

NS = uuid.UUID("0b5c3f1e-7d2a-5e4f-9c8b-1a2d3e4f5a6b")
WHO = {
    "arch": "Architektur",
    "struct": "Tragwerksplanung",
    "light": "Lichtplanung",
    "elec": "Elektroplanung",
    "heat": "Heizungsplanung",
    "plumb": "Sanitärplanung",
    "vent": "Lüftungsplanung",
}
WORD = {
    "wall": "Wand",
    "door": "Tür",
    "win": "Fenster",
    "niche": "Nische",
    "slab": "Decke",
    "void": "Deckenöffnung",
    "roof": "Dach",
    "stair": "Treppe",
    "room": "Raum",
    "sep": "Raumtrennung",
    "level": "Geschoss",
    "grid": "Achse",
}
GLOBAL_ID = re.compile(r"(?:void:)?([0-9A-Za-z_$]{22})(?::glass#\d+)?")
"""The import keys that are an element's GlobalId in the architect's file."""
EYE = (-6.0, -6.0, 4.0)
"""Where the camera stands, from the middle of the targets: south-west of them and above."""

Vec3 = tuple[float, float, float]


@dataclass
class Topic:
    req: Req
    guid: str
    created: Entry | None
    closed: Entry | None
    components: list[str]
    camera: tuple[Vec3, Vec3, Vec3] | None
    """Where it stands, where it looks and which way is up, in the file's coordinates."""
    about: str
    """The targets, for the description: `w7 (Wand), r3 (Raum "Küche")`."""


def file_guids(history: History) -> dict[str, str]:
    """Element id to its GlobalId in the IFC file it was imported from."""
    out: dict[str, str] = {}
    for key, (ident, _) in history.ifc_state().items():
        m = GLOBAL_ID.fullmatch(key)
        if m is not None:
            out[ident] = m.group(1)
    return out


def spot(d: Derived, key: str) -> Vec3 | None:
    """A point in the middle of an element, in the model's coordinates; none if it has no place
    in the architecture."""
    a = d.arch
    if key in a.walls:
        w = a.walls[key]
        x, y = w.plan_point((w.s0 + w.s1) / 2, w.mid)
        return (x, y, a.levels[w.level].z + 1.25)
    if key in a.openings:
        o = a.openings[key]
        w = a.walls[o.host]
        x, y = w.plan_point(o.mid, w.mid)
        return (x, y, a.levels[o.level].z + (o.sill + o.top) / 2)
    if key in a.rooms:
        r = a.rooms[key]
        p = r.poly.representative_point()
        return (p.x, p.y, a.levels[r.level].z + 1.25)
    if key in a.slabs:
        s = a.slabs[key]
        p = s.outline.representative_point()
        return (p.x, p.y, s.top)
    if key in a.voids:
        v = a.voids[key]
        p = v.poly.representative_point()
        return (p.x, p.y, a.slabs[v.slab].top if v.slab in a.slabs else 0.0)
    if key in a.stairs:
        st = a.stairs[key]
        p = st.poly.representative_point()
        return (p.x, p.y, a.levels[st.level].z + 1.25)
    if key in a.roofs:
        rf = a.roofs[key]
        return ((rf.x0 + rf.x1) / 2, (rf.y0 + rf.y1) / 2, rf.eaves_z)
    return None


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _camera(spots: list[Vec3], back: Any) -> tuple[Vec3, Vec3, Vec3]:
    """A camera south-west of the targets and above them, looking at their middle. `back` takes a
    point and a direction of the model to the file: (x, y, z, is_point) -> (x, y, z)."""
    c = tuple(sum(p[i] for p in spots) / len(spots) for i in range(3))
    eye = (c[0] + EYE[0], c[1] + EYE[1], c[2] + EYE[2])
    look = _unit((c[0] - eye[0], c[1] - eye[1], c[2] - eye[2]))
    k = look[2]
    up = _unit((-k * look[0], -k * look[1], 1.0 - k * look[2]))
    return back(*eye, True), back(*look, False), back(*up, False)


def topics(d: Derived, rep: Report, history: History, owner: str) -> list[Topic]:
    """The requests whose targets belong to `owner`, open or not, as topics."""
    project = d.model.project_name() or "project"
    guids = file_guids(history)
    last = history.ifc_last() or {}
    turn, dx, dy = (float(x) for x in last.get("frame", (0.0, 0.0, 0.0)))
    ground = float(last.get("ground", 0.0))
    r = math.radians(turn)
    cos, sin = math.cos(r), math.sin(r)

    def back(x: float, y: float, z: float, point: bool) -> Vec3:
        """From the model to the file: turned back, then moved back (see `Frame`)."""
        fx, fy = cos * x + sin * y, -sin * x + cos * y
        if point:
            return (fx - dx, fy - dy, z + ground)
        return (fx, fy, z)

    entries = history.entries()
    out: list[Topic] = []
    reqs = [e for e in d.model.of_kind("req") if isinstance(e, Req)]
    for q in reqs:
        if rep.request_owner(q) != owner:
            continue
        made = next((e for e in entries if q.id in e.ids), None)
        touched = [e for e in entries if q.id in e.touched() and e is not made]
        closed = touched[-1] if not q.open and touched else None
        components: list[str] = []
        about: list[str] = []
        spots: list[Vec3] = []
        for t in q.targets.refs():
            el = d.model.get(t)
            kind = el.kind if el is not None else ""
            word = WORD.get(kind, kind)
            label = f' "{el.label}"' if el is not None and el.label else ""
            about.append(f"{t} ({word}{label})" if word else t)
            components.append(
                guids.get(t) or ifc_guid(project, f"{t}/opening" if kind == "niche" else t)
            )
            p = spot(d, t)
            if p is not None:
                spots.append(p)
        out.append(
            Topic(
                q,
                str(uuid.uuid5(NS, f"{project}/{q.id}")),
                made,
                closed,
                components,
                _camera(spots, back) if spots else None,
                ", ".join(about),
            )
        )
    return out


def _el(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    e = ET.SubElement(parent, tag, attrs)
    if text is not None:
        e.text = text
    return e


def _xyz(parent: ET.Element, tag: str, v: Vec3) -> None:
    e = _el(parent, tag)
    for name, value in zip("XYZ", v, strict=True):
        _el(e, name, f"{value:.4f}")


def _bytes(root: ET.Element) -> bytes:
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def markup(t: Topic, owner: str, project: str, stand: int) -> bytes:
    q = t.req
    status = "Open" if q.open else "Closed"
    root = ET.Element("Markup")
    topic = _el(root, "Topic", Guid=t.guid, TopicType="Request", TopicStatus=status)
    _el(topic, "Title", q.label or q.id)
    _el(topic, "Labels", WHO.get(q.disc, q.disc))
    made = t.created
    _el(topic, "CreationDate", made.time if made else "1970-01-01T00:00:00Z")
    _el(topic, "CreationAuthor", made.by if made else "uea")
    if t.closed is not None:
        _el(topic, "ModifiedDate", t.closed.time)
        _el(topic, "ModifiedAuthor", t.closed.by)
    who, to = WHO.get(q.disc, q.disc), WHO.get(owner, owner)
    _el(
        topic,
        "Description",
        f"Anfrage {q.id} der {who} an die {to}. Betrifft: {t.about}. Aus UEA ({project},"
        f" Stand {stand}).",
    )
    view = str(uuid.uuid5(NS, f"{project}/{q.id}/view"))
    if t.closed is not None:
        comment = _el(root, "Comment", Guid=str(uuid.uuid5(NS, f"{project}/{q.id}/closed")))
        _el(comment, "Date", t.closed.time)
        _el(comment, "Author", t.closed.by)
        text = f"Abgelehnt: {q.rejected}" if q.rejected else f"Erledigt (Stand {q.done})."
        _el(comment, "Comment", text)
        _el(comment, "Viewpoint", Guid=view)
    views = _el(root, "Viewpoints", Guid=view)
    _el(views, "Viewpoint", "viewpoint.bcfv")
    return _bytes(root)


def viewpoint(t: Topic, project: str) -> bytes:
    root = ET.Element("VisualizationInfo", Guid=str(uuid.uuid5(NS, f"{project}/{t.req.id}/view")))
    comps = _el(root, "Components")
    sel = _el(comps, "Selection")
    for g in t.components:
        _el(sel, "Component", IfcGuid=g)
    _el(comps, "Visibility", DefaultVisibility="true")
    if t.camera is not None:
        cam = _el(root, "PerspectiveCamera")
        _xyz(cam, "CameraViewPoint", t.camera[0])
        _xyz(cam, "CameraDirection", t.camera[1])
        _xyz(cam, "CameraUpVector", t.camera[2])
        _el(cam, "FieldOfView", "60")
    return _bytes(root)


def write_bcf(
    found: list[Topic], path: Path, owner: str, project: str, title: str, stand: int
) -> None:
    version = ET.Element("Version", VersionId="2.1")
    _el(version, "DetailedVersion", "2.1")
    ext = ET.Element("ProjectExtension")
    _el(_el(ext, "Project", ProjectId=str(uuid.uuid5(NS, project))), "Name", title)
    _el(ext, "ExtensionSchema")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bcf.version", _bytes(version))
        z.writestr("project.bcfp", _bytes(ext))
        for t in found:
            z.writestr(f"{t.guid}/markup.bcf", markup(t, owner, project, stand))
            z.writestr(f"{t.guid}/viewpoint.bcfv", viewpoint(t, project))

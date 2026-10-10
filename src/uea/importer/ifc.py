"""Reading an architect's IFC into plain data (decision 0029).

Only what UEA can map is read: storeys, walls with their layers, doors and windows with the
opening they fill, slabs and spaces. Geometry comes from IfcOpenShell's tessellation, so it does not
matter how the exporting program wrote a body (extrusion, clipping, mesh): a wall is the strip its
footprint draws. Lengths are metres, heights are absolute (the world z of the file).
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import hashlib
import math
import multiprocessing
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
import ifcopenshell.util.unit as uu
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

Vec = tuple[float, float]
Entity = Any

STATUS = {"NEW": "new", "EXISTING": "existing", "DEMOLISH": "demolish", "TEMPORARY": "temp"}
STRUCTURE = ("IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcOpeningElement")
COMPONENT_OF = ("IfcRoof", "IfcStair", "IfcRamp", "IfcCurtainWall", "IfcRailing")
"""Parts of these are counted with the whole, not one by one."""
NOTCH = 0.03
"""A footprint may differ this much (relative to its area) from a plain strip."""


class NotImportable(Exception):
    """The file cannot be imported at all."""


@dataclass(frozen=True)
class Layer:
    material: str
    t: float


@dataclass
class Storey:
    guid: str
    name: str
    z: float


@dataclass
class Wall:
    guid: str
    name: str
    storey: str | None
    a: Vec
    b: Vec
    """The ends of the centre line of the whole wall, finishes included."""
    t: float
    z0: float
    z1: float
    sloped: bool
    layers: tuple[Layer, ...]
    first: Vec | None
    """World direction from the wall's centre to the face of its first layer, if the file says."""
    material: str | None
    type_guid: str | None
    type_name: str | None
    lb: bool
    status: str
    note: str | None = None


@dataclass
class Opening:
    guid: str
    kind: Literal["door", "win"]
    wall: str
    fp: Polygon
    z0: float
    z1: float
    type_guid: str | None
    type_name: str | None
    u: float | None
    status: str


@dataclass
class Slab:
    guid: str
    storey: str
    layers: tuple[Layer, ...]
    """Top to bottom."""
    material: str | None
    z0: float
    z1: float
    area: float
    type_name: str | None
    status: str


@dataclass
class Space:
    guid: str
    storey: str | None
    name: str
    long_name: str
    hint: str
    at: Vec
    area: float
    z0: float
    fp: Polygon


@dataclass
class Source:
    file: str
    sha: str
    schema: str
    app: str
    title: str
    storeys: list[Storey] = field(default_factory=list[Storey])
    walls: list[Wall] = field(default_factory=list[Wall])
    openings: list[Opening] = field(default_factory=list[Opening])
    slabs: list[Slab] = field(default_factory=list[Slab])
    spaces: list[Space] = field(default_factory=list[Space])
    skipped: Counter[str] = field(default_factory=Counter[str])
    notes: list[str] = field(default_factory=list[str])


@dataclass
class Shape:
    verts: Any
    faces: Any

    def z(self) -> tuple[float, float]:
        return float(self.verts[:, 2].min()), float(self.verts[:, 2].max())


# ---------- geometry ----------


def shapes(f: Entity, products: Iterable[Entity]) -> dict[int, Shape]:
    """The tessellated bodies in world coordinates, without the openings cut out of them."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("disable-opening-subtractions", True)
    include = list(products)
    out: dict[int, Shape] = {}
    if not include:
        return out
    it = ifcopenshell.geom.iterator(settings, f, multiprocessing.cpu_count(), include=include)
    if it.initialize():
        while True:
            sh = it.get()
            g = sh.geometry
            if len(g.verts) and len(g.faces):
                out[sh.id] = Shape(
                    np.array(g.verts, dtype=float).reshape(-1, 3),
                    np.array(g.faces, dtype=int).reshape(-1, 3),
                )
            if not it.next():
                break
    return out


def footprint(sh: Shape) -> Polygon | None:
    """The plan outline of a body: its top and bottom faces together."""
    tri = np.round(sh.verts[sh.faces], 4)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    size = np.linalg.norm(normal, axis=1)
    flat = np.abs(normal[:, 2]) > 0.5 * np.maximum(size, 1e-12)
    parts = [Polygon(t[:, :2]) for t in tri[flat]]
    parts = [p for p in parts if p.area > 1e-9]
    if not parts:
        return None
    union = unary_union(parts)
    if union.geom_type == "MultiPolygon":
        union = max(list(union.geoms), key=_area)
    return union if isinstance(union, Polygon) else None


def _area(g: Any) -> float:
    return float(g.area)


def strip(fp: Polygon, along: Vec | None) -> tuple[Vec, Vec, float, bool]:
    """A footprint as a wall: the ends of its centre line, its thickness, and whether it is one.

    The direction is the long side of the smallest rectangle around the footprint, turned to agree
    with `along` (the wall's own x axis) if given. The thickness is the width across; mitred ends
    keep the centre line from face to face.
    """
    rect = fp.minimum_rotated_rectangle
    pts = list(rect.exterior.coords)[:3]
    e1 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    e2 = (pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    long_ = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
    size = math.hypot(*long_) or 1.0
    u = (long_[0] / size, long_[1] / size)
    if along is not None:
        turn = u[0] * along[0] + u[1] * along[1] < 0
    else:
        turn = u[0] < -1e-9 or (abs(u[0]) <= 1e-9 and u[1] < 0)
    if turn:
        u = (-u[0], -u[1])
    n = (-u[1], u[0])
    ts = [x * n[0] + y * n[1] for x, y in fp.exterior.coords]
    t0, t1 = min(ts), max(ts)
    mid = (t0 + t1) / 2
    base = (n[0] * mid, n[1] * mid)
    line = LineString(
        [
            (base[0] - u[0] * 1000, base[1] - u[1] * 1000),
            (base[0] + u[0] * 1000, base[1] + u[1] * 1000),
        ]
    )
    cut = fp.intersection(line)
    if cut.is_empty:
        cut = fp
    ss = [(x * u[0] + y * u[1]) for x, y in _coords(cut)]
    s0, s1 = min(ss), max(ss)
    a = (u[0] * s0 + base[0], u[1] * s0 + base[1])
    b = (u[0] * s1 + base[0], u[1] * s1 + base[1])
    t = t1 - t0
    plain = abs(fp.area - t * (s1 - s0)) <= NOTCH * max(fp.area, 1e-9)
    return a, b, t, plain


def _coords(g: Any) -> list[Vec]:
    if g.geom_type == "Point":
        return [(g.x, g.y)]
    if hasattr(g, "geoms"):
        return [c for part in g.geoms for c in _coords(part)]
    return [(x, y) for x, y, *_ in g.coords]


def _axes(ent: Entity) -> tuple[Vec | None, Vec | None]:
    """The wall's own x and y axes in the world, as plan directions."""
    if ent.ObjectPlacement is None:
        return None, None
    m = up.get_local_placement(ent.ObjectPlacement)
    out: list[Vec | None] = []
    for col in (0, 1):
        x, y = float(m[0][col]), float(m[1][col])
        size = math.hypot(x, y)
        out.append((x / size, y / size) if size > 1e-6 else None)
    return out[0], out[1]


# ---------- properties ----------


def _layers(
    mat: Entity | None, scale: float
) -> tuple[tuple[Layer, ...], str | None, str | None, str | None]:
    """Layers in the file's order, the material name if there is one material and no layers,
    and the axis and sense of the layer set usage."""
    if mat is None:
        return (), None, None, None
    axis = sense = None
    layer_set: Entity | None = None
    if mat.is_a("IfcMaterialLayerSetUsage"):
        layer_set, axis, sense = mat.ForLayerSet, mat.LayerSetDirection, mat.DirectionSense
    elif mat.is_a("IfcMaterialLayerSet"):
        layer_set = mat
    elif mat.is_a("IfcMaterial"):
        return (), mat.Name, None, None
    if layer_set is None:
        return (), None, None, None
    out: list[Layer] = []
    for lay in layer_set.MaterialLayers:
        t = float(lay.LayerThickness or 0.0) * scale
        if t < 1e-4:
            continue
        name = (lay.Material.Name if lay.Material is not None else None) or lay.Name or "layer"
        out.append(Layer(str(name), t))
    return tuple(out), None, axis, sense


def _status(ent: Entity, pset: str) -> str:
    return STATUS.get(str(ue.get_pset(ent, pset, "Status") or "").upper(), "new")


def _type_of(ent: Entity) -> tuple[str | None, str | None]:
    t = ue.get_type(ent)
    return (t.GlobalId, t.Name or None) if t is not None else (None, None)


def _u_value(ent: Entity, pset: str) -> float | None:
    v = ue.get_pset(ent, pset, "ThermalTransmittance")
    return float(v) if isinstance(v, int | float) and v > 0 else None


def _container(ent: Entity) -> Entity | None:
    """The storey a product is in: where it is contained, or the storey it is part of."""
    found = ue.get_container(ent, ifc_class="IfcBuildingStorey")
    if found is not None:
        return found
    parent = ue.get_aggregate(ent)
    while parent is not None and not parent.is_a("IfcBuildingStorey"):
        parent = ue.get_aggregate(parent)
    return parent


# ---------- reading ----------


def read(path: Path) -> Source:
    data = path.read_bytes()
    try:
        f = ifcopenshell.open(str(path))
    except Exception as e:
        raise NotImportable(f"cannot read {path} as IFC: {e}") from None
    app = ""
    try:
        app = str(f.header.file_name.originating_system or "")
    except Exception:
        app = ""
    if app.startswith("UEA"):
        raise NotImportable(
            f"{path.name} was exported by UEA. UEA's exports are views and are never read back;"
            " the model is where the project lives (decision 0011)"
        )
    projects = f.by_type("IfcProject")
    title = ""
    if projects:
        title = str(projects[0].LongName or projects[0].Name or "")
    src = Source(path.name, hashlib.sha256(data).hexdigest(), f.schema, app, title)
    scale = uu.calculate_unit_scale(f)
    for s in f.by_type("IfcBuildingStorey"):
        z = s.Elevation
        if z is None and s.ObjectPlacement is not None:
            z = float(up.get_local_placement(s.ObjectPlacement)[2][3])
        src.storeys.append(
            Storey(s.GlobalId, str(s.Name or s.LongName or s.GlobalId), (z or 0) * scale)
        )
    src.storeys.sort(key=lambda s: (s.z, s.name))
    walls = f.by_type("IfcWall")
    doors = [*f.by_type("IfcDoor"), *f.by_type("IfcWindow")]
    slabs = [s for s in f.by_type("IfcSlab") if _is_floor(s)]
    spaces = [s for s in f.by_type("IfcSpace") if str(s.PredefinedType or "") != "EXTERNAL"]
    openings = {o.id(): o for d in doors for r in d.FillsVoids for o in [r.RelatingOpeningElement]}
    sh = shapes(f, [*walls, *doors, *slabs, *spaces, *openings.values()])
    handled: set[int] = set()
    walled: dict[int, str] = {}
    for w in walls:
        handled.add(w.id())
        wall = _wall(w, sh.get(w.id()), scale, src)
        if wall is not None:
            src.walls.append(wall)
            walled[w.id()] = wall.guid
    for d in doors:
        handled.add(d.id())
        op = _opening(d, sh, walled, scale, src)
        if op is not None:
            src.openings.append(op)
    for s in slabs:
        handled.add(s.id())
        slab = _slab(s, sh.get(s.id()), scale, src)
        if slab is not None:
            src.slabs.append(slab)
    for s in spaces:
        handled.add(s.id())
        space = _space(s, sh.get(s.id()), src)
        if space is not None:
            src.spaces.append(space)
    products: list[Entity] = list(f.by_type("IfcProduct"))
    for p in products:
        c = p.is_a()
        if p.id() in handled or c in STRUCTURE:
            continue
        parent = ue.get_aggregate(p)
        if parent is not None and parent.is_a() in COMPONENT_OF:
            continue
        src.skipped[c] += 1
    return src


def _is_floor(slab: Entity) -> bool:
    if str(slab.PredefinedType or "") in ("ROOF", "LANDING"):
        return False
    parent = ue.get_aggregate(slab)
    return parent is None or parent.is_a() not in COMPONENT_OF


def _wall(w: Entity, sh: Shape | None, scale: float, src: Source) -> Wall | None:
    fp = footprint(sh) if sh is not None else None
    if sh is None or fp is None:
        src.skipped["IfcWall (no body)"] += 1
        return None
    x_axis, y_axis = _axes(w)
    a, b, t, plain = strip(fp, x_axis)
    if t < 0.02 or math.hypot(b[0] - a[0], b[1] - a[1]) < 0.05:
        src.skipped["IfcWall (smaller than 2 cm or 5 cm)"] += 1
        return None
    z0, z1 = sh.z()
    mid = (z0 + z1) / 2
    tops = sh.verts[sh.verts[:, 2] > mid][:, 2]
    sloped = bool(len(tops) and float(tops.max() - tops.min()) > 0.02)
    layers, material, axis, sense = _layers(ue.get_material(w, should_inherit=True), scale)
    first: Vec | None = None
    if layers and axis == "AXIS2" and sense in ("POSITIVE", "NEGATIVE") and y_axis is not None:
        towards_y = -1.0 if sense == "POSITIVE" else 1.0
        first = (y_axis[0] * towards_y, y_axis[1] * towards_y)
    tg, tn = _type_of(w)
    storey = _container(w)
    return Wall(
        w.GlobalId,
        str(w.Name or ""),
        storey.GlobalId if storey is not None else None,
        a,
        b,
        t,
        z0,
        z1,
        sloped,
        layers,
        first,
        material,
        tg,
        tn,
        bool(ue.get_pset(w, "Pset_WallCommon", "LoadBearing")),
        _status(w, "Pset_WallCommon"),
        None if plain else "its footprint is not a plain strip; taken as one",
    )


def _opening(
    d: Entity, sh: dict[int, Shape], walled: dict[int, str], scale: float, src: Source
) -> Opening | None:
    cls = d.is_a()
    hosts = [
        (o, v.RelatingBuildingElement)
        for r in d.FillsVoids
        for o in [r.RelatingOpeningElement]
        for v in o.VoidsElements
    ]
    if not hosts:
        src.skipped[f"{cls} (not in a wall)"] += 1
        return None
    oe, host = hosts[0]
    if host.id() not in walled:
        src.skipped[f"{cls} (its wall was not imported)"] += 1
        return None
    body = sh.get(oe.id()) or sh.get(d.id())
    fp = footprint(body) if body is not None else None
    if body is None or fp is None:
        src.skipped[f"{cls} (no body)"] += 1
        return None
    z0, z1 = body.z()
    tg, tn = _type_of(d)
    pset = "Pset_DoorCommon" if cls == "IfcDoor" else "Pset_WindowCommon"
    return Opening(
        d.GlobalId,
        "door" if cls == "IfcDoor" else "win",
        walled[host.id()],
        fp,
        z0,
        z1,
        tg,
        tn,
        _u_value(d, pset),
        _status(d, pset),
    )


def _slab(s: Entity, sh: Shape | None, scale: float, src: Source) -> Slab | None:
    fp = footprint(sh) if sh is not None else None
    if sh is None or fp is None:
        src.skipped["IfcSlab (no body)"] += 1
        return None
    z0, z1 = sh.z()
    layers, material, _, sense = _layers(ue.get_material(s, should_inherit=True), scale)
    if layers and sense == "POSITIVE":
        layers = tuple(reversed(layers))
    storey = _container(s)
    _, tn = _type_of(s)
    return Slab(
        s.GlobalId,
        storey.GlobalId if storey is not None else "",
        layers,
        material,
        z0,
        z1,
        fp.area,
        tn,
        _status(s, "Pset_SlabCommon"),
    )


def _space(s: Entity, sh: Shape | None, src: Source) -> Space | None:
    fp = footprint(sh) if sh is not None else None
    if fp is None:
        src.skipped["IfcSpace (no body)"] += 1
        return None
    storey = _container(s)
    cat = ue.get_pset(s, "Pset_SpaceCommon", "Category") or ue.get_pset(
        s, "Pset_SpaceCommon", "Reference"
    )
    name, long_name = str(s.Name or ""), str(s.LongName or "")
    hint = " ".join(x for x in (long_name, name, str(s.ObjectType or ""), str(cat or "")) if x)
    p = fp.centroid if fp.contains(fp.centroid) else fp.representative_point()
    return Space(
        s.GlobalId,
        storey.GlobalId if storey is not None else None,
        name,
        long_name,
        hint,
        (float(p.x), float(p.y)),
        fp.area,
        sh.z()[0] if sh is not None else 0.0,
        fp,
    )

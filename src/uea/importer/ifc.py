"""Reading an architect's IFC into plain data (decisions 0029, 0030, 0031).

Only what UEA can map is read: storeys, walls with their layers, curtain walls, doors and windows
with the opening they fill, niches, slabs and the voids in them, spaces, grids, and the faces of
stairs and roofs. Geometry comes from IfcOpenShell's tessellation, so it does not matter how the
exporting program wrote a body (extrusion, clipping, mesh): a wall is the strip its footprint draws,
a stair is the horizontal faces its treads make, a roof is the planes of its top. Lengths are
metres, heights are absolute (the world z of the file). The plan is the file's, unless it lies far
from the origin or turned off the axes (`Frame`). One building is read. Deciding what UEA element a
stair or a roof is happens in `stairs.py` and `roofs.py`; this module only reads.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import hashlib
import math
import multiprocessing
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
import ifcopenshell.util.unit as uu
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from uea.core.syntax import fmt_num
from uea.importer.surfaces import Plane, Shape, flat_tops, merge, planes, top_z

Vec = tuple[float, float]
Entity = Any

STATUS = {"NEW": "new", "EXISTING": "existing", "DEMOLISH": "demolish", "TEMPORARY": "temp"}
STRUCTURE = ("IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcOpeningElement")
COMPONENT_OF = ("IfcRoof", "IfcStair", "IfcRamp", "IfcCurtainWall", "IfcRailing", "IfcWall")
"""Parts of these are counted with the whole, not one by one."""
STAIR_PARTS = ("IfcStair", "IfcStairFlight", "IfcSlab", "IfcBuildingElementProxy", "IfcPlate")
"""What makes up a stair's treads. Railings and stringers (members) are left out: their top faces
would pass for treads."""
ROOF_PARTS = (
    "IfcRoof",
    "IfcSlab",
    "IfcPlate",
    "IfcBuildingElementPart",
    "IfcBuildingElementProxy",
)
"""What makes up a roof's planes; a roof nested in another counts with it."""
WALL_PARTS = ("IfcWall", "IfcBuildingElementPart")
"""What a wall in several parts is made of: stacked walls, or one part per layer."""
CURTAIN_PARTS = (
    "IfcCurtainWall",
    "IfcPlate",
    "IfcMember",
    "IfcBuildingElementPart",
    "IfcBuildingElementProxy",
)
"""What makes up the body of a curtain wall: panels and mullions. Its doors are doors."""
FAR = 100.0
"""A plan whose walls lie farther than this (m) from the origin is moved to it."""
TURN_SHARE = 0.5
"""A plan is turned when at least this share of its wall length runs in one direction off x."""
TURN_MIN = 0.1
"""... and that direction is more than this (degrees) off x or y; closer, the walls snap."""
STRIP_MIN = 0.8
"""A wall footprint that fills less of the strip around it is no wall UEA can draw."""
PROFILE_POINTS = 11
"""A wall's top is sampled at this many points along its centre line."""
_PROFILE_AT = [float(s) for s in np.linspace(0.02, 0.98, PROFILE_POINTS)]
HOLE_MIN = 0.05
"""A hole in a slab smaller than this (m²) is a sliver of the tessellation, not an opening."""
JOINED = 0.05
"""Roof slabs with no IfcRoof over them that lie this close (m) are the planes of one roof."""
NOTCH = 0.03
"""A footprint may differ this much (relative to its area) from a plain strip."""


class NotImportable(Exception):
    """The file cannot be imported at all."""


@dataclass(frozen=True)
class Frame:
    """How the file's plan becomes the model's: moved by (dx, dy), then turned by `turn` degrees
    about the origin. The first import of a project chooses it; later ones keep it, so a newer file
    lands where the first one did."""

    turn: float = 0.0
    dx: float = 0.0
    dy: float = 0.0

    @property
    def moves(self) -> bool:
        return bool(self.turn or self.dx or self.dy)

    def _cs(self) -> tuple[float, float]:
        r = math.radians(self.turn)
        return math.cos(r), math.sin(r)

    def vec(self, x: float, y: float) -> Vec:
        """A direction, turned."""
        c, s = self._cs()
        return (c * x - s * y, s * x + c * y)

    def pt(self, x: float, y: float) -> Vec:
        """A point of the file's plan in the model."""
        return self.vec(x + self.dx, y + self.dy)

    def back(self, x: float, y: float) -> Vec:
        """A point of the model in the file's plan."""
        c, s = self._cs()
        return (c * x + s * y - self.dx, -s * x + c * y - self.dy)

    def shape(self, sh: Shape) -> Shape:
        if not self.moves:
            return sh
        c, s = self._cs()
        x, y = sh.verts[:, 0] + self.dx, sh.verts[:, 1] + self.dy
        v = sh.verts.copy()
        v[:, 0] = c * x - s * y
        v[:, 1] = s * x + c * y
        return Shape(v, sh.faces)

    def record(self) -> list[float]:
        return [self.turn, self.dx, self.dy]


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
    profile: tuple[tuple[float, float, float], ...] = ()
    """The top of the wall sampled along its centre line: (x, y, z)."""
    curtain: bool = False
    """A curtain wall: UEA makes it a wall with windows over its face."""
    u: float | None = None
    """Of a curtain wall: its U-value, for the windows."""


@dataclass
class Niche:
    """A recess in one face of a wall, or a hole through it that nothing fills."""

    guid: str
    wall: str
    fp: Polygon
    """Where it lies in the wall, in plan."""
    z0: float
    z1: float
    status: str
    through: bool = False
    dia: float | None = None
    """A core drilling: its diameter."""


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
    holes: tuple[Polygon, ...] = ()
    """Openings cut into the body of the slab itself."""


@dataclass
class Void:
    """An opening element in a floor slab."""

    guid: str
    slab: str
    """GlobalId of the slab it opens."""
    fp: Polygon
    dia: float | None = None
    """A core drilling: its diameter."""


@dataclass
class Grid:
    """A straight grid axis: its tag and two points on it."""

    key: str
    tag: str
    a: Vec
    b: Vec


@dataclass
class Stair:
    """What the faces of a stair say: its tread surfaces, lowest first."""

    guid: str
    name: str
    label: str
    """Class and name, for the report: `IfcStairFlight "Lauf 1"`."""
    storey: str | None
    treads: list[tuple[float, BaseGeometry]]
    """Height and plan region of each group of horizontal faces that look up."""
    z0: float
    z1: float
    status: str


@dataclass
class Roof:
    """The planes of a roof: the faces that look up, and the ones that look down."""

    guid: str
    name: str
    label: str
    """Class and name, for the report: `IfcRoof "Dach"`."""
    storey: str | None
    top: list[Plane]
    under: list[Plane]
    layers: tuple[Layer, ...]
    """Top to bottom."""
    material: str | None
    type_guid: str | None
    type_name: str | None
    z0: float
    z1: float
    status: str

    @property
    def region(self) -> BaseGeometry:
        return unary_union([p.region for p in self.top])


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
    voids: list[Void] = field(default_factory=list[Void])
    spaces: list[Space] = field(default_factory=list[Space])
    grids: list[Grid] = field(default_factory=list[Grid])
    stairs: list[Stair] = field(default_factory=list[Stair])
    roofs: list[Roof] = field(default_factory=list[Roof])
    niches: list[Niche] = field(default_factory=list[Niche])
    skipped: Counter[str] = field(default_factory=Counter[str])
    notes: list[str] = field(default_factory=list[str])
    frame: Frame = field(default_factory=Frame)
    building: str | None = None
    """GlobalId of the building read, if the file has more than one."""


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
    reach = [x * u[0] + y * u[1] for x, y in fp.exterior.coords]
    lo, hi = min(reach) - 1.0, max(reach) + 1.0
    line = LineString(
        [
            (base[0] + u[0] * lo, base[1] + u[1] * lo),
            (base[0] + u[0] * hi, base[1] + u[1] * hi),
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
    if g.geom_type == "Polygon":
        return [(x, y) for x, y, *_ in g.exterior.coords]
    return [(x, y) for x, y, *_ in g.coords]


def _axes(ent: Entity, frame: Frame) -> tuple[Vec | None, Vec | None]:
    """The wall's own x and y axes in the model, as plan directions."""
    if ent.ObjectPlacement is None:
        return None, None
    m = up.get_local_placement(ent.ObjectPlacement)
    out: list[Vec | None] = []
    for col in (0, 1):
        x, y = float(m[0][col]), float(m[1][col])
        size = math.hypot(x, y)
        out.append(frame.vec(x / size, y / size) if size > 1e-6 else None)
    return out[0], out[1]


def place(bodies: list[Shape]) -> Frame:
    """Where a plan goes: moved to the origin if it lies far from it (a file in survey
    coordinates), so that its lower left corner is 0,0, and turned so that most of its walls run
    along x and y.

    The turn is measured after the move: plan geometry millions of metres from the origin loses
    the precision a direction needs.
    """
    if not bodies:
        return Frame()
    lo = np.min([b.verts[:, :2].min(axis=0) for b in bodies], axis=0)
    hi = np.max([b.verts[:, :2].max(axis=0) for b in bodies], axis=0)
    far = math.hypot(*((lo + hi) / 2)) > FAR
    if far:
        bodies = [Shape(b.verts - np.array([lo[0], lo[1], 0.0]), b.faces) for b in bodies]
    turned = Frame(_turn(bodies))
    if not far:
        return turned
    corner = np.min([turned.shape(b).verts[:, :2].min(axis=0) for b in bodies], axis=0)
    back = turned.back(float(corner[0]), float(corner[1]))
    return Frame(turned.turn, -float(lo[0]) - back[0], -float(lo[1]) - back[1])


def _turn(bodies: list[Shape]) -> float:
    """The turn that puts most of the wall length along x and y, in degrees; 0 if none does."""
    runs: list[tuple[float, float]] = []
    for sh in bodies:
        fp = footprint(sh)
        if fp is None:
            continue
        a, b, _, _ = strip(fp, None)
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        runs.append(((angle + 45.0) % 90.0 - 45.0, length))
    total = sum(length for _, length in runs)
    if not runs or total <= 0:
        return 0.0

    def close(x: float, y: float) -> bool:
        d = abs(x - y) % 90.0
        return min(d, 90.0 - d) <= TURN_MIN

    best = max(runs, key=lambda r: sum(n for m, n in runs if close(m, r[0])))
    group = [(m, n) for m, n in runs if close(m, best[0])]
    weight = sum(n for _, n in group)
    turn = 0.0
    if weight >= TURN_SHARE * total:
        # angles near ±45 wrap around: count them on the side of the one that won
        mean = sum(
            (m if abs(m - best[0]) < 45 else m - math.copysign(90.0, m)) * n for m, n in group
        )
        mean /= weight
        if abs(mean) > TURN_MIN:
            turn = round(-mean, 6)
    return turn


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


def _kind(ent: Entity) -> str:
    """The predefined type in capitals. IFC2X3 has none on spaces and openings, and says on
    another attribute whether a space is outside."""
    for name in ("PredefinedType", "InteriorOrExteriorSpace"):
        value = getattr(ent, name, None)
        if value:
            return str(value).upper()
    return ""


def _status(ent: Entity, pset: str) -> str:
    return STATUS.get(str(ue.get_pset(ent, pset, "Status") or "").upper(), "new")


def _type_of(ent: Entity) -> tuple[str | None, str | None]:
    t = ue.get_type(ent)
    return (t.GlobalId, t.Name or None) if t is not None else (None, None)


def _u_value(ent: Entity, pset: str) -> float | None:
    v = ue.get_pset(ent, pset, "ThermalTransmittance")
    return float(v) if isinstance(v, int | float) and v > 0 else None


def _container(ent: Entity) -> Entity | None:
    """The storey a product is in: where it, or the whole it is part of, is contained."""
    cur: Entity | None = ent
    for _ in range(12):
        if cur is None:
            break
        if cur.is_a("IfcBuildingStorey"):
            return cur
        found = ue.get_container(cur, ifc_class="IfcBuildingStorey")
        if found is not None:
            return found
        cur = ue.get_aggregate(cur)
    return None


def _building_of(storey: Entity) -> Entity | None:
    parent = ue.get_aggregate(storey)
    for _ in range(12):
        if parent is None or parent.is_a("IfcBuilding"):
            return parent
        parent = ue.get_aggregate(parent)
    return None


def _world_z(ent: Entity | None, scale: float) -> float | None:
    if ent is None or ent.ObjectPlacement is None:
        return None
    return float(up.get_local_placement(ent.ObjectPlacement)[2][3]) * scale


def _storey_heights(storeys: list[Entity], scale: float) -> dict[int, float]:
    """The height of each storey in the world of the file, where the geometry is.

    The placement says it. Where every storey has the same placement and only `Elevation` tells
    them apart, the elevation counts, from the building's placement (IFC gives it relative to the
    building).
    """
    placed = {s.id(): _world_z(s, scale) for s in storeys}
    raised = {
        s.id(): float(s.Elevation) * scale + (_world_z(_building_of(s), scale) or 0.0)
        for s in storeys
        if s.Elevation is not None
    }
    heights = [z for z in placed.values() if z is not None]
    flat = len(heights) > 1 and max(heights) - min(heights) < 1e-6
    if flat and len(set(raised.values())) > 1:
        placed = {k: raised.get(k, v) for k, v in placed.items()}
    return {k: (v if v is not None else raised.get(k, 0.0)) for k, v in placed.items()}


def _pick_building(
    f: Entity, want: str | None, remembered: str | None, walls: list[Entity], src: "Source"
) -> tuple[Entity | None, Entity | None]:
    """The building to read: the one asked for, else the one an earlier import read, else the main
    one, the one with the most walls. Both are returned; the others are reported."""
    buildings: list[Entity] = list(f.by_type("IfcBuilding"))
    if not buildings:
        return None, None
    count: Counter[int] = Counter()
    for w in walls:
        st = _container(w)
        b = _building_of(st) if st is not None else None
        if b is not None:
            count[b.id()] += 1
    main = max(buildings, key=lambda b: (count[b.id()], -buildings.index(b)))
    chosen = {b.GlobalId: b for b in buildings}.get(remembered or "", main)
    if want is not None:
        low = want.casefold()
        found = [
            b
            for b in buildings
            if low in (str(b.GlobalId).casefold(), str(b.Name or "").casefold())
            or low == str(b.LongName or "").casefold()
        ]
        if not found:
            names = ", ".join(f'"{b.Name or b.GlobalId}"' for b in buildings)
            raise NotImportable(f"{src.file} has no building {want!r}; its buildings: {names}")
        chosen = found[0]
    if len(buildings) > 1:
        src.building = chosen.GlobalId
        for b in buildings:
            if b is not chosen:
                src.skipped[f"{label(b)} (one building per import; --building picks it)"] += 1
    return chosen, main


# ---------- reading ----------


def read(
    path: Path,
    *,
    building: str | None = None,
    remembered: str | None = None,
    frame: Frame | None = None,
) -> Source:
    """The file as plain data. `building` names the building to read (name or GlobalId);
    `remembered` and `frame` are what the project's first import chose."""
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
    every_wall = [w for w in f.by_type("IfcWall") if not _within(w, ("IfcWall",))]
    home, main = _pick_building(f, building, remembered, every_wall, src)
    # what is in no storey goes with the main building, the one with the most walls
    loose = home is None or main is None or home.id() == main.id()
    storeys = [
        s for s in f.by_type("IfcBuildingStorey") if home is None or _building_of(s) in (None, home)
    ]
    heights = _storey_heights(storeys, scale)
    for s in storeys:
        src.storeys.append(
            Storey(s.GlobalId, str(s.Name or s.LongName or s.GlobalId), heights[s.id()])
        )
    src.storeys.sort(key=lambda s: (s.z, s.name))
    mine = {s.id() for s in storeys}

    def ours(e: Entity) -> bool:
        """In the building read."""
        if home is None:
            return True
        st = _container(e)
        return loose if st is None else st.id() in mine

    walls = [w for w in every_wall if ours(w)]
    curtains = [
        c for c in f.by_type("IfcCurtainWall") if ours(c) and not _within(c, ("IfcCurtainWall",))
    ]
    doors = [d for d in (*f.by_type("IfcDoor"), *f.by_type("IfcWindow")) if ours(d)]
    slabs = [s for s in f.by_type("IfcSlab") if _is_floor(s) and ours(s)]
    spaces = [s for s in f.by_type("IfcSpace") if _kind(s) != "EXTERNAL" and ours(s)]
    openings = {o.id(): o for d in doors for r in d.FillsVoids for o in [r.RelatingOpeningElement]}
    voiding, recesses = _voiding(f, openings, {s.id() for s in slabs}, ours, src)
    stairs = [(r, _family(r, STAIR_PARTS)) for r in _stair_roots(f) if ours(r)]
    roofs = [(r, _family(r, ROOF_PARTS)) for r in _roof_roots(f) if ours(r)]
    wall_parts = {w.id(): _family(w, WALL_PARTS) for w in walls}
    curtain_parts = {c.id(): _family(c, CURTAIN_PARTS) for c in curtains}
    families = [*wall_parts.values(), *curtain_parts.values(), *(fam for _, fam in stairs)]
    parts = {e.id(): e for fam in (*families, *(fam for _, fam in roofs)) for e in fam}
    sh = shapes(
        f,
        [
            *parts.values(),
            *doors,
            *slabs,
            *spaces,
            *openings.values(),
            *(o for o, _ in (*voiding, *recesses)),
        ],
    )
    chosen = frame is None
    if frame is None:
        bodies = [merge(sh[e.id()] for e in fam if e.id() in sh) for fam in wall_parts.values()]
        frame = place([b for b in bodies if b is not None])
    src.frame = frame
    if frame.moves:
        sh = {k: frame.shape(v) for k, v in sh.items()}
        moved = [f"moved by {_num(frame.dx)},{_num(frame.dy)} m"] if frame.dx or frame.dy else []
        if frame.turn:
            moved.append(f"turned by {_deg(frame.turn)}°")
        src.notes.append(
            "the file's plan is "
            + " and ".join(moved)
            + (
                ", so its walls run along x and y near the origin"
                if chosen
                else ", as at the first import"
            )
        )
    roofs = _joined(roofs, sh)
    handled: set[int] = {g.id() for g in f.by_type("IfcGrid")}
    walled: dict[int, str] = {}
    for w in walls:
        handled.update(e.id() for e in (w, *wall_parts[w.id()]))
        wall = _wall(w, wall_parts[w.id()], sh, scale, src)
        if wall is not None:
            src.walls.append(wall)
            # an opening may cut one of its parts: it is in the wall all the same
            for e in (w, *wall_parts[w.id()]):
                walled[e.id()] = wall.guid
    for c in curtains:
        handled.update(e.id() for e in (c, *curtain_parts[c.id()]))
        wall = _curtain(c, curtain_parts[c.id()], sh, src)
        if wall is not None:
            src.walls.append(wall)
            walled[c.id()] = wall.guid
    for d in doors:
        handled.add(d.id())
        op = _opening(d, sh, walled, src)
        if op is not None:
            src.openings.append(op)
    by_guid = {w.guid: w for w in src.walls}
    for o, host in recesses:
        handled.add(o.id())
        niche = _niche(o, by_guid.get(walled.get(host.id(), "")), sh, scale, src)
        if niche is not None:
            src.niches.append(niche)
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
    for o, host in voiding:
        void = _void(o, host, sh, scale, src)
        if void is not None:
            src.voids.append(void)
    for root, fam in stairs:
        handled.add(root.id())
        stair = _stair(root, fam, sh, src)
        if stair is not None:
            src.stairs.append(stair)
    for root, fam in roofs:
        handled.update(e.id() for e in (root, *fam))
        roof = _roof(root, fam, sh, scale, src)
        if roof is not None:
            src.roofs.append(roof)
    _grids([g for g in f.by_type("IfcGrid") if ours(g)], scale, src)
    products: list[Entity] = list(f.by_type("IfcProduct"))
    for p in products:
        c = p.is_a()
        if p.id() in handled or c in STRUCTURE or not ours(p):
            continue
        parent = ue.get_aggregate(p)
        if parent is not None and parent.is_a() in COMPONENT_OF:
            continue
        src.skipped[c] += 1
    return src


def _num(v: float) -> str:
    return fmt_num(round(v, 4))


def _deg(v: float) -> str:
    return fmt_num(round(v, 2))


def _is_floor(slab: Entity) -> bool:
    if _kind(slab) in ("ROOF", "LANDING"):
        return False
    parent = ue.get_aggregate(slab)
    return parent is None or parent.is_a() not in COMPONENT_OF


def _first(
    layers: tuple[Layer, ...], axis: str | None, sense: str | None, y: Vec | None
) -> Vec | None:
    """Where the first layer lies, from the layer set usage: along the wall's own y axis."""
    if layers and axis == "AXIS2" and sense in ("POSITIVE", "NEGATIVE") and y is not None:
        towards_y = -1.0 if sense == "POSITIVE" else 1.0
        return (y[0] * towards_y, y[1] * towards_y)
    return None


def _bent(w: Entity) -> str | None:
    """Why a wall is no straight wall, from its axis: curved, or bent along a polyline."""
    rep = getattr(w, "Representation", None)
    for r in rep.Representations if rep is not None else ():
        if r.RepresentationIdentifier != "Axis":
            continue
        for item in r.Items:
            if _curve_bends(item) == "arc":
                return "curved"
            if _curve_bends(item) == "kink":
                return "its axis bends"
    return None


def _curve_bends(c: Entity) -> str | None:
    if c.is_a("IfcTrimmedCurve"):
        return None if c.BasisCurve.is_a("IfcLine") else "arc"
    if c.is_a("IfcConic") or c.is_a("IfcBSplineCurve"):
        return "arc"
    if c.is_a("IfcCompositeCurve"):
        found = [_curve_bends(getattr(s, "ParentCurve", None) or s) for s in c.Segments]
        return "arc" if "arc" in found else "kink" if len(found) > 1 else None
    if c.is_a("IfcIndexedPolyCurve"):
        if any(s.is_a("IfcArcIndex") for s in c.Segments or ()):
            return "arc"
        pts = [(float(p[0]), float(p[1])) for p in c.Points.CoordList]
        return "kink" if _straight(pts) is None else None
    if c.is_a("IfcPolyline"):
        pts = [(float(p.Coordinates[0]), float(p.Coordinates[1])) for p in c.Points]
        return "kink" if _straight(pts) is None else None
    return None


def _material_name(ent: Entity) -> str | None:
    mat = ue.get_material(ent, should_inherit=True)
    if mat is None:
        return None
    if mat.is_a("IfcMaterial"):
        return str(mat.Name or "") or None
    layers, name, _, _ = _layers(mat, 1.0)
    return layers[0].material if layers else name


def _skins(
    parts: list[tuple[Entity, Shape]], a: Vec, b: Vec
) -> tuple[tuple[Layer, ...], Vec] | None:
    """The layers of a wall whose parts lie side by side, one part per layer (a program that
    writes each layer as a part): in order across the wall, and the side of the first."""
    if any(not e.is_a("IfcBuildingElementPart") for e, _ in parts):
        return None
    u = (b[0] - a[0], b[1] - a[1])
    size = math.hypot(*u)
    if size < 1e-9:
        return None
    n = (-u[1] / size, u[0] / size)
    found: list[tuple[float, Layer]] = []
    for e, s in parts:
        fp = footprint(s)
        if fp is None:
            return None
        qs = [x * n[0] + y * n[1] for x, y in fp.exterior.coords]
        name = _material_name(e) or str(e.Name or "") or "layer"
        found.append((min(qs), Layer(name, round(max(qs) - min(qs), 4))))
    found.sort(key=lambda x: x[0])
    for (q0, lay), (q1, _) in pairwise(found):
        if abs(q0 + lay.t - q1) > 0.005:
            return None  # not side by side: parts above one another, or a gap
    return tuple(lay for _, lay in found), (-n[0], -n[1])


def _wall(
    w: Entity, fam: list[Entity], sh: dict[int, Shape], scale: float, src: Source
) -> Wall | None:
    called = label(w)
    bent = _bent(w)
    if bent is not None:
        src.skipped[f"{called} ({bent})"] += 1
        return None
    bodies = [(e, sh[e.id()]) for e in fam if e.id() in sh]
    body = merge(s for _, s in bodies)
    fp = footprint(body) if body is not None else None
    if body is None or fp is None:
        src.skipped["IfcWall (no body)"] += 1
        return None
    x_axis, y_axis = _axes(w, src.frame)
    a, b, t, plain = strip(fp, x_axis)
    layers, material, axis, sense = _layers(ue.get_material(w, should_inherit=True), scale)
    first = _first(layers, axis, sense, y_axis)
    note: str | None = None
    parts = [(e, s) for e, s in bodies if e is not w]
    if parts:
        note = f"made of {len(parts)} parts; imported as one wall"
        stacked = (
            f"made of {len(parts)} parts one above another; imported as one wall,"
            " the tallest part's"
        )
        tallest = max(parts, key=lambda p: p[1].z()[1] - p[1].z()[0])
        if not plain:
            # stacked parts of different thickness: the tallest one is the wall
            own = footprint(tallest[1])
            if own is not None:
                fp = own
                a, b, t, plain = strip(own, x_axis)
                note = stacked
        if not layers:
            skins = _skins(parts, a, b)
            if skins is not None:
                layers, first = skins
                material = None
                note = f"made of {len(parts)} parts, one per layer; imported as one wall"
            else:
                mat = ue.get_material(tallest[0], should_inherit=True)
                layers, material, axis, sense = _layers(mat, scale)
                first = _first(layers, axis, sense, _axes(tallest[0], src.frame)[1])
                note = stacked
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if t < 0.02 or length < 0.05:
        src.skipped["IfcWall (smaller than 2 cm or 5 cm)"] += 1
        return None
    if fp.area < STRIP_MIN * t * length:
        src.skipped[f"{called} (its footprint is no straight strip)"] += 1
        return None
    if not plain:
        note = "its footprint is not a plain strip; taken as one"
    z0, z1 = body.z()
    mid = (z0 + z1) / 2
    tops = body.verts[body.verts[:, 2] > mid][:, 2]
    along = [(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s) for s in _PROFILE_AT]
    profile = tuple(
        (x, y, z) for (x, y), z in zip(along, top_z(body, along), strict=True) if z is not None
    )
    # the corners of a gable end lie below its middle: the profile shows what the corners do not.
    # Parts stacked one on another have tops inside the wall: there only the profile counts.
    heights = [z for _, _, z in profile]
    sloped = bool(
        (not parts and len(tops) and float(tops.max() - tops.min()) > 0.02)
        or (len(heights) > 1 and max(heights) - min(heights) > 0.02)
    )
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
        note,
        profile,
    )


def _curtain(c: Entity, fam: list[Entity], sh: dict[int, Shape], src: Source) -> Wall | None:
    """A curtain wall as the strip around its panels and mullions (its footprint is a comb, so how
    much of the strip it fills says nothing; a bent one says so in its axis)."""
    called = label(c)
    bent = _bent(c)
    if bent is not None:
        src.skipped[f"{called} ({bent})"] += 1
        return None
    body = merge(sh[e.id()] for e in fam if e.id() in sh)
    feet = [p for e in fam if e.id() in sh and (p := footprint(sh[e.id()])) is not None]
    if body is None or not feet:
        src.skipped[f"{called} (no body)"] += 1
        return None
    hull = unary_union(feet).convex_hull
    if not isinstance(hull, Polygon):
        src.skipped[f"{called} (no body)"] += 1
        return None
    x_axis, _ = _axes(c, src.frame)
    a, b, t, _ = strip(hull, x_axis)
    if t < 0.02 or math.hypot(b[0] - a[0], b[1] - a[1]) < 0.05:
        src.skipped[f"{called} (smaller than 2 cm or 5 cm)"] += 1
        return None
    z0, z1 = body.z()
    tg, tn = _type_of(c)
    storey = _container(c)
    return Wall(
        c.GlobalId,
        str(c.Name or ""),
        storey.GlobalId if storey is not None else None,
        a,
        b,
        t,
        z0,
        z1,
        False,
        (),
        None,
        "curtain",
        tg,
        tn,
        False,
        _status(c, "Pset_CurtainWallCommon"),
        curtain=True,
        u=_u_value(c, "Pset_CurtainWallCommon"),
    )


def _opening(
    d: Entity, sh: dict[int, Shape], walled: dict[int, str], src: Source
) -> Opening | None:
    cls = d.is_a()
    hosts = [
        (o, v.RelatingBuildingElement)
        for r in d.FillsVoids
        for o in [r.RelatingOpeningElement]
        for v in o.VoidsElements
    ]
    if hosts:
        oe, host = hosts[0]
        body = sh.get(oe.id()) or sh.get(d.id())
    else:
        # a door in a curtain wall is one of its parts; its windows are its glazing
        host = ue.get_aggregate(d)
        if host is None or not host.is_a("IfcCurtainWall"):
            src.skipped[f"{cls} (not in a wall)"] += 1
            return None
        if cls != "IfcDoor":
            return None
        body = sh.get(d.id())
    if host.id() not in walled:
        src.skipped[f"{cls} (its wall was not imported)"] += 1
        return None
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
    holes = tuple(h for h in (Polygon(r) for r in fp.interiors) if h.area >= HOLE_MIN)
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
        holes,
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


# ---------- voids, stairs, roofs, grids ----------


def _within(ent: Entity, classes: tuple[str, ...]) -> bool:
    parent = ue.get_aggregate(ent)
    return parent is not None and any(parent.is_a(c) for c in classes)


def _voiding(
    f: Entity,
    filled: dict[int, Entity],
    floors: set[int],
    ours: Callable[[Entity], bool],
    src: Source,
) -> tuple[list[tuple[Entity, Entity]], list[tuple[Entity, Entity]]]:
    """The opening elements nothing fills: those cut into a floor slab, and those cut into a wall
    (a niche, if it does not go through), each with its host. Openings in anything else are
    counted as not imported."""
    floor: list[tuple[Entity, Entity]] = []
    wall: list[tuple[Entity, Entity]] = []
    for o in f.by_type("IfcOpeningElement"):
        if o.id() in filled:
            continue
        for rel in o.VoidsElements:
            host = rel.RelatingBuildingElement
            if not ours(host):
                continue
            if host.id() in floors:
                floor.append((o, host))
            elif host.is_a("IfcWall"):
                wall.append((o, host))
            else:
                src.skipped["IfcOpeningElement (not in a wall or a floor slab)"] += 1
    return floor, wall


NICHE_FACE = 0.005
"""A recess that reaches this close to a face of its wall opens on that face."""


def _niche(
    o: Entity, w: Wall | None, sh: dict[int, Shape], scale: float, src: Source
) -> Niche | None:
    """A recess in one face of a wall, or a hole through it (decision 0039)."""
    if w is None:
        src.skipped["IfcOpeningElement (its wall was not imported)"] += 1
        return None
    body = sh.get(o.id())
    fp = footprint(body) if body is not None else None
    if body is None or fp is None:
        src.skipped["IfcOpeningElement (no body)"] += 1
        return None
    u = (w.b[0] - w.a[0], w.b[1] - w.a[1])
    size = math.hypot(*u) or 1.0
    n = (-u[1] / size, u[0] / size)
    qs = [(x - w.a[0]) * n[0] + (y - w.a[1]) * n[1] for x, y in fp.exterior.coords]
    lo, hi = max(min(qs), -w.t / 2), min(max(qs), w.t / 2)
    status = _status(o, "Pset_OpeningElementCommon")
    if hi - lo >= w.t - 0.01:
        z0, z1 = body.z()
        return Niche(o.GlobalId, w.guid, fp, z0, z1, status, through=True, dia=_dia(o, scale))
    if min(qs) > -w.t / 2 + NICHE_FACE and max(qs) < w.t / 2 - NICHE_FACE:
        src.skipped["IfcOpeningElement (a recess inside its wall)"] += 1
        return None
    z0, z1 = body.z()
    return Niche(o.GlobalId, w.guid, fp, z0, z1, status)


def _dia(o: Entity, scale: float) -> float | None:
    """The diameter of an opening whose body is a swept circle: a core drilling."""
    rep = o.Representation
    for r in rep.Representations if rep is not None else ():
        for it in r.Items:
            if it.is_a("IfcExtrudedAreaSolid") and it.SweptArea.is_a("IfcCircleProfileDef"):
                return float(it.SweptArea.Radius) * 2 * scale
    return None


def _void(o: Entity, host: Entity, sh: dict[int, Shape], scale: float, src: Source) -> Void | None:
    body = sh.get(o.id())
    fp = footprint(body) if body is not None else None
    if fp is None:
        src.skipped["IfcOpeningElement (no body)"] += 1
        return None
    return Void(o.GlobalId, host.GlobalId, fp, _dia(o, scale))


def _stair_roots(f: Entity) -> list[Entity]:
    """The stairs: each IfcStair, and the flights that belong to none."""
    out: list[Entity] = list(f.by_type("IfcStair"))
    out += [s for s in f.by_type("IfcStairFlight") if not _within(s, ("IfcStair",))]
    return out


def _roof_roots(f: Entity) -> list[Entity]:
    """The roofs: each IfcRoof, and the roof slabs that belong to none (see `_joined`)."""
    out: list[Entity] = [r for r in f.by_type("IfcRoof") if not _within(r, ("IfcRoof",))]
    out += [s for s in f.by_type("IfcSlab") if _kind(s) == "ROOF" and not _within(s, ("IfcRoof",))]
    return out


def _joined(
    roofs: list[tuple[Entity, list[Entity]]], sh: dict[int, Shape]
) -> list[tuple[Entity, list[Entity]]]:
    """Roof slabs that no IfcRoof gathers, and that touch, are the planes of one roof: a program
    that writes every pitch as a slab of its own still means one roof. The slab with the lowest
    GlobalId stands for the group."""
    lone = sorted((x for x in roofs if x[0].is_a("IfcSlab")), key=lambda x: x[0].GlobalId)
    out = [x for x in roofs if not x[0].is_a("IfcSlab")]
    feet = {r.id(): footprint(sh[r.id()]) if r.id() in sh else None for r, _ in lone}
    groups: list[list[tuple[Entity, list[Entity]]]] = []
    for item in lone:
        fp = feet[item[0].id()]
        touching = [
            g
            for g in groups
            if fp is not None
            and any((o := feet[r.id()]) is not None and fp.distance(o) <= JOINED for r, _ in g)
        ]
        group = [item]
        for g in touching:
            groups.remove(g)
            group += g
        groups.append(sorted(group, key=lambda x: x[0].GlobalId))
    out += [(g[0][0], [e for _, fam in g for e in fam]) for g in groups]
    return out


def _family(root: Entity, classes: tuple[str, ...]) -> list[Entity]:
    """A product and the parts of it that carry the body, if they are of the given classes."""
    out: list[Entity] = [root] if getattr(root, "Representation", None) is not None else []
    queue = list(ue.get_parts(root))
    while queue:
        e = queue.pop()
        if any(e.is_a(c) for c in classes):
            if getattr(e, "Representation", None) is not None:
                out.append(e)
            queue.extend(ue.get_parts(e))
    return out


def label(ent: Entity) -> str:
    """Class and name of a product, as the report names it."""
    name = str(ent.Name or "").replace('"', "'")
    return f'{ent.is_a()} "{name}"' if name else ent.is_a()


def _stair(root: Entity, fam: list[Entity], sh: dict[int, Shape], src: Source) -> Stair | None:
    cls, called = root.is_a(), label(root)
    body = merge(sh[e.id()] for e in fam if e.id() in sh)
    if body is None:
        src.skipped[f"{called} (no body)"] += 1
        return None
    treads = flat_tops(body)
    if len(treads) < 2:
        src.skipped[f"{called} (fewer than two tread levels in its body)"] += 1
        return None
    storey = _container(root)
    z0, z1 = body.z()
    pset = "Pset_StairFlightCommon" if cls == "IfcStairFlight" else "Pset_StairCommon"
    return Stair(
        root.GlobalId,
        str(root.Name or ""),
        called,
        storey.GlobalId if storey is not None else None,
        treads,
        z0,
        z1,
        _status(root, pset),
    )


def _roof(
    root: Entity, fam: list[Entity], sh: dict[int, Shape], scale: float, src: Source
) -> Roof | None:
    cls, called = root.is_a(), label(root)
    body = merge(sh[e.id()] for e in fam if e.id() in sh)
    if body is None:
        src.skipped[f"{called} (no body)"] += 1
        return None
    top = planes(body, up=True)
    if not top:
        src.skipped[f"{called} (no faces that look up)"] += 1
        return None
    layers: tuple[Layer, ...] = ()
    material: str | None = None
    for e in (root, *fam):
        found, mat, _, sense = _layers(ue.get_material(e, should_inherit=True), scale)
        if found:
            layers = tuple(reversed(found)) if sense == "POSITIVE" else found
            material = None
            break
        material = material or mat
    tg = tn = None
    for e in (root, *fam):
        tg, tn = _type_of(e)
        if tg or tn:
            break
    storey = _container(root)
    z0, z1 = body.z()
    return Roof(
        root.GlobalId,
        str(root.Name or ""),
        called,
        storey.GlobalId if storey is not None else None,
        top,
        planes(body, up=False),
        layers,
        material,
        tg,
        tn,
        z0,
        z1,
        _status(root, "Pset_RoofCommon" if cls == "IfcRoof" else "Pset_SlabCommon"),
    )


def _grids(grids: list[Entity], scale: float, src: Source) -> None:
    for g in grids:
        m = (
            up.get_local_placement(g.ObjectPlacement)
            if g.ObjectPlacement is not None
            else np.eye(4)
        )
        for letter, axes in (("U", g.UAxes), ("V", g.VAxes)):
            for i, axis in enumerate(axes or ()):
                tag = str(axis.AxisTag or f"{letter}{i + 1}")
                ends = _axis_line(axis.AxisCurve)
                if ends is None:
                    src.skipped["IfcGrid axis (not a straight line)"] += 1
                    continue
                a, b = (
                    src.frame.pt(float(w[0]) * scale, float(w[1]) * scale)
                    for w in (m @ np.array([x, y, 0.0, 1.0]) for x, y in ends)
                )
                src.grids.append(Grid(f"{g.GlobalId}:{letter}:{tag}", tag, a, b))


def _axis_line(curve: Entity | None) -> tuple[Vec, Vec] | None:
    """Two points on a straight grid axis, in the grid's own coordinates (file units)."""
    if curve is None:
        return None
    if curve.is_a("IfcPolyline"):
        return _straight([(float(c.Coordinates[0]), float(c.Coordinates[1])) for c in curve.Points])
    if curve.is_a("IfcIndexedPolyCurve"):
        if any(s.is_a("IfcArcIndex") for s in curve.Segments or ()):
            return None
        return _straight([(float(c[0]), float(c[1])) for c in curve.Points.CoordList])
    if curve.is_a("IfcTrimmedCurve"):
        return _axis_line(curve.BasisCurve) if curve.BasisCurve.is_a("IfcLine") else None
    if curve.is_a("IfcLine"):
        p, v = curve.Pnt.Coordinates, curve.Dir
        d = v.Orientation.DirectionRatios
        k = float(v.Magnitude or 1.0) / (math.hypot(d[0], d[1], d[2] if len(d) > 2 else 0.0) or 1.0)
        a = (float(p[0]), float(p[1]))
        return _straight([a, (a[0] + k * float(d[0]), a[1] + k * float(d[1]))])
    return None


def _straight(pts: list[Vec]) -> tuple[Vec, Vec] | None:
    """The ends of a polyline if it is one straight line of some length, else nothing."""
    if len(pts) < 2:
        return None
    a, b = pts[0], pts[-1]
    size = math.hypot(b[0] - a[0], b[1] - a[1])
    if size < 1e-9:
        return None
    for p in pts[1:-1]:
        if abs((p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])) / size > 0.002 * size:
            return None
    return a, b

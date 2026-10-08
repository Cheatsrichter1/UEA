"""IFC4 export with IfcOpenShell (LGPL, used as a library).

Stable GlobalIds come from the project name and the element id, so a re-export of the same
element keeps its GlobalId. Geometry is explicit: extrusions for walls, slabs and stairs, a
boolean clipping where one roof cuts a wall, triangulated solids for roof planes, for walls
under several roofs and for rooms under a sloped ceiling.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import math
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.type
import ifcopenshell.guid
import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from uea import __version__
from uea.core.values import Layers
from uea.derive import Derived
from uea.geom import Lin, Part, halfplane, polys, union_pieces
from uea.packs.arch.geometry import ArchGeo, OpeningGeo, RoofGeo, StairGeo, StairPartGeo, WallGeo
from uea.packs.arch.kinds import Door, DoorType, Roof, Room, Win, WinType

NS = uuid.UUID("6f1d2a8e-3c4b-5d6e-8f90-a1b2c3d4e5f6")
STATUS = {"new": "NEW", "existing": "EXISTING", "demolish": "DEMOLISH", "temp": "TEMPORARY"}
Entity = Any


def roof_type(el: Roof) -> str:
    """The IfcRoofTypeEnum of a roof."""
    if el.shape == "gable" and el.halfhip is not None:
        return "HIPPED_GABLE_ROOF"
    if el.shape == "mansard":
        return "GAMBREL_ROOF" if el.ridge is not None else "MANSARD_ROOF"
    return {
        "gable": "GABLE_ROOF",
        "shed": "SHED_ROOF",
        "hip": "HIP_ROOF",
        "flat": "FLAT_ROOF",
    }[el.shape]


class Writer:
    def __init__(self, d: Derived) -> None:
        self.d = d
        self.g: ArchGeo = d.arch
        self.f = ifcopenshell.file(schema="IFC4")
        self.project_name = d.model.project_name() or "project"
        self.materials: dict[str, Entity] = {}
        self.types: dict[str, Entity] = {}
        self.counts: dict[str, int] = {}
        self._roof_pieces: dict[str, list[tuple[int, Lin, Polygon]]] = {}

    # ---------- basics ----------

    def guid(self, key: str) -> str:
        return ifcopenshell.guid.compress(uuid.uuid5(NS, f"{self.project_name}/{key}").hex)

    def entity(
        self, cls: str, key: str, name: str | None = None, predefined: str | None = None
    ) -> Entity:
        e = ifcopenshell.api.root.create_entity(
            self.f, ifc_class=cls, predefined_type=predefined, name=name
        )
        e.GlobalId = self.guid(key)
        if cls not in ("IfcProject", "IfcOpeningElement") and not cls.endswith("Type"):
            self.counts[cls] = self.counts.get(cls, 0) + 1
        return e

    def pt(self, *c: float) -> Entity:
        return self.f.createIfcCartesianPoint([float(x) for x in c])

    def dir(self, *c: float) -> Entity:
        return self.f.createIfcDirection([float(x) for x in c])

    def axis(
        self,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        z: tuple[float, float, float] | None = None,
        x: tuple[float, float, float] | None = None,
    ) -> Entity:
        return self.f.createIfcAxis2Placement3D(
            self.pt(*origin), self.dir(*z) if z else None, self.dir(*x) if x else None
        )

    def placement(
        self, rel: Entity | None, origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> Entity:
        return self.f.createIfcLocalPlacement(rel, self.axis(origin))

    def ring(self, pts: Sequence[tuple[float, ...]]) -> Entity:
        pp = [self.f.createIfcCartesianPoint([float(x), float(y)]) for x, y in pts]
        return self.f.createIfcPolyline([*pp, pp[0]])

    def profile(self, poly: Polygon) -> Entity:
        p = orient(poly, 1.0)
        outer = self.ring(list(p.exterior.coords)[:-1])
        if p.interiors:
            inner = [self.ring(list(h.coords)[:-1]) for h in p.interiors]
            return self.f.createIfcArbitraryProfileDefWithVoids("AREA", None, outer, inner)
        return self.f.createIfcArbitraryClosedProfileDef("AREA", None, outer)

    def extrude(self, poly: Polygon, z0: float, h: float) -> Entity:
        return self.f.createIfcExtrudedAreaSolid(
            self.profile(poly), self.axis((0.0, 0.0, z0)), self.dir(0, 0, 1), float(h)
        )

    def clip(self, solid: Entity, planes: list[Lin], offset: float = 0.0) -> Entity:
        """Remove everything above each plane z = a*x + b*y + c (+ offset)."""
        out = solid
        for p in planes:
            n = (-p.a, -p.b, 1.0)
            ln_ = math.sqrt(sum(c * c for c in n))
            n = (n[0] / ln_, n[1] / ln_, n[2] / ln_)
            ref = (
                (n[2], 0.0, -n[0]) if abs(n[0]) > 1e-9 or abs(n[2]) < 1 - 1e-9 else (1.0, 0.0, 0.0)
            )
            rl = math.sqrt(sum(c * c for c in ref)) or 1.0
            ref = (ref[0] / rl, ref[1] / rl, ref[2] / rl)
            plane = self.f.createIfcPlane(self.axis((0.0, 0.0, p.c + offset), n, ref))
            half = self.f.createIfcHalfSpaceSolid(plane, False)
            out = self.f.createIfcBooleanClippingResult("DIFFERENCE", out, half)
        return out

    def body(self, items: list[Entity], kind: str) -> Entity:
        rep = self.f.createIfcShapeRepresentation(self.body_ctx, "Body", kind, items)
        return self.f.createIfcProductDefinitionShape(None, None, [rep])

    def pset(self, product: Entity, name: str, props: dict[str, Any]) -> None:
        clean = {k: v for k, v in props.items() if v is not None}
        if not clean:
            return
        ps = ifcopenshell.api.pset.add_pset(self.f, product=product, name=name)
        ifcopenshell.api.pset.edit_pset(self.f, pset=ps, properties=clean)

    def material(self, name: str) -> Entity:
        if name not in self.materials:
            self.materials[name] = ifcopenshell.api.material.add_material(self.f, name=name)
        return self.materials[name]

    def layer_set(self, name: str, layers: Layers) -> Entity:
        ls = ifcopenshell.api.material.add_material_set(
            self.f, name=name, set_type="IfcMaterialLayerSet"
        )
        for x in layers.items:
            layer = ifcopenshell.api.material.add_layer(
                self.f, layer_set=ls, material=self.material(x.material)
            )
            ifcopenshell.api.material.edit_layer(
                self.f, layer=layer, attributes={"LayerThickness": float(x.t), "Name": x.material}
            )
        return ls

    def type_of(
        self, cls: str, name: str, layers: Layers | None, predefined: str | None = None
    ) -> Entity:
        key = f"type/{name}"
        if key not in self.types:
            t = self.entity(cls, key, name, predefined)
            if layers is not None:
                ifcopenshell.api.material.assign_material(
                    self.f,
                    products=[t],
                    type="IfcMaterialLayerSet",
                    material=self.layer_set(name, layers),
                )
            self.types[key] = t
        return self.types[key]

    # ---------- model ----------

    def write(self, path: Path) -> dict[str, int]:
        f = self.f
        m = self.d.model
        proj_el = m.of_kind("project")
        title = (proj_el[0].label or proj_el[0].id) if proj_el else self.project_name
        project = self.entity("IfcProject", "project", title)
        units = [
            f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
            f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
            f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
            f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
        ]
        project.UnitsInContext = f.createIfcUnitAssignment(units)
        model_ctx = ifcopenshell.api.context.add_context(f, context_type="Model")
        self.body_ctx = ifcopenshell.api.context.add_context(
            f,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=model_ctx,
        )
        site = self.entity("IfcSite", "site", "Grundstück")
        building = self.entity("IfcBuilding", "building", title)
        ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
        ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)
        site.ObjectPlacement = self.placement(None)
        building.ObjectPlacement = self.placement(site.ObjectPlacement)
        if proj_el:
            pe = proj_el[0]
            ground = getattr(pe, "ground", None)
            if ground is not None:
                site.RefElevation = float(ground)
        self.storeys: dict[str, Entity] = {}
        for lv_id in self.g.level_order():
            lv = self.g.levels[lv_id]
            st = self.entity("IfcBuildingStorey", f"level/{lv_id}", lv_id)
            el = m[lv_id]
            st.LongName = el.label
            st.Elevation = float(lv.z)
            st.ObjectPlacement = self.placement(building.ObjectPlacement, (0.0, 0.0, lv.z))
            self.storeys[lv_id] = st
        if self.storeys:
            ifcopenshell.api.aggregate.assign_object(
                f, products=list(self.storeys.values()), relating_object=building
            )
        self.contained: dict[str, list[Entity]] = {k: [] for k in self.storeys}
        for w in self.g.walls.values():
            self.wall(w)
        for sl in self.g.slabs.values():
            self.slab(sl.id)
        for rf in self.g.roofs.values():
            self.roof(rf)
        for st in self.g.stairs.values():
            self.stair(st.id)
        for rg in self.g.rooms.values():
            self.space(rg.id)
        for lv_id, items in self.contained.items():
            if items:
                ifcopenshell.api.spatial.assign_container(
                    f, products=items, relating_structure=self.storeys[lv_id]
                )
        f.header.file_name.originating_system = f"UEA {__version__}"
        f.header.file_name.preprocessor_version = "IfcOpenShell"
        f.write(str(path))
        return dict(sorted(self.counts.items()))

    def _common(self, e: Entity, uea_id: str, label: str | None) -> None:
        e.Tag = uea_id
        if label:
            e.Description = label

    def wall(self, w: WallGeo) -> None:
        m = self.d.model
        el = m[w.id]
        lv = self.g.levels[w.level]
        e = self.entity("IfcWall", w.id, w.id, "SOLIDWALL" if w.lb else "PARTITIONING")
        self._common(e, w.id, el.label)
        e.ObjectPlacement = self.placement(self.storeys[w.level].ObjectPlacement)
        lo = w.lo - w.finish("lo")
        hi = w.hi + w.finish("hi")
        z0 = w.bottom - lv.z
        top = max((z for _, z in w.top), default=w.bottom + 2.5) - lv.z
        body = w.box(lo, hi)
        top_el = getattr(el, "top", None)
        parts = (
            self.g.roof_parts(self.g.roofs[top_el.id].level)
            if top_el is not None and top_el.id in self.g.roofs
            else []
        )
        items: list[Entity] = []
        kind = "SweptSolid"
        if len(parts) == 1:
            solid = self.extrude(body, z0, max(top - z0, 0.01))
            items = [self.clip(solid, [Lin(p.a, p.b, p.c - lv.z) for p in parts[0].planes])]
            kind = "Clipping"
        elif parts:
            under = [
                Part(rf.foot, tuple(Lin(p.a, p.b, p.c - lv.z) for p in rf.planes)) for rf in parts
            ]
            floor = Lin(0.0, 0.0, z0)
            items = [self.prism(poly, floor, f) for _, f, poly in union_pieces(under, body)]
            kind = "Tessellation"
        if not items:
            items = [self.extrude(body, z0, max(top - z0, 0.01))]
            kind = "SweptSolid"
        e.Representation = self.body(items, kind)
        t = self.type_of("IfcWallType", el.type.id, w.layers)
        ifcopenshell.api.type.assign_type(
            self.f, related_objects=[e], relating_type=t, should_map_representations=False
        )
        self.pset(
            e,
            "Pset_WallCommon",
            {
                "IsExternal": w.ext is not None,
                "LoadBearing": w.lb,
                "Status": STATUS[w.status],
                "Reference": el.type.id,
            },
        )
        self.contained[w.level].append(e)
        for o in self.g.openings.values():
            if o.host == w.id:
                self.opening(o, w, e)

    def opening(self, o: OpeningGeo, w: WallGeo, wall: Entity) -> None:
        m = self.d.model
        el = m[o.id]
        place = self.storeys[w.level].ObjectPlacement
        if o.kind == "niche":
            a, b = (
                (w.hi - o.depth, w.hi + 0.05) if o.face == "hi" else (w.lo - 0.05, w.lo + o.depth)
            )
            a -= w.finish("lo") if o.face == "lo" else 0.0
            b += w.finish("hi") if o.face == "hi" else 0.0
            op = self.entity("IfcOpeningElement", f"{o.id}/opening", o.id, "RECESS")
        else:
            a, b = w.lo - w.finish("lo") - 0.05, w.hi + w.finish("hi") + 0.05
            op = self.entity("IfcOpeningElement", f"{o.id}/opening", o.id, "OPENING")
        op.ObjectPlacement = self.placement(place)
        box = Polygon(
            [
                w.plan_point(o.lo, a),
                w.plan_point(o.hi, a),
                w.plan_point(o.hi, b),
                w.plan_point(o.lo, b),
            ]
        )
        op.Representation = self.body([self.extrude(box, o.sill, o.top - o.sill)], "SweptSolid")
        ifcopenshell.api.feature.add_feature(self.f, feature=op, element=wall)
        if o.kind == "niche":
            return
        cls = "IfcDoor" if o.kind == "door" else "IfcWindow"
        e = self.entity(cls, o.id, o.id, "DOOR" if o.kind == "door" else "WINDOW")
        self._common(e, o.id, el.label)
        e.ObjectPlacement = self.placement(place)
        e.OverallWidth = float(o.width)
        e.OverallHeight = float(o.top - o.sill)
        panel = Polygon(
            [
                w.plan_point(o.lo, w.mid - 0.03),
                w.plan_point(o.hi, w.mid - 0.03),
                w.plan_point(o.hi, w.mid + 0.03),
                w.plan_point(o.lo, w.mid + 0.03),
            ]
        )
        e.Representation = self.body([self.extrude(panel, o.sill, o.top - o.sill)], "SweptSolid")
        ifcopenshell.api.feature.add_filling(self.f, opening=op, element=e)
        typ = self._opening_type(el)
        u = None
        if isinstance(typ, DoorType):
            u = typ.ud or typ.uw
        elif isinstance(typ, WinType):
            u = typ.uw
        if typ is not None:
            t = self.type_of("IfcDoorType" if o.kind == "door" else "IfcWindowType", typ.id, None)
            ifcopenshell.api.type.assign_type(
                self.f, related_objects=[e], relating_type=t, should_map_representations=False
            )
        pset = "Pset_DoorCommon" if o.kind == "door" else "Pset_WindowCommon"
        self.pset(
            e,
            pset,
            {
                "IsExternal": w.ext is not None,
                "ThermalTransmittance": u,
                "Status": STATUS[o.status],
            },
        )
        self.contained[w.level].append(e)

    def _opening_type(self, el: Any) -> DoorType | WinType | None:
        m = self.d.model
        typ = getattr(el, "type", None)
        if typ is not None and typ.id in m:
            t = m[typ.id]
            return t if isinstance(t, DoorType | WinType) else None
        cat = "door" if isinstance(el, Door) else "win" if isinstance(el, Win) else None
        for t in m.of_kind("type", cat):
            if getattr(t, "default", False) and isinstance(t, DoorType | WinType):
                return t
        return None

    def slab(self, key: str) -> None:
        sl = self.g.slabs[key]
        el = self.d.model[key]
        lv = self.g.levels[sl.level]
        lowest = lv.below is None
        e = self.entity("IfcSlab", key, key, "BASESLAB" if lowest else "FLOOR")
        self._common(e, key, el.label)
        e.ObjectPlacement = self.placement(self.storeys[sl.level].ObjectPlacement)
        top = sl.top + sl.layers.before_core() - lv.z
        items = [self.extrude(p, top - sl.layers.total, sl.layers.total) for p in polys(sl.net)]
        e.Representation = self.body(items, "SweptSolid")
        t = self.type_of("IfcSlabType", el.type.id, sl.layers, "BASESLAB" if lowest else "FLOOR")
        ifcopenshell.api.type.assign_type(
            self.f, related_objects=[e], relating_type=t, should_map_representations=False
        )
        self.pset(
            e,
            "Pset_SlabCommon",
            {"IsExternal": lowest, "LoadBearing": True, "Status": STATUS[sl.status]},
        )
        self.contained[sl.level].append(e)

    def roof_pieces(self, level: str) -> list[tuple[int, Lin, Polygon]]:
        """The planes of all roofs of a storey, cut against each other where they meet."""
        if level not in self._roof_pieces:
            roofs = self.g.roofs_on(level)
            parts = [Part(rf.over, tuple(rf.planes)) for rf in roofs]
            x0, y0, x1, y1 = shapely.union_all([rf.over for rf in roofs]).bounds
            self._roof_pieces[level] = union_pieces(parts, shapely.box(x0, y0, x1, y1))
        return self._roof_pieces[level]

    def roof(self, rf: RoofGeo) -> None:
        el = self.d.model[rf.id]
        assert isinstance(el, Roof)
        lv = self.g.levels[rf.level]
        shape = roof_type(el)
        roof = self.entity("IfcRoof", rf.id, rf.id, shape)
        self._common(roof, rf.id, el.label)
        roof.ObjectPlacement = self.placement(self.storeys[rf.level].ObjectPlacement)
        parts: list[Entity] = []
        if rf.status == "demolish":
            pieces = union_pieces([Part(rf.over, tuple(rf.planes))], rf.over)
        else:
            index = [r.id for r in self.g.roofs_on(rf.level)].index(rf.id)
            pieces = [p for p in self.roof_pieces(rf.level) if p[0] == index]
        for i, (_, plane, poly) in enumerate(pieces):
            s = self.entity("IfcSlab", f"{rf.id}/{i}", f"{rf.id}.{i + 1}", "ROOF")
            s.ObjectPlacement = self.placement(roof.ObjectPlacement)
            rel = Lin(plane.a, plane.b, plane.c - lv.z)
            bottom, top = rel.minus(rf.lining_of(plane)), rel.minus(-rf.skin_of(plane))
            s.Representation = self.body([self.prism(poly, bottom, top)], "Tessellation")
            parts.append(s)
        if parts:
            ifcopenshell.api.aggregate.assign_object(self.f, products=parts, relating_object=roof)
        rt = el.type.id
        layers = getattr(self.d.model[rt], "layers", None)
        if layers is not None:
            t = self.type_of("IfcRoofType", rt, layers, shape)
            ifcopenshell.api.type.assign_type(
                self.f, related_objects=[roof], relating_type=t, should_map_representations=False
            )
        self.pset(roof, "Pset_RoofCommon", {"IsExternal": True, "Status": STATUS[rf.status]})
        self.contained[rf.level].append(roof)

    def prism(self, poly: Polygon, bottom: Lin, top: Lin) -> Entity:
        """A closed triangulated solid between two planes over a polygon."""
        p = orient(poly, 1.0)
        rings = [[(c[0], c[1]) for c in list(r.coords)[:-1]] for r in (p.exterior, *p.interiors)]
        index: dict[tuple[float, float], int] = {}
        coords: list[tuple[float, float, float]] = []
        for ring in rings:
            for x, y in ring:
                index[(x, y)] = len(coords) // 2 + 1
                coords += [(x, y, bottom(x, y)), (x, y, top(x, y))]
        tri: list[tuple[int, int, int]] = []
        for t in shapely.constrained_delaunay_triangles(p).geoms:
            assert isinstance(t, Polygon)
            corners = [(c[0], c[1]) for c in list(orient(t, 1.0).exterior.coords)[:3]]
            a, b, c = (index[v] for v in corners)
            tri.append((2 * a, 2 * b, 2 * c))  # top, facing up
            tri.append((2 * a - 1, 2 * c - 1, 2 * b - 1))  # bottom, facing down
        for ring in rings:
            for i, a in enumerate(ring):
                b = ring[(i + 1) % len(ring)]
                ia, ib = index[a], index[b]
                tri.append((2 * ia - 1, 2 * ib - 1, 2 * ib))
                tri.append((2 * ia - 1, 2 * ib, 2 * ia))
        pl = self.f.createIfcCartesianPointList3D([[float(c) for c in xyz] for xyz in coords])
        return self.f.createIfcTriangulatedFaceSet(pl, None, True, [list(t) for t in tri], None)

    def stair(self, key: str) -> None:
        s = self.g.stairs[key]
        el = self.d.model[key]
        kinds = {
            ("straight", False): "STRAIGHT_RUN_STAIR",
            ("l", False): "QUARTER_TURN_STAIR",
            ("l", True): "QUARTER_WINDING_STAIR",
            ("u", False): "HALF_TURN_STAIR",
        }
        stair = self.entity("IfcStair", key, key, kinds[(s.shape, s.winders > 0)])
        self._common(stair, key, el.label)
        place = self.storeys[s.level].ObjectPlacement
        stair.ObjectPlacement = self.placement(place)
        children: list[Entity] = []
        for i, part in enumerate(p for p in s.parts if p.kind == "flight"):
            children.append(self.flight(stair, s, part, i))
        for part in (p for p in s.parts if p.kind == "landing"):
            slab = self.entity("IfcSlab", f"{key}/landing", f"{key}.landing", "LANDING")
            slab.ObjectPlacement = self.placement(stair.ObjectPlacement)
            slab.Representation = self.body([self.tread(s, part)], "SweptSolid")
            children.append(slab)
        winders = [p for p in s.parts if p.kind == "winder"]
        if winders:
            wf = self.entity("IfcStairFlight", f"{key}/winders", f"{key}.winders", "WINDER")
            wf.ObjectPlacement = self.placement(stair.ObjectPlacement)
            wf.NumberOfRisers = len(winders)
            wf.RiserHeight = float(s.riser)
            wf.Representation = self.body([self.tread(s, p) for p in winders], "SweptSolid")
            children.append(wf)
        ifcopenshell.api.aggregate.assign_object(self.f, products=children, relating_object=stair)
        self.pset(
            stair,
            "Pset_StairCommon",
            {
                "NumberOfRiser": s.n,
                "NumberOfTreads": s.n - 1,
                "RiserHeight": float(s.riser),
                "TreadLength": float(s.tread),
                "Status": STATUS[s.status],
            },
        )
        self.contained[s.level].append(stair)

    def tread(self, s: StairGeo, part: StairPartGeo) -> Entity:
        """A landing or a winder: a slab 0.2 thick whose top is at the tread's height."""
        top = part.tread * s.riser
        return self.extrude(part.poly, top - 0.2, 0.2)

    def flight(self, stair: Entity, s: StairGeo, part: StairPartGeo, i: int) -> Entity:
        """One straight flight: the stepped profile extruded across the width."""
        flight = self.entity("IfcStairFlight", f"{s.id}/flight{i}", f"{s.id}.{i + 1}", "STRAIGHT")
        flight.ObjectPlacement = self.placement(stair.ObjectPlacement)
        n, riser, tread = part.risers, s.riser, s.tread
        flight.NumberOfRisers = n
        flight.NumberOfTreads = n - 1
        flight.RiserHeight = float(riser)
        flight.TreadLength = float(tread)
        cx, cy = part.climb
        across = (cy, -cx)
        origin = (part.start[0] - across[0] * s.w / 2, part.start[1] - across[1] * s.w / 2)
        prof: list[tuple[float, float]] = [(0.0, 0.0)]
        for k in range(n):
            u = k * tread
            prof.append((u, (k + 1) * riser))
            if k < n - 1:
                prof.append((u + tread, (k + 1) * riser))
        prof.append(((n - 1) * tread, n * riser - 0.2))
        prof.append((0.3, 0.0))
        profile = self.f.createIfcArbitraryClosedProfileDef("AREA", None, self.ring(prof))
        pos = self.axis(
            (origin[0], origin[1], part.tread * riser),
            (across[0], across[1], 0.0),
            (cx, cy, 0.0),
        )
        solid = self.f.createIfcExtrudedAreaSolid(profile, pos, self.dir(0, 0, 1), float(s.w))
        flight.Representation = self.body([solid], "SweptSolid")
        return flight

    def space(self, key: str) -> None:
        rg = self.g.rooms[key]
        el = self.d.model[key]
        assert isinstance(el, Room)
        e = self.entity("IfcSpace", key, key, "INTERNAL")
        e.LongName = el.label or el.use
        e.ObjectPlacement = self.placement(self.storeys[rg.level].ObjectPlacement)
        items: list[Entity] = []
        flat = True
        for plane, piece in rg.ceiling.pieces(rg.fin):
            for poly in polys(halfplane(piece, plane.minus(0.01))):
                if plane.flat:
                    items.append(self.extrude(poly, 0.0, plane.c))
                else:
                    flat = False
                    items.append(self.prism(poly, Lin(0.0, 0.0, 0.0), plane))
        if items:
            e.Representation = self.body(items, "SweptSolid" if flat else "Tessellation")
        self.pset(
            e,
            "Pset_SpaceCommon",
            {"Reference": el.use, "IsExternal": False},
        )
        qto = ifcopenshell.api.pset.add_qto(self.f, product=e, name="Qto_SpaceBaseQuantities")
        quantities: dict[str, Any] = {
            "NetFloorArea": float(rg.area_fin),
            "GrossFloorArea": float(rg.area),
        }
        if rg.height is not None:
            quantities["Height"] = float(rg.height)
        if rg.volume is not None:
            quantities["NetVolume"] = float(rg.volume)
        ifcopenshell.api.pset.edit_qto(self.f, qto=qto, properties=quantities)
        ifcopenshell.api.aggregate.assign_object(
            self.f, products=[e], relating_object=self.storeys[rg.level]
        )


def export_ifc(d: Derived, path: Path) -> dict[str, int]:
    return Writer(d).write(path)

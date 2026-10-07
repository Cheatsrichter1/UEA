"""Architecture element kinds (`arch.uea`).

Datums (docs/decisions/0012-datums-and-positions.md): plan positions are the faces of a
type's core layer; heights count from the storey's FFL; openings store their structural size.
"""

from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import BeforeValidator, model_validator

from uea.core.schema import Element, F, Status, spec
from uea.core.values import Anchor, Layers, Point, Ref, Size, Span, parse_place


def _place(v: Any) -> Any:
    return parse_place(v) if isinstance(v, str) else v


Place = Annotated[Anchor | Span | None, BeforeValidator(_place)]


def _position_first(el: Element, x: object, y: object) -> tuple[str, ...]:
    """Write the position before the span: y=S+ x=W..E."""
    rest = tuple(k for k in spec(type(el)).kv if k not in ("x", "y"))
    return ("y", "x", *rest) if isinstance(y, Anchor) else ("x", "y", *rest)


def _core_check(layers: Layers) -> None:
    cores = [i for i, x in enumerate(layers.items) if x.core]
    if not cores:
        raise ValueError("layers need a core layer marked with *, e.g. *brick:0.365")
    if cores != list(range(cores[0], cores[-1] + 1)):
        raise ValueError("core layers (*) must be next to each other")


# ---------- types ----------


class _ArchType(Element):
    kind: ClassVar[str] = "type"
    pack: ClassVar[str] = "arch"


class _Layered(_ArchType):
    layers: Annotated[Layers, F("material:thickness in m, comma-separated; * marks the core")]

    @model_validator(mode="after")
    def _check(self) -> Self:
        _core_check(self.layers)
        return self


class WallType(_Layered):
    category: ClassVar[str | None] = "wall"
    doc: ClassVar[str] = (
        "Wall build-up, inside to outside (interior walls: -x/-y face first). The core layer"
        " (*) is what wall positions refer to: layers=plaster:0.015,*brick:0.365,render:0.02"
    )


class SlabType(_Layered):
    category: ClassVar[str | None] = "slab"
    doc: ClassVar[str] = (
        "Slab build-up, top to bottom. The core top is the storey's SSL:"
        " layers=*concrete:0.25,xps:0.14"
    )


class FloorType(_ArchType):
    category: ClassVar[str | None] = "floor"
    doc: ClassVar[str] = (
        "Floor build-up on a slab, top to bottom (Fußbodenaufbau, the level's fb):"
        " layers=parquet:0.015,screed:0.065,eps:0.07"
    )
    layers: Annotated[Layers, F("material:thickness in m, comma-separated")]


class RoofType(_Layered):
    category: ClassVar[str | None] = "roof"
    doc: ClassVar[str] = (
        "Roof build-up, outside to inside. The core is the rafter layer:"
        " layers=tiles:0.04,battens:0.07,*rafters:0.18"
    )


class WinType(_ArchType):
    category: ClassVar[str | None] = "win"
    doc: ClassVar[str] = "Window type. A window without type= uses the type marked default."
    uw: Annotated[float | None, F("Uw", unit="W/(m²K)")] = None
    default: Annotated[bool, F("used by windows without type=", flag=True)] = False


class DoorType(_ArchType):
    category: ClassVar[str | None] = "door"
    doc: ClassVar[str] = "Door type. A door without type= uses the type marked default."
    ud: Annotated[float | None, F("Ud", unit="W/(m²K)")] = None
    uw: Annotated[float | None, F("Uw of a glazed door", unit="W/(m²K)")] = None
    default: Annotated[bool, F("used by doors without type=", flag=True)] = False


# ---------- elements ----------


class Wall(Element):
    kind: ClassVar[str] = "wall"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "w"
    positional: ClassVar[tuple[str, ...]] = ("level", "type")
    doc: ClassVar[str] = (
        "A straight wall. One of x=/y= is its position (a core face, e.g. y=S+ or"
        " x=w4+2.26), the other its span (x=W..E, y=w1..w3). on= stacks it on a wall below."
    )
    level: Annotated[Ref, F("storey", targets=("level",))]
    type: Annotated[Ref, F("wall type", targets=("type:wall",))]
    x: Annotated[Place, F("x position (anchor±d) or span (a..b)", unit="m")] = None
    y: Annotated[Place, F("y position (anchor±d) or span (a..b)", unit="m")] = None
    on: Annotated[Ref | None, F("same footprint as this wall", targets=("wall",))] = None
    top: Annotated[Ref | None, F("roof that cuts the wall's top", targets=("roof",))] = None
    h: Annotated[float | None, F("height above the SSL, if not up to the slab above", unit="m")] = (
        None
    )
    lb: Annotated[bool, F("load-bearing", flag=True)] = False
    flip: Annotated[bool, F("reverse the layer order", flag=True)] = False
    status: Status = "new"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.on is not None:
            if self.x is not None or self.y is not None:
                raise ValueError("on= gives the footprint; leave out x= and y=")
            return self
        ok = (isinstance(self.x, Anchor) and isinstance(self.y, Span)) or (
            isinstance(self.y, Anchor) and isinstance(self.x, Span)
        )
        if not ok:
            raise ValueError(
                "give a position on one axis and a span on the other, e.g. y=S+ x=W..E,"
                " or on=<wall>"
            )
        if self.h is not None and self.h <= 0:
            raise ValueError("h must be larger than 0")
        return self

    def kv_order(self) -> tuple[str, ...]:
        return _position_first(self, self.x, self.y)


class _Opening(Element):
    pack: ClassVar[str] = "arch"
    positional: ClassVar[tuple[str, ...]] = ("host", "size")
    size: Annotated[Size, F("structural opening width x height (Rohbaurichtmaß)", unit="m")]
    x: Annotated[Anchor | None, F("edge position along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("edge position along a wall running along y", unit="m")] = None

    @model_validator(mode="after")
    def _one_axis(self) -> Self:
        if (self.x is None) == (self.y is None):
            raise ValueError("give its position along the host wall with x= or y=")
        return self

    @property
    def along(self) -> Anchor:
        a = self.x if self.x is not None else self.y
        assert a is not None
        return a


class Door(_Opening):
    kind: ClassVar[str] = "door"
    prefix: ClassVar[str | None] = "d"
    doc: ClassVar[str] = (
        "A door in a wall. Stands on the FFL. into= is the room it opens into; hand= its handing"
        " (l or r as DIN links/rechts, seen from that room)."
    )
    host: Annotated[Ref, F("wall", targets=("wall",))]
    sill: Annotated[float | None, F("bottom above the FFL, if not on the floor", unit="m")] = None
    into: Annotated[Ref | None, F("room the leaf opens into", targets=("room",))] = None
    hand: Annotated[Literal["l", "r"] | None, F("handing: l or r, seen from the into room")] = None
    type: Annotated[
        Ref | None, F("door type; default type if left out", targets=("type:door",))
    ] = None
    status: Status = "new"


class Win(_Opening):
    kind: ClassVar[str] = "win"
    prefix: ClassVar[str | None] = "f"
    doc: ClassVar[str] = (
        "A window in a wall. It hangs from the storey's head height (head=); sill= only if it"
        " deviates."
    )
    host: Annotated[Ref, F("wall", targets=("wall",))]
    sill: Annotated[float | None, F("sill height above the FFL, if not from head", unit="m")] = None
    type: Annotated[
        Ref | None, F("window type; default type if left out", targets=("type:win",))
    ] = None
    status: Status = "new"


class Niche(_Opening):
    kind: ClassVar[str] = "niche"
    prefix: ClassVar[str | None] = "ni"
    doc: ClassVar[str] = "A niche in one face of a wall (host w5.n), d deep."
    host: Annotated[Ref, F("wall face, e.g. w5.n", targets=("wall",))]
    sill: Annotated[float, F("bottom above the FFL", unit="m")] = 0.0
    d: Annotated[float, F("depth into the wall", unit="m")]
    status: Status = "new"

    @model_validator(mode="after")
    def _face(self) -> Self:
        if self.host.face is None or self.host.face == "c":
            raise ValueError("host needs a face: w5.n, w5.s, w5.e or w5.w")
        if self.d <= 0:
            raise ValueError("d must be larger than 0")
        return self


class Slab(Element):
    kind: ClassVar[str] = "slab"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "sl"
    positional: ClassVar[tuple[str, ...]] = ("level", "type")
    doc: ClassVar[str] = (
        "The slab under a storey; its top is the storey's SSL. Its outline comes from"
        " the walls below it (the storey's own walls for the lowest slab)."
    )
    level: Annotated[Ref, F("storey it carries", targets=("level",))]
    type: Annotated[Ref, F("slab type", targets=("type:slab",))]
    status: Status = "new"


class Void(Element):
    kind: ClassVar[str] = "void"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "v"
    positional: ClassVar[tuple[str, ...]] = ("slab",)
    doc: ClassVar[str] = (
        "An opening in a slab: over a stair (over=st1) or given by x= and y= spans."
    )
    slab: Annotated[Ref, F("slab", targets=("slab",))]
    over: Annotated[Ref | None, F("stair whose footprint it opens", targets=("stair",))] = None
    x: Annotated[Span | None, F("x span", unit="m")] = None
    y: Annotated[Span | None, F("y span", unit="m")] = None
    status: Status = "new"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.over is None) == (self.x is None or self.y is None):
            raise ValueError("give over=<stair> or both x= and y= spans")
        return self


class Roof(Element):
    kind: ClassVar[str] = "roof"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "rf"
    positional: ClassVar[tuple[str, ...]] = ("level", "type", "shape")
    doc: ClassVar[str] = (
        "A roof over a storey's outline. gable (Satteldach, ridge=x|y), shed (Pultdach, up="
        " the side it rises to), hip (Walmdach). knee: underside of the rafters at the outer"
        " face of the eaves wall, above the storey's SSL (Kniestock). Derived: eaves height"
        " (top of the roof skin above the outer wall face) and ridge height."
    )
    level: Annotated[Ref, F("storey the roof sits on", targets=("level",))]
    type: Annotated[Ref, F("roof type", targets=("type:roof",))]
    shape: Annotated[Literal["gable", "shed", "hip"], F("gable, shed or hip")]
    ridge: Annotated[Literal["x", "y"] | None, F("ridge direction of a gable roof")] = None
    up: Annotated[Literal["n", "s", "e", "w"] | None, F("side a shed roof rises to")] = None
    pitch: Annotated[float, F("roof pitch", unit="°")]
    knee: Annotated[
        float, F("rafter underside at the eaves wall's outer face, above the SSL", unit="m")
    ] = 0.0
    eave: Annotated[float, F("overhang at the eaves", unit="m")] = 0.0
    verge: Annotated[float, F("overhang at the verge", unit="m")] = 0.0
    status: Status = "new"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not 0 < self.pitch < 75:
            raise ValueError("pitch must be between 0 and 75 degrees")
        if self.shape == "gable" and self.ridge is None:
            raise ValueError("a gable roof needs ridge=x or ridge=y")
        if self.shape == "shed" and self.up is None:
            raise ValueError("a shed roof needs up=n|s|e|w, the side it rises to")
        if self.shape != "gable" and self.ridge is not None:
            raise ValueError("ridge= is only for gable roofs")
        if self.shape != "shed" and self.up is not None:
            raise ValueError("up= is only for shed roofs")
        return self


class Stair(Element):
    kind: ClassVar[str] = "stair"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "st"
    positional: ClassVar[tuple[str, ...]] = ("level", "to")
    doc: ClassVar[str] = (
        "A straight single-flight stair from one storey to another. x=/y= place its footprint"
        " like a wall; up= is the direction it climbs; n risers, run (n-1) x tread."
    )
    level: Annotated[Ref, F("storey it starts on", targets=("level",))]
    to: Annotated[Ref, F("storey it arrives at", targets=("level",))]
    x: Annotated[Anchor, F("x position of the footprint", unit="m")]
    y: Annotated[Anchor, F("y position of the footprint", unit="m")]
    up: Annotated[Literal["n", "s", "e", "w"], F("direction it climbs")]
    w: Annotated[float, F("width", unit="m")]
    n: Annotated[int, F("number of risers")]
    tread: Annotated[float, F("tread depth", unit="m")]
    status: Status = "new"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.n < 2:
            raise ValueError("n must be at least 2")
        if self.w <= 0 or self.tread <= 0:
            raise ValueError("w and tread must be larger than 0")
        return self


class Sep(Element):
    kind: ClassVar[str] = "sep"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "rs"
    positional: ClassVar[tuple[str, ...]] = ("level",)
    doc: ClassVar[str] = (
        "A room separation line without a wall (open kitchen): a position on one axis, a span"
        " on the other."
    )
    level: Annotated[Ref, F("storey", targets=("level",))]
    x: Annotated[Place, F("x position or span", unit="m")] = None
    y: Annotated[Place, F("y position or span", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        ok = (isinstance(self.x, Anchor) and isinstance(self.y, Span)) or (
            isinstance(self.y, Anchor) and isinstance(self.x, Span)
        )
        if not ok:
            raise ValueError("give a position on one axis and a span on the other")
        return self

    def kv_order(self) -> tuple[str, ...]:
        return _position_first(self, self.x, self.y)


RoomUse = Literal[
    "living",
    "dining",
    "kitchen",
    "bedroom",
    "office",
    "bath",
    "wc",
    "hall",
    "utility",
    "storage",
    "laundry",
    "technical",
    "cellar",
    "attic",
    "garage",
    "other",
]


class Room(Element):
    kind: ClassVar[str] = "room"
    pack: ClassVar[str] = "arch"
    prefix: ClassVar[str | None] = "r"
    positional: ClassVar[tuple[str, ...]] = ("level", "use")
    doc: ClassVar[str] = (
        "A room: the region around the seed point at= bounded by walls and separators."
    )
    level: Annotated[Ref, F("storey", targets=("level",))]
    use: Annotated[RoomUse, F("use; decides e.g. whether it counts as Wohnfläche")]
    at: Annotated[Point, F("seed point inside the room", unit="m")]
    floor: Annotated[Ref | None, F("floor type", targets=("type:floor",))] = None
    tile: Annotated[float | None, F("wall tiling height above the FFL", unit="m")] = None


TYPES: tuple[type[Element], ...] = (WallType, SlabType, FloorType, RoofType, WinType, DoorType)
KINDS: tuple[type[Element], ...] = (
    *TYPES,
    Wall,
    Door,
    Win,
    Niche,
    Slab,
    Void,
    Roof,
    Stair,
    Sep,
    Room,
)

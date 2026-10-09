"""Things mounted on a wall or in a room: luminaires and electrical devices (decision 0025).

A device sits on one face of a wall, a distance along it, at a height above the storey's FFL
(the centre of the device). A luminaire or smoke detector may hang in a room instead, at a point.
Positions are anchors like everywhere else, and they may anchor on another mounted thing:
`x=sw2+0.071` is one frame width past the switch sw2.
"""

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import model_validator
from shapely.geometry import Point as SPoint

from uea.core.schema import Element, F
from uea.core.values import Anchor, Ref
from uea.derive import Derived, GeoError, Unresolved
from uea.packs.arch.geometry import Axis, Resolver

MOUNT_KINDS = frozenset({"lum", "sock", "conn", "switch", "data", "board"})
"""Kinds with a position along a wall that other positions may anchor on."""
FRAME = 0.071
"""Width of one frame of a device (a socket or switch), in m."""
DEPTH_INTO_ROOM = 0.05
"""A wall device belongs to the room 5 cm in front of its face."""


class WallMounted(Element):
    """Base of the electrical devices on a wall."""

    default_z: ClassVar[float | None] = None
    """The height above the FFL when z= is left out; none: z= is required."""

    host: Annotated[Ref, F("wall; for an interior wall its face too: w5.s", targets=("wall",))]
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[
        Anchor | None, F("centre along a wall in any direction, from its start a", unit="m")
    ] = None
    z: Annotated[float | None, F("height of its centre above the FFL", unit="m")] = None

    @model_validator(mode="after")
    def _one_axis(self) -> Self:
        if sum(v is not None for v in (self.x, self.y, self.s)) != 1:
            raise ValueError(
                "give its position along the host wall with x= or y= (wall along that axis),"
                " or s= (wall in any direction)"
            )
        return self

    @property
    def along(self) -> Anchor:
        a = self.x or self.y or self.s
        assert a is not None
        return a

    @property
    def width(self) -> float:
        return FRAME


@dataclass
class Mounted:
    id: str
    kind: str
    level: str
    point: tuple[float, float]
    """On a wall: the plan point on its face. In a room: where it hangs."""
    z: float
    """Absolute height of its centre."""
    room: str | None
    wall: str | None = None
    face: Literal["lo", "hi"] | None = None
    letter: str | None = None
    """The face as the arch format writes it: n, s, e, w, l or r."""
    axis: Axis = "x"
    s: float = 0.0
    """Position along the wall, as the openings give theirs."""
    width: float = FRAME


class Mounts:
    """Places everything that is mounted, memoized in `d.mounts`."""

    def __init__(self, d: Derived) -> None:
        self.d = d
        self.m = d.model
        self.g = d.arch
        self.arch = Resolver(d, reuse=True)

    def place(self, key: str) -> Mounted:
        return self.d.resolve(key, self.d.mounts, lambda: self._place(key))

    def _place(self, key: str) -> Mounted:
        el: Any = self.m[key]
        host = self.m.get(el.host.id)
        if host is None or host.kind not in ("wall", "room"):
            raise Unresolved(el.host.id, missing=True)
        if host.kind == "room":
            return self._in_room(key, el)
        return self._on_wall(key, el)

    # ---------- anchors ----------

    def point(self, a: Anchor, axis: Axis) -> float:
        """A position along a wall; it may anchor on another mounted thing."""
        if a.ref is not None:
            other = self.m.get(a.ref)
            if other is not None and other.kind in MOUNT_KINDS:
                at = self.place(a.ref)
                if at.wall is None or at.axis != axis:
                    raise GeoError(
                        f"{axis}={a.fmt()}: {a.ref} does not lie along {axis}",
                        f"anchor on something that stands on a wall running along {axis}",
                    )
                a = Anchor(None, None, a.sign, a.dist, at.s)
        return self.arch.point(a, axis)

    # ---------- on a wall ----------

    def _on_wall(self, key: str, el: Any) -> Mounted:
        wall = self.g.walls.get(el.host.id)
        if wall is None:
            raise Unresolved(el.host.id, missing=True)
        cls = type(self.m[key])
        code = f"E-{cls.pack.upper()}-002"
        lo_face, hi_face = wall.faces
        if el.host.face is None:
            if wall.ext is None:
                raise GeoError(
                    f"{key} is on {wall.id}, which has a room on each side: say which face",
                    f"host {wall.id}.{hi_face} or {wall.id}.{lo_face}",
                    code,
                )
            side: Literal["lo", "hi"] = "hi" if wall.ext == "lo" else "lo"
        elif el.host.face in (hi_face, lo_face):
            side = "hi" if el.host.face == hi_face else "lo"
        else:
            raise GeoError(
                f"host {el.host.fmt()}: {wall.id} runs along {wall.along}; its faces are"
                f" .{hi_face} and .{lo_face}",
                None,
                code,
            )
        axis = wall.along
        given: Axis | None = "x" if el.x is not None else "y" if el.y is not None else None
        if given is None and el.s is not None:
            given = "s"
        if given is None:
            raise GeoError(
                f"{key} is on {wall.id}: give its position along it with {axis}=",
                f"{axis}=<anchor>, e.g. {axis}={wall.id}+1",
            )
        anchor: Anchor | None = el.x or el.y or el.s
        assert anchor is not None
        if given != axis:
            where = (
                "at an angle: give s=, the distance from its start a"
                if axis == "s"
                else (f"along {axis}: give {axis}=")
            )
            raise GeoError(
                f"{key} is on {wall.id}, which runs {where}, not {given}=",
                f"~ {key} {given}= {axis}={anchor.fmt()}",
            )
        s = self.point(anchor, axis)
        zrel: float | None = el.z if el.z is not None else getattr(cls, "default_z", None)
        if zrel is None:
            raise GeoError(f"{key} needs a height above the FFL", f"~ {key} z=1.2")
        lv = self.g.levels[wall.level]
        c = wall.hi if side == "hi" else wall.lo
        x, y = wall.plan_point(s, c)
        sign = 1.0 if side == "hi" else -1.0
        nx, ny = wall.n
        room = self.g.room_at(
            wall.level, x + sign * nx * DEPTH_INTO_ROOM, y + sign * ny * DEPTH_INTO_ROOM
        )
        letter = hi_face if side == "hi" else lo_face
        width = float(getattr(el, "width", FRAME))
        return Mounted(
            key, el.kind, wall.level, (x, y), lv.z + zrel, room, wall.id, side, letter, axis, s,
            width,
        )  # fmt: skip

    # ---------- in a room ----------

    def _in_room(self, key: str, el: Any) -> Mounted:
        rg = self.g.rooms.get(el.host.id)
        if rg is None:
            raise Unresolved(el.host.id, missing=True)
        if any(getattr(el, a, None) is not None for a in ("x", "y", "s")):
            raise GeoError(
                f"{key} is in room {rg.id}: place it with at=, not x=/y=/s=",
                f"~ {key} x= y= s= at=<x>,<y>",
            )
        at = getattr(el, "at", None)
        if at is not None:
            x, y = self.arch.point(at.x, "x"), self.arch.point(at.y, "y")
        else:
            c = rg.fin.centroid
            p = c if rg.fin.contains(c) else rg.fin.representative_point()
            x, y = p.x, p.y
        lv = self.g.levels[rg.level]
        if getattr(el, "z", None) is not None:
            z = lv.z + float(el.z)
        else:
            h = self.ceiling(rg.id, x, y)
            if h is None:
                raise GeoError(f"{key} has no ceiling to hang from in {rg.id}", f"~ {key} z=2.5")
            z = lv.z + h
        return Mounted(
            key, el.kind, rg.level, (x, y), z, rg.id, width=float(getattr(el, "width", 0.2))
        )

    def ceiling(self, room: str, x: float, y: float) -> float | None:
        """The clear height of a room above its FFL at a point."""
        rg = self.g.rooms[room]
        at = SPoint(x, y)
        for f, piece in rg.ceiling.pieces(rg.fin):
            if piece.buffer(1e-6).contains(at):
                return f(x, y)
        return None

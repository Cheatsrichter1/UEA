"""Electrical element kinds (`elec.uea`): boards, RCDs, circuits, devices and feeds.

Devices stand on a wall (`sock s4 w4 c4 y=f2+0.3 z=1.15 n=2`); positions are anchors like
everywhere, heights are above the FFL and name the centre of the device (decision 0025).
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Point, Ref
from uea.packs.elec.values import Breaker, Cable, Controls, Rating
from uea.packs.mount import FRAME, WallMounted


class Board(WallMounted):
    kind: ClassVar[str] = "board"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "b"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A distribution board on a wall: board b1 w6.w y=w3-0.6 z=1.4 main=SLS-E35 meters=1."
        " media: a media distribution board (Medienverteiler) for the data outlets."
    )
    main: Annotated[str | None, F("main switch, e.g. SLS-E35")] = None
    spd: Annotated[str | None, F("surge protection, e.g. T1+T2")] = None
    meters: Annotated[int, F("electricity meters")] = 0
    media: Annotated[bool, F("a media distribution board", flag=True)] = False

    @property
    def width(self) -> float:
        return 0.5


class Rcd(Element):
    kind: ClassVar[str] = "rcd"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "fi"
    positional: ClassVar[tuple[str, ...]] = ("board", "rating", "type")
    doc: ClassVar[str] = (
        "A residual current device (Fehlerstromschutzschalter) in a board: rcd fi1 b1 40/0.03 A,"
        " rated A / residual A, then its type (AC, A, F or B)."
    )
    board: Annotated[Ref, F("distribution board", targets=("board",))]
    rating: Annotated[Rating, F("rated current / residual current", unit="A")]
    type: Annotated[Literal["AC", "A", "F", "B"], F("RCD type")]


class Circ(Element):
    kind: ClassVar[str] = "circ"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "c"
    positional: ClassVar[tuple[str, ...]] = ("rcd", "cable", "breaker")
    doc: ClassVar[str] = (
        'A circuit behind an RCD: circ c1 fi1 NYM-J5x2.5 B16 p=3 "Küche Herd". p= phases (1 or'
        " 3). Its connected load is the luminaires, connections and feeds on it."
    )
    rcd: Annotated[Ref, F("RCD that protects it", targets=("rcd",))]
    cable: Annotated[Cable, F("cable designation, type, cores x mm²")]
    breaker: Annotated[Breaker, F("circuit breaker: characteristic and rated current")]
    p: Annotated[int, F("phases, 1 or 3")] = 1

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.p not in (1, 3):
            raise ValueError("p must be 1 or 3")
        if self.p == 3 and self.cable.cores < 4:
            raise ValueError(
                f"a three-phase circuit needs a cable with 4 or 5 cores, not {self.cable.fmt()}"
            )
        return self


class Sock(WallMounted):
    kind: ClassVar[str] = "sock"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "s"
    positional: ClassVar[tuple[str, ...]] = ("host", "circuit")
    default_z: ClassVar[float | None] = 0.3
    doc: ClassVar[str] = (
        "A socket box on a wall: sock s4 w4 c4 y=f2+0.3 z=1.15 n=2. z= is 0.3 if left out;"
        " n= the outlets in its frame."
    )
    circuit: Annotated[Ref, F("circuit", targets=("circ",))]
    n: Annotated[int, F("outlets in the frame")] = 1

    @model_validator(mode="after")
    def _count(self) -> Self:
        if not 1 <= self.n <= 6:
            raise ValueError("n must be between 1 and 6")
        return self

    @property
    def width(self) -> float:
        return FRAME * self.n


class Conn(WallMounted):
    kind: ClassVar[str] = "conn"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "a"
    positional: ClassVar[tuple[str, ...]] = ("host", "circuit")
    default_z: ClassVar[float | None] = 0.3
    doc: ClassVar[str] = (
        'A fixed connection (Anschluss) for an appliance: conn a1 w4 c1 y=w1+0.9 z=0.6 "Herd".'
        " w= its power, counted in the circuit's load."
    )
    circuit: Annotated[Ref, F("circuit", targets=("circ",))]
    w: Annotated[float | None, F("connected power", unit="W")] = None


class Switch(WallMounted):
    kind: ClassVar[str] = "switch"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "sw"
    positional: ClassVar[tuple[str, ...]] = ("host", "circuit")
    default_z: ClassVar[float | None] = 1.05
    doc: ClassVar[str] = (
        "A light switch: switch sw2 w5.s c10 x=d2+0.15 ctl=l2,l3. ctl= the luminaires it"
        " controls: , separates channels, + joins luminaires of one channel. A luminaire with two"
        " switches is a two-way circuit, with three an intermediate one. dim: a dimmer."
    )
    circuit: Annotated[Ref, F("circuit", targets=("circ",))]
    ctl: Annotated[Controls, F("luminaires it controls: l1 or l2,l3 or l15+l16")]
    dim: Annotated[bool, F("a dimmer", flag=True)] = False

    @property
    def width(self) -> float:
        return FRAME * len(self.ctl.groups)


class Data(WallMounted):
    kind: ClassVar[str] = "data"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "dt"
    positional: ClassVar[tuple[str, ...]] = ("host", "board")
    default_z: ClassVar[float | None] = 0.3
    doc: ClassVar[str] = (
        "A data outlet (network, antenna) cabled to a distribution board: data dt1 w2 b2"
        " y=w5-0.75 n=2."
    )
    board: Annotated[Ref, F("distribution board it is cabled to", targets=("board",))]
    n: Annotated[int, F("ports in the frame")] = 1

    @model_validator(mode="after")
    def _count(self) -> Self:
        if not 1 <= self.n <= 6:
            raise ValueError("n must be between 1 and 6")
        return self

    @property
    def width(self) -> float:
        return FRAME * self.n


class Smoke(Element):
    kind: ClassVar[str] = "smoke"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "rm"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "A smoke alarm (Rauchwarnmelder) in a room, at the ceiling: smoke rm1 r5. at= a point."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    at: Annotated[Point | None, F("point in the room, x,y; default the middle", unit="m")] = None
    z: Annotated[float | None, F("height above the FFL; default the ceiling", unit="m")] = None


class Feed(Element):
    kind: ClassVar[str] = "feed"
    pack: ClassVar[str] = "elec"
    prefix: ClassVar[str | None] = "fd"
    positional: ClassVar[tuple[str, ...]] = ("target", "circuit")
    doc: ClassVar[str] = (
        "A circuit feeding an element of another discipline (a heat pump, a fan): feed fd1 g1 c7."
        " w= its power, counted in the circuit's load."
    )
    target: Annotated[Ref, F("the powered element")]
    circuit: Annotated[Ref, F("circuit", targets=("circ",))]
    w: Annotated[float | None, F("connected power", unit="W")] = None


KINDS: tuple[type[Element], ...] = (Board, Rcd, Circ, Sock, Conn, Switch, Data, Smoke, Feed)

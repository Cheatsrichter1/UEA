"""Medical and hospital systems (`med.uea`): medical gases, the fire alarm system, the nurse call
system, and the medical locations with their IT systems and safety power (decision 0058).

Devices stand on a wall like the electrical ones (`gas ge1 w29.s o2,air,vac x=W+2`); detectors,
gas pendants and the sources stand in a room. The electrical design feeds the panels, the IT
systems and the gas plant with `feed` lines (electrical sits below this pack).
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Anchor, Point, Ref, RefList
from uea.packs.mount import WallMounted

GASES: dict[str, str] = {
    "o2": "Sauerstoff (O2)",
    "air": "Druckluft medizinisch (AIR 5 bar)",
    "air8": "Druckluft für Instrumente (AIR 800)",
    "vac": "Vakuum (VAC)",
    "n2o": "Lachgas (N2O)",
    "co2": "Kohlendioxid (CO2)",
    "agss": "Narkosegas-Fortleitung (AGSS)",
}
"""The medical gases and their German names, in plan and legend order."""
GAS_WIDTH = 0.09
"""Width one gas takes in an outlet panel, in m."""


def parse_gases(s: str) -> tuple[str, ...]:
    parts = [p for p in s.split(",") if p]
    if not parts:
        raise ValueError(f"gases: name one or more of {', '.join(GASES)}")
    bad = [p for p in parts if p not in GASES]
    if bad:
        raise ValueError(f"gases: unknown {', '.join(bad)}; known: {', '.join(GASES)}")
    if len(set(parts)) != len(parts):
        raise ValueError(f"gases: {s} names a gas twice")
    return tuple(parts)


class GasSrc(Element):
    kind: ClassVar[str] = "gsrc"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "gq"
    positional: ClassVar[tuple[str, ...]] = ("host", "gas")
    doc: ClassVar[str] = (
        "The central supply of one medical gas in a room (Gasversorgung: a cylinder battery, a"
        ' tank connection, a compressor or vacuum plant): gsrc gq1 r20 o2 at=W+42,S+16 "O2'
        ' Flaschenbatterie". Its pipes reach every outlet of its gas; via= the slab holes they'
        " change storey through."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    gas: Annotated[
        Literal["o2", "air", "air8", "vac", "n2o", "co2", "agss"],
        F("the gas: o2, air, air8, vac, n2o, co2 or agss"),
    ]
    at: Annotated[
        Point | None, F("plan point x,y; the middle of the room if left out", unit="m")
    ] = None
    z: Annotated[float, F("height of its connection above the FFL", unit="m")] = 1.5
    via: Annotated[
        RefList | None,
        F("slab holes or voids its pipes change storey through", targets=("hole", "void")),
    ] = None


class GasOutlet(Element):
    kind: ClassVar[str] = "gas"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "ge"
    positional: ClassVar[tuple[str, ...]] = ("host", "gases")
    default_z: ClassVar[float | None] = 1.6
    doc: ClassVar[str] = (
        "Medical gas outlets (Entnahmestellen) side by side: on a wall face, e.g. in a bed-head"
        " unit (gas ge1 w29.s o2,air,vac x=W+2; z= 1.6 if left out), or in a room as a ceiling"
        " pendant (gas ge2 r16 o2,air,vac,agss at=W+20,S+13). Each gas comes from the nearest"
        " source of that gas."
    )
    host: Annotated[Ref, F("wall face, or room for a ceiling pendant", targets=("wall", "room"))]
    gases: Annotated[str, F("the gases, comma-separated: o2,air,vac")]
    at: Annotated[Point | None, F("point in the room, x,y (a pendant)", unit="m")] = None
    x: Annotated[Anchor | None, F("centre along a wall running along x", unit="m")] = None
    y: Annotated[Anchor | None, F("centre along a wall running along y", unit="m")] = None
    s: Annotated[Anchor | None, F("centre along a wall in any direction", unit="m")] = None
    z: Annotated[float | None, F("height of its centre above the FFL", unit="m")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        parse_gases(self.gases)
        axes = sum(v is not None for v in (self.x, self.y, self.s))
        if axes > 1:
            raise ValueError("give one of x=, y= or s=, for outlets on a wall")
        if axes and self.at is not None:
            raise ValueError("at= is for a pendant in a room, x=/y=/s= for outlets on a wall")
        return self

    @property
    def gas_list(self) -> tuple[str, ...]:
        return parse_gases(self.gases)

    @property
    def width(self) -> float:
        return GAS_WIDTH * len(self.gas_list)


class FirePanel(WallMounted):
    kind: ClassVar[str] = "fpanel"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "bz"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    default_z: ClassVar[float | None] = 1.6
    doc: ClassVar[str] = (
        'The fire alarm panel (Brandmelderzentrale, BMZ) on a wall: fpanel bz1 w8.w y=S+14 "BMZ".'
        " Once there is one, every room needs an automatic detector (W-MED-010)."
    )

    @property
    def width(self) -> float:
        return 0.6


class Detector(Element):
    kind: ClassVar[str] = "fdet"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "md"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    doc: ClassVar[str] = (
        "An automatic fire detector (Brandmelder) at the ceiling of a room: fdet md1 r5;"
        " sensor=smoke|heat|multi (smoke if left out), at= a point, panel= its panel."
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    sensor: Annotated[
        Literal["smoke", "heat", "multi"], F("what it senses: smoke, heat or multi (both)")
    ] = "smoke"
    at: Annotated[Point | None, F("point in the room, x,y; default the middle", unit="m")] = None
    z: Annotated[float | None, F("height above the FFL; default the ceiling", unit="m")] = None
    panel: Annotated[
        Ref | None, F("its fire alarm panel; the only one if left out", targets=("fpanel",))
    ] = None


class CallPoint(WallMounted):
    kind: ClassVar[str] = "mcp"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "hm"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    default_z: ClassVar[float | None] = 1.4
    doc: ClassVar[str] = (
        "A manual call point (Handfeuermelder) on a wall, usually at an exit or a stair door:"
        " mcp hm1 w6.n x=d16-0.3. z= 1.4 if left out; panel= its panel."
    )
    panel: Annotated[
        Ref | None, F("its fire alarm panel; the only one if left out", targets=("fpanel",))
    ] = None


class CallPanel(WallMounted):
    kind: ClassVar[str] = "cpanel"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "rz"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    default_z: ClassVar[float | None] = 1.4
    doc: ClassVar[str] = (
        "The nurse call panel (Rufzentrale, Stationsterminal) on a wall, at the nurses' station:"
        " cpanel rz1 w29.s x=W+22. Once there is one, bedrooms need a bed call and baths and WCs"
        " a pull call."
    )

    @property
    def width(self) -> float:
        return 0.3


ROLE_Z: dict[str, float] = {"bed": 1.1, "pull": 2.0, "lamp": 2.2, "duty": 1.4}
"""The height of a call device above the FFL when z= is left out, by role."""


class Call(WallMounted):
    kind: ClassVar[str] = "call"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "ru"
    positional: ClassVar[tuple[str, ...]] = ("host", "role")
    default_z: ClassVar[float | None] = 1.4
    doc: ClassVar[str] = (
        "A nurse call device (Rufanlage) on a wall: bed (Bettruf, at the bed head, z 1.1), pull"
        " (Zugruf in a bath or WC, z 2.0), lamp (Zimmersignalleuchte over a door outside, z 2.2;"
        " door= the door of the room it signals), duty (Dienstzimmer- or Anwesenheitstaster, z"
        " 1.4): call ru1 w36.w bed y=S+1.2. panel= its panel."
    )
    role: Annotated[Literal["bed", "pull", "lamp", "duty"], F("bed, pull, lamp or duty")]
    door: Annotated[Ref | None, F("the door of the room a lamp signals", targets=("door",))] = None
    panel: Annotated[
        Ref | None, F("its nurse call panel; the only one if left out", targets=("cpanel",))
    ] = None

    @model_validator(mode="after")
    def _lamp(self) -> Self:
        if self.door is not None and self.role != "lamp":
            raise ValueError("door= is for a lamp: the door of the room it signals")
        return self

    @property
    def width(self) -> float:
        return 0.12 if self.role == "lamp" else 0.071


class MedLoc(Element):
    kind: ClassVar[str] = "medloc"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "mb"
    positional: ClassVar[tuple[str, ...]] = ("room", "group")
    doc: ClassVar[str] = (
        "A medical location (medizinisch genutzter Bereich) and its group, 0, 1 or 2, as the"
        " planner classifies it with the clinic: medloc mb1 r16 2 it=it1. Group 2 (applied parts"
        " in the heart, life support: OP, intensive care) needs an IT system (it=)."
    )
    room: Annotated[Ref, F("room", targets=("room",))]
    group: Annotated[int, F("group 0, 1 or 2")]
    it: Annotated[Ref | None, F("the medical IT system that supplies it", targets=("itsys",))] = (
        None
    )

    @model_validator(mode="after")
    def _group(self) -> Self:
        if self.group not in (0, 1, 2):
            raise ValueError("group must be 0, 1 or 2")
        return self


class ItSys(WallMounted):
    kind: ClassVar[str] = "itsys"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "it"
    positional: ClassVar[tuple[str, ...]] = ("host",)
    default_z: ClassVar[float | None] = 1.4
    doc: ClassVar[str] = (
        "A medical IT system (IT-System: isolating transformer and insulation monitor, in its"
        " own board) on a wall near the rooms it supplies: itsys it1 w21.e y=S+12 kva=8 sv=sv2."
        " sv= the safety power source behind it."
    )
    kva: Annotated[float | None, F("rated power of its transformer", unit="kVA")] = None
    sv: Annotated[Ref | None, F("the safety power source that feeds it", targets=("safety",))] = (
        None
    )

    @property
    def width(self) -> float:
        return 0.6


class Safety(Element):
    kind: ClassVar[str] = "safety"
    pack: ClassVar[str] = "med"
    prefix: ClassVar[str | None] = "sv"
    positional: ClassVar[tuple[str, ...]] = ("host", "source")
    doc: ClassVar[str] = (
        "A safety power source (Sicherheitsstromversorgung) in a room: ups (USV, switches over"
        " without a break), genset (Netzersatzanlage, a diesel generator) or battery (a central"
        ' battery for the safety lighting): safety sv1 r20 genset kw=150 "NEA".'
    )
    host: Annotated[Ref, F("room", targets=("room",))]
    source: Annotated[Literal["ups", "genset", "battery"], F("ups, genset or battery")]
    kw: Annotated[float | None, F("rated power", unit="kW")] = None
    at: Annotated[
        Point | None, F("plan point x,y; the middle of the room if left out", unit="m")
    ] = None
    z: Annotated[float, F("height above the FFL", unit="m")] = 0.0


KINDS: tuple[type[Element], ...] = (
    GasSrc,
    GasOutlet,
    FirePanel,
    Detector,
    CallPoint,
    CallPanel,
    Call,
    MedLoc,
    ItSys,
    Safety,
)

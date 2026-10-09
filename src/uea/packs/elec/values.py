"""Values of the electrical pack: cable designations, breakers, RCD ratings and switch control."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from uea.core.syntax import fmt_num
from uea.core.values import NUM, Ref, Value

_CABLE = re.compile(rf"^(?P<kind>[A-Za-z][A-Za-z0-9-]*?)(?P<cores>\d+)(?P<sep>[xG])(?P<mm2>{NUM})$")
_BREAKER = re.compile(rf"^(?P<char>[BCDKZ])(?P<amps>{NUM})$")
_RATING = re.compile(rf"^(?P<amps>{NUM})/(?P<idn>{NUM})$")


@dataclass(frozen=True, slots=True)
class Cable(Value):
    """A cable by its designation: `NYM-J3x2.5` is NYM-J with 3 cores of 2.5 mm² copper."""

    kind: str
    cores: int
    mm2: float
    sep: str = "x"
    """`x` or `G` (with a green-yellow earth core), as written."""

    def fmt(self) -> str:
        return f"{self.kind}{self.cores}{self.sep}{fmt_num(self.mm2)}"

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _CABLE.match(s)
        if not m:
            raise ValueError(
                f"{s!r} is not a cable designation like NYM-J3x2.5 (type, cores x mm²)"
            )
        cores, mm2 = int(m["cores"]), float(m["mm2"])
        if cores < 2 or mm2 <= 0:
            raise ValueError(f"cable {s}: at least 2 cores and more than 0 mm²")
        return cls(m["kind"], cores, mm2, m["sep"])


@dataclass(frozen=True, slots=True)
class Breaker(Value):
    """A circuit breaker by tripping characteristic and rated current: `B16`."""

    char: str
    amps: float

    def fmt(self) -> str:
        return f"{self.char}{fmt_num(self.amps)}"

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _BREAKER.match(s)
        if not m or float(m["amps"]) <= 0:
            raise ValueError(f"{s!r} is not a breaker like B16 (B, C, D, K or Z, then amps)")
        return cls(m["char"], float(m["amps"]))


@dataclass(frozen=True, slots=True)
class Rating(Value):
    """An RCD by rated current and rated residual current, in A: `40/0.03`."""

    amps: float
    idn: float

    def fmt(self) -> str:
        return f"{fmt_num(self.amps)}/{fmt_num(self.idn)}"

    @classmethod
    def parse(cls, s: str) -> Self:
        m = _RATING.match(s)
        if not m or float(m["amps"]) <= 0 or float(m["idn"]) <= 0:
            raise ValueError(f"{s!r} is not an RCD rating like 40/0.03 (rated A / residual A)")
        return cls(float(m["amps"]), float(m["idn"]))


@dataclass(frozen=True, slots=True)
class Controls(Value):
    """What a switch controls: channels separated by `,`, luminaires of a channel by `+`.

    `l2,l3`: a two-channel switch, one luminaire each. `l15+l16`: one channel, two luminaires.
    """

    groups: tuple[tuple[Ref, ...], ...]

    def fmt(self) -> str:
        return ",".join("+".join(r.fmt() for r in g) for g in self.groups)

    def refs(self) -> tuple[str, ...]:
        return tuple(r.id for g in self.groups for r in g)

    def map_refs(self, f: Callable[[str], str]) -> Self:
        return type(self)(tuple(tuple(r.map_refs(f) for r in g) for g in self.groups))

    @classmethod
    def parse(cls, s: str) -> Self:
        groups = s.split(",")
        if not s or any(not g or any(not p for p in g.split("+")) for g in groups):
            raise ValueError(f"{s!r} is not a control list like l1 or l2,l3 or l15+l16")
        return cls(tuple(tuple(Ref.parse(p) for p in g.split("+")) for g in groups))

"""The sizes of a pipe or duct system, from the manufacturer (decisions 0035, 0037)."""

import re
from dataclasses import dataclass
from typing import Self

from uea.core.syntax import fmt_num
from uea.core.values import Value

_BORE = re.compile(r"^(?:(?P<dn>\d+):)?(?P<da>\d+(?:\.\d+)?)x(?P<s>\d+(?:\.\d+)?)$")


@dataclass(frozen=True, slots=True)
class Bore:
    """One size of a pipe system: outer diameter and wall in mm, and for a drain pipe its DN."""

    dn: int | None
    da: float
    s: float

    @property
    def di(self) -> float:
        """Inner diameter, mm."""
        return self.da - 2 * self.s

    @property
    def name(self) -> str:
        return f"DN {self.dn}" if self.dn is not None else f"{fmt_num(self.da)}x{fmt_num(self.s)}"

    def fmt(self) -> str:
        head = f"{self.dn}:" if self.dn is not None else ""
        return f"{head}{fmt_num(self.da)}x{fmt_num(self.s)}"


@dataclass(frozen=True, slots=True)
class Bores(Value):
    """The sizes of a pipe system, small to large: `16x2,20x2.25` (outer diameter x wall, mm) or,
    for drain pipes, `100:110x2.7` (DN, then outer diameter x wall)."""

    items: tuple[Bore, ...]

    def fmt(self) -> str:
        return ",".join(b.fmt() for b in self.items)

    @classmethod
    def parse(cls, s: str) -> Self:
        items: list[Bore] = []
        for part in s.split(","):
            m = _BORE.match(part)
            if not m:
                raise ValueError(
                    f"size {part!r}: write outer diameter x wall in mm, e.g. 20x2.25, or for a"
                    " drain pipe DN:outer x wall, e.g. 100:110x2.7"
                )
            b = Bore(int(m["dn"]) if m["dn"] else None, float(m["da"]), float(m["s"]))
            if b.s <= 0 or b.di <= 0:
                raise ValueError(f"size {part}: the wall must be more than 0 and leave a bore")
            if items and b.di <= items[-1].di:
                raise ValueError(f"sizes: list them from small to large ({part} after the last)")
            items.append(b)
        return cls(tuple(items))

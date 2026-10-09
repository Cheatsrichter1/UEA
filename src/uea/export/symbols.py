"""Symbols of the electrical plans (decision 0026): simplified and drawn by us, in the spirit of
DIN EN 60617 and not copied from it.

A symbol is drawn in a local frame: `a` runs along the wall, `b` out of the wall into the room,
both in mm on paper, so a symbol is as big on paper at every scale. A device on a ceiling has the
same frame with `a` to the right and `b` up.
"""

import math
from dataclasses import dataclass

from uea.export.drawing import Arc, Circle, Drawing, Line, Pen, Poly, Pt, Sheet, Text

SPACING = 3.4
"""Distance between the outlets of a frame, in mm."""


@dataclass(frozen=True)
class Spot:
    """Where a symbol stands: a point, the direction along the wall and the one into the room."""

    o: Pt
    t: Pt = (1.0, 0.0)
    v: Pt = (0.0, 1.0)


class Ink:
    """Draws in the local frame of a spot, in mm on paper."""

    def __init__(self, dw: Drawing, sh: Sheet, spot: Spot, color: str, layer: str) -> None:
        self.dw = dw
        self.sh = sh
        self.sp = spot
        self.color = color
        self.layer = layer

    def at(self, a: float, b: float) -> Pt:
        sp, m = self.sp, self.sh.m
        return (
            sp.o[0] + sp.t[0] * m(a) + sp.v[0] * m(b),
            sp.o[1] + sp.t[1] * m(a) + sp.v[1] * m(b),
        )

    def pen(self, mm: float = 0.18, dash: tuple[float, ...] = ()) -> Pen:
        return Pen(self.color, self.sh.m(mm), tuple(self.sh.m(x) for x in dash))

    def line(self, a0: float, b0: float, a1: float, b1: float, mm: float = 0.18) -> None:
        self.dw.add(Line(self.at(a0, b0), self.at(a1, b1), self.pen(mm), self.layer))

    def circle(
        self, a: float, b: float, r: float, fill: str | None = None, mm: float = 0.18
    ) -> None:
        self.dw.add(Circle(self.at(a, b), self.sh.m(r), self.pen(mm), fill, self.layer))

    def half(self, a: float, b: float, r: float, mm: float = 0.18) -> None:
        """The half circle on the room side of the wall."""
        sp = self.sp
        th = math.degrees(math.atan2(sp.t[1], sp.t[0]))
        left = sp.t[0] * sp.v[1] - sp.t[1] * sp.v[0] > 0
        a0, a1 = (th, th + 180.0) if left else (th - 180.0, th)
        self.dw.add(Arc(self.at(a, b), self.sh.m(r), a0, a1, self.pen(mm), self.layer))

    def poly(
        self, pts: list[tuple[float, float]], fill: str | None = None, mm: float = 0.18
    ) -> None:
        self.dw.add(Poly([self.at(a, b) for a, b in pts], fill, self.pen(mm), self.layer))

    def text(self, a: float, b: float, txt: str, mm: float = 1.5, bold: bool = False) -> None:
        self.dw.add(Text(self.at(a, b), txt, self.sh.m(mm), self.color, "middle", bold, self.layer))


def sock(ink: Ink, n: int = 1) -> float:
    """A socket: a half circle for each outlet of its frame. Returns how far it reaches out."""
    for k in range(n):
        a = (k - (n - 1) / 2) * SPACING
        ink.half(a, 0.0, 1.5)
        ink.line(a - 2.0, 0.0, a + 2.0, 0.0)
    return 1.5


def conn(ink: Ink) -> float:
    """A fixed connection: a circle with a cross, on the wall."""
    ink.circle(0.0, 1.2, 1.2)
    ink.line(-0.85, 0.35, 0.85, 2.05)
    ink.line(-0.85, 2.05, 0.85, 0.35)
    ink.line(-1.8, 0.0, 1.8, 0.0)
    return 2.4


def switch(ink: Ink, channels: int = 1, two_way: bool = False, dim: bool = False) -> float:
    """A switch: a circle with a stroke for each channel; a stroke on the other side too for a
    two-way switch; the circle is filled for a dimmer."""
    ink.circle(0.0, 1.3, 1.2, "#cccccc" if dim else None)
    angles = {1: [50.0], 2: [35.0, 65.0]}.get(channels, [25.0, 50.0, 75.0][:channels])
    for ang in angles:
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        ink.line(1.2 * c, 1.3 + 1.2 * s, 3.7 * c, 1.3 + 3.7 * s, 0.25)
    if two_way:
        c, sn = math.cos(math.radians(50)), math.sin(math.radians(50))
        ink.line(-1.2 * c, 1.3 + 1.2 * sn, -3.7 * c, 1.3 + 3.7 * sn, 0.25)
    return 4.0


def lum(ink: Ink, on_wall: bool = False) -> float:
    """A luminaire: a circle with a cross; one on a wall sits on a line."""
    r = 1.5 if on_wall else 2.0
    b = r if on_wall else 0.0
    ink.circle(0.0, b, r)
    k = r * 0.707
    ink.line(-k, b - k, k, b + k)
    ink.line(-k, b + k, k, b - k)
    if on_wall:
        ink.line(-2.2, 0.0, 2.2, 0.0)
    return b + r


def smoke(ink: Ink) -> float:
    """A smoke alarm: a circle with RM."""
    ink.circle(0.0, 0.0, 1.9)
    ink.text(0.0, -0.5, "RM", 1.4, True)
    return 1.9


def data(ink: Ink, n: int = 1) -> float:
    """A data outlet: a triangle for each port, on the wall."""
    for k in range(n):
        a = (k - (n - 1) / 2) * SPACING
        ink.poly([(a - 1.5, 0.0), (a + 1.5, 0.0), (a, 2.6)])
    return 2.6


def board(ink: Ink, width: float = 5.0) -> float:
    """A distribution board: a dark box on the wall with a diagonal."""
    w = max(width, 3.0) / 2
    ink.poly([(-w, 0.0), (w, 0.0), (w, 1.8), (-w, 1.8)], "#505050", 0.25)
    ink.line(-w, 0.0, w, 1.8, 0.18)
    return 1.8

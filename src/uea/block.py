"""`uea block`: a simple building as ordinary model lines, for options on a plot (decision 0057).

A block is a box of storeys on a rectangle: per storey four walls, its slab and one room, and
a roof on top. Its lines are an ordinary batch, so every calculator, check and export works on
it unchanged, and the agent may edit it like any other part of the model. The walls take the
type MASS (a core of 0.3 m, no finishes), so the rectangle given is the outline at the outer
faces. Storeys are added where the model has none: EG at ±0.00, then OG1, OG2 at the height
h= apart, with no floor build-up. A roof other than flat gets its own storey (DG) with
knee= under it.
"""

from dataclasses import dataclass

from uea.core.model import Model
from uea.core.values import Span
from uea.packs.project import Level

WALL, SLAB, ROOF = "MASS", "MASS-D", "MASS-R"
TYPES = {
    WALL: "+ type MASS wall layers=*mass:0.3",
    SLAB: "+ type MASS-D slab layers=*concrete:0.25",
    ROOF: "+ type MASS-R roof layers=*roof:0.3",
}
SHAPES = ("flat", "gable", "hip", "shed")


@dataclass
class Block:
    x: Span
    y: Span
    storeys: int
    h: float = 3.0
    start: str | None = None
    """The storey the block starts on; else the lowest storey at or above ±0.00, or EG."""
    roof: str = "flat"
    pitch: float = 30.0
    ridge: str | None = None
    up: str | None = None
    knee: float = 0.0
    use: str = "other"


def _int(v: str, name: str) -> int:
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"{name}={v} is not a whole number") from None


def _num(v: str, name: str) -> float:
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"{name}={v} is not a number") from None


def parse(args: list[str]) -> Block:
    given: dict[str, str] = {}
    for a in args:
        k, sep, v = a.partition("=")
        if not sep or not v:
            raise ValueError(f"{a}: give name=value, e.g. storeys=3")
        given[k] = v
    for need in ("x", "y", "storeys"):
        if need not in given:
            raise ValueError(f"uea block needs {need}=: x=W..E y=S..N storeys=3")
    b = Block(
        Span.parse(given.pop("x")),
        Span.parse(given.pop("y")),
        _int(given.pop("storeys"), "storeys"),
    )
    if "h" in given:
        b.h = _num(given.pop("h"), "h")
    b.start = given.pop("from", None)
    b.roof = given.pop("roof", "flat")
    if b.roof not in SHAPES:
        raise ValueError(f"roof={b.roof}: one of {', '.join(SHAPES)}")
    if "pitch" in given:
        b.pitch = _num(given.pop("pitch"), "pitch")
    b.ridge = given.pop("ridge", None)
    b.up = given.pop("up", None)
    if "knee" in given:
        b.knee = _num(given.pop("knee"), "knee")
    b.use = given.pop("use", "other")
    if given:
        raise ValueError(
            f"unknown setting {', '.join(given)}=. uea block takes x y storeys h from roof pitch"
            " ridge up knee use"
        )
    for name, sp in (("x", b.x), ("y", b.y)):
        for a in (sp.a, sp.b):
            if a.sign is not None or a.face is not None:
                raise ValueError(
                    f"{name}={sp.fmt()}: give the ends as grids or numbers, e.g. x=W..E or"
                    " x=0..12 (add grids for other lines)"
                )
    if not 1 <= b.storeys <= 60:
        raise ValueError("storeys= is 1 to 60")
    if b.h <= 0.5:
        raise ValueError("h= is the storey height in m, e.g. 3")
    if b.roof == "gable" and b.ridge not in ("x", "y"):
        raise ValueError("a gable roof needs ridge=x or ridge=y")
    if b.roof == "shed" and b.up not in ("n", "e", "s", "w"):
        raise ValueError("a shed roof needs up=n, e, s or w")
    return b


def ops(model: Model, b: Block) -> str:
    """The batch that builds the block."""
    levels = sorted((e for e in model.of_kind("level") if isinstance(e, Level)), key=lambda e: e.z)
    names = {e.id for e in levels}
    types = {e.id for e in model.of_kind("type")}
    out = [TYPES[t] for t in (WALL, SLAB, ROOF) if t not in types]
    if b.start is not None:
        first = next((e for e in levels if e.id == b.start), None)
        if first is None:
            raise ValueError(
                f"from={b.start}: no such storey. Storeys: {' '.join(names) or 'none'}"
            )
    else:
        first = next((e for e in levels if e.z >= -1e-9), None)
    stack: list[tuple[str, float]] = []
    if first is None:
        out.append("+ level EG z=0 fb=0")
        names.add("EG")
        stack.append(("EG", 0.0))
    else:
        stack.append((first.id, first.z))
    above = [e for e in levels if first is not None and e.z > first.z + 1e-9]
    count = b.storeys + (0 if b.roof == "flat" else 1)
    n = 1
    while len(stack) < count:
        if above:
            e = above.pop(0)
            stack.append((e.id, e.z))
            continue
        roof_storey = len(stack) == b.storeys
        base = "DG" if roof_storey else "OG"
        name = base if roof_storey and base not in names else f"{base}{n}"
        while name in names:
            n += 1
            name = f"{base}{n}"
        names.add(name)
        z = stack[-1][1] + b.h
        out.append(f"+ level {name} z={z:g} fb=0")
        stack.append((name, z))
        n += 1
    xa, xb, ya, yb = b.x.a.fmt(), b.x.b.fmt(), b.y.a.fmt(), b.y.b.fmt()
    top = stack[-1][0]
    for i, (lv, _) in enumerate(stack):
        last = lv == top
        tail = " top=@roof" if last else ""
        out += [
            f"+ wall @s{i} {lv} {WALL} y={ya}+ x={xa}..{xb} lb{tail}",
            f"+ wall @n{i} {lv} {WALL} y={yb}- x={xa}..{xb} lb{tail}",
            f"+ wall @w{i} {lv} {WALL} x={xa}+ y=@s{i}..@n{i} lb{tail}",
            f"+ wall @e{i} {lv} {WALL} x={xb}- y=@s{i}..@n{i} lb{tail}",
            f"+ slab _ {lv} {SLAB}",
        ]
        use = "attic" if b.roof != "flat" and last else b.use
        out.append(f"+ room _ {lv} {use} at=@w{i}+0.5,@s{i}+0.5")
    roof = f"+ roof @roof {top} {ROOF} {b.roof}"
    if b.roof == "flat":
        roof += f" knee={b.h - 0.3:g}"
    else:
        roof += f" pitch={b.pitch:g} knee={b.knee:g}"
        if b.ridge:
            roof += f" ridge={b.ridge}"
        if b.up:
            roof += f" up={b.up}"
    out.append(roof)
    return "\n".join(out)

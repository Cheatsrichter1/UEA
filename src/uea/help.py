"""`uea help`: short, layered help. An agent loads only the topic it needs."""

from uea.core.issues import CORE_CODES
from uea.core.registry import Registry
from uea.core.schema import Element, spec, usage

ROOT = """\
UEA: a building model for agents. A project is a folder of .uea text files, one per
discipline. Read it with commands, change it with batches of operations. Code computes
areas, heights and checks; you decide. A human reviews the exports and signs.

  uea init <dir>                  new project
  uea show [scope]                summary: project, EG, arch, arch:EG, or an id
  uea get <id>...                 elements with derived values
  uea find <kind> [filters]       find wall ext lb · find door room=r3 · find win level=OG
  uea apply --by <who> -m <why>   atomic batch of operations from stdin (help ops)
  uea revert <batch> --by <who>   undo a batch as a new batch
  uea check [discipline]          open issues, requests and waivers
  uea calc [name] [scope]         calculators, e.g. calc wofl (help calc)
  uea render <level>              plan image (PNG) to look at
  uea export <format> [scope]     for humans: ifc, svg, png
  uea log [n]                     recent batches
  Options: -C <dir> run in another folder · --json machine-readable output

Topics: uea help start | ops | positions | arch | <kind> | codes | calc
"""

START = """\
Start a building:
  uea init haus && cd haus
  batch 1: + project, + level (z= OKFF, fb= floor build-up, head= Sturzhöhe), + grid, + type
  batch 2 per storey: walls, then doors/windows, stair, slab, sep, rooms
  uea check after each batch; uea show EG to see rooms and areas; uea render EG to look.
Rules: one element per line. You name levels, grids and types; UEA assigns all other ids
(use @name placeholders inside a batch). Positions are relative (help positions), so moving
one wall moves what is placed on it. Plan positions are Rohbau faces; heights are above OKFF.
Example (four exterior walls and the room inside them):
  uea apply --by arch-agent -m "EG walls" <<'EOF'
  + wall @s EG AW-365 y=S+ x=W..E lb
  + wall @n EG AW-365 y=N- x=W..E lb
  + wall @w EG AW-365 x=W+ y=@s..@n lb
  + wall @o EG AW-365 x=E- y=@s..@n lb
  + room _ EG living at=@w+1,@s+1
  EOF
"""

OPS = """\
uea apply --by <who> -m <why> [--dry-run] < ops   (quote the heredoc: <<'EOF')
  + wall @a EG IW-115 x=w6+1.385 y=w5..w3    add; @a is a placeholder, UEA assigns the id
  + door _ @a 0.76x2.01 y=w5+0.26            _ : nothing in the batch refers to it
  ~ w9 type=IW-175 lb                        set fields; flags as bare words; k= resets
  ~ d1 1.51x2.26                             a bare value sets the positional field it fits
  - w9 d3                                    remove
  > grid E x=10.74                           replace the whole element
  ~ q1 done | ~ q1 rejected="reason"         close or reject a request
A batch is atomic. Placeholders may be used before they are defined. It is rejected if it
adds an error in a discipline it writes; nothing changes then. Errors it causes in other
disciplines are reported (affects ...) and stay open there. --dry-run checks without writing.
Output: ok batch N (packs): +added changed -removed, the ids, new issues, what follows.
"""

POSITIONS = """\
Positions (metres, Rohbau). anchor±distance; the sign says from which face and which way.
  x=w4+2.26     my -x side is 2.26 past w4's +x face; I extend in +x (a clear dimension)
  x=E-          my +x side is on grid E; I extend in -x
  y=w5.n-       explicit face: my +y side on w5's north face
  x=d4+0.25     0.25 past the + edge of opening d4
  y=f2.c        on the centre of f2
  y=w1..w3      span between the faces of w1 and w3 that face each other
  x=W..E        span between grids
  on=w1         same footprint as w1 (a wall on the wall below)
  at=w4+1,w1+1  a point: x anchor, y anchor
  x=3.2+        raw coordinate (escape hatch)
Anchors: grids, walls, openings, stairs, separators. Faces: .n .s .e .w, centre .c.
Walls: one axis is a position, the other a span. Openings: their edge along the wall.
Heights: z of a level is its OKFF (±0.00 = OKFF EG); OK Rohdecke = z - fb. Windows hang
from the level's head= (Sturzhöhe); sill= only if one deviates. Doors stand on OKFF.
Names of levels and grids: no '-', because W-1.2 means grid W minus 1.2.
"""

ARCH_NOTES = """\
Wall layers inside to outside (interior walls: -x/-y face first); * marks the core, which is
what positions refer to. Slab layers top to bottom; the core top is OK Rohdecke. Floor types
are the Fußbodenaufbau (fb). Roof layers outside to inside.
Status flags on physical elements: existing (Bestand), demolish, temp; none means new.
Derived, never stored: exterior walls, room outlines and areas (Rohbau and Fertig), heights,
volumes, slab outlines, stair risers, Traufe and First. Read them with uea get.
"""

CALC = """\
uea calc                list calculators
uea calc wofl [level]   Wohnfläche per WoFlV (norm). Writes out/wofl.md.
Results say calculator, kind (norm or custom), version and inputs. A custom result is never
norm-compliant. Project calculators live in calc/ (custom).
"""


def kind_help(cls: type[Element]) -> str:
    sp = spec(cls)
    lines = [usage(cls) + ' ["label"] [k=v...] [flags]', cls.doc]
    for name in sp.positional:
        f = sp.fields[name]
        lines.append(f"  <{name}>  {_field_doc(f.meta.doc, f.meta.unit, f.choices)}")
    for name in sp.kv:
        f = sp.fields[name]
        req = " (required)" if f.required else ""
        lines.append(f"  {name}=  {_field_doc(f.meta.doc, f.meta.unit, f.choices)}{req}")
    flags = list(sp.flags) + [
        v for n in sp.flag_enums for v in sp.fields[n].choices if v != sp.fields[n].default
    ]
    if flags:
        lines.append(f"  flags: {' '.join(flags)}")
    if cls.prefix:
        lines.append(f"  ids: {cls.prefix}1, {cls.prefix}2, ... (assigned by UEA)")
    return "\n".join(lines)


def _field_doc(doc: str, unit: str | None, choices: tuple[str, ...]) -> str:
    out = doc
    if choices:
        out += f" [{' '.join(choices)}]"
    if unit:
        out += f" ({unit})"
    return out


def pack_help(reg: Registry, pack: str) -> str:
    p = reg.packs[pack]
    lines = [f"{p.name}: {p.title} ({p.file})"]
    for cls in p.kinds:
        name = f"type {cls.category}" if cls.kind == "type" else cls.kind
        lines.append(f"  {name:<12} {cls.doc}")
    if pack == "arch":
        lines.append(ARCH_NOTES.rstrip())
    lines.append(f"Details: uea help <kind>, e.g. uea help {p.kinds[-1].kind}")
    return "\n".join(lines)


def codes_help(reg: Registry) -> str:
    lines = [
        "Issue codes (E = error, W = warning)."
        " Every issue names the element, the numbers and a fix."
    ]
    for code, text in CORE_CODES.items():
        lines.append(f"  {code}  {text}")
    for p in reg.packs.values():
        for code, text in p.codes.items():
            lines.append(f"  {code}  {text}")
    return "\n".join(lines)


def help_text(reg: Registry, topic: str | None) -> str | None:
    if topic is None:
        return ROOT
    t = topic.lower()
    fixed = {"start": START, "ops": OPS, "positions": POSITIONS, "calc": CALC}
    if t in fixed:
        return fixed[t]
    if t == "codes":
        return codes_help(reg)
    if t in reg.packs:
        return pack_help(reg, t)
    if t in reg.kinds:
        return kind_help(reg.kinds[t])
    if t == "type":
        return "\n\n".join(kind_help(c) for c in reg.types.values())
    if t.startswith("type:") and t[5:] in reg.types:
        return kind_help(reg.types[t[5:]])
    return None

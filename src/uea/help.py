"""`uea help`: short, layered help. An agent loads only the topic it needs."""

from uea.core.issues import CORE_CODES
from uea.core.registry import Registry
from uea.core.schema import Element, spec, usage

COMMANDS: tuple[tuple[str, str], ...] = (
    ("uea init <dir>", "new project"),
    ("uea show [scope]", "summary: project, EG, arch, arch:EG, or an id"),
    ("uea get <id>...", "elements with derived values"),
    ("uea find <kind> [filters]", "find wall ext lb · find door room=r3 · find win level=OG"),
    ("uea apply --by <who> -m <why>", "atomic batch of operations from stdin (help ops)"),
    ("uea revert <batch> --by <who>", "undo a batch as a new batch"),
    ("uea check [discipline]", "open issues, requests and waivers"),
    ("uea calc [name] [scope]", "calculators, e.g. calc wofl (help calc)"),
    ("uea render <level>", "plan image (PNG) to look at (help export)"),
    ("uea export <format> [scope]", "for humans: pdf, dxf, xlsx, ifc, svg, png (help export)"),
    ("uea log [n]", "recent batches"),
    ("uea help [topic]", "this help, or a topic"),
)
"""Every command with a one-line description: the root help and docs/reference.md."""

TOPICS = "start | ops | positions | arch | elec | <kind> | codes | calc | export"

ROOT = (
    """\
UEA: a building model for agents. A project is a folder of .uea text files, one per
discipline. Read it with commands, change it with batches of operations. Code computes
areas, heights and checks; you decide. A human reviews the exports and signs.

"""
    + "\n".join(f"  {u:<31} {d}" for u, d in COMMANDS[:-1])
    + f"""
  Options: -C <dir> run in another folder · --json machine-readable output

Topics: uea help {TOPICS}
"""
)

START = """\
Start a building: uea init haus && cd haus, then send batches of operations:
  uea apply --by arch-agent -m "why" <<'EOF'
  ...one operation per line...
  EOF
Batch 1, the project data. You name the project, levels, grids and types:
  + project haus "EFH Müller" site=DE-HE postcode=64283 ground=-0.3
  + level EG z=0 fb=0.15 head=2.26
  + grid W x=0              (likewise E x=10.49, S y=0, N y=8.49)
  + type AW-365 wall "Ziegel 36,5" layers=plaster:0.015,*brick:0.365,render:0.02
  z: FFL (finished floor level, OKFF) · fb: floor build-up · head: window head height
  layers: material:thickness in m, comma-separated, * marks the core (uea help type)
Batch 2 per storey: walls, then doors/windows, stair, slab, sep, rooms. UEA assigns their
ids; inside a batch use @name placeholders. Four exterior walls and the room inside them:
  + wall @s EG AW-365 y=S+ x=W..E lb
  + wall @n EG AW-365 y=N- x=W..E lb
  + wall @w EG AW-365 x=W+ y=@s..@n lb
  + wall @o EG AW-365 x=E- y=@s..@n lb
  + room _ EG living "Wohnen" at=@w+1,@s+1
uea check after each batch; uea show EG to see rooms and areas; uea render EG to look.
Positions are relative (help positions), so moving one wall moves what is placed on it.
Plan positions are core faces; heights are above the storey's FFL.
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
Positions (metres, core faces). anchor±distance; the sign says from which face and which way.
  x=w4+2.26     my -x side is 2.26 past w4's +x face; I extend in +x (a clear dimension)
  x=w6-0.135    my +x side is 0.135 before w6's -x face; I extend in -x
  x=E-          my +x side is on grid E; I extend in -x
  x=W+1.51      1.51 past grid W, e.g. a window measured from the outside corner
  y=w5.n-       explicit face: my +y side on w5's north face
  x=d4+0.25     0.25 past the + edge of opening d4
  y=f2.c        on the centre of f2
  y=w1..w3      span between the faces of w1 and w3 that face each other
  x=W..E        span between grids
  on=w1         same footprint as w1 (a wall on the wall below)
  at=w4+1,w1+1  a point: x anchor, y anchor
  x=3.2+        raw coordinate (escape hatch)
  a=w4.c,w1.c b=3,5.5  wall in any direction: its axis from point a to point b
  s=1.2+        opening in such a wall: from its start a (s=d1+0.5: from an opening)
Anchors: grids, walls, openings, stairs, separators. Faces: .n .s .e .w, centre .c; a wall at an
angle has .l .r (left, right of a to b) and no x=/y= anchors. Walls: a position and a span, or
a=/b=. Openings: their edge along the wall.
Heights: a level's z is its FFL (finished floor level, OKFF; ±0.00 = FFL of the ground
storey). Its SSL (structural slab level, OK Rohdecke) = z - fb. Windows hang from the
level's head= (head height, Sturzhöhe); sill= only if one deviates. Doors stand on the FFL.
Names of levels and grids: no '-', because W-1.2 means grid W minus 1.2.
"""

ARCH_NOTES = """\
Layers: material:thickness in metres, comma-separated; * marks the core, which is what
positions refer to: layers=plaster:0.015,*brick:0.365,render:0.02. Walls inside to outside
(interior walls: -x/-y face first), slabs top to bottom (the core top is the SSL), floor
types top to bottom (the floor build-up, fb), roofs outside to inside.
Status flags on physical elements: existing (Bestand), demolish, temp; none means new.
Derived, never stored: exterior walls, room outlines and areas (shell: between core faces;
fin: between finished surfaces), heights, volumes, slab outlines, stair risers, eaves and
ridge heights. Read them with uea get.
"""

ELEC_NOTES = """\
A device stands on a wall face: host w4 (an exterior wall: the room side) or w5.n (an interior
wall needs its face), a position along it (x= or y= like an opening's; x=sw1+0.071 is one frame
past switch sw1) and z=, the height of its centre above the FFL (sockets 0.3, switches 1.05 if
left out). Luminaires are in light.uea. A switch wires the luminaires in its ctl=: they take its
circuit, two switches make a two-way circuit, three an intermediate one. A circuit's load is
its luminaires and the w= of its connections and feeds, against breaker x 230 V x phases.
Cable sizing and voltage drop come with the calculators. The checks are planning rules and
cite no norm.
"""

CALC = """\
uea calc                list calculators
uea calc wofl [level]   Wohnfläche per WoFlV (norm). Writes out/wofl.md.
Results say calculator, kind (norm or custom), version and inputs. A custom result is never
norm-compliant. Project calculators live in calc/ (custom).
"""

EXPORT = """\
uea render <level> [-o file]        working plan (PNG) with element ids, for you to look at
uea export pdf|dxf [name] [-o f]    sheets for humans, A3 1:100 or larger: a floor plan per storey
                                    (name: a level), a section per section (its name) and the four
                                    facades (north|east|south|west), with dimensions and height
                                    marks; all if none is given
uea export xlsx [level] [-o file]   tables: rooms, walls, openings, slabs, roofs, stairs, quantities
uea export ifc [-o file]            IFC4 model for humans and other software
uea export svg|png [name] [-o f]    the same sheet as a picture, to check what the PDF shows
Files go to out/ unless -o says otherwise; the output names them. Sections: + section A x=W+5 look=w
(uea help section). Sheets and tables are labelled in German, for the people who read them. The
title block stays unsigned: a human signs.
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
    if pack == "elec":
        lines.append(ELEC_NOTES.rstrip())
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
    fixed = {
        "start": START,
        "ops": OPS,
        "positions": POSITIONS,
        "calc": CALC,
        "export": EXPORT,
        "render": EXPORT,
    }
    if t in fixed:
        return fixed[t]
    if t == "codes":
        return codes_help(reg)
    if t in reg.kinds and t in reg.packs:
        # `project` is a kind and a pack: the kind's fields matter more
        others = [c.kind for c in reg.packs[t].kinds if c.kind != t]
        more = f"\nThe {t} pack also has: {' '.join(others)} (uea help {others[0]})"
        return kind_help(reg.kinds[t]) + (more if others else "")
    if t in reg.packs:
        return pack_help(reg, t)
    if t in reg.kinds:
        return kind_help(reg.kinds[t])
    if t == "type":
        return "\n\n".join(kind_help(c) for c in reg.types.values())
    if t.startswith("type:") and t[5:] in reg.types:
        return kind_help(reg.types[t[5:]])
    return None

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
    (
        "uea calc [name] [scope]",
        "calculators, e.g. calc wofl; their norm tables: uea data (help calc)",
    ),
    ("uea render <level>", "plan image (PNG) to look at (help export)"),
    ("uea export <format> [scope]", "for humans: pdf, dxf, xlsx, ifc, svg, png, bcf (help export)"),
    ("uea import ifc <file> --by <who>", "an architect's IFC into arch (help import)"),
    ("uea log [n]", "recent batches"),
    ("uea help [topic]", "this help, or a topic"),
)
"""Every command with a one-line description: the root help and docs/reference.md."""

TOPICS = (
    "start | ops | positions | arch | elec | heat | plumb | vent | struct | <kind> | codes | calc"
    " | export | import"
)

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
Holes (Durchbrüche, Kernbohrungen, Schlitze) answer the services' requests: their checks say
where a pipe, duct or facade terminal passes a wall or slab without one.
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

HEAT_NOTES = """\
src= says where an element gets its heat: a tank from a generator, a manifold from a tank or a
generator, underfloor heating from a manifold, a radiator from any of them. The types carry the
manufacturer's data. Derived (uea get): the loops of each underfloor heating (its area over the
spacing, plus the way to the manifold and back, each loop within max=), each manifold's loops
against its outlets, each emitter's output, and the pipes from each generator and tank (a
tree over what it supplies; a home run from a manifold to each radiator on it). Whether the
emitters cover each room's Heizlast, and the generators the building's: uea calc heatload.
Pipe sizes, valve settings and pump heads: uea calc hydronic (help calc).
Pipes that change storey pass the slab through a hole: via= on their tank, generator or
manifold names it; ask arch for one with a request.
"""

PLUMB_NOTES = """\
The pipes are derived, not written: cold water from the meter, through a riser to the other
storeys (each riser and stack through a hole in the slab); hot water from the nearest tank in
heat.uea whose type is dhw; waste water from each fixture to its stack (to=, else the nearest on
its storey) or the sewer connection, down the stack and under the floor to the sewer. Each
network is the shortest tree over the rectilinear distances, a lower bound like the cables. uea
get shows each fixture's way. Pipe sizes: uea calc water and uea calc drain (help calc).
"""

VENT_NOTES = """\
A central unit's terminals take its air: sup and ext in the rooms, oda and eha on an exterior
wall. The ducts are derived like the pipes: from the unit, the shortest tree over its terminals
of each kind of air. A decentral unit goes through an exterior wall; pair= joins a push-pull
pair, the other side is derived. The flows the rooms need, and whether the system gives them:
uea calc airflow; duct sizes and the fans' pressure: uea calc ducts (help calc). Ducts that
change storey pass the slab through a hole, via= on the unit; units and terminals on the facade
through a hole in the wall. Ask arch for them with a request.
"""

STRUCT_NOTES = """\
The load path is the architecture's: a slab rests on the load-bearing walls (lb) of the storey
below, a load-bearing wall on those of the storey below its core overlaps. struct.uea adds what
the architecture does not give: beams where a wall or a slab has no wall under it, and point or
line loads the rooms' uses do not cover. Sections and strengths are rows of the office's tables.
The roof rests on the walls under its eaves. uea calc loads: the loads and their takedown; uea
calc struct: the Statische Berechnung, every position proved (help calc); uea export pdf
struct:<level>: the Positionsplan. The signature is the Tragwerksplaner's.
"""

CALC = """\
uea calc                list calculators
uea calc wofl [level]   Wohnfläche per WoFlV (norm). Writes out/wofl.md.
uea calc cable method=B2 [scope] [insulation=PVC temp=<C> group=<n> arrangement=<a>]
                        each circuit's cable against its breaker, In <= Iz (norm). Iz from the
                        office's table ampacity; temp-factor with temp=, group-factor with group=
uea calc vdrop limit=<%> [scope] [reserve=1.2 cos=1 demand=1 current=auto|in]
                        voltage drop from the board to the farthest device (norm; table
                        conductor). Length: the derived cable length (uea get c1) times reserve
uea calc equip grade=<g> [scope] [combos=one|each]
                        each room's sockets, lighting, data outlets and connections against its
                        minimum (DIN 18015-2, norm; table elec-minimum by use, grade and area).
                        Scope: a storey or a room. A waiver of W-ELEC-010 on a room accepts it
uea calc uvalue [scope] U-value of each build-up as the rooms use it (norm; tables material,
                        surface). Scope: a room or a type
uea calc heatload tb=<W/m2K> n50=<1/h> shielding=none|moderate|heavy [scope]
                  [groundwater=deep|shallow te=<C> tme=<C>]
                        Heizlast room by room (norm). tb: thermal bridge surcharge. Scope: a
                        storey or a room. Room temperatures by use and theta_e by postcode come
                        from the office's tables (uea data)
uea calc water [building=residential]
                        drinking-water pipe sizes and each fixture's pressure (norm). Flows by
                        fixture, the peak flow and vmax from the office's tables; the supply
                        pressure from the meter, the pipes from the pipe type
uea calc drain slope=<%> [building=residential]
                        waste-water pipe sizes and the branch lengths (norm); slope: the pipes
                        under the building
uea calc hydronic tb= n50= shielding= spread=<K> vmax=<m/s>
                        heating pipe sizes and the hydraulic balance on each room's Heizlast
                        (norm): valve and kv per circuit, throttles, pump heads
uea calc airflow n50=<1/h> insulation=high|low
                        the dwelling's air flows (DIN 1946-6, norm), whether a ventilation
                        measure is needed, each room's flow against the units in vent.uea
uea calc ducts n50= insulation= vmax=<m/s>
                        duct sizes of the central units and each side's fan pressure (norm)
uea calc loads [soil=<kN/m²> sk=<kN/m²> qp=<kN/m²>]
                        the loads of the slabs, roofs, beams and walls, their takedown to the
                        foundation and the line loads on the footings (DIN EN 1991, norm); sk,
                        qp: the site's snow load and wind pressure, needed with a roof; soil=
                        the soil's design resistance gives each footing's width
uea calc struct [soil= sk= qp=]
                        the Statische Berechnung (norm): slabs as plates and beams on the solver
                        PyNite (pip install 'uea[struct]'), masonry walls (DIN EN 1996-3),
                        lintels from the office's table, footings; one line per position
Scope of cable and vdrop: a circuit, an RCD or a board. All if left out. Settings are
name=value after the name.
Norm tables come from the office's own licensed copies and are not in UEA: uea data lists them,
uea data show <id> gives the columns, uea data add <id> <file.csv> --edition <e> installs one.
Without a table the calculator stops and names it.
Results say calculator, kind (norm or custom), version, settings and the edition of each table. A
custom result is never norm-compliant. Project calculators live in calc/ (custom).
"""

EXPORT = """\
uea render <level> [-o file]        working plan (PNG) with element ids, for you to look at
uea export pdf|dxf [name] [-o f]    sheets for humans, A3 1:100 or larger: a floor plan per storey
                                    (name: a level), a section per section (its name) and the four
                                    facades (north|east|south|west), with dimensions and height
                                    marks; all if none is given. Electrical: elec (all),
                                    elec:<level> (installation plan, 1:50), a board id (its
                                    single-line diagram with phases and the field in rows).
                                    Heating: heat (all), heat:<level>, heat:schema (the
                                    Heizungs- und Trinkwasserschema). Plumbing: plumb,
                                    plumb:<level> (fixtures and the derived pipes), plumb:schema
                                    (the Strangschema). Ventilation: vent, vent:<level>.
                                    Structure: struct:<level> (the Positionsplan)
uea export pdf <result>             a calculation report to sign: out/<result>.md on A4 (e.g.
                                    heatload, struct); refused if the model changed since uea calc
uea export xlsx [level] [-o file]   tables: rooms, walls, openings, slabs, roofs, stairs,
                                    quantities, electrical, emitters, manifolds, fixtures, pipes,
                                    ventilation units, air terminals, ducts
uea export ifc [-o file]            IFC4 model for humans and other software
uea export bcf [discipline] [-o f]  requests to that discipline (default arch) as BCF 2.1 topics
uea export svg|png [name] [-o f]    the same sheet as a picture, to check what the PDF shows
Files go to out/ unless -o says otherwise; the output names them. Sections: + section A x=W+5 look=w
(uea help section). Sheets and tables are labelled in German, for the people who read them. The
title block stays unsigned: a human signs.
"""

IMPORT = """\
uea import ifc <file> --by <who> [-m why] [--dry-run] [--building name]   an architect's IFC
Mapped: storeys (levels), grids along x or y, walls (an axis through the core, a type from the
layers; top= the roof they end under; curtain walls get windows over their face), doors, windows
niches and holes (a position on their wall), one floor slab per storey (its finish is fb and a
floor type) and its openings (voids; over= the stair below; round ones and rectangles up to
0.25 m² are holes), stairs and roofs whose faces fit a UEA stair
or roof, spaces (rooms; use from the names; a sep where two spaces meet with no wall). The rest is
listed as not imported, with the reason. One building per import; a plan far from the origin or
turned is moved and turned (noted). Errors the import causes in the model are listed, not
blocking: fix them with a batch. The same project again with a newer file: elements nobody has
edited since are updated, new ones added, ones the file lost removed, the rest listed as kept:.
Ids stay. UEA's own exports are refused: the model is where the project lives. Requests to the
architect: uea export bcf.
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
    if pack == "heat":
        lines.append(HEAT_NOTES.rstrip())
    if pack == "plumb":
        lines.append(PLUMB_NOTES.rstrip())
    if pack == "vent":
        lines.append(VENT_NOTES.rstrip())
    if pack == "struct":
        lines.append(STRUCT_NOTES.rstrip())
    if p.kinds:
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
        "import": IMPORT,
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

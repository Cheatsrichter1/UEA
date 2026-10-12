# UEA reference

Every command, operation, element kind, type, issue code and calculator UEA has today.
Generated from the code by `uv run python -m uea.reference`; do not edit it by hand, a test
fails when it is out of date. Agents get the same facts in layers through `uea help`.

## Commands

| Command | What it does |
|---|---|
| `uea init <dir>` | new project |
| `uea show [scope]` | summary: project, EG, arch, arch:EG, or an id |
| `uea get <id>...` | elements with derived values |
| `uea find <kind> [filters]` | find wall ext lb · find door room=r3 · find win level=OG |
| `uea apply --by <who> -m <why>` | atomic batch of operations from stdin (help ops) |
| `uea revert <batch> --by <who>` | undo a batch as a new batch |
| `uea check [discipline]` | open issues, requests and waivers |
| `uea calc [name] [scope]` | calculators, e.g. calc wofl; their norm tables: uea data (help calc) |
| `uea render <level>` | plan image (PNG) to look at (help export) |
| `uea export <format> [scope]` | for humans: pdf, dxf, xlsx, ifc, svg, png, bcf (help export) |
| `uea import ifc <file> --by <who>` | an architect's IFC into arch (help import) |
| `uea log [n]` | recent batches |
| `uea help [topic]` | this help, or a topic |

Full syntax. Every command also takes `-C <dir>` and `--json`.

```
uea help [topic]
uea version
uea init dir
uea show [scope]
uea get id [id ...]
uea find [--skip N] [--ids] kind [filters ...]
uea apply [--by WHO] [-m WHY] [-f FILE] [--dry-run]
uea revert [--by WHO] [-m WHY] batch
uea check [discipline]
uea log [n]
uea calc [name] [scope|name=value ...]
uea data [--edition E] [--source S] [action] [rest ...]
uea render [-o FILE] scope [view]
uea export [-o FILE] format [scope]
uea import [--by WHO] [-m WHY] [--dry-run] [--building NAME] format file
```

## Operations

```
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
```

## Positions and heights

```
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
```

## Element kinds and types

One element per line: `kind id positional... "label" key=value... flags`. Levels, grids and types carry a name you choose; UEA assigns the ids of everything else.

### Project, levels and grids (`project.uea`)

Kinds: `project`, `level`, `grid`.

#### `project`

The project, one per project: project <name> "title" site=DE-HE postcode=64283 ground=-0.3 north=12

`project <name>`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| site | `site=` |  | country and state as ISO 3166-2, e.g. DE-HE |
| postcode | `postcode=` |  | postcode |
| ground | `ground=` | m | terrain height relative to ±0.00, the ground storey's FFL |
| north | `north=` | ° | true north, clockwise from the plan's +y axis; plans get a north arrow |

#### `level`

A storey. z is its FFL (finished floor level, OKFF); its SSL (structural slab level, OK Rohdecke) is z - fb. Windows hang from head (Sturzhöhe).

`level <name>`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| z | `z=` | m | FFL; ±0.00 is the FFL of the ground storey (required) |
| fb | `fb=` | m | floor build-up: FFL minus SSL |
| head | `head=` | m | head height: window heads above the FFL |

#### `grid`

A grid line: x= for a line along y, y= for a line along x.

`grid <name>`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| x | `x=` | m | x of a grid line running along y |
| y | `y=` | m | y of a grid line running along x |

### Architecture (`arch.uea`)

Types: `type … wall`, `type … slab`, `type … floor`, `type … roof`, `type … win`, `type … door`.

Kinds: `wall`, `door`, `win`, `niche`, `slab`, `void`, `hole`, `roof`, `stair`, `sep`, `room`, `section`.

#### `type … wall`

Wall build-up, inside to outside (interior walls: -x/-y face first). The core layer (*) is what wall positions refer to: layers=plaster:0.015,*brick:0.365,render:0.02

`type <name> wall`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| layers | `layers=` |  | material:thickness in m, comma-separated; * marks the core (required) |

#### `type … slab`

Slab build-up, top to bottom. The core top is the storey's SSL: layers=*concrete:0.25,xps:0.14

`type <name> slab`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| layers | `layers=` |  | material:thickness in m, comma-separated; * marks the core (required) |

#### `type … floor`

Floor build-up on a slab, top to bottom (Fußbodenaufbau, the level's fb): layers=parquet:0.015,screed:0.065,eps:0.07

`type <name> floor`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| layers | `layers=` |  | material:thickness in m, comma-separated (required) |

#### `type … roof`

Roof build-up, outside to inside. The core is the rafter layer: layers=tiles:0.04,battens:0.07,*rafters:0.18

`type <name> roof`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| layers | `layers=` |  | material:thickness in m, comma-separated; * marks the core (required) |

#### `type … win`

Window type. A window without type= uses the type marked default.

`type <name> win`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| uw | `uw=` | W/(m²K) | Uw |
| default | flag `default` | | used by windows without type= |

#### `type … door`

Door type. A door without type= uses the type marked default.

`type <name> door`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| ud | `ud=` | W/(m²K) | Ud |
| uw | `uw=` | W/(m²K) | Uw of a glazed door |
| default | flag `default` | | used by doors without type= |

#### `wall`

A wall. One of x=/y= is its position (a core face, e.g. y=S+ or x=w4+2.26), the other its span (x=W..E, y=w1..w3); or a=/b=, the points x,y its axis runs between, in any direction. on= stacks it on a wall below.

`wall <id> <level> <type>` · ids `w1`, `w2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey |
| type | positional |  | wall type |
| x | `x=` | m | x position (anchor±d) or span (a..b) |
| y | `y=` | m | y position (anchor±d) or span (a..b) |
| a | `a=` |  | start of the axis, a point x,y (wall in any direction) |
| b | `b=` |  | end of the axis, a point x,y (wall in any direction) |
| on | `on=` |  | same footprint as this wall |
| top | `top=` |  | roof that cuts the wall's top |
| h | `h=` | m | height above the SSL, if not up to the slab above |
| lb | flag `lb` | | load-bearing |
| flip | flag `flip` | | reverse the layer order |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `door`

A door in a wall. Stands on the FFL. into= is the room it opens into; hand= its handing (l or r as DIN links/rechts, seen from that room).

`door <id> <host> <size>` · ids `d1`, `d2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall |
| size | positional | m | structural opening width x height (Rohbaurichtmaß) |
| x | `x=` | m | edge position along a wall running along x |
| y | `y=` | m | edge position along a wall running along y |
| s | `s=` | m | edge position along a wall in any direction, from its start a |
| sill | `sill=` | m | bottom above the FFL, if not on the floor |
| into | `into=` |  | room the leaf opens into |
| hand | `hand=` | `l` `r` | handing: l or r, seen from the into room |
| type | `type=` |  | door type; default type if left out |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `win`

A window in a wall. It hangs from the storey's head height (head=); sill= only if it deviates.

`win <id> <host> <size>` · ids `f1`, `f2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall |
| size | positional | m | structural opening width x height (Rohbaurichtmaß) |
| x | `x=` | m | edge position along a wall running along x |
| y | `y=` | m | edge position along a wall running along y |
| s | `s=` | m | edge position along a wall in any direction, from its start a |
| sill | `sill=` | m | sill height above the FFL, if not from head |
| type | `type=` |  | window type; default type if left out |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `niche`

A niche in one face of a wall (host w5.n), d deep.

`niche <id> <host> <size>` · ids `ni1`, `ni2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall face, e.g. w5.n |
| size | positional | m | structural opening width x height (Rohbaurichtmaß) |
| x | `x=` | m | edge position along a wall running along x |
| y | `y=` | m | edge position along a wall running along y |
| s | `s=` | m | edge position along a wall in any direction, from its start a |
| sill | `sill=` | m | bottom above the FFL |
| d | `d=` | m | depth into the wall (required) |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `slab`

The slab under a storey; its top is the storey's SSL. Its outline comes from the walls below it (the storey's own walls for the lowest slab).

`slab <id> <level> <type>` · ids `sl1`, `sl2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey it carries |
| type | positional |  | slab type |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `void`

An opening in a slab: over a stair (over=st1) or given by x= and y= spans.

`void <id> <slab>` · ids `v1`, `v2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| slab | positional |  | slab |
| over | `over=` |  | stair whose footprint it opens |
| x | `x=` | m | x span |
| y | `y=` | m | y span |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `hole`

An opening without a fill (Durchbruch, Kernbohrung, Schlitz), the answer to a request: through a wall (x=, y= or s= its edge, sill= its bottom), a chase in a wall face (host w6.e, d= its depth), or through a slab (at= its centre, size along x and y). round: a core drilling, the size its diameter twice: 0.18x0.18.

`hole <id> <host> <size>` · ids `ho1`, `ho2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall, wall face (a chase) or slab |
| size | positional | m | width x height in a wall; x by y in a slab |
| x | `x=` | m | edge position along a wall running along x |
| y | `y=` | m | edge position along a wall running along y |
| s | `s=` | m | edge position along a wall in any direction, from its start a |
| at | `at=` | m | centre in a slab |
| sill | `sill=` | m | bottom above the FFL, in a wall |
| d | `d=` | m | depth of a chase into its wall face |
| round | flag `round` | | round (a core drilling) |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `roof`

A roof over a storey's outline, or the rectangle x= y= (roofs of a storey are one roof: L, T). gable (Satteldach, ridge=x|y; halfhip=<run> hips the ends, Krüppelwalm), shed (Pultdach, up= the side it rises to), hip (Walmdach; a square gives a Zeltdach), mansard (pitch up to rise= above the eaves, then upper=; ridge=x|y gables the ends), flat (knee= is its underside). knee: underside of the rafters at the outer face of the eaves wall, above the storey's SSL (Kniestock). Derived: eaves height (top of the roof skin above the outer wall face) and ridge height.

`roof <id> <level> <type> <shape>` · ids `rf1`, `rf2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey the roof sits on |
| type | positional |  | roof type |
| shape | positional | `gable` `shed` `hip` `mansard` `flat` | gable, shed, hip, mansard or flat |
| ridge | `ridge=` | `x` `y` | ridge direction of a gable or mansard roof |
| up | `up=` | `n` `s` `e` `w` | side a shed roof rises to |
| pitch | `pitch=` | ° | roof pitch, of a mansard below the break; not for flat |
| halfhip | `halfhip=` | m | horizontal run of the hipped ends of a gable roof |
| upper | `upper=` | ° | pitch of a mansard roof above the break |
| rise | `rise=` | m | height of a mansard roof's break above the eaves |
| knee | `knee=` | m | rafter underside at the eaves wall's outer face, above the SSL |
| eave | `eave=` | m | overhang at the eaves |
| verge | `verge=` | m | overhang at the verge |
| x | `x=` | m | x span of the rectangle it covers, if not the outline |
| y | `y=` | m | y span of the rectangle it covers, if not the outline |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `stair`

A stair between two storeys: straight, or shape=l|u (quarter, half turn) with a landing, or winders=. x=/y= place its footprint like a wall; up= is the direction the first flight climbs; n risers, n-1 treads.

`stair <id> <level> <to>` · ids `st1`, `st2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey it starts on |
| to | positional |  | storey it arrives at |
| x | `x=` | m | x position of the footprint (required) |
| y | `y=` | m | y position of the footprint (required) |
| up | `up=` | `n` `s` `e` `w` | direction the first flight climbs (required) |
| w | `w=` | m | width (required) |
| n | `n=` |  | number of risers (required) |
| tread | `tread=` | m | tread depth (required) |
| shape | `shape=` | `straight` `l` `u` | straight, l (quarter turn), u (half turn) |
| turn | `turn=` | `l` `r` | which way the second flight turns, seen while climbing |
| n1 | `n1=` |  | risers of the first flight, up to the turn (default: half) |
| winders | `winders=` |  | winder treads in the turn instead of a landing (shape l) |
| gap | `gap=` | m | well between the two flights, shape u (default 0.1) |
| status | flag | `existing` `demolish` `temp` | status; new unless flagged existing (Bestand), demolish or temp |

#### `sep`

A room separation line without a wall (open kitchen): a position on one axis, a span on the other.

`sep <id> <level>` · ids `rs1`, `rs2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey |
| x | `x=` | m | x position or span |
| y | `y=` | m | y position or span |

#### `room`

A room: the region around the seed point at= bounded by walls and separators.

`room <id> <level> <use>` · ids `r1`, `r2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey |
| use | positional | `living` `dining` `kitchen` `bedroom` `office` `bath` `wc` `hall` `utility` `storage` `laundry` `technical` `cellar` `attic` `garage` `other` | use; decides e.g. whether it counts as Wohnfläche |
| at | `at=` | m | seed point inside the room (required) |
| floor | `floor=` |  | floor type |
| tile | `tile=` | m | wall tiling height above the FFL |

#### `section`

A section (Schnitt A-A): a vertical cut through the building at x= or y=. Name it A, B (uea help export).

`section <name>`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| x | `x=` | m | x of a cut across x (the cut plane runs along y) |
| y | `y=` | m | y of a cut across y (the cut plane runs along x) |
| look | `look=` | `n` `s` `e` `w` | viewing direction: e or w for x=, n or s for y=; default e for x=, n for y= |

### Structure (`struct.uea`)

Kinds: `beam`, `load`.

#### `beam`

A beam (Unterzug) under the slab of a storey: beam bm1 OG HEB-160 a=w6,w1+1 b=w6,w5. It carries that slab and the walls of the storey that stand on it, and rests on the load-bearing walls of the storey below that it crosses. section: a row of the office's beam-section table.

`beam <id> <level> <section>` · ids `bm1`, `bm2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey whose slab it carries |
| section | positional |  | section, a name in the office's beam-section table |
| a | `a=` |  | start of its axis, a point x,y (required) |
| b | `b=` |  | end of its axis, a point x,y (required) |

#### `load`

A load on the slab of a storey: load lo1 OG g=3 at=w4+0.5,w5+0.5 "Pufferspeicher 300 l" (a point load, kN), or a=/b= for a line load (kN/m). g permanent, q imposed, characteristic.

`load <id> <level>` · ids `lo1`, `lo2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey whose slab carries it |
| g | `g=` | kN or kN/m | permanent part, characteristic |
| q | `q=` | kN or kN/m | imposed part, characteristic |
| at | `at=` |  | a point load: where it stands |
| a | `a=` |  | a line load: the start of its line |
| b | `b=` |  | a line load: the end of its line |

### Luminaires (`light.uea`)

Types: `type … lum`.

Kinds: `lum`.

#### `type … lum`

Luminaire type. A luminaire without type= uses the type marked default.

`type <name> lum`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| flux | `flux=` | lm | luminous flux |
| w | `w=` | W | power |
| dist | `dist=` |  | light distribution for the photometric calculation, e.g. cos1, cos3 |
| default | flag `default` | | used by luminaires without type= |

#### `lum`

A luminaire. In a room (host r2): at= a point, z= its height; by default the middle of the room at the ceiling. On a wall (host w1.s): x=/y= along it, z= its height.

`lum <id> <host>` · ids `l1`, `l2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room, or wall face |
| at | `at=` | m | point in the room, x,y |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction |
| z | `z=` | m | height of its centre above the FFL |
| type | `type=` |  | luminaire type; default type if left out |

### Electrical (`elec.uea`)

Kinds: `board`, `rcd`, `circ`, `sock`, `conn`, `switch`, `data`, `smoke`, `feed`.

#### `board`

A distribution board on a wall: board b1 w6.w y=w3-0.6 z=1.4 main=SLS-E35 meters=1. media: a media distribution board (Medienverteiler) for the data outlets.

`board <id> <host>` · ids `b1`, `b2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| main | `main=` |  | main switch, e.g. SLS-E35 |
| spd | `spd=` |  | surge protection, e.g. T1+T2 |
| meters | `meters=` |  | electricity meters |
| media | flag `media` | | a media distribution board |

#### `rcd`

A residual current device (Fehlerstromschutzschalter) in a board: rcd fi1 b1 40/0.03 A, rated A / residual A, then its type (AC, A, F or B).

`rcd <id> <board> <rating> <type>` · ids `fi1`, `fi2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| board | positional |  | distribution board |
| rating | positional | A | rated current / residual current |
| type | positional | `AC` `A` `F` `B` | RCD type |

#### `circ`

A circuit behind an RCD: circ c1 fi1 NYM-J5x2.5 B16 p=3 "Küche Herd". p= phases (1 or 3). Its connected load is the luminaires, connections and feeds on it.

`circ <id> <rcd> <cable> <breaker>` · ids `c1`, `c2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| rcd | positional |  | RCD that protects it |
| cable | positional |  | cable designation, type, cores x mm² |
| breaker | positional |  | circuit breaker: characteristic and rated current |
| p | `p=` |  | phases, 1 or 3 |

#### `sock`

A socket box on a wall: sock s4 w4 c4 y=f2+0.3 z=1.15 n=2. z= is 0.3 if left out; n= the outlets in its frame.

`sock <id> <host> <circuit>` · ids `s1`, `s2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| circuit | positional |  | circuit |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| n | `n=` |  | outlets in the frame |

#### `conn`

A fixed connection (Anschluss) for an appliance: conn a1 w4 c1 y=w1+0.9 z=0.6 "Herd". w= its power, counted in the circuit's load.

`conn <id> <host> <circuit>` · ids `a1`, `a2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| circuit | positional |  | circuit |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| w | `w=` | W | connected power |

#### `switch`

A light switch: switch sw2 w5.s c10 x=d2+0.15 ctl=l2,l3. ctl= the luminaires it controls: , separates channels, + joins luminaires of one channel. A luminaire with two switches is a two-way circuit, with three an intermediate one. dim: a dimmer.

`switch <id> <host> <circuit>` · ids `sw1`, `sw2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| circuit | positional |  | circuit |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| ctl | `ctl=` |  | luminaires it controls: l1 or l2,l3 or l15+l16 (required) |
| dim | flag `dim` | | a dimmer |

#### `data`

A data outlet (network, antenna) cabled to a distribution board: data dt1 w2 b2 y=w5-0.75 n=2.

`data <id> <host> <board>` · ids `dt1`, `dt2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| board | positional |  | distribution board it is cabled to |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| n | `n=` |  | ports in the frame |

#### `smoke`

A smoke alarm (Rauchwarnmelder) in a room, at the ceiling: smoke rm1 r5. at= a point.

`smoke <id> <host>` · ids `rm1`, `rm2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room |
| at | `at=` | m | point in the room, x,y; default the middle |
| z | `z=` | m | height above the FFL; default the ceiling |

#### `feed`

A circuit feeding an element of another discipline (a heat pump, a fan): feed fd1 g1 c7. w= its power, counted in the circuit's load.

`feed <id> <target> <circuit>` · ids `fd1`, `fd2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| target | positional |  | the powered element |
| circuit | positional |  | circuit |
| w | `w=` | W | connected power |

### Heating (`heat.uea`)

Types: `type … gen`, `type … tank`, `type … man`, `type … ufh`, `type … rad`, `type … hpipe`.

Kinds: `gen`, `tank`, `man`, `ufh`, `rad`.

#### `type … gen`

Heat generator type: type WP-8 gen kw=8 source=air dp=120. kw: heat output at the design outdoor temperature and flow temperature; dp: its loss on the heating side, for uea calc hydronic; from the manufacturer.

`type <name> gen`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| kw | `kw=` | kW | heat output at the design point (required) |
| source | `source=` | `air` `ground` `water` `gas` `oil` `wood` `district` `electric` | heat source: air, ground, water (heat pumps), gas, oil, wood, district, electric |
| dp | `dp=` | hPa | its pressure loss on the heating side at the design flow |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … tank`

Storage tank type: type HM-200 tank vol=200 dhw dp=150 (dhw: heats drinking water; dp: its pressure loss on the drinking-water side at the design flow, for uea calc water).

`type <name> tank`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| vol | `vol=` | l | volume (required) |
| dp | `dp=` | hPa | drinking-water pressure loss at the design flow |
| default | flag `default` | | used by elements of its kind without type= |
| dhw | flag `dhw` | | heats drinking water |

#### `type … man`

Manifold type (Heizkreisverteiler): type HKV-10 man outlets=10 w=0.55.

`type <name> man`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| outlets | `outlets=` |  | heating circuits it can connect (required) |
| w | `w=` | m | width of its cabinet |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … ufh`

Underfloor heating type (Fußbodenheizung): type FBH-15 ufh spacing=0.15 q=60 max=100 pipe=16x2 k=0.007. q: heat output per m² at the system's design temperatures and the floor covering, from the manufacturer; max: the longest loop, connection lines included; pipe, k: the loop's pipe and its roughness, for uea calc hydronic.

`type <name> ufh`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| spacing | `spacing=` | m | pipe spacing (required) |
| q | `q=` | W/m² | heat output per floor area (required) |
| max | `max=` | m | longest loop, with its connection lines (required) |
| pipe | `pipe=` | mm | the loop's pipe, outer diameter x wall |
| k | `k=` | mm | roughness of the loop's pipe |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … rad`

Radiator type: type HK-22 rad w=1100 length=1 height=0.6. w: heat output at the system's design temperatures, from the manufacturer.

`type <name> rad`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| w | `w=` | W | heat output at the design temperatures (required) |
| length | `length=` | m | length |
| height | `height=` | m | height |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … hpipe`

Heating pipe system, for the pipes between generators, tanks, manifolds and radiators: type CU hpipe sizes=15x1,18x1,22x1,28x1.5 k=0.0015 bend=0.5 tee=1.3 default. k: roughness; bend, tee: loss coefficients ζ, from the manufacturer.

`type <name> hpipe`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| sizes | `sizes=` | mm | sizes from small to large, outer diameter x wall (required) |
| k | `k=` | mm | roughness of the pipe wall (required) |
| bend | `bend=` |  | loss coefficient ζ of a bend (required) |
| tee | `tee=` |  | loss coefficient ζ of a tee (required) |
| default | flag `default` | | used by elements of its kind without type= |

#### `gen`

A heat generator (heat pump, boiler) on a storey, inside or outside: gen g1 EG at=W-1.2,N-1 type=WP-8 "Wärmepumpe außen".

`gen <id> <level>` · ids `g1`, `g2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey |
| at | `at=` | m | plan point x,y (required) |
| z | `z=` | m | height above the FFL |
| type | `type=` |  | generator type; default if left out |
| via | `via=` |  | slab holes or voids its pipes change storey through |

#### `tank`

A storage tank (or a heat pump's indoor unit with one) in a room: tank t1 r3 at=w4+0.4,w5+0.4 src=g1. at= default the middle of the room.

`tank <id> <host>` · ids `t1`, `t2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room |
| at | `at=` | m | plan point x,y |
| src | `src=` |  | generator that heats it |
| type | `type=` |  | tank type; default if left out |
| via | `via=` |  | slab holes or voids its pipes change storey through |

#### `man`

A manifold (Heizkreisverteiler) in a niche, or on a wall face like a device: man hv1 ni1 t1, man hv2 w12.n g1 x=w15+0.5 z=0.6.

`man <id> <host> <src>` · ids `hv1`, `hv2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | niche, or wall face |
| src | positional |  | tank or generator it gets its heat from |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction |
| z | `z=` | m | height of its centre above the FFL |
| type | `type=` |  | manifold type; default if left out |
| via | `via=` |  | slab holes or voids its pipes change storey through |

#### `ufh`

Underfloor heating over a room's floor, from a manifold: ufh uh1 r1 hv1. area= the heated part, if not the whole finished floor.

`ufh <id> <room> <src>` · ids `uh1`, `uh2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| room | positional |  | room |
| src | positional |  | manifold |
| area | `area=` | m² | heated floor area |
| type | `type=` |  | type; default if left out |

#### `rad`

A radiator (Heizkörper) on a wall face: rad hk1 w1 hv1 x=f1. z= its centre, 0.45 if left out.

`rad <id> <host> <src>` · ids `hk1`, `hk2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| src | positional |  | manifold, tank or generator |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| type | `type=` |  | type; default if left out |

### Plumbing (`plumb.uea`)

Types: `type … pipe`, `type … drain`.

Kinds: `san`, `meter`, `riser`, `stack`, `sewer`.

#### `type … pipe`

Drinking-water pipe system: type MV pipe sizes=16x2,20x2.25,26x3 k=0.007 bend=1.4 tee=1.7. k: roughness; bend, tee: loss coefficients ζ of a bend and of a tee (the branch), from the manufacturer.

`type <name> pipe`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| sizes | `sizes=` | mm | sizes from small to large, outer diameter x wall (required) |
| k | `k=` | mm | roughness of the pipe wall (required) |
| bend | `bend=` |  | loss coefficient ζ of a bend (required) |
| tee | `tee=` |  | loss coefficient ζ of a tee (required) |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … drain`

Drain pipe system: type HT drain sizes=50:50x1.8,70:75x1.9,100:110x2.7 (DN, then outer diameter x wall). The stack's type serves its branches too, the sewer's the pipes under the building.

`type <name> drain`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| sizes | `sizes=` | mm | sizes from small to large, DN:outer diameter x wall (required) |
| default | flag `default` | | used by elements of its kind without type= |

#### `san`

A sanitary fixture on a wall face (san sa1 w4 sink y=f2.c) or in a room (san sa7 r9 shower at=w15-0.45,w10-0.45). Fixtures: basin, sink, wc, urinal, bidet, shower, bath, wm (washing machine), dw (dishwasher), tap (outside tap), floor (floor drain). z= its outlet; to= the stack or sewer its waste runs to, else the nearest on its storey.

`san <id> <host> <fixture>` · ids `sa1`, `sa2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall face, or room |
| fixture | positional | `basin` `sink` `wc` `urinal` `bidet` `shower` `bath` `wm` `dw` `tap` `floor` | what it is |
| at | `at=` | m | point in the room, x,y |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction |
| z | `z=` | m | height of its water outlet above the FFL |
| water | `water=` | `cold` `both` `none` | cold, both (cold and hot) or none; by fixture if left out |
| to | `to=` |  | stack or sewer its waste water runs to |

#### `meter`

Where the drinking water enters, with its meter (Wasserzähler): meter wz1 r3 at=w4+0.3,w3-0.3 p=4 dp=450. p: the lowest supply pressure the water supplier states; dp: the loss of the meter, filter and the other apparatus at the design flow.

`meter <id> <host>` · ids `wz1`, `wz2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room |
| at | `at=` | m | plan point x,y; the middle of the room if left out |
| z | `z=` | m | height above the FFL |
| p | `p=` | bar | lowest supply pressure |
| dp | `dp=` | hPa | pressure loss of the meter and apparatus |
| type | `type=` |  | pipe system; the default pipe type if left out |

#### `riser`

A riser (Steigleitung) for cold and hot water, from a room up through the storeys above: riser sr1 r3 at=w4+0.2,w3-1. Fixtures on other storeys than the meter get their water through it.

`riser <id> <host>` · ids `sr1`, `sr2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room on its lowest storey |
| at | `at=` | m | plan point x,y; the middle of the room if left out |

#### `stack`

A stack (Fallleitung) with its vent through the roof, from a room up through the storeys above: stack fl1 r3 at=w4+0.15,w3-1.6. Its foot runs to the sewer.

`stack <id> <host>` · ids `fl1`, `fl2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room on its lowest storey |
| at | `at=` | m | plan point x,y; the middle of the room if left out |
| type | `type=` |  | drain pipe system; the default drain type if left out |

#### `sewer`

Where the waste water leaves the building for the public sewer (an inspection chamber or the wall it passes): sewer kn1 EG at=W-2,N-2. The pipes to it run under the storey's floor.

`sewer <id> <level>` · ids `kn1`, `kn2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey whose floor the pipes run under |
| at | `at=` | m | plan point x,y (required) |
| type | `type=` |  | drain pipe system; the default drain type if left out |

### Ventilation (`vent.uea`)

Types: `type … ahu`, `type … fan`, `type … duct`.

Kinds: `ahu`, `fan`, `air`.

#### `type … ahu`

Central ventilation unit type (Lüftungsgerät mit Wärmerückgewinnung): type KWL-250 ahu flow=250 dp=150 hr=0.85. flow: the largest air flow; dp: the external pressure it delivers at that flow, for each side; hr: heat recovery; from the manufacturer.

`type <name> ahu`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| flow | `flow=` | m³/h | largest air flow (required) |
| dp | `dp=` | Pa | external pressure at that flow |
| hr | `hr=` |  | heat recovery efficiency, 0 to 1 |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … fan`

Decentral unit type (dezentrales Lüftungsgerät, Abluftventilator): type DZ-160 fan flow=30 hr=0.8. flow: its air flow at the nominal level, through the unit; from the manufacturer.

`type <name> fan`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| flow | `flow=` | m³/h | air flow at the nominal level (required) |
| hr | `hr=` |  | heat recovery efficiency, 0 to 1 |
| default | flag `default` | | used by elements of its kind without type= |

#### `type … duct`

Round duct system: type R duct sizes=80,100,125,160 k=0.15 bend=0.3 tee=0.6 default (inner diameters, mm). k: roughness; bend, tee: loss coefficients ζ, from the manufacturer.

`type <name> duct`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| sizes | `sizes=` | mm | inner diameters from small to large (required) |
| k | `k=` | mm | roughness of the duct wall (required) |
| bend | `bend=` |  | loss coefficient ζ of a bend (required) |
| tee | `tee=` |  | loss coefficient ζ of a tee (required) |
| default | flag `default` | | used by elements of its kind without type= |

#### `ahu`

A central ventilation unit with heat recovery in a room: ahu lg1 r3 at=w4+0.5,w3-0.4. at= default the middle of the room; z= its duct connections above the FFL.

`ahu <id> <host>` · ids `lg1`, `lg2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room |
| at | `at=` | m | plan point x,y |
| z | `z=` | m | height of its duct connections above the FFL |
| type | `type=` |  | unit type; default if left out |
| via | `via=` |  | slab holes or voids its ducts change storey through |

#### `fan`

A decentral unit through an exterior wall: fan vl1 w11 y=w12-0.5 pair=vl2. mode: alt (push-pull, in pairs; the default), ext (exhaust fan), both (supplies and extracts at once). pair= the other unit of a push-pull pair; the other side is derived. z= 2.2 if left out.

`fan <id> <host>` · ids `vl1`, `vl2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | wall; for an interior wall its face too: w5.s |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction, from its start a |
| z | `z=` | m | height of its centre above the FFL |
| mode | `mode=` | `alt` `ext` `both` | alt (push-pull pair), ext (exhaust) or both |
| pair | `pair=` |  | the other unit of its push-pull pair |
| type | `type=` |  | unit type; default if left out |

#### `air`

An air terminal of a central unit (Luftdurchlass): in a room for supply or extract air (air ld1 r2 sup at=w2-1.5,w1+2; at= default the middle, z= default the ceiling), or on an exterior wall for outdoor or exhaust air (air ld9 w4 oda y=w3-1 z=2.4). role: sup, ext, oda (outdoor air in), eha (exhaust air out). src= its unit; the only or nearest if left out.

`air <id> <host> <role>` · ids `ld1`, `ld2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| host | positional |  | room, or wall for oda and eha |
| role | positional | `sup` `ext` `oda` `eha` | sup, ext, oda or eha |
| at | `at=` | m | plan point in the room, x,y |
| x | `x=` | m | centre along a wall running along x |
| y | `y=` | m | centre along a wall running along y |
| s | `s=` | m | centre along a wall in any direction |
| z | `z=` | m | height of its centre above the FFL |
| src | `src=` |  | its central unit |

### Requests and waivers (`issues.uea`)

Kinds: `req`, `waive`.

#### `req`

A request from one discipline to the owner of its targets: req _ elec w7 "Schlitz 10x5". Open until the owner sets done (~ q1 done) or rejected="reason".

`req <id> <disc> <targets>` · ids `q1`, `q2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| disc | positional | `arch` `struct` `light` `elec` `heat` `plumb` `vent` | discipline that asks |
| targets | positional |  | elements the request is about |
| done | `done=` |  | batch that resolved it |
| rejected | `rejected=` |  | reason the owner rejected it |

#### `waive`

An issue accepted on purpose: waive _ W-ELEC-010 r5 "Wunsch Bauherr" by=elektroplaner. Reports list every waiver.

`waive <id> <code> <target>` · ids `wv1`, `wv2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| code | positional |  | issue code, e.g. W-ARCH-005 |
| target | positional |  | element the issue is on |
| by | `by=` |  | who accepted it |

## Issue codes

E is an error, W a warning.

| Code | Meaning |
|---|---|
| E-REF-001 | reference to an element that does not exist |
| E-REF-002 | reference against the discipline graph (references only point upstream) |
| E-REF-003 | reference to an element of the wrong kind |
| E-GEO-001 | position cannot be resolved |
| E-GEO-002 | depends on an element whose position cannot be resolved |
| E-GEO-003 | positions refer to each other in a cycle |
| W-ISSUE-001 | waiver that matches no issue |
| E-ARCH-001 | opening or hole outside its wall |
| E-ARCH-002 | openings or holes overlap in one wall |
| E-ARCH-003 | opening or hole higher than its wall |
| E-ARCH-004 | door opens into a room that is not next to it |
| W-ARCH-005 | door handing incomplete (into= without hand= or the other way round) |
| E-ARCH-006 | window sill below the FFL |
| E-ARCH-007 | niche or chase as deep as its wall or deeper |
| E-ARCH-008 | new opening or hole in a demolished wall |
| W-ARCH-010 | wall without a height yet (no storey or roof above) |
| E-ARCH-011 | walls overlap |
| E-ARCH-020 | room seed not in a free region |
| E-ARCH-021 | two rooms in one region |
| W-ARCH-022 | region without a room |
| W-ARCH-023 | room floor build-up differs from the storey's fb |
| E-ARCH-030 | slab without an outline |
| W-ARCH-031 | two slabs on one storey |
| W-ARCH-032 | void or hole outside its slab |
| W-ARCH-033 | stair runs into a slab without a void |
| W-ARCH-034 | stair outside the step rule 2h+a = 0.59-0.65 m (Schrittmaßregel) |
| W-ARCH-035 | stair not inside a room |
| E-ARCH-040 | roof without an outline |
| W-ARCH-041 | roof outline is not a rectangle |
| W-ARCH-042 | part of the outline is under no roof |
| E-ARCH-043 | roof shape does not fit its rectangle |
| W-ARCH-050 | two default types in one category |
| W-ARCH-051 | door or window without type and no default type |
| W-ARCH-060 | section outside the building (it cuts no wall) |
| W-STRUCT-001 | load-bearing wall that stands on no load-bearing wall of the storey below |
| W-STRUCT-002 | slab with no load-bearing wall under it |
| W-STRUCT-003 | beam that rests on fewer than two load-bearing walls |
| W-STRUCT-004 | hole in a slab over the wall that carries the slab |
| E-LIGHT-002 | luminaire on a wall without a usable face |
| E-ELEC-001 | device outside its host wall |
| E-ELEC-002 | device on a wall without a usable face |
| E-ELEC-003 | device in an opening of its wall |
| W-ELEC-004 | device closer than 0.1 m to an opening |
| E-ELEC-005 | device below the floor or above the top of its wall |
| E-ELEC-006 | device on a demolished wall |
| E-ELEC-011 | switch controls something that is not a luminaire |
| W-ELEC-012 | switch on the hinge side of a door, where the open leaf covers it |
| W-ELEC-020 | connected load larger than the circuit breaker carries |
| W-ELEC-022 | circuit that feeds nothing |
| W-ELEC-030 | luminaire that no switch controls |
| W-ELEC-031 | luminaire switched from more than one circuit |
| W-ELEC-040 | distribution board without an RCD |
| E-HEAT-002 | manifold or radiator on a wall without a usable face |
| W-HEAT-001 | heating element without a type, and none of its kind is marked default |
| W-HEAT-002 | manifold with more loops than outlets |
| W-HEAT-003 | underfloor heating too far from its manifold for a loop |
| W-HEAT-004 | generator, tank or manifold that supplies nothing (a tank that heats drinking water supplies the hot water) |
| W-HEAT-005 | pipes that change storey through a slab with no hole for them |
| E-PLUMB-002 | fixture on a wall without a usable face |
| W-PLUMB-001 | fixture that takes water, and there is no meter |
| W-PLUMB-002 | fixture that takes hot water, and no storage tank heats drinking water |
| W-PLUMB-003 | fixture whose waste water has nowhere to go |
| W-PLUMB-004 | riser or stack that nothing runs through |
| W-PLUMB-005 | a second meter or sewer connection; the first one serves |
| W-PLUMB-006 | pipe that passes a slab with no hole for it |
| E-VENT-002 | unit or terminal on a wall without a usable face, or outdoor or exhaust air in a room |
| W-VENT-001 | ventilation unit without a type, and none of its kind is marked default |
| W-VENT-002 | push-pull unit without a matching pair |
| W-VENT-003 | decentral unit, or outdoor or exhaust air terminal, not on an exterior wall |
| W-VENT-004 | air terminal with no central unit |
| W-VENT-005 | central unit without outdoor air, exhaust air, supply or extract terminals |
| W-VENT-006 | decentral unit, or outdoor or exhaust air terminal, with no hole through its wall |
| W-VENT-007 | ducts that change storey through a slab with no hole for them |

## Calculators

Projects add `custom` calculators in `calc/`. A `custom` result is never presented as norm-compliant. A calculator that needs norm tables stops and names the one that is missing; the office installs its tables with `uea data add` from its own licensed copy (`docs/decisions/0008-office-supplied-norm-data.md`). Settings are written `name=value` after the calculator's name and are recorded in the result.

| Name | Kind | Version | Standard | What it computes |
|---|---|---|---|---|
| `wofl` | norm | 0.1.0 | WoFlV vom 25.11.2003 | Wohnfläche per WoFlV |
| `cable` | norm | 0.1.0 | DIN VDE 0100-430 (433.1), DIN VDE 0100-520, DIN VDE 0298-4 | Leitungsquerschnitt (Überlastschutz) |
| `vdrop` | norm | 0.1.0 | DIN VDE 0100-520 (IEC 60364-5-52, Anhang G) | Spannungsfall der Stromkreise |
| `equip` | norm | 0.1.0 | DIN 18015-2 | Mindestausstattung (DIN 18015-2) |
| `uvalue` | norm | 0.1.0 | DIN EN ISO 6946:2018-03 | U-Werte der Bauteile |
| `heatload` | norm | 0.2.0 | DIN EN 12831-1:2017-09 mit DIN/TS 12831-1:2020-04 | Heizlast raumweise |
| `hydronic` | norm | 0.1.1 | Verfahren B des hydraulischen Abgleichs; Heizlast nach DIN EN 12831-1:2017-09 | Rohrnetz und hydraulischer Abgleich |
| `water` | norm | 0.1.0 | DIN 1988-300:2012-05 | Trinkwasser-Rohrbemessung |
| `drain` | norm | 0.1.0 | DIN 1986-100:2016-12 mit DIN EN 12056-2 | Schmutzwasser-Rohrbemessung |
| `airflow` | norm | 0.1.0 | DIN 1946-6:2019-12 | Lüftungskonzept und Luftvolumenströme |
| `ducts` | norm | 0.1.1 | Luftvolumenströme nach DIN 1946-6:2019-12; Druckverlust nach Darcy-Weisbach | Luftleitungen |
| `loads` | norm | 0.2.0 | DIN EN 1991-1-1:2010-12, DIN EN 1991-1-3:2010-12, DIN EN 1991-1-4:2010-12, je mit NA; DIN EN 1990:2010-12 mit NA | Lastannahmen und Lastabtrag |
| `struct` | norm | 0.1.0 | DIN EN 1996-3:2010-12 mit NA (Mauerwerk, vereinfachtes Verfahren); DIN EN 1992-1-1:2011-01 mit NA (Biegebemessung der Decken); DIN EN 1993-1-1, DIN EN 1995-1-1 mit NA (Unterzüge); Lasten: DIN EN 1991-1-1:2010-12, DIN EN 1991-1-3:2010-12, DIN EN 1991-1-4:2010-12, je mit NA; DIN EN 1990:2010-12 mit NA | Statische Berechnung |

### `cable` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `method` | str | required | installation method as your ampacity table names it, e.g. B2 |
| `insulation` | str | PVC | insulation of the cables (PVC / XLPE) |
| `temp` | float |  | ambient temperature in °C; left out: the table's reference |
| `group` | int | 1 | circuits grouped together; 1: no grouping factor |
| `arrangement` | str |  | how they are grouped, as your group-factor table names it |

### `vdrop` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `limit` | float | required | the permissible voltage drop of the circuit, in % of 230 V |
| `reserve` | float | 1.2 | factor on the derived length, for the route on site |
| `cos` | float | 1.0 | power factor of the load, more than 0 and at most 1 |
| `demand` | float | 1.0 | share of In taken as the current of a circuit with sockets, more than 0 and at most 1 |
| `current` | str | auto | auto: declared load if the circuit has no socket, else In times demand; in: always In (auto / in) |

### `equip` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `grade` | str | required | the equipment grade the client chose, as your table names it |
| `combos` | str | one | a socket or data frame with several outlets counts as one, or each outlet counts (one / each) |

### `heatload` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `tb` | float | required | thermal bridge surcharge ΔU_TB, W/(m²K), on the outer surfaces |
| `n50` | float | required | air change rate at 50 Pa the building is to meet, 1/h |
| `shielding` | str | required | shielding of the building (none / moderate / heavy) |
| `groundwater` | str | deep | groundwater under the building (deep / shallow) |
| `te` | float |  | θ_e in °C instead of the table outdoor |
| `tme` | float |  | θ_m,e in °C instead of the table outdoor |

### `hydronic` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `tb` | float | required | thermal bridge surcharge ΔU_TB, W/(m²K), on the outer surfaces |
| `n50` | float | required | air change rate at 50 Pa the building is to meet, 1/h |
| `shielding` | str | required | shielding of the building (none / moderate / heavy) |
| `groundwater` | str | deep | groundwater under the building (deep / shallow) |
| `te` | float |  | θ_e in °C instead of the table outdoor |
| `tme` | float |  | θ_m,e in °C instead of the table outdoor |
| `spread` | float | required | design spread between flow and return, K |
| `vmax` | float | required | the highest velocity in the heating pipes, m/s |

### `water` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `building` | str | residential | building use, a row of the table peak-flow |

### `drain` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `slope` | float | required | slope of the pipes under the building, % |
| `building` | str | residential | building use, a row of the table drain-k |

### `airflow` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `n50` | float | required | air change rate at 50 Pa the building is to meet, 1/h |
| `insulation` | str | required | thermal insulation of the building (high / low) |

### `ducts` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `n50` | float | required | air change rate at 50 Pa the building is to meet, 1/h |
| `insulation` | str | required | thermal insulation of the building (high / low) |
| `vmax` | float | required | the highest air velocity in the ducts, m/s |

### `loads` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `soil` | float |  | design resistance of the soil σ_R,d under strip footings, kN/m², from the geotechnical report |
| `sk` | float |  | characteristic snow load on the ground s_k at the site, kN/m² (DIN EN 1991-1-3/NA, the snow load zone and the altitude); needed with a roof |
| `qp` | float |  | peak velocity pressure q_p at the roof's height, kN/m² (DIN EN 1991-1-4/NA, the wind zone and the terrain); needed with a roof |

### `struct` settings

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `soil` | float |  | design resistance of the soil σ_R,d under strip footings, kN/m², from the geotechnical report |
| `sk` | float |  | characteristic snow load on the ground s_k at the site, kN/m² (DIN EN 1991-1-3/NA, the snow load zone and the altitude); needed with a roof |
| `qp` | float |  | peak velocity pressure q_p at the roof's height, kN/m² (DIN EN 1991-1-4/NA, the wind zone and the terrain); needed with a roof |

### Norm tables

One CSV file for each table, the first line the header: `uea data add <id> <file.csv> --edition <e>`. Comma or semicolon separated; with a semicolon, a decimal comma is read. Numbers must be more than 0 unless the column says otherwise. No two rows may have the same key.

#### `ampacity`: Current-carrying capacity Iz (DIN VDE 0298-4)

Copper conductors. One row for each installation method, insulation, number of loaded conductors and cross-section the office uses.

| Column | Type | Meaning |
|---|---|---|
| `method` | text | reference installation method as the table names it: A1, B2, C, ... |
| `insulation` | text | insulation of the cable (one of PVC, XLPE) |
| `loaded` | num > 0 | loaded conductors: 2 (single-phase) or 3 (three-phase) |
| `mm2` | num > 0 | conductor cross-section, mm² |
| `amps` | num > 0 | current-carrying capacity at reference conditions, A |

One row for each: method, insulation, loaded, mm2.

#### `temp-factor`: Correction factor for the ambient temperature (DIN VDE 0298-4)

Needed only when the calculation is run with temp=<°C>.

| Column | Type | Meaning |
|---|---|---|
| `insulation` | text | insulation of the cable (one of PVC, XLPE) |
| `celsius` | num > 0 | ambient temperature, °C |
| `factor` | num > 0 | factor for Iz |

One row for each: insulation, celsius.

#### `group-factor`: Correction factor for grouped circuits (DIN VDE 0298-4)

Needed only when the calculation is run with group=<n> above 1.

| Column | Type | Meaning |
|---|---|---|
| `arrangement` | text | how they are grouped, as the table names it |
| `circuits` | num > 0 | number of circuits in the group |
| `factor` | num > 0 | factor for Iz |

One row for each: arrangement, circuits.

#### `conductor`: Conductor data for the voltage drop (DIN VDE 0100-520 (IEC 60364-5-52, Annex G))

One row for copper (cables NYM, NYY, ...) and one for aluminium (cables starting NA) if used.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | conductor material (one of Cu, Al) |
| `rho` | num > 0 | resistivity of the conductor in service, Ω·mm²/m |
| `lambda` | num > 0 | reactance of the cable per length, mΩ/m |

One row for each: material.

#### `elec-minimum`: Minimum electrical equipment of a room (DIN 18015-2)

One row per use, grade and area range. A use with no rows is not checked.

| Column | Type | Meaning |
|---|---|---|
| `use` | text | room use as UEA names it: living, kitchen, bedroom, ... |
| `grade` | text | equipment grade as the office's table names it, e.g. 1, 2, 3 |
| `upto` | num > 0 | finished floor area up to, m²; the last row of a use covers any area |
| `sock` | num ≥ 0 | socket outlets |
| `light` | num ≥ 0 | lighting outlets |
| `data` | num ≥ 0 | communication outlets (telephone, data, TV) |
| `conn` | num ≥ 0 | dedicated connections (cooker, washing machine, ...) |

One row for each: use, grade, upto.

#### `material`: Thermal conductivity of building materials (DIN 4108-4, DIN EN ISO 10456, or the manufacturer's declared design value)

One row for each material in layers= of the types, e.g. ziegel-t9 for *ziegel-t9:0.365.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | the material name as the layers of the types write it |
| `lambda` | num > 0 | design thermal conductivity λ, W/(m·K) |

One row for each: material.

#### `surface`: Surface resistances (DIN EN ISO 6946)

Three rows: up, horizontal, down.

| Column | Type | Meaning |
|---|---|---|
| `flow` | text | direction of the heat flow (one of up, horizontal, down) |
| `rsi` | num > 0 | internal surface resistance R_si, m²·K/W |
| `rse` | num > 0 | external surface resistance R_se, m²·K/W |

One row for each: flow.

#### `outdoor`: Design outdoor temperature by postcode (DIN/TS 12831-1)

One row for each postcode the office plans in, or only the project's.

| Column | Type | Meaning |
|---|---|---|
| `postcode` | text | postcode, as in postcode= of the project |
| `te` | num | design outdoor temperature θ_e, °C |
| `tme` | num | annual mean outdoor temperature θ_m,e, °C |

One row for each: postcode.

#### `room-temp`: Internal temperature and minimum air change by room use (DIN/TS 12831-1)

One row for each use the rooms of the project have.

| Column | Type | Meaning |
|---|---|---|
| `use` | text | room use, as UEA names it (one of living, dining, kitchen, bedroom, office, bath, wc, hall, utility, storage, laundry, technical, cellar, attic, garage, other) |
| `heated` | text | whether rooms of this use are heated (one of yes, no) |
| `ti` | num | internal design temperature θ_int, or of the unheated space, °C |
| `nmin` | num ≥ 0 | minimum air change rate n_min, 1/h |

One row for each: use.

#### `infiltration`: Shielding coefficient e (DIN EN 12831-1, DIN/TS 12831-1)

| Column | Type | Meaning |
|---|---|---|
| `openings` | text | outside walls with windows or doors the room has (one of 0, 1, 2+) |
| `shielding` | text | shielding of the building (one of none, moderate, heavy) |
| `e` | num ≥ 0 | shielding coefficient e |

One row for each: openings, shielding.

#### `height-factor`: Height correction factor ε (DIN EN 12831-1, DIN/TS 12831-1)

| Column | Type | Meaning |
|---|---|---|
| `upto` | num > 0 | height of the room's middle above the terrain up to which it holds, m |
| `eps` | num > 0 | height correction factor ε |

One row for each: upto.

#### `heatload-factors`: Factors of the Heizlast (DIN EN 12831-1, DIN/TS 12831-1)

fg1: annual variation of the outdoor temperature for the ground; gw-deep, gw-shallow: G_w with the groundwater deeper or less deep than the standard's limit; rho-cp: heat capacity of air per volume, Wh/(m³·K).

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which factor (one of fg1, gw-deep, gw-shallow, rho-cp) |
| `value` | num > 0 | its value |

One row for each: name.

#### `fixture-flow`: Design flow and minimum flow pressure by fixture (DIN 1988-300)

One row for each fixture the project has.

| Column | Type | Meaning |
|---|---|---|
| `fixture` | text | fixture, as UEA names it (one of basin, sink, wc, urinal, bidet, shower, bath, wm, dw, tap, floor) |
| `vr-cold` | num ≥ 0 | design flow V̇_R of cold water, l/s |
| `vr-hot` | num ≥ 0 | design flow V̇_R of hot water, l/s |
| `pmin` | num ≥ 0 | minimum flow pressure p_min,Fl, hPa |

One row for each: fixture.

#### `peak-flow`: Peak flow constants by building use (DIN 1988-300)

V̇_S = a · (ΣV̇_R)^b − c.

| Column | Type | Meaning |
|---|---|---|
| `building` | text | building use, as building= of the calculator names it |
| `a` | num > 0 | constant a |
| `b` | num > 0 | constant b |
| `c` | num ≥ 0 | constant c |

One row for each: building.

#### `water-factors`: Limits of the drinking-water sizing (DIN 1988-300)

vmax: the highest flow velocity in the pipes, m/s.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which value (one of vmax) |
| `value` | num > 0 | its value |

One row for each: name.

#### `fixture-drain`: Discharge unit and branch size by fixture (DIN 1986-100)

One row for each fixture the project has.

| Column | Type | Meaning |
|---|---|---|
| `fixture` | text | fixture, as UEA names it (one of basin, sink, wc, urinal, bidet, shower, bath, wm, dw, tap, floor) |
| `du` | num > 0 | discharge unit DU, l/s |
| `dn` | num > 0 | DN of its single branch |

One row for each: fixture.

#### `drain-k`: Frequency factor K by building use (DIN 1986-100)

| Column | Type | Meaning |
|---|---|---|
| `building` | text | building use, as building= of the calculator names it |
| `k` | num > 0 | frequency factor K |

One row for each: building.

#### `drain-branch`: Unvented collecting branches (DIN 1986-100)

| Column | Type | Meaning |
|---|---|---|
| `dn` | num > 0 | DN |
| `qmax` | num > 0 | the highest Q_ww it may carry, l/s |
| `lmax` | num > 0 | the longest it may be, m |

One row for each: dn.

#### `drain-stack`: Stacks with main vent (DIN 1986-100)

| Column | Type | Meaning |
|---|---|---|
| `dn` | num > 0 | DN |
| `qmax` | num > 0 | the highest Q_ww it may carry, l/s |

One row for each: dn.

#### `drain-factors`: Values of the drainage sizing (DIN 1986-100)

single-lmax: the longest unvented branch to one fixture, m; kb: the roughness of the pipes under the building, mm; fill: the highest filling h/d they may run at.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which value (one of single-lmax, kb, fill) |
| `value` | num > 0 | its value |

One row for each: name.

#### `vent-total`: Total air flow of the dwelling by ventilation level (DIN 1946-6)

q_v,ges = f · (a · A_NE² + b · A_NE + c), m³/h, with A_NE in m².

| Column | Type | Meaning |
|---|---|---|
| `level` | text | fl-high, fl-low (by insulation), rl, nl or il (one of fl-high, fl-low, rl, nl, il) |
| `a` | num | a, m³/h per m⁴ |
| `b` | num | b, m³/h per m² |
| `c` | num | c, m³/h |
| `f` | num > 0 | factor f |

One row for each: level.

#### `vent-room`: Air flows by room use (DIN 1946-6)

One row for each use the rooms of the project have.

| Column | Type | Meaning |
|---|---|---|
| `use` | text | room use, as UEA names it (one of living, dining, kitchen, bedroom, office, bath, wc, hall, utility, storage, laundry, technical, cellar, attic, garage, other) |
| `role` | text | supply, extract, overflow, or none (not in the dwelling) (one of supply, extract, overflow, none) |
| `extract` | num ≥ 0 | extract flow of an extract room at the nominal level, m³/h |
| `fr` | num ≥ 0 | factor of a supply room for its share of the supply air |

One row for each: use.

#### `vent-infiltration`: Infiltration of the dwelling (DIN 1946-6)

q_v,inf = komp · V_NE · n_50 · (lage · dp / 50)^n, m³/h; dp in Pa.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which factor (one of komp, lage, dp, n) |
| `value` | num > 0 | its value |

One row for each: name.

#### `unit-weight`: Unit weights of building materials (DIN EN 1991-1-1, Anhang A, or the manufacturer)

One row for each material the load-bearing walls, slabs, floors, partitions and roofs name. A layer of rafters with insulation between them: the weight of both, smeared over the layer.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | material, as the layers name it |
| `gamma` | num > 0 | unit weight γ, kN/m³ |

One row for each: material.

#### `imposed-load`: Imposed loads on floors by room use (DIN EN 1991-1-1/NA, Tabelle 6.1DE)

One row for each use the rooms of the project have.

| Column | Type | Meaning |
|---|---|---|
| `use` | text | room use, as UEA names it (one of living, dining, kitchen, bedroom, office, bath, wc, hall, utility, storage, laundry, technical, cellar, attic, garage, other) |
| `qk` | num ≥ 0 | imposed load q_k, kN/m² |

One row for each: use.

#### `partition-load`: Surcharge for light partitions (DIN EN 1991-1-1, 6.3.1.2(8), with NA)

A partition heavier than the last row is a line load on its slab.

| Column | Type | Meaning |
|---|---|---|
| `upto` | num > 0 | weight of the partition up to, kN/m |
| `qk` | num > 0 | surcharge on the imposed load, kN/m² |

One row for each: upto.

#### `struct-factors`: Partial factors and design settings (DIN EN 1990/NA, Tabelle NA.A.1.2(B); DIN EN 1996-1-1/NA, 2.4.3, 3.7.1; DIN EN 1996-3/NA, 4.2.2.3; DIN EN 1992-1-1/NA, 2.4.2.4, 3.1.6, 3.2)

gamma-g, gamma-q: γ_G and γ_Q; gamma-g-inf: γ_G of a favourable permanent action (the uplift of a roof); gamma-m: γ_M of the masonry; zeta: ζ for the long-term strength of masonry; rho2: ρ_2 of a wall held by slabs at both ends; gamma-c, alpha-cc: γ_C and α_cc of concrete; gamma-s: γ_S and fyk: f_yk (N/mm²) of the reinforcing steel; d1: the distance of the reinforcement's axis from the face of a slab, m. Each calculation needs the rows it uses.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which value (one of gamma-g, gamma-q, gamma-g-inf, gamma-m, zeta, rho2, gamma-c, alpha-cc, gamma-s, fyk, d1) |
| `value` | num > 0 | its value |

One row for each: name.

#### `struct-psi`: Combination factors ψ0 (DIN EN 1990/NA, Tabelle NA.A.1.1)

imposed: the imposed loads of the rooms (category A); snow at the site's altitude; wind.

| Column | Type | Meaning |
|---|---|---|
| `action` | text | variable action (one of imposed, snow, wind) |
| `psi0` | num ≥ 0 | ψ0 |

One row for each: action.

#### `snow-shape`: Snow load shape coefficient μ1 of a roof by its pitch (DIN EN 1991-1-3, 5.3.2 and Tabelle 5.2, with NA)

Rows from 0° up to the steepest pitch of the project; between rows UEA interpolates.

| Column | Type | Meaning |
|---|---|---|
| `pitch` | num ≥ 0 | roof pitch, ° |
| `mu1` | num ≥ 0 | shape coefficient μ1 |

One row for each: pitch.

#### `wind-roof`: External pressure coefficients of a roof by its pitch (DIN EN 1991-1-4, 7.2.3 to 7.2.6, with NA)

The coefficients the office takes for the load of a roof plane on the walls under its eaves (its choice of zone, e.g. H); between rows UEA interpolates.

| Column | Type | Meaning |
|---|---|---|
| `pitch` | num ≥ 0 | roof pitch, ° |
| `pressure` | num ≥ 0 | c_pe,10 for pressure on the roof (0 if none) |
| `suction` | num | c_pe,10 for suction, negative |

One row for each: pitch.

#### `beam-section`: Sections of beams (the manufacturer's tables or DIN EN 10365 (steel), DIN EN 14080 (glued laminated timber))

One row for each section the beams name.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | the section, as the beam names it |
| `material` | text | a material of the beam-material table |
| `w` | num > 0 | section modulus W_y, cm³ |
| `i` | num > 0 | second moment of area I_y, cm⁴ |
| `av` | num > 0 | shear area A_v, cm² |
| `g` | num > 0 | weight, kN/m |

One row for each: name.

#### `struct-limits`: Limits of the methods (DIN EN 1996-3/NA, 4.2.1.1; DIN EN 1992-1-1/NA, 5.4(NA.5); DIN EN 1990/NA, A.1.4 with the office's choice of deflection limit)

building-height (m), span (the largest span of the slabs on a wall, m), qk (kN/m²) and clear-height (m): the conditions of the simplified method for masonry; xi: the largest x/d of a slab without a check of its rotation; deflection: n of the limit L/n of a beam.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | which limit (one of building-height, span, qk, clear-height, xi, deflection) |
| `value` | num > 0 | its value |

One row for each: name.

#### `masonry`: Characteristic compressive strength of masonry (DIN EN 1996-1-1/NA, NA.D, or the national technical approval of the unit)

One row for each material the cores of the load-bearing walls name.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | the material of a wall's core layer |
| `fk` | num > 0 | f_k of the unit with its mortar, N/mm² |

One row for each: material.

#### `masonry-end`: Reduction factor Φ2 of a wall at the end support of a slab (DIN EN 1996-3/NA, 4.2.2.3)

For the strength class of the project's masonry; a span longer than the last row is outside the table.

| Column | Type | Meaning |
|---|---|---|
| `upto` | num > 0 | span of the slab l_f up to, m |
| `phi` | num > 0 | Φ2 |

One row for each: upto.

#### `concrete`: Concrete of slabs (DIN EN 1992-1-1, Tabelle 3.1, for the strength class the office specifies)

One row for each material the cores of the slabs name.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | the material of a slab's core layer |
| `fck` | num > 0 | f_ck, N/mm² |
| `ecm` | num > 0 | E_cm, N/mm² |

One row for each: material.

#### `lintel`: Lintels over openings in load-bearing walls (the manufacturer's load tables (allgemeine bauaufsichtliche Zulassung))

UEA takes, for each opening, the first type in the table's order that carries the load over the span in a wall of that thickness.

| Column | Type | Meaning |
|---|---|---|
| `type` | text | the lintel, for the report |
| `t` | num > 0 | the thickness of wall core it is for, m |
| `span` | num > 0 | clear span up to, m |
| `qrd` | num > 0 | design load it carries at that span, kN/m |

One row for each: type, t, span.

#### `beam-material`: Strengths of the materials of beams (DIN EN 1993-1-1/NA (steel), DIN EN 1995-1-1/NA and DIN EN 14080 (timber))

f_d = k_mod · f_k / γ_M for bending and shear.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | the material, as the beam-section table names it |
| `fk` | num > 0 | bending strength f_y or f_m,k, N/mm² |
| `fvk` | num > 0 | shear strength f_y/√3 or f_v,k, N/mm² |
| `e` | num > 0 | modulus of elasticity, N/mm² |
| `gamma` | num > 0 | partial factor γ_M |
| `kmod` | num > 0 | k_mod for the load duration of the design (1 for steel) |

One row for each: material.

## Exports

`uea export` writes `ifc`, `xlsx`, `pdf`, `dxf`, `svg`, `png`, `bcf`; `uea render` writes a PNG plan image for agents. Files go to `out/`. Drawings are labelled in German, for the people who read them.

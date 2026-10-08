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
| `uea calc [name] [scope]` | calculators, e.g. calc wofl (help calc) |
| `uea render <level>` | plan image (PNG) to look at (help export) |
| `uea export <format> [scope]` | for humans: ifc, svg, png (help export) |
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
uea calc [name] [scope]
uea render [-o FILE] scope [view]
uea export [-o FILE] format [scope]
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

The project, one per project: project <name> "title" site=DE-HE postcode=64283 ground=-0.3

`project <name>`

| Field | Written as | Values | Meaning |
|---|---|---|---|
| site | `site=` |  | country and state as ISO 3166-2, e.g. DE-HE |
| postcode | `postcode=` |  | postcode |
| ground | `ground=` | m | terrain height relative to ±0.00, the ground storey's FFL |

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

Kinds: `wall`, `door`, `win`, `niche`, `slab`, `void`, `roof`, `stair`, `sep`, `room`.

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

#### `roof`

A roof over a storey's outline, or the rectangle x= y= (roofs of a storey are one roof: L, T). gable (Satteldach, ridge=x|y), shed (Pultdach, up= the side it rises to), hip (Walmdach). knee: underside of the rafters at the outer face of the eaves wall, above the storey's SSL (Kniestock). Derived: eaves height (top of the roof skin above the outer wall face) and ridge height.

`roof <id> <level> <type> <shape>` · ids `rf1`, `rf2`, … assigned by UEA

| Field | Written as | Values | Meaning |
|---|---|---|---|
| level | positional |  | storey the roof sits on |
| type | positional |  | roof type |
| shape | positional | `gable` `shed` `hip` | gable, shed or hip |
| ridge | `ridge=` | `x` `y` | ridge direction of a gable roof |
| up | `up=` | `n` `s` `e` `w` | side a shed roof rises to |
| pitch | `pitch=` | ° | roof pitch (required) |
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
| E-ARCH-001 | opening outside its wall |
| E-ARCH-002 | openings overlap in one wall |
| E-ARCH-003 | opening higher than its wall |
| E-ARCH-004 | door opens into a room that is not next to it |
| W-ARCH-005 | door handing incomplete (into= without hand= or the other way round) |
| E-ARCH-006 | window sill below the FFL |
| E-ARCH-007 | niche as deep as its wall or deeper |
| E-ARCH-008 | new opening in a demolished wall |
| W-ARCH-010 | wall without a height yet (no storey or roof above) |
| E-ARCH-011 | walls overlap |
| E-ARCH-020 | room seed not in a free region |
| E-ARCH-021 | two rooms in one region |
| W-ARCH-022 | region without a room |
| W-ARCH-023 | room floor build-up differs from the storey's fb |
| E-ARCH-030 | slab without an outline |
| W-ARCH-031 | two slabs on one storey |
| W-ARCH-032 | void outside its slab |
| W-ARCH-033 | stair runs into a slab without a void |
| W-ARCH-034 | stair outside the step rule 2h+a = 0.59-0.65 m (Schrittmaßregel) |
| W-ARCH-035 | stair not inside a room |
| E-ARCH-040 | roof without an outline |
| W-ARCH-041 | roof outline is not a rectangle |
| W-ARCH-042 | part of the outline is under no roof |
| W-ARCH-050 | two default types in one category |
| W-ARCH-051 | door or window without type and no default type |

## Calculators

Projects add `custom` calculators in `calc/`. A `custom` result is never presented as norm-compliant.

| Name | Kind | Version | Standard | What it computes |
|---|---|---|---|---|
| `wofl` | norm | 0.1.0 | WoFlV vom 25.11.2003 | Wohnfläche per WoFlV |

## Exports

`uea export` writes `ifc`, `svg`, `png`; `uea render` writes a PNG plan image for agents. Files go to `out/`. Drawings are labelled in German, for the people who read them.

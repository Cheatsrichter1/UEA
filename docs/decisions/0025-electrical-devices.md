# 0025: The electrical pack, slice 1: devices, circuits and checks

Status: Accepted (slice 1 built; slice 2 in 0026; slice 3a in 0027; slice 3b in 0028)
Date: 2026-10-09

## Context

Phase 3 of `ROADMAP.md` is the electrical design. It is large, so it goes in three slices that each end with something a human can open (the order was agreed with the user on 2026-10-09):

1. **The pack and its checks** (this record): the kinds, placement on walls, circuits and loads, validators, XLSX tables.
2. **The Installationsplan per storey** as PDF and DXF with simplified symbols, and the Verteilungsplan.
3. **Cable lengths and the first `norm` calculators** (voltage drop, cable sizing) on tables the office supplies (`0008-office-supplied-norm-data.md`).

Haus Müller's draft (`docs/prototype/haus-mueller/elec.uea`, `light.uea`) already wrote the electrics in the format; the slice builds that.

## Decision

**Kinds** (`elec.uea`, ids assigned by UEA). The positions are anchors like an opening's; `x=sw1+0.071` is one frame past the switch sw1.

| Kind | Id | Line |
|---|---|---|
| `board` | `b` | `board b1 w6.w y=w3-0.6 z=1.4 main=SLS-E35 spd=T1+T2 meters=1`, `media` for a Medienverteiler |
| `rcd` | `fi` | `rcd fi1 b1 40/0.03 A`: rated A / residual A, then AC, A, F or B |
| `circ` | `c` | `circ c1 fi1 NYM-J5x2.5 B16 p=3 "Küche Herd"` |
| `sock` | `s` | `sock s4 w4 c4 y=f2+0.3 z=1.15 n=2` |
| `conn` | `a` | `conn a1 w4 c1 y=w1+0.9 z=0.6 w=7000`: a fixed connection |
| `switch` | `sw` | `switch sw2 w5.s c10 x=d2+0.15 ctl=l2,l3`, `dim` for a dimmer |
| `data` | `dt` | `data dt1 w2 b2 y=w5-0.75 n=2`: cabled to a board |
| `smoke` | `rm` | `smoke rm1 r5`: in a room, at the ceiling |
| `feed` | `fd` | `feed fd1 g1 c7`: a circuit feeding an element of another discipline |

The light pack holds the luminaires, as `0006-pack-order.md` says: `type … lum` (`flux`, `w`, `dist`, `default`) and `lum l1 r1` (in a room, `at=` and `z=`, by default the middle at the ceiling) or `lum l7 w1.s x=d5-0.3 z=2.4` (on a wall). `illum` (illuminance targets) belongs to the later light design and is not built.

**Values.** A cable is its designation, `NYM-J3x2.5` (type, cores, mm²), a breaker `B16`, an RCD `40/0.03`; they are parsed, not defined as types. The standard library of FUTURE.md would add data (current-carrying capacity) later. `p=3` needs a cable with four or five cores.

**Placement** (`packs/mount.py`, shared by electrical devices and luminaires):

- A device stands on one face of a wall. A wall with an outside takes it on the room side; a wall with a room on each side needs its face (`w5.n`); anything else is E-ELEC-002.
- The position along the wall is `x=`, `y=` or `s=` like an opening's, the centre of the device. Heights are the centre above the FFL: sockets and data 0.3 and switches 1.05 when `z=` is left out, boards and luminaires on a wall need `z=`.
- Its room is the room 5 cm in front of its face. A luminaire or smoke alarm hung in a room is at its ceiling, from the room's own clear height.
- **A luminaire's circuit is its switches'.** The `ctl=` of a switch lists the luminaires it controls: `,` separates channels, `+` joins the luminaires of a channel. The circuit of the switches is the luminaire's circuit, and the number of switches gives the kind of circuit: one single, two a two-way (Wechselschaltung), three or more an intermediate (Kreuzschaltung). A luminaire with no switch, or switches on two circuits, is a warning.
- **The load of a circuit** is its luminaires (`w` of their type), the `w=` of its connections and the `w=` of its feeds, against breaker × 230 V × phases. Sockets carry no declared load. This is arithmetic on the numbers written down; it is not a cable calculation and not the Gleichzeitigkeit of a norm.

**Checks.** Our own planning rules, in code constants, not a norm's: a clause is only cited where a check implements it.

| Code | Meaning |
|---|---|
| E-ELEC-001 | the device lies outside its wall |
| E-ELEC-002 | the face is missing or is not a face of the wall |
| E-ELEC-003 | the frame overlaps an opening of the wall (the message gives `x=d1+0.15`) |
| W-ELEC-004 | its centre is closer than 0.1 m to an opening |
| E-ELEC-005 | below the floor or above the top of the wall |
| E-ELEC-006 | on a demolished wall |
| E-ELEC-011 | a switch controls something that is not a luminaire |
| W-ELEC-012 | a switch within 0.5 m of the hinge edge of a door that opens into its room: the open leaf covers it. The hinge side comes from the arch pack's `door_hinge`, the same rule that draws the swing |
| W-ELEC-020 | the connected load is larger than the breaker carries |
| W-ELEC-022 | a circuit that feeds nothing |
| W-ELEC-030 / 031 | a luminaire with no switch / switched from two circuits |
| W-ELEC-040 | a board other than a media board has no RCD |

`W-ELEC-010` is kept for the minimum equipment of a room (how many sockets, DIN 18015-2). It needs the office's table and comes with the calculators; without a table there is no such check. Issues sit on the device, so a waiver is `waive wv1 W-ELEC-004 s5 "Wunsch Bauherr"`.

**Upstream changes.** A device is placed from anchors, so it follows when a wall, a window or a grid moves; the batch says `follows:` and reports the errors the move causes in elec, which stay open there (ARCHITECTURE §5). Door handing, turned by the architect, clears W-ELEC-012 the same way.

**Output.** `uea get s1` gives wall face, position, height, room, circuit, RCD and board; `uea get l1` how it is switched; `uea get c1` its devices and load; `uea show EG` counts what is mounted on a storey. `uea export xlsx` adds the sheets Verteiler, Stromkreise, Installationsgeräte (with the sum of the sockets' outlets) and Leuchten.

**Haus Müller.** The draft's `light.uea` and `elec.uea` load, apart from the `illum` targets and the `feed` lines to the heat pump and the fans, which wait for those disciplines: 2 boards, 30 sockets (45 outlets), 18 switches, 3 data outlets, 5 smoke alarms, 20 luminaires on 19 circuits, no error. The three circuits whose feeds are missing are the only warnings.

## Alternatives

- **Cable and breaker as types** in the project file: every office would write the same twenty lines. A parsed designation costs nothing and the standard library can add the data later.
- **A circuit on the luminaire** (`lum l1 r1 c10`): the prototype wired through the switch, and a luminaire without a switch is a design error worth a warning. One place for the fact, and two switches on one luminaire stay possible.
- **Sockets with a declared load**: guessing a load per outlet invents a number the norm treats with factors. Declared loads only.
- **Clearances from a norm table now**: DIN 18015-3 gives installation zones and distances, and the text is licensed. The checks are plain planning rules; the zones come with the cable paths in slice 3.
- **The device centre or its frame against an opening**: the frame decides whether it overlaps (an error), the centre whether it is too close (a warning). A two-gang switch 0.15 m from a door is placed as people place it.

## Consequences

- Two disciplines are new in the registry: `light` (the luminaire types and luminaires) and `elec`. `Derived` has `mounts` (everything placed on a wall or in a room) and `elec`; `Resolver` can be reused by other packs. Pack describers may add lines to kinds of other packs (`Pack.also`: the switching of a luminaire).
- `door_hinge` moved into `packs/arch/geometry.py` and the plan's `door_swing` uses it.
- The help grew by 3 tokens in the bench's reading (`help elec` is on demand); the task set is unchanged.
- The circuit loads are declared numbers. A person who signs the installation checks the design; UEA does not certify it.
- Open for the next slices: the Installationsplan and its symbols, the Verteilungsplan, cable lengths along the installation zones, the norm calculators, `W-ELEC-010`, Bestand electrics (status on devices), several boards with a feed between them.

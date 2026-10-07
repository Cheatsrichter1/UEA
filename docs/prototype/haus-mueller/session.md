# Haus Müller: agent session (draft)

How the files in this folder came about, as an agent would build them through the CLI. The commands and the output format are drafts; the output is written by hand, with values computed from the files. Batches 3, 4, 6–8, 10, 11, 14, 20 and 22 are summarised rather than shown.

| Batch | By | Content |
|---|---|---|
| 1 | arch | Project, levels, grids, types |
| 2 | arch | EG: walls, openings, stair, slabs, rooms |
| 3 | arch | OG: walls, openings, slab, rooms |
| 4 | arch | Spitzboden: gable walls, roof, room |
| 5 | heat | Heat pump, indoor unit; requests q1, q2 for manifold niches |
| 6 | plumb | Sanitary fixtures; request q3 for the Fallleitung |
| 7 | vent | Decentral ventilation units; request q4 for core drillings |
| 8 | elec | Boards, RCDs, circuits |
| 9 | elec | EG devices and luminaires |
| 10 | elec | OG devices and luminaires |
| 11 | elec | Feeds to the heat pump, indoor unit and fans |
| 12 | elektroplaner | Waiver wv1 |
| 13 | arch | Niches ni1, ni2; closes q1, q2 |
| 14 | heat | Manifolds, Fußbodenheizung |
| 15 | arch | Wider Haustür (later reverted) |
| 16 | elec | Moves sw8 out of the new door opening |
| 17 | arch | Reverts 15 |
| 18 | elec | Asks architecture to turn five doors (request q5) |
| 19 | arch | Turns the doors so the light switches are on the lock side; closes q5 |
| 20 | elec | Luminaire types and illuminance targets for r2 |
| 21 | elec | Four dimmed downlights in r2 after the lighting calculation; request q6 |
| 22 | elec | Board contents for the Verteilungsplan: SLS, SPD, meter |

## Start

```
$ uea init haus-mueller && cd haus-mueller
ok project haus-mueller: empty. Next: uea help start
```

## Batch 1: project, levels, grids, types

Levels, grids and types are named by the agent. Every other element gets its id from UEA.

```
$ uea apply --by arch-agent -m "Projekt, Geschosse, Achsen, Typen" <<'EOF'
+ project haus-mueller "EFH Müller" site=DE-HE postcode=64283 ground=-0.3
+ level EG z=0 fb=0.15 head=2.26
+ level OG z=2.875 fb=0.15 head=2.26
+ level DB z=5.86 fb=0.26
+ grid W x=0
+ grid E x=10.49
+ grid S y=0
+ grid N y=8.49
+ type AW-365 wall "Ziegel 36,5 verputzt" layers=putz-kalkgips:0.015,*ziegel-t9:0.365,putz-leicht:0.02
+ type IW-240 wall "KS 24 verputzt" layers=putz-kalkgips:0.015,*ks:0.24,putz-kalkgips:0.015
...
EOF
ok batch 1 (project, arch): +21
```

## Batch 2: the EG shell

`@name` is a placeholder for an element added in the same batch; `_` adds an element nobody in the batch refers to. Rooms are added last but doors already point at them: references resolve at the end of the batch. Windows carry no sill: they hang from the storey's Sturzhöhe of 2,26 m.

```
$ uea apply --by arch-agent -m "EG Rohbau" <<'EOF'
+ wall @s EG AW-365 y=S+ x=W..E lb
+ wall @o EG AW-365 x=E- y=@s..@n lb
+ wall @n EG AW-365 y=N- x=W..E lb
+ wall @w EG AW-365 x=W+ y=@s..@n lb
+ wall @m EG IW-240 y=@s+4.51 x=@w..@o lb
+ wall @h EG IW-115 x=@w+2.26 y=@m..@n
+ wall @k EG IW-115 x=@h+1.385 y=@m..@n
+ door _ @o 1.135x2.26 y=@m+0.385 into=@diele hand=r type=TH-1
+ door _ @m 0.885x2.01 x=@k+1.76 into=@wohn hand=l
+ door _ @k 0.76x2.01 y=@m+0.26 into=@diele hand=r
+ door _ @m 0.885x2.01 x=@h-0.135 into=@hwr hand=r
+ door _ @s 2.26x2.26 x=W+5.385 type=HST-1
+ win _ @s 1.26x1.26 x=W+1.51
+ win _ @w 1.26x1.135 y=S+1.76
+ win _ @s 1.26x2.26 x=W+8.26
+ win _ @o 1.51x1.51 y=S+1.385
+ win _ @n 1.01x1.01 x=W+0.885
+ win _ @n 0.76x1.01 x=W+3.01
+ stair @st EG OG y=@n- x=@o-1.125 up=w w=1 n=16 tread=0.26
+ slab _ EG BP-25
+ slab @d OG DE-20
+ void _ @d over=@st
+ sep _ EG x=@w+3.51 y=@s..@m
+ room _ EG "Küche" kitchen at=@w+1,@s+1 floor=FB-fli
+ room @wohn EG "Wohnen/Essen" living at=@o-1,@s+1 floor=FB-par
+ room @hwr EG "HWR" utility at=@w+1,@n-1 floor=FB-fli
+ room _ EG "WC" wc at=@h+0.5,@n-1 floor=FB-fli tile=1.2
+ room @diele EG "Diele" hall at=@o-1,@m+1 floor=FB-fli
EOF
ok batch 2 (arch): +28
 @s=w1 @o=w2 @n=w3 @w=w4 @m=w5 @h=w6 @k=w7 d1-d5 f1-f6 @st=st1 sl1 @d=sl2 v1 rs1
 r1 @wohn=r2 @hwr=r3 r4 @diele=r5
st1: 16 risers 0.180, tread 0.26, 2h+a 0.619
```

## Reading the model

```
$ uea show EG
EG z=0 ssl=-0.15 h=2.515 | 7 walls 5 doors 6 win st1 | 5 rooms 71.72 m² fin
r1 Küche 15.66 · r2 Wohnen/Essen 27.93 · r3 HWR 6.65 · r4 WC 4.04 · r5 Diele 17.45
elec 17 sock (25 outlets) 1 conn 9 switch 1 data 1 smoke · light 12 lum · heat 5 ufh, g1 t1 · plumb 4 san · vent 1 fan
issues 0 · requests 0 open

$ uea get r1
r1 room EG "Küche" kitchen floor=FB-fli at=w4+1,w1+1
 bounds w4 w1 rs1 w5 | shell 3.51x4.51=15.83 | fin 3.495x4.48=15.66 | h 2.515 | V 39.38
 openings f1 f2 d4→r3 · open to r2 over rs1
 elec s1-s6 a1 sw1 · light l1 · plumb sa1 · heat uh1
```

(The counts in `show EG` are those of the finished model.)

## Batch 5: a request from heating

The heat agent cannot cut niches into the architecture's walls, so it asks.

```
$ uea apply --by heat-agent -m "Wärmepumpe, Inneneinheit; Nischen für Heizkreisverteiler anfragen" <<'EOF'
+ gen _ EG at=W-1.2,N-1 type=WP-LW-8 "Wärmepumpe außen"
+ tank _ r3 at=w4+0.4,w5+0.4 type=HM-200 src=g1 "Inneneinheit mit 200 l Speicher"
+ req _ heat w5 "Nische 0,60x0,75x0,11 für Heizkreisverteiler EG in der Diele"
+ req _ heat w12 "Nische 0,60x0,75x0,11 für Heizkreisverteiler OG im Flur"
EOF
ok batch 5 (heat, issues): +4 g1 t1 q1 q2
open for arch: q1 q2
```

## Batch 9: EG devices (excerpt)

One batch writes two files: luminaires go to `light.uea`, everything else to `elec.uea`.

```
$ uea apply --by elec-agent -m "EG Elektro" <<'EOF'
+ lum @kue r1
+ switch _ w5.s c10 x=w4+3.2 ctl=@kue
+ sock _ w4 c3 y=w1+0.3 z=1.15 n=2
+ sock _ w4 c4 y=w1+0.9 z=2.1 "Dunstabzug"
...
+ lum @diele r5 at=w7+1.5,w5+1
+ lum @stair r10 at=w9-3,w10-0.5
+ switch _ w2 c10 y=d1-0.15 ctl=@diele,@entry
+ switch _ w5.n c10 x=d2-0.15 ctl=@diele
+ switch @sw8 w2 c10 y=w3-1.2 ctl=@stair
...
EOF
ok batch 9 (elec, light): +37 @kue=l1 ... @stair=l9 @sw8=sw8
l6: 2 switches → Wechselschaltung
```

## Batch 13: architecture answers the request

```
$ uea check arch
q1 from heat on w5: "Nische 0,60x0,75x0,11 für Heizkreisverteiler EG in der Diele"
q2 from heat on w12: "Nische 0,60x0,75x0,11 für Heizkreisverteiler OG im Flur"
q3 from plumb on sl2: "Durchbruch DN 125 für Fallleitung unter sa5, im HWR an w4"
q4 from vent on w2 w8 w9 w11: "Kernbohrungen Ø180 für vl1 bis vl4, Fassade prüfen"
close: ~ q1 done · reject: ~ q1 rejected="reason"

$ uea apply --by arch-agent -m "Nischen für Heizkreisverteiler" <<'EOF'
+ niche _ w5.n 0.6x0.75 x=w7+0.4 sill=0.3 d=0.11
+ niche _ w12.n 0.6x0.75 x=w9-0.3 sill=0.3 d=0.11
~ q1 done
~ q2 done
EOF
ok batch 13 (arch, issues): +2 ni1 ni2 · done q1 q2
```

## Batch 15: an upstream change that breaks electrical

The Bauherr wants a wider Haustür. The batch is accepted, because the error it causes belongs to electrical, not architecture. The entrance light follows the door on its own, because it is placed relative to it.

```
$ uea apply --by arch-agent -m "Haustür 1,51 breit (Bauherr)" <<'EOF'
~ d1 1.51x2.26
EOF
ok batch 15 (arch): 1 changed (d1)
follows: l8 (light)
affects elec: E-ELEC-003 sw8 on w2 at y=6.925 lies in opening d1 (y 5.500–7.010). Fix: move sw8, e.g. y=d1+0.15

$ uea apply --by elec-agent -m "sw8 an den Treppenantritt" <<'EOF'
~ sw8 y=w3-0.9
EOF
ok batch 16 (elec): 1 changed (sw8) · fixed E-ELEC-003
```

## Batch 17: revert

```
$ uea revert 15 --by arch-agent -m "Bauherr: doch die alte Haustür"
ok batch 17 (arch): reverted 15 · 1 changed (d1)
follows: l8 (light)

$ uea log 4
17 arch-agent  revert 15: Bauherr: doch die alte Haustür  ~d1
16 elec-agent  sw8 an den Treppenantritt  ~sw8
15 arch-agent  Haustür 1,51 breit (Bauherr)  ~d1
14 heat-agent  Heizkreisverteiler und FBH  +hv1 hv2 uh1-uh10
```

The history entry for batch 15 in `log.jsonl`:

```json
{"batch":15,"time":"2026-10-07T14:02:11Z","by":"arch-agent","msg":"Haustür 1,51 breit (Bauherr)","ops":["~ d1 1.51x2.26"],"inverse":["~ d1 1.135x2.26"],"ids":[],"files":{"arch.uea":"sha256:9f2c…"}}
```

## Batches 18 and 19: door handing

Drawing the door swings in the electrical plan shows five switches on the hinge side of their door: open the door and the leaf covers the switch. The warning is Elektro's, because Elektro placed the switches next to existing doors. Elektro could move the switches, but here the door handing was never a real decision, so it asks Architektur.

```
$ uea check elec
W-ELEC-012 sw4 on the hinge side of d4 (hand=r), which opens into r3. Fix: move sw4 past the other edge, or ask arch to turn d4
W-ELEC-012 sw6 on the hinge side of d1 (hand=r) ...
W-ELEC-012 sw12, sw13, sw14 ...

$ uea apply --by elec-agent -m "Türanschläge anfragen" <<'EOF'
+ req _ elec d1,d4,d6,d8,d9 "Türanschlag drehen: Lichtschalter liegen auf der Bandseite"
EOF
ok batch 18 (issues): +1 q5
open for arch: q5

$ uea apply --by arch-agent -m "Türanschläge: Schalter auf die Schlossseite" <<'EOF'
~ d1 hand=l
~ d4 hand=l
~ d6 hand=r
~ d8 hand=l
~ d9 hand=l
~ q5 done
EOF
ok batch 19 (arch, issues): 5 changed (d1 d4 d6 d8 d9) · done q5
fixed elec: W-ELEC-012 sw4 sw6 sw12 sw13 sw14
```

## Batches 20 and 21: code calculates, the agent decides

Batch 20 gives the luminaires in r2 product types (placeholders with flux and distribution) and adds two targets: 150 lx for the room, 200 lx on the dining table. Both are planning assumptions; for living rooms there is no binding norm.

```
$ uea calc light-point r2
custom light-point 0.0.1 · r2 Wohnen/Essen · not norm-compliant
il1 Raum ohne Randzone  Em 100 lx  Ziel 150  NOT MET  U0 0,37
il2 Esstisch            Em 253 lx  Ziel 200  ok       U0 0,53
report: out/lichtberechnung-r2.md

$ uea apply --by elec-agent -m "Wohnen: 4 Downlights, gedimmt" <<'EOF'
+ type DL-11 lum "LED-Einbaudownlight 11 W" flux=1050 w=11 dist=cos3
+ lum @a r2 at=w2-1,w1+1.2 type=DL-11
+ lum @b r2 at=w2-3,w1+1.2 type=DL-11
+ lum @c r2 at=w2-1,w5-1.2 type=DL-11
+ lum @d r2 at=w2-3,w5-1.2 type=DL-11
+ switch _ w5.s c10 x=sw2+0.071 ctl=@a+@b+@c+@d dim
+ req _ elec sl2 "4 Betoneinbaugehäuse für l17 bis l20 über r2, vor dem Betonieren"
EOF
ok batch 21 (light, elec, issues): +7 DL-11 @a=l17 @b=l18 @c=l19 @d=l20 sw18 q6
open for arch: q6

$ uea calc light-point r2
custom light-point 0.0.1 · r2 Wohnen/Essen · not norm-compliant
il1 Raum ohne Randzone  Em 235 lx  Ziel 150  ok  U0 0,27
il2 Esstisch            Em 296 lx  Ziel 200  ok  U0 0,55
report: out/lichtberechnung-r2.md
```

`x=sw2+0.071` puts the dimmer into the same 2-gang frame as sw2, at the standard box spacing.

## End state

```
$ uea check
0 errors · 0 warnings
requests open: q3 plumb→arch sl2 · q4 vent→arch w2 w8 w9 w11 · q6 elec→arch sl2
waived: W-ELEC-010 r5 (wv1, by elektroplaner)
```

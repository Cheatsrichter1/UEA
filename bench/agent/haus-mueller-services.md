# Brief: Haustechnik Einfamilienhaus Müller

Bauherr Müller, Hessen, PLZ 64283. The architecture of the house is modelled in UEA already
(`uea show`, `uea get`): two storeys and a Spitzboden, eleven rooms. Plan its building services
in UEA: Elektro (with the luminaires), Heizung, Sanitär and Lüftung. No Statik. Products and
their data are illustrative placeholders, not design data.

Conventions:
- Rooms by their names in the model. "North wall" of a room is the wall on its north side.
- Heights are above the storey's OKFF.
- Where a discipline needs something of the architecture (a niche, a hole through a wall or a
  slab), it asks the architect with a request; the architect answers it in the model.

## Elektro

**Distribution.** One Zählerschrank/UV in the HWR on its east wall (the HWR/WC wall), 1,40 high:
main switch SLS-E35, surge protection T1+T2, one meter. A media distribution board next to it,
also in the HWR.

**RCDs.** Four 40/0,03 A type A, one 40/0,03 A type B for the heat pump.

**Circuits.** NYM-J, B16 with 2,5 mm² unless the table says otherwise.

| RCD | Circuit | Serves |
|---|---|---|
| A 1 | Küche Herd, 5×2,5, three-phase | the cooker connection in the Küche |
| A 1 | Küche Geschirrspüler | its socket |
| A 1 | Küche Steckdosen 1 | worktop and fridge sockets |
| A 1 | Küche Steckdosen 2 | the other worktop sockets and the cooker hood |
| A 2 | Waschmaschine | its socket in the HWR |
| A 2 | Trockner | its socket in the HWR |
| A 2 | Wohnen/Essen | the sockets of Wohnen/Essen |
| A 2 | HWR, WC, Diele | the other sockets of these rooms |
| A 2 | Lüftungsgerät, B10 1,5 mm² | the central ventilation unit |
| A 3 | Licht EG, Treppe, B10 1,5 mm² | every light of the EG rooms, the light at the Haustür, and the stair light |
| A 3 | Flur OG | the sockets of the Flur |
| A 3 | Licht OG, B10 1,5 mm² | every light of the OG rooms except the stair light |
| A 3 | Außen | the terrace socket and the terrace light |
| A 4 | Schlafen, Kind 1, Kind 2, Bad | one circuit each, for the sockets of the room |
| B | Wärmepumpe außen, 5×2,5, three-phase | the heat pump |
| B | Wärmepumpe innen | the indoor unit |

**Devices per room.** Sockets as the number of outlets; place them in frames as you see fit.

| Room | Outlets | Other | Lights | Switches |
|---|---|---|---|---|
| Küche | 9: two double ones over the worktop, the dishwasher, the fridge, the cooker hood at 2,10, and a double one by the door | cooker connection | 1 ceiling light | 1 |
| Wohnen/Essen | 10 | 2 data ports | a pendant over the dining table, a ceiling light, 4 dimmable downlights | 3: the room's lights at the door, the downlights' dimmer beside it, the terrace light |
| HWR | 3: washing machine, dryer, one more | | 1 | 1 |
| WC | 1 | | 1 | 1 |
| Diele | 1 | smoke alarm | 1 | 3: Diele and Haustür light by the front door, Diele by the door to Wohnen, the stair light |
| Schlafen | 6, two of them double at both sides of the bed | smoke alarm | 1 | 3: at the door and at both sides of the bed |
| Kind 1 | 5 | 2 data ports, smoke alarm | 1 | 1 |
| Kind 2 | 5 | 2 data ports, smoke alarm | 1 | 1 |
| Bad | 2, a double one by the basin | | a ceiling light and a mirror light | 1, for both |
| Flur | 2 | smoke alarm | the stair light and 2 ceiling lights | 3: the stair light (with the one in the Diele), and the two ceiling lights from both ends |
| Outside | 1 on the terrace | | the terrace light and the light at the Haustür | |

Switches stand on the lock side of their door. The downlights sit in the concrete slab: ask the
architect for housings to be cast in.

## Heizung

- An air-to-water heat pump outside, 1,2 m west of the house and 1 m south of its north face:
  8 kW, pressure loss 120 hPa.
- Its indoor unit with a 200 l drinking-water tank in the HWR, in its south-west corner (0,4 m
  from both walls); it heats the drinking water; pressure loss 150 hPa.
- Two manifolds with 10 outlets, 0,55 wide, each in a niche of 0,60 × 0,75 × 0,11 at 0,30
  above the floor: EG in the Diele on the 24 wall, 0,40 east of the WC/Diele wall; OG in the
  Flur on the 24 wall, its east edge 0,30 west of the east wall.
- Fußbodenheizung in every heated room, on the manifold of its storey: spacing 0,15, 60 W/m²,
  loops at most 100 m, pipe 16×2 with roughness 0,007 mm.
- In the Bad also a towel radiator, 300 W, 0,60 × 1,20, on the north wall 0,90 from the west
  wall (centre), 0,90 high, on the OG manifold.
- Pipes: copper 15×1, 18×1, 22×1, 28×1,5, roughness 0,0015 mm, ζ 0,5 per bend, 1,3 per tee.

## Sanitär

- The water meter in the HWR in its north-east corner (0,3 from both walls), 4 bar, 450 hPa
  loss.
- A riser and the Fallleitung in the HWR along its west wall: the riser 1,20 south of the
  north wall, the stack under the WC of the Bad. Both 0,15 from the west wall.
- The sewer connection: a manhole outside, 1,5 m west of the house and 2 m south of its north
  face, on KG pipe.
- Fixtures: Küche a sink under the west window; HWR a washing machine on the west wall, 0,60
  south of the north wall; WC a WC under its window and a basin on its west wall, 1,30 south of
  the north wall; Bad a WC under its window, a basin on its south wall 1,25 east of the west
  wall, a shower 0,90 × 0,90 in its north-east corner.
- Pipes: multilayer 16×2, 20×2, 26×3, 32×3, roughness 0,007 mm, ζ 1,4 per bend, 1,7 per tee.
  Waste water HT 50, 75, 90, 110; under the floor KG 110, 125, 160.

## Lüftung

- A central unit with heat recovery in the HWR, 0,4 west of its east wall and 0,5 north of the
  24 wall: 250 m³/h, 150 Pa external pressure, 85 % heat recovery.
- Outdoor air through the west wall of the HWR, 0,70 south of the north face of the house;
  exhaust air through the north wall of the HWR, 2,15 east of the west face of the house. Both
  2,40 high, core drillings Ø 180.
- Supply air: two terminals in Wohnen/Essen, one in each bedroom. Extract air: Küche, HWR, WC
  and Bad, one terminal each.
- Ducts: spiral-seam Ø 80, 100, 125, 160, roughness 0,15 mm, ζ 0,3 per bend, 0,6 per tee.
- The building is to reach n50 = 1,5 1/h; its insulation is high.

## Calculations

Run with these settings; where a result is not met, change the design until it is:

- `heatload` tb=0.05 n50=1.5 shielding=moderate
- `hydronic` with the same and spread=5 vmax=0.8
- `airflow` n50=1.5 insulation=high
- `ducts` with the same and vmax=3

## Deliverables

1. The model, with `uea check` showing no errors and no warnings, and every request to the
   architect answered except the one for the housings of the downlights.
2. The four calculation reports.
3. The installation plans of EG and OG for each discipline, and the XLSX tables.

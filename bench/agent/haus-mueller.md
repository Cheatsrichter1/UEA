# Brief: Einfamilienhaus Müller

Bauherr Müller, Hessen, PLZ 64283. Model the shell of the house in UEA (Architektur only):
storeys, build-ups, walls, slabs, openings, stair, rooms and the roof. No Elektro, Heizung or
Statik. Build-ups and U-values are illustrative.

Conventions of this brief:
- Plan dimensions are Rohbau: faces of the load-bearing layer, without plaster or render.
  "Clear" means between Rohbau faces.
- x runs west to east, y south to north. The origin is the south-west outside corner of the
  Rohbau.
- Openings are Rohbaurichtmaße, width × height. Window positions, and the Hebeschiebetür's,
  give the opening's edge nearer the origin, measured from the Rohbau outside face of the house: south and north windows from
  the west outside face, west and east windows from the south outside face.
- Heights are above the storey's OKFF.

## Site and storeys

- Terrain 0,30 below OKFF EG.
- EG: OKFF ±0,00, Fußbodenaufbau 15 cm.
- OG: OKFF +2,875, Fußbodenaufbau 15 cm.
- Spitzboden (cold, not habitable): OKFF +5,86, floor build-up 26 cm.
- In EG and OG all window heads (Sturz) are at 2,26 above OKFF.

## Build-ups

- Außenwand: 1,5 cm Kalkgipsputz inside | 36,5 cm Ziegel T9 | 2 cm Leichtputz outside.
- Tragende Innenwand: 24 cm Kalksandstein, 1,5 cm Kalkgipsputz on both sides.
- Nichttragende Innenwand: 11,5 cm Kalksandstein, 1,5 cm Kalkgipsputz on both sides.
- Bodenplatte: 25 cm Stahlbeton on 14 cm XPS.
- Geschossdecke: 20 cm Stahlbeton, 1 cm Gipsputz underneath.
- Floor with Parkett: 1,5 Parkett | 6,5 Zementestrich (Heizestrich) | 3 EPS Trittschall | 4 EPS.
- Floor with tiles: the same, with 1,5 cm Fliese instead of Parkett.
- Spitzboden floor: 2 cm OSB on 24 cm EPS.
- Roof: Ziegel 4 | Lattung 3 | Konterlattung 4 | Sparren 18 cm.
- Windows: Kunststofffenster 3-fach, Uw 0,9; the standard window.
- Doors: Innentür (the standard door), Haustür Ud 1,3, Hebeschiebetür Uw 0,9.

## Outline

Rohbau 10,49 × 8,49 m. Außenwände 36,5, all load-bearing, the same in EG and OG.

## EG

- A load-bearing 24 cm wall runs west–east between the exterior walls, 4,51 clear north of
  the south wall.
- North of it, from the west: HWR 2,26 clear wide, an 11,5 wall, WC 1,385 clear wide, an 11,5
  wall, then the Diele up to the east wall. Both 11,5 walls run from the 24 wall to the north
  wall.
- South of it: the Küche in the west, open to Wohnen/Essen. No wall between them; the room
  boundary is 3,51 east of the west wall's inside face.
- Stair: straight, one flight from EG to OG, 1,00 wide, 16 risers, tread 26 cm. It stands in
  the Diele against the north wall, its east end 1,125 clear from the east wall, and climbs
  westward.
- Doors:
  - Haustür 1,135 × 2,26 in the east wall, its south edge 0,385 north of the 24 wall. Opens
    into the Diele, DIN links.
  - Wohnen 0,885 × 2,01 in the 24 wall, its west edge 1,76 east of the WC/Diele wall. Opens
    into Wohnen/Essen, DIN links.
  - WC 0,76 × 2,01 in the WC/Diele wall, its south edge 0,26 north of the 24 wall. Opens into
    the Diele, DIN rechts.
  - HWR 0,885 × 2,01 in the 24 wall, its east edge 0,135 west of the HWR/WC wall. Opens into
    the HWR, DIN links.
  - Hebeschiebetür 2,26 × 2,26 in the south wall at 5,385.
- Windows:
  - South: 1,26 × 1,26 at 1,51 (Küche); 1,26 × 2,26 at 8,26 (Wohnen/Essen).
  - West: 1,26 × 1,135 at 1,76 (Küche).
  - East: 1,51 × 1,51 at 1,385 (Wohnen/Essen).
  - North: 1,01 × 1,01 at 0,885 (HWR); 0,76 × 1,01 at 3,01 (WC).
- Rooms: Küche, HWR, WC (wall tiles to 1,20) and Diele with tiles; Wohnen/Essen with Parkett.
- Slabs: Bodenplatte under the EG; Geschossdecke under the OG with a hole over the stair.

## OG

- The exterior walls and the 24 wall stand on those of the EG.
- South of the 24 wall, from the west: Schlafen 4,01 clear wide, an 11,5 wall, Kind 1 2,885
  clear wide, an 11,5 wall, then Kind 2. Both walls run from the south wall to the 24 wall.
- North of the 24 wall: the Bad in the west, 2,76 clear wide, behind an 11,5 wall from the 24
  wall to the north wall. The Flur with the stair hole takes the rest.
- Doors, all 0,885 × 2,01:
  - Bad: in the Bad/Flur wall, its south edge 0,26 north of the 24 wall. Into the Bad, DIN
    rechts.
  - Schlafen: in the 24 wall, its west edge 0,125 east of the Bad/Flur wall. Into Schlafen,
    DIN rechts.
  - Kind 1: in the 24 wall, its west edge 0,135 east of the Schlafen/Kind 1 wall. Into Kind 1,
    DIN links.
  - Kind 2: in the 24 wall, its west edge 0,135 east of the Kind 1/Kind 2 wall. Into Kind 2,
    DIN links.
- Windows:
  - South: 1,51 × 1,385 at 1,385 (Schlafen); 1,26 × 1,385 at 5,26 (Kind 1); 1,26 × 1,385 at
    8,135 (Kind 2).
  - West: 1,01 × 1,385 at 2,01 (Schlafen); 1,01 × 1,01 at 6,135 (Bad).
  - East: 1,01 × 1,385 at 2,26 (Kind 2).
  - North: 1,26 × 1,26 at 6,51 (Flur).
- Rooms: Schlafen, Kind 1, Kind 2 and Flur with Parkett; Bad with tiles, wall tiles to 2,00.

## Spitzboden and roof

- Geschossdecke 20 cm under the Spitzboden.
- Satteldach, 25°, ridge west–east.
- Gable walls: Außenwand 36,5 at the west and east ends, load-bearing, over the full depth of
  the house and up to the roof.
- The underside of the rafters meets the outer face of the eaves walls 0,20 above the
  Spitzboden's OK Rohdecke.
- Overhangs: 0,50 at the eaves, 0,30 at the verges.
- One room, Spitzboden, on the insulated floor.

## Deliverables

1. The model, with `uea check` showing no errors.
2. A short report: the Fertig area of every room, Traufe and First, and the Wohnfläche per
   WoFlV.
3. An IFC export and plan images of EG and OG.

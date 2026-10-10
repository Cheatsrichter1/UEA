# 0029: IFC import, slice 4a

Status: Accepted (slice 4a built)
Date: 2026-10-10

## Context

`0011-ifc-import.md` decided that `uea import ifc` exists and that ids stay stable across re-imports. Slice 4a of phase 4 builds the first part: storeys, walls, openings, floor slabs and spaces. Roofs, stairs, slab voids and grids are slice 4b.

An IFC is geometry and properties; UEA wants intent. A wall in the file is a body with a layer set, in UEA it is an axis between two points with a type. The importer therefore reads what the file says and asks UEA for what UEA derives itself (which side of a wall is the outside, how high a wall reaches), so the rules are not written twice.

## Decision

**Command.** `uea import ifc <file> --by <who> [-m why] [--dry-run]`, with `--json`. One batch, like any other, with `uea revert` and `uea log`. The output names the counts per kind, the new issues, what was not imported (by IFC class) and notes; `--dry-run` writes nothing.

**Geometry comes from IfcOpenShell's tessellation, not from the representations.** Exporters write bodies as extrusions, clippings, brep or mesh; the plan footprint of the tessellated body is the same for all of them. A wall is the strip its footprint draws (a footprint that is not a plain strip is taken as one and noted). Openings are read without being cut out of their walls.

**Walls.**
- The axis runs through the middle of the core layer, as UEA draws it. The core is the thickest layer whose material name says structural (brick, concrete, timber, steel, ...), else the thickest. Which side the first layer is on comes from the layer set usage (`LayerSetDirection`, `DirectionSense`); without a usage the side is unknown, the axis is the middle of the body (a few millimetres off the core for unequal finishes) and the first layer is assumed to be the outside, as an exterior wall is listed in IFC.
- A wall type is made from the layers in the file, in UEA's order (inside to outside). The order is turned over when the first layer of most exterior walls of that type is on the outside; a wall that is the other way round gets `flip`. Which side is outside is UEA's own derivation, from a scratch model of the first pass. A body whose layers do not add up to its footprint is imported as one core layer of the measured thickness, and noted.
- Walls within 0.1° of the x or y direction are snapped to it (ordinary `h`/`v` walls, positions as `x=`/`y=`); the others stay skew, with `s=` positions on them.
- A wall end that stops up to 3 cm short of another wall's core is moved to reach it (0.5 mm in), because UEA joins at 2 mm and exporters leave the finish layers in between.
- `h=` is written only where the height UEA derives from the slabs differs from the file's by more than 5 cm. A sloped wall top (under a roof) is given its highest point until the roof is imported.
- `lb` from `Pset_WallCommon.LoadBearing`, a status word from `Status`.

**Levels.** The ground storey is the storey at elevation 0, else the lowest one with walls; every `z` is relative to it (the note says so when it is not 0 in the file). The name is the short storey name (`EG`, `OG`, `KG`) or `L1`, `B1`. `head` is the most common window top above the FFL of the storey.

**Slabs.** One slab per storey, the largest. UEA derives the outline from the walls, so the slab outline is not imported. The layers from the core up are the floor build-up: they become `fb` and a floor type, which the rooms of the storey get. The core is found as for walls; the direction of the layer set (`AXIS3`) says which end is the top. Other slabs of a storey are counted in the report.

**Openings.** A door or window is a position along its wall, measured from its footprint. Sill and head are written only where they differ from UEA's defaults (a door on the floor; a window ending at the `head` of its level). Types come from the IFC types, with `ThermalTransmittance` as `ud=`/`uw=`.

**Rooms.** A space becomes a seed point (its centroid). The use comes from the words in its names (`LongName`, `Name`, category: German and English, first match wins, else `other`). Where two spaces share an edge of 0.4 m or more with no wall on it (open plan), the importer writes a `sep` along it, so UEA's rooms split as the architect's spaces do.

**Re-import.**
- The identity of an imported element is its IFC GlobalId. The history entry of the batch keeps, for what the import added or changed, which key became which id and a hash of the line as it was imported (`ifc` in `log.jsonl`). The lines of the model carry nothing of it, and an import that was reverted is forgotten.
- A later import updates the elements nobody has edited since (hash equal), adds new ones with new ids (ids are never reused), and removes the unedited elements the file lost, unless something still refers to them. Everything else is left alone and listed as `kept:` with the reason: edited in UEA since the import, deleted in UEA since the import (it is not re-added), gone from the file but edited or still referred to. Levels and types are never removed.
- An import whose result changes nothing writes no batch.

**Errors do not reject an import.** An ordinary batch is rejected when it adds an error in the pack it writes. An architect's model is not ours to reject, and an agent needs it in the model to fix it: the errors the import causes (`E-ARCH-021` for two seeds in one region, say) are listed as new issues, and the batch is written.

**Own exports are refused.** A file from UEA (`originating_system` "UEA ...") is views of a model that exists; reading it back would make a second copy of the project (`0011`).

**The help** names the command and has a topic `import`: +26 tokens in the bench's reading of the help; the task set is unchanged at 3,403.

## Alternatives

- **Read the representations (extrusion profile and depth).** Exact for extrusions, nothing for everything else; every program writes bodies differently.
- **Wall axes from the file's own placement.** Exporters put it on a face or on the centre of the body, not on the core.
- **One type per IFC wall type, whatever the layers.** Two walls of one type with different layers (a common export fault) would silently lose one build-up. The key is the type plus the layers.
- **Rooms from space boundaries.** Few exporters write them; the footprint of the space is always there.
- **Block an import on errors, or repair them (extend a wall, add a separator).** Hides what the architect's file says; repair needs a judgement the agent should make.
- **GlobalIds in the lines of the model.** Every line would grow by 22 characters for something only the importer reads.
- **Remove everything a new file lost, edited or not.** It would delete work.

## Consequences

- Tested with hand-built IFC files whose results are worked out by hand (`tests/ifc_make.py`, `tests/test_import.py`) and with UEA's own export of Haus Müller, relabelled as another program's: 3 levels, 17 walls, 9 doors, 13 windows, 11 rooms come back, room areas within 0.5 %. **Not yet tried on a real office file**, which phase 4 asks for; real files will show what the fixtures do not (curtain walls, walls in several parts, split storeys, layer sets on types only).
- Roofs, stairs, slab voids and grids (slice 4b) are listed as not imported; their walls get a plain top, or `h=`.
- Walls with no layer set usage are a few millimetres off in position; the rooms of the round trip differ by about 0.1 %.
- The per-import record in the log grows with the elements it changed, not with the whole model.
- Slice 4c (open): units other than metres are scaled by IfcOpenShell, but untested; several buildings in one file; curved walls; BCF for requests to the architect (`0011`).

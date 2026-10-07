# 0012: Datums, positions and openings

Status: Accepted (syntax still draft)
Date: 2026-10-07

## Context

Every dimension in the model needs one fixed reference, or areas, Heizlast, plans and every device position become ambiguous. The Haus Müller prototype (`docs/prototype/haus-mueller/`) tried a complete set of references on a real Einfamilienhaus and generated plans from it.

## Decision

- **Plan positions are Rohbau:** the faces of a type's core layer, marked `*` in its layers. Fertigmaß is derived from the other layers; both can be read everywhere.
- **Heights count from the storey's OKFF.** A level stores `z` (its OKFF; ±0,00 is OKFF EG) and `fb` (the Fußbodenaufbau), so OK Rohdecke is `z − fb`.
- **Positions are relative:** `anchor±distance`. The anchor is a grid, a wall face, an opening edge or centre, or a device; the sign says from which face and in which direction. A wall's position is a clear dimension, as in a Maßkette. Raw coordinates are for imported elements.
- **Openings store their Rohbaurichtmaß `W x H`.** Each storey has one Sturzhöhe (`head=` on the level). Windows hang from it and their sill is derived; `sill=` is written only for a window that deviates. Doors stand on OKFF.
- **Devices:** `z` is the box centre above OKFF, and a device's position along its wall is its box centre.
- **Roofs store the construction value:** `kn` is the underside of the rafters at the outer face of the eaves wall, above OK Rohdecke. Traufhöhe, Firsthöhe and the Kniestock as a Landesbauordnung defines it are derived.
- **Names:** level and grid names start with a letter and contain no `-`, because in a position `W-1.2` means grid W minus 1.2 m. Numeric axes get a letter name and a label for drawings (`grid A1 x=0 label=1`).

## Alternatives

- **Wall axis instead of a face:** what some CAD tools use, but German Maßketten dimension Rohbau faces, and an axis position needs the wall thickness to give a clear dimension.
- **Heights from OK Rohdecke:** matches the Rohbau, but the heights a human checks (Brüstung, Schalterhöhe, Türhöhe) are given from OKFF.
- **A `sill` on every window:** matches the BRH annotation on plans. But a window whose height changes then moves its head, breaking the façade line and the lintel, and the field repeats on every window.
- **Kniestock as a Landesbauordnung defines it:** the definitions differ between the Länder. Storing the construction value and deriving each Land's value keeps the model independent of the site.

## Consequences

- Every field's schema states its datum.
- Validators check what the derived values imply, for example sill heights for Absturzsicherung.
- The prototype is the worked example; in it, all 13 windows hang from a Sturzhöhe of 2,26 m.

# 0039: Openings without a fill

Status: Accepted (built; for the user's veto)
Date: 2026-10-11

## Context

The Todo in `ROADMAP.md` names openings without a fill (Durchbrüche, Kernbohrungen, Schlitze; `IfcOpeningElement` with nothing in it) as the main handoff from the Fachplaner to the architect: a request asks for a hole, and the architect answers with the element. Until now the model had niches and slab voids only, so Haus Müller's requests for the stack (q3), the core drillings (q4) and the ducts to the OG (q7) could be asked but never answered, and nothing told the services agent that a pipe passes a slab with no hole in it. The IFC import listed such openings as not imported. The derived networks (`0027`, `0035`, `0037`, `0038`) change storey anywhere, so nothing said where a hole had to be.

## Decision

**One kind, `hole` (ho), in `arch.uea`, owned by the architect:**

| Host | Position | What it is |
|---|---|---|
| a wall | `x=`, `y=` or `s=` its edge along the wall, `sill=` its bottom, like a window | a hole through the wall and its finishes (Wanddurchbruch) |
| a wall face (`w6.e`) | the same, and `d=` its depth from the core face | a chase (Schlitz) |
| a slab | `at=` its centre; the size along x and y | a hole through the slab and the floor build-up on it (Deckendurchbruch) |

`round` makes it a core drilling (Kernbohrung); its size gives the diameter twice (`0.18x0.18`). A hole has a status like every physical element. It is not an opening of the wall in the derived sense: it takes no area off the wall in the tables or the Heizlast, and no device check treats it as a door or window.

**The handoff:** the services say where they need a hole; the architect answers with one; the services name it.
- A section of a pipe or duct network that changes storey passes the slabs between. A vertical one (a riser, a stack) passes where it stands, and the hole or void around that point is its hole. Any other goes through the nearest hole or void its network names in `via=`, on the tank, generator or manifold it comes from, or on the central ventilation unit. The detour counts in its length and bends, and the tree is grown on those lengths (`routed`), so a duct goes up once through its hole instead of up and down again.
- Checks, one per discipline because the warning belongs to the one that must ask: `W-PLUMB-006` (a riser or stack passes a slab with no hole there; its point in the message), `W-HEAT-005` and `W-VENT-007` (pipes or ducts change storey through a slab and no hole in it is in `via=`), `W-VENT-006` (a decentral unit, or an outdoor or exhaust air terminal, with no hole through its wall at its point). Each fix names the request to write.
- The arch checks cover holes as they cover openings: outside the wall (`E-ARCH-001`), overlapping an opening or another hole (`E-ARCH-002`), above the wall (`E-ARCH-003`), a chase as deep as the wall (`E-ARCH-007`), new in a demolished wall (`E-ARCH-008`), outside the slab (`W-ARCH-032`).

**Read and drawn:**
- `uea get <hole>`: where it is, its heights, through or chase, round or not, and what passes it (`for sr1`).
- The floor plans: each hole with its outline, a cross and a label (`KB Ø18 UK +2,31`, `WD 40/25 UK …`, `S 5/100 T 3 UK …`, `DD 40/25`); holes in the slab above dashed. The installation plans show them too, since they draw on the floor plan.
- The XLSX table Aussparungen: kind, host, whether it is load-bearing, size or diameter, depth, bottom, centre, what passes it (from the derived networks), the label, status.
- The IFC: an `IfcOpeningElement` voiding its wall or slab, `RECESS` for a chase, a swept `IfcCircleProfileDef` for a core drilling.
- The IFC import maps them back: a wall opening nothing fills is a hole (round if its body is a swept circle); a slab opening that is round, or a single rectangle up to 0.25 m² and over no stair, is a hole, a larger one stays a void. Haus Müller's six holes come back from its own IFC where they were.

## Alternatives

- **Slab holes as voids, wall holes as windows without glass.** Voids are the stair's and a shaft's; a window is a product with a U-value that the Heizlast and the tables count. A hole is neither.
- **Two kinds, one for walls and one for slabs.** One kind, like IFC's `IfcOpeningElement`, is fewer words for the agent; the host says which.
- **The hole names what passes it (`for=fl1`).** References point upstream (`UPSTREAM` in `core/registry.py`): the architecture cannot name a plumbing element. The services name the hole (`via=`), and a vertical riser or stack needs no name: the hole around it is its hole.
- **Holes derived from the networks.** Code would decide where the architect cuts a load-bearing slab. The services ask, the architect decides and answers, and a human signs.
- **Every crossing of a wall checked as well.** The networks are rectilinear trees, not routes (`0027`), so where a pipe crosses an interior wall is not known. Facade terminals are, so those are checked; routes along shafts and installation zones stay open.
- **A check that holes in load-bearing members are approved.** Approval is the Tragwerksplaner's (phase 8); the table says which holes are in load-bearing walls and slabs so the engineer can be asked.

## Consequences

- Haus Müller answers its requests. Batch 23 replaced the decentral units by a central one (`0038`), and the checks then asked for six holes. Requests q8 (the riser) and q9 (the heating pipes to hv2) were added, the architect answered q3, q4, q7, q8 and q9 with ho1 to ho6 in batch 26, and the tank and the unit name their holes. `docs/prototype/haus-mueller/session.md` shows the round trip. Only q6 (housings for downlights) stays open.
- With the holes the ducts are grown on their real detours: the supply side goes up once, through ho3, instead of up to the bedrooms and down again to the living room. With the synthetic tables the supply side needs 24.5 Pa instead of 28.2 Pa.
- `uea apply` names a derived pipe or duct that follows a change by the element at its end (`follows: ld5 (vent)`); it printed an empty `follows:` line before.
- The help names holes and `via=` in two lines each of the arch, heat and vent notes and a few words of the plumb and import notes. The bench could not be rerun in this environment (tiktoken's download is blocked), so their token cost is not measured; the task set does not touch holes.
- Tested by hand in `tests/test_holes.py` (geometry, the arch checks, the three services' handoffs, a pipe's and a duct's detour through `via=`, the plan labels, the IFC entities, the table, the command line), and in the import tests (a wall opening nothing fills becomes a hole; Haus Müller through another program keeps its holes).
- Open: holes in roofs; a shaft through several storeys as one element; pipes crossing walls on routes along installation zones; the Tragwerksplaner's approval of holes in load-bearing members (phase 8); the size of a hole checked against what passes it.

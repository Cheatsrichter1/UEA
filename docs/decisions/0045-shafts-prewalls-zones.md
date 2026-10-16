# 0045: Shafts, pre-wall installations and installation zones

Status: Accepted
Date: 2026-10-12

## Context

The services' networks are derived as rectilinear trees: pipes, cables and ducts (`0027-cable-routes.md`, `0035-plumbing.md`, `0037-heating-pipes-and-strangschema.md`, `0038-ventilation.md`). Since `0039-openings-without-a-fill.md` they pass slabs through the holes their networks name. The Todo of the roadmap (since removed; now `FUTURE.md`, Backlog) left three things open, shared by the disciplines:

- vertical shafts through several storeys as one element;
- pre-wall installations (Vorwandinstallation) in WC and bath;
- the runs along shafts and installation zones instead of the shortest straight legs.

## Decision

Three elements of `arch.uea`. They belong to the building and are drawn on its plans, and every discipline uses them.

**`shaft sh1 EG 0.4x0.6 at=<centre> to=DB`**, a shaft from a storey up through the storeys above.

- It opens every slab it passes, as a void does.
- It is not floor area of the rooms it stands in (their finished outline loses its footprint).
- A section of any network that changes storey goes through it on its own, like a hole named in `via=`. The nearest of the shafts and named holes wins, and the detour counts.
- A riser standing in it passes the slabs in it. The missing-hole checks are satisfied.
- It is drawn on each storey it runs through, outlined with a cross.
- `E-ARCH-070` flags a shaft whose top storey is not above its lowest.

**`prewall vw1 w9.n 1.6x1.2 y=<edge> d=0.2`**, a pre-wall installation in front of a wall face. Width, height and edge work like an opening's; d is its depth from the finished face.

- Every fixture and device on that face within it sits on its front: a wall-hung WC, a basin, a socket in the pre-wall.
- It is an installation zone along its middle at half its height, so the pipes of its fixtures run in it.
- Drawn hatched.
- For the Wohnfläche, a pre-wall higher than 1.5 m on more than 0.1 m² does not count (WoFlV §3 Abs. 3 Nr. 1, an amtliches Werk); `wofl` 0.2.0.

**`zone iz1 EG a=<point> b=<point> z=2.3`**, an installation zone (Installationszone, Trasse): a horizontal run on a storey.

- Zones that cross or touch form one network; zones at different heights join by the difference.
- On a storey with zones, every section between two nodes of that storey follows them: straight (rectilinear) from its node to the nearest point of a zone, along the zones by the shortest way, and straight on to the other node.
- This holds for the pipes of drinking water and waste water, the heating pipes and home runs, the ducts, and the cables and data home runs.
- The way is kept on the section (`path`). The services' plans draw it and the zones themselves, thin and dashed. The lengths include it.
- Storeys without zones keep the rectilinear lower bound, as before.

## Alternatives

- **The zones of DIN 18015-3 laid out automatically** (bands at fixed distances from ceilings, floors, corners and openings): their distances are in the licensed text, and an office's practice varies. Zones the agent writes cost a line each and say what the planner wants.
- **A shaft as one void per slab:** works for the slabs, but repeats the element on every storey and does not tell the networks it is the way up.
- **Pre-walls as walls:** a wall has a core, a type and a load path; a pre-wall has a depth and carries fixtures. A wall would make the rooms split around it.
- **Routing around obstacles in the zones:** a router of its own; the zones are the obstacle-free runs by definition.

## Consequences

- Haus Müller can model its HWR shaft and the WC and bath pre-walls (the example files are not changed in this step).
- Lengths on storeys with zones are no longer the lower bound but the length along the zones; the calculators size what they get.
- Not done: zones on a slope or vertical zones beside openings, pre-walls in the IFC export (shafts are, as openings of the slabs), the clash of runs in one zone.

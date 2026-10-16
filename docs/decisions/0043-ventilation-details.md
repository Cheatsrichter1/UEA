# 0043: Inlets, overflow openings, terminal losses, heat recovery and ventilation in the IFC

Status: Accepted
Date: 2026-10-12

## Context

Phase 7 left open (`0038-ventilation.md`): overflow openings and outdoor air inlets, heat recovery in the Heizlast, the losses of terminals and silencers, and ventilation in the IFC export.

## Decision

**Outdoor air inlets** (`inlet al1 w1 x=W+2`, type `inlet flow=`): an Außenluftdurchlass through an exterior wall. For `airflow` its type's flow (the manufacturer's, at the exhaust system's design pressure difference) counts as its room's supply, so an exhaust system with fans in the wet rooms and inlets in the living rooms is checked like any other. Inlets need a hole through their wall like a decentral unit (`W-VENT-003`, `W-VENT-006`).

**Overflow openings** (`over ue1 d3 cut=0.01` or `area=150`): the undercut of a door (its width × the cut) or an overflow element with its free area. Once `vent.uea` has one, `airflow` checks every supply and extract room: the free area of the openings in its doors against the area its flow needs, from the office's table `vent-overflow` (by flow). The air's way through the overflow zone is not followed; each room is checked at its own doors. Before the first `over`, no room is checked, so a model in progress does not fail on it.

**Terminal and silencer losses.** An air terminal gives its loss at its design flow (`dp=`), a central unit the loss of the silencers on each side (`sil=`); `ducts` adds them to the ways and the fans' pressure.

**Heat recovery in the Heizlast.** `uea calc heatload ... insulation=high|low` takes the ventilation system in: with the flows of `airflow` (which is why it needs the building's insulation), the supply air comes in at θ_su = θ_e + η · (θ_ex − θ_e), with η the unit's `hr=`. An extract room draws its air over from the others, and outdoor air makes up what falls short of V̇_min (DIN EN 12831-1, 6.3.3, simplified). Without the setting the Heizlast is as before, on the safe side.

**IFC.** Units (IfcUnitaryEquipment AIRHANDLER, decentral units as USERDEFINED, exhaust fans IfcFan), terminals and inlets (IfcAirTerminal: DIFFUSER, GRILLE, LOUVRE) as boxes, the derived ducts as swept circles (IfcDuctSegment), each unit's network of one kind of air an IfcDistributionSystem VENTILATION with its members. The ducts are drawn at the smallest size of the duct type: their sizes need the office's tables, and the export does not. The export no longer picks up a caller's owner-history settings.

## Alternatives

- **An overflow element in a wall:** rarer in a house; a door undercut and an element in the leaf cover the Einfamilienhaus. It can follow as a wall host later.
- **Following the air through the overflow zone:** needs the graph of rooms and doors; the room check at its doors is what a planner checks first.
- **Heat recovery always on:** the Heizlast would then need the ventilation tables for every project. With the setting the planner chooses, and the result names the tables.
- **Ducts at their computed sizes in the IFC:** the export would depend on the office's tables.

## Consequences

- `airflow` 0.2.0, `ducts` 0.2.0, `heatload` 0.3.0 (with 0042); validation reports updated.
- New kinds `inlet`, `over`, type `inlet`; table `vent-overflow`.
- Open: overflow elements in walls, the way through the overflow zone, heating and plumbing in the IFC, the losses at flows other than the design flow.

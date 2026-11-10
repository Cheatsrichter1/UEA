# Medical and hospital systems

[Decision records](README.md)

## 0058 Medical and hospital systems

A new discipline `med` (`med.uea`) for what a hospital needs beyond the services of a house. It sits beside `heat`, `plumb` and `vent`, below the architecture and above the electrical design, which feeds its panels, IT systems and gas plants.

| Kind | Id | Where |
|---|---|---|
| `gsrc` | gq | the central supply of one gas in a room: `o2`, `air`, `air8`, `vac`, `n2o`, `co2`, `agss`; `via=` its slab holes |
| `gas` | ge | outlets side by side: on a wall face (`gases=o2,air,vac`, z 1.6) or a ceiling pendant in a room (`at=`) |
| `fpanel` | bz | the fire alarm panel (BMZ) on a wall |
| `fdet` | md | an automatic detector at a room's ceiling, `sensor=smoke\|heat\|multi` |
| `mcp` | hm | a manual call point on a wall, z 1.4 |
| `cpanel` | rz | the nurse call panel at the nurses' station |
| `call` | ru | a nurse call device: `bed`, `pull`, `lamp` (over a door outside, `door=` that door), `duty` |
| `medloc` | mb | a room's medical location group 0, 1 or 2; `it=` its IT system |
| `itsys` | it | a medical IT system (isolating transformer, insulation monitor) on a wall; `sv=` its safety source |
| `safety` | sv | a safety power source in a room: `ups`, `genset`, `battery`, `kw=` |

- **Derived:** the gas pipes, one network per source and gas. Each outlet takes each of its gases from the nearest source of that gas. On the source's storey the shortest rectilinear tree over its outlets; every other storey gets one riser from the source (through `via=` or a shaft, decision 0045) to its nearest outlet and a tree over that storey's outlets from there. Gas pipes do not hop between the outlets of two storeys, as the shortest tree would through the bathroom shafts. They follow the installation zones. Also derived: the detectors and calls in each room, the room each door lamp signals (its door's `into=`), each room's medical location.
- **Checks** `W-MED-001` to `W-MED-040`, `E-MED-002`: outlets without a source, sources without outlets, pipes through slabs without a hole; with a fire alarm panel, every room but baths and WCs has a detector, every storey with detectors a manual call point; with a nurse call panel, bedrooms have a bed call, baths and WCs a pull call, rooms with bed calls a door lamp; group 2 needs an IT system, the IT system a safety source, and not a genset alone; group 1 or 2 needs a safety source; panels, IT systems and the machine-made gases (`air`, `air8`, `vac`, `agss`) need a `feed`.
- **The checks are planning rules and cite no norm.** What a building needs is fixed by the Brandschutzkonzept, the clinic and the standards the planner applies (DIN VDE 0100-710, DIN VDE 0833-2, DIN VDE 0834, DIN EN ISO 7396-1). A rule that does not fit a room is waived there with the reason. The panel rules apply only once there is a panel: a building without one has not planned that system yet. Room rules sit on the room, like `W-ELEC-010`, so they can be waived per room.
- **Plans** `med:EG` (M-01): group 1 and 2 locations tinted, gas pipes in one plot colour per gas, symbols for every device. A section that changes storey through a hole is drawn to that hole on both storeys, with a ring there; this applies to the heating and ventilation plans too.
- **Not yet:** a calculator for the gas flows and pipe sizes (it needs the office's tables), zone valve boxes, IFC export of the new kinds, circuits without an RCD for the IT systems' primary side (`circ` needs an `rcd`), safety lighting, a room use for patient rooms (they are `bedroom`).

Why: the electrical pack could have taken the fire alarm, the nurse call and the IT systems, but these are separate trades (Fachplaner, Errichter, Abnahme) with their own drawings, and the elec pack already feeds things of other packs. Putting them above `elec` lets a `feed` reach them without a new reference direction. Group and system requirements were kept out of code as numbers: the switch-over times, detector spacing and outlet counts are norm values, and the clinic decides the groups.

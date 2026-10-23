# Heating, plumbing and ventilation

The `heat`, `plumb` and `vent` packs, their derived networks, sheets and calculators. Every sizing needs the office's tables, so none of it is a check in `uea check`, which must read the same on every machine. Index in [README.md](README.md).

## 0033 U-values and Heizlast

- **`uea calc uvalue [scope]`** (DIN EN ISO 6946): per build-up (a wall, slab or roof type, or a slab with a room's floor type, `DE-20 + FB-par`) and per use (heat-flow direction, what lies beyond). R = d / λ per homogeneous layer, U = 1 / (R_si + Σ R + R_se). λ from table `material` by the layer's material name; R_si, R_se from `surface`; R_se = 0 to the ground, = R_si to a room.
- **The surfaces of a room** (`packs/heat/envelope.py`): the shell outline is matched to the walls; beyond each stretch a 0.3 m strip finds the neighbour room, else outside air (exterior wall) or unknown (counted as outside, noted). Heights FFL to FFL; below `ground=` the wall borders the ground. Windows and doors are subtracted. Floors and ceilings are shared with the rooms below and above by overlap; the ground below the lowest storey; a roof's sloped area above.
- **`uea calc heatload tb= n50= shielding= [scope]`** (DIN EN 12831-1 with DIN/TS 12831-1): Φ_HL = Φ_T + Φ_V. Φ_T = Σ A · U_c · f · (θ_int − θ_e), U_c = U + ΔU_TB; f is 1 to outside, f_g1 · (θ_int − θ_m,e)/(θ_int − θ_e) · G_w to the ground, (θ_int − θ_j)/(θ_int − θ_e) to a room. Φ_V = V̇ · ρc_p · (θ_int − θ_e), V̇ = max(2 · V · n_50 · e · ε, n_min · V). The building's load is the sum without flows between rooms.
- **Tables:** `material`, `surface`, `outdoor` (θ_e, θ_m,e by postcode), `room-temp` (by room use), `infiltration`, `height-factor`, `heatload-factors`. `tb`, `n50`, `shielding` have no default; `te=`, `tme=` override `outdoor`.
- **Stated deviations:** the component U instead of U_equiv to the ground (safe side), the room infiltration formula instead of q_env50, no reheat or neighbouring buildings.

Why: in `uea get` the values would differ by machine; λ in the model would carry licensed values with every copy; shell outlines with storey heights are what the model derives exactly. Two calculators, because U-values are useful alone.

## 0034 Heating elements

| Kind | Id | Where | `src=` |
|---|---|---|---|
| `gen` | g | a storey and `at=`, inside or outside | |
| `tank` | t | a room, `at=` | a generator |
| `man` | hv | a niche (`man hv1 ni1 t1`) or a wall face | a tank or generator |
| `ufh` | uh | a room (`area=`, else the finished floor) | a manifold |
| `rad` | hk | a wall face | a manifold, tank or generator |

- Types carry the maker's data: `gen kw= source=`, `tank vol= dhw`, `man outlets= w=`, `ufh spacing= q= max=`, `rad w= length= height=`. An element without `type=` takes the kind's `default`.
- **Derived:** underfloor loops (pipe = area / spacing, plus the rectilinear run to the manifold and back; as few equal loops as keep each within `max=`), what each generator, tank and manifold supplies, each emitter's output.
- Checks `W-HEAT-001` to `004`, `E-HEAT-002`. Emitters against the Heizlast are checked by `uea calc heatload`: each room's shortfall, the generators against the building; a shortfall fails.
- `feed` lines reach generators, tanks and manifolds; electrical derives after heating.

Why: output per DIN EN 1264 and 442 needs licensed tables (later, 0042); the loop count is derived like cable lengths; a manifold in a niche is where a request put it.

## 0035 Plumbing

| Kind | Id | Where |
|---|---|---|
| `san` | sa | a wall face or a room; fixture: basin, sink, wc, urinal, bidet, shower, bath, wm, dw, tap, floor |
| `meter` | wz | a room; `p=` lowest supply pressure, `dp=` meter loss |
| `riser` | sr | a room; cold and hot water up through the storeys |
| `stack` | fl | a room; a Fallleitung vented through the roof |
| `sewer` | kn | a storey and `at=`, inside or outside |

- `water=cold|both|none` with defaults per fixture; `z=` the outlet height. Types: `pipe sizes=16x2,... k= bend= tee=` and `drain sizes=100:110x2.7,...`. Hot water comes from heating tanks with `dhw` (plumbing may reference heating, not the reverse); the tank type gets `dp=`.
- **The pipes are derived:** cold water as the shortest rectilinear tree from the meter over fixtures and `dhw` tanks, growing from risers on other storeys; hot water from the nearest `dhw` tank; waste water from each fixture to its stack (`to=` or nearest) or the sewer, branches per stack and storey, the stack to its foot, the feet to the sewer, at the FFL. Each section knows its fixtures, length and bends.
- Checks `W-PLUMB-001` to `005`, `E-PLUMB-002`.
- **`uea calc water`** (DIN 1988-300): ΣV̇_R per section, V̇_S = a · (ΣV̇_R)^b − c bounded; the smallest size within v_max; Darcy-Weisbach with Colebrook-White and ζ for bends and tees; the pressure at each fixture p_min,V − Δp_apparatus − Δp_geo − ΣΔp ≥ p_min,Fl, growing the worst section until met. Tables `fixture-flow`, `peak-flow`, `water-factors`; `building=`.
- **`uea calc drain slope=<%>`** (DIN 1986-100): Q_ww = K · √ΣDU; branch DN by fixture, collecting branches and stacks by Q_max tables, pipes under the building by Prandtl-Colebrook at the slope and filling; no section smaller than one feeding it; unvented branch lengths checked. Tables `fixture-drain`, `drain-k`, `drain-branch`, `drain-stack`, `drain-factors`.
- Formulas live in `hydraulics.py`; the standards' numbers come from the office.

Why: pipes as elements would be many lines of what code derives; agents steer the trees with risers, stacks and `to=`.

## 0036 Heating and plumbing sheets

- **Plans per storey** (`export/tga.py`), like the installation plan: `heat:EG` (underfloor areas in pale red with loops and output, manifolds, radiators, generators, tanks; H-01...) and `plumb:EG` (fixtures with marks WT, WC, DU..., meter, risers, stacks, sewer, tank; derived pipes cold green, hot orange, waste brown dashed; S-01...). DXF layers `H-`, `S-`.
- **Heizungs- und Trinkwasserschema** (`export/schema.py`, `heat:schema`, H-00): generators and tanks, a row per manifold with a zigzag per loop and a box per radiator, cold and hot water to each fixture at the foot. What it leaves out is written on it.
- **Tables:** Heizflächen, Heizkreisverteiler, Sanitärobjekte, Rohrleitungen, Rohrmengen. Sizes are not in them.
- **Calculation reports as PDF** (`export/report.py`): `uea export pdf <result>` sets `out/<result>.md` on A4 with a header (calculator, version, kind, batch, "ENTWURF – nicht unterzeichnet"), page numbers and an empty signature block. It refuses a result whose model files changed since. Set in bundled DejaVu Sans (`src/uea/export/fonts/`, subset by `tools/fonts/subset.py`) so Φ and θ print everywhere.

Why: two plans follow the trades and stay legible at 1:50; sizes would make sheets differ by machine; one Markdown renderer serves every calculator; signing stale numbers is the error to prevent.

## 0037 Heating pipes and Strangschema

- **Heating pipes are derived:** from each generator and tank the shortest rectilinear tree over what it supplies (`src=`), one section standing for flow and return; a home run from each manifold to each radiator; underfloor loops are the manifold's. Shared code in `packs/net.py`, `pipes.py`, `hydraulics.py`.
- Types: `hpipe sizes=15x1,... k= bend= tee= default`; the underfloor type's `pipe=16x2 k=`; the generator's `dp=`.
- **`uea calc hydronic tb= n50= shielding= spread= vmax=`** (hydraulic balance, Verfahren B): each room's Heizlast shared among its emitters; V̇ = Φ / (ρ c_p Δθ); loops share their underfloor flow; sections take the smallest size within `vmax=` and lose 2 · (R l + Σζ ρv²/2). The worst circuit sets each manifold's loss and the others' valves take the difference (kv); the worst end sets each pump head. A tank separates generator and heating circuits.
- The heating sheets draw flow red and return blue dashed, with a ring where a pipe changes storey.
- **Strangschema** (`plumb:schema`, S-00, not to scale): storeys as bands, meter and tanks, risers and stacks as verticals through the roof and to the sewer, each storey's distribution and waste. No sizes.

Why: Verfahren B starts from room loads, not emitter outputs; one spread per calculation until mixers exist (0042); the planner picks pumps and valves from head and kv.

## 0038 Ventilation

| Kind | Id | Where |
|---|---|---|
| `ahu` | lg | a central unit with heat recovery in a room, `z=` 1.8 |
| `fan` | vl | a decentral unit on an exterior wall, `z=` 2.2; `mode=alt\|ext\|both`, `pair=` |
| `air` | ld | a terminal: `sup` or `ext` in a room, `oda` or `eha` on an exterior wall; `src=` its unit |

- Types: `ahu flow= dp= hr=`, `fan flow= hr=`, `duct sizes=80,100,... k= bend= tee=`.
- **Derived:** the second half of each pair; per unit and kind of air the shortest rectilinear duct tree over its terminals; what each room has. `feed` lines reach the units.
- Checks `W-VENT-001` to `005`, `E-VENT-002`.
- **`uea calc airflow n50= insulation=high|low`** (DIN 1946-6, the Lüftungskonzept): the dwelling is every room `vent-room` does not mark `none`; q_v,ges = f · (a A² + b A + c) for FL, RL, NL, IL (`vent-total`); q_v,inf from `vent-infiltration`, a measure is needed if q_v,inf < q_v,ges,FL. Design flow max(q_NL, Σ extract), extract rooms from `vent-room`, supply rooms by f_R. A push-pull unit gives half each way. A short room, an undersized unit or a needed measure without a system fails.
- **`uea calc ducts n50= insulation= vmax=`:** flows from `airflow`; the smallest diameter within `vmax=`, Δp = R l + Σζ ρv²/2; each side's worst way against the unit's `dp=`, the rest throttled.
- Plans `vent:EG` (L-01): ducts outdoor green, supply blue, extract yellow, exhaust brown. Tables Lüftungsgeräte, Luftdurchlässe, Luftleitungen, Luftmengen.

Why: room flows are derived by the standard from area and use, not written by the agent; its coefficients are licensed. Haus Müller's two decentral pairs gave 60 of 164 m³/h, so the design moved to a central unit, which meets every room.

## 0042 Emitters, mixing and circulation

- **Emitter output** (`packs/heat/emitters.py`): a type keeps `w=`/`q=` at design temperatures, or gives test values: radiator `wn=` (75/65/20 °C) and `n=`, Φ = Φ_n · (Δθ/Δθ_n)^n with the logarithmic excess temperature (DIN EN 442-2); underfloor `kh=`, q = K_H · Δθ_H (DIN EN 1264-2), with `heatload floor=` and `bathfloor=` failing a floor that is too warm. Temperatures from the manifold (`flow= spread=`), else the system's.
- **Mixing:** a manifold with `mix` runs its circuits at its own `flow=` and spread and draws V̇ = Φ / (ρ c_p (θ_V,system − θ_R,circuit)); in the balance its mixing valve is the throttle, with kv.
- **Circulation:** `recirc zk1 t1` derives the return beside the tank's hot-water pipes except single-fixture branches. `uea calc recirc loss=<W/m> dt=<K> dead=<l>` (DIN 1988-300 short method): flows carry the heat lost beyond at the allowed drop; size within v_max; pump head from the worst end; uncirculated branches checked against `dead=` (the planner sets DVGW W 551's 3 l). `W-PLUMB-007`.

Why: exponents and K_H are catalogue and norm data; circulating every short branch wastes heat; the short method is the standard's for houses.

## 0043 Ventilation details

- **Inlets:** `inlet al1 w1 x=W+2` with type `inlet flow=`, counted as the room's supply in `airflow`; they need a hole like a decentral unit.
- **Overflow openings:** `over ue1 d3 cut=0.01` (door undercut) or `area=150`. Once `vent.uea` has one, `airflow` checks each supply and extract room's door openings against table `vent-overflow`.
- **Losses:** terminals `dp=`, units `sil=` for silencers; `ducts` adds them.
- **Heat recovery in the Heizlast:** `heatload ... insulation=` takes the system in: supply air at θ_e + η (θ_ex − θ_e) with η = `hr=`; extract rooms draw from others (DIN EN 12831-1 6.3.3, simplified). Without the setting, as before.
- **IFC:** units, terminals and inlets as boxes, derived ducts as swept circles at the type's smallest size, a VENTILATION distribution system per network.

Why: following air through the overflow zone needs a room graph; heat recovery always on would require ventilation tables in every project; computed duct sizes would tie the IFC to the office's tables.

# Electrical and lighting

The `elec` and `light` packs, their sheets and calculators. Index in [README.md](README.md).

## 0025 Electrical devices

**Kinds** (`elec.uea`), placed by anchors like openings:

| Kind | Id | Line |
|---|---|---|
| `board` | `b` | `board b1 w6.w y=w3-0.6 z=1.4 main=SLS-E35 spd=T1+T2 meters=1`, `media` for a Medienverteiler |
| `rcd` | `fi` | `rcd fi1 b1 40/0.03 A` |
| `circ` | `c` | `circ c1 fi1 NYM-J5x2.5 B16 p=3 "Küche Herd"` |
| `sock` | `s` | `sock s4 w4 c4 y=f2+0.3 z=1.15 n=2` |
| `conn` | `a` | `conn a1 w4 c1 y=w1+0.9 z=0.6 w=7000` |
| `switch` | `sw` | `switch sw2 w5.s c10 x=d2+0.15 ctl=l2,l3`, `dim` |
| `data` | `dt` | `data dt1 w2 b2 y=w5-0.75 n=2` |
| `smoke` | `rm` | `smoke rm1 r5` |
| `feed` | `fd` | `feed fd1 g1 c7`: a circuit feeding another discipline's element |

The light pack holds the luminaire types (`flux`, `w`, `dist`) and `lum`, in a room (default at the ceiling middle) or on a wall. Cables, breakers and RCDs are parsed designations, not types.

- **Placement** (`packs/mount.py`): a device stands on a wall face; exterior walls take it on the room side, interior walls need the face (`w5.n`). Default heights: sockets and data 0.3, switches 1.05. Its room is the one 5 cm in front of the face.
- **A luminaire's circuit is its switches'.** `ctl=` lists the luminaires (`,` channels, `+` joined); one switch is single, two a Wechselschaltung, three a Kreuzschaltung.
- **Circuit load** is the luminaires' `w`, connections and feeds against breaker × 230 V × phases. Sockets carry no declared load. Arithmetic, not a norm's Gleichzeitigkeit.
- **Checks** are our own planning rules: E-ELEC-001 to 006 (placement), E-ELEC-011, W-ELEC-012 (switch behind a door leaf, from the same `door_hinge` that draws the swing), W-ELEC-020 (overload), W-ELEC-022, W-ELEC-030/031, W-ELEC-040 (no RCD). `W-ELEC-010` is the calculator `equip` (0041).
- Devices follow upstream moves; `uea get` gives face, position, room, circuit, RCD and board; XLSX adds Verteiler, Stromkreise, Installationsgeräte and Leuchten.

Why: cable types in the project would be the same twenty lines in every office; a circuit on the luminaire would hide unswitched luminaires; guessed socket loads invent numbers; DIN 18015-3 clearances are licensed.

## 0026 Electrical sheets

- `uea export pdf|dxf|svg|png elec`, `elec:EG` (installation plan), `b1` (board diagram).
- **Installation plan** (`export/install.py`, `symbols.py`): the floor plan in grey as background, our own simplified symbols "in Anlehnung an DIN EN 60617", colour per circuit with the circuit id beside each device, dashed switching lines. 1:50 where it fits; legend left of the title block. German `E-` DXF layers.
- **Board diagram** (`export/board.py`): single-line, not to scale: supply, meter, SLS, busbar, SPD, each RCD with its circuits (breaker, poles, phase, cable, label, what hangs on it).
- **Phases are derived** (`share_phases`): each single-phase circuit to the least-loaded phase (at least 1000 W each), three-phase a third on each. **The field is derived:** rows of 12 TE; SPD and RCD 4 TE, breakers 1 TE per pole. Both assumptions are printed.

Why: copying the standard's symbols copies its content; wire lines would invent routes; rotating phases per RCD leaves boards unbalanced.

## 0027 Cable routes

- A circuit's cable is the shortest tree from its board (Prim, ties to the lower id) over every socket, connection, switch and controlled luminaire. Derived, never stored.
- A run is rectilinear (Σ |Δx| + |Δy| + |Δz|) between absolute device heights, plus 0.3 m per run for ends and loops (a planning allowance).
- Data outlets have one run per port from their board. A `feed` reaches its element where it has a place; otherwise it is "not placed".
- `uea get c10`: `cable 58.1 m in 21 runs | farthest l18 at 25.4 m`. XLSX: Leitungen, Kabelmengen, cable columns on Stromkreise.
- On storeys with installation zones the runs follow them (0045). Otherwise the lengths are a lower bound; calculators add a reserve and record it.

Why: straight lines are short by a third and flatter the voltage drop; an agent-declared chain or length is a guess UEA exists to remove.

## 0028 Norm tables and electrical calculators

**Storage:** `uea data` manages tables on the machine (`UEA_DATA`, else `$XDG_DATA_HOME/uea`, else `~/.local/share/uea`), one `tables/<id>.json` each; never in a project.

| Command | |
|---|---|
| `uea data` | the tables the calculators need and what is installed |
| `uea data show <id>` | columns, what to copy into them, what is installed |
| `uea data add <id> <file.csv> --edition <e> [--source <s>]` | check and install |
| `uea data remove <id>` | |

- **Format:** one CSV per table; comma or semicolon (then a decimal comma); `#` lines skipped; numbers > 0; unique keys. Every fault is reported with its line and nothing is installed unless all is valid. The edition is required; the SHA-256 of the CSV is kept.
- **Calculators declare** their tables (`Spec`: id, title, standard, columns, key) and settings (`params`). The same declarations feed `uea data show`, errors and `docs/reference.md`. Missing tables stop the calculator with the command to add them.
- Results record settings and, per table, id, standard, edition, source and hash.
- **`cable`:** In ≤ Iz from `ampacity` by installation method (required), insulation, loaded conductors and section, times `temp-factor` and `group-factor` when set; I2 = 1.45 In follows for B, C, D breakers. Names the smallest sufficient section. Never interpolated; copper only.
- **`vdrop`:** ΔU = b · (ρ L / S · cos φ + λ L sin φ) · I, as % of 230 V (IEC 60364-5-52 Annex G); ρ and λ from `conductor`; L the derived length times `reserve` (1.2); I the declared load, or In × `demand` with sockets; `limit` required.
- `W-ELEC-010` is a calculator, so `uea check` is the same on every machine.

Why: tables in the repo or project break the licences; CSV is what an agent or a spreadsheet writes; interpolation and built-in ρ, λ or limits would put the standard's numbers or invented values in code.

## 0041 Minimum equipment

`uea calc equip grade=<g> [scope] [combos=one|each]` (`packs/elec/equip.py`), a `norm` calculator for DIN 18015-2.

- Table `elec-minimum`: use, grade, area up to, and the numbers of sockets, lighting outlets, communication outlets and dedicated connections. A room takes the first row whose area covers its finished area; past the last row it takes the last and says so.
- Counts what the model mounts in the room. `combos` is the office's reading of multi-outlet frames.
- `waive _ W-ELEC-010 <room> "reason"` accepts a shortfall; the report lists it.

Why: as a check it would differ by machine; counting switches instead of luminaires is wrong; the numbers are licensed.

## 0050 Illuminance

- **`illum il1 r2 em=150 h=0.75 "label"`** in `light.uea`: the maintained illuminance the working plane must reach; with `at=` and `area=` a task area. The target is the planner's (DIN EN 12464-1 or the client's wish).
- **`uea calc light refl=<r> mf=<f> [scope]`** (`packs/light/illuminance.py`), utilisation factor method (LiTG 3.5, CIE 40): Ē = MF · Σ Φᵢ · UFᵢ / A, with k = 2A / (hᵢ U) per luminaire.
- Table `light-uf`: UF by distribution (`dist=`), reflectances (`refl=`, e.g. 753) and k, linear between rows of k; outside the table the room is "without data". `mf` and `refl` have no defaults.
- A low room names how many more luminaires of its main type reach the target. Luminaires at or below the plane add nothing. Task areas are listed, not checked.

Why: a point calculation needs photometric files and interreflection to be acceptable (later); dwelling targets are design decisions, not table values; a default MF of 0.8 would hide an assumption the signer must make.

"""A generated large project: an apartment block, to measure what partial views cost.

`block(storeys, units)` gives the text of each `.uea` file. The block is a row of flats,
`units` per storey, each a bay of 8 by 12 m with a living room to the south and a bedroom to the
north, its own board with circuits and sockets, and underfloor heating from a manifold in the
flat. One heat pump and one tank feed every manifold. Storeys stack their walls with `on=`.

The types and products are illustrative placeholders, like those of Haus Müller.
"""

from pathlib import Path

BAY = 8.0
DEPTH = 12.0
HEIGHT = 2.9


def level_name(i: int) -> str:
    return "EG" if i == 0 else f"OG{i}"


def block(storeys: int = 8, units: int = 6) -> dict[str, str]:
    project = [
        'project block "Wohnblock"',
        *(
            f"level {level_name(i)} z={round(i * HEIGHT, 3):g} fb=0.15 head=2.26"
            for i in range(storeys)
        ),
        "grid W x=0",
        f"grid E x={units * BAY:g}",
        "grid S y=0",
        f"grid N y={DEPTH:g}",
    ]
    arch = [
        "type AW wall layers=putz:0.015,*ziegel:0.365,putz:0.02",
        "type TW wall layers=putz:0.015,*ks:0.24,putz:0.015",
        "type IW wall layers=putz:0.015,*ks:0.115,putz:0.015",
        "type DE slab layers=*stb:0.2,putz:0.01",
        "type FB floor layers=parkett:0.015,ze:0.065,eps:0.07",
        "type FE win default",
        "type TI door default",
    ]
    elec: list[str] = []
    heat = [
        'type WP gen "Wärmepumpe" kw=60 source=air dp=120',
        'type SP tank "Speicher" vol=1000 dhw dp=150',
        'type HKV man "Heizkreisverteiler" outlets=8 w=0.6 default',
        'type FBH ufh "Fußbodenheizung" spacing=0.15 q=60 max=100 pipe=16x2 k=0.007 default',
        'type CU hpipe "Kupferrohr" sizes=15x1,18x1,22x1,28x1.5,35x1.5 k=0.0015 bend=0.5 tee=1.3'
        " default",
    ]
    ids = {"w": 0, "d": 0, "f": 0, "r": 0, "sl": 0, "ni": 0, "sh": 0}

    def new(prefix: str) -> str:
        ids[prefix] += 1
        return f"{prefix}{ids[prefix]}"

    first: dict[str, str] = {}
    """Walls of the ground storey, by role, that the storeys above stack on."""

    def wall(s: int, walls: dict[str, str], role: str, line: str) -> str:
        """A wall of storey s; above the ground storey it stands on the one below."""
        ident = new("w")
        if s == 0:
            arch.append(f"wall {ident} EG {line}")
            first[role] = ident
        else:
            lb = " lb" if line.endswith(" lb") else ""
            top = " h=2.75" if s == storeys - 1 else ""
            arch.append(f"wall {ident} {level_name(s)} {line.split()[0]} on={first[role]}{lb}{top}")
        walls[role] = ident
        return ident

    board = rcd = circ = sock = man = ufh = 0
    roof = level_name(storeys - 1)
    for s in range(storeys):
        lv = level_name(s)
        arch.append(f"slab {new('sl')} {lv} DE")
        walls: dict[str, str] = {}
        south = wall(s, walls, "s", "AW y=S+ x=W..E lb")
        north = wall(s, walls, "n", "AW y=N- x=W..E lb")
        east = wall(s, walls, "e", f"AW x=E- y={south}..{north} lb")
        west = wall(s, walls, "w", f"AW x=W+ y={south}..{north} lb")
        for u in range(units):
            x0 = u * BAY
            left = west if u == 0 else walls[f"p{u}"]
            if u < units - 1:
                wall(s, walls, f"p{u + 1}", f"TW x=W+{x0 + BAY:g} y={south}..{north} lb")
            right = east if u == units - 1 else walls[f"p{u + 1}"]
            mid = wall(s, walls, f"m{u}", f"IW y=S+6 x={left}..{right}")
            liv, bed = new("r"), new("r")
            arch.append(
                f'room {liv} {lv} "Wohnen {s}.{u + 1}" living at={left}+1,{south}+1 floor=FB'
            )
            arch.append(
                f'room {bed} {lv} "Schlafen {s}.{u + 1}" bedroom at={left}+1,{north}-1 floor=FB'
            )
            arch.append(f"door {new('d')} {mid} 0.885x2.01 x={left}+1.5 into={bed} hand=l")
            arch.append(f"win {new('f')} {south} 1.51x1.26 x=W+{x0 + 3:g}")
            arch.append(f"win {new('f')} {north} 1.26x1.26 x=W+{x0 + 3:g}")
            if s == 0:
                arch.append(f"shaft {new('sh')} EG 0.6x0.5 at={right}-0.6,S+5.5 to={roof}")
            ni = new("ni")
            arch.append(
                f"niche {ni} {mid}.s 0.5x0.75 x={right}-{1.6 + 0.8 * (s % 2):g} sill=0.3 d=0.1"
            )
            board += 1
            b = f"b{board}"
            elec.append(f'board {b} {mid}.n x={right}-0.8 z=1.6 "UV {s}.{u + 1}"')
            rcd += 1
            fi = f"fi{rcd}"
            elec.append(f"rcd {fi} {b} 40/0.03 A")
            for host, side in ((south, "Wohnen"), (north, "Schlafen")):
                circ += 1
                c = f"c{circ}"
                elec.append(f'circ {c} {fi} NYM-J3x2.5 B16 "{side}"')
                for k in range(3):
                    sock += 1
                    elec.append(f"sock s{sock} {host} {c} x={left}+{1 + 2 * k:g}")
            man += 1
            hv = f"hv{man}"
            heat.append(f"man {hv} {ni} t1")
            for room in (liv, bed):
                ufh += 1
                heat.append(f"ufh uh{ufh} {room} {hv}")
    heat.insert(5, "gen g1 EG at=W-1.5,N-1 type=WP")
    heat.insert(6, f"tank t1 r1 at={first['w']}+0.6,{first['s']}+0.6 src=g1 type=SP")
    return {
        "project.uea": "\n".join(project) + "\n",
        "arch.uea": "\n".join(arch) + "\n",
        "elec.uea": "\n".join(elec) + "\n",
        "heat.uea": "\n".join(heat) + "\n",
    }


def write(root: Path, storeys: int = 8, units: int = 6) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in block(storeys, units).items():
        (root / name).write_text(text, encoding="utf-8")

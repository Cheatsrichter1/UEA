"""The token task set: fixed agent tasks with a reference solution and an end-state check.

The reference solution is what a careful agent types; the runner counts the tokens of the
commands, the operations and UEA's output. A change to the file format or the CLI output must
keep or lower these numbers (CLAUDE.md, ROADMAP.md). Agent runs, which add the error rate,
use the same briefs and checks.
"""

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from uea.derive import report
from uea.project import Project

ROOT = Path(__file__).resolve().parent.parent
PROTOTYPE = ROOT / "docs" / "prototype" / "haus-mueller"


@dataclass
class Step:
    args: list[str]
    stdin: str | None = None


@dataclass
class Task:
    id: str
    brief: str
    steps: list[Step]
    check: Callable[[Project], list[str]]
    setup: str | None = None
    """'house': start from the Haus Müller prototype; a task id: run that task's steps first."""
    notes: list[str] = field(default_factory=list[str])


def apply(by: str, msg: str, ops: str) -> Step:
    return Step(["apply", "--by", by, "-m", msg], ops)


BATCH1 = """\
+ project haus-mueller "EFH Müller" site=DE-HE postcode=64283 ground=-0.3
+ level EG z=0 fb=0.15 head=2.26
+ level OG z=2.875 fb=0.15 head=2.26
+ level DB z=5.86 fb=0.26
+ grid W x=0
+ grid E x=10.49
+ grid S y=0
+ grid N y=8.49
+ type AW-365 wall "Ziegel 36,5 verputzt" layers=putz-kalkgips:0.015,*ziegel-t9:0.365,putz-leicht:0.02
+ type IW-240 wall "KS 24 verputzt" layers=putz-kalkgips:0.015,*ks:0.24,putz-kalkgips:0.015
+ type IW-115 wall "KS 11,5 verputzt" layers=putz-kalkgips:0.015,*ks:0.115,putz-kalkgips:0.015
+ type BP-25 slab "Bodenplatte 25 cm" layers=*stb:0.25,xps:0.14
+ type DE-20 slab "Stahlbetondecke 20 cm" layers=*stb:0.2,putz-gips:0.01
+ type FB-par floor "Parkett auf Heizestrich" layers=parkett:0.015,ze:0.065,eps-tsd:0.03,eps:0.04
+ type FB-fli floor "Fliese auf Heizestrich" layers=fliese:0.015,ze:0.065,eps-tsd:0.03,eps:0.04
+ type FB-db floor "Dämmung oberste Geschossdecke" layers=osb:0.02,eps:0.24
+ type DA-25 roof "Ziegel auf Sparren" layers=ziegel:0.04,lattung:0.03,konterlattung:0.04,*sparren:0.18
+ type FE-3S win "Kunststofffenster 3-fach" uw=0.9 default
+ type TI-1 door "Innentür" default
+ type TH-1 door "Haustür" ud=1.3
+ type HST-1 door "Hebeschiebetür" uw=0.9
"""

BATCH_EG = """\
+ wall @s EG AW-365 y=S+ x=W..E lb
+ wall @o EG AW-365 x=E- y=@s..@n lb
+ wall @n EG AW-365 y=N- x=W..E lb
+ wall @w EG AW-365 x=W+ y=@s..@n lb
+ wall @m EG IW-240 y=@s+4.51 x=@w..@o lb
+ wall @h EG IW-115 x=@w+2.26 y=@m..@n
+ wall @k EG IW-115 x=@h+1.385 y=@m..@n
+ door _ @o 1.135x2.26 y=@m+0.385 into=@diele hand=l type=TH-1
+ door _ @m 0.885x2.01 x=@k+1.76 into=@wohn hand=l
+ door _ @k 0.76x2.01 y=@m+0.26 into=@diele hand=r
+ door _ @m 0.885x2.01 x=@h-0.135 into=@hwr hand=l
+ door _ @s 2.26x2.26 x=W+5.385 type=HST-1
+ win _ @s 1.26x1.26 x=W+1.51
+ win _ @w 1.26x1.135 y=S+1.76
+ win _ @s 1.26x2.26 x=W+8.26
+ win _ @o 1.51x1.51 y=S+1.385
+ win _ @n 1.01x1.01 x=W+0.885
+ win _ @n 0.76x1.01 x=W+3.01
+ stair @st EG OG y=@n- x=@o-1.125 up=w w=1 n=16 tread=0.26
+ slab _ EG BP-25
+ slab @d OG DE-20
+ void _ @d over=@st
+ sep _ EG x=@w+3.51 y=@s..@m
+ room _ EG "Küche" kitchen at=@w+1,@s+1 floor=FB-fli
+ room @wohn EG "Wohnen/Essen" living at=@o-1,@s+1 floor=FB-par
+ room @hwr EG "HWR" utility at=@w+1,@n-1 floor=FB-fli
+ room _ EG "WC" wc at=@h+0.5,@n-1 floor=FB-fli tile=1.2
+ room @diele EG "Diele" hall at=@o-1,@m+1 floor=FB-fli
"""

BATCH_OG = """\
+ wall @s OG AW-365 on=w1 lb
+ wall @o OG AW-365 on=w2 lb
+ wall @n OG AW-365 on=w3 lb
+ wall @w OG AW-365 on=w4 lb
+ wall @m OG IW-240 on=w5 lb
+ wall @a OG IW-115 x=@w+4.01 y=@s..@m
+ wall @b OG IW-115 x=@a+2.885 y=@s..@m
+ wall @c OG IW-115 x=@w+2.76 y=@m..@n
+ door _ @c 0.885x2.01 y=@m+0.26 into=@bad hand=r
+ door _ @m 0.885x2.01 x=@c+0.125 into=@schlafen hand=r
+ door _ @m 0.885x2.01 x=@a+0.135 into=@k1 hand=l
+ door _ @m 0.885x2.01 x=@b+0.135 into=@k2 hand=l
+ win _ @s 1.51x1.385 x=W+1.385
+ win _ @w 1.01x1.385 y=S+2.01
+ win _ @s 1.26x1.385 x=W+5.26
+ win _ @s 1.26x1.385 x=W+8.135
+ win _ @o 1.01x1.385 y=S+2.26
+ win _ @w 1.01x1.01 y=S+6.135
+ win _ @n 1.26x1.26 x=W+6.51
+ room @schlafen OG "Schlafen" bedroom at=@w+1,@s+1 floor=FB-par
+ room @k1 OG "Kind 1" bedroom at=@a+1,@s+1 floor=FB-par
+ room @k2 OG "Kind 2" bedroom at=@o-1,@s+1 floor=FB-par
+ room @bad OG "Bad" bath at=@w+1,@n-1 floor=FB-fli tile=2
+ room _ OG "Flur" hall at=@o-1,@m+1 floor=FB-par
"""

BATCH_DB = """\
+ slab _ DB DE-20
+ wall _ DB AW-365 x=W+ y=S..N lb top=@roof
+ wall _ DB AW-365 x=E- y=S..N lb top=@roof
+ roof @roof DB DA-25 gable ridge=x pitch=25 knee=0.2 eave=0.5 verge=0.3
+ room _ DB "Spitzboden" attic at=W+1.365,S+4 floor=FB-db
"""


def _areas(p: Project, want: dict[str, float]) -> list[str]:
    d, rep = report(p.load())
    out = [f"{i.code} {i.el}" for i in rep.errors()]
    for k, v in want.items():
        r = d.arch.rooms.get(k)
        if r is None:
            out.append(f"{k} missing")
        elif round(r.area_fin, 2) != v:
            out.append(f"{k} fin {r.area_fin:.2f}, expected {v}")
    return out


def check_eg(p: Project) -> list[str]:
    return _areas(p, {"r1": 15.66, "r2": 27.93, "r3": 6.65, "r4": 4.04, "r5": 17.45})


def check_house(p: Project) -> list[str]:
    out = _areas(p, {"r6": 17.83, "r7": 12.79, "r8": 11.67, "r9": 8.14, "r10": 20.43})
    d, _ = report(p.load())
    rf = d.arch.roofs.get("rf1")
    if rf is None or round(rf.ridge_z, 2) != 8.10 or round(rf.eaves_z, 2) != 6.12:
        out.append("rf1: ridge +8.10 and eaves +6.12 expected")
    return out


def check_moved(p: Project) -> list[str]:
    # HWR 0.25 wider: (2.23 + 0.25) x 2.98; WC follows and keeps its width; Diele loses 0.25
    return _areas(p, {"r3": round(2.48 * 2.98, 2), "r4": 4.04, "r5": round(5.605 * 2.98, 2)})


def check_request(p: Project) -> list[str]:
    q = p.load().get("q7")
    if q is None:
        return ["q7 missing"]
    return [] if getattr(q, "done", None) is not None else ["q7 not done"]


def check_reverted(p: Project) -> list[str]:
    d1 = p.load().get("d1")
    if d1 is None:
        return ["d1 missing"]
    return [] if "1.135x2.26" in d1.line() else [f"d1 is {d1.line()}"]


def check_wofl(p: Project) -> list[str]:
    path = p.out / "wofl.json"
    if not path.exists():
        return ["out/wofl.json missing"]
    total = json.loads(path.read_text())["data"]["total"]
    return [] if round(total, 2) == 134.89 else [f"Wohnfläche {total}"]


def check_nothing(p: Project) -> list[str]:
    return []


TASKS: list[Task] = [
    Task(
        "eg-shell",
        "Start the project EFH Müller (Hessen, PLZ 64283, terrain -0.30) with EG, OG and a cold"
        " Spitzboden, the wall, slab, floor, roof, window and door types, and build the EG:"
        " 36.5 cm Ziegel outside on a 10.49 x 8.49 outline, a 24 cm bearing wall 4.51 clear from"
        " the south wall, HWR 2.26 and WC 1.385 wide on the north side, Diele with a straight"
        " stair, open kitchen and living room, doors and windows.",
        [
            apply("arch-agent", "Projekt, Geschosse, Achsen, Typen", BATCH1),
            apply("arch-agent", "EG Rohbau", BATCH_EG),
            Step(["check"]),
            Step(["show", "EG"]),
        ],
        check_eg,
    ),
    Task(
        "og-roof",
        "Build the OG (bedrooms, children, bath, hall) on the EG walls, then the Spitzboden"
        " with a 25° Satteldach, ridge along x, kn 0.20, overhangs 0.50 and 0.30.",
        [
            apply("arch-agent", "OG", BATCH_OG),
            apply("arch-agent", "Spitzboden und Dach", BATCH_DB),
            Step(["check"]),
            Step(["get", "rf1"]),
        ],
        check_house,
        setup="eg-shell",
    ),
    Task(
        "move-wall",
        "The Bauherr wants the HWR 25 cm wider. Change it and report the new room areas.",
        [
            Step(["get", "w6"]),
            apply("arch-agent", "HWR 25 cm breiter", "~ w6 x=w4+2.51\n"),
            Step(["show", "EG"]),
        ],
        check_moved,
        setup="house",
    ),
    Task(
        "request",
        "Electrical needs a 10 x 5 cm chase in w7 for the riser. Ask architecture; architecture"
        " accepts and closes the request.",
        [
            apply(
                "elec-agent",
                "Schlitz anfragen",
                '+ req _ elec w7 "Schlitz 10x5 cm für Steigleitung"\n',
            ),
            Step(["check", "arch"]),
            apply("arch-agent", "Schlitz eingeplant", "~ q7 done\n"),
        ],
        check_request,
        setup="house",
    ),
    Task(
        "revert",
        "Widen the front door to 1.51, then undo it because the Bauherr changed his mind.",
        [
            apply("arch-agent", "Haustür 1,51 breit", "~ d1 1.51x2.26\n"),
            Step(["log", "2"]),
            Step(["revert", "2", "--by", "arch-agent", "-m", "Bauherr: doch die alte Haustür"]),
        ],
        check_reverted,
        setup="house",
    ),
    Task(
        "wohnflaeche",
        "Compute the Wohnfläche of the house per WoFlV.",
        [Step(["calc", "wofl"])],
        check_wofl,
        setup="house",
    ),
    Task(
        "query",
        "Which OG walls are exterior and load-bearing? What is the Wohnen/Essen room like?"
        " Which doors open off the OG hall?",
        [
            Step(["find", "wall", "ext", "lb", "level=OG", "--ids"]),
            Step(["get", "r2"]),
            Step(["find", "door", "room=r10", "--ids"]),
        ],
        check_nothing,
        setup="house",
    ),
]

HELP = [["help"], ["help", "start"], ["help", "ops"], ["help", "positions"], ["help", "arch"]]
"""What an agent reads once before its first task."""


def prepare(task: Task, root: Path, run_steps: Callable[[Path, list[Step]], object]) -> None:
    """Set up a task's starting state in root (an initialised project)."""
    if task.setup == "house":
        for name in ("project.uea", "arch.uea", "issues.uea"):
            shutil.copy(PROTOTYPE / name, root / name)
    elif task.setup is not None:
        before = next(t for t in TASKS if t.id == task.setup)
        prepare(before, root, run_steps)
        run_steps(root, before.steps)

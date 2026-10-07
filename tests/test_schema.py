import pytest

from tests.conftest import model_from
from uea.core.model import element_from_raw
from uea.core.syntax import LineError, parse_line
from uea.packs import default_registry


def el(text: str):  # type: ignore[no-untyped-def]
    raw = parse_line(text)
    assert raw is not None
    return element_from_raw(default_registry(), raw)


@pytest.mark.parametrize(
    "line",
    [
        "level EG z=0 fb=0.15 head=2.26",
        "grid W x=0",
        'type AW-365 wall "Ziegel" layers=putz:0.015,*ziegel:0.365,putz:0.02',
        "type FE-3S win uw=0.9 default",
        "wall w1 EG AW-365 y=S+ x=W..E lb",
        "wall w4 EG AW-365 x=W+ y=w1..w3 lb",
        "wall w8 OG AW-365 on=w1 lb existing",
        "door d1 w2 1.135x2.26 y=w5+0.385 into=r5 din=l typ=TH-1",
        "win f2 w4 1.26x1.135 y=S+1.76",
        "niche ni1 w5.n 0.6x0.75 x=w7+0.4 sill=0.3 d=0.11",
        "void v1 sl2 over=st1",
        "roof rf1 DB DA-25 gable ridge=x pitch=25 kn=0.2 eave=0.5 verge=0.3",
        "stair st1 EG OG x=w2-1.125 y=w3- up=w w=1 n=16 tread=0.26",
        'room r1 EG kitchen "Küche" at=w4+1,w1+1 floor=FB-fli',
        'req q1 heat w5 "Nische" done=13',
        'waive wv1 W-ELEC-010 r5 "Wunsch Bauherr" by=elektroplaner',
    ],
)
def test_canonical_round_trip(line: str) -> None:
    assert el(line).line() == line


def test_wall_writes_position_before_span() -> None:
    assert el("wall w1 EG AW x=W..E y=S+").line() == "wall w1 EG AW y=S+ x=W..E"


def test_label_goes_after_positionals() -> None:
    assert (
        el('room r1 EG "Küche" kitchen at=w4+1,w1+1').line()
        == 'room r1 EG kitchen "Küche" at=w4+1,w1+1'
    )


@pytest.mark.parametrize(
    ("line", "msg"),
    [
        ("wall w1 EG AW y=S+ x=W..E tpye=x", "unknown field 'tpye'"),
        ("wall w1 EG AW y=S+ x=W..E lb heavy", "unknown flag 'heavy'"),
        ("wall w1 EG", "missing <type>"),
        ("wall w1 EG AW level=EG", "level is positional"),
        ("wall d1 EG AW y=S+ x=W..E", "ids of this kind are w<number>"),
        ("level E-G z=0", "no -"),
        ("level w1 z=0", "looks like an element id"),
        ("wall w1 EG AW y=S+ x=W+", "a span on the other"),
        ("grid W x=0 y=1", "exactly one of x= or y="),
        ("type X wall layers=a:0.1", "core layer"),
        ("type X cable", "unknown category"),
        ("roof rf1 DB T gable pitch=30", "needs ridge"),
        ("niche ni1 w5 0.6x0.75 x=W+1 d=0.1", "host needs a face"),
        ("door d1 w2 1x2", "x= or y="),
        ("req q1 heat w5", "needs its text"),
        ('waive wv1 X-1 r5 "a"', "not an issue code"),
        ("wall w1 EG AW y=S+ x=W..E existing demolish", "given twice"),
        ("foo f1", "unknown kind 'foo'"),
    ],
)
def test_strict_errors(line: str, msg: str) -> None:
    with pytest.raises(LineError, match=msg):
        el(line)


def test_status_flag() -> None:
    w = el("wall w1 EG AW y=S+ x=W..E demolish")
    assert w.model_dump()["status"] == "demolish"
    assert w.line().endswith(" demolish")


def test_canonical_order_in_file() -> None:
    m = model_from(
        """\
level OG z=3
level EG z=0
grid N y=8
grid W x=0
grid E x=10
type B wall layers=*a:0.1
type A wall layers=*a:0.1
wall w10 EG A y=N- x=W..E
wall w2 EG A y=N- x=W..E
"""
    )
    assert m.pack_text("project").splitlines() == [
        "level EG z=0",
        "level OG z=3",
        "grid W x=0",
        "grid E x=10",
        "grid N y=8",
    ]
    assert [line.split()[1] for line in m.pack_text("arch").splitlines()] == ["A", "B", "w2", "w10"]

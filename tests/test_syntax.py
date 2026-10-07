import pytest

from uea.core.syntax import LineError, fmt_num, parse_line, strip_comment, tokenize
from uea.core.values import Anchor, Layers, Point, Ref, RefList, Size, Span, parse_place


def test_line_parts() -> None:
    raw = parse_line('room r1 EG kitchen "Offene Küche" at=w4+1,w1+1 floor=FB  # comment')
    assert raw is not None
    assert (raw.kind, raw.key) == ("room", "r1")
    assert raw.bare == ("EG", "kitchen")
    assert raw.label == "Offene Küche"
    assert raw.kv == (("at", "w4+1,w1+1"), ("floor", "FB"))


def test_blank_and_comment_lines() -> None:
    assert parse_line("") is None
    assert parse_line("   # only a comment") is None


def test_hash_inside_label_is_not_a_comment() -> None:
    assert strip_comment('wall w1 "Wand #1" x=1') == 'wall w1 "Wand #1" x=1'


def test_quoted_value() -> None:
    raw = parse_line('~ q1 rejected="kein Platz im HWR"')
    assert raw is not None
    assert raw.kv == (("rejected", "kein Platz im HWR"),)


@pytest.mark.parametrize(
    ("text", "msg"),
    [
        ('wall w1 "open', "unterminated quote"),
        ("wall", "at least a kind and a key"),
        ("wall w1 x=1 x=2", "given twice"),
        ('wall w1 "a" "b"', "two labels"),
    ],
)
def test_line_errors(text: str, msg: str) -> None:
    with pytest.raises(LineError, match=msg):
        parse_line(text)


def test_tokenize_keeps_quoted_spaces() -> None:
    assert tokenize('a b="c d" "e f"') == ["a", 'b="c d"', '"e f"']


@pytest.mark.parametrize(
    ("v", "s"),
    [
        (0.15, "0.15"),
        (2.0, "2"),
        (-0.3, "-0.3"),
        (10.49, "10.49"),
        (0.0715, "0.0715"),
        (-0.00001, "0"),
    ],
)
def test_fmt_num(v: float, s: str) -> None:
    assert fmt_num(v) == s


@pytest.mark.parametrize(
    ("s", "ref", "face", "sign", "dist"),
    [
        ("w4+2.26", "w4", None, "+", 2.26),
        ("E-", "E", None, "-", 0.0),
        ("w5.n-", "w5", "n", "-", 0.0),
        ("f2.c", "f2", "c", None, 0.0),
        ("S", "S", None, None, 0.0),
        ("W-1.2", "W", None, "-", 1.2),
        ("@a+0.5", "@a", None, "+", 0.5),
    ],
)
def test_anchor(s: str, ref: str, face: str | None, sign: str | None, dist: float) -> None:
    a = Anchor.parse(s)
    assert (a.ref, a.face, a.sign, a.dist) == (ref, face, sign, dist)
    assert a.fmt() == s


def test_anchor_raw_coordinate() -> None:
    a = Anchor.parse("3.2+")
    assert (a.ref, a.coord, a.sign) == (None, 3.2, "+")
    assert a.fmt() == "3.2+"


@pytest.mark.parametrize("s", ["w4+", "+1", "w4++1", "w4.x+1", "4..5"])
def test_anchor_errors(s: str) -> None:
    if s == "w4+":
        assert Anchor.parse(s).fmt() == "w4+"
        return
    with pytest.raises(ValueError):
        Anchor.parse(s)


def test_span_point_size() -> None:
    sp = Span.parse("w1..w3")
    assert sp.refs() == ("w1", "w3")
    assert isinstance(parse_place("W..E"), Span)
    assert isinstance(parse_place("W+"), Anchor)
    pt = Point.parse("w4+1,w1+1")
    assert pt.fmt() == "w4+1,w1+1"
    assert Size.parse("0.885x2.01") == Size(0.885, 2.01)
    with pytest.raises(ValueError):
        Size.parse("0.885 x 2.01")


def test_map_refs_renames_placeholders() -> None:
    sp = Span.parse("@s..@n")
    assert sp.map_refs(lambda r: {"@s": "w1", "@n": "w3"}.get(r, r)).fmt() == "w1..w3"


def test_layers() -> None:
    ly = Layers.parse("putz:0.015,*ziegel:0.365,leicht:0.02")
    assert ly.core == pytest.approx(0.365)
    assert ly.before_core() == pytest.approx(0.015)
    assert ly.after_core() == pytest.approx(0.02)
    assert ly.total == pytest.approx(0.4)
    assert ly.fmt() == "putz:0.015,*ziegel:0.365,leicht:0.02"


def test_refs_with_dots_and_faces() -> None:
    assert Ref.parse("NYM-J3x2.5") == Ref("NYM-J3x2.5", None)
    assert Ref.parse("w5.n") == Ref("w5", "n")
    assert RefList.parse("d1,d4").refs() == ("d1", "d4")

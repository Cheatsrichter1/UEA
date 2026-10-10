"""From a read IFC to a batch of operations (decision 0029).

The IFC is geometry and properties; UEA wants intent. Walls become axes with a type, openings
become positions on their wall, slabs become one slab per storey (UEA derives the outline from the
walls), spaces become seed points. What UEA derives itself, the importer asks UEA for instead of
repeating the rules: the outside of a wall and the height a wall reaches come from a scratch
derive of the first pass.

Re-import: every imported element is remembered by its IFC key, with a hash of the line it was
imported as. A later import updates elements that nobody has edited since, adds new ones, removes
those the IFC lost, and reports the rest.
"""

import hashlib
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import LineString, Point, Polygon

from uea.core.model import Model, element_from_raw, refs_of
from uea.core.ops import Applied
from uea.core.syntax import fmt_num, parse_line
from uea.derive import derive
from uea.importer.ifc import Layer, Opening, Slab, Source, Space, Storey, Vec, Wall
from uea.packs import default_registry

STRUCTURAL = (
    "beton",
    "concrete",
    "stahlbeton",
    "stb",
    "ziegel",
    "brick",
    "mauerwerk",
    "masonry",
    "kalksandstein",
    "porenbeton",
    "ytong",
    "holz",
    "timber",
    "clt",
    "stahl",
    "steel",
    "block",
)
"""Material names that mark the load-bearing layer of a build-up."""
USES: tuple[tuple[str, str], ...] = (
    ("wc", r"\bwc\b|toilet|abort"),
    ("kitchen", r"k(ü|ue)che|kitchen|kochen"),
    ("bath", r"\bbad|bath|dusche|shower"),
    ("laundry", r"wasch|laundry"),
    ("bedroom", r"schlaf|bedroom|kinderzimmer|child|gast(zimmer)?\b|guest"),
    ("dining", r"esszimmer|essen|dining"),
    ("living", r"wohn|living|stube|lounge"),
    ("office", r"b(ü|ue)ro|office|arbeit|study"),
    ("technical", r"technik|heiz|boiler|hausanschluss|technical|haustechnik"),
    ("utility", r"\bhwr\b|hauswirtschaft|utility"),
    ("storage", r"abstell|storage|lager|vorrat|\bstauraum"),
    ("garage", r"garage|carport"),
    ("cellar", r"keller|cellar|basement"),
    ("attic", r"dachraum|attic|spitzboden|\bdach\b"),
    ("hall", r"flur|diele|hall|corridor|eingang|entry|vorraum|windfang|treppe|stair"),
)
"""Room use by the words in a space's names, first match wins."""
SNAP = 0.0017
"""A wall this close to a grid direction (radians, 0.1°) becomes an ordinary h or v wall."""
LEVEL_REACH = 1.0
"""A slab belongs to the storey whose FFL is at most this far above its top."""
HEIGHT_TOL = 0.05
"""A wall top this close to the height UEA derives needs no h=."""
GAP = 0.03
"""A wall end this close to the core of another wall is moved to touch it, so UEA joins them."""
JOIN = 0.002
"""UEA's join tolerance: a wall end this close to a core already touches it."""
SEP_MIN = 0.4
"""Spaces that share a boundary at least this long, with no wall on it, get a separator."""
SEP_REACH = 0.05
MIN_OPENING = 0.05
MIN_ROOM = 0.5


def slug(text: str, limit: int = 20) -> str:
    """ASCII letters, digits and hyphens: the form a name takes in the model."""
    s = text.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:limit].strip("-")


def line_hash(line: str) -> str:
    return hashlib.sha1(line.encode("utf-8")).hexdigest()[:10]


def room_use(hint: str) -> str:
    low = hint.lower()
    for use, pattern in USES:
        if re.search(pattern, low):
            return use
    return "other"


@dataclass(frozen=True)
class Known:
    """An element of an earlier import: its id and the hash of the line it was imported as."""

    id: str
    hash: str


@dataclass
class Item:
    key: str
    kind: str
    """Element kind: level, type, wall, door, win, slab, room."""
    what: str
    """For the report: what the item is called."""
    tail: str
    """The line after kind and id. `\\0` stands for the id of the host wall."""
    name: str | None = None
    """For named kinds (level, type): the chosen name."""
    category: str | None = None
    """For types: wall, slab, floor, door, win."""
    host: str | None = None
    """For openings: the key of the wall."""
    op: str = ""
    """What the plan does: new, update, keep (edited since), deleted (removed since), skip."""
    id: str | None = None


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list[Item])
    ops: list[str] = field(default_factory=list[str])
    gone: list[str] = field(default_factory=list[str])
    """Keys of earlier imports that are no longer in the file and are removed."""
    kept: list[str] = field(default_factory=list[str])
    notes: list[str] = field(default_factory=list[str])
    skipped: Counter[str] = field(default_factory=Counter[str])
    placeholders: dict[str, Item] = field(default_factory=dict[str, Item])
    known: dict[str, "Known"] = field(default_factory=dict[str, "Known"])
    src: Source | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.ops)

    def counts(self, applied: Applied | None = None) -> dict[str, int]:
        """Elements added or changed by kind; with `applied`, only those that really changed."""
        c: Counter[str] = Counter()
        mapped = {p: i for p, i in applied.added if p is not None} if applied is not None else {}
        for it in self.items:
            if it.op == "new" or (
                it.op == "update"
                and (applied is None or mapped.get(it.id or "", it.id) in applied.changed)
            ):
                c[it.kind] += 1
        return dict(c)

    def record(self, applied: Applied) -> dict[str, Any]:
        """What the history keeps of this import: key to id and the hash of the line, for what
        this import added or changed. Earlier records stand for the rest."""
        assert self.src is not None
        mapped = {p: i for p, i in applied.added if p is not None}
        ids: dict[str, str] = {}
        lines: dict[str, str] = {}
        for it in self.items:
            if it.op not in ("new", "update") or it.id is None:
                continue
            ident = mapped.get(it.id, it.id)
            if ident not in applied.model:
                continue
            digest = line_hash(applied.model[ident].line())
            if self.known.get(it.key) == Known(ident, digest):
                continue
            ids[it.key] = ident
            lines[ident] = digest
        return {
            "file": self.src.file,
            "sha": self.src.sha[:16],
            "app": self.src.app,
            "ids": ids,
            "lines": lines,
            "gone": self.gone,
        }


# ---------- geometry helpers ----------


def _unit(v: Vec) -> Vec:
    s = math.hypot(*v)
    return (v[0] / s, v[1] / s) if s > 1e-9 else (1.0, 0.0)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _num(v: float) -> str:
    return fmt_num(round(v, 4))


def _pt(p: Vec) -> str:
    return f"{_num(p[0])},{_num(p[1])}"


def layers_text(layers: Sequence[Layer], core: int | None = None) -> str:
    """Layers as the model writes them: material:thickness, the core marked with a star."""
    return ",".join(
        f"{'*' if i == core else ''}{slug(lay.material, 16).lower() or 'layer'}:{_num(lay.t)}"
        for i, lay in enumerate(layers)
    )


def core_index(layers: tuple[Layer, ...]) -> int:
    """The load-bearing layer: the thickest with a structural material name, else the thickest."""
    structural = [
        i for i, lay in enumerate(layers) if any(w in lay.material.lower() for w in STRUCTURAL)
    ]
    pool = structural or list(range(len(layers)))
    return max(pool, key=lambda i: (round(layers[i].t, 4), -i))


@dataclass
class Sig:
    """One build-up as the file gives it: the key of its wall type and its layers."""

    key: str
    type_name: str | None
    layers: tuple[Layer, ...]
    core: int
    measured: bool
    """The layers do not add up to the footprint: one core layer of the measured thickness."""
    votes_out: int = 0
    votes_in: int = 0

    @property
    def total(self) -> float:
        return sum(lay.t for lay in self.layers)

    @property
    def core_t(self) -> float:
        return self.layers[self.core].t

    @property
    def symmetric(self) -> bool:
        return self.layers == self.layers[::-1]

    @property
    def rev(self) -> bool:
        """UEA lists a wall type inside to outside: the file's order is turned over when its first
        layer is on the outside."""
        return not self.symmetric and self.votes_out > self.votes_in

    def shift(self) -> float:
        """How far the core centre lies from the footprint centre, toward the first layer."""
        before = sum(lay.t for lay in self.layers[: self.core])
        after = sum(lay.t for lay in self.layers[self.core + 1 :])
        return (after - before) / 2

    def core_text(self) -> str:
        """The layers in the file's order, for a type that only has to have the right core."""
        return layers_text(self.layers, self.core)

    def text(self) -> str:
        items = list(self.layers)
        core = self.core
        if self.rev:
            items.reverse()
            core = len(items) - 1 - core
        return layers_text(items, core)


@dataclass
class Lv:
    storey: Storey
    name: str
    z: float
    """FFL relative to the ground storey."""
    off: float = 0.0
    """Elevation of the ground storey in the file: absolute height = off + UEA height."""
    fb: float = 0.0
    head: float | None = None

    @property
    def ssl(self) -> float:
        return self.z - self.fb


@dataclass
class WRec:
    w: Wall
    lv: Lv
    sig: Sig
    a: Vec
    b: Vec
    o: str
    n: Vec
    first: Vec | None
    tmp: str = ""
    flip: bool = False
    h: float | None = None


def frame(a: Vec, b: Vec) -> tuple[Vec, Vec, str]:
    """The ends of a wall, snapped to a grid direction if close, and its o and its hi direction."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if abs(dy) <= SNAP * length:
        y = (a[1] + b[1]) / 2
        return (a[0], y), (b[0], y), "h"
    if abs(dx) <= SNAP * length:
        x = (a[0] + b[0]) / 2
        return (x, a[1]), (x, b[1]), "v"
    return a, b, "d"


def _hi(a: Vec, b: Vec, o: str) -> Vec:
    if o == "h":
        return (0.0, 1.0)
    if o == "v":
        return (1.0, 0.0)
    u = _unit((b[0] - a[0], b[1] - a[1]))
    return (-u[1], u[0])


# ---------- the plan ----------


class Builder:
    def __init__(self, src: Source, model: Model, state: dict[str, Known]) -> None:
        self.src = src
        self.model = model
        self.state = state
        self.plan = Plan(src=src)
        self.taken: set[str] = set()
        self.levels: dict[str, Lv] = {}
        self.sigs: dict[str, Sig] = {}
        self.recs: list[WRec] = []
        self.by_guid: dict[str, WRec] = {}
        self.floor_of: dict[str, str] = {}
        """Level name: the floor type its rooms get."""
        self.slab_key: dict[str, str] = {}

    # --- names

    def name(self, key: str, base: str, *, keep_case: bool = False) -> str:
        known = self.state.get(key)
        if known is not None:
            self.taken.add(known.id)
            return known.id
        base = base if keep_case else base.upper()
        if not base or not base[0].isalpha():
            base = "T-" + base if base else "T"
        out, n = base, 2
        while out in self.model or out in self.taken:
            out = f"{base}-{n}"
            n += 1
        self.taken.add(out)
        return out

    def level_name(self, key: str, st: Storey, index: int, ground: int) -> str:
        known = self.state.get(key)
        if known is not None:
            self.taken.add(known.id)
            return known.id
        word = re.sub(r"[^A-Za-z0-9_]", "", st.name.translate(str.maketrans("äöüß", "aouS")))
        if 1 <= len(word) <= 6 and word[0].isalpha() and not re.fullmatch(r"[a-z]+\d+", word):
            base = word
        else:
            base = f"L{index - ground}" if index >= ground else f"B{ground - index}"
        out, n = base, 2
        while out in self.model or out in self.taken:
            out = f"{base}_{n}"
            n += 1
        self.taken.add(out)
        return out

    # --- levels

    def storey_at(self, z: float) -> Storey | None:
        """The storey a thing without a container belongs to, by its lowest height."""
        if not self.src.storeys:
            return None
        below = [s for s in self.src.storeys if s.z <= z + 0.5]
        return max(below, key=lambda s: s.z) if below else self.src.storeys[0]

    def wall_storey(self, w: Wall) -> Storey | None:
        for s in self.src.storeys:
            if s.guid == w.storey:
                return s
        return self.storey_at(w.z0)

    def slab_storey(self, s: Slab) -> Storey | None:
        above = [st for st in self.src.storeys if s.z1 - 0.05 <= st.z <= s.z1 + LEVEL_REACH]
        return min(above, key=lambda st: st.z) if above else None

    def space_storey(self, s: Space) -> Storey | None:
        for st in self.src.storeys:
            if st.guid == s.storey:
                return st
        return self.storey_at(s.z0)

    def make_levels(self) -> None:
        used = {id(self.wall_storey(w)): self.wall_storey(w) for w in self.src.walls}
        storeys = sorted((s for s in used.values() if s is not None), key=lambda s: s.z)
        if not storeys:
            return
        zero = [s for s in storeys if abs(s.z) < 0.01]
        ground = zero[0] if zero else storeys[0]
        self.plan.notes.append(
            f"ground storey {ground.name} (±0.00)"
            + ("" if zero else f", the lowest; its elevation in the file is {_num(ground.z)} m")
        )
        gi = storeys.index(ground)
        for i, s in enumerate(storeys):
            name = self.level_name(s.guid, s, i, gi)
            self.levels[s.guid] = Lv(s, name, round(s.z - ground.z, 4), ground.z)

    # --- types

    def wall_sig(self, w: Wall) -> Sig:
        measured = False
        layers = w.layers
        if not layers or abs(sum(lay.t for lay in layers) - w.t) > 0.01:
            material = w.material or (max(layers, key=lambda lay: lay.t).material if layers else "")
            if layers:
                self.plan.notes.append(
                    f"wall {w.name or w.guid}: its layers add up to"
                    f" {_num(sum(lay.t for lay in layers))} m, its footprint is {_num(w.t)} m;"
                    " the footprint counts"
                )
            layers = (Layer(material or "wall", round(w.t, 3)),)
            measured = True
        digest = hashlib.sha1(repr([(x.material, round(x.t, 4)) for x in layers]).encode())
        short = digest.hexdigest()[:8]
        if w.type_guid and not measured:
            key = f"type:{w.type_guid}"
            if key in self.sigs and self.sigs[key].layers != layers:
                key += ":" + short
        else:
            key = "layers:" + short
        if key not in self.sigs:
            self.sigs[key] = Sig(key, w.type_name, layers, core_index(layers), measured)
        return self.sigs[key]

    # --- walls

    def make_walls(self) -> None:
        for w in self.src.walls:
            st = self.wall_storey(w)
            lv = self.levels.get(st.guid) if st is not None else None
            if lv is None:
                self.plan.skipped["IfcWall (no storey)"] += 1
                continue
            sig = self.wall_sig(w)
            a, b, o = frame(w.a, w.b)
            n = _hi(a, b, o)
            first = w.first if w.first is not None and abs(_dot(w.first, n)) > 0.5 else None
            if first is not None and not sig.measured:
                k = sig.shift() * (1.0 if _dot(first, n) > 0 else -1.0)
                a = (a[0] + n[0] * k, a[1] + n[1] * k)
                b = (b[0] + n[0] * k, b[1] + n[1] * k)
            rec = WRec(
                w,
                lv,
                sig,
                (round(a[0], 4), round(a[1], 4)),
                (round(b[0], 4), round(b[1], 4)),
                o,
                n,
                first,
            )
            self.recs.append(rec)
            self.by_guid[w.guid] = rec
            if w.sloped:
                self.plan.notes.append(
                    f"wall {w.name or w.guid}: its top slopes (under a roof); set to its highest"
                    " point until the roof is modelled"
                )

    def close_gaps(self) -> None:
        """Walls whose end stops a few millimetres short of another wall's core reach it.

        UEA joins a wall end to the wall it touches (within 2 mm); exporters leave the finish
        layers or a rounding in between, and a gap of that size keeps the outline open.
        """
        cores: dict[str, list[tuple[WRec, Polygon]]] = {}
        for rec in self.recs:
            u = _unit((rec.b[0] - rec.a[0], rec.b[1] - rec.a[1]))
            n = (-u[1], u[0])
            h = rec.sig.core_t / 2
            box = Polygon(
                [
                    (rec.a[0] + n[0] * h, rec.a[1] + n[1] * h),
                    (rec.b[0] + n[0] * h, rec.b[1] + n[1] * h),
                    (rec.b[0] - n[0] * h, rec.b[1] - n[1] * h),
                    (rec.a[0] - n[0] * h, rec.a[1] - n[1] * h),
                ]
            )
            cores.setdefault(rec.lv.name, []).append((rec, box))
        for rec in self.recs:
            u = _unit((rec.b[0] - rec.a[0], rec.b[1] - rec.a[1]))
            for which, p, out in (("a", rec.a, (-u[0], -u[1])), ("b", rec.b, u)):
                reach = self._reach(rec, p, out, cores[rec.lv.name])
                if reach is None:
                    continue
                q = (
                    round(p[0] + out[0] * (reach + 0.0005), 4),
                    round(p[1] + out[1] * (reach + 0.0005), 4),
                )
                if which == "a":
                    rec.a = q
                else:
                    rec.b = q

    @staticmethod
    def _reach(rec: WRec, p: Vec, out: Vec, cores: list[tuple[WRec, Polygon]]) -> float | None:
        """How far a wall end must grow along `out` to touch a core that is a little ahead."""
        here = Point(p)
        ray = LineString([p, (p[0] + out[0] * GAP, p[1] + out[1] * GAP)])
        best: float | None = None
        for other, box in cores:
            if other is rec:
                continue
            x0, y0, x1, y1 = box.bounds
            if not (x0 - GAP <= p[0] <= x1 + GAP and y0 - GAP <= p[1] <= y1 + GAP):
                continue
            if box.distance(here) <= JOIN:
                return None
            hit = ray.intersection(box)
            if hit.is_empty:
                continue
            d = hit.distance(here)
            if best is None or d < best:
                best = d
        return best

    # --- scratch derive

    def scratch(self, slabs: dict[str, "SlabPick"]) -> None:
        """Let UEA derive the outside of each wall and the height it reaches."""
        reg = default_registry()
        m = Model(reg)
        names = {s.key: f"TS{i}" for i, s in enumerate(self.sigs.values())}
        lines = [f"level {lv.name} z={_num(lv.z)} fb={_num(lv.fb)}" for lv in self.levels.values()]
        lines += [f"type {names[s.key]} wall layers={s.core_text()}" for s in self.sigs.values()]
        for i, (lname, pick) in enumerate(slabs.items()):
            lines.append(f"type TL{i} slab layers={pick.layers_text()}")
            lines.append(f"slab sl{i + 1} {lname} TL{i}")
        for i, rec in enumerate(self.recs, 1):
            rec.tmp = f"w{i}"
            lines.append(
                f"wall w{i} {rec.lv.name} {names[rec.sig.key]} a={_pt(rec.a)} b={_pt(rec.b)}"
            )
        try:
            for line in lines:
                raw = parse_line(line)
                if raw is not None:
                    m.put(element_from_raw(reg, raw))
            d = derive(m)
        except Exception as e:
            self.plan.notes.append(
                f"could not derive the first pass ({e}); sides and heights not set"
            )
            return
        votes: list[tuple[WRec, Vec | None]] = []
        for rec in self.recs:
            g = d.arch.walls.get(rec.tmp)
            if g is None:
                continue
            ext = None
            if g.ext is not None:
                ext = g.n if g.ext == "hi" else (-g.n[0], -g.n[1])
            first = rec.first if rec.first is not None else ext
            if ext is not None and first is not None:
                if _dot(first, ext) > 0:
                    rec.sig.votes_out += 1
                else:
                    rec.sig.votes_in += 1
            votes.append((rec, ext))
        for rec, ext in votes:
            first = rec.first
            if first is None:
                continue
            uea_first = (-first[0], -first[1]) if rec.sig.rev else first
            inner0 = (-ext[0], -ext[1]) if ext is not None else (-rec.n[0], -rec.n[1])
            rec.flip = not rec.sig.symmetric and _dot(uea_first, inner0) < 0
        for rec in self.recs:
            g = d.arch.walls.get(rec.tmp)
            if g is None:
                continue
            top = rec.w.z1 - rec.lv.off
            reach = top - rec.lv.ssl
            if not g.top or rec.w.sloped or abs(g.top[0][1] - top) > HEIGHT_TOL:
                rec.h = reach


@dataclass
class SlabPick:
    slab: Slab
    layers: tuple[Layer, ...]
    """From the core down."""
    above: tuple[Layer, ...]
    """Above the core, top to bottom: the floor build-up."""
    ssl: float
    """Absolute height of the core's top."""

    def layers_text(self) -> str:
        return layers_text(self.layers, 0)


def _slab_pick(s: Slab) -> SlabPick:
    layers = s.layers
    if not layers:
        material = s.material or "slab"
        return SlabPick(s, (Layer(material, round(s.z1 - s.z0, 3)),), (), s.z1)
    total = sum(lay.t for lay in layers)
    if abs(total - (s.z1 - s.z0)) > 0.01:
        return SlabPick(
            s, (Layer(layers[core_index(layers)].material, round(s.z1 - s.z0, 3)),), (), s.z1
        )
    ci = core_index(layers)
    above = layers[:ci]
    return SlabPick(s, layers[ci:], above, s.z1 - sum(lay.t for lay in above))


def _guard(text: str) -> str:
    return text.replace('"', "'")


def plan(src: Source, model: Model, state: dict[str, Known]) -> Plan:
    b = Builder(src, model, state)
    p = b.plan
    p.known = state
    p.skipped.update(src.skipped)
    b.make_levels()
    if not b.levels:
        p.notes.append("no walls with a storey: nothing to import")
        return p
    b.make_walls()
    b.close_gaps()
    # slabs: the largest one of each storey
    picks: dict[str, SlabPick] = {}
    for s in src.slabs:
        st = b.slab_storey(s)
        lv = b.levels.get(st.guid) if st is not None else None
        if lv is None:
            p.skipped["IfcSlab (no storey with walls at its top)"] += 1
            continue
        cur = picks.get(lv.name)
        if cur is None or s.area > cur.slab.area:
            if cur is not None:
                p.skipped["IfcSlab (merged into the storey's largest)"] += 1
            picks[lv.name] = _slab_pick(s)
        else:
            p.skipped["IfcSlab (merged into the storey's largest)"] += 1
    by_name = {lv.name: lv for lv in b.levels.values()}
    for lname, pick in picks.items():
        lv = by_name[lname]
        lv.fb = (
            max(0.0, round(lv.storey.z - pick.ssl, 4)) if pick.ssl <= lv.storey.z + 0.01 else 0.0
        )
    # head heights: the most common window top above the FFL of each storey
    tops: dict[str, Counter[float]] = {}
    for op in src.openings:
        rec = b.by_guid.get(op.wall)
        if rec is not None and op.kind == "win":
            tops.setdefault(rec.lv.name, Counter())[
                round((op.z1 - rec.lv.storey.z) * 200) / 200
            ] += 1
    for lname, c in tops.items():
        by_name[lname].head = c.most_common(1)[0][0]
    b.scratch(picks)
    _items(b, picks, by_name)
    _emit(b)
    return p


def _items(b: Builder, picks: dict[str, SlabPick], by_name: dict[str, Lv]) -> None:
    p = b.plan
    items = p.items
    for lv in b.levels.values():
        tail = f"z={_num(lv.z)} fb={_num(lv.fb)}" + (f" head={_num(lv.head)}" if lv.head else "")
        label = f' "{_guard(lv.storey.name)}"' if lv.storey.name != lv.name else ""
        items.append(
            Item(
                lv.storey.guid,
                "level",
                lv.name,
                label.strip() + (" " if label else "") + tail,
                name=lv.name,
            )
        )
    wall_types: dict[str, str] = {}
    for s in b.sigs.values():
        base = slug(s.type_name or "") or f"W{round(s.total * 1000)}"
        name = b.name(s.key, base)
        wall_types[s.key] = name
        label = (
            f' "{_guard(s.type_name)}"' if s.type_name and slug(s.type_name).upper() != name else ""
        )
        items.append(
            Item(s.key, "type", name, f"wall{label} layers={s.text()}", name=name, category="wall")
        )
    slab_types: dict[str, str] = {}
    slab_keys: dict[str, str] = {}
    floor_types: dict[str, str] = {}
    floor_keys: dict[str, str] = {}
    for lname, pick in picks.items():
        base = (
            slug(pick.slab.type_name or "") or f"D{round(sum(lay.t for lay in pick.layers) * 1000)}"
        )
        digest = hashlib.sha1(f"{pick.slab.type_name}|{pick.layers_text()}".encode()).hexdigest()
        key = f"slab:{digest[:8]}"
        if key in slab_keys:
            slab_types[lname] = slab_keys[key]
        else:
            name = b.name(key, base)
            slab_keys[key] = slab_types[lname] = name
            items.append(
                Item(
                    key,
                    "type",
                    name,
                    f"slab layers={pick.layers_text()}",
                    name=name,
                    category="slab",
                )
            )
        if pick.above:
            text = layers_text(pick.above)
            fkey = "floor:" + hashlib.sha1(text.encode()).hexdigest()[:8]
            if fkey not in floor_keys:
                fname = b.name(fkey, "FB-" + slab_types[lname])
                floor_keys[fkey] = fname
                items.append(
                    Item(fkey, "type", fname, f"floor layers={text}", name=fname, category="floor")
                )
            floor_types[lname] = floor_keys[fkey]
    door_types: dict[str, str] = {}
    for op in b.src.openings:
        if op.type_guid is None or op.wall not in b.by_guid:
            continue
        key = f"type:{op.type_guid}"
        if key in door_types:
            continue
        name = b.name(key, slug(op.type_name or "") or ("TD" if op.kind == "door" else "TW"))
        door_types[key] = name
        u = f" {'ud' if op.kind == 'door' else 'uw'}={_num(op.u)}" if op.u else ""
        items.append(Item(key, "type", name, f"{op.kind}{u}", name=name, category=op.kind))
    for rec in b.recs:
        flags = (" lb" if rec.w.lb else "") + (" flip" if rec.flip else "")
        flags += "" if rec.w.status == "new" else f" {rec.w.status}"
        h = f" h={_num(rec.h)}" if rec.h is not None else ""
        tail = f"{rec.lv.name} {wall_types[rec.sig.key]} a={_pt(rec.a)} b={_pt(rec.b)}{h}{flags}"
        items.append(Item(rec.w.guid, "wall", rec.w.name or rec.w.guid, tail))
    for lname, pick in picks.items():
        guid = pick.slab.guid
        items.append(Item(guid, "slab", f"slab of {lname}", f"{lname} {slab_types[lname]}"))
        b.slab_key[lname] = guid
    for op in b.src.openings:
        item = _opening(b, op, door_types)
        if item is not None:
            items.append(item)
    items.extend(_seps(b))
    for sp in b.src.spaces:
        item = _room(b, sp, floor_types)
        if item is not None:
            items.append(item)


def _opening(b: Builder, op: Opening, types: dict[str, str]) -> Item | None:
    rec = b.by_guid.get(op.wall)
    if rec is None:
        b.plan.skipped[
            f"{'IfcDoor' if op.kind == 'door' else 'IfcWindow'} (its wall was not imported)"
        ] += 1
        return None
    ffl = rec.lv.storey.z
    pts = list(op.fp.exterior.coords)
    if rec.o == "h":
        lo, hi, axis = min(x for x, _ in pts), max(x for x, _ in pts), "x"
    elif rec.o == "v":
        lo, hi, axis = min(y for _, y in pts), max(y for _, y in pts), "y"
    else:
        u = _unit((rec.b[0] - rec.a[0], rec.b[1] - rec.a[1]))
        ss = [(x - rec.a[0]) * u[0] + (y - rec.a[1]) * u[1] for x, y in pts]
        lo, hi, axis = min(ss), max(ss), "s"
    width = hi - lo
    z0 = max(op.z0, ffl) if op.kind == "door" else op.z0
    height = op.z1 - z0
    if width < MIN_OPENING or height < MIN_OPENING:
        b.plan.skipped["opening smaller than 5 cm"] += 1
        return None
    sill = z0 - ffl
    extra = ""
    if op.kind == "door":
        if sill > 0.02:
            extra += f" sill={_num(sill)}"
    else:
        head = rec.lv.head
        if head is None or abs(sill - (head - height)) > 0.01:
            extra += f" sill={_num(max(sill, 0.0))}"
    if op.type_guid is not None and f"type:{op.type_guid}" in types:
        extra += f" type={types[f'type:{op.type_guid}']}"
    if op.status != "new":
        extra += f" {op.status}"
    kind = op.kind
    tail = f"\0 {_num(width)}x{_num(height)} {axis}={_num(lo)}+{extra}"
    return Item(op.guid, kind, f"{kind} in {rec.w.name or rec.w.guid}", tail, host=op.wall)


def _room(b: Builder, sp: Space, floors: dict[str, str]) -> Item | None:
    st = b.space_storey(sp)
    lv = b.levels.get(st.guid) if st is not None else None
    if lv is None:
        b.plan.skipped["IfcSpace (no storey with walls)"] += 1
        return None
    if sp.area < MIN_ROOM:
        b.plan.skipped["IfcSpace (smaller than 0.5 m²)"] += 1
        return None
    label = sp.long_name or sp.name
    tail = f"{lv.name} {room_use(sp.hint)}"
    if label:
        tail += f' "{_guard(label)}"'
    tail += f" at={_pt(sp.at)}"
    if lv.name in floors:
        tail += f" floor={floors[lv.name]}"
    return Item(sp.guid, "room", f"room {label or sp.guid}", tail)


def _seps(b: Builder) -> list[Item]:
    """Open-plan rooms: where two spaces meet with no wall between them, UEA needs a separator."""
    out: list[Item] = []
    by_level: dict[str, list[Space]] = {}
    for sp in b.src.spaces:
        st = b.space_storey(sp)
        lv = b.levels.get(st.guid) if st is not None else None
        if lv is not None and sp.area >= MIN_ROOM:
            by_level.setdefault(lv.name, []).append(sp)
    for lname, spaces in by_level.items():
        ordered = sorted(spaces, key=lambda s: s.guid)
        for i, one in enumerate(ordered):
            for two in ordered[i + 1 :]:
                sliver = one.fp.buffer(0.005).intersection(two.fp.buffer(0.005))
                parts: list[Any] = list(getattr(sliver, "geoms", [sliver]))
                for k, part in enumerate(parts):
                    item = _sep(lname, one, two, k, part)
                    if item is not None:
                        out.append(item)
    return out


def _sep(level: str, one: Space, two: Space, k: int, part: Any) -> Item | None:
    if part.is_empty or part.geom_type != "Polygon":
        return None
    x0, y0, x1, y1 = part.bounds
    w, h = x1 - x0, y1 - y0
    if min(w, h) > 0.03 or max(w, h) < SEP_MIN:
        return None
    if w >= h:
        pos, lo, hi = (y0 + y1) / 2, x0 - SEP_REACH, x1 + SEP_REACH
        tail = f"{level} y={_num(pos)} x={_num(lo)}..{_num(hi)}"
    else:
        pos, lo, hi = (x0 + x1) / 2, y0 - SEP_REACH, y1 + SEP_REACH
        tail = f"{level} x={_num(pos)} y={_num(lo)}..{_num(hi)}"
    return Item(f"sep:{one.guid}:{two.guid}:{k}", "sep", f"separator {one.name}/{two.name}", tail)


# ---------- emitting ----------

NAMED = ("level", "type")


def _emit(b: Builder) -> None:
    p = b.plan
    model, state = b.model, b.state
    refs: dict[str, str] = {}
    seq = 0
    seen = {it.key for it in p.items}
    for it in p.items:
        known = state.get(it.key)
        tail = it.tail
        if it.host is not None:
            host = refs.get(it.host)
            if host is None:
                it.op = "skip"
                continue
            tail = tail.replace("\0", host)
        if known is not None:
            cur = model.get(known.id)
            if cur is None:
                it.op = "deleted"
                p.kept.append(f"{known.id} ({it.what}): removed in UEA since the import")
                continue
            refs[it.key] = known.id
            it.id = known.id
            if line_hash(cur.line()) != known.hash:
                it.op = "keep"
                p.kept.append(f"{known.id} ({it.what}): edited in UEA since the import")
                continue
            it.op = "update"
            p.ops.append(f"> {it.kind} {known.id} {tail}")
        elif it.kind in NAMED:
            assert it.name is not None
            it.op = "new"
            it.id = it.name
            refs[it.key] = it.name
            head = f"{it.kind} {it.name}"
            p.ops.append(f"+ {head} {tail}")
        else:
            seq += 1
            ph = f"@p{seq}"
            it.op = "new"
            it.id = ph
            refs[it.key] = ph
            p.placeholders[ph] = it
            p.ops.append(f"+ {it.kind} {ph} {tail}")
    # what an earlier import brought and the file no longer has
    removing: set[str] = set()
    for key, known in state.items():
        if key in seen:
            continue
        el = model.get(known.id)
        if el is None or el.prefix is None:
            continue
        if line_hash(el.line()) != known.hash:
            p.kept.append(f"{known.id}: gone from the IFC, but edited in UEA since the import")
            continue
        removing.add(known.id)
    for el in model:
        if el.id in removing:
            continue
        for _, ref in refs_of(el):
            if ref in removing:
                removing.discard(ref)
                p.kept.append(f"{ref}: gone from the IFC, but {el.id} still refers to it")
    order = sorted(
        (k for k, v in state.items() if v.id in removing),
        key=lambda k: state[k].id.startswith("w"),
    )
    for key in order:
        p.ops.append(f"- {state[key].id}")
        p.gone.append(key)

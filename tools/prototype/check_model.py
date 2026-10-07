"""Prototype review tool: checks a hand-written UEA project and draws its floor plans.

Not UEA code. Usage: python3 check_model.py MODEL_DIR [OUT_DIR]
Prints problems and resolved geometry; with OUT_DIR it also writes grundriss-EG.svg and grundriss-OG.svg.
"""
import json, math, re, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OUTDIR = Path(sys.argv[2]) if len(sys.argv) > 2 else None
FILES = ["project", "arch", "light", "elec", "heat", "plumb", "vent", "issues"]
NAMED = {"project", "level", "grid", "type"}
POS = {  # positional field names per kind (for checks and the JSON comparison)
    "project": [], "level": [], "grid": [], "type": ["category"],
    "wall": ["level", "type"], "door": ["host", "size"], "win": ["host", "size"],
    "niche": ["host", "size"], "slab": ["level", "type"], "void": ["slab"],
    "roof": ["level", "type", "shape"], "stair": ["from", "to"], "sep": ["level"],
    "room": ["level", "use"], "lum": ["host"], "board": ["host"],
    "rcd": ["board", "rating", "rcdtype"], "circ": ["parent", "cable", "protection"],
    "sock": ["host", "circuit"], "conn": ["host", "circuit"], "switch": ["host", "circuit"],
    "data": ["host", "board"], "smoke": ["room"], "feed": ["target", "circuit"],
    "gen": ["level"], "tank": ["room"], "man": ["niche"], "ufh": ["room", "manifold"],
    "san": ["host", "kind"], "fan": ["host"], "req": ["from", "targets"], "waive": ["code", "target"], "illum": ["room"],
}
PREFIX = {}
TOK = re.compile(r'"[^"]*"|\S+')
ID = re.compile(r"^([a-z]+)(\d+)$")
problems = []

def parse_line(line):
    toks = TOK.findall(line)
    kind, key = toks[0], toks[1]
    el = {"kind": kind, "key": key, "pos": [], "kv": {}, "flags": [], "label": None}
    for t in toks[2:]:
        if t.startswith('"'):
            el["label"] = t[1:-1]
        elif "=" in t:
            k, v = t.split("=", 1)
            el["kv"][k] = v
        elif len(el["pos"]) < len(POS[kind]):
            el["pos"].append(t)
        else:
            el["flags"].append(t)
    return el

els, order, sizes = {}, [], {}
for f in FILES:
    text = (ROOT / f"{f}.uea").read_text(encoding="utf-8")
    sizes[f] = (len(text.splitlines()), len(text))
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        el = parse_line(line)
        el["file"] = f
        if el["key"] in els:
            problems.append(f"duplicate id {el['key']}")
        els[el["key"]] = el
        order.append(el["key"])
        if el["kind"] not in NAMED:
            m = ID.match(el["key"])
            if not m:
                problems.append(f"bad id {el['key']}")
                continue
            p = m.group(1)
            if PREFIX.setdefault(el["kind"], p) != p:
                problems.append(f"kind {el['kind']} has prefixes {PREFIX[el['kind']]} and {p}")

# every kind has its own prefix
seen = {}
for k, p in PREFIX.items():
    if p in seen:
        problems.append(f"prefix {p} used by {seen[p]} and {k}")
    seen[p] = k

# reference check: names in name fields, anchors in position expressions
NAMEFIELDS = {"level", "type", "host", "slab", "to", "room", "board", "parent", "circuit",
              "target", "niche", "manifold", "targets"} - {"from"}
EXPRKEYS = {"x", "y", "at", "on", "over", "into", "ctl", "pair", "top", "floor"}
ANCH = re.compile(r"^([A-Za-z][A-Za-z0-9]*)(?:\.[nsewc])?(?:[+-][\d.]*)?$")
for k in order:
    el = els[k]
    refs = []
    if el["kind"] == "grid":
        continue
    for name, v in zip(POS[el["kind"]], el["pos"]):
        if name in NAMEFIELDS:
            refs += [x.split(".")[0] for x in v.split(",")]
    for kk, v in el["kv"].items():
        if kk in {"floor", "src"} or kk == "typ" and el["kind"] in {"door", "win", "lum"}:
            refs.append(v)
        elif kk in EXPRKEYS:
            for part in re.split(r",|\.\.|\+(?=[a-z])", v):
                m = ANCH.match(part)
                if not m:
                    problems.append(f"{k}: cannot parse '{part}' in {kk}={v}")
                else:
                    refs.append(m.group(1))
    for r in refs:
        if r not in els:
            problems.append(f"{k}: unknown reference {r}")

# ---------- geometry ----------
grids = {k: (list(e["kv"])[0], float(list(e["kv"].values())[0])) for k, e in els.items() if e["kind"] == "grid"}
levels = {k: (float(e["kv"]["z"]), float(e["kv"]["fb"])) for k, e in els.items() if e["kind"] == "level"}

def layers(tname):
    out = []
    for part in els[tname]["kv"]["layers"].split(","):
        m, t = part.split(":")
        out.append((m.lstrip("*"), float(t), m.startswith("*")))
    return out

def core(tname):
    return sum(t for _, t, c in layers(tname) if c)

walls, openings, devices = {}, {}, {}
EXPR = re.compile(r"^(?P<ref>[A-Za-z]+\d*)(?:\.(?P<face>[nsewc]))?(?P<sign>[+-])?(?P<d>[\d.]+)?$")

class Pending(Exception):
    pass

def anchor(ref, face, sign, axis):
    if ref in grids:
        gaxis, val = grids[ref]
        assert gaxis == axis, (ref, axis)
        return val
    if ref in walls:
        w = walls[ref]
        perp = "y" if w["o"] == "h" else "x"
        if perp != axis:
            raise ValueError(f"{ref} is not parallel to {axis}-position")
        lo, hi = w["pos"]
        if face:
            return {"n": hi, "e": hi, "s": lo, "w": lo}[face]
        return hi if sign == "+" else lo
    if ref in openings:
        o = openings[ref]
        assert o["axis"] == axis, (ref, axis)
        lo, hi = o["iv"]
        if face == "c":
            return (lo + hi) / 2
        return hi if sign == "+" else lo
    if ref in devices:
        return devices[ref]["along"]
    if ref in els and els[ref]["kind"] in {"wall", "door", "win", "niche"}:
        raise Pending(ref)
    raise ValueError(f"cannot anchor on {ref}")

def point(expr, axis):
    m = EXPR.match(expr)
    a = anchor(m["ref"], m["face"], m["sign"], axis)
    d = float(m["d"] or 0)
    return a + d if m["sign"] == "+" else a - d if m["sign"] == "-" else a

def interval(expr, axis, length):
    m = EXPR.match(expr)
    a = anchor(m["ref"], m["face"], m["sign"], axis)
    d = float(m["d"] or 0)
    if m["sign"] == "+":
        return (a + d, a + d + length)
    return (a - d - length, a - d)

def span(expr, axis):
    a, b = expr.split("..")
    def val(r, other):
        if r in grids:
            return grids[r][1]
        if r not in walls:
            raise Pending(r)
        lo, hi = walls[r]["pos"]
        oc = grids[other][1] if other in grids else sum(walls[other]["pos"]) / 2 if other in walls else None
        if oc is None:
            raise Pending(other)
        return hi if oc > (lo + hi) / 2 else lo
    return tuple(sorted((val(a, b), val(b, a))))

pending = [k for k in order if els[k]["kind"] == "wall"]
for _ in range(10):
    left = []
    for k in pending:
        e = els[k]
        try:
            if "on" in e["kv"]:
                src = walls.get(e["kv"]["on"]) or (_ for _ in ()).throw(Pending(e["kv"]["on"]))
                walls[k] = dict(src, level=e["pos"][0], type=e["pos"][1], lb="lb" in e["flags"], id=k)
                continue
            t = core(e["pos"][1])
            if "y" in e["kv"] and ".." not in e["kv"]["y"]:
                o, pos, sp = "h", interval(e["kv"]["y"], "y", t), span(e["kv"]["x"], "x")
            else:
                o, pos, sp = "v", interval(e["kv"]["x"], "x", t), span(e["kv"]["y"], "y")
            walls[k] = dict(o=o, pos=pos, span=sp, level=e["pos"][0], type=e["pos"][1], lb="lb" in e["flags"], id=k)
        except Pending:
            left.append(k)
    pending = left
    if not pending:
        break
if pending:
    problems.append(f"unresolved walls {pending}")

def wsize(s):
    w, h = s.split("x")
    return float(w), float(h)

pending = [k for k in order if els[k]["kind"] in {"door", "win", "niche"}]
for _ in range(10):
    left = []
    for k in pending:
        e = els[k]
        host = e["pos"][0].split(".")[0]
        w = walls[host]
        axis = "x" if w["o"] == "h" else "y"
        wd, ht = wsize(e["pos"][1])
        try:
            iv = interval(e["kv"][axis], axis, wd)
        except Pending:
            left.append(k)
            continue
        if "sill" in e["kv"]:
            sill = float(e["kv"]["sill"])
        elif e["kind"] == "win":
            sill = round(float(els[w["level"]]["kv"]["head"]) - ht, 4)  # windows hang from the storey's Sturzhöhe
        else:
            sill = 0.0  # doors stand on OKFF
        openings[k] = dict(id=k, kind=e["kind"], host=host, axis=axis, iv=iv, sill=sill, top=sill + ht,
                           face=e["pos"][0].split(".")[1] if "." in e["pos"][0] else None)
        if not (w["span"][0] - 1e-9 <= iv[0] and iv[1] <= w["span"][1] + 1e-9):
            problems.append(f"{k} outside host {host} span {w['span']}: {iv}")
    pending = left
    if not pending:
        break
for a in openings.values():
    for b in openings.values():
        if a["id"] < b["id"] and a["host"] == b["host"]:
            if a["iv"][0] < b["iv"][1] - 1e-9 and b["iv"][0] < a["iv"][1] - 1e-9 and a["sill"] < b["top"] and b["sill"] < a["top"]:
                problems.append(f"openings {a['id']} and {b['id']} overlap")

# stair
stairs = {}
for k in order:
    e = els[k]
    if e["kind"] == "stair":
        n, tread, wd = int(e["kv"]["n"]), float(e["kv"]["tread"]), float(e["kv"]["w"])
        run = (n - 1) * tread
        along = "x" if e["kv"]["up"] in "we" else "y"
        across = "y" if along == "x" else "x"
        iv_along = interval(e["kv"][along], along, run)
        iv_across = interval(e["kv"][across], across, wd)
        xs, ys = (iv_along, iv_across) if along == "x" else (iv_across, iv_along)
        rise = levels[e["pos"][1]][0] - levels[e["pos"][0]][0]
        stairs[k] = dict(x=xs, y=ys, up=e["kv"]["up"], n=n, tread=tread, riser=rise / n, level=e["pos"][0])

# room separators and rooms
seps = {}
for k in order:
    e = els[k]
    if e["kind"] == "sep":
        if "x" in e["kv"] and ".." not in e["kv"]["x"]:
            seps[k] = dict(o="v", pos=(point(e["kv"]["x"], "x"),) * 2, span=span(e["kv"]["y"], "y"), level=e["pos"][0], id=k)
        else:
            seps[k] = dict(o="h", pos=(point(e["kv"]["y"], "y"),) * 2, span=span(e["kv"]["x"], "x"), level=e["pos"][0], id=k)

def at(expr):
    xs, ys = expr.split(",")
    return point(xs, "x"), point(ys, "y")

rooms = {}
for k in order:
    e = els[k]
    if e["kind"] != "room":
        continue
    lvl = e["pos"][0]
    px, py = at(e["kv"]["at"])
    bounds = list(walls.values()) + list(seps.values())
    bounds = [b for b in bounds if b["level"] == lvl]
    def best(o, cmp_side):
        cands = []
        for b in bounds:
            if b["o"] != o:
                continue
            along = py if o == "v" else px
            if not (b["span"][0] <= along <= b["span"][1]):
                continue
            p = px if o == "v" else py
            if cmp_side == "lo" and b["pos"][1] <= p:
                cands.append((b["pos"][1], b))
            if cmp_side == "hi" and b["pos"][0] >= p:
                cands.append((-b["pos"][0], b))
        if not cands:
            return None
        v, b = max(cands, key=lambda c: c[0])
        return (abs(v), b)
    W_, E_, S_, N_ = best("v", "lo"), best("v", "hi"), best("h", "lo"), best("h", "hi")
    if S_ is None:
        S_ = (grids["S"][1], None)
    if N_ is None:
        N_ = (grids["N"][1], None)
    rooms[k] = dict(id=k, name=e["label"], level=lvl, use=e["pos"][1], x=(W_[0], E_[0]), y=(S_[0], N_[0]),
                    bounds=dict(w=W_[1], e=E_[1], s=S_[1], n=N_[1]), floor=e["kv"].get("floor"))

def finish(b, side_into_room):
    """Thickness of non-core layers on the face of bounding element b that faces the room."""
    if b is None or "type" not in b:
        return 0.0
    ls = layers(b["type"])
    ci = [i for i, l in enumerate(ls) if l[2]][0]
    inner, outer = sum(l[1] for l in ls[:ci]), sum(l[1] for l in ls[ci + 1:])
    if b["id"] in {w for w in walls if walls[w]["level"] and els[w]["pos"][1].startswith("AW")}:
        return inner  # exterior walls: first layers face inside
    return inner if side_into_room == "lo" else outer

for r in rooms.values():
    b = r["bounds"]
    rx = r["x"][1] - r["x"][0]
    ry = r["y"][1] - r["y"][0]
    fx = rx - finish(b["w"], "hi") - finish(b["e"], "lo")
    fy = ry - finish(b["s"], "hi") - finish(b["n"], "lo")
    r.update(rohbau=(rx, ry), fertig=(fx, fy), a_roh=rx * ry, a_fertig=fx * fy)
    r["center"] = ((r["x"][0] + r["x"][1]) / 2, (r["y"][0] + r["y"][1]) / 2)

def room_at(lvl, x, y):
    for r in rooms.values():
        if r["level"] == lvl and r["x"][0] <= x <= r["x"][1] and r["y"][0] <= y <= r["y"][1]:
            return r["id"]
    return "outside"

CENTER = (grids["E"][1] / 2, grids["N"][1] / 2)
DEFZ = {"sock": 0.3, "switch": 1.05, "data": 0.3}

def host_face(host):
    wid, _, face = host.partition(".")
    w = walls[wid]
    lo, hi = w["pos"]
    if not face:
        if "AW" not in w["type"]:
            raise ValueError(f"interior wall {wid} needs a face")
        c = CENTER[1] if w["o"] == "h" else CENTER[0]
        face = ("n" if w["o"] == "h" else "e") if abs(hi - c) < abs(lo - c) else ("s" if w["o"] == "h" else "w")
        face = face if abs(({"n": hi, "e": hi, "s": lo, "w": lo}[face]) - c) < abs(({"n": lo, "e": lo, "s": hi, "w": hi}[face]) - c) else face
    val = {"n": hi, "e": hi, "s": lo, "w": lo}[face]
    normal = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}[face]
    return w, face, val, normal

for k in order:
    e = els[k]
    if e["kind"] in {"sock", "conn", "switch", "data", "board", "lum", "fan", "san", "smoke", "tank", "gen"}:
        host = e["pos"][0] if e["pos"] else None
        z = float(e["kv"].get("z", DEFZ.get(e["kind"], 0)))
        if e["kind"] == "gen":
            x, y = at(e["kv"]["at"])
            devices[k] = dict(id=k, kind="gen", level=e["pos"][0], x=x, y=y, z=0, room="outside")
            continue
        if host and host in rooms:
            r = rooms[host]
            x, y = at(e["kv"]["at"]) if "at" in e["kv"] else r["center"]
            devices[k] = dict(id=k, kind=e["kind"], level=r["level"], x=x, y=y, z=None, room=host, ceiling=e["kind"] in {"lum", "smoke"})
            if room_at(r["level"], x, y) != host:
                problems.append(f"{k} at ({x:.2f},{y:.2f}) is not inside {host}")
            continue
        w, face, val, normal = host_face(host)
        axis = "x" if w["o"] == "h" else "y"
        c = point(e["kv"][axis], axis)
        x, y = (c, val) if axis == "x" else (val, c)
        rid = room_at(w["level"], x + normal[0] * 0.05, y + normal[1] * 0.05)
        devices[k] = dict(id=k, kind=e["kind"], level=w["level"], x=x, y=y, z=z, wall=w["id"], face=face, along=c, room=rid)
        if not (w["span"][0] - 1e-9 <= c <= w["span"][1] + 1e-9):
            problems.append(f"{k} at {c:.3f} outside {w['id']} span {w['span']}")
        for o in openings.values():
            if o["host"] == w["id"] and o["kind"] != "niche" and o["iv"][0] - 0.1 < c < o["iv"][1] + 0.1 and o["sill"] - 0.1 < z < o["top"] + 0.1:
                problems.append(f"{k} ({axis}={c:.3f}, z={z}) within 0.10 of opening {o['id']} {o['iv']} z {o['sill']}..{o['top']}")
        if rid == "outside" and face and e["kind"] not in {"lum", "sock"}:
            problems.append(f"{k} faces outside")

# back-to-back boxes in thin walls
wall_devs = {}
for d in devices.values():
    if "wall" in d:
        wall_devs.setdefault(d["wall"], []).append(d)
for wid, ds in wall_devs.items():
    if core(walls[wid]["type"]) > 0.2:
        continue
    for a in ds:
        for b in ds:
            if a["id"] < b["id"] and a["face"] != b["face"] and abs(a["along"] - b["along"]) < 0.15 and abs(a["z"] - b["z"]) < 0.25:
                problems.append(f"{a['id']} and {b['id']} back to back in {wid}")

# switch on the hinge side of a door that opens into the switch's room
for d in devices.values():
    if d["kind"] != "switch":
        continue
    for o in openings.values():
        e = els[o["id"]]
        if o["kind"] != "door" or o["host"] != d["wall"] or e["kv"].get("into") != d["room"]:
            continue
        lo, hi = o["iv"]
        if not (lo - 0.5 < d["along"] < hi + 0.5) or lo <= d["along"] <= hi:
            continue
        w = walls[o["host"]]
        rc = rooms[e["kv"]["into"]]["center"]
        if w["o"] == "h":
            hmin = (e["kv"]["din"] == "l") == (rc[1] < w["pos"][0])
        else:
            hmin = (e["kv"]["din"] == "l") == (rc[0] > w["pos"][1])
        if (d["along"] < lo) == hmin:
            problems.append(f"{d['id']} is on the hinge side of {o['id']} (din={e['kv']['din']})")

# stair checks
for k, s in stairs.items():
    step = 2 * s["riser"] + s["tread"]
    print(f"{k}: riser {s['riser']:.4f} tread {s['tread']} 2h+a {step:.3f} footprint x {s['x'][0]:.3f}..{s['x'][1]:.3f} y {s['y'][0]:.3f}..{s['y'][1]:.3f}")

# ---------- report ----------
print("PROBLEMS:" if problems else "no problems")
for p in problems:
    print("  ", p)
print("\nwalls:")
for k, w in walls.items():
    print(f"  {k} {w['level']} {w['o']} pos {w['pos'][0]:.3f}..{w['pos'][1]:.3f} span {w['span'][0]:.3f}..{w['span'][1]:.3f}")
print("\nopenings:")
for k, o in openings.items():
    print(f"  {k} in {o['host']} {o['axis']} {o['iv'][0]:.3f}..{o['iv'][1]:.3f} z {o['sill']}..{o['top']:.3f}")
print("\nrooms:")
tot = {}
for k, r in rooms.items():
    tot[r["level"]] = tot.get(r["level"], 0) + r["a_fertig"]
    print(f"  {k} {r['level']} {r['name']}: x {r['x'][0]:.3f}..{r['x'][1]:.3f} y {r['y'][0]:.3f}..{r['y'][1]:.3f} "
          f"roh {r['rohbau'][0]:.3f}x{r['rohbau'][1]:.3f}={r['a_roh']:.4f} fertig {r['fertig'][0]:.3f}x{r['fertig'][1]:.3f}={r['a_fertig']:.4f}")
print("  totals fertig:", {k: round(v, 2) for k, v in tot.items()})
print("\ndevices per room:")
per = {}
for d in devices.values():
    per.setdefault(d["room"], []).append(d["id"])
for r, ids in per.items():
    print(f"  {r}: {' '.join(ids)}")

# outlets per level
for lvl in ("EG", "OG"):
    socks = [els[d["id"]] for d in devices.values() if d["kind"] == "sock" and d["level"] == lvl]
    print(lvl, "sock", len(socks), "outlets", sum(int(s["kv"].get("n", 1)) for s in socks))

# ---------- size comparison ----------
def to_obj(el):
    o = {"kind": el["kind"], ("name" if el["kind"] in NAMED else "id"): el["key"]}
    o.update(dict(zip(POS[el["kind"]], el["pos"])))
    if el["label"] is not None:
        o["label"] = el["label"]
    for k, v in el["kv"].items():
        try:
            o[k] = float(v) if re.fullmatch(r"-?[\d.]+", v) else v
        except ValueError:
            o[k] = v
    for f in el["flags"]:
        o[f] = True
    return o

objs = [to_obj(els[k]) for k in order]
line_chars = sum(c for _, c in sizes.values())
mini = json.dumps(objs, ensure_ascii=False, separators=(",", ":"))
pretty = json.dumps(objs, ensure_ascii=False, indent=2)
print("\nfiles:", {f: s for f, s in sizes.items()})
print(f"elements {len(objs)}  line format {line_chars} chars  json-min {len(mini)} ({len(mini)/line_chars:.2f}x)  json-pretty {len(pretty)} ({len(pretty)/line_chars:.2f}x)")

# ---------- svg ----------
S = 60
def svg_level(lvl, title):
    ox, oy = 1.6, 1.2
    W_ = (grids["E"][1] + 3.2) * S
    H_ = (grids["N"][1] + 2.6) * S
    X = lambda x: (x + ox) * S
    Y = lambda y: H_ - (y + oy) * S
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_:.0f}" height="{H_ + 30:.0f}" font-family="sans-serif">',
           f'<rect width="100%" height="100%" fill="white"/>',
           f'<text x="10" y="{H_ + 20:.0f}" font-size="13">{title}  (Rohbau, 1 m = {S} px; generated from {ROOT.name})</text>']
    def rect(x0, x1, y0, y1, **kw):
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        out.append(f'<rect x="{X(x0):.1f}" y="{Y(y1):.1f}" width="{(x1 - x0) * S:.1f}" height="{(y1 - y0) * S:.1f}" {a}/>')
    def text(x, y, t, size=9, **kw):
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        out.append(f'<text x="{X(x):.1f}" y="{Y(y):.1f}" font-size="{size}" {a}>{t}</text>')
    for r in rooms.values():
        if r["level"] == lvl:
            rect(r["x"][0], r["x"][1], r["y"][0], r["y"][1], fill="#f7f7f2")
    for s in stairs.values():
        if s["level"] == lvl or (lvl == "OG" and s["level"] == "EG"):
            rect(s["x"][0], s["x"][1], s["y"][0], s["y"][1], fill="none", stroke="#333", stroke_width=1,
                 stroke_dasharray="4 3" if lvl == "OG" else "none")
            for i in range(s["n"]):
                xx = s["x"][0] + i * s["tread"]
                out.append(f'<line x1="{X(xx):.1f}" y1="{Y(s["y"][0]):.1f}" x2="{X(xx):.1f}" y2="{Y(s["y"][1]):.1f}" stroke="#999" stroke-width="0.7"/>')
            ym = (s["y"][0] + s["y"][1]) / 2
            out.append(f'<line x1="{X(s["x"][1] - 0.1):.1f}" y1="{Y(ym):.1f}" x2="{X(s["x"][0] + 0.15):.1f}" y2="{Y(ym):.1f}" stroke="#c00" stroke-width="1.2" marker-end="url(#a)"/>')
    out.insert(1, '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#c00"/></marker></defs>')
    for w in walls.values():
        if w["level"] != lvl:
            continue
        (x0, x1), (y0, y1) = (w["span"], w["pos"]) if w["o"] == "h" else (w["pos"], w["span"])
        rect(x0, x1, y0, y1, fill="#444" if w["lb"] else "#888")
    for s in seps.values():
        if s["level"] == lvl:
            out.append(f'<line x1="{X(s["pos"][0]):.1f}" y1="{Y(s["span"][0]):.1f}" x2="{X(s["pos"][0]):.1f}" y2="{Y(s["span"][1]):.1f}" stroke="#666" stroke-dasharray="6 4"/>')
    for o in openings.values():
        w = walls[o["host"]]
        if w["level"] != lvl:
            continue
        lo, hi = o["iv"]
        if w["o"] == "h":
            x0, x1, y0, y1 = lo, hi, *w["pos"]
        else:
            x0, x1, (y0, y1) = *w["pos"], (lo, hi)
        if o["kind"] == "niche":
            d = 0.11
            if o["face"] == "n": y0 = y1 - d
            if o["face"] == "s": y1 = y0 + d
            if o["face"] == "e": x0 = x1 - d
            if o["face"] == "w": x1 = x0 + d
            rect(x0, x1, y0, y1, fill="#fff", stroke="#06c", stroke_dasharray="2 2")
            continue
        rect(x0, x1, y0, y1, fill="white")
        if o["kind"] == "win":
            if w["o"] == "h":
                for f_ in (0.35, 0.5, 0.65):
                    yy = y0 + (y1 - y0) * f_
                    out.append(f'<line x1="{X(x0):.1f}" y1="{Y(yy):.1f}" x2="{X(x1):.1f}" y2="{Y(yy):.1f}" stroke="#06c" stroke-width="0.8"/>')
            else:
                for f_ in (0.35, 0.5, 0.65):
                    xx = x0 + (x1 - x0) * f_
                    out.append(f'<line x1="{X(xx):.1f}" y1="{Y(y0):.1f}" x2="{X(xx):.1f}" y2="{Y(y1):.1f}" stroke="#06c" stroke-width="0.8"/>')
        else:
            e = els[o["id"]]
            into = e["kv"].get("into")
            text((x0 + x1) / 2 - 0.1, (y0 + y1) / 2 - 0.05, o["id"], 8, fill="#a40")
            if not into:
                continue
            rc = rooms[into]["center"]
            wd = hi - lo
            if w["o"] == "h":
                face_y = y1 if rc[1] > y1 else y0
                sgn = 1 if rc[1] > y1 else -1
                viewer_left_is_minx = sgn < 0  # viewer in room facing the wall
                hinge_min = (e["kv"]["din"] == "l") == viewer_left_is_minx
                hx = lo if hinge_min else hi
                ox_ = hi if hinge_min else lo
                px_, py_ = hx, face_y + sgn * wd
                sweep = 1 if (hinge_min == (sgn > 0)) else 0
                out.append(f'<line x1="{X(hx):.1f}" y1="{Y(face_y):.1f}" x2="{X(px_):.1f}" y2="{Y(py_):.1f}" stroke="#a40"/>')
                out.append(f'<path d="M{X(ox_):.1f},{Y(face_y):.1f} A{wd * S:.1f},{wd * S:.1f} 0 0 {sweep} {X(px_):.1f},{Y(py_):.1f}" fill="none" stroke="#a40" stroke-width="0.7"/>')
            else:
                face_x = x1 if rc[0] > x1 else x0
                sgn = 1 if rc[0] > x1 else -1
                viewer_left_is_miny = sgn > 0  # in room east of wall, facing west: left is -y
                hinge_min = (e["kv"]["din"] == "l") == viewer_left_is_miny
                hy = lo if hinge_min else hi
                oy_ = hi if hinge_min else lo
                px_, py_ = face_x + sgn * wd, hy
                sweep = 0 if (hinge_min == (sgn > 0)) else 1
                out.append(f'<line x1="{X(face_x):.1f}" y1="{Y(hy):.1f}" x2="{X(px_):.1f}" y2="{Y(py_):.1f}" stroke="#a40"/>')
                out.append(f'<path d="M{X(face_x):.1f},{Y(oy_):.1f} A{wd * S:.1f},{wd * S:.1f} 0 0 {sweep} {X(px_):.1f},{Y(py_):.1f}" fill="none" stroke="#a40" stroke-width="0.7"/>')
    for r in rooms.values():
        if r["level"] == lvl:
            cx, cy = r["center"]
            text(cx - 0.6, cy + 0.35, f'{r["id"]} {r["name"]}', 11, font_weight="bold")
            text(cx - 0.6, cy + 0.1, f'{r["a_fertig"]:.2f} m²', 10)
    style = {"sock": ("circle", "#d00"), "conn": ("rect", "#d00"), "switch": ("rect", "#060"), "data": ("circle", "#80c"),
             "board": ("rect", "#000"), "lum": ("circle", "#e90"), "smoke": ("circle", "#555"), "fan": ("circle", "#0aa"),
             "san": ("rect", "#06c"), "tank": ("rect", "#c60"), "gen": ("rect", "#c60")}
    for d in devices.values():
        if d["level"] != lvl and not (d["kind"] == "gen" and lvl == "EG"):
            continue
        shape, col = style[d["kind"]]
        x, y = d["x"], d["y"]
        if "wall" in d:
            nx, ny = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}[d["face"]]
            x, y = x + nx * 0.09, y + ny * 0.09
        r_ = 0.25 if d["kind"] in {"tank", "gen", "san"} else 0.07
        if shape == "circle":
            out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{r_ * S:.1f}" fill="{col}" fill-opacity="0.85"/>')
        else:
            rect(x - r_, x + r_, y - r_, y + r_, fill=col, fill_opacity="0.6")
        text(x + 0.08, y + 0.08, d["id"], 7, fill=col)
    out.append("</svg>")
    return "\n".join(out)

if OUTDIR:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    project = next(e for e in els.values() if e["kind"] == "project")
    for lvl in ("EG", "OG"):
        z = levels[lvl][0]
        title = f"{project['label']}, {lvl} {'±0,00' if z == 0 else '+' + f'{z:.3f}'.replace('.', ',')}"
        (OUTDIR / f"grundriss-{lvl}.svg").write_text(svg_level(lvl, title), encoding="utf-8")

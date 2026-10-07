"""Prototype exports from a hand-written UEA project: Ansichten, Elektro-Installationspläne,
Verteilungsplan, Heizungsschema and a custom lighting calculation.

Not UEA code. Usage: python3 make_exports.py MODEL_DIR OUT_DIR
Runs check_model.py first and stops if the model has problems.
"""
import contextlib, hashlib, html, io, math, runpy, sys
from datetime import date
from pathlib import Path

SCR = Path(__file__).resolve().parent
MODEL, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
_argv = sys.argv
sys.argv = ["check_model.py", str(MODEL), str(OUT)]
with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path(str(SCR / "check_model.py"))
sys.argv = _argv
assert not G["problems"], G["problems"]
els, walls, openings, rooms, devices, stairs, grids, levels, order = (
    G[k] for k in ["els", "walls", "openings", "rooms", "devices", "stairs", "grids", "levels", "order"])
layers, core, finish, at = G["layers"], G["core"], G["finish"], G["at"]
PROJECT = next(e for e in els.values() if e["kind"] == "project")
GROUND = float(PROJECT["kv"]["ground"])
EX, NY = grids["E"][1], grids["N"][1]
STATE = hashlib.sha256(b"".join((MODEL / f"{f}.uea").read_bytes() for f in G["FILES"])).hexdigest()[:12]
DATE = date.today().strftime("%d.%m.%Y")


def de(v, nd=2):
    return f"{v:.{nd}f}".replace(".", ",").replace("-", "−")


def kote(v, nd=2):
    return "±0,00" if abs(v) < 1e-9 else ("+" if v > 0 else "") + de(v, nd)


class Svg:
    def __init__(s, w, h):
        s.w, s.h, s.items = w, h, []

    def _a(s, kw):
        return " ".join(f'{k.rstrip("_").replace("_", "-")}="{v}"' for k, v in kw.items() if v is not None)

    def line(s, x1, y1, x2, y2, stroke="#000", sw=1, **kw):
        s.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def rect(s, x, y, w, h, fill="none", stroke="#000", sw=1, **kw):
        s.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def poly(s, pts, fill="none", stroke="#000", sw=1, **kw):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        s.items.append(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def pline(s, pts, stroke="#000", sw=1, **kw):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        s.items.append(f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def circle(s, cx, cy, r, fill="none", stroke="#000", sw=1, **kw):
        s.items.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def path(s, d, fill="none", stroke="#000", sw=1, **kw):
        s.items.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {s._a(kw)}/>')

    def text(s, x, y, t, size=11, anchor="start", weight="normal", fill="#000", rot=None):
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ""
        s.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}"{tr}>{html.escape(str(t))}</text>')

    def save(s, name):
        body = "\n".join(s.items)
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.w:.0f}" height="{s.h:.0f}" font-family="DejaVu Sans, Arial, sans-serif">\n'
            f'<rect width="100%" height="100%" fill="white"/>\n{body}\n</svg>\n', encoding="utf-8")


def plankopf(svg, title, note="unmaßstäblich"):
    w, h = 430, 92
    x, y = svg.w - w - 15, svg.h - h - 15
    svg.rect(x, y, w, h, fill="white", stroke="#000", sw=1.2)
    svg.line(x, y + 26, x + w, y + 26)
    svg.text(x + 8, y + 18, f"{PROJECT['label']} · {PROJECT['key']}", 13, weight="bold")
    svg.text(x + 8, y + 44, title, 13, weight="bold")
    svg.text(x + 8, y + 62, f"Prototyp aus dem UEA-Modell, nicht zur Ausführung · {note}", 10)
    svg.text(x + 8, y + 78, f"Modellstand {STATE} · {DATE} · erzeugt aus {MODEL.name}", 10, fill="#444")


# ---------------------------------------------------------------- roof geometry
rf = els["rf1"]
PITCH = math.radians(float(rf["kv"]["pitch"]))
KN, EAVE, VERGE = (float(rf["kv"][k]) for k in ("kn", "eave", "verge"))
_rl = layers(rf["pos"][1])
_ci = [i for i, l in enumerate(_rl) if l[2]][0]
T_VERT = sum(l[1] for l in _rl[:_ci + 1]) / math.cos(PITCH)
RD_DB = levels["DB"][0] - levels["DB"][1]
UK0 = RD_DB + KN  # underside of rafters at the outer wall face


def uk(d):  # underside of rafters at horizontal distance d inside the eaves wall face
    return UK0 + d * math.tan(PITCH)


RIDGE_D = NY / 2
TRAUFE = uk(0) + T_VERT
FIRST = uk(RIDGE_D) + T_VERT

# ---------------------------------------------------------------- Ansichten
FACES = {
    "S": dict(title="Ansicht Süd", L=EX, h=True, sel=lambda w: w["o"] == "h" and w["pos"][0] < 0.01, u=lambda a: a),
    "N": dict(title="Ansicht Nord", L=EX, h=True, sel=lambda w: w["o"] == "h" and w["pos"][1] > NY - 0.01, u=lambda a: EX - a),
    "E": dict(title="Ansicht Ost", L=NY, h=False, sel=lambda w: w["o"] == "v" and w["pos"][1] > EX - 0.01, u=lambda a: a),
    "W": dict(title="Ansicht West", L=NY, h=False, sel=lambda w: w["o"] == "v" and w["pos"][0] < 0.01, u=lambda a: NY - a),
}


def ansichten():
    S = 45
    FW, FH = 920, 520
    svg = Svg(2 * FW + 40, 2 * FH + 150)
    for idx, key in enumerate(["S", "E", "N", "W"]):
        f = FACES[key]
        fx, fy = 20 + (idx % 2) * FW, 20 + (idx // 2) * FH
        PX = lambda u: fx + 70 + (u + 2.2) * S
        PY = lambda z: fy + 50 + (8.9 - z) * S
        L = f["L"]
        svg.text(fx + 10, fy + 24, f["title"], 16, weight="bold")
        # terrain
        svg.line(PX(-2.0), PY(GROUND), PX(L + 2.0), PY(GROUND), sw=1.6)
        for i in range(int((L + 4) / 0.25)):
            u = -2.0 + i * 0.25
            svg.line(PX(u), PY(GROUND), PX(u - 0.15), PY(GROUND - 0.15), stroke="#666", sw=0.6)
        fw = [w for w in walls.values() if f["sel"](w)]
        # facade body
        if f["h"]:
            top = uk(-EAVE)
            svg.rect(PX(0), PY(top), L * S, (top - GROUND) * S, fill="#f2eee6", stroke="#000", sw=1.4)
            # fascia and roof face
            svg.rect(PX(-VERGE), PY(uk(-EAVE) + T_VERT), (L + 2 * VERGE) * S, T_VERT * S, fill="#7a4a3a", stroke="#000")
            y0, y1 = uk(-EAVE) + T_VERT, FIRST
            svg.rect(PX(-VERGE), PY(y1), (L + 2 * VERGE) * S, (y1 - y0) * S, fill="#b5654a", stroke="#000", sw=1.2)
            z = y0 + 0.14
            while z < y1 - 0.05:
                svg.line(PX(-VERGE), PY(z), PX(L + VERGE), PY(z), stroke="#7a3a2a", sw=0.5)
                z += 0.14
            svg.line(PX(-VERGE), PY(y1), PX(L + VERGE), PY(y1), sw=3)
        else:
            mid = f["u"](RIDGE_D)
            pts = [(PX(0), PY(GROUND)), (PX(0), PY(uk(0))), (PX(mid), PY(uk(RIDGE_D))), (PX(L), PY(uk(0))), (PX(L), PY(GROUND))]
            svg.poly(pts, fill="#f2eee6", stroke="#000", sw=1.4)
            lo = [(PX(-EAVE), PY(uk(-EAVE))), (PX(mid), PY(uk(RIDGE_D))), (PX(L + EAVE), PY(uk(-EAVE)))]
            hi = [(PX(L + EAVE), PY(uk(-EAVE) + T_VERT)), (PX(mid), PY(FIRST)), (PX(-EAVE), PY(uk(-EAVE) + T_VERT))]
            svg.poly(lo + hi, fill="#7a4a3a", stroke="#000", sw=1.2)
        # storey lines
        for lv, name in (("EG", "OKFF EG"), ("OG", "OKFF OG")):
            z = levels[lv][0]
            svg.line(PX(0), PY(z), PX(L), PY(z), stroke="#999", sw=0.6, stroke_dasharray="6 4")
        # openings
        for o in openings.values():
            if o["kind"] == "niche" or o["host"] not in {w["id"] for w in fw}:
                continue
            lz = levels[walls[o["host"]]["level"]][0]
            u0, u1 = sorted((f["u"](o["iv"][0]), f["u"](o["iv"][1])))
            z0, z1 = lz + o["sill"], lz + o["top"]
            svg.rect(PX(u0), PY(z1), (u1 - u0) * S, (z1 - z0) * S, fill="#fff", stroke="#000", sw=1.2)
            fr = 0.06
            if o["kind"] == "win" or els[o["id"]]["kv"].get("typ") == "HST-1":
                n = 2 if u1 - u0 > 1.3 else 1
                wseg = (u1 - u0 - 2 * fr) / n
                for i in range(n):
                    a = u0 + fr + i * wseg
                    svg.rect(PX(a + 0.02), PY(z1 - fr), (wseg - 0.04) * S, (z1 - z0 - 2 * fr) * S, fill="#cfe3ef", stroke="#333", sw=0.8)
                if o["sill"] > 0:
                    svg.line(PX(u0 - 0.04), PY(z0 - 0.03), PX(u1 + 0.04), PY(z0 - 0.03), sw=1.6)
            else:
                svg.rect(PX(u0 + fr), PY(z1 - fr), (u1 - u0 - 2 * fr) * S, (z1 - z0 - fr) * S, fill="#8a7a6a", stroke="#333", sw=0.8)
                svg.circle(PX(u1 - 0.2), PY(z0 + 1.05), 2.5, fill="#ddd")
            svg.text(PX((u0 + u1) / 2), PY(z1) - 4, o["id"], 9, anchor="middle", fill="#a40")
        # exterior devices, fans, heat pump
        fwid = {w["id"] for w in fw}
        for d in devices.values():
            if d.get("wall") in fwid and (d["room"] == "outside" or d["kind"] == "fan"):
                u = f["u"](d["along"])
                z = levels[d["level"]][0] + d["z"]
                if d["kind"] == "lum":
                    svg.circle(PX(u), PY(z), 5, fill="#ffd34d")
                elif d["kind"] == "fan":
                    svg.circle(PX(u), PY(z), 0.1 * S, fill="#eee")
                    svg.line(PX(u - 0.1), PY(z), PX(u + 0.1), PY(z), sw=0.6)
                else:
                    svg.rect(PX(u) - 4, PY(z) - 4, 8, 8, fill="#ccc")
                svg.text(PX(u) + 7, PY(z) + 3, d["id"], 9, fill="#06c")
        g = devices["g1"]
        gx, gy = g["x"], g["y"]
        along = gx if f["h"] else gy
        front = {"W": gx < 0, "E": gx > EX, "S": gy < 0, "N": gy > NY}[key]
        u = f["u"](along)
        if front or not (0 < u < L):
            svg.rect(PX(u - 0.5), PY(GROUND + 0.9), 1.0 * S, 0.9 * S, fill="#e8e8e8", stroke="#000")
            svg.circle(PX(u), PY(GROUND + 0.45), 0.3 * S, fill="none", stroke="#555")
            svg.text(PX(u), PY(GROUND + 0.9) - 4, "g1 WP", 9, anchor="middle", fill="#06c")
        # height marks
        mx = PX(L + 2.5)
        marks = [(FIRST, "First", 2), (TRAUFE, "Traufe" if f["h"] else "Traufe (Außenwand/Dachhaut)", 2),
                 (levels["OG"][0], "OKFF OG", 3), (0.0, "OKFF EG", 2), (GROUND, "Gelände", 2)]
        for z, name, nd in marks:
            svg.poly([(mx, PY(z)), (mx - 6, PY(z) - 8), (mx + 6, PY(z) - 8)], fill="#000")
            svg.line(mx - 14, PY(z), mx + 14, PY(z), sw=0.8)
            svg.text(mx + 18, PY(z) - 2, f"{kote(z, nd)}  {name}", 10)
        # width dimension
        dy = PY(GROUND) + 26
        svg.line(PX(0), dy, PX(L), dy, sw=0.8)
        for u in (0, L):
            svg.line(PX(u) - 5, dy + 5, PX(u) + 5, dy - 5, sw=1.2)
            svg.line(PX(u), dy - 8, PX(u), dy + 8, sw=0.6)
        svg.text(PX(L / 2), dy - 4, de(L), 11, anchor="middle")
    svg.text(30, svg.h - 70, "Fensterteilung, Sockel, Dachrinne und Fallrohre sind nicht im Modell und schematisch bzw. weggelassen.", 11, fill="#444")
    svg.text(30, svg.h - 52, f"Dach: Satteldach {de(math.degrees(PITCH), 0)}°, Kniestock {de(KN)} (UK Sparren an Außenkante über OK Rohdecke DB), Traufüberstand {de(EAVE)}, Ortgang {de(VERGE)}.", 11, fill="#444")
    plankopf(svg, "Ansichten Nord, Ost, Süd, West")
    svg.save("ansichten.svg")


# ---------------------------------------------------------------- floor plan base
def floor_base(svg, lvl, X, Y, S, room_labels=True, faded=False):
    wallc = "#9a9a9a" if faded else "#444"
    for r in rooms.values():
        if r["level"] == lvl:
            svg.rect(X(r["x"][0]), Y(r["y"][1]), (r["x"][1] - r["x"][0]) * S, (r["y"][1] - r["y"][0]) * S, fill="#fbfbf8", stroke="none")
    for s in stairs.values():
        if s["level"] == lvl or lvl == "OG":
            svg.rect(X(s["x"][0]), Y(s["y"][1]), (s["x"][1] - s["x"][0]) * S, (s["y"][1] - s["y"][0]) * S, fill="none", stroke="#888",
                     stroke_dasharray="5 3" if lvl != s["level"] else None)
            for i in range(s["n"]):
                xx = s["x"][0] + i * s["tread"]
                svg.line(X(xx), Y(s["y"][0]), X(xx), Y(s["y"][1]), stroke="#bbb", sw=0.6)
    for w in walls.values():
        if w["level"] != lvl:
            continue
        (x0, x1), (y0, y1) = (w["span"], w["pos"]) if w["o"] == "h" else (w["pos"], w["span"])
        svg.rect(X(x0), Y(y1), (x1 - x0) * S, (y1 - y0) * S, fill=wallc, stroke="none")
    for s in G["seps"].values():
        if s["level"] == lvl:
            svg.line(X(s["pos"][0]), Y(s["span"][0]), X(s["pos"][0]), Y(s["span"][1]), stroke="#999", stroke_dasharray="6 4")
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
            continue
        svg.rect(X(x0), Y(y1), (x1 - x0) * S, (y1 - y0) * S, fill="#fff", stroke="none")
        if o["kind"] == "win":
            if w["o"] == "h":
                svg.line(X(x0), Y((y0 + y1) / 2), X(x1), Y((y0 + y1) / 2), stroke="#888", sw=0.8)
            else:
                svg.line(X((x0 + x1) / 2), Y(y0), X((x0 + x1) / 2), Y(y1), stroke="#888", sw=0.8)
    for o in openings.values():
        w = walls[o["host"]]
        e = els[o["id"]]
        if w["level"] != lvl or o["kind"] != "door" or "into" not in e["kv"]:
            continue
        lo, hi = o["iv"]
        wd = hi - lo
        rc = rooms[e["kv"]["into"]]["center"]
        if w["o"] == "h":
            y0, y1 = w["pos"]
            face, sgn = (y1, 1) if rc[1] > y1 else (y0, -1)
            hmin = (e["kv"]["din"] == "l") == (sgn < 0)
            h_, o_ = (lo, hi) if hmin else (hi, lo)
            hp, op, tp = (h_, face), (o_, face), (h_, face + sgn * wd)
        else:
            x0, x1 = w["pos"]
            face, sgn = (x1, 1) if rc[0] > x1 else (x0, -1)
            hmin = (e["kv"]["din"] == "l") == (sgn > 0)
            h_, o_ = (lo, hi) if hmin else (hi, lo)
            hp, op, tp = (face, h_), (face, o_), (face + sgn * wd, h_)
        cross = (op[0] - hp[0]) * (tp[1] - hp[1]) - (op[1] - hp[1]) * (tp[0] - hp[0])
        svg.line(X(hp[0]), Y(hp[1]), X(tp[0]), Y(tp[1]), stroke="#b08060", sw=1)
        svg.path(f"M{X(op[0]):.1f},{Y(op[1]):.1f} A{wd * S:.1f},{wd * S:.1f} 0 0 {1 if cross < 0 else 0} {X(tp[0]):.1f},{Y(tp[1]):.1f}",
                 stroke="#b08060", sw=0.7)
    if room_labels:
        for r in rooms.values():
            if r["level"] == lvl:
                cx, cy = r["center"]
                svg.text(X(cx), Y(cy - 0.55), r["name"], 12, anchor="middle", fill="#777", weight="bold")
                svg.text(X(cx), Y(cy - 0.55) + 13, f'{r["id"]} · {de(r["a_fertig"])} m²', 9, anchor="middle", fill="#999")


# ---------------------------------------------------------------- switching
ctl, sw_of = {}, {}
for k in order:
    e = els[k]
    if e["kind"] == "switch":
        rockers = [g.split("+") for g in e["kv"]["ctl"].split(",")]
        ctl[k] = rockers
        for g in rockers:
            for l in g:
                sw_of.setdefault(l, []).append(k)


def rocker_code(sw, group):
    ss = sw_of[group[0]]
    if len(ss) == 1:
        return "D" if "dim" in els[sw]["flags"] else "A"
    if len(ss) == 2:
        return "W"
    pts = {s: (devices[s]["x"], devices[s]["y"]) for s in ss}
    pairs = [(math.dist(pts[a], pts[b]), a, b) for a in ss for b in ss if a < b]
    _, a, b = max(pairs)
    return "W" if sw in (a, b) else "K"


PAL = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]
CIRCS = [k for k in order if els[k]["kind"] == "circ"]
CCOL = {c: PAL[i % len(PAL)] for i, c in enumerate(CIRCS)}
NORMAL = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}


def installationsplan(lvl):
    S = 72
    W_ = (EX + 3.0) * S
    svg = Svg(W_ + 420, (NY + 2.6) * S + 130)
    X = lambda x: 20 + (x + 1.5) * S
    Y = lambda y: 40 + (NY + 1.2 - y) * S
    floor_base(svg, lvl, X, Y, S, faded=True)
    svg.text(20, 26, f"Elektro-Installationsplan {lvl} mit Schaltungen", 18, weight="bold")

    placed, shift = {}, {}
    for d in sorted((d for d in devices.values() if d["level"] == lvl and "wall" in d), key=lambda d: int(d["id"].lstrip("abcdefghijklmnopqrstuvwxyz") or 0)):
        key = (d["wall"], d["face"])
        sh = 0.0
        while any(abs(d["along"] + sh - a) < 0.15 for a in placed.get(key, [])):
            sh += 0.17
        placed.setdefault(key, []).append(d["along"] + sh)
        shift[d["id"]] = sh

    def frame(d):
        nx, ny = NORMAL[d["face"]]
        t = (ny, -nx)
        sh = shift.get(d["id"], 0.0)
        return (d["x"] + t[0] * sh, d["y"] + t[1] * sh), (nx, ny), t

    def P(p):
        return X(p[0]), Y(p[1])

    def off(p, n, t, a, b):
        return (p[0] + n[0] * a + t[0] * b, p[1] + n[1] * a + t[1] * b)

    lvl_dev = [d for d in devices.values() if d["level"] == lvl]
    # switching lines first (under symbols)
    for d in lvl_dev:
        if d["kind"] != "switch":
            continue
        p, n, t = frame(d)
        a = P(off(p, n, t, 0.16, 0))
        col = CCOL[els[d["id"]]["pos"][1]]
        for g in ctl[d["id"]]:
            for l in g:
                ld = devices[l]
                if ld["level"] != lvl:
                    continue
                svg.line(*a, X(ld["x"]), Y(ld["y"]), stroke=col, sw=0.9, stroke_dasharray="4 3", opacity="0.8")
    for d in lvl_dev:
        e = els[d["id"]]
        k = d["kind"]
        circ = e["pos"][1] if k in {"sock", "conn", "switch"} else None
        col = CCOL.get(circ, "#333")
        label = d["id"] + (f" {circ}" if circ else "")
        if "wall" in d:
            p, n, t = frame(d)
            if k == "sock":
                base = off(p, n, t, 0.05, 0)
                svg.line(*P(p), *P(base), stroke=col, sw=1.4)
                c = off(p, n, t, 0.05, 0)
                r = 0.1
                a1, a2 = P(off(c, n, t, 0, -r)), P(off(c, n, t, 0, r))
                svg.line(*a1, *a2, stroke=col, sw=1.4)
                svg.path(f"M{a1[0]:.1f},{a1[1]:.1f} A{r * S:.1f},{r * S:.1f} 0 0 {0 if (n[0] + n[1]) > 0 else 1} {a2[0]:.1f},{a2[1]:.1f}", stroke=col, sw=1.4)
                pk = off(c, n, t, r + 0.04, 0)
                svg.line(*P(off(pk, n, t, 0, -0.07)), *P(off(pk, n, t, 0, 0.07)), stroke=col, sw=1.4)
                nn = int(e["kv"].get("n", 1))
                if nn > 1:
                    q = P(off(c, n, t, 0.07, 0.13))
                    svg.text(q[0], q[1] + 3, str(nn), 10, anchor="middle", weight="bold", fill=col)
            elif k == "switch":
                c = off(p, n, t, 0.16, 0)
                svg.line(*P(p), *P(off(p, n, t, 0.1, 0)), stroke=col, sw=1.2)
                svg.circle(*P(c), 0.06 * S, fill="white", stroke=col, sw=1.4)
                codes = [rocker_code(d["id"], g) for g in ctl[d["id"]]]
                for i, code in enumerate(codes):
                    ang = (1 if i == 0 else -1)
                    tip = off(c, n, t, 0.17, 0.12 * ang)
                    svg.line(*P(c), *P(tip), stroke=col, sw=1.3)
                    svg.line(*P(tip), *P(off(tip, n, t, -0.05, 0.05 * ang)), stroke=col, sw=1.3)
                    if code in "WK":
                        tip2 = off(c, n, t, -0.12, -0.12 * ang)
                        svg.line(*P(c), *P(tip2), stroke=col, sw=1.3)
                        svg.line(*P(tip2), *P(off(tip2, n, t, 0.05, -0.05 * ang)), stroke=col, sw=1.3)
                q = P(off(c, n, t, 0.0, -0.2))
                svg.text(q[0], q[1] + 3, "/".join(codes), 9, anchor="middle", weight="bold", fill=col)
            elif k == "conn":
                c = off(p, n, t, 0.12, 0)
                svg.rect(X(c[0]) - 6, Y(c[1]) - 6, 12, 12, fill=col)
                q = P(off(c, n, t, 0.18, 0))
                svg.text(q[0], q[1] + 3, e["label"] or "", 9, anchor="middle", fill=col)
            elif k == "data":
                c = off(p, n, t, 0.12, 0)
                svg.rect(X(c[0]) - 8, Y(c[1]) - 6, 16, 12, fill="white", stroke="#80c", sw=1.2)
                svg.text(X(c[0]), Y(c[1]) + 3, "TD", 7, anchor="middle", fill="#80c")
            elif k == "board":
                c = off(p, n, t, 0.1, 0)
                a, b = P(off(c, n, t, -0.08, -0.28)), P(off(c, n, t, 0.08, 0.28))
                xs, ys = sorted((a[0], b[0])), sorted((a[1], b[1]))
                svg.rect(xs[0], ys[0], xs[1] - xs[0], ys[1] - ys[0], fill="#fff", stroke="#000", sw=1.4)
                svg.line(xs[0], ys[1], xs[1], ys[0])
                label = d["id"] + " " + (e["label"] or "")
            elif k == "lum":
                c = off(p, n, t, 0.12, 0)
                svg.line(*P(p), *P(c), stroke="#c80", sw=1)
                svg.circle(*P(c), 0.08 * S, fill="white", stroke="#c80", sw=1.4)
                r = 0.08 * S * 0.7
                svg.line(X(c[0]) - r, Y(c[1]) - r, X(c[0]) + r, Y(c[1]) + r, stroke="#c80")
                svg.line(X(c[0]) - r, Y(c[1]) + r, X(c[0]) + r, Y(c[1]) - r, stroke="#c80")
            elif k == "fan":
                c = off(p, n, t, 0.12, 0)
                svg.circle(*P(c), 0.08 * S, fill="#e6f7f7", stroke="#0aa", sw=1.2)
                svg.text(*P(c), "L", 8, anchor="middle", fill="#0aa")
            else:
                continue
            q = P(off(p, n, t, 0.38, 0))
            if k not in {"board"}:
                svg.text(q[0], q[1] + 3, label, 8, anchor="middle", fill=col)
            else:
                svg.text(q[0] + 4, q[1] + 3, label, 9, fill="#000")
            zdef = {"sock": 0.3, "switch": 1.05, "data": 0.3}.get(k)
            if zdef is not None and abs(d["z"] - zdef) > 1e-6:
                q2 = P(off(p, n, t, 0.38, 0))
                svg.text(q2[0], q2[1] + 13, f"h={de(d['z'])}", 7, anchor="middle", fill="#666")
        else:
            x, y = X(d["x"]), Y(d["y"])
            if k == "lum":
                typ = e["kv"].get("typ", "")
                r = (0.06 if typ.startswith("DL") else 0.11) * S
                svg.circle(x, y, r, fill="white", stroke="#c80", sw=1.5)
                rr = r * 0.7
                svg.line(x - rr, y - rr, x + rr, y + rr, stroke="#c80", sw=1.2)
                svg.line(x - rr, y + rr, x + rr, y - rr, stroke="#c80", sw=1.2)
                svg.text(x + r + 3, y - 3, d["id"] + (f" {typ}" if typ else ""), 8, fill="#c80")
                if "z" in e["kv"]:
                    svg.text(x + r + 3, y + 8, f"Pendel h={de(float(e['kv']['z']))}", 7, fill="#666")
            elif k == "smoke":
                if any(o["kind"] == "lum" and o["level"] == lvl and math.dist((o["x"], o["y"]), (d["x"], d["y"])) < 0.3 for o in devices.values()):
                    x += 0.45 * S
                svg.rect(x - 9, y - 9, 18, 18, fill="#fff", stroke="#555", sw=1.2)
                svg.text(x, y + 3, "RM", 7, anchor="middle", fill="#555")
                svg.text(x + 12, y + 3, d["id"], 8, fill="#555")
    # feeds
    for k in order:
        e = els[k]
        if e["kind"] != "feed":
            continue
        tgt = devices[e["pos"][0]]
        if tgt["level"] != lvl:
            continue
        circ = e["pos"][1]
        x, y = X(tgt["x"]), Y(tgt["y"])
        svg.poly([(x - 7, y - 7), (x + 8, y), (x - 7, y + 7)], fill=CCOL[circ])
        svg.text(x + 10, y + 14, f"{k} → {tgt['id']} {circ}", 8, fill=CCOL[circ])
    # legend
    lx = W_ + 30
    svg.rect(lx - 10, 50, 390, svg.h - 230, fill="white", stroke="#000")
    svg.text(lx, 74, "Legende (Symbole vereinfacht nach DIN EN 60617)", 11, weight="bold")
    items = [("Schutzkontaktsteckdose, Zahl = Mehrfach, h = Höhe ≠ 0,30", "#d62728"),
             ("Schalter: A Aus, D Dimmer, W Wechsel, K Kreuz, A/A Serien", "#1f77b4"),
             ("Leuchtenauslass Decke / Wand, kleine = Downlight", "#c80"),
             ("Geräteanschlussdose", "#d62728"), ("Datendose TD", "#80c"), ("Rauchwarnmelder RM", "#555"),
             ("Einspeisung zu Gerät anderer Gewerke (feed)", "#000"), ("Schaltverbindung Schalter → Leuchte", "#000")]
    for i, (t_, c_) in enumerate(items):
        svg.text(lx, 98 + i * 18, "• " + t_, 10, fill=c_)
    used = sorted({els[d["id"]]["pos"][1] for d in lvl_dev if d["kind"] in {"sock", "conn", "switch"}} |
                  {els[k]["pos"][1] for k in order if els[k]["kind"] == "feed" and devices[els[k]["pos"][0]]["level"] == lvl},
                  key=lambda c: int(c[1:]))
    y0 = 98 + len(items) * 18 + 20
    svg.text(lx, y0, "Stromkreise auf diesem Plan", 11, weight="bold")
    for i, c in enumerate(used):
        e = els[c]
        svg.rect(lx, y0 + 10 + i * 17, 10, 10, fill=CCOL[c], stroke="none")
        svg.text(lx + 16, y0 + 19 + i * 17, f'{c}  {e["pos"][2]}{" 3p" if e["kv"].get("p") == "3" else ""}  {e["pos"][1]}  {e["label"]}', 10)
    plankopf(svg, f"Elektro-Installationsplan {lvl}")
    svg.save(f"elektro-{lvl}.svg")


# ---------------------------------------------------------------- Verteilungsplan
def verteilung():
    b1 = els["b1"]
    rcds = [k for k in order if els[k]["kind"] == "rcd"]
    by_rcd = {r: [c for c in CIRCS if els[c]["pos"][0] == r] for r in rcds}
    # derived phase assignment: single-phase circuits L1, L2, L3 in turn
    phase, i = {}, 0
    for c in CIRCS:
        if els[c]["kv"].get("p") == "3":
            phase[c] = "L1–L3"
        else:
            phase[c] = f"L{i % 3 + 1}"
            i += 1
    # what hangs on each circuit
    def load(c):
        socks = [d for d in devices.values() if d["kind"] == "sock" and els[d["id"]]["pos"][1] == c]
        conns = [d for d in devices.values() if d["kind"] == "conn" and els[d["id"]]["pos"][1] == c]
        sws = [k for k in ctl if els[k]["pos"][1] == c]
        lums = sorted({l for k in sws for g in ctl[k] for l in g}, key=lambda l: int(l[1:]))
        feeds = [els[k]["pos"][0] for k in order if els[k]["kind"] == "feed" and els[k]["pos"][1] == c]
        out = []
        if socks:
            out.append(f"{len(socks)} Dosen / {sum(int(els[d['id']]['kv'].get('n', 1)) for d in socks)} Steckpl.")
        if conns:
            out.append(" ".join(els[d["id"]]["label"] or d["id"] for d in conns))
        if sws:
            out.append(f"{len(sws)} Schalter, {len(lums)} Leuchte{'n' if len(lums) != 1 else ''}")
        if feeds:
            out.append("→ " + " ".join(feeds))
        return out
    COLW = 74
    x0 = 300
    width = x0 + sum(max(1, len(v)) for v in by_rcd.values()) * COLW + 60
    svg = Svg(max(width, 1500), 1040)
    svg.text(20, 30, "Verteilungsplan b1 Zählerschrank/UV – Übersichtsschaltplan (einpolig)", 18, weight="bold")
    # supply chain
    sx = 90
    svg.rect(sx - 70, 50, 140, 34, fill="#f4f4f4")
    svg.text(sx, 66, "Netz / HAK", 11, anchor="middle")
    svg.text(sx, 79, "(nicht im Modell)", 9, anchor="middle", fill="#666")
    svg.line(sx, 84, sx, 110)
    svg.circle(sx, 128, 18, fill="white")
    svg.text(sx, 132, "kWh", 10, anchor="middle")
    svg.text(sx + 26, 132, f"Zähler ({b1['kv'].get('meters')})", 10)
    svg.line(sx, 146, sx, 170)
    svg.rect(sx - 30, 170, 60, 34, fill="white")
    svg.text(sx, 186, "SLS", 11, anchor="middle", weight="bold")
    svg.text(sx, 199, b1["kv"]["main"].replace("SLS-", ""), 10, anchor="middle")
    svg.line(sx, 204, sx, 260)
    bus_y = 260
    svg.line(sx, bus_y, width - 40, bus_y, sw=3)
    svg.text(sx + 8, bus_y - 6, "L1 L2 L3 N PE", 9, fill="#444")
    # SPD
    px_ = 190
    svg.line(px_, bus_y, px_, 300)
    svg.rect(px_ - 30, 300, 60, 34, fill="white")
    svg.text(px_, 316, "SPD", 11, anchor="middle", weight="bold")
    svg.text(px_, 329, b1["kv"]["spd"], 10, anchor="middle")
    svg.line(px_, 334, px_, 352)
    for i_, wdt in enumerate((20, 13, 6)):
        svg.line(px_ - wdt / 2, 352 + i_ * 5, px_ + wdt / 2, 352 + i_ * 5, sw=1.4)
    x = x0
    for r in rcds:
        cs = by_rcd[r]
        gw = max(1, len(cs)) * COLW
        cx = x + gw / 2
        svg.line(cx, bus_y, cx, 300)
        svg.rect(cx - 46, 300, 92, 50, fill="white", sw=1.3)
        rating, typ = els[r]["pos"][1], els[r]["pos"][2]
        svg.text(cx, 316, f"{r}  RCD", 11, anchor="middle", weight="bold")
        svg.text(cx, 330, f"{rating.replace('/', ' A / ').replace('.', ',')} A", 9, anchor="middle")
        svg.text(cx, 343, f"Typ {typ}, 4-polig", 9, anchor="middle")
        svg.line(cx, 350, cx, 380)
        svg.line(x + COLW / 2, 380, x + gw - COLW / 2, 380, sw=2)
        for j, c in enumerate(cs):
            e = els[c]
            ccx = x + j * COLW + COLW / 2
            svg.line(ccx, 380, ccx, 400)
            svg.rect(ccx - 24, 400, 48, 30, fill="white", stroke=CCOL[c], sw=1.6)
            svg.text(ccx, 414, e["pos"][2], 11, anchor="middle", weight="bold")
            svg.text(ccx, 426, "3-polig" if e["kv"].get("p") == "3" else "1-polig", 8, anchor="middle")
            svg.line(ccx, 430, ccx, 460, stroke=CCOL[c], sw=1.6)
            svg.poly([(ccx - 5, 460), (ccx + 5, 460), (ccx, 469)], fill=CCOL[c], stroke="none")
            svg.text(ccx, 486, c, 13, anchor="middle", weight="bold", fill=CCOL[c])
            svg.text(ccx, 501, phase[c], 10, anchor="middle")
            svg.text(ccx, 515, e["pos"][1].replace(".", ","), 8, anchor="middle")
            lines = [e["label"]] + load(c)
            for k_, t_ in enumerate(lines):
                svg.text(ccx - 18 + k_ * 13, 528, t_, 9 if k_ == 0 else 8, rot=90, weight="bold" if k_ == 0 else "normal",
                         fill="#000" if k_ == 0 else "#444")
        x += gw
    # Belegungsplan
    by = 760
    svg.text(20, by - 14, "Belegung Verteilerfeld (abgeleitet), 12 TE je Reihe", 13, weight="bold")
    TE = 30
    rows = [[("SPD " + b1["kv"]["spd"], 4, "#ddd")]]
    for r in rcds:
        row = [(f"{r} RCD", 4, "#eee")]
        for c in by_rcd[r]:
            row.append((f"{c} {els[c]['pos'][2]}", 3 if els[c]["kv"].get("p") == "3" else 1, CCOL[c]))
        rows.append(row)
    for ri, row in enumerate(rows):
        yy = by + ri * 36
        svg.rect(20, yy, 12 * TE, 28, fill="none", stroke="#aaa")
        svg.text(12 * TE + 30, yy + 18, f"Reihe {ri + 1}: {sum(w for _, w, _ in row)} TE", 10, fill="#444")
        xx = 20
        for name, w, colr in row:
            grey = colr in ("#ddd", "#eee")
            svg.rect(xx, yy, w * TE, 28, fill=colr if grey else "white", stroke="#000" if grey else colr, sw=1.4)
            if w > 1:
                svg.text(xx + w * TE / 2, yy + 18, name, 10, anchor="middle")
            else:
                svg.text(xx + TE / 2 + 3, yy + 26, name.split()[0], 9, rot=-90)
            xx += w * TE
    tx = 560
    notes = [f"{len(CIRCS)} Stromkreise an {len(rcds)} RCD · {len(rows)} Reihen à 12 TE im Verteilerfeld",
             "Phasenaufteilung abgeleitet: Wechselstromkreise der Reihe nach auf L1, L2, L3 (ohne Lastangaben).",
             "Zähler, SLS und SPD stehen als Felder an b1 (meters, main, spd). HAK, Hauptleitung, Steuerbox nach §14a EnWG",
             "und ein eigener WP-Zähler sind nicht modelliert.",
             "Leitungslängen, Spannungsfall und Abschaltbedingung: Rechner noch nicht vorhanden; Kabel sind Platzhalter."]
    for i_, t_ in enumerate(notes):
        svg.text(tx, by + 10 + i_ * 18, t_, 11, fill="#333")
    plankopf(svg, "Verteilungsplan b1 (Übersichtsschaltplan, Belegung)")
    svg.save("verteilung-b1.svg")


# ---------------------------------------------------------------- Heizungsschema
LOOP_M2 = 13.5  # assumption: VA 15 cm, about 100 m per loop incl. Anbindung


def heat_area(r):
    a = r["a_fertig"]
    for s in stairs.values():
        sa = (s["x"][1] - s["x"][0]) * (s["y"][1] - s["y"][0])
        if r["level"] == s["level"] and r["x"][0] <= s["x"][0] <= r["x"][1] and r["y"][0] <= s["y"][0] <= r["y"][1]:
            a -= sa  # no floor heating under the stair
        if r["level"] == "OG" and r["x"][0] <= s["x"][0] <= r["x"][1] and r["y"][0] <= s["y"][0] <= r["y"][1]:
            a -= sa  # stair hole
    return a


def heizungsschema():
    svg = Svg(1640, 1060)
    svg.text(20, 30, "Heizungs- und Trinkwasserschema (Prinzip)", 18, weight="bold")
    RED, BLUE, WW, KW = "#d62728", "#1f77b4", "#ff7f0e", "#2ca02c"
    # heat pump outside
    svg.rect(30, 150, 170, 110, fill="#f4f4f4", sw=1.4)
    g1 = els["g1"]
    svg.text(115, 175, "g1 Wärmepumpe", 12, anchor="middle", weight="bold")
    svg.text(115, 192, "Luft/Wasser, außen", 10, anchor="middle")
    svg.text(115, 208, f"Typ {g1['kv']['typ']} (Platzhalter)", 9, anchor="middle", fill="#666")
    svg.circle(115, 235, 16)
    svg.line(103, 235, 127, 235)
    svg.text(115, 278, "Einspeisung fd1 c7 (3-polig)", 9, anchor="middle", fill="#666")
    svg.line(240, 90, 240, 560, stroke="#888", sw=6, opacity="0.5")
    svg.text(248, 104, "Außenwand w4", 9, fill="#666")
    # indoor unit
    t1 = els["t1"]
    svg.rect(290, 110, 330, 440, fill="#fafafa", sw=1.4)
    svg.text(455, 132, f"t1 Inneneinheit {t1['kv']['typ']} (HWR r3)", 12, anchor="middle", weight="bold")
    svg.text(455, 147, "innerer Aufbau aus dem Typ, Platzhalter", 9, anchor="middle", fill="#666")
    # primary lines g1 -> t1
    svg.line(200, 180, 360, 180, stroke=RED, sw=3)
    svg.line(200, 230, 360, 230, stroke=BLUE, sw=3)
    svg.text(215, 172, "VL", 10, fill=RED)
    svg.text(215, 248, "RL", 10, fill=BLUE)
    # pump and 3-way valve
    svg.circle(380, 180, 14, fill="white", stroke=RED, sw=2)
    svg.poly([(373, 172), (373, 188), (389, 180)], fill=RED)
    svg.text(380, 206, "Pumpe", 8, anchor="middle")
    svg.line(394, 180, 440, 180, stroke=RED, sw=3)
    svg.poly([(440, 170), (440, 190), (460, 180)], fill="white", stroke="#000")
    svg.poly([(480, 170), (480, 190), (460, 180)], fill="white", stroke="#000")
    svg.poly([(450, 200), (470, 200), (460, 180)], fill="white", stroke="#000")
    svg.text(460, 160, "Umschaltventil", 8, anchor="middle")
    svg.line(480, 180, 640, 180, stroke=RED, sw=3)
    svg.line(360, 230, 640, 230, stroke=BLUE, sw=3)
    svg.line(460, 200, 460, 330, stroke=RED, sw=3)
    # storage
    svg.rect(400, 330, 160, 190, fill="#fff", sw=1.4, rx="30")
    svg.text(480, 360, "TWW-Speicher 200 l", 11, anchor="middle", weight="bold")
    svg.path("M460,330 L460,390 L500,400 L460,410 L500,420 L460,430 L500,440 L460,450 L460,470 L380,470 L380,230",
             stroke=BLUE, sw=2)
    svg.line(540, 345, 590, 345, stroke=WW, sw=3)
    svg.text(560, 337, "WW", 10, fill=WW)
    svg.text(395, 497, "KW", 10, fill=KW)
    # manifolds
    mans = {"OG": "hv2", "EG": "hv1"}
    ys = {"OG": 140, "EG": 410}
    svg.line(640, 180, 640, ys["EG"] + 40, stroke=RED, sw=3)
    svg.line(660, 230, 660, ys["EG"] + 70, stroke=BLUE, sw=3)
    svg.line(640, 180, 640, ys["OG"] + 40, stroke=RED, sw=3)
    svg.line(660, 230, 660, ys["OG"] + 70, stroke=BLUE, sw=3)
    summary = []
    for lv, hv in mans.items():
        y = ys[lv]
        loops = []
        for k in order:
            e = els[k]
            if e["kind"] == "ufh" and e["pos"][1] == hv:
                r = rooms[e["pos"][0]]
                a = heat_area(r)
                n = max(1, math.ceil(a / LOOP_M2))
                loops += [(k, r, a, i + 1, n) for i in range(n)]
        x0 = 700
        x1 = x0 + len(loops) * 72
        svg.line(640, y + 40, x1, y + 40, stroke=RED, sw=4)
        svg.line(660, y + 70, x1, y + 70, stroke=BLUE, sw=4)
        niche = els[hv]["pos"][0]
        host = els[niche]["pos"][0]
        wsize = float(els[niche]["pos"][1].split("x")[0])
        svg.text(x0, y + 22, f"{lv}: {hv} Heizkreisverteiler in Nische {niche} ({host}, {de(wsize)} m breit) · {len(loops)} Abgänge",
                 12, weight="bold")
        summary.append((hv, len(loops), wsize))
        for i, (k, r, a, j, n) in enumerate(loops):
            cx = x0 + 36 + i * 72
            svg.line(cx - 8, y + 40, cx - 8, y + 120, stroke=RED, sw=1.6)
            svg.line(cx + 8, y + 70, cx + 8, y + 120, stroke=BLUE, sw=1.6)
            pts = [(cx - 8, y + 120)]
            for s_ in range(5):
                yy = y + 124 + s_ * 12
                pts += [(cx - 22, yy), (cx + 22, yy + 6)]
            pts += [(cx + 8, y + 190), (cx + 8, y + 120)]
            svg.pline(pts, stroke="#c0504d", sw=1.2)
            svg.text(cx, y + 206, f"{k} {r['id']}", 9, anchor="middle", weight="bold")
            svg.text(cx, y + 218, r["name"][:12], 9, anchor="middle")
            svg.text(cx, y + 230, f"Kreis {j}/{n}", 8, anchor="middle", fill="#555")
            if j == 1:
                svg.text(cx, y + 242, f"{de(a, 1)} m²", 8, anchor="middle", fill="#555")
    # drinking water
    fy = 700
    svg.text(700, fy - 20, "Trinkwasser-Entnahmestellen (plumb)", 12, weight="bold")
    svg.line(590, 345, 590, fy, stroke=WW, sw=3)
    svg.rect(20, fy + 10, 200, 46, fill="#f4f4f4")
    svg.text(120, fy + 30, "Hausanschluss Trinkwasser", 10, anchor="middle")
    svg.text(120, fy + 44, "(nicht im Modell)", 9, anchor="middle", fill="#666")
    svg.line(220, fy + 40, 720, fy + 40, stroke=KW, sw=3)
    svg.line(380, fy + 40, 380, 505, stroke=KW, sw=3)
    svg.line(380, 505, 400, 505, stroke=KW, sw=3)
    fixtures = [k for k in order if els[k]["kind"] == "san"]
    hot = {"sink", "basin", "shower"}
    xe = 700 + len(fixtures) * 110
    svg.line(590, fy, xe, fy, stroke=WW, sw=3)
    svg.line(220, fy + 40, xe, fy + 40, stroke=KW, sw=3)
    names = {"sink": "Spüle", "basin": "Waschtisch", "shower": "Dusche", "wc": "WC", "wm": "Waschmaschine"}
    for i, k in enumerate(fixtures):
        e = els[k]
        cx = 770 + i * 110
        d = devices[k]
        if e["pos"][1] in hot:
            svg.line(cx - 10, fy, cx - 10, fy + 90, stroke=WW, sw=1.6)
        svg.line(cx + 10, fy + 40, cx + 10, fy + 90, stroke=KW, sw=1.6)
        svg.rect(cx - 40, fy + 90, 80, 46, fill="white")
        svg.text(cx, fy + 108, f"{k} {names[e['pos'][1]]}", 9, anchor="middle", weight="bold")
        svg.text(cx, fy + 122, f"{d['room']} {rooms[d['room']]['name'][:10]}", 9, anchor="middle")
    # legend and notes
    ly = 880
    for i, (c_, t_) in enumerate([(RED, "Heizung Vorlauf"), (BLUE, "Heizung Rücklauf"), (WW, "Trinkwasser warm"), (KW, "Trinkwasser kalt")]):
        svg.line(30, ly + i * 18, 70, ly + i * 18, stroke=c_, sw=3)
        svg.text(78, ly + 4 + i * 18, t_, 10)
    notes = [f"Kreise je Raum abgeleitet aus der Fläche (Annahme: Verlegeabstand 15 cm, höchstens {de(LOOP_M2, 1)} m² je Kreis);",
             "Treppe und Treppenloch abgezogen. Heizlast, Vorlauftemperatur und Massenströme: Rechner noch nicht vorhanden.",
             ] + [f"{hv}: {n} Abgänge in einer {de(w)} m breiten Nische – Verteilerschrank gegen Herstellerdaten prüfen." for hv, n, w in summary] + [
             "Sicherheitsgruppe, Ausdehnungsgefäß, Zirkulation und Leitungsführung sind nicht modelliert."]
    for i, t_ in enumerate(notes):
        svg.text(260, ly + 4 + i * 17, t_, 11, fill="#333")
    plankopf(svg, "Heizungs- und Trinkwasserschema")
    svg.save("heizungsschema.svg")


# ---------------------------------------------------------------- Lichtberechnung
def licht():
    rid = "r2"
    r = rooms[rid]
    b = r["bounds"]
    x0, x1 = r["x"][0] + finish(b["w"], "hi"), r["x"][1] - finish(b["e"], "lo")
    y0, y1 = r["y"][0] + finish(b["s"], "hi"), r["y"][1] - finish(b["n"], "lo")
    lz, fb = levels[r["level"]]
    slab = [k for k in order if els[k]["kind"] == "slab" and els[k]["pos"][0] == "OG"][0]
    up_z, up_fb = levels["OG"]
    hc = (up_z - up_fb) - sum(l[1] for l in layers(els[slab]["pos"][1])) - lz
    il = [k for k in order if els[k]["kind"] == "illum" and els[k]["pos"][0] == rid]
    H = float(els[il[0]]["kv"]["h"])
    MF = 0.8
    RHO = {"Decke": 0.7, "Wände": 0.5, "Boden": 0.3}
    lums = [k for k in order if els[k]["kind"] == "lum" and devices[k]["room"] == rid]

    def lum_data(k):
        e = els[k]
        t = els[e["kv"]["typ"]]
        flux = float(t["kv"]["flux"])
        n = int(t["kv"]["dist"].replace("cos", ""))
        zl = float(e["kv"].get("z", hc))
        return dict(id=k, x=devices[k]["x"], y=devices[k]["y"], z=zl, flux=flux, n=n, I0=flux * (n + 1) / (2 * math.pi), typ=e["kv"]["typ"])

    A_floor = (x1 - x0) * (y1 - y0)
    A_walls = 2 * ((x1 - x0) + (y1 - y0)) * hc
    A_tot = 2 * A_floor + A_walls
    rho = (A_floor * RHO["Decke"] + A_floor * RHO["Boden"] + A_walls * RHO["Wände"]) / A_tot
    step = 0.25
    nx, ny = round((x1 - x0) / step), round((y1 - y0) / step)
    gx = [x0 + (i + 0.5) * (x1 - x0) / nx for i in range(nx)]
    gy = [y0 + (j + 0.5) * (y1 - y0) / ny for j in range(ny)]

    def calc(ids):
        L = [lum_data(k) for k in ids]
        flux = sum(l["flux"] for l in L)
        grid = []
        for y in gy:
            row = []
            for x in gx:
                e = 0.0
                for l in L:
                    h = l["z"] - H
                    if h <= 0:
                        continue
                    d2 = (x - l["x"]) ** 2 + (y - l["y"]) ** 2 + h * h
                    cg = h / math.sqrt(d2)
                    e += MF * l["I0"] * cg ** (l["n"] + 1) / d2
                row.append(e)
            grid.append(row)
        cell = (x1 - x0) / nx * (y1 - y0) / ny
        f_dir = sum(sum(row) for row in grid) * cell          # maintained flux reaching the work plane directly
        f_rest = MF * flux - f_dir                             # the rest hits the walls first
        e_ind = (f_dir * RHO["Boden"] + f_rest * RHO["Wände"]) / (A_tot * (1 - rho))
        grid = [[e + e_ind for e in row] for row in grid]
        return L, flux, e_ind, grid

    def stats(grid, sel):
        v = [grid[j][i] for j, y in enumerate(gy) for i, x in enumerate(gx) if sel(x, y)]
        em = sum(v) / len(v)
        return dict(em=em, emin=min(v), emax=max(v), u0=min(v) / em, n=len(v))

    t2 = els[il[1]]
    tx, ty = at(t2["kv"]["at"])
    tw, th = (float(v) for v in t2["kv"]["area"].split("x"))
    zones = {
        il[0]: (lambda x, y: x0 + 0.5 <= x <= x1 - 0.5 and y0 + 0.5 <= y <= y1 - 0.5, float(els[il[0]]["kv"]["em"]), "Raum ohne 0,5-m-Randzone"),
        il[1]: (lambda x, y: abs(x - tx) <= tw / 2 and abs(y - ty) <= th / 2, float(t2["kv"]["em"]), f"Esstisch {de(tw)} × {de(th)} m"),
    }
    base = [k for k in lums if not els[k]["kv"]["typ"].startswith("DL")]
    variants = {"A": base, "B": lums}
    res = {v: calc(ids) for v, ids in variants.items()}
    st = {v: {z: stats(res[v][3], zones[z][0]) for z in zones} for v in variants}

    # false colour plot
    S = 70
    PW = (x1 - x0) * S
    svg = Svg(2 * PW + 260, (y1 - y0) * S + 280)
    svg.text(20, 28, f"Lichtberechnung {rid} {r['name']} – Beleuchtungsstärke auf {de(H)} m, Verfahren custom (nicht normkonform)", 16, weight="bold")
    stops = [(0, (40, 40, 120)), (50, (40, 110, 200)), (100, (60, 180, 120)), (200, (240, 220, 60)), (400, (240, 120, 40)), (800, (200, 30, 30))]

    def colour(e):
        for (a, ca), (b_, cb) in zip(stops, stops[1:]):
            if e <= b_:
                f = (e - a) / (b_ - a)
                return "#%02x%02x%02x" % tuple(int(ca[i] + f * (cb[i] - ca[i])) for i in range(3))
        return "#%02x%02x%02x" % stops[-1][1]

    for vi, v in enumerate(variants):
        ox, oy = 30 + vi * (PW + 60), 70
        X = lambda x: ox + (x - x0) * S
        Y = lambda y: oy + (y1 - y) * S
        L, flux, e_ind, grid = res[v]
        svg.text(ox, oy - 12, f"Variante {v}: {', '.join(l['id'] for l in L)} · {de(flux, 0)} lm", 12, weight="bold")
        for j, y in enumerate(gy):
            for i, x in enumerate(gx):
                svg.rect(X(x - step / 2), Y(y + step / 2), step * S + 0.5, step * S + 0.5, fill=colour(grid[j][i]), stroke="none")
        for j, y in enumerate(gy):
            for i, x in enumerate(gx):
                if i % 2 == 1 and j % 2 == 1:
                    svg.text(X(x), Y(y) + 3, f"{grid[j][i]:.0f}", 8, anchor="middle", fill="#000")
        svg.rect(X(x0), Y(y1), PW, (y1 - y0) * S, stroke="#000", sw=1.5)
        svg.rect(X(x0 + 0.5), Y(y1 - 0.5), PW - S, (y1 - y0 - 1) * S, stroke="#fff", sw=1, stroke_dasharray="5 4")
        svg.rect(X(tx - tw / 2), Y(ty + th / 2), tw * S, th * S, stroke="#fff", sw=2)
        for l in L:
            svg.circle(X(l["x"]), Y(l["y"]), 7, fill="white", stroke="#000", sw=1.5)
            svg.text(X(l["x"]) + 9, Y(l["y"]) - 6, l["id"], 10, weight="bold", fill="#fff")
        svg.text(ox, Y(y0) + 22, "Westen: offen zur Küche (Raumtrennung rs1) · Norden: w5 · Süden: w1 · Osten: w2", 9, fill="#444")
        ry = Y(y0) + 44
        for z, (sel, target, name) in zones.items():
            s_ = st[v][z]
            ok = "erfüllt" if s_["em"] >= target else "nicht erfüllt"
            svg.text(ox, ry, f"{z} {name}: Em {s_['em']:.0f} lx (Ziel {target:.0f}) {ok} · Emin {s_['emin']:.0f} · U0 {de(s_['u0'])}", 11)
            ry += 16
    lx = 30 + 2 * (PW + 60) - 30
    for i, (e, _) in enumerate(stops):
        svg.rect(lx, 80 + i * 26, 22, 22, fill=colour(e))
        svg.text(lx + 28, 96 + i * 26, f"{e} lx", 10)
    plankopf(svg, f"Lichtberechnung {rid} {r['name']}", note="Rechenverfahren custom")
    svg.save("lichtberechnung-r2.svg")

    # report
    t = []
    t.append(f"# Lichtberechnung {rid} {r['name']}\n")
    t.append("> **Rechenverfahren: `custom`, nicht normkonform.** Ein Prototyp, um zu zeigen, wie ein Rechenergebnis aus dem Modell aussieht. "
             "Die Lichtstärkeverteilungen sind Platzhalter (cosⁿ), keine Herstellerdaten (LDT). Für Wohnräume gibt es keine verbindlichen Mindestwerte; "
             "die Ziele sind Planungsannahmen aus `light.uea` (il1, il2).\n")
    t.append("| | |\n|---|---|")
    t.append(f"| Rechner | `light-point` 0.0.1, Kind `custom` |\n| Modellstand | `{STATE}` |\n| Datum | {DATE} |")
    t.append(f"| Raum | {rid} {r['name']}, {r['level']}, Fertigmaß {de(x1 - x0, 3)} × {de(y1 - y0, 3)} m = {de(A_floor)} m², lichte Höhe {de(hc, 3)} m |")
    t.append(f"| Nutzebene | {de(H)} m über OKFF, Raster {de(step)} m ({nx} × {ny} Punkte) |")
    t.append(f"| Wartungsfaktor | {de(MF)} |")
    t.append(f"| Reflexionsgrade (Annahme) | Decke {de(RHO['Decke'], 1)}, Wände {de(RHO['Wände'], 1)}, Boden {de(RHO['Boden'], 1)}; Mittel {de(rho)} |")
    t.append("\n## Verfahren\n")
    t.append("Direktanteil Punkt für Punkt: E = MF · I₀ · cos^(n+1) γ / d², mit I₀ = Φ (n+1) / 2π für eine nach unten strahlende cosⁿ-Verteilung. "
             "Indirektanteil gleichmäßig über den Raum: der direkt auf die Nutzebene fallende Lichtstrom wird mit dem Boden-, der Rest mit dem Wand-Reflexionsgrad "
             "einmal reflektiert und dann gemittelt verteilt: E_ind = (Φ_dir · ρ_Boden + Φ_rest · ρ_Wand) / (A · (1 − ρ)), A = alle Raumflächen. "
             "Die offene Seite zur Küche wird wie eine Wand behandelt; Licht aus der Küche (l1) zählt nicht.\n")
    t.append("## Leuchten\n")
    t.append("| Leuchte | Typ | Lichtstrom | Verteilung | Position x / y | Lichtpunkthöhe |\n|---|---|---|---|---|---|")
    for k in lums:
        l = lum_data(k)
        t.append(f"| {k} | {l['typ']} | {l['flux']:.0f} lm | cos{l['n']} | {de(l['x'], 3)} / {de(l['y'], 3)} | {de(l['z'], 3)} m |")
    t.append("\n## Ergebnisse\n")
    t.append("| Variante | Leuchten | Zone | Em | Emin | Emax | U0 | Ziel | |\n|---|---|---|---|---|---|---|---|---|")
    for v in variants:
        for z, (sel, target, name) in zones.items():
            s_ = st[v][z]
            t.append(f"| {v} | {', '.join(variants[v])} | {z} {name} | {s_['em']:.0f} lx | {s_['emin']:.0f} lx | {s_['emax']:.0f} lx | {de(s_['u0'])} | {target:.0f} lx | "
                     f"{'erfüllt' if s_['em'] >= target else '**nicht erfüllt**'} |")
    t.append(f"\nIndirektanteil: Variante A {res['A'][2]:.0f} lx, Variante B {res['B'][2]:.0f} lx.\n")
    t.append("## Entscheidung\n")
    t.append("Variante A (nur Pendel- und Deckenleuchte) verfehlt die Annahme für die Allgemeinbeleuchtung. Der Agent hat deshalb vier Downlights "
             "(l17–l20, gedimmt über sw18) ergänzt und die Rechnung wiederholt: Variante B ist der Stand im Modell. Die Downlights brauchen "
             "Einbaugehäuse in der Betondecke sl2; dafür steht die Anfrage q6 an die Architektur.\n")
    t.append("![Falschfarbendarstellung](lichtberechnung-r2.png)\n")
    (OUT / "lichtberechnung-r2.md").write_text("\n".join(t), encoding="utf-8")
    return st


ansichten()
installationsplan("EG")
installationsplan("OG")
verteilung()
heizungsschema()
st = licht()
print("first", round(FIRST, 3), "traufe", round(TRAUFE, 3), "uk eave", round(uk(-EAVE), 3))
for v, zs in st.items():
    for z, s_ in zs.items():
        print(v, z, {k: round(x, 2) for k, x in s_.items()})
print("written:", sorted(p.name for p in OUT.iterdir()))

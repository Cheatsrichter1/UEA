"""The site plan (Lageplan) of the plot (decision 0057): `uea export pdf site`.

It draws the plot with the length of each edge and the streets on it, the building's footprint
with its number of Vollgeschosse in Roman numerals, and the Abstandsflächen. The footprint is
the union of the storeys above the terrain, as for the GR (`baunvo`); the Abstandsflächen and
the Vollgeschosse are those of the results of `uea calc setback` and `uea calc baunvo`, drawn
only while the model is as they computed it, so the sheet never shows what it calculated itself.
"""

import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon

from uea.derive import Derived
from uea.export.drawing import Drawing, Poly, Pt
from uea.export.paper import (
    BLACK,
    GREY,
    L_DIM,
    L_TEXT,
    Chain,
    Paper,
    Stand,
    dim_text,
    fit_sheet,
    poly_item,
)
from uea.export.report import stale
from uea.geom import polys, union
from uea.packs.site.kinds import streets

L_PLOT = "A-GRUNDSTUECK"
L_BUILDING = "A-GEBAEUDE"
L_SETBACK = "A-ABSTANDSFLAECHE"
SITE_LAYER_COLORS = {L_PLOT: "#000000", L_BUILDING: "#000000", L_SETBACK: "#2f6fde"}
FITS = (("A3", 200), ("A3", 500), ("A2", 500), ("A1", 500), ("A1", 1000), ("A0", 1000))
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")


def _fresh(out: Path, stem: str, hashes: dict[str, str]) -> dict[str, Any] | None:
    path = out / f"{stem}.json"
    if not path.exists():
        return None
    rec: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return None if stale(rec, hashes) else rec


def footprint(d: Derived, terrain: float) -> Polygon | None:
    from uea.packs.site.baunvo import storey_outline

    g = d.arch
    keep = [
        storey_outline(g, k)
        for k in g.level_order()
        if g.levels[k].above is None or g.levels[g.levels[k].above or ""].ssl - terrain > 1e-9
    ]
    shape = union(keep)
    found = polys(shape)
    return max(found, key=lambda p: p.area) if found else None


class SitePlan(Paper):
    def __init__(self, d: Derived, stand: Stand, out: Path, hashes: dict[str, str]) -> None:
        super().__init__(d, stand, "Lageplan")
        self.setback = _fresh(out, "setback", hashes)
        self.baunvo = _fresh(out, "baunvo", hashes)

    def draw(self) -> Drawing | None:
        pg = self.d.site.plot
        if pg is None:
            return None
        pl = self.m[pg.id]
        proj = self.m.of_kind("project")
        terrain = getattr(proj[0], "ground", None) if proj else None
        foot = footprint(self.d, terrain or 0.0)
        areas = (
            [Polygon(f["area"]) for f in self.setback["data"]["faces"] if len(f["area"]) >= 3]
            if self.setback
            else []
        )
        extent = union([pg.poly, *([foot] if foot else []), *areas]).bounds
        need = {"S": 26.0, "N": 14.0, "W": 26.0, "E": 14.0}
        self.dw.sheet = fit_sheet(extent, need, extra=self.north_room, fits=FITS)
        sh = self.sh
        for a in areas:
            self.dw.add(poly_item(a, "#dbe6fb", self.pen(0.18, "#2f6fde", (2.0, 1.0)), L_SETBACK))
        self.dw.add(poly_item(pg.poly, None, self.pen(0.5, BLACK, (6.0, 1.5, 1.0, 1.5)), L_PLOT))
        self._edges(pg.poly, streets(getattr(pl, "street", None)))
        if foot is not None:
            self.dw.add(poly_item(foot, "#9a9a9a", self.pen(0.5), L_BUILDING))
            c = foot.representative_point()
            n = self.baunvo["data"]["full"] if self.baunvo else None
            if isinstance(n, int) and 1 <= n <= len(ROMAN):
                self.text((c.x, c.y - sh.m(1.8)), ROMAN[n - 1], 5.0, L_TEXT, bold=True)
            x0, y0, x1, y1 = foot.bounds
            self.dimension(
                (x0, y0, x1, y1),
                {"S": [Chain("total", [x0, x1])], "W": [Chain("total", [y0, y1])]},
            )
        self._legend(pg.area)
        label = getattr(pl, "label", None) or pg.id
        self.title_block("Lageplan", f"Grundstück {label}", "L-01")
        self.north_arrow()
        return self.dw

    def _edges(self, poly: Polygon, street: dict[int, float]) -> None:
        """The length of each edge outside it, and the streets along theirs."""
        sh = self.sh
        pts: list[Pt] = [(float(x), float(y)) for x, y, *_ in poly.exterior.coords][:-1]
        ccw = poly.exterior.is_ccw
        for i, (a, b) in enumerate(zip(pts, [*pts[1:], pts[0]], strict=True), 1):
            length = math.dist(a, b)
            if length < 0.01:
                continue
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            nx, ny = (uy, -ux) if ccw else (-uy, ux)
            ang = math.degrees(math.atan2(uy, ux))
            if ang > 90 or ang <= -90:
                ang -= 180
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            off = sh.m(2.5)
            at: Pt = (mx + nx * off, my + ny * off)
            self.text(at, dim_text(length), 2.5, L_DIM, rot=ang)
            if i in street:
                w = street[i]
                band = [
                    a,
                    b,
                    (b[0] + nx * w, b[1] + ny * w),
                    (a[0] + nx * w, a[1] + ny * w),
                ]
                self.dw.add(Poly(band, "#f0efe9", self.pen(0.18, GREY), L_PLOT))
                far = sh.m(2.5) + w / 2
                self.text(
                    (mx + nx * far, my + ny * far),
                    f"Straße ({dim_text(w)} m)",
                    2.5,
                    L_TEXT,
                    rot=ang,
                    color=GREY,
                )

    def _legend(self, area: float) -> None:
        sh = self.sh
        lines = [f"Grundstück {dim_text(area)} m²"]
        if self.baunvo:
            b = self.baunvo["data"]
            lines.append(f"GRZ {b['grz']:.2f}".replace(".", ","))
            if b.get("gfz") is not None:
                lines.append(f"GFZ {b['gfz']:.2f}".replace(".", ","))
        if self.setback:
            lines.append("Abstandsflächen: uea calc setback")
        else:
            lines.append("Abstandsflächen: nicht berechnet oder Modell geändert")
        for k, txt in enumerate(lines):
            self.text(sh.pt(30.0, sh.paper[1] - 18.0 - 5.0 * k), txt, 2.8, L_TEXT, anchor="start")


def sheet_site(d: Derived, stand: Stand, out: Path, hashes: dict[str, str]) -> Drawing | None:
    return SitePlan(d, stand, out, hashes).draw()

"""`uea compare <project>...`: the options on a plot side by side, for a human (decision 0057).

Each option is a project of its own (a folder). The comparison reads the results each one has
computed: `baunvo`, `setback`, `din277` and `costs`, and refuses a result its model has changed
since, as a calculation report does. It calculates nothing except a cost per m² BGF; a missing
result is a gap with the command that fills it. It writes `options.md` and `options.pdf`, in
German, a basis for the client's decision.
"""
# pyright: reportUnknownMemberType=false

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from uea.calc import de, md_table
from uea.export.report import rerun, stale
from uea.project import LoadError, NotAProject, Project

RESULTS = ("baunvo", "setback", "din277", "costs")
Fn = Callable[[dict[str, Any], dict[str, Any]], str]
"""A row's value from a result's data and inputs."""


def _eur(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _load(
    p: Project, where: str
) -> tuple[str, dict[str, dict[str, Any]], list[tuple[str, str, str]]]:
    """The option's title, its fresh results and what it lacks: (result, why, command)."""
    model = p.load()
    proj = model.of_kind("project")
    title = (proj[0].label or proj[0].id) if proj else p.root.name
    hashes = p.hashes()
    got: dict[str, dict[str, Any]] = {}
    lacks: list[tuple[str, str, str]] = []
    for name in RESULTS:
        path = p.out / f"{name}.json"
        if not path.exists():
            lacks.append((name, "missing", f"uea -C {where} calc {name}"))
            continue
        rec: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if stale(rec, hashes):
            lacks.append((name, "stale", f"uea -C {where} {rerun(rec)[4:]}"))
            continue
        got[name] = rec
    return title, got, lacks


def _cell(res: dict[str, dict[str, Any]], name: str, fn: Fn) -> str:
    rec = res.get(name)
    if rec is None:
        return "–"
    try:
        return fn(rec["data"], rec.get("inputs", {}))
    except (KeyError, TypeError, ValueError):
        return "–"


def _lim(v: float, limit: Any, places: int = 2) -> str:
    out = de(v, places)
    if isinstance(limit, int | float):
        out += f" ({de(float(limit), places)})"
        if v > float(limit) + 1e-9:
            out = f"**{out}**"
    return out


def table(options: list[tuple[str, dict[str, dict[str, Any]]]]) -> str:
    def lims(i: dict[str, Any]) -> dict[str, Any]:
        return i.get("limits", {})

    rows: list[list[str]] = []
    spec: list[tuple[str, str, Fn]] = [
        ("Grundstück m²", "baunvo", lambda d, i: de(d["area"])),
        ("Grundfläche GR m²", "baunvo", lambda d, i: de(d["gr"])),
        ("GRZ (zulässig)", "baunvo", lambda d, i: _lim(d["grz"], lims(i).get("grz"), 3)),
        (
            "Geschossfläche GF m²",
            "baunvo",
            lambda d, i: de(d["gf"]) if d["gf"] is not None else "–",
        ),
        (
            "GFZ (zulässig)",
            "baunvo",
            lambda d, i: _lim(d["gfz"], lims(i).get("gfz"), 3) if d["gfz"] is not None else "–",
        ),
        (
            "Vollgeschosse (zulässig)",
            "baunvo",
            lambda d, i: (
                _lim(d["full"], lims(i).get("storeys"), 0) if d["full"] is not None else "–"
            ),
        ),
        (
            "Abstandsflächen",
            "setback",
            lambda d, i: (
                "eingehalten" if not d["over"] else f"**{len(d['over'])} Fassaden außerhalb**"
            ),
        ),
        ("BGF m²", "din277", lambda d, i: de(d["total"]["bgf"])),
        ("NRF m²", "din277", lambda d, i: de(d["total"]["nrf"])),
        ("BRI m³", "din277", lambda d, i: de(d["total"]["bri"])),
        ("Kosten brutto €", "costs", lambda d, i: _eur(d["gross"])),
    ]
    for label, name, fn in spec:
        rows.append([label, *(_cell(res, name, fn) for _, res in options)])
    per: list[str] = ["Kosten brutto je m² BGF €"]
    for _, res in options:
        c, a = res.get("costs"), res.get("din277")
        if c and a and a["data"]["total"]["bgf"]:
            per.append(_eur(c["data"]["gross"] / a["data"]["total"]["bgf"]))
        else:
            per.append("–")
    rows.append(per)
    return md_table(["", *(t for t, _ in options)], rows, tuple(range(1, len(options) + 1)))


def compare(dirs: list[str]) -> tuple[str, list[str]]:
    """The comparison as Markdown, and the agent's lines on what is missing."""
    options: list[tuple[str, dict[str, dict[str, Any]]]] = []
    lacks: list[tuple[str, str, str, str]] = []
    for d in dirs:
        try:
            p = Project.find(Path(d))
            title, res, miss = _load(p, d)
        except (NotAProject, LoadError) as e:
            raise ValueError(f"{d}: {e}") from None
        options.append((title, res))
        lacks += [(title, *m) for m in miss]
    stages = {res["costs"]["data"].get("stage") for _, res in options if "costs" in res}
    stage = {"estimate": "Kostenschätzung", "calculation": "Kostenberechnung"}
    cost = ", ".join(stage.get(str(s), str(s)) for s in sorted(stages, key=str)) or "–"
    out = [
        "# Varianten im Vergleich",
        "",
        table(options),
        "",
        "Fett: über der zulässigen Grenze des Plans. In Klammern: was der Plan zulässt.",
        "",
        "## Grundlagen",
        "",
        "- Maß der baulichen Nutzung: uea calc baunvo (BauNVO, Vollgeschoss nach"
        " Landesbauordnung).",
        "- Abstandsflächen: uea calc setback (Landesbauordnung).",
        "- Flächen und Rauminhalte: uea calc din277 (DIN 277).",
        f"- Kosten: uea calc costs ({cost} nach DIN 276, Kennwerte des Büros).",
        "",
        "Jede Variante ist ein eigenes Projekt; die Werte sind die Ergebnisse dieser Berechnungen"
        " an ihrem Modellstand. Eine Entscheidungsgrundlage, keine Entscheidung; Prüfung und"
        " Verantwortung liegen bei der unterzeichnenden fachkundigen Person.",
        "",
    ]
    if lacks:
        why = {"missing": "fehlt", "stale": "veraltet, das Modell wurde seither geändert"}
        out += [
            "## Fehlende Ergebnisse",
            "",
            *(f"- {t}: {name} {why[w]}" for t, name, w, _ in lacks),
            "",
        ]
    lines = [f"{t}: {name} {w}: {cmd}" for t, name, w, cmd in lacks]
    return "\n".join(out), lines


def write_pdf(md: str, path: Path) -> int:
    """The comparison on A4 pages; returns how many."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    from uea import __version__
    from uea.export.report import Styles, flowables

    st = Styles()
    size = landscape(A4)
    left = 15 * mm
    pages = [0]

    def decorate(canvas: Any, doc: Any) -> None:
        pages[0] = doc.page
        canvas.saveState()
        canvas.setFont(st.font, 7)
        canvas.drawRightString(size[0] - left, size[1] - 10 * mm, "ENTWURF – nicht unterzeichnet")
        canvas.drawString(left, 8 * mm, f"Variantenvergleich · UEA {__version__}")
        canvas.drawRightString(size[0] - left, 8 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=size,
        leftMargin=left,
        rightMargin=left,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title="Varianten im Vergleich",
        author="UEA",
        creator=f"UEA {__version__}",
    )
    doc.build(flowables(md, st, size[0] - 2 * left), onFirstPage=decorate, onLaterPages=decorate)
    return pages[0]

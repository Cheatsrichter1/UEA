"""A calculation report as a PDF to sign (decision 0036): `uea export pdf heatload` sets the last
result of `uea calc heatload` (out/heatload.md with its record) on A4 pages with a header, page
numbers and an empty signature block. It refuses a result the model has changed since.

The report is the Markdown the calculator wrote: headings, paragraphs, lists and tables, with
**bold** and `code`. It needs a font with Greek letters (Φ, θ): DejaVu Sans, Liberation Sans,
Noto Sans or Arial, found where systems keep them; without one the Greek letters are spelled out
in Helvetica.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

import json
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from uea import __version__

FONTS = (
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
    ("arial.ttf", "arialbd.ttf"),
    ("Arial.ttf", "Arial Bold.ttf"),
)
FOLDERS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    str(Path.home() / ".fonts"),
    str(Path.home() / ".local/share/fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "C:/Windows/Fonts",
)
GREEK = {
    "Φ": "Phi",
    "θ": "theta",
    "ρ": "rho",
    "Σ": "Sum ",
    "λ": "lambda",
    "ζ": "zeta",
    "ε": "eps",
    "Δ": "Delta ",
    "√": "sqrt",
    "≤": "<=",
    "≥": ">=",
    "→": "->",
    "\u0307": "",
}


def _font() -> tuple[str, str]:
    """A regular and a bold font with Greek letters, registered; else Helvetica."""
    if "UEA-Report" in pdfmetrics.getRegisteredFontNames():
        return "UEA-Report", "UEA-Report-Bold"
    for regular, bold in FONTS:
        for folder in FOLDERS:
            hits = list(Path(folder).rglob(regular)) if Path(folder).is_dir() else []
            if hits:
                strong = list(hits[0].parent.glob(bold))
                pdfmetrics.registerFont(TTFont("UEA-Report", str(hits[0])))
                pdfmetrics.registerFont(TTFont("UEA-Report-Bold", str((strong or hits)[0])))
                return "UEA-Report", "UEA-Report-Bold"
    return "Helvetica", "Helvetica-Bold"


class Styles:
    def __init__(self) -> None:
        self.font, self.bold = _font()
        f, b = self.font, self.bold
        self.body = ParagraphStyle("body", fontName=f, fontSize=9, leading=12, spaceAfter=4)
        self.h1 = ParagraphStyle("h1", fontName=b, fontSize=15, leading=19, spaceAfter=8)
        self.h2 = ParagraphStyle("h2", fontName=b, fontSize=11.5, leading=15, spaceBefore=8,
                                 spaceAfter=4)  # fmt: skip
        self.h3 = ParagraphStyle("h3", fontName=b, fontSize=10, leading=13, spaceBefore=6)
        self.li = ParagraphStyle("li", parent=self.body, leftIndent=10, bulletIndent=2)
        self.cell = ParagraphStyle("cell", fontName=f, fontSize=7, leading=8.6)
        self.cell_r = ParagraphStyle("cellr", parent=self.cell, alignment=2)

    def inline(self, text: str) -> str:
        """Markdown bold and code as the markup of a paragraph."""
        if self.font == "Helvetica":
            for k, v in GREEK.items():
                text = text.replace(k, v)
        t = escape(text)
        t = re.sub(r"\*\*(.+?)\*\*", rf'<font name="{self.bold}">\1</font>', t)
        t = re.sub(r"`(.+?)`", r"\1", t)
        return t.replace("<br>", "<br/>").replace("&lt;br&gt;", "<br/>")


def flowables(md: str, st: Styles, width: float) -> list[Flowable]:
    out: list[Flowable] = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(Paragraph(st.inline(" ".join(para)), st.body))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|"):
            flush()
            rows: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows, st, width))
            out.append(Spacer(1, 4))
            continue
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            style = {1: st.h1, 2: st.h2}.get(level, st.h3)
            out.append(Paragraph(st.inline(line.lstrip("#").strip()), style))
        elif line.startswith("- "):
            flush()
            out.append(Paragraph(st.inline(line[2:]), st.li, bulletText="•"))
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
        i += 1
    flush()
    return out


def table(rows: list[str], st: Styles, width: float) -> Table:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    right: set[int] = set()
    body: list[list[str]] = []
    for r in cells:
        if all(re.fullmatch(r":?-{3,}:?", c) for c in r if c):
            right = {k for k, c in enumerate(r) if c.endswith(":")}
            continue
        body.append(r)
    n = max(len(r) for r in body)
    weight: list[float] = []
    for k in range(n):
        col = [r[k] for r in body if k < len(r)]
        word = max((len(w) for c in col for w in c.split()), default=1)
        weight.append(max(word + 1.0, 0.6 * min(max(map(len, col), default=1), 40)))
    total = sum(weight)
    widths = [width * w / total for w in weight]
    data = [
        [
            Paragraph(st.inline(r[k]) if k < len(r) else "", st.cell_r if k in right else st.cell)
            for k in range(n)
        ]
        for r in body
    ]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    return t


def signature(st: Styles, width: float) -> Flowable:
    head = Paragraph(
        st.inline(
            "**Aufgestellt und geprüft** (nicht durch UEA: UEA rechnet, ein Mensch zeichnet)"
        ),
        st.body,
    )
    cells = [["Name, Qualifikation", "Ort, Datum", "Unterschrift"], ["", "", ""]]
    t = Table(cells, colWidths=[width / 3] * 3, rowHeights=[12, 22 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), st.font),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#666666")),
            ]
        )
    )
    return KeepTogether([Spacer(1, 10), head, Spacer(1, 4), t])


def stale(record: dict[str, Any], hashes: dict[str, str]) -> bool:
    """Whether the model has changed since the result was computed."""
    return record.get("state", {}).get("files") != hashes


def rerun(record: dict[str, Any]) -> str:
    """The command that computes the result again."""
    settings = record.get("inputs", {}).get("settings", {})
    parts = ["uea calc", str(record.get("calculator", ""))]
    if record.get("scope"):
        parts.append(str(record["scope"]))
    parts += [f"{k}={v}" for k, v in settings.items() if v is not None]
    return " ".join(parts)


def write_report(md: str, record: dict[str, Any], project: str, path: Path) -> int:
    """The report as A4 pages; returns how many."""
    st = Styles()
    left = right = 18 * mm
    width = A4[0] - left - right
    batch = record.get("state", {}).get("batch")
    head = (
        f"{project} · {record.get('calculator')} {record.get('version')} ({record.get('kind')})"
        f" · Batch {batch if batch is not None else '–'}"
    )
    pages = [0]

    def decorate(canvas: Any, doc: Any) -> None:
        pages[0] = doc.page
        canvas.saveState()
        canvas.setFont(st.font, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(left, A4[1] - 12 * mm, head)
        canvas.drawRightString(A4[0] - right, A4[1] - 12 * mm, "ENTWURF – nicht unterzeichnet")
        canvas.drawString(left, 10 * mm, f"UEA {__version__} · aus dem Modell berechnet")
        canvas.drawRightString(A4[0] - right, 10 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=md.splitlines()[0] if md else "Bericht",
        author="UEA",
        creator=f"UEA {__version__}",
    )
    story = [*flowables(md, st, width), signature(st, width)]
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return pages[0]


def export_report(
    out_dir: Path, stem: str, hashes: dict[str, str], project: str, path: Path | None
) -> str | tuple[Path, int]:
    """The PDF of out/<stem>.md, or why not."""
    record = json.loads((out_dir / f"{stem}.json").read_text(encoding="utf-8"))
    md_path = out_dir / f"{stem}.md"
    if not md_path.exists():
        return f"out/{stem}.md is missing: {rerun(record)}"
    if stale(record, hashes):
        batch = record.get("state", {}).get("batch")
        return (
            f"out/{stem}.json is from batch {batch}, and the model has changed since: run"
            f" {rerun(record)} again"
        )
    target = path or out_dir / f"{stem}.pdf"
    n = write_report(md_path.read_text(encoding="utf-8"), record, project, target)
    return target, n

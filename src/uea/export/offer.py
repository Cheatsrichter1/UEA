"""The fee offer (Honorarangebot) to sign: `uea export offer` (decision 0054).

It sets the fees of the `uea calc hoai` results in out/ into a German letter: the office's
letterhead, the client (`client=` on the project), one section per service with its phases and
fee, the sum with VAT, the office's terms and a signature block. Every number is the result's;
nothing is calculated here except the shares of the phases and the sums. The letterhead and the
terms are the office's own texts, installed like a norm table (`uea data add offer`). A result the
model has changed since is refused, as for a calculation report. The offer is a draft until the
office signs it; UEA sends nothing.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from uea import __version__
from uea.calc import data, de, md_table
from uea.calc.data import Col, Spec
from uea.calc.hoai import SERVICES
from uea.export.report import Styles, flowables, rerun, stale
from uea.fmt import ar

KEYS = ("office", "sender", "place", "intro", "terms", "closing", "signer")
OFFER = Spec(
    "offer",
    "Texts of the fee offer",
    "the office's own texts",
    (
        Col("key", "text", "which text", KEYS),
        Col("text", "text", "the text; | starts a new line"),
    ),
    ("key",),
    "The office's letterhead and terms for uea export offer. office: the letterhead (name|street"
    "|town|phone); sender: the return address above the client's, in one line; place: the town"
    " before the date; intro: the opening; terms: the terms of the offer, | between paragraphs;"
    " closing: the closing; signer: who signs (name, qualification). Only office is needed.",
)

INTRO = (
    "Sehr geehrte Damen und Herren,|vielen Dank für Ihre Anfrage. Für die Planungsleistungen"
    " am Projekt „{title}“ bieten wir Ihnen das folgende Honorar nach HOAI 2021 an."
)
CLOSING = "Mit freundlichen Grüßen"
PHASES_DE = (
    "Grundlagenermittlung",
    "Vorplanung",
    "Entwurfsplanung",
    "Genehmigungsplanung",
    "Ausführungsplanung",
    "Vorbereitung der Vergabe",
    "Mitwirkung bei der Vergabe",
    "Objektüberwachung und Dokumentation",
    "Objektbetreuung",
)
"""The service phases (Leistungsphasen) of § 34, § 51 and § 55 HOAI, in short."""


@dataclass
class Fee:
    stem: str
    record: dict[str, Any]

    @property
    def d(self) -> dict[str, Any]:
        return self.record["data"]


def eur(v: float) -> str:
    """An amount for the client: 1.234.567,89."""
    return f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _rate(rate: float) -> str:
    if rate == 0:
        return "Basishonorarsatz"
    if rate == 100:
        return "oberer Honorarsatz"
    return f"Honorarsatz {de(rate, 0)} % zwischen Basishonorarsatz und oberem Honorarsatz"


def _basis(how: Any) -> str:
    """Where the chargeable costs come from, as the hoai result records it."""
    if not isinstance(how, dict):
        return ""
    h: dict[str, Any] = how  # pyright: ignore[reportUnknownVariableType]
    src = {"estimate": "aus der Kostenschätzung", "calculation": "aus der Kostenberechnung"}
    parts = [src.get(str(h.get("from")), "vorgegeben")]
    if "kg300" in h:
        part = f"KG 300 {eur(h['kg300'])} € und KG 400 {eur(h['kg400'])} €"
        if h.get("half"):
            part += f", der Teil über 25 % zur Hälfte ({eur(h['half'])} €, § 33 Abs. 2)"
        parts.append(part)
    elif "kg" in h:
        parts.append(f"KG {h['kg']}, § 54")
    return "; ".join(parts)


def _lines(text: str) -> list[str]:
    return [x.strip() for x in text.split("|") if x.strip()]


def fees(out_dir: Path, scope: str | None) -> list[Fee] | str:
    """The hoai results the offer is made of: those scope names, else all in out/."""
    found: dict[str, Fee] = {}
    for p in sorted(out_dir.glob("hoai*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if rec.get("calculator") == "hoai" and rec.get("ok", True):
            found[p.stem] = Fee(p.stem, rec)
    if not found:
        return "no fee yet: uea calc hoai service=<s> zone=<z> ... (help calc)"
    if scope is None:
        return list(found.values())
    picked: list[Fee] = []
    for s in scope.split(","):
        f = found.get(s.strip())
        if f is None:
            return f"no fee result {s.strip()!r}. In out/: {' '.join(found)}"
        picked.append(f)
    return picked


def offer_md(
    title: str, client: str | None, fs: list[Fee], texts: dict[str, str], today: date
) -> tuple[str, list[str]]:
    """The offer as Markdown, and what it lacks."""
    lacks: list[str] = []
    out: list[str] = []
    office = _lines(texts.get("office", ""))
    if office:
        out += [f"**{office[0]}**<br>" + "<br>".join(office[1:]), ""]
    else:
        lacks.append("no letterhead: uea data add offer <file.csv> (key office)")
    if texts.get("sender"):
        out += [texts["sender"], ""]
    if client:
        out += ["<br>".join(_lines(client)), ""]
    else:
        lacks.append('no client: ~ <project> client="Name|Street|Town"')
    place = texts.get("place")
    when = today.strftime("%d.%m.%Y")
    out += [f"{place}, {when}" if place else when, "", f"# Honorarangebot: {title}", ""]
    for para in _lines(texts.get("intro", INTRO).replace("{title}", title)):
        out += [para, ""]
    sums: list[list[str]] = []
    net = vat = 0.0
    rates: set[float] = set()
    for n, f in enumerate(fs, 1):
        x = f.d
        service = str(x["service"])
        name, shares, clause = SERVICES[service]
        settings = f.record.get("inputs", {}).get("settings", {})
        groups = settings.get("groups")
        kgs = ", ".join(g.strip() for g in str(groups).split(",")) if groups else ""
        head = f"{name}, KG {kgs}" if groups else name
        basis = _basis(x.get("basis"))
        out += [
            f"## {n}. {head}",
            "",
            f"Honorarzone {x['zone']}, {_rate(float(x['rate']))}. Anrechenbare Kosten"
            f" {eur(float(x['chargeable']))} € netto" + (f" ({basis})." if basis else "."),
            "",
        ]
        full = float(x["full"])
        rows = [
            [
                f"LPH {p} {PHASES_DE[p - 1]}",
                f"{shares[p - 1]} %",
                eur(full * shares[p - 1] / 100),
            ]
            for p in x["phases"]
        ]
        rows.append(["Leistungsphasen zusammen", f"{de(float(x['share']), 0)} %", eur(x["fee"])])
        if x.get("conversion"):
            rows.append(["Umbauzuschlag (§ 36)", "", eur(x["conversion"])])
        if x.get("incidental"):
            rows.append(["Nebenkosten (§ 14)", "", eur(x["incidental"])])
        rows.append([f"**Honorar netto** ({clause})", "", f"**{eur(x['net'])}**"])
        out += [md_table(["Leistung", "Anteil", "Honorar €"], rows, (1, 2)), ""]
        sums.append([f"{n}. {head}", eur(x["net"])])
        net += float(x["net"])
        vat += float(x["vat"])
        rates.add(float(settings.get("ust", 19.0)))
    tax = f"Umsatzsteuer {de(rates.pop(), 0)} %" if len(rates) == 1 else "Umsatzsteuer"
    sums += [
        ["Summe netto", eur(net)],
        [tax, eur(vat)],
        ["**Summe brutto**", f"**{eur(net + vat)}**"],
    ]
    out += ["## Zusammenfassung", "", md_table(["Leistung", "Honorar €"], sums, (1,)), ""]
    terms = _lines(texts.get("terms", ""))
    if terms:
        out += ["## Bedingungen", "", *(f"{t}\n" for t in terms)]
    else:
        lacks.append("no terms: key terms in the table offer")
    batches = sorted({f.record.get("state", {}).get("batch") or 0 for f in fs})
    out += [
        "Grundlage: Honorarermittlungen nach HOAI 2021 aus dem Modell (Modellstand Batch"
        f" {', '.join(map(str, batches))}). Seit der HOAI 2021 sind die Tafelwerte"
        " Orientierungswerte; das Honorar wird vereinbart.",
        "",
        texts.get("closing", CLOSING),
        "",
    ]
    return "\n".join(out), lacks


def signature(st: Styles, signer: str | None) -> Flowable:
    lines: list[Flowable] = [
        Spacer(1, 16 * mm),
        Paragraph("_" * 40, st.body),
        Paragraph(st.inline(signer or "Name, Qualifikation"), st.body),
    ]
    return KeepTogether(lines)


def _sections(fl: list[Flowable], st: Styles) -> list[Flowable]:
    """Each section from its heading on kept on one page, so no sum stands alone."""
    out: list[Flowable] = []
    group: list[Flowable] = []
    for f in fl:
        if isinstance(f, Paragraph) and f.style is st.h2:
            if group:
                out.append(KeepTogether(group))
            group = [f]
        elif group:
            group.append(f)
        else:
            out.append(f)
    if group:
        out.append(KeepTogether(group))
    return out


def write_offer(md: str, project: str, signer: str | None, path: Path) -> int:
    """The offer as A4 pages; returns how many."""
    st = Styles()
    left = right = 22 * mm
    width = A4[0] - left - right
    pages = [0]

    def decorate(canvas: Any, doc: Any) -> None:
        pages[0] = doc.page
        canvas.saveState()
        canvas.setFont(st.font, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawRightString(A4[0] - right, A4[1] - 12 * mm, "ENTWURF – nicht unterzeichnet")
        canvas.drawString(left, 10 * mm, f"{project} · Honorarangebot · UEA {__version__}")
        canvas.drawRightString(A4[0] - right, 10 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=f"Honorarangebot: {project}",
        author="UEA",
        creator=f"UEA {__version__}",
    )
    doc.build(
        [*_sections(flowables(md, st, width), st), signature(st, signer)],
        onFirstPage=decorate,
        onLaterPages=decorate,
    )
    return pages[0]


def export_offer(
    out_dir: Path,
    scope: str | None,
    hashes: dict[str, str],
    title: str,
    client: str | None,
    path: Path | None,
) -> str | tuple[Path, int, list[str]]:
    """out/offer.md and the PDF with its pages and the agent's lines, or why not."""
    fs = fees(out_dir, scope)
    if isinstance(fs, str):
        return fs
    old = [f for f in fs if stale(f.record, hashes)]
    if old:
        return "the model has changed since: " + "; ".join(rerun(f.record) for f in old)
    table = data.load(OFFER)
    texts = {str(r["key"]): str(r["text"]) for r in table.rows} if table else {}
    md, lacks = offer_md(title, client, fs, texts, date.today())
    (out_dir / "offer.md").write_text(md, encoding="utf-8")
    target = path or out_dir / "offer.pdf"
    n = write_offer(md, title, texts.get("signer"), target)
    net = sum(float(f.d["net"]) for f in fs)
    return target, n, [f"{' '.join(f.stem for f in fs)} · net {ar(net)} €", *lacks]

"""The LV as GAEB DA XML 3.3, phase 83 (Angebotsaufforderung): what bidders receive (0048).

Titles become BoQ categories, positions items with quantity, unit, short and long text. Unit
prices are the office's estimate and are left out. The file follows the structure of the
GAEB DA XML schema; it has not been validated against the official schema in this repository.
"""

from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from uea import __version__
from uea.export.lv import Lv

NS = "http://www.gaeb.de/GAEB_DA_XML/DA83/3.3"


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrs)
    if text is not None:
        el.text = text
    return el


def _paragraphs(parent: ET.Element, tag: str, paras: list[str]) -> None:
    box = _sub(parent, tag)
    for p in paras:
        _sub(_sub(box, "p"), "span", p)


def gaeb_xml(lv: Lv, name: str, label: str, now: datetime | None = None) -> bytes:
    now = now or datetime.now(UTC)
    root = ET.Element("GAEB", {"xmlns": NS})
    info = _sub(root, "GAEBInfo")
    _sub(info, "Version", "3.3")
    _sub(info, "VersDate", "2021-05")
    _sub(info, "Date", now.strftime("%Y-%m-%d"))
    _sub(info, "Time", now.strftime("%H:%M:%S"))
    _sub(info, "ProgSystem", "UEA")
    _sub(info, "ProgName", f"UEA {__version__}")
    prj = _sub(root, "PrjInfo")
    _sub(prj, "NamePrj", name)
    _sub(prj, "LblPrj", label)
    _sub(prj, "Cur", "EUR")
    _sub(prj, "CurLbl", "Euro")
    award = _sub(root, "Award")
    _sub(award, "DP", "83")
    ainfo = _sub(award, "AwardInfo")
    _sub(ainfo, "Cur", "EUR")
    _sub(ainfo, "CurLbl", "Euro")
    boq = _sub(award, "BoQ", ID="UEA_LV")
    binfo = _sub(boq, "BoQInfo")
    _sub(binfo, "Name", "LV")
    _paragraphs(binfo, "LblTx", [f"Leistungsverzeichnis {label}"])
    title_len = max([2, *(len(t.oz) for t in lv.titles)])
    item_len = max([4, *(len(p.oz) for p in lv.positions)])
    for kind, n in (("BoQLevel", title_len), ("Item", item_len)):
        bk = _sub(binfo, "BoQBkdn")
        _sub(bk, "Type", kind)
        _sub(bk, "Length", str(n))
        _sub(bk, "Num", "Yes")
    body = _sub(boq, "BoQBody")
    for t in lv.titles:
        ctgy = _sub(body, "BoQCtgy", ID=f"UEA_{t.id}", RNoPart=t.oz.zfill(title_len))
        _paragraphs(ctgy, "LblTx", [t.text])
        items = _sub(_sub(ctgy, "BoQBody"), "Itemlist")
        for p in t.positions:
            item = _sub(items, "Item", ID=f"UEA_{p.id}", RNoPart=p.oz.zfill(item_len))
            _sub(item, "Qty", f"{p.qty:.3f}")
            _sub(item, "QU", p.unit)
            text = _sub(_sub(item, "Description"), "CompleteText")
            if p.long:
                _paragraphs(_sub(text, "DetailTxt"), "Text", p.long)
            _paragraphs(_sub(_sub(text, "OutlineText"), "OutlTxt"), "TextOutlTxt", [p.short])
    ET.indent(root, space=" ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_gaeb(lv: Lv, path: Path, name: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gaeb_xml(lv, name, label))

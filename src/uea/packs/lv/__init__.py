"""The LV pack: the Leistungsverzeichnis as titles and positions in the model (decision 0048)."""

from uea.core.registry import Pack
from uea.packs.lv.geometry import derive_lv, describe, lv_checks, lv_signatures
from uea.packs.lv.kinds import KINDS

CODES: dict[str, str] = {
    "E-LV-001": "position whose selector or measure cannot be used",
    "W-LV-002": "position that counts nothing",
    "W-LV-003": "element counted by two positions with the same measure",
    "E-LV-004": "two titles or positions with the same number",
    "W-LV-005": "selected elements the measure gives nothing for yet",
}

PACK = Pack(
    name="lv",
    title="Leistungsverzeichnis: titles and positions",
    kinds=KINDS,
    derive=derive_lv,
    checks=(lv_checks,),
    codes=CODES,
    signatures=lv_signatures,
    describe=describe,
)

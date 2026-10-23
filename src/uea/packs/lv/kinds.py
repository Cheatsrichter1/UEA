"""Kinds of the LV pack: titles and positions (docs/decisions/tender.md, 0048)."""

import re
from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Ref

Measure = Literal["n", "len", "area", "vol", "heat", "water", "drain", "duct"]
OZ_RE = re.compile(r"^\d{1,4}$")


class Title(Element):
    kind: ClassVar[str] = "title"
    pack: ClassVar[str] = "lv"
    doc: ClassVar[str] = (
        'A title of the LV (a trade or a part of one), named by you: title T01 "Mauerarbeiten".'
        " Titles are numbered 01, 02 in the order of their names; oz= pins a number once the LV"
        " went out."
    )
    oz: Annotated[str | None, F("pinned number, digits: 03")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.label:
            raise ValueError('a title needs its text as a quoted label: "Mauerarbeiten"')
        if self.oz is not None and not OZ_RE.match(self.oz):
            raise ValueError(f"oz={self.oz} must be 1 to 4 digits")
        return self


class Pos(Element):
    kind: ClassVar[str] = "pos"
    pack: ClassVar[str] = "lv"
    prefix: ClassVar[str | None] = "p"
    positional: ClassVar[tuple[str, ...]] = ("title",)
    doc: ClassVar[str] = (
        'A position of the LV: pos _ T01 area sel="wall type=AW-365" "Außenmauerwerk 36,5"'
        " kg=331. The label is its short text. measure and sel= say what code counts (uea help"
        " lv); or fix=<quantity> unit=<unit> for work no element carries: fix=1 unit=psch."
    )
    title: Annotated[Ref, F("title it belongs to", targets=("title",))]
    measure: Annotated[
        Measure | None,
        F("what it counts of each selected element, a bare word (uea help lv)", flag_enum=True),
    ] = None
    sel: Annotated[
        str | None, F('the elements it counts, as uea find takes them: sel="win level=OG"')
    ] = None
    fix: Annotated[float | None, F("a fixed quantity instead of a measure")] = None
    unit: Annotated[str | None, F("unit of a fixed quantity: psch, h, St, t")] = None
    text: Annotated[str | None, F("key of its long text in the office's table lv-texts")] = None
    ep: Annotated[float | None, F("unit price (Einheitspreis)", unit="€")] = None
    kg: Annotated[int | None, F("cost group per DIN 276, three digits: 331")] = None
    oz: Annotated[str | None, F("pinned number within its title, digits: 0010")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.label:
            raise ValueError('a position needs its short text as a quoted label: "Mauerwerk"')
        if self.fix is None:
            if self.measure is None or not self.sel:
                raise ValueError(
                    'give a measure and sel="<kind> <filters>", or fix=<quantity> unit=<unit>'
                )
            if self.unit is not None:
                raise ValueError("unit= is for fix=; a measure has its own unit")
        else:
            if self.measure is not None or self.sel is not None:
                raise ValueError("give either fix= or a measure with sel=, not both")
            if self.fix < 0:
                raise ValueError("fix must be 0 or more")
            if not self.unit:
                raise ValueError("fix= needs unit=<unit>: psch, h, St, t, ...")
        if self.ep is not None and self.ep < 0:
            raise ValueError("ep must be 0 or more")
        if self.kg is not None and not 100 <= self.kg <= 899:
            raise ValueError(f"kg={self.kg} is not a DIN 276 cost group (three digits, 100-899)")
        if self.oz is not None and not OZ_RE.match(self.oz):
            raise ValueError(f"oz={self.oz} must be 1 to 4 digits")
        return self


KINDS: tuple[type[Element], ...] = (Title, Pos)

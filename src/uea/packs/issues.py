"""Requests between disciplines and waivers (`issues.uea`).

See docs/decisions/0010-requests-in-the-model.md.
"""

import re
from typing import Annotated, ClassVar, Literal, Self

from pydantic import model_validator

from uea.core.registry import Pack
from uea.core.schema import Element, F
from uea.core.values import Ref, RefList

Discipline = Literal["arch", "struct", "light", "elec", "heat", "plumb", "vent"]
CODE_RE = re.compile(r"^[EW]-[A-Z]+-\d{3}$")


class Req(Element):
    kind: ClassVar[str] = "req"
    pack: ClassVar[str] = "issues"
    prefix: ClassVar[str | None] = "q"
    positional: ClassVar[tuple[str, ...]] = ("disc", "targets")
    doc: ClassVar[str] = (
        'A request from one discipline to the owner of its targets: req _ elec w7 "Schlitz'
        ' 10x5". Open until the owner sets done (~ q1 done) or rejected="reason".'
    )
    disc: Annotated[Discipline, F("discipline that asks")]
    targets: Annotated[RefList, F("elements the request is about")]
    done: Annotated[int | None, F("batch that resolved it")] = None
    rejected: Annotated[str | None, F("reason the owner rejected it")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.label:
            raise ValueError('a request needs its text as a quoted label: "Schlitz 10x5 cm"')
        if self.done is not None and self.rejected is not None:
            raise ValueError("a request is either done or rejected")
        return self

    @property
    def open(self) -> bool:
        return self.done is None and self.rejected is None


class Waive(Element):
    kind: ClassVar[str] = "waive"
    pack: ClassVar[str] = "issues"
    prefix: ClassVar[str | None] = "wv"
    positional: ClassVar[tuple[str, ...]] = ("code", "target")
    doc: ClassVar[str] = (
        'An issue accepted on purpose: waive _ W-ELEC-010 r5 "Wunsch Bauherr" by=elektroplaner.'
        " Reports list every waiver."
    )
    code: Annotated[str, F("issue code, e.g. W-ARCH-005")]
    target: Annotated[Ref, F("element the issue is on")]
    by: Annotated[str | None, F("who accepted it")] = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not CODE_RE.match(self.code):
            raise ValueError(f"{self.code!r} is not an issue code like W-ARCH-005")
        if not self.label:
            raise ValueError('a waiver needs its reason as a quoted label: "Wunsch Bauherr"')
        return self


PACK = Pack(name="issues", title="Requests and waivers", kinds=(Req, Waive))

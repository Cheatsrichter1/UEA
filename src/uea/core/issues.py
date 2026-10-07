"""Issues: what validation finds. Every issue names its element, the numbers and a fix."""

from dataclasses import dataclass
from typing import Literal

CORE_CODES: dict[str, str] = {
    "E-REF-001": "reference to an element that does not exist",
    "E-REF-002": "reference against the discipline graph (references only point upstream)",
    "E-REF-003": "reference to an element of the wrong kind",
    "E-GEO-001": "position cannot be resolved",
    "E-GEO-002": "depends on an element whose position cannot be resolved",
    "E-GEO-003": "positions refer to each other in a cycle",
    "W-ISSUE-001": "waiver that matches no issue",
}


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    el: str
    msg: str
    fix: str | None = None
    others: tuple[str, ...] = ()
    rule: str | None = None
    """Norm clause, only when the check really implements that clause."""

    @property
    def severity(self) -> Literal["error", "warning"]:
        return "error" if self.code.startswith("E") else "warning"

    @property
    def key(self) -> tuple[str, str, tuple[str, ...]]:
        return (self.code, self.el, self.others)

    def text(self) -> str:
        out = f"{self.code} {self.el} {self.msg}"
        if self.rule:
            out += f" [{self.rule}]"
        if self.fix:
            out += f". Fix: {self.fix}"
        return out

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "el": self.el,
            "msg": self.msg,
            "fix": self.fix,
            "others": list(self.others),
            "rule": self.rule,
        }

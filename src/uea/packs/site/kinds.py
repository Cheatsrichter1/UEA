"""Kinds of the site pack: the plot and the limits the plan sets on it (decision 0055)."""

from typing import Annotated, ClassVar, Self

from pydantic import model_validator

from uea.core.schema import Element, F
from uea.core.values import Points


class Plot(Element):
    kind: ClassVar[str] = "plot"
    pack: ClassVar[str] = "site"
    prefix: ClassVar[str | None] = "pl"
    doc: ClassVar[str] = (
        'The plot (Baugrundstück), one per project, and the limits its plan sets: plot _ "Flst.'
        ' 123/4" outline=W-3,S-5;E+4,S-5;E+4,N+6;W-3,N+6 grz=0.4 gfz=0.8 storeys=2 plan="B-Plan'
        ' Nr. 12". You read the limits from the Bebauungsplan; uea calc baunvo checks them.'
    )
    outline: Annotated[
        Points, F("its boundary: points x,y joined by ;, in order round it", unit="m")
    ]
    grz: Annotated[float | None, F("highest GRZ (Grundflächenzahl, § 19 BauNVO)")] = None
    grz2: Annotated[
        float | None,
        F("highest GRZ with § 19 Abs. 4 (below ground); else GRZ + 50 %, at most 0.8"),
    ] = None
    gfz: Annotated[float | None, F("highest GFZ (Geschossflächenzahl, § 20 BauNVO)")] = None
    gr: Annotated[float | None, F("highest Grundfläche instead of a GRZ", unit="m²")] = None
    gf: Annotated[float | None, F("highest Geschossfläche instead of a GFZ", unit="m²")] = None
    storeys: Annotated[int | None, F("most Vollgeschosse (Zahl der Vollgeschosse)")] = None
    plan: Annotated[str | None, F('where the limits come from: "B-Plan Nr. 12", "§ 34 BauGB"')] = (
        None
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        for name in ("grz", "grz2", "gfz"):
            v = getattr(self, name)
            if v is not None and not 0 < v <= 10:
                raise ValueError(f"{name}={v:g} is a ratio, e.g. 0.4")
        for name in ("gr", "gf"):
            v = getattr(self, name)
            if v is not None and v <= 0:
                raise ValueError(f"{name}= must be more than 0 m²")
        if self.storeys is not None and self.storeys < 1:
            raise ValueError("storeys= is 1 or more")
        return self


KINDS: tuple[type[Element], ...] = (Plot,)

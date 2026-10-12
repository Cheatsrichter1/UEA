"""Actions and their combination (DIN EN 1990, 6.4.3.2, equation 6.10, with NA): the permanent
action G and the variable actions Q (imposed), S (snow) and W (wind), each characteristic."""

from dataclasses import dataclass

from uea.calc import Env
from uea.packs.struct.tables import FACTORS, LIMITS, PSI

VARIABLE = {"q": "imposed", "s": "snow", "w": "wind"}


@dataclass
class Act:
    """Characteristic actions, kN (or kN/m, kN/m², as the context says)."""

    g: float = 0.0
    q: float = 0.0
    s: float = 0.0
    w: float = 0.0

    def add(self, o: "Act", f: float = 1.0) -> None:
        self.g += o.g * f
        self.q += o.q * f
        self.s += o.s * f
        self.w += o.w * f

    def times(self, f: float) -> "Act":
        return Act(self.g * f, self.q * f, self.s * f, self.w * f)

    @property
    def total(self) -> float:
        return self.g + self.q + self.s + self.w

    def get(self, k: str) -> float:
        return float(getattr(self, k))

    def data(self, places: int = 3) -> dict[str, float]:
        return {k.upper(): round(self.get(k), places) for k in "gqsw"}


class Factors:
    """The office's factors, read when first needed: a calculation needs only the rows it
    uses."""

    def __init__(self, env: Env) -> None:
        self.env = env
        self._psi: dict[str, float] | None = None

    def value(self, name: str) -> float:
        row = self.env.table(FACTORS).find(name=name)
        if row is None:
            raise ValueError(f"struct-factors has no row for {name}: add it to the table")
        return float(row["value"])

    def limit(self, name: str) -> float:
        row = self.env.table(LIMITS).find(name=name)
        if row is None:
            raise ValueError(f"struct-limits has no row for {name}: add it to the table")
        return float(row["value"])

    def psi(self, k: str) -> float:
        if self._psi is None:
            t = self.env.table(PSI)
            self._psi = {str(r["action"]).casefold(): float(r["psi0"]) for r in t.rows}
        name = VARIABLE[k]
        if name not in self._psi:
            raise ValueError(f"struct-psi has no row for {name}: add it to the table")
        return self._psi[name]

    def design(self, a: Act) -> float:
        """E_d = γ_G·G + γ_Q·(Q_k,1 + Σ ψ0,i·Q_k,i), the leading variable action the one that
        gives the most; only actions that push down count (a negative W is the uplift)."""
        var = {k: a.get(k) for k in VARIABLE if a.get(k) > 0}
        out = self.value("gamma-g") * a.g
        if not var:
            return out
        if len(var) == 1:
            return out + self.value("gamma-q") * sum(var.values())
        best = max(
            lead + sum(self.psi(k) * v for k, v in var.items() if k != key)
            for key, lead in var.items()
        )
        return out + self.value("gamma-q") * best

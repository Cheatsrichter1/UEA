"""Shared helpers: build models and projects from line text."""

import shutil
from pathlib import Path

import pytest

from uea.core.model import Model, element_from_raw
from uea.core.syntax import parse_line
from uea.derive import Derived, Report, report
from uea.packs import default_registry
from uea.project import Project

ROOT = Path(__file__).resolve().parent.parent
PROTOTYPE = ROOT / "docs" / "prototype" / "haus-mueller"

BOX = """\
project box "Box"
level EG z=0 fb=0.15 head=2.26
level OG z=2.9 fb=0.15 head=2.26
grid W x=0
grid E x=10
grid S y=0
grid N y=8
type AW wall layers=gips:0.01,*mw:0.3,putz:0.02
type IW wall layers=gips:0.01,*ks:0.115,gips:0.01
type DE slab layers=*stb:0.2,gips:0.01
type FB floor layers=fliese:0.02,estrich:0.13
type FE win default
type TI door default
wall w1 EG AW y=S+ x=W..E lb
wall w2 EG AW x=E- y=w1..w3 lb
wall w3 EG AW y=N- x=W..E lb
wall w4 EG AW x=W+ y=w1..w3 lb
"""


def model_from(text: str) -> Model:
    reg = default_registry()
    m = Model(reg)
    for line in text.splitlines():
        raw = parse_line(line)
        if raw is not None:
            m.put(element_from_raw(reg, raw))
    return m


def derive_text(text: str) -> tuple[Derived, Report]:
    return report(model_from(text))


def codes(rep: Report) -> list[tuple[str, str]]:
    return sorted((i.code, i.el) for i in rep.issues)


@pytest.fixture
def prototype(tmp_path: Path) -> Project:
    """Haus Müller (project, arch, issues) in a temporary folder."""
    for name in ("project.uea", "arch.uea", "issues.uea"):
        shutil.copy(PROTOTYPE / name, tmp_path / name)
    return Project(tmp_path)


@pytest.fixture
def empty(tmp_path: Path) -> Project:
    return Project.init(tmp_path / "p")

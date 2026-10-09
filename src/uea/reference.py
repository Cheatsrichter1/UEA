"""docs/reference.md: every command, operation, kind, type, issue code and calculator.

Generated from the code, so it cannot drift: `uv run python -m uea.reference` writes it, and a
test fails when the committed file is out of date. Agents read the same facts in layers
through `uea help`; this file is the whole list in one place, for people and for review.
"""

import re
from pathlib import Path

from uea.calc import builtin
from uea.calc.data import specs_of
from uea.cli import build_parser
from uea.core.issues import CORE_CODES
from uea.core.registry import Registry
from uea.core.schema import Element, spec, usage
from uea.export.cli import FORMATS
from uea.help import COMMANDS, OPS, POSITIONS
from uea.packs import default_registry

PATH = Path(__file__).resolve().parents[2] / "docs" / "reference.md"

HEAD = """\
# UEA reference

Every command, operation, element kind, type, issue code and calculator UEA has today.
Generated from the code by `uv run python -m uea.reference`; do not edit it by hand, a test
fails when it is out of date. Agents get the same facts in layers through `uea help`.
"""


def _cell(s: str) -> str:
    return s.replace("|", "\\|")


def commands() -> list[str]:
    out = ["## Commands", "", "| Command | What it does |", "|---|---|"]
    out += [f"| `{u}` | {_cell(d)} |" for u, d in COMMANDS]
    out += ["", "Full syntax. Every command also takes `-C <dir>` and `--json`.", "", "```"]
    for sp in build_parser().commands.values():
        line = " ".join(sp.format_usage().split()).removeprefix("usage: ")
        out.append(re.sub(r" \[-C DIR\] \[--json\]", "", line))
    out += ["```", ""]
    return out


def operations() -> list[str]:
    return ["## Operations", "", "```", OPS.rstrip(), "```", ""]


def positions() -> list[str]:
    return ["## Positions and heights", "", "```", POSITIONS.rstrip(), "```", ""]


def kind_section(cls: type[Element]) -> list[str]:
    sp = spec(cls)
    name = f"type … {cls.category}" if cls.kind == "type" else cls.kind
    out = [f"#### `{name}`", "", cls.doc, "", f"`{usage(cls)}`"]
    if cls.prefix:
        out[-1] += f" · ids `{cls.prefix}1`, `{cls.prefix}2`, … assigned by UEA"
    out += ["", "| Field | Written as | Values | Meaning |", "|---|---|---|---|"]
    for n in sp.positional:
        f = sp.fields[n]
        out.append(
            f"| {n} | positional | {_values(f.choices, f.meta.unit)} | {_cell(f.meta.doc)} |"
        )
    for n in sp.kv:
        f = sp.fields[n]
        req = " (required)" if f.required else ""
        out.append(
            f"| {n} | `{n}=` | {_values(f.choices, f.meta.unit)} | {_cell(f.meta.doc)}{req} |"
        )
    for n in sp.flags:
        out.append(f"| {n} | flag `{n}` | | {_cell(sp.fields[n].meta.doc)} |")
    for n in sp.flag_enums:
        f = sp.fields[n]
        words = " ".join(f"`{v}`" for v in f.choices if v != f.default)
        out.append(f"| {n} | flag | {words} | {_cell(f.meta.doc)} |")
    out.append("")
    return out


def _values(choices: tuple[str, ...], unit: str | None) -> str:
    if choices:
        return " ".join(f"`{c}`" for c in choices)
    return unit or ""


def kinds(reg: Registry) -> list[str]:
    out = [
        "## Element kinds and types",
        "",
        'One element per line: `kind id positional... "label" key=value... flags`. Levels,'
        " grids and types carry a name you choose; UEA assigns the ids of everything else.",
        "",
    ]
    for p in reg.packs.values():
        out += [f"### {p.title} (`{p.file}`)", ""]
        types = [c for c in p.kinds if c.kind == "type"]
        if types:
            out += ["Types: " + ", ".join(f"`type … {c.category}`" for c in types) + ".", ""]
        others = [c for c in p.kinds if c.kind != "type"]
        out += ["Kinds: " + ", ".join(f"`{c.kind}`" for c in others) + ".", ""]
        for cls in types + others:
            out += kind_section(cls)
    return out


def codes(reg: Registry) -> list[str]:
    out = [
        "## Issue codes",
        "",
        "E is an error, W a warning.",
        "",
        "| Code | Meaning |",
        "|---|---|",
    ]
    all_codes = dict(CORE_CODES)
    for p in reg.packs.values():
        all_codes.update(p.codes)
    out += [f"| {c} | {_cell(t)} |" for c, t in all_codes.items()]
    out.append("")
    return out


def calculators() -> list[str]:
    out = [
        "## Calculators",
        "",
        "Projects add `custom` calculators in `calc/`. A `custom` result is never presented as"
        " norm-compliant. A calculator that needs norm tables stops and names the one that is"
        " missing; the office installs its tables with `uea data add` from its own licensed copy"
        " (`docs/decisions/0008-office-supplied-norm-data.md`). Settings are written"
        " `name=value` after the calculator's name and are recorded in the result.",
        "",
        "| Name | Kind | Version | Standard | What it computes |",
        "|---|---|---|---|---|",
    ]
    calcs = list(builtin().values())
    for c in calcs:
        out.append(f"| `{c.name}` | {c.kind} | {c.version} | {c.norm or ''} | {_cell(c.title)} |")
    out.append("")
    for c in calcs:
        if not c.params:
            continue
        out += [
            f"### `{c.name}` settings",
            "",
            "| Setting | Type | Default | Meaning |",
            "|---|---|---|---|",
        ]
        for pm in c.params:
            default = "required" if pm.default is None and not pm.optional else pm.default
            default = "" if default is None or default == "" else default
            values = f" ({' / '.join(pm.choices)})" if pm.choices else ""
            out.append(
                f"| `{pm.name}` | {pm.kind.__name__} | {default} | {_cell(pm.doc)}{values} |"
            )
        out.append("")
    specs = specs_of(calcs)
    if specs:
        out += [
            "### Norm tables",
            "",
            "One CSV file for each table, the first line the header: `uea data add <id> <file.csv>"
            " --edition <e>`. Comma or semicolon separated; with a semicolon, a decimal comma is"
            " read. Numbers must be more than 0. No two rows may have the same key.",
            "",
        ]
        for sp in specs.values():
            out += [f"#### `{sp.id}`: {sp.title} ({sp.standard})", ""]
            if sp.doc:
                out += [sp.doc, ""]
            out += ["| Column | Type | Meaning |", "|---|---|---|"]
            for col in sp.cols:
                allowed = f" (one of {', '.join(col.choices)})" if col.choices else ""
                out.append(f"| `{col.name}` | {col.kind} | {_cell(col.doc)}{allowed} |")
            out += ["", f"One row for each: {', '.join(sp.key)}.", ""]
    return out


def exports() -> list[str]:
    fmts = ", ".join(f"`{f}`" for f in FORMATS)
    return [
        "## Exports",
        "",
        f"`uea export` writes {fmts}; `uea render` writes a PNG plan image for agents. Files go"
        " to `out/`. Drawings are labelled in German, for the people who read them.",
        "",
    ]


def reference() -> str:
    reg = default_registry()
    parts = [
        HEAD,
        *commands(),
        *operations(),
        *positions(),
        *kinds(reg),
        *codes(reg),
        *calculators(),
        *exports(),
    ]
    return "\n".join(parts).rstrip() + "\n"


if __name__ == "__main__":
    PATH.write_text(reference(), encoding="utf-8")
    print(f"wrote {PATH}")

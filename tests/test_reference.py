"""docs/reference.md is generated from the code and must match it."""

from uea.reference import PATH, reference


def test_reference_is_current() -> None:
    assert PATH.read_text(encoding="utf-8") == reference(), (
        "docs/reference.md is out of date: uv run python -m uea.reference"
    )


def test_reference_lists_every_kind_and_command() -> None:
    text = reference()
    for word in (
        "`uea apply",
        "#### `wall`",
        "#### `type … roof`",
        "| hand | `hand=`",
        "E-ARCH-011",
    ):
        assert word in text, word

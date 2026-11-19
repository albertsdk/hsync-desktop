# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Every user-visible literal in a ``.ui`` file must exist in the locales.

A label left in a ``.ui`` file is a second source of truth that no translation
reaches: the runtime replaces it from ``hsync_desktop.locales`` (so the designer
value is invisible in the app) or, worse, does not replace it and ships stale
English wording that contradicts the translated UI. This guard keeps the two in
sync by requiring each literal to be a value of ``locales/en.py`` (the SSOT for
every locale) or one of the few non-translatable forms below.

Consumers: hsync-desktop maintainers (i18n drift guard).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hsync_desktop.locales.en import translations as EN

UI_DIR = Path(__file__).resolve().parents[1] / "hsync_desktop" / "ui"

# Non-translatable literals: symbols/placeholders, a unit suffix, a style sheet,
# or a sample value a label shows until the code fills it in.
_ALLOWED = (
    re.compile(r"^[●–—↑↓⇄✕\s]*$"),
    re.compile(r"^\s*(?:s|MB/s|%)\s*$"),
    re.compile(r"(?:color|background-color|border|padding|font-size)\s*:"),
    re.compile(r"^\d[\d.,]*\s*(?:B|KB|MB|GB)(?:\s*\([^)]*\))?$"),
    re.compile(r"^version \d+\.\d+\.\d+ \(engine \d+\.\d+\.\d+\)$"),
)

# Designer previews for fields the code fills from the user's configuration (or
# from a dynamic value); they are not labels.
_SAMPLES = frozenset(
    {
        "my-bucket",
        "my-group",
        "https://server.example.com",
        "/path/to/ca.pem",
        "/path/to/logfile.log",
        "Select a folder…",
        "(optional)",
        "⚠ {count}",
        "0 (0 B)",
    }
)


def _literals(path: Path) -> list[str]:
    return [
        match.group(1)
        for match in re.finditer(r"<string>(.*?)</string>", path.read_text(encoding="utf-8"), re.S)
        if match.group(1)
    ]


@pytest.mark.parametrize("ui", sorted(UI_DIR.glob("*.ui")), ids=lambda path: path.name)
def test_ui_literals_come_from_the_locale_files(ui: Path) -> None:
    """A literal that is not a locale value (nor a symbol/unit/sample) drifts."""
    stray = [
        literal
        for literal in _literals(ui)
        if literal not in EN.values()
        and literal not in _SAMPLES
        and not any(pattern.search(literal) for pattern in _ALLOWED)
    ]
    assert not stray, f"{ui.name}: literal(s) missing from locales/en.py: {stray}"

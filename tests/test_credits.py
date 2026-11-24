# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The credits data and the published ``CONTRIBUTORS.md`` must not drift."""

from __future__ import annotations

import re
from pathlib import Path

from hsync_desktop.credits import CREDIT_SECTIONS
from hsync_desktop.i18n import tr

CONTRIBUTORS_MD = Path(__file__).resolve().parents[1] / "CONTRIBUTORS.md"

# Markdown heading -> locale key of the matching credit section.
SECTION_KEYS = {
    "Maintainer": "about.credits.maintainer",
    "Contributors": "about.credits.contributors",
}

# ``- Name ([@handle](url)) — role`` or ``- Name`` (no public handle yet).
_PERSON_RE = re.compile(r"^- ([^(\n—]+?)(?: \(\[@([\w-]+)\]\([^)]*\)\))?(?: — .*)?$")


def _documented() -> dict[str, list[tuple[str, str]]]:
    """Parse ``CONTRIBUTORS.md`` into ``{heading: [(name, handle), ...]}``."""
    sections: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for line in CONTRIBUTORS_MD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None and line.startswith("- "):
            match = _PERSON_RE.match(line)
            assert match, f"unparsable contributors entry: {line!r}"
            sections[current].append((match.group(1), match.group(2) or ""))
    return sections


class TestContributorsFile:
    def test_exists_next_to_the_project(self) -> None:
        assert CONTRIBUTORS_MD.is_file()

    def test_headings_map_to_the_credit_sections(self) -> None:
        assert set(_documented()) == set(SECTION_KEYS)

    def test_every_documented_person_is_credited_in_the_app(self) -> None:
        documented = _documented()
        typed = {section.title_key: list(section.people) for section in CREDIT_SECTIONS}
        for heading, key in SECTION_KEYS.items():
            assert [(person.name, person.handle) for person in typed[key]] == documented[heading]


class TestCreditSections:
    def test_section_titles_resolve_to_a_translation(self) -> None:
        for section in CREDIT_SECTIONS:
            assert tr(section.title_key) != section.title_key

    def test_every_credited_person_is_unique(self) -> None:
        names = [person.name for section in CREDIT_SECTIONS for person in section.people]
        assert len(names) == len(set(names))

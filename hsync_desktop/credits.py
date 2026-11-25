# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""People credited in the About window.

Display names and handles are proper nouns and are never translated; only the
section titles come from the locales. The published ``CONTRIBUTORS.md`` is the
human-facing twin of this data: ``tests/test_credits.py`` fails when the two
drift apart, so a new name is added to both in the same change.

Consumers: ``hsync_desktop/about_dialog.py`` (Credits tab), ``tests/test_credits.py``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Person:
    """One credited person: display name and, when known, the GitHub handle."""

    name: str
    handle: str = ""


@dataclass(frozen=True)
class CreditSection:
    """A titled group of credited people; ``title_key`` is a locale key."""

    title_key: str
    people: tuple[Person, ...]


CREDIT_SECTIONS: tuple[CreditSection, ...] = (
    CreditSection(
        title_key="about.credits.maintainer",
        people=(Person(name="Alberto Basso", handle="albertsdk"),),
    ),
    CreditSection(
        title_key="about.credits.contributors",
        people=(
            Person(name="Stefan Hirshi", handle="stefanhirshi"),
            Person(name="Nicola Cotellessa"),
            Person(name="Lorenzo Beltrami", handle="nonnemilia"),
        ),
    ),
)


def person_label(person: Person) -> str:
    """Display form used by the About window: name, plus ``(@handle)`` if known."""
    return f"{person.name} (@{person.handle})" if person.handle else person.name

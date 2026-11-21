# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Maps a validation :class:`Issue` to a localized message."""

from __future__ import annotations

from hsync_desktop.i18n import tr
from hsync_desktop.wizard.validation import Issue

__all__ = ["issue_message"]

# Codes whose sentence already exists for the Settings field: the wizard shows
# the same text rather than keeping a second copy of the password rules.
_SHARED_PASSWORD_KEYS = {
    "password_too_short": "p2pauth.error.too_short",
    "password_too_weak": "p2pauth.error.too_weak",
}


def issue_message(issue: Issue) -> str:
    """Return the localized message for *issue* (``wizard.error|warn.<code>``)."""
    if issue.level == "error" and issue.code in _SHARED_PASSWORD_KEYS:
        return tr(_SHARED_PASSWORD_KEYS[issue.code])
    prefix = "wizard.error." if issue.level == "error" else "wizard.warn."
    return tr(prefix + issue.code)

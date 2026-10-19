# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Maps a validation :class:`Issue` to a localized message."""

from __future__ import annotations

from hsync_desktop.i18n import tr
from hsync_desktop.wizard.validation import Issue

__all__ = ["issue_message"]


def issue_message(issue: Issue) -> str:
    """Return the localized message for *issue* (``wizard.error|warn.<code>``)."""
    prefix = "wizard.error." if issue.level == "error" else "wizard.warn."
    return tr(prefix + issue.code)

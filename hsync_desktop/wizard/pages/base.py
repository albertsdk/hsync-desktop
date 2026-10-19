# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Base class and shared behaviour for the wizard pages."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from hsync_desktop.wizard.model import WizardDraft
from hsync_desktop.wizard.validation import Issue
from hsync_desktop.wizard.widgets import InlineError

__all__ = ["WizardPage"]


class WizardPage(QWidget):
    """One wizard step.

    Pages never touch QSettings: they move data in and out of a
    :class:`WizardDraft` (:meth:`load` / :meth:`store`) and emit :attr:`changed`
    when the user edits something (the dialog then autosaves the draft).
    """

    changed = Signal()

    def apply_translations(self) -> None:
        """Re-apply localized strings (also called on a live language change)."""

    def load(self, draft: WizardDraft) -> None:
        """Populate the widgets from *draft*."""

    def store(self, draft: WizardDraft) -> None:
        """Write the widget values back into *draft*."""

    def issues(self) -> list[Issue]:
        """Validation issues for this page (empty when valid)."""
        return []

    def field_error_targets(self) -> dict[str, tuple[QWidget, InlineError]]:
        """Map a validation issue ``field`` to ``(widget, error label)``."""
        return {}

    def focus_first(self) -> None:
        """Focus the first useful control (default: nothing)."""

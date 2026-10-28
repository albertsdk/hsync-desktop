# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Inline show/hide toggle for masked secret fields.

Used by the Settings dialog (the p2p shared password and the server API key) so
the user can read a secret they must transcribe to another device. The action
sits inside the line edit, so the field keeps its form-row placement and its
buddy label. The revealed state is never persisted: a new dialog builds a new
action, so it always opens masked again.
"""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLineEdit

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon

__all__ = ["add_reveal_toggle", "refresh_reveal_tooltip"]


def add_reveal_toggle(line_edit: QLineEdit) -> QAction:
    """Add an inline eye action that reveals/hides a masked line edit.

    Returns the checkable ``QAction`` so the caller can re-apply its translated
    tooltip when the language or the tooltip preference changes.
    """
    action = QAction(line_edit)
    action.setCheckable(True)
    action.setProperty("revealTooltips", True)
    action.setIcon(icon("view-hidden"))
    action.toggled.connect(lambda shown: _apply(line_edit, action, shown))
    line_edit.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
    refresh_reveal_tooltip(action)
    return action


def refresh_reveal_tooltip(action: QAction, *, tooltips_enabled: bool = True) -> None:
    """Re-apply the translated tooltip/label for the action's current state.

    ``tooltips_enabled`` mirrors the Settings "show tooltips" preference: with it
    off the action carries no tooltip and no accessible label.
    """
    action.setProperty("revealTooltips", tooltips_enabled)
    if not tooltips_enabled:
        action.setToolTip("")
        action.setText("")
        return
    text = tr("secret.hide") if action.isChecked() else tr("secret.show")
    action.setToolTip(text)
    action.setText(text)


def _apply(line_edit: QLineEdit, action: QAction, shown: bool) -> None:
    line_edit.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
    action.setIcon(icon("view-visible" if shown else "view-hidden"))
    refresh_reveal_tooltip(action, tooltips_enabled=bool(action.property("revealTooltips")))

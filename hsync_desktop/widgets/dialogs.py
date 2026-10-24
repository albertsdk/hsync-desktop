# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Shared localized Yes/No confirmation dialogs.

Every confirmation in the GUI shares the same contract: standard ``Yes``/``No``
buttons, retitled with the localized ``action.yes`` / ``action.no`` labels (and
optionally the app icons), with ``No`` as the safe default. Hand-building the
box at each call site let those details drift, so the construction lives here.

Consumers: ``main_window/{actions,events,lifecycle,start,trust,ui,window}``,
``settings/dialog``, ``wizard/dialog``, ``trusted_keys``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon

__all__ = ["build_confirm_box", "confirm"]


def build_confirm_box(
    parent: QWidget | None,
    *,
    title: str,
    text: str,
    icon_name: QMessageBox.Icon = QMessageBox.Icon.Warning,
    default_yes: bool = False,
    with_icons: bool = False,
) -> QMessageBox:
    """Build a localized Yes/No box whose default answer is ``No`` unless asked."""
    box = QMessageBox(parent)
    box.setIcon(icon_name)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    yes_btn = box.button(QMessageBox.StandardButton.Yes)
    no_btn = box.button(QMessageBox.StandardButton.No)
    if yes_btn is not None:
        yes_btn.setText(tr("action.yes"))
        if with_icons:
            yes_btn.setIcon(icon("dialog-ok"))
    if no_btn is not None:
        no_btn.setText(tr("action.no"))
        if with_icons:
            no_btn.setIcon(icon("dialog-cancel"))
    box.setDefaultButton(
        QMessageBox.StandardButton.Yes if default_yes else QMessageBox.StandardButton.No
    )
    return box


def confirm(
    parent: QWidget | None,
    *,
    title: str,
    text: str,
    icon_name: QMessageBox.Icon = QMessageBox.Icon.Warning,
    default_yes: bool = False,
    with_icons: bool = False,
) -> bool:
    """Show a localized Yes/No confirmation; True only on an explicit ``Yes``."""
    box = build_confirm_box(
        parent,
        title=title,
        text=text,
        icon_name=icon_name,
        default_yes=default_yes,
        with_icons=with_icons,
    )
    return box.exec() == QMessageBox.StandardButton.Yes

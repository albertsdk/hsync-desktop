# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Shared localized Yes/No confirmation dialogs.

Every confirmation in the GUI shares the same contract: standard ``Yes``/``No``
buttons, retitled with the localized ``action.yes`` / ``action.no`` labels (and
optionally the app icons), with ``No`` as the safe default. Hand-building the
box at each call site let those details drift, so the construction lives here.

A confirmation that may be silenced adds an opt-out checkbox through
``build_optout_confirm_box``: the checkbox always starts unchecked, so silence is
always the user's explicit act, and only the caller decides what an
acknowledgement covers.

Consumers: ``main_window/{actions,events,lifecycle,start,trust,ui,window}``,
``settings/dialog``, ``wizard/dialog``, ``trusted_keys``, ``shares/dialog``
(destructive share deletion).
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QPushButton, QWidget

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon

__all__ = [
    "build_confirm_box",
    "build_destructive_confirm_box",
    "build_optout_confirm_box",
    "confirm",
    "dialog_parent",
]


def dialog_parent(fallback: QWidget | None = None) -> QWidget | None:
    """Parent a box raised from a slot: the modal window that is actually in front.

    A box parented to the main window while a modal dialog is open is stacked
    behind that dialog, so the user answers a prompt they cannot read. Every
    message box reached from a dialog action goes through here.
    """
    return QApplication.activeModalWidget() or fallback


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


def build_optout_confirm_box(
    parent: QWidget | None,
    *,
    title: str,
    text: str,
    checkbox_text: str,
    icon_name: QMessageBox.Icon = QMessageBox.Icon.Warning,
    with_icons: bool = True,
) -> tuple[QMessageBox, QCheckBox]:
    """Build a confirm box whose opt-out checkbox starts unchecked.

    The box keeps the shared contract (localized ``Yes``/``No``, ``No`` as the
    default answer) and returns the checkbox so the caller can read the user's
    choice. Nothing is persisted here: what an acknowledgement covers, and for
    how long, belongs to the call site.
    """
    box = build_confirm_box(
        parent,
        title=title,
        text=text,
        icon_name=icon_name,
        with_icons=with_icons,
    )
    checkbox = QCheckBox(checkbox_text)
    box.setCheckBox(checkbox)
    return box, checkbox


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


def build_destructive_confirm_box(
    parent: QWidget | None,
    *,
    title: str,
    text: str,
    accept_text: str,
    accept_icon: str = "edit-delete",
    checkbox_text: str | None = None,
) -> tuple[QMessageBox, QPushButton, QCheckBox | None]:
    """Build a localized confirm box whose accept button names the action.

    A destructive action does not answer Yes/No: the accept button repeats the
    verb ("Delete"), so the click stays unambiguous even when the message is long.
    Cancel keeps the app label and icon and is the default answer, so a stray
    Enter never destroys anything. Returns the box, the accept button (compare it
    with ``clickedButton()``) and the opt-out checkbox when one was requested.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    accept = box.addButton(accept_text, QMessageBox.ButtonRole.DestructiveRole)
    accept.setIcon(icon(accept_icon))
    cancel = box.addButton(tr("action.cancel"), QMessageBox.ButtonRole.RejectRole)
    cancel.setIcon(icon("dialog-cancel"))
    box.setDefaultButton(cancel)
    checkbox: QCheckBox | None = None
    if checkbox_text is not None:
        checkbox = QCheckBox(checkbox_text)
        checkbox.setChecked(True)
        box.setCheckBox(checkbox)
    return box, accept, checkbox

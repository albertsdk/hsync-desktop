# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Shared confirmation dialog for file-panel actions."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from hsync_desktop.i18n import tr


def _confirm_dialog(
    parent: QWidget,
    title: str,
    message: str,
    default_no: bool = True,
) -> bool:
    """Show a confirmation dialog with translated Yes/No buttons.

    Returns True if user clicked Yes, False otherwise.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QMessageBox.Icon.Question)

    btn_yes = msg.addButton(tr("btn.yes"), QMessageBox.ButtonRole.YesRole)
    btn_no = msg.addButton(tr("btn.no"), QMessageBox.ButtonRole.NoRole)

    if default_no:
        msg.setDefaultButton(btn_no)
    else:
        msg.setDefaultButton(btn_yes)

    msg.exec()
    return msg.clickedButton() == btn_yes

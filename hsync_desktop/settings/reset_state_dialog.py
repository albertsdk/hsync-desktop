# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Confirmation dialog for forgetting a folder's sync state."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon


class ResetStateDialog(QDialog):
    """Ask before forgetting a folder's sync state.

    A custom dialog rather than ``QMessageBox``: the built-in "Show Details" /
    "Hide Details" button is a Qt-owned string (no bundled translation) and the
    standard buttons carry no app icon, so either would break the themed,
    fully translated UI.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.reset_state.title"))
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        confirm = QLabel(tr("settings.reset_state.confirm"))
        confirm.setWordWrap(True)
        layout.addWidget(confirm)

        self._details = QLabel(tr("settings.reset_state.details"))
        self._details.setWordWrap(True)
        self._details.setVisible(False)
        layout.addWidget(self._details)

        self._toggle = QPushButton(tr("settings.reset_state.show_details"))
        self._toggle.setIcon(icon("utilities-log-viewer"))
        self._toggle.setCheckable(True)
        self._toggle.toggled.connect(self._on_toggle_details)
        layout.addWidget(self._toggle)

        buttons = QDialogButtonBox(self)
        self._cancel = buttons.addButton(
            tr("action.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._cancel.setIcon(icon("dialog-cancel"))
        self._reset = buttons.addButton(
            tr("settings.reset_state.action"),
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        self._reset.setIcon(icon("dialog-ok"))
        # Destructive: a stray Enter cancels, never resets.
        self._cancel.setDefault(True)
        self._reset.setAutoDefault(False)
        buttons.rejected.connect(self.reject)
        self._reset.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def _on_toggle_details(self, shown: bool) -> None:
        self._details.setVisible(shown)
        self._toggle.setText(
            tr(
                "settings.reset_state.hide_details"
                if shown
                else "settings.reset_state.show_details"
            )
        )

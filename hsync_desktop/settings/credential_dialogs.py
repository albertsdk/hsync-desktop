# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Dialogs that prompt for the server API key and the p2p key."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.crypto import decrypt_value, encrypt_value
from hsync_desktop.i18n import tr
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.text import escape_mnemonics


class ApiKeyDialog(QDialog):
    """Dialog to prompt for API key when authentication fails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("api_key_dialog", self)

        self.setWindowTitle(tr("apikey.title"))

        # Get widget references from .ui
        self._lbl_error: QLabel = self.findChild(QLabel, "lblError")  # type: ignore[assignment]
        self._lbl_prompt: QLabel = self.findChild(QLabel, "lblPrompt")  # type: ignore[assignment]
        self._lbl_key_label: QLabel = self.findChild(QLabel, "lblKeyLabel")  # type: ignore[assignment]
        self._api_key_edit: QLineEdit = self.findChild(QLineEdit, "editApiKey")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and load current values."""
        self._lbl_error.setText(tr("apikey.error_message"))
        self._lbl_prompt.setText(tr("apikey.prompt"))
        self._lbl_key_label.setText(tr("apikey.label"))
        self._api_key_edit.setPlaceholderText(tr("apikey.label"))

        # Load current API key if any
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        self._api_key_edit.setText(current_key)

        # Buttons
        self._button_box.addButton(
            escape_mnemonics(tr("apikey.save")), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_btn = self._button_box.addButton(
            tr("apikey.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        # Focus on input
        self._api_key_edit.setFocus()

    def _on_save(self) -> None:
        """Save the API key and accept the dialog."""
        api_key = self._api_key_edit.text().strip()
        if api_key:
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            s.setValue("connection/api_key", encrypt_value(api_key))
            self.accept()
        else:
            # Show warning if empty
            QMessageBox.warning(
                self,
                tr("apikey.title"),
                tr("apikey.prompt"),
            )


# ─── p2p Key Dialog ─────────────────────────────────────────────────────────


class P2PKeyDialog(QDialog):
    """Dialog to prompt for p2p key when p2p authentication fails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("p2p_key_dialog", self)

        self.setWindowTitle(tr("p2pauth.title"))

        # Get widget references from .ui
        self._lbl_error: QLabel = self.findChild(QLabel, "lblError")  # type: ignore[assignment]
        self._lbl_prompt: QLabel = self.findChild(QLabel, "lblPrompt")  # type: ignore[assignment]
        self._lbl_key_label: QLabel = self.findChild(QLabel, "lblKeyLabel")  # type: ignore[assignment]
        self._p2p_key_edit: QLineEdit = self.findChild(QLineEdit, "editP2PKey")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and load current values."""
        self._lbl_error.setText(tr("p2pauth.error_message"))
        self._lbl_prompt.setText(tr("p2pauth.prompt"))
        self._lbl_key_label.setText(tr("p2pauth.label"))
        self._p2p_key_edit.setPlaceholderText(tr("p2pauth.label"))

        # Load current p2p key if any
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_key = decrypt_value(str(s.value("p2p/key", "", str)))
        self._p2p_key_edit.setText(current_key)

        # Buttons
        self._button_box.addButton(
            escape_mnemonics(tr("p2pauth.save")), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_btn = self._button_box.addButton(
            tr("p2pauth.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        # Focus on input
        self._p2p_key_edit.setFocus()

    def _on_save(self) -> None:
        """Save the p2p key and accept the dialog."""
        p2p_key = self._p2p_key_edit.text().strip()
        if p2p_key:
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            s.setValue("p2p/key", encrypt_value(p2p_key))
            self.accept()
        else:
            QMessageBox.warning(
                self,
                tr("p2pauth.title"),
                tr("p2pauth.prompt"),
            )

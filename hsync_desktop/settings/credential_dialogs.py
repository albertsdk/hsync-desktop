# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Dialogs that prompt for the server API key and the p2p key."""

from __future__ import annotations

from hsync_common.protocol.rdv_tokens import (
    WeakGroupPassphrase,
    derive_group_key,
    validate_group_passphrase,
)
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.crypto import decrypt_value, encrypt_value
from hsync_desktop.fonts import monospace_font
from hsync_desktop.i18n import tr
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.secret_reveal import add_reveal_toggle
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
        if not p2p_key:
            QMessageBox.warning(
                self,
                tr("p2pauth.title"),
                tr("p2pauth.prompt"),
            )
            return
        try:
            validate_group_passphrase(p2p_key)
        except WeakGroupPassphrase as exc:
            QMessageBox.warning(
                self,
                tr("p2pauth.title"),
                tr(f"p2pauth.error.{exc.code}"),
            )
            return
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.setValue("p2p/key", encrypt_value(p2p_key))
        s.setValue("p2p/key_mode", "passphrase")
        self.accept()


def resolve_group_key(secret: str, key_mode: str) -> str:
    """Return the group key a discovery server expects for this shared secret.

    The desktop field always accepts a *shared password* (the group key is
    derived with scrypt) except for legacy installs that stored a raw 32+
    character key (``key_mode == "raw"``), which is already the key itself.
    The server derives its bucket tokens from this same 64-hex key, so this is
    the exact value an operator needs in the ``bucket=<key>`` line of a
    protected or private discovery server — see
    ``hsync_common.protocol.rdv_tokens::derive_group_key``.
    """
    if key_mode == "raw":
        return secret
    return derive_group_key(secret)


class GroupKeyDialog(QDialog):
    """Reveal/copy the group key a protected discovery server expects.

    There is no token for the user to type: the app derives the key from the
    Shared password (Settings → p2p Mode). This dialog shows the resulting
    64-hex key as the exact ``bucket=<key>`` line for the server's key file,
    so it can be handed to whoever operates the discovery server, and reminds
    the user that it is every bit as sensitive as the password.
    """

    def __init__(self, group_key: str, bucket: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group_key = group_key
        self._bucket_line = f"{bucket}={group_key}" if bucket else f"<bucket>={group_key}"
        self._build_ui()
        self._apply_translations()

    def _build_ui(self) -> None:
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        self._lbl_intro = QLabel(self)
        self._lbl_intro.setWordWrap(True)
        layout.addWidget(self._lbl_intro)

        # Read-only, masked by default: the key is as sensitive as the password.
        self._key_edit = QLineEdit(self)
        self._key_edit.setReadOnly(True)
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setText(self._group_key)
        self._key_edit.setFont(monospace_font())
        self._reveal = add_reveal_toggle(self._key_edit)
        layout.addWidget(self._key_edit)

        # The exact line the server operator provisions (bucket=<key>).
        self._lbl_bucket = QLabel(self)
        self._lbl_bucket.setFont(monospace_font())
        self._lbl_bucket.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._lbl_bucket)

        self._lbl_warning = QLabel(self)
        self._lbl_warning.setWordWrap(True)
        layout.addWidget(self._lbl_warning)

        # Copy + Close
        self._btn_copy = QPushButton(self)
        self._btn_copy.clicked.connect(self._on_copy)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self._btn_copy)
        buttons.addStretch()
        buttons.addWidget(box)
        layout.addLayout(buttons)

        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(self._restore_copy_label)

    def _on_copy(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._bucket_line)
        self._btn_copy.setText(tr("group_key.copied"))
        self._copy_timer.start(2000)

    def _restore_copy_label(self) -> None:
        self._btn_copy.setText(tr("group_key.copy"))

    def _apply_translations(self) -> None:
        self.setWindowTitle(tr("group_key.title"))
        self._lbl_intro.setText(tr("group_key.intro"))
        self._lbl_bucket.setText(tr("group_key.bucket_hint").format(line=self._bucket_line))
        self._lbl_warning.setText(tr("group_key.warning"))
        self._btn_copy.setText(tr("group_key.copy"))

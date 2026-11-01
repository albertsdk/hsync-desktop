# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the GUI group-key reveal (protected discovery servers).

A protected/private discovery server only introduces devices that know the
group key. There is no token to type: the desktop derives the key from the
Shared password (Settings → p2p Mode) and lets the user copy the ``bucket=<key>``
line for the server's key file.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLineEdit

import hsync_desktop.settings.dialog as dialog_mod
from hsync_desktop.i18n import tr
from hsync_desktop.locales import de, en, es, fr, it, ja, nl, pl, pt, ru, zh
from hsync_desktop.settings import SettingsDialog
from hsync_desktop.settings.credential_dialogs import (
    GroupKeyDialog,
    resolve_group_key,
)
from hsync_desktop.widgets.text import escape_mnemonics

ALL_MODULES = [en, it, de, fr, es, pt, zh, ru, nl, pl, ja]


@pytest.fixture
def dialog(qtbot, monkeypatch, tmp_path):
    """A SettingsDialog backed by an isolated settings store."""
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: settings)
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def seeded_dialog(qtbot, monkeypatch, tmp_path):
    """A SettingsDialog pre-seeded with a shared password + discovery server.

    The stored p2p secret is plaintext (``decrypt_value`` reads it), and the
    dialog snapshots its derived key on load, so the password-change warning and
    the apply-time reminder can be exercised.
    """
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("p2p/enabled", True)
    settings.setValue("p2p/key", "shared-password-1234")
    settings.setValue("p2p/key_mode", "passphrase")
    settings.setValue("p2p/rendezvous_server_endpoints", "rdv.example.net")
    settings.setValue("sync/bucket", "photos")
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: settings)
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


class _FakeMessageBox:
    """QMessageBox stand-in recording the buttons and returning a fixed choice."""

    class Icon:
        Warning = object()
        Information = object()

    class ButtonRole:
        ActionRole = object()
        AcceptRole = object()
        RejectRole = object()

    choice = "apply"  # "show" | "apply" | "cancel"

    def __init__(self, *args, **kwargs):
        self.buttons = {}
        self.title = ""
        self.text = ""

    def setIcon(self, icon):
        pass

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        btn = object()
        self.buttons[text] = btn
        return btn

    def setDefaultButton(self, btn):
        pass

    def exec(self):
        return 0

    def clickedButton(self):
        labels = {
            "show": escape_mnemonics(tr("settings.show_group_key")),
            "apply": tr("settings.apply"),
            "cancel": tr("settings.cancel"),
        }
        return self.buttons[labels[self.choice]]


class TestResolveGroupKey:
    def test_a_shared_password_is_derived(self):
        key = resolve_group_key("a-shared-password-1234", "passphrase")
        assert len(key) == 64

    def test_a_raw_legacy_key_is_used_as_is(self):
        secret = "0123456789abcdef0123456789abcdef"
        assert resolve_group_key(secret, "raw") == secret


class TestGroupKeyDialog:
    def test_the_secret_lives_only_in_the_masked_field(self, qtbot):
        key = "a" * 64
        dlg = GroupKeyDialog(key, "photos")
        qtbot.addWidget(dlg)

        # One single surface carries the secret: the read-only masked field now
        # holds the whole provisioning line. The labels explain, never echo it.
        assert dlg._key_edit.echoMode() == QLineEdit.EchoMode.Password
        assert dlg._key_edit.text() == "photos=" + key
        assert dlg._lbl_caption.text() == tr("group_key.caption")
        for label in (dlg._lbl_intro, dlg._lbl_caption, dlg._lbl_warning):
            assert key not in label.text()

        dlg._reveal.setChecked(True)
        assert dlg._key_edit.echoMode() == QLineEdit.EchoMode.Normal
        dlg._reveal.setChecked(False)
        assert dlg._key_edit.echoMode() == QLineEdit.EchoMode.Password

    def test_copy_puts_the_bucket_line_on_the_clipboard(self, qtbot):
        from PySide6.QtGui import QGuiApplication

        dlg = GroupKeyDialog("b" * 64, "photos")
        qtbot.addWidget(dlg)

        dlg._on_copy()

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        assert clipboard.text() == "photos=" + "b" * 64

    def test_a_missing_bucket_shows_the_placeholder(self, qtbot):
        dlg = GroupKeyDialog("c" * 64)
        qtbot.addWidget(dlg)
        assert dlg._key_edit.text() == "<bucket>=" + "c" * 64


class TestShowGroupKeyAction:
    def test_the_button_is_gated_on_a_rendezvous_and_a_password(self, dialog):
        assert dialog.btn_show_group_key is not None
        assert not dialog.p2p_key.text()
        assert not dialog.p2p_rendezvous.text().strip()
        assert dialog.btn_show_group_key.isHidden()
        assert not dialog.btn_show_group_key.isEnabled()

        dialog.p2p_key.setText("a-shared-password-1234")
        assert dialog.btn_show_group_key.isHidden()

        dialog.p2p_rendezvous.setText("rdv.example.net")
        assert not dialog.btn_show_group_key.isHidden()
        assert dialog.btn_show_group_key.isEnabled()

        dialog.p2p_key.setText("")
        assert not dialog.btn_show_group_key.isEnabled()

    def test_the_button_row_hides_without_a_discovery_server(self, dialog):
        dialog.p2p_key.setText("a-shared-password-1234")
        dialog.p2p_rendezvous.setText("rdv.example.net")
        assert not dialog.btn_show_group_key.isHidden()
        dialog.p2p_rendezvous.setText("")
        assert dialog.btn_show_group_key.isHidden()

    def test_click_opens_the_dialog_with_the_derived_key(self, dialog, monkeypatch):
        opened: list[tuple[str, str]] = []

        class _FakeGroupKeyDialog:
            def __init__(self, group_key: str, bucket: str, parent=None):
                opened.append((group_key, bucket))

            def exec(self):
                return None

        monkeypatch.setattr(dialog_mod, "GroupKeyDialog", _FakeGroupKeyDialog)
        dialog.p2p_key.setText("a-shared-password-1234")
        dialog.p2p_rendezvous.setText("rdv.example.net")
        dialog.bucket.setText("photos")

        dialog.btn_show_group_key.click()

        assert len(opened) == 1
        group_key, bucket = opened[0]
        assert len(group_key) == 64
        assert bucket == "photos"

    def test_the_button_warns_without_a_password(self, dialog, monkeypatch):
        warned: list[str] = []
        monkeypatch.setattr(
            dialog_mod.QMessageBox, "warning", lambda *a, **k: warned.append((a, k))
        )

        dialog._on_show_group_key()

        assert warned and warned[0][0][2] == tr("settings.show_group_key_no_password")


class TestPasswordChangeRendezvousReminder:
    def test_changing_the_password_shows_the_warning_row(self, seeded_dialog):
        dlg = seeded_dialog
        assert dlg._lbl_p2p_key_rdv_warning.isHidden()
        dlg.p2p_key.setText("a-different-password-5678")
        assert not dlg._lbl_p2p_key_rdv_warning.isHidden()
        dlg.p2p_key.setText("shared-password-1234")  # back to the loaded value
        assert dlg._lbl_p2p_key_rdv_warning.isHidden()

    def test_no_warning_without_a_discovery_server(self, dialog):
        dialog.p2p_key.setText("a-different-password-5678")
        assert not dialog._rdv_key_mismatch()
        assert dialog._lbl_p2p_key_rdv_warning.isHidden()

    def test_commit_aborts_when_the_user_cancels_the_reminder(self, seeded_dialog, monkeypatch):
        dlg = seeded_dialog
        dlg.p2p_key.setText("a-different-password-5678")
        asked: list[bool] = []
        monkeypatch.setattr(
            type(dlg), "_confirm_rdv_key_update", lambda self: asked.append(True) or False
        )
        assert not dlg._commit()
        assert asked == [True]

    def test_commit_proceeds_when_the_reminder_is_accepted(self, seeded_dialog, monkeypatch):
        dlg = seeded_dialog
        dlg.p2p_key.setText("a-different-password-5678")
        monkeypatch.setattr(type(dlg), "_confirm_rdv_key_update", lambda self: True)
        saved: list[bool] = []
        monkeypatch.setattr(type(dlg), "save", lambda self: saved.append(True))
        assert dlg._commit()
        assert saved == [True]

    def test_reminder_show_choice_opens_the_group_key_dialog(self, seeded_dialog, monkeypatch):
        monkeypatch.setattr(dialog_mod, "QMessageBox", _FakeMessageBox)
        monkeypatch.setattr(_FakeMessageBox, "choice", "show")
        opened: list[tuple[str, str]] = []

        class _FakeGroupKeyDialog:
            def __init__(self, group_key: str, bucket: str, parent=None):
                opened.append((group_key, bucket))

            def exec(self):
                return None

        monkeypatch.setattr(dialog_mod, "GroupKeyDialog", _FakeGroupKeyDialog)
        dlg = seeded_dialog
        dlg.p2p_key.setText("a-different-password-5678")

        assert dlg._confirm_rdv_key_update()

        assert len(opened) == 1
        group_key, bucket = opened[0]
        assert len(group_key) == 64
        assert bucket == "photos"
        assert dlg._rdv_key_reminder_ack

    def test_reminder_cancel_choice_aborts(self, seeded_dialog, monkeypatch):
        monkeypatch.setattr(dialog_mod, "QMessageBox", _FakeMessageBox)
        monkeypatch.setattr(_FakeMessageBox, "choice", "cancel")
        dlg = seeded_dialog
        dlg.p2p_key.setText("a-different-password-5678")
        assert not dlg._confirm_rdv_key_update()

    def test_reminder_apply_choice_proceeds_without_the_dialog(self, seeded_dialog, monkeypatch):
        monkeypatch.setattr(dialog_mod, "QMessageBox", _FakeMessageBox)
        monkeypatch.setattr(_FakeMessageBox, "choice", "apply")
        opened: list = []
        monkeypatch.setattr(dialog_mod, "GroupKeyDialog", lambda *a, **k: opened.append(a))
        dlg = seeded_dialog
        dlg.p2p_key.setText("a-different-password-5678")
        assert dlg._confirm_rdv_key_update()
        assert opened == []
        assert not dlg._rdv_key_reminder_ack


class TestP2PKeyDialogRendezvousReminder:
    def test_a_changed_key_with_a_discovery_server_reminds(self, qtbot, monkeypatch, tmp_path):
        import hsync_desktop.settings.credential_dialogs as cred_mod
        from hsync_desktop.settings.credential_dialogs import P2PKeyDialog

        settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        settings.setValue("p2p/rendezvous_server_endpoints", "rdv.example.net")
        settings.setValue("sync/bucket", "photos")
        monkeypatch.setattr(cred_mod, "QSettings", lambda *a, **k: settings)

        dlg = P2PKeyDialog()
        qtbot.addWidget(dlg)
        dlg._p2p_key_edit.setText("a-brand-new-password-1234")

        shown: list[tuple[str, str]] = []
        monkeypatch.setattr(cred_mod, "QMessageBox", _FakeMessageBox)
        monkeypatch.setattr(_FakeMessageBox, "choice", "show")

        class _FakeGroupKeyDialog:
            def __init__(self, group_key: str, bucket: str, parent=None):
                shown.append((group_key, bucket))

            def exec(self):
                return None

        monkeypatch.setattr(cred_mod, "GroupKeyDialog", _FakeGroupKeyDialog)
        dlg._on_save()

        assert len(shown) == 1
        assert len(shown[0][0]) == 64
        assert shown[0][1] == "photos"

    def test_no_reminder_without_a_discovery_server(self, qtbot, monkeypatch, tmp_path):
        import hsync_desktop.settings.credential_dialogs as cred_mod
        from hsync_desktop.settings.credential_dialogs import P2PKeyDialog

        settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(cred_mod, "QSettings", lambda *a, **k: settings)

        dlg = P2PKeyDialog()
        qtbot.addWidget(dlg)
        dlg._p2p_key_edit.setText("a-brand-new-password-1234")

        shown: list[tuple[str, str]] = []
        monkeypatch.setattr(cred_mod, "QMessageBox", _FakeMessageBox)
        monkeypatch.setattr(cred_mod, "GroupKeyDialog", lambda *a, **k: shown.append(a))
        dlg._on_save()

        assert shown == []


class TestDiscoveryServerTerminology:
    """User-facing strings say 'discovery server', never the internals' name."""

    def test_the_settings_help_link_uses_user_terminology(self):
        assert tr("help.rendezvous_setup") == "Discovery server setup guide"

    def test_no_new_key_leaks_the_internal_name(self):
        for module in ALL_MODULES:
            for key, value in module.translations.items():
                if key.startswith(("group_key.", "settings.show_group_key", "tip.show_group_key")):
                    assert "rendezvous" not in value.lower(), f"{module.__name__}:{key}"

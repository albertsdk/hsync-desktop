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

ALL_MODULES = [en, it, de, fr, es, pt, zh, ru, nl, pl, ja]


@pytest.fixture
def dialog(qtbot, monkeypatch, tmp_path):
    """A SettingsDialog backed by an isolated settings store."""
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: settings)
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestResolveGroupKey:
    def test_a_shared_password_is_derived(self):
        key = resolve_group_key("a-shared-password-1234", "passphrase")
        assert len(key) == 64

    def test_a_raw_legacy_key_is_used_as_is(self):
        secret = "0123456789abcdef0123456789abcdef"
        assert resolve_group_key(secret, "raw") == secret


class TestGroupKeyDialog:
    def test_the_key_is_masked_and_revealable(self, qtbot):
        dlg = GroupKeyDialog("a" * 64, "photos")
        qtbot.addWidget(dlg)

        assert dlg._key_edit.echoMode() == QLineEdit.EchoMode.Password
        assert dlg._key_edit.text() == "a" * 64
        assert dlg._lbl_bucket.text() == tr("group_key.bucket_hint").format(
            line="photos=" + "a" * 64
        )

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
        assert dlg._lbl_bucket.text() == tr("group_key.bucket_hint").format(
            line="<bucket>=c" * 0 + "<bucket>=" + "c" * 64
        )


class TestShowGroupKeyAction:
    def test_the_button_is_gated_on_a_non_empty_password(self, dialog):
        assert dialog.btn_show_group_key is not None
        assert not dialog.p2p_key.text()
        assert not dialog.btn_show_group_key.isEnabled()

        dialog.p2p_key.setText("a-shared-password-1234")

        assert dialog.btn_show_group_key.isEnabled()

        dialog.p2p_key.setText("")

        assert not dialog.btn_show_group_key.isEnabled()

    def test_click_opens_the_dialog_with_the_derived_key(self, dialog, monkeypatch):
        opened: list[tuple[str, str]] = []

        class _FakeGroupKeyDialog:
            def __init__(self, group_key: str, bucket: str, parent=None):
                opened.append((group_key, bucket))

            def exec(self):
                return None

        monkeypatch.setattr(dialog_mod, "GroupKeyDialog", _FakeGroupKeyDialog)
        dialog.p2p_key.setText("a-shared-password-1234")
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


class TestDiscoveryServerTerminology:
    """User-facing strings say 'discovery server', never the internals' name."""

    def test_the_settings_help_link_uses_user_terminology(self):
        assert tr("help.rendezvous_setup") == "Discovery server setup guide"

    def test_no_new_key_leaks_the_internal_name(self):
        for module in ALL_MODULES:
            for key, value in module.translations.items():
                if key.startswith(("group_key.", "settings.show_group_key", "tip.show_group_key")):
                    assert "rendezvous" not in value.lower(), f"{module.__name__}:{key}"

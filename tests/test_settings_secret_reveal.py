# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the inline show/hide toggle on the Settings secret fields."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLineEdit

import hsync_desktop.settings.dialog as dialog_mod
from hsync_desktop.i18n import tr
from hsync_desktop.settings import SettingsDialog
from hsync_desktop.widgets.secret_reveal import add_reveal_toggle, refresh_reveal_tooltip


@pytest.fixture
def dialog(qtbot, monkeypatch, tmp_path):
    """A SettingsDialog backed by an isolated settings store."""
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: settings)
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestSettingsReveal:
    def test_p2p_password_starts_masked(self, dialog):
        assert dialog.p2p_key.echoMode() == QLineEdit.EchoMode.Password
        action = dialog._p2p_key_reveal
        assert action.isCheckable()
        assert not action.isChecked()
        assert action.toolTip() == tr("secret.show")

    def test_toggling_reveals_and_masks_the_p2p_password(self, dialog):
        action = dialog._p2p_key_reveal
        action.setChecked(True)
        assert dialog.p2p_key.echoMode() == QLineEdit.EchoMode.Normal
        assert action.toolTip() == tr("secret.hide")
        assert not action.icon().isNull()
        action.setChecked(False)
        assert dialog.p2p_key.echoMode() == QLineEdit.EchoMode.Password
        assert action.toolTip() == tr("secret.show")

    def test_api_key_toggles_independently(self, dialog):
        assert dialog.api_key.echoMode() == QLineEdit.EchoMode.Password
        dialog._api_key_reveal.setChecked(True)
        assert dialog.api_key.echoMode() == QLineEdit.EchoMode.Normal
        assert dialog.p2p_key.echoMode() == QLineEdit.EchoMode.Password

    def test_a_reopened_dialog_is_masked_again(self, dialog, qtbot):
        dialog._p2p_key_reveal.setChecked(True)
        another = SettingsDialog()
        qtbot.addWidget(another)
        assert another.p2p_key.echoMode() == QLineEdit.EchoMode.Password
        assert not another._p2p_key_reveal.isChecked()


class TestRevealHelper:
    def test_tooltips_preference_clears_and_restores_the_label(self, qtbot):
        edit = QLineEdit()
        qtbot.addWidget(edit)
        action = add_reveal_toggle(edit)

        refresh_reveal_tooltip(action, tooltips_enabled=False)
        assert action.toolTip() == ""
        assert action.text() == ""

        refresh_reveal_tooltip(action, tooltips_enabled=True)
        assert action.toolTip() == tr("secret.show")
        assert action.text() == tr("secret.show")

        action.setChecked(True)
        assert action.toolTip() == tr("secret.hide")
        assert edit.echoMode() == QLineEdit.EchoMode.Normal

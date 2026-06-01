# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for the SettingsDialog security gates.

Covers the two security constraints added to the desktop settings:

* ``_apply_lan_key_gate`` - the LAN shared secret is only editable when
  both LAN mode and LAN HTTPS are enabled (a secret must never travel
  over plain HTTP).
* ``_confirm_insecure_api_key`` - the API key is never sent over an
  ``http://`` URL or with SSL verification disabled without an explicit
  user confirmation.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import SettingsDialog


@pytest.fixture
def dialog(qtbot):
    """Create a SettingsDialog registered with qtbot for cleanup."""
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestLanKeyGate:
    """The shared secret field follows the LAN_HTTPS state."""

    def test_enabled_when_lan_and_https(self, dialog):
        dialog.lan_mode.setChecked(True)
        dialog.lan_https.setChecked(True)
        dialog._apply_lan_key_gate()
        assert dialog.lan_key.isEnabled()

    def test_disabled_without_https(self, dialog):
        dialog.lan_mode.setChecked(True)
        dialog.lan_https.setChecked(False)
        dialog._apply_lan_key_gate()
        assert not dialog.lan_key.isEnabled()
        assert dialog.lan_key.toolTip() == tr("tip.lan_key_https_required")

    def test_disabled_when_lan_off(self, dialog):
        dialog.lan_mode.setChecked(False)
        dialog.lan_https.setChecked(True)
        dialog._apply_lan_key_gate()
        assert not dialog.lan_key.isEnabled()

    def test_label_disabled_without_https(self, dialog):
        lbl = dialog.findChild(QLabel, "lblLanKey")
        if lbl is None:
            pytest.skip("lblLanKey is not present in the .ui file")
        dialog.lan_mode.setChecked(True)
        dialog.lan_https.setChecked(False)
        dialog._apply_lan_key_gate()
        assert not lbl.isEnabled()


class TestInsecureApiKeyGate:
    """The API key is gated against insecure transports."""

    def test_skipped_in_lan_mode(self, dialog):
        dialog.lan_mode.setChecked(True)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_allowed_when_api_key_empty(self, dialog):
        dialog.lan_mode.setChecked(False)
        dialog.api_key.setText("")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_allowed_when_https_and_verify(self, dialog):
        dialog.lan_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("https://host")
        dialog.insecure.setChecked(False)
        assert dialog._confirm_insecure_api_key() is True

    def test_warns_on_http_url_and_user_cancels(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        dialog.lan_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is False

    def test_warns_on_http_url_and_user_proceeds(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
        dialog.lan_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_warns_when_skip_ssl_enabled(self, dialog, monkeypatch):
        shown = {}

        def fake_exec(self):
            shown["value"] = True
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.lan_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("https://host")
        dialog.insecure.setChecked(True)
        assert dialog._confirm_insecure_api_key() is False
        assert shown.get("value") is True

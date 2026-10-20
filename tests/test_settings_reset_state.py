# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the "Reset sync state" button in the Settings dialog.

The dialog only *asks* for the reset (it sets ``reset_state_folder`` and closes);
the MainWindow runs the client command. These tests cover the request itself,
the confirmation gate and the capability/sync-state gating.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import SettingsDialog
from hsync_desktop.settings.tab_indices import _SYNC_TAB_INDEX
from tests._helpers import _resolve_dialog


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep the reset flow's ``save()`` off the real user settings store."""
    from PySide6.QtCore import QSettings

    from hsync_desktop.settings import dialog as dialog_mod

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: store)
    return store


class TestButtonPlacement:
    def test_button_is_in_the_sync_tab(self, dialog):
        assert dialog._tabs.widget(_SYNC_TAB_INDEX).isAncestorOf(dialog.btn_reset_state)

    def test_button_label_is_translated(self, dialog):
        assert dialog.btn_reset_state.text() == tr("settings.reset_state.button")


class TestRequest:
    def test_needs_a_folder(self, dialog, monkeypatch):
        warned: list[str] = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warned.append(a[2])))
        dialog.shared_path.setText("")

        dialog._on_reset_state()

        assert dialog.reset_state_folder == ""
        assert warned == [tr("settings.reset_state.no_folder")]

    def test_confirm_requests_a_reset_and_accepts(self, dialog, monkeypatch):
        _resolve_dialog(monkeypatch, tr("settings.reset_state.action"))
        dialog.shared_path.setText("/data/photos")

        dialog._on_reset_state()

        assert dialog.reset_state_folder == "/data/photos"
        assert dialog.result() == SettingsDialog.DialogCode.Accepted

    def test_reset_saves_through_the_validated_accept_path(self, dialog, monkeypatch):
        """The reset must persist the session's edits before closing as Accepted."""
        saved: list[int] = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(1))
        _resolve_dialog(monkeypatch, tr("settings.reset_state.action"))
        dialog.shared_path.setText("/data/photos")

        dialog._on_reset_state()

        assert saved == [1]
        assert dialog.reset_state_folder == "/data/photos"

    def test_a_vetoed_commit_keeps_the_dialog_open_without_a_reset(self, dialog, monkeypatch):
        _resolve_dialog(monkeypatch, tr("settings.reset_state.action"))
        dialog.shared_path.setText("/data/photos")
        monkeypatch.setattr(dialog, "_commit", lambda: False)

        dialog._on_reset_state()

        assert dialog.reset_state_folder == ""
        assert dialog.result() != SettingsDialog.DialogCode.Accepted

    def test_cancel_keeps_the_dialog_open(self, dialog, monkeypatch):
        _resolve_dialog(monkeypatch, tr("action.cancel"))
        dialog.shared_path.setText("/data/photos")

        dialog._on_reset_state()

        assert dialog.reset_state_folder == ""
        assert dialog.result() != SettingsDialog.DialogCode.Accepted

    def test_dismissed_dialog_changes_nothing(self, dialog, monkeypatch):
        _resolve_dialog(monkeypatch, None)
        dialog.shared_path.setText("/data/photos")

        dialog._on_reset_state()

        assert dialog.reset_state_folder == ""

    def test_default_button_is_cancel(self, dialog, monkeypatch):
        captured: list[QMessageBox] = []

        def fake_exec(box):
            captured.append(box)
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.shared_path.setText("/data/photos")

        dialog._on_reset_state()

        assert captured
        assert captured[0].defaultButton() is captured[0].button(QMessageBox.StandardButton.Cancel)


class TestGating:
    @staticmethod
    def _dialog(qtbot, monkeypatch, *, supported: bool):
        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop.settings import dialog as dialog_mod

        subcommands = ["p2p", "state"] if supported else ["p2p"]
        doc = build_capabilities(
            app_version="1.0.0", subcommands=subcommands, cli_options_by_subcommand={}
        )
        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: doc)
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        return dlg

    def test_disabled_while_sync_runs(self, qtbot, monkeypatch):
        dlg = self._dialog(qtbot, monkeypatch, supported=True)
        assert dlg.btn_reset_state.isEnabled()

        dlg.set_connection_active(True)
        assert not dlg.btn_reset_state.isEnabled()

        dlg.set_connection_active(False)
        assert dlg.btn_reset_state.isEnabled()

    def test_disabled_when_the_binary_lacks_the_state_subcommand(self, qtbot, monkeypatch):
        dlg = self._dialog(qtbot, monkeypatch, supported=False)

        assert not dlg.btn_reset_state.isEnabled()
        assert dlg.btn_reset_state.toolTip() == tr("tip.capability_unsupported")

    def test_re_enabling_the_connection_keeps_the_capability_gate(self, qtbot, monkeypatch):
        dlg = self._dialog(qtbot, monkeypatch, supported=False)
        dlg.set_connection_active(True)
        dlg.set_connection_active(False)

        assert not dlg.btn_reset_state.isEnabled()

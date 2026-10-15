# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the SettingsDialog security gates.

Covers the API-key security constraint of the desktop settings:

* ``_confirm_insecure_api_key`` - the API key is never sent over an
  ``http://`` URL or with SSL verification disabled without an explicit
  user confirmation.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import _P2P_TAB_INDEX, _SERVER_TAB_INDEX, SettingsDialog


class TestForceMasterLiveWarning:
    """Force-master vs. directional sync is also gated live, not only on save.

    The prompt is diversified by trigger: picking a non-bidirectional
    direction offers to disable force-master (Yes: toggle off + jump to the
    p2p tab), while enabling force-master offers to go back to a
    bidirectional sync (Yes: direction reset + jump to the sync tab). The
    save gate keeps its own "reset the direction" message.
    """

    @staticmethod
    def _reset_conflict_state(dialog):
        """Force the three widgets to a known state (the fixture loads the
        real QSettings, whose saved p2p flags would otherwise leak in)."""
        dialog.sync_direction_combo.setCurrentIndex(0)
        dialog.force_master.setChecked(False)
        dialog.p2p_mode.setChecked(False)

    @staticmethod
    def _arm_conflict_silently(dialog):
        """Reach the p2p+force-master+direction conflict without its live
        prompts (signals blocked, used by the save-gate tests)."""
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.blockSignals(True)
        dialog.force_master.setChecked(True)
        dialog.force_master.blockSignals(False)

    def test_conflict_requires_p2p_and_force_master_and_direction(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        assert dialog._force_master_conflict() is False  # still bidirectional
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only (No: kept)
        assert dialog._force_master_conflict() is True
        dialog.p2p_mode.setChecked(False)
        assert dialog._force_master_conflict() is False  # force-master inert w/o p2p
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(False)
        assert dialog._force_master_conflict() is False

    def test_direction_change_offers_disabling_force_master(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)  # still bidirectional: silent
        dialog.sync_direction_combo.setCurrentIndex(2)  # download-only
        assert shown == [tr("warn.force_master_disable_msg")]
        assert dialog.force_master.isChecked() is False  # disabled on "Yes"
        assert dialog.sync_direction_combo.currentData() == "download-only"
        assert dialog._tabs.currentIndex() == _P2P_TAB_INDEX  # p2p tab

    def test_direction_change_yes_emits_toggle_signal(self, dialog, monkeypatch):
        """Regression: "Yes" must let the toggle's own `toggled` fire.

        Swallowing it with blockSignals froze the thumb animation, so the
        switch kept painting as ON while checked was False: clicking it on
        the p2p tab flipped it back to ON and re-triggered the enable
        prompt in a loop.
        """
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        emitted: list[bool] = []
        dialog.force_master.toggled.connect(emitted.append)
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only → prompt → Yes
        assert emitted == [False]
        assert dialog.force_master.isChecked() is False
        assert dialog._tabs.currentIndex() == _P2P_TAB_INDEX  # p2p tab

    def test_never_master_enabling_emits_force_master_off_signal(self, dialog):
        """Same stale-paint cause in the mutual exclusion: the forced
        uncheck must reach the animation so force-master stops drawing ON."""
        self._reset_conflict_state(dialog)
        dialog.never_master.setChecked(False)
        dialog.force_master.setChecked(True)
        emitted: list[bool] = []
        dialog.force_master.toggled.connect(emitted.append)
        dialog.never_master.setChecked(True)
        assert emitted == [False]
        assert dialog.force_master.isChecked() is False

    def test_direction_change_cancel_keeps_state(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        start_tab = dialog._tabs.currentIndex()
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only
        assert shown == [tr("warn.force_master_disable_msg")]
        assert dialog.force_master.isChecked() is True  # untouched on "No"
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

    def test_force_master_enable_offers_bidirectional_sync(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)  # force off: silent
        expected = tr("warn.force_master_sync_msg").format(
            direction=dialog.sync_direction_combo.currentText()
        )
        dialog.force_master.setChecked(True)
        assert shown == [expected]
        assert dialog.force_master.isChecked() is True  # the toggle stays on
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert dialog._tabs.currentIndex() == 0  # sync tab

    def test_force_master_enable_cancel_keeps_direction(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        start_tab = dialog._tabs.currentIndex()
        dialog.force_master.setChecked(True)
        assert shown == [
            tr("warn.force_master_sync_msg").format(
                direction=dialog.sync_direction_combo.currentText()
            )
        ]
        assert dialog.force_master.isChecked() is True
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

    def test_force_master_enable_silent_when_bidirectional(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)  # bidirectional: no prompt
        assert calls == []

    def test_force_master_enable_silent_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.setChecked(True)  # force-master inert w/o p2p
        assert calls == []

    def test_no_warning_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.force_master.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        assert calls == []
        assert dialog.sync_direction_combo.currentData() == "upload-only"

    def test_no_warning_without_force_master(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        assert calls == []

    def test_no_warning_when_selecting_bidirectional(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        self._arm_conflict_silently(dialog)
        dialog.sync_direction_combo.setCurrentIndex(0)  # back to bidirectional
        assert calls == []

    def test_load_does_not_trigger_warning(self, qtbot, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG

        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved = {k: s.value(k) for k in ("sync/direction", "p2p/enabled", "p2p/force_master")}
        try:
            s.setValue("sync/direction", "upload-only")
            s.setValue("p2p/enabled", True)
            s.setValue("p2p/force_master", True)
            s.sync()
            dlg = SettingsDialog()
            qtbot.addWidget(dlg)
            assert calls == []
        finally:
            for key, value in saved.items():
                if value is None:
                    s.remove(key)
                else:
                    s.setValue(key, value)
            s.sync()

    def test_accept_gate_resets_direction_on_yes(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        saved = []
        msg_keys = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        monkeypatch.setattr(
            dialog,
            "_maybe_warn_force_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or True,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.force_master_msg"]  # save-gate message
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert saved == [True]

    def test_accept_gate_cancel_skips_save(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        saved = []
        msg_keys = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        monkeypatch.setattr(
            dialog,
            "_maybe_warn_force_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or False,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.force_master_msg"]  # save-gate message
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert saved == []


class TestIgnoreDeleteWarning:
    """Declining the ignore-delete warning restores the toggle; the restore
    must fire `toggled` too, otherwise the switch keeps painting as OFF
    while checked is True (same stale-paint cause as the force-master
    prompt loop).
    """

    def test_decline_emits_toggle_signal_and_keeps_checked(self, dialog, monkeypatch):
        def fake_exec(self):
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.ignore_delete.setChecked(True)  # known starting state
        emitted: list[bool] = []
        dialog.ignore_delete.toggled.connect(emitted.append)
        dialog.ignore_delete.setChecked(False)  # user unchecks → warning → "No"
        # The nested restore signal is delivered before the outer uncheck
        # finishes, so assert both emissions rather than their order.
        assert sorted(emitted) == [False, True]
        assert dialog.ignore_delete.isChecked() is True

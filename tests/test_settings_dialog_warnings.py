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


class TestPreferMasterLiveWarning:
    """Prefer-master vs. directional sync is also gated live, not only on save.

    The prompt is diversified by trigger: picking a non-bidirectional
    direction offers to disable prefer-master (Yes: toggle off + jump to the
    p2p tab), while enabling prefer-master offers to go back to a
    bidirectional sync (Yes: direction reset + jump to the sync tab). The
    save gate keeps its own "reset the direction" message.
    """

    @staticmethod
    def _reset_conflict_state(dialog):
        """Force the three widgets to a known state (the fixture loads the
        real QSettings, whose saved p2p flags would otherwise leak in)."""
        dialog.sync_direction_combo.setCurrentIndex(0)
        dialog.prefer_master.setChecked(False)
        dialog.p2p_mode.setChecked(False)

    @staticmethod
    def _arm_conflict_silently(dialog):
        """Reach the p2p+prefer-master+direction conflict without its live
        prompts (signals blocked, used by the save-gate tests)."""
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.prefer_master.blockSignals(True)
        dialog.prefer_master.setChecked(True)
        dialog.prefer_master.blockSignals(False)

    def test_conflict_requires_p2p_and_prefer_master_and_direction(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.prefer_master.setChecked(True)
        assert dialog._prefer_master_conflict() is False  # still bidirectional
        # Force the incompatible direction without its live prompt (which would
        # otherwise revert it on "No").
        dialog.sync_direction_combo.blockSignals(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.sync_direction_combo.blockSignals(False)
        assert dialog._prefer_master_conflict() is True
        dialog.p2p_mode.setChecked(False)
        assert dialog._prefer_master_conflict() is False  # prefer-master inert w/o p2p
        dialog.p2p_mode.setChecked(True)
        dialog.prefer_master.setChecked(False)
        assert dialog._prefer_master_conflict() is False

    def test_direction_change_offers_disabling_prefer_master(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.prefer_master.setChecked(True)  # still bidirectional: silent
        dialog.sync_direction_combo.setCurrentIndex(2)  # download-only
        assert shown == [tr("warn.prefer_master_disable_msg")]
        assert dialog.prefer_master.isChecked() is False  # disabled on "Yes"
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
        dialog.prefer_master.setChecked(True)
        emitted: list[bool] = []
        dialog.prefer_master.toggled.connect(emitted.append)
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only → prompt → Yes
        assert emitted == [False]
        assert dialog.prefer_master.isChecked() is False
        assert dialog._tabs.currentIndex() == _P2P_TAB_INDEX  # p2p tab

    def test_never_master_enabling_emits_prefer_master_off_signal(self, dialog):
        """Same stale-paint cause in the mutual exclusion: the forced
        uncheck must reach the animation so prefer-master stops drawing ON."""
        self._reset_conflict_state(dialog)
        dialog.never_master.setChecked(False)
        dialog.prefer_master.setChecked(True)
        emitted: list[bool] = []
        dialog.prefer_master.toggled.connect(emitted.append)
        dialog.never_master.setChecked(True)
        assert emitted == [False]
        assert dialog.prefer_master.isChecked() is False

    def test_direction_change_cancel_reverts_to_bidirectional(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.prefer_master.setChecked(True)
        start_tab = dialog._tabs.currentIndex()
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only
        assert shown == [tr("warn.prefer_master_disable_msg")]
        assert dialog.prefer_master.isChecked() is True  # kept on "No"
        # Declining keeps prefer-master, so the incompatible direction must not
        # stay selected (the invariant prefer-master => bidirectional).
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert dialog._tabs.currentIndex() == start_tab

    def test_prefer_master_enable_offers_bidirectional_sync(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)  # force off: silent
        expected = tr("warn.prefer_master_sync_msg").format(
            direction=dialog.sync_direction_combo.currentText()
        )
        dialog.prefer_master.setChecked(True)
        assert shown == [expected]
        assert dialog.prefer_master.isChecked() is True  # the toggle stays on
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert dialog._tabs.currentIndex() == 0  # sync tab

    def test_prefer_master_enable_cancel_reverts_the_toggle(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        start_tab = dialog._tabs.currentIndex()
        dialog.prefer_master.setChecked(True)
        assert shown == [
            tr("warn.prefer_master_sync_msg").format(
                direction=dialog.sync_direction_combo.currentText()
            )
        ]
        # Declining keeps the direction, so prefer-master must go back off.
        assert dialog.prefer_master.isChecked() is False
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

    def test_prefer_master_enable_silent_when_bidirectional(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.prefer_master.setChecked(True)  # bidirectional: no prompt
        assert calls == []

    def test_prefer_master_enable_silent_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.prefer_master.setChecked(True)  # prefer-master inert w/o p2p
        assert calls == []

    def test_no_warning_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.prefer_master.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        assert calls == []
        assert dialog.sync_direction_combo.currentData() == "upload-only"

    def test_no_warning_without_prefer_master(self, dialog, monkeypatch):
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
        saved = {k: s.value(k) for k in ("sync/direction", "p2p/enabled", "p2p/prefer_master")}
        try:
            s.setValue("sync/direction", "upload-only")
            s.setValue("p2p/enabled", True)
            s.setValue("p2p/prefer_master", True)
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
            "_maybe_warn_prefer_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or True,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_rendezvous.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.prefer_master_msg"]  # save-gate message
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
            "_maybe_warn_prefer_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or False,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_rendezvous.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.prefer_master_msg"]  # save-gate message
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert saved == []


class TestDeletionPolicyWarning:
    """Leaving ``keep`` is confirmed; declining restores ``keep``.

    Only the transition that can destroy data asks, so a fresh dialog (default
    ``propagate``) switching between the other values stays silent.
    """

    def test_declining_restores_keep(self, dialog, monkeypatch):
        def fake_exec(self):
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        keep = dialog.deletion_policy.findData("keep")
        propagate = dialog.deletion_policy.findData("propagate")
        dialog.deletion_policy.setCurrentIndex(keep)
        assert dialog._deletion_policy_loaded == "keep"

        emitted: list[int] = []
        dialog.deletion_policy.currentIndexChanged.connect(emitted.append)
        dialog.deletion_policy.setCurrentIndex(propagate)  # user leaves keep → "No"

        assert dialog.deletion_policy.currentData() == "keep"
        # The restore is a nested index change: assert both were emitted, not
        # the order Qt delivers them in.
        assert set(emitted) == {propagate, keep}
        assert dialog._deletion_policy_loaded == "keep"

    def test_switching_to_propagate_after_confirm_is_kept(self, dialog, monkeypatch):
        def fake_exec(self):
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.deletion_policy.setCurrentIndex(dialog.deletion_policy.findData("keep"))
        dialog.deletion_policy.setCurrentIndex(dialog.deletion_policy.findData("propagate"))
        assert dialog.deletion_policy.currentData() == "propagate"
        assert dialog._deletion_policy_loaded == "propagate"


class TestVerboseLogPanelPrompt:
    """Enabling detailed logging offers to reveal an otherwise invisible log."""

    @staticmethod
    def _record(monkeypatch, result):
        shown: list[str] = []

        def fake_exec(self):
            shown.append(self.text())
            return result

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        return shown

    def test_enabling_verbose_offers_the_log_panel(self, dialog, monkeypatch):
        shown = self._record(monkeypatch, QMessageBox.StandardButton.Yes)
        dialog.show_log_panel.setChecked(False)
        dialog.logfile.setText("")
        dialog.verbose.setChecked(False)

        dialog.verbose.setChecked(True)

        assert shown == [tr("warn.verbose_no_log_msg")]
        assert dialog.show_log_panel.isChecked() is True

    def test_no_prompt_when_the_panel_is_visible(self, dialog, monkeypatch):
        shown = self._record(monkeypatch, QMessageBox.StandardButton.Yes)
        dialog.show_log_panel.setChecked(True)
        dialog.logfile.setText("")
        dialog.verbose.setChecked(False)

        dialog.verbose.setChecked(True)

        assert shown == []

    def test_no_prompt_when_a_log_file_is_set(self, dialog, monkeypatch):
        shown = self._record(monkeypatch, QMessageBox.StandardButton.Yes)
        dialog.show_log_panel.setChecked(False)
        dialog.logfile.setText("/tmp/hsync.log")
        dialog.verbose.setChecked(False)

        dialog.verbose.setChecked(True)

        assert shown == []

    def test_declining_leaves_the_panel_hidden(self, dialog, monkeypatch):
        self._record(monkeypatch, QMessageBox.StandardButton.No)
        dialog.show_log_panel.setChecked(False)
        dialog.logfile.setText("")
        dialog.verbose.setChecked(False)

        dialog.verbose.setChecked(True)

        assert dialog.show_log_panel.isChecked() is False
        assert dialog.verbose.isChecked() is True

    def test_turning_verbose_off_never_prompts(self, dialog, monkeypatch):
        shown = self._record(monkeypatch, QMessageBox.StandardButton.Yes)
        dialog.show_log_panel.setChecked(False)
        dialog.logfile.setText("")
        dialog.verbose.setChecked(True)
        shown.clear()

        dialog.verbose.setChecked(False)

        assert shown == []

    def test_a_restored_state_does_not_prompt(self, qtbot, monkeypatch, tmp_path):
        import hsync_desktop.settings.dialog as dialog_mod
        from tests._helpers import _settings

        s = _settings(tmp_path)
        s.setValue("output/verbose", True)
        s.setValue("appearance/show_log", False)
        s.setValue("output/logfile", "")
        monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: s)
        shown = self._record(monkeypatch, QMessageBox.StandardButton.Yes)

        dlg = SettingsDialog()
        qtbot.addWidget(dlg)

        assert shown == []
        assert dlg.verbose.isChecked() is True
        assert dlg.show_log_panel.isChecked() is False

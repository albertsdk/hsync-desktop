# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the system tray tooltip."""

from __future__ import annotations

from hsync_desktop.i18n import tr
from hsync_desktop.system_tray import SystemTray


class TestSimulationNote:
    """The tray tooltip repeats the mode so it is visible while minimised."""

    def test_tooltip_gains_and_loses_the_mode_note(self, qapp):
        tray = SystemTray()
        try:
            tray.update_status("connected")
            assert tr("status.connected") in tray.toolTip()
            assert tr("simulation.badge") not in tray.toolTip()

            tray.set_simulation(True)
            assert tr("simulation.badge") in tray.toolTip()

            tray.set_simulation(False)
            assert tr("simulation.badge") not in tray.toolTip()
        finally:
            tray.hide()


class TestPreviewChangesEntry:
    """The tray entry answers in both states: only the window's rule disables it."""

    def test_the_entry_shows_the_windows_wording(self, qapp):
        """The tray has no other text, so the window pushes the sentence.

        The same entry answers differently in the two engine states; the window
        owns that choice (``set_preview_changes_tooltip``), and the menu has to be
        told to show it.
        """
        tray = SystemTray()
        try:
            assert tray._act_preview_changes.toolTip() == tr("tip.preview_changes")
            menu = tray.contextMenu()
            assert menu is not None
            assert menu.toolTipsVisible()

            tray.set_preview_changes_tooltip(tr("tip.compare_waiting"))
            assert tray._act_preview_changes.toolTip() == tr("tip.compare_waiting")
        finally:
            tray.hide()

    def test_it_emits_its_signal_with_its_own_rule(self, qapp):
        tray = SystemTray()
        try:
            emitted: list[int] = []
            tray.preview_changes_requested.connect(lambda: emitted.append(1))

            # Start's rule no longer applies to it: it answers while running.
            tray.set_start_enabled(False)
            assert tray._act_preview_changes.isEnabled()

            tray.set_preview_changes_enabled(False)
            assert not tray._act_preview_changes.isEnabled()

            tray.set_preview_changes_enabled(True)
            assert tray._act_preview_changes.text() == tr("tray.preview_changes")

            tray._act_preview_changes.trigger()
            assert emitted == [1]
        finally:
            tray.hide()

    def test_only_a_stop_disables_it(self, qapp):
        tray = SystemTray()
        try:
            tray.set_running(True)
            assert tray._act_preview_changes.isEnabled()

            tray.set_running(False)
            assert tray._act_preview_changes.isEnabled()

            tray.set_stopping()
            assert not tray._act_preview_changes.isEnabled()
        finally:
            tray.hide()


class TestStoppingState:
    """The tray follows the window while a stop is in flight."""

    def test_stopping_names_the_state_and_disables_the_run_actions(self, qapp):
        tray = SystemTray()
        try:
            tray.set_running(True)
            tray.update_status("stopping")

            assert tr("status.stopping") in tray.toolTip()
            assert tray._act_stop.isEnabled()

            tray.set_stopping()

            assert not tray._act_start.isEnabled()
            assert not tray._act_stop.isEnabled()
            assert not tray._act_preview_changes.isEnabled()
        finally:
            tray.hide()

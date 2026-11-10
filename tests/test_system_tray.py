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


class TestMenuEntries:
    """The menu names the state and offers the navigation and info entries."""

    def test_the_state_line_names_the_link(self, qapp):
        tray = SystemTray()
        try:
            assert tray._act_status.text() == tr("status.disconnected")
            assert not tray._act_status.isEnabled()

            tray.update_status("connected")
            assert tray._act_status.text() == tr("status.connected")

            tray.update_status("waiting")
            assert tray._act_status.text() == tr("status.waiting")
        finally:
            tray.hide()

    def test_the_folder_entry_follows_the_folder(self, qapp):
        tray = SystemTray()
        try:
            opened: list[int] = []
            tray.open_folder_requested.connect(lambda: opened.append(1))

            assert not tray._act_open_folder.isEnabled()
            assert tray._act_open_folder.text() == tr("tray.open_folder")

            tray.set_open_folder_enabled(True)
            assert tray._act_open_folder.isEnabled()

            tray._act_open_folder.trigger()
            assert opened == [1]
        finally:
            tray.hide()

    def test_the_about_entry_opens_the_app_info(self, qapp):
        tray = SystemTray()
        try:
            shown: list[int] = []
            tray.about_requested.connect(lambda: shown.append(1))

            assert tray._act_about.text() == tr("menu.help.about")

            tray._act_about.trigger()
            assert shown == [1]
        finally:
            tray.hide()

    def test_the_menu_order_keeps_navigation_runs_config_and_info_apart(self, qapp):
        """State, navigation, run controls, configuration, info, quit."""
        tray = SystemTray()
        try:
            menu = tray.contextMenu()
            assert menu is not None
            actions = [a for a in menu.actions() if not a.isSeparator()]
            labels = [a.text() for a in actions]

            assert labels == [
                tr("status.disconnected"),
                tr("tray.show"),
                tr("tray.open_folder"),
                tr("tray.start"),
                tr("tray.preview_changes"),
                tr("tray.stop"),
                tr("tray.settings"),
                tr("tray.setup_wizard"),
                tr("menu.help.about"),
                tr("tray.quit"),
            ]
        finally:
            tray.hide()

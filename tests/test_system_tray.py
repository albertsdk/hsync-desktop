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


class TestCheckChangesEntry:
    """The tray entry mirrors the window's rule: running alone is not enough."""

    def test_running_does_not_enable_the_check_entry(self, qapp):
        tray = SystemTray()
        try:
            tray.set_running(True)
            assert not tray._act_check_changes.isEnabled()

            tray.set_check_changes_enabled(True)
            assert tray._act_check_changes.isEnabled()

            tray.set_check_changes_enabled(False)
            assert not tray._act_check_changes.isEnabled()
        finally:
            tray.hide()


class TestPreviewChangesEntry:
    """The explicit "Preview changes" entry follows Start's enablement rule."""

    def test_the_entry_explains_what_it_will_not_do(self, qapp):
        """The tray has no other text, so the tooltip has to separate the entry
        from Start, and the menu has to be told to show it."""
        tray = SystemTray()
        try:
            assert tray._act_preview_changes.toolTip() == tr("tip.preview_changes")
            menu = tray.contextMenu()
            assert menu is not None
            assert menu.toolTipsVisible()
        finally:
            tray.hide()

    def test_it_mirrors_start_and_emits_its_signal(self, qapp):
        tray = SystemTray()
        try:
            emitted: list[int] = []
            tray.preview_changes_requested.connect(lambda: emitted.append(1))

            tray.set_start_enabled(False)
            assert not tray._act_preview_changes.isEnabled()

            tray.set_start_enabled(True)
            assert tray._act_preview_changes.isEnabled()
            assert tray._act_preview_changes.text() == tr("tray.preview_changes")

            tray._act_preview_changes.trigger()
            assert emitted == [1]
        finally:
            tray.hide()

    def test_running_and_stopping_disable_it(self, qapp):
        tray = SystemTray()
        try:
            tray.set_running(True)
            assert not tray._act_preview_changes.isEnabled()

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
            assert not tray._act_check_changes.isEnabled()
        finally:
            tray.hide()

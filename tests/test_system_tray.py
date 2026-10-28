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

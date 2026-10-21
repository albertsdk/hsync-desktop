# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the preview summary dialog, real run vs Simulation Mode."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from hsync_desktop.i18n import tr
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog


def _stats(**counts: int) -> PreviewStats:
    stats = PreviewStats()
    for key, value in counts.items():
        setattr(stats, key, value)
    return stats


def _button_texts(dialog: PreviewSummaryDialog) -> list[str]:
    return [button.text() for button in dialog.findChildren(QPushButton)]


class TestSimulationMode:
    """A simulation reports the work and cannot offer to apply it."""

    def test_simulation_replaces_sync_with_close(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=2), simulation=True)
        qtbot.addWidget(dialog)

        assert _button_texts(dialog) == [tr("preview_summary.close")]
        assert tr("preview_summary.simulation") in dialog._lbl_title.text()
        assert dialog.windowTitle().endswith(tr("simulation.window_title_suffix"))

    def test_real_run_keeps_sync_and_cancel(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=2))
        qtbot.addWidget(dialog)

        assert _button_texts(dialog) == [
            tr("preview_summary.cancel"),
            tr("preview_summary.sync"),
        ]
        assert tr("preview_summary.simulation") not in dialog._lbl_title.text()
        assert dialog.windowTitle() == tr("preview_summary.title")

    def test_nothing_to_do_keeps_ok_in_both_modes(self, qtbot):
        for simulation in (False, True):
            dialog = PreviewSummaryDialog(PreviewStats(), simulation=simulation)
            qtbot.addWidget(dialog)

            assert _button_texts(dialog) == [tr("preview_summary.ok")]

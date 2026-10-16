# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the unified BandwidthDialog (0 = unlimited, no enable checkbox)."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QCheckBox, QDialogButtonBox, QDoubleSpinBox

from hsync_desktop.bandwidth_dialog import BandwidthDialog
from hsync_desktop.i18n import tr


def _dialog(qtbot, upload_bps, download_bps):
    from hsync_desktop import bandwidth_dialog as mod

    with patch.object(mod, "get_bandwidth_limits", return_value=(upload_bps, download_bps)):
        dlg = BandwidthDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestStrategy:
    def test_no_enable_checkboxes(self, qtbot):
        """The redundant 'Limit speed' checkboxes are gone; 0 means unlimited."""
        dlg = _dialog(qtbot, None, None)
        assert dlg.findChildren(QCheckBox) == []

    def test_spins_use_zero_as_unlimited(self, qtbot):
        dlg = _dialog(qtbot, None, None)
        up: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnUpload")
        down: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnDownload")
        assert up.value() == 0
        assert down.value() == 0
        assert up.specialValueText() == tr("settings.unlimited")
        assert down.specialValueText() == tr("settings.unlimited")

    def test_loaded_limits_show_in_mb(self, qtbot):
        dlg = _dialog(qtbot, 5 * 1024 * 1024, None)
        assert dlg.get_bandwidth_values() == (5.0, None)

    def test_spins_are_capped_at_the_engine_maximum(self, qtbot):
        from hsync_desktop.config import BANDWIDTH_MAX_MBPS

        dlg = _dialog(qtbot, None, None)
        up: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnUpload")
        down: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnDownload")
        assert up.maximum() == BANDWIDTH_MAX_MBPS
        assert down.maximum() == BANDWIDTH_MAX_MBPS

    def test_buttons_use_app_theme_icons(self, qtbot):
        """Apply/Cancel carry the same themed icons as the app's Save/Cancel."""
        dlg = _dialog(qtbot, None, None)
        box: QDialogButtonBox = dlg.findChild(QDialogButtonBox, "buttonBox")
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and not ok.icon().isNull()
        assert cancel is not None and not cancel.icon().isNull()
        assert ok.text() == tr("bandwidth.apply")
        assert cancel.text() == tr("settings.cancel")


class TestPersistence:
    def test_accept_saves_values(self, qtbot):
        dlg = _dialog(qtbot, None, None)
        up: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnUpload")
        down: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox, "spnDownload")
        up.setValue(2.5)
        down.setValue(0)

        from hsync_desktop import bandwidth_dialog as mod

        with patch.object(mod, "save_bandwidth_limits") as save:
            dlg._on_accept()
            save.assert_called_once_with(2.5, None)

    def test_zero_means_unlimited(self, qtbot):
        dlg = _dialog(qtbot, None, None)
        assert dlg.get_bandwidth_values() == (None, None)

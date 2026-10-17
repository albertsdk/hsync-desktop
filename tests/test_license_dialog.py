# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the Help -> License viewer."""

from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from hsync_desktop.license_dialog import LicenseDialog, license_text


def test_license_text_contains_the_project_license() -> None:
    text = license_text()
    assert "BSD 3-Clause License" in text
    assert "Redistribution and use in source and binary forms" in text


class TestLicenseDialog:
    def test_shows_a_readonly_license_with_a_close_button(self, qtbot) -> None:
        dlg = LicenseDialog()
        qtbot.addWidget(dlg)

        assert dlg._view.isReadOnly()
        assert dlg._view.toPlainText() == license_text()
        assert dlg._buttons.button(QDialogButtonBox.StandardButton.Close) is not None

    def test_uses_the_small_monospace_font(self, qtbot, monkeypatch) -> None:
        from PySide6.QtGui import QFont

        import hsync_desktop.license_dialog as mod

        monkeypatch.setattr(mod, "small_monospace_font", lambda: QFont("Probe Small"))

        dlg = LicenseDialog()
        qtbot.addWidget(dlg)

        assert dlg._view.font().family() == "Probe Small"

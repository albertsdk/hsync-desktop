# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The Settings dialog scrolls tall pages and stays within the screen.

A tall Advanced page must not force a tall, fixed window: every tab page scrolls,
and ``finalize_size`` clamps the resizable dialog to the screen.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QScrollArea

import hsync_desktop.settings.tab_builders as tab_builders


class TestScrollableTabs:
    def test_every_tab_page_scrolls(self, dialog):
        for index in range(dialog._tabs.count()):
            page = dialog._tabs.widget(index)
            assert page is not None
            assert page.findChild(QScrollArea) is not None, f"tab {index} has no scroll area"


class TestResizableDialog:
    def test_minimum_width_is_kept_for_the_description_cap(self, dialog):
        # tests/test_settings_tab_descriptions.py requires
        # label.maximumWidth() < dialog.minimumWidth(), so 640 stays mandated.
        assert dialog.minimumWidth() == 640

    def test_dialog_is_not_fixed_size(self, dialog):
        # setFixedSize was removed: the dialog can grow/shrink and be maximized.
        assert dialog.maximumWidth() > dialog.minimumWidth()
        assert dialog.maximumHeight() > dialog.minimumHeight()


class TestScreenClamp:
    _AVAIL = QSize(1024, 600)

    @staticmethod
    def _clamp(monkeypatch, dialog, avail) -> None:
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: avail)
        tab_builders.finalize_size(dialog)

    def test_dialog_fits_a_small_screen(self, monkeypatch, dialog):
        self._clamp(monkeypatch, dialog, self._AVAIL)
        assert dialog.width() <= int(self._AVAIL.width() * 0.9)
        assert dialog.height() <= int(self._AVAIL.height() * 0.9)

    def test_showing_advanced_still_fits_the_screen(self, monkeypatch, dialog):
        dialog.show_advanced.setChecked(False)
        self._clamp(monkeypatch, dialog, self._AVAIL)
        dialog.show_advanced.setChecked(True)  # triggers the re-clamp
        assert dialog.height() <= int(self._AVAIL.height() * 0.9)

    def test_offscreen_guard_keeps_a_usable_size(self, monkeypatch, dialog):
        # A headless platform may report no usable geometry: never resize to 0.
        self._clamp(monkeypatch, dialog, None)
        assert dialog.width() >= 640
        assert dialog.height() > 0

    def test_toggling_advanced_preserves_a_maximized_dialog(self, monkeypatch, dialog):
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: self._AVAIL)
        dialog.setWindowState(Qt.WindowState.WindowMaximized)
        dialog.show_advanced.setChecked(True)  # re-fit must not de-maximize
        assert dialog.isMaximized()

    def test_toggling_advanced_keeps_a_user_resized_geometry(self, monkeypatch, dialog):
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: self._AVAIL)
        dialog.resize(1100, 900)
        dialog.show_advanced.setChecked(True)  # re-fit must not shrink the window
        assert (dialog.width(), dialog.height()) == (1100, 900)

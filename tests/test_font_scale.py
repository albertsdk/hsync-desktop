# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""A live font-size change must reach every widget, not only the explicit ones."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from hsync_desktop import fonts
from hsync_desktop.config import FONT_SCALE_COMPACT

_STATUS_BAR_AND_HEADER = (
    "_status_label",
    "_peers_label",
    "_share_size_label",
    "_sync_state_label",
    "_sent_label",
    "_recv_label",
    "_role_label",
    "_path_label",
    "_remote_label",
    "_group_label",
)


@pytest.fixture()
def app_fonts():
    """Restore the application font and the resolved caches after the test."""
    app = QApplication.instance()
    saved_app_font = QFont(app.font())
    saved_ui, saved_mono = fonts._ui_font, fonts._mono_font
    try:
        yield app
    finally:
        app.setFont(saved_app_font)
        fonts._ui_font = saved_ui
        fonts._mono_font = saved_mono


class TestResetWidgetFonts:
    """The stylesheet pins each widget's font at polish time; resetting frees it."""

    def test_a_child_with_an_explicit_font_follows_the_application_font(self, qtbot, app_fonts):
        parent = QWidget()
        qtbot.addWidget(parent)
        child = QLabel("text", parent)
        child.setFont(QFont("Sans", 20))
        app_fonts.setFont(QFont("Sans", 9))

        assert child.font().pointSizeF() == pytest.approx(20.0)

        fonts.reset_widget_fonts(parent)

        assert child.font().pointSizeF() == pytest.approx(app_fonts.font().pointSizeF())


class TestLiveFontScaleChange:
    """The status bar and the share/mode labels follow the new scale."""

    def test_the_status_bar_and_header_labels_follow_the_scale(
        self, window, monkeypatch, app_fonts
    ):
        import hsync_desktop.main_window.start as start_mod

        monkeypatch.setattr(start_mod, "get_saved_font_scale", lambda: FONT_SCALE_COMPACT)

        window._apply_settings_changes()

        # Every status-bar and header label must use the resolved UI font (the
        # bug: the stylesheet pinned their font at polish time, so they kept the
        # previous scale while the table, log and menus followed).
        expected = fonts.ui_font().pointSizeF()
        for name in _STATUS_BAR_AND_HEADER:
            assert getattr(window, name).font().pointSizeF() == pytest.approx(expected), name

    def test_the_explicit_fonts_are_re_applied_after_the_reset(
        self, window, monkeypatch, app_fonts
    ):
        import hsync_desktop.main_window.start as start_mod

        monkeypatch.setattr(start_mod, "get_saved_font_scale", lambda: FONT_SCALE_COMPACT)

        window._apply_settings_changes()

        assert window._file_panel.table.font().pointSizeF() == pytest.approx(
            fonts.table_font().pointSizeF()
        )
        assert window._log_view.font().pointSizeF() == pytest.approx(
            fonts.log_monospace_font().pointSizeF()
        )
        assert window.menuBar().font().pointSizeF() == pytest.approx(fonts.ui_font().pointSizeF())

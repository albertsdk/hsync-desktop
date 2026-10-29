# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The Settings dialog scrolls tall pages and stays within the screen.

A tall Advanced page must not force a tall, fixed window: every tab page scrolls,
and ``finalize_size`` clamps the resizable dialog to the screen.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QBoxLayout, QPushButton, QScrollArea

import hsync_desktop.i18n as i18n_module
import hsync_desktop.settings.tab_builders as tab_builders
from hsync_desktop.i18n import get_language, set_language
from hsync_desktop.settings.dialog import _P2P_TAB_INDEX, _SERVER_TAB_INDEX


class TestScrollableTabs:
    def test_every_tab_page_scrolls(self, dialog):
        for index in range(dialog._tabs.count()):
            page = dialog._tabs.widget(index)
            assert page is not None
            assert page.findChild(QScrollArea) is not None, f"tab {index} has no scroll area"


class TestResizableDialog:
    def test_minimum_width_covers_the_content_and_description_cap(self, dialog):
        # tests/test_settings_tab_descriptions.py requires
        # label.maximumWidth() < dialog.minimumWidth(); the content only raises
        # the minimum above the historical 640 px floor.
        assert dialog.minimumWidth() >= 640

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


class TestFitCurrentTab:
    """A tab whose content fits the screen grows the dialog instead of scrolling."""

    def test_grows_to_remove_the_scrollbar_when_content_fits(self, qtbot, dialog, monkeypatch):
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(4000, 4000))
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(10)
        dialog.resize(800, 320)

        tab_builders.fit_current_tab(dialog)

        scroll = dialog._tabs.currentWidget().findChild(QScrollArea)
        assert scroll.verticalScrollBar().maximum() == 0
        assert dialog.height() > 320

    def test_never_exceeds_the_screen(self, qtbot, dialog, monkeypatch):
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(1024, 600))
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(10)
        dialog.resize(800, 300)

        tab_builders.fit_current_tab(dialog)

        assert dialog.height() <= int(600 * 0.9)


class TestContentWidth:
    """The dialog is wide enough for every tab's content (no clipped controls)."""

    def test_width_fits_the_p2p_test_button(self, qtbot, dialog, monkeypatch):
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(4000, 4000))
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(10)
        index = next(
            i
            for i in range(dialog._tabs.count())
            if dialog._tabs.widget(i).isAncestorOf(dialog.btn_test_connection)
        )
        dialog._tabs.setCurrentIndex(index)
        dialog.setMinimumWidth(640)
        dialog.resize(640, dialog.height())

        tab_builders.fit_current_tab(dialog)

        scroll = dialog._tabs.currentWidget().findChild(QScrollArea)
        assert dialog.width() >= scroll.widget().sizeHint().width()
        assert dialog.minimumWidth() >= scroll.widget().sizeHint().width()

    def test_the_trust_action_rows_are_not_clipped(self, qtbot, dialog, monkeypatch, tmp_path):
        """Both mode tabs fit their button pair in every locale.

        The pair is added as a spanning form row: the field column is only as
        wide as the caption column leaves it, which used to clip the labels.
        """
        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(4000, 4000))
        store = QSettings(str(tmp_path / "lang.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(i18n_module, "QSettings", lambda *a, **k: store)
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(10)
        pairs = (
            (_P2P_TAB_INDEX, (dialog.btn_manage_trusted_keys, dialog.btn_test_rendezvous)),
            (
                _SERVER_TAB_INDEX,
                (dialog.btn_manage_trusted_keys_server, dialog.btn_test_connection),
            ),
        )
        previous = get_language()
        try:
            for lang in ("en", "it", "de", "es", "ru"):
                set_language(lang)
                dialog._apply_translations()
                for index, buttons in pairs:
                    dialog._tabs.setCurrentIndex(index)
                    qtbot.wait(5)
                    for button in buttons:
                        assert button.width() >= button.sizeHint().width(), (
                            lang,
                            button.text(),
                        )
        finally:
            set_language(previous)
            dialog._apply_translations()


class TestActionRow:
    """The button pair stacks instead of clipping when one row is too narrow."""

    def test_the_row_stacks_and_unstacks_with_the_available_width(self, qtbot, monkeypatch):
        """The direction follows the width the form gives the row.

        The width is supplied instead of resized: a visible top-level widget is
        sized by its own layout, which would defeat the harness.
        """
        from hsync_desktop.settings.form_helpers import _action_row

        first, second = QPushButton("Manage trusted servers"), QPushButton("Test Connection")
        row = _action_row(first, second)
        qtbot.addWidget(row)
        pair_need = first.sizeHint().width() + second.sizeHint().width() + row.layout().spacing()

        monkeypatch.setattr(type(row), "width", lambda self: pair_need - 40)
        row._apply_direction()
        assert row.layout().direction() == QBoxLayout.Direction.TopToBottom

        monkeypatch.setattr(type(row), "width", lambda self: pair_need + 200)
        row._apply_direction()
        assert row.layout().direction() == QBoxLayout.Direction.LeftToRight

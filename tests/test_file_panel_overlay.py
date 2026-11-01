# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the busy overlay: the scan mode and the import mode it shares."""

from __future__ import annotations

from hsync_common.format import format_bytes

from hsync_desktop.file_panel.import_ops import CopyProgress, ImportPhase
from hsync_desktop.file_panel.overlay import LoadingOverlay
from hsync_desktop.i18n import tr


def _progress(**overrides) -> CopyProgress:
    """A copy of the current item, with only the fields a test cares about."""
    values: dict = {
        "phase": ImportPhase.COPY,
        "items_done": 0,
        "items_total": 1,
        "files_done": 0,
        "bytes_done": 0,
        "files_total": None,
        "bytes_total": None,
    }
    values.update(overrides)
    return CopyProgress(**values)


class TestScanMode:
    def test_scan_shows_a_determinate_bar_without_cancel(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_loading()
        assert not overlay.isHidden()
        assert overlay._cancel_button.isHidden()
        assert overlay._detail.isHidden()
        overlay.set_progress(3, 10)
        assert (overlay._progress.value(), overlay._progress.maximum()) == (3, 10)
        assert "(3/10)" in overlay._label.text()


class TestImportMode:
    def test_known_totals_make_the_bar_determinate(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress(files_done=1, bytes_done=10, files_total=5, bytes_total=100))
        assert not overlay.isHidden()
        assert not overlay._cancel_button.isHidden()
        assert (overlay._progress.value(), overlay._progress.maximum()) == (10, 100)
        assert overlay._detail.text() == tr("loading.import_progress_total").format(
            files=1, total_files=5, size=format_bytes(10), total_size=format_bytes(100)
        )

    def test_unknown_totals_keep_the_bar_busy(self, qtbot):
        """No total, no percentage: the bar must not promise a figure."""
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress(phase=ImportPhase.SCAN, files_done=3, bytes_done=500))
        assert (overlay._progress.minimum(), overlay._progress.maximum()) == (0, 0)
        assert overlay._label.text() == tr("loading.import_scan")
        assert overlay._detail.text() == tr("loading.import_progress").format(
            files=3, size=format_bytes(500)
        )

    def test_a_multi_item_batch_reports_the_item_position(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress(items_done=1, items_total=3, files_done=2))
        assert overlay._detail.text().startswith(tr("loading.import_items").format(done=1, total=3))

    def test_the_bar_falls_back_to_files_when_the_bytes_are_zero(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress(files_done=1, files_total=5, bytes_total=0))
        assert (overlay._progress.value(), overlay._progress.maximum()) == (1, 5)

    def test_cancel_click_emits_once_and_disables_the_button(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress())
        seen: list = []
        overlay.cancel_requested.connect(lambda: seen.append(1))
        overlay._cancel_button.click()
        overlay._cancel_button.click()  # disabled: a second request is refused
        assert len(seen) == 1
        assert not overlay._cancel_button.isEnabled()

    def test_a_progress_update_does_not_re_arm_cancel(self, qtbot):
        """Re-enabling on render would hide that the request was taken."""
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress())
        overlay._cancel_button.click()
        overlay.show_import(_progress(files_done=1, files_total=2, bytes_total=4))
        assert not overlay._cancel_button.isEnabled()

    def test_reset_cancel_re_arms_the_button_for_the_next_batch(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress())
        overlay._cancel_button.click()
        overlay.reset_cancel()
        assert overlay._cancel_button.isEnabled()

    def test_the_scan_takes_the_widget_back_from_the_import(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress(files_total=2, bytes_total=4))
        overlay.show_loading()
        assert overlay._cancel_button.isHidden()
        assert overlay._detail.isHidden()
        assert overlay._label.text() == tr("loading.files")

    def test_hide_loading_hides_the_widget(self, qtbot):
        overlay = LoadingOverlay()
        qtbot.addWidget(overlay)
        overlay.show_import(_progress())
        overlay.hide_loading()
        assert overlay.isHidden()

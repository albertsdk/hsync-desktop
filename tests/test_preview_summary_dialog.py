# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the preview confirmation: plan model, wording, layout, buttons."""

from __future__ import annotations

from hsync_common.format import format_bytes
from PySide6.QtWidgets import QPushButton, QTreeWidgetItem

from hsync_desktop.i18n import tr
from hsync_desktop.preview_summary_dialog import (
    DETAIL_CAP,
    LARGEST_CAP,
    PreviewItem,
    PreviewStats,
    PreviewSummaryDialog,
    _format_time,
)


def _stats(**counts: int) -> PreviewStats:
    stats = PreviewStats()
    for key, value in counts.items():
        setattr(stats, key, value)
    return stats


def _button_texts(dialog: PreviewSummaryDialog) -> list[str]:
    return [button.text() for button in dialog.findChildren(QPushButton)]


def _groups(dialog: PreviewSummaryDialog) -> list[str]:
    tree = dialog._tree
    return [tree.topLevelItem(index).text(0) for index in range(tree.topLevelItemCount())]


def _children(group_item: QTreeWidgetItem) -> list[tuple[str, str]]:
    return [
        (group_item.child(index).text(0), group_item.child(index).text(1))
        for index in range(group_item.childCount())
    ]


class TestPlanModel:
    """PreviewStats is the plan: counts, sizes, bounded detail lists."""

    def test_transfers_keep_counts_sizes_and_the_largest_first(self):
        stats = PreviewStats()
        stats.record_transfer("download", "small.bin", 1)
        stats.record_transfer("download", "big.bin", 100)
        stats.record_transfer("upload", "middle.bin", 50)

        assert (stats.to_download, stats.download_size) == (2, 101)
        assert (stats.to_upload, stats.upload_size) == (1, 50)
        assert [item.path for item in stats.largest] == ["big.bin", "middle.bin", "small.bin"]
        assert stats.transfer_size == 151
        assert stats.action_count == 3

    def test_the_largest_list_is_bounded(self):
        stats = PreviewStats()
        for index in range(LARGEST_CAP + 5):
            stats.record_transfer("upload", f"f{index}", index)

        assert len(stats.largest) == LARGEST_CAP
        assert stats.to_upload == LARGEST_CAP + 5
        assert stats.largest[0].size == LARGEST_CAP + 4

    def test_deletions_and_renames_are_counted_and_listed(self):
        stats = PreviewStats()
        stats.record_delete("gone.bin", 12)
        stats.record_rename("old.bin", "new.bin")

        assert (stats.to_delete, stats.delete_size) == (1, 12)
        assert stats.deletes == [PreviewItem("delete", "gone.bin", 12)]
        assert stats.renames == [PreviewItem("rename", "new.bin", src="old.bin")]
        assert stats.truncated_deletes() == 0

    def test_the_detail_lists_are_bounded_but_the_counts_are_exact(self):
        stats = PreviewStats()
        for index in range(DETAIL_CAP + 3):
            stats.record_delete(f"f{index}", 1)

        assert len(stats.deletes) == DETAIL_CAP
        assert stats.to_delete == DETAIL_CAP + 3
        assert stats.truncated_deletes() == 3

    def test_reset_forgets_everything(self):
        stats = PreviewStats()
        stats.record_transfer("download", "a", 1)
        stats.record_delete("b", 2)
        stats.record_rename("c", "d")
        stats.skipped_deletes = 4
        stats.guard_deletes = 5
        stats.guard_local = 6
        stats.synced = 7

        stats.reset()

        assert stats == PreviewStats()

    def test_has_work_follows_every_action_kind(self):
        assert not PreviewStats().has_work()
        for field in ("to_download", "to_upload", "to_delete", "to_rename"):
            stats = PreviewStats()
            setattr(stats, field, 1)
            assert stats.has_work(), field


class TestButtons:
    """Applying a plan is never the default; a simulation cannot apply it."""

    def test_simulation_replaces_sync_with_close(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=2), simulation=True)
        qtbot.addWidget(dialog)

        assert _button_texts(dialog) == [tr("preview_summary.close")]
        assert dialog.windowTitle().endswith(tr("simulation.window_title_suffix"))
        assert tr("preview_summary.simulation") in dialog._lbl_context.text()

    def test_a_real_run_makes_cancel_the_default(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=2))
        qtbot.addWidget(dialog)

        assert _button_texts(dialog) == [
            tr("preview_summary.cancel"),
            tr("preview_summary.sync"),
        ]
        assert dialog.windowTitle() == tr("preview_summary.title")
        buttons = dialog._button_box.buttons()
        defaults = [button for button in buttons if button.isDefault()]
        assert [button.text() for button in defaults] == [tr("preview_summary.cancel")]

    def test_nothing_to_do_keeps_ok_in_both_modes(self, qtbot):
        for simulation in (False, True):
            dialog = PreviewSummaryDialog(PreviewStats(), simulation=simulation)
            qtbot.addWidget(dialog)

            assert _button_texts(dialog) == [tr("preview_summary.ok")]


class TestSummary:
    """One line states how many changes and how much data they move."""

    def test_the_summary_counts_every_action_and_the_transfer_size(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("download", "a", 1000)
        stats.record_delete("b", 500)
        stats.record_rename("c", "d")
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        text = dialog._lbl_summary.text()
        assert tr("preview_summary.summary_changes").format(count=3) in text
        assert format_bytes(1000) in text

    def test_the_footnote_reports_the_already_synced_files(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=1, synced=120))
        qtbot.addWidget(dialog)

        assert dialog._lbl_footnote.isVisibleTo(dialog)
        assert f"{tr('preview_summary.synced')}: 120" == dialog._lbl_footnote.text()

    def test_without_synced_files_the_footnote_is_hidden(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=1))
        qtbot.addWidget(dialog)

        assert not dialog._lbl_footnote.isVisibleTo(dialog)


class TestContext:
    """Scope, direction, simulation and kept deletions are stated once."""

    def test_the_scope_and_the_direction_are_named(self, qtbot):
        dialog = PreviewSummaryDialog(
            _stats(to_upload=1), direction="upload-only", scope="photos/2024"
        )
        qtbot.addWidget(dialog)

        context = dialog._lbl_context.text()
        assert tr("preview_summary.context_scope").format(path="photos/2024") in context
        assert tr("menu.sync.direction.upload_only") in context

    def test_a_bidirectional_run_states_no_direction(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=1))
        qtbot.addWidget(dialog)

        assert not dialog._lbl_context.isVisibleTo(dialog)

    def test_kept_deletions_are_reported(self, qtbot):
        stats = _stats(to_upload=1, skipped_deletes=3)
        dialog = PreviewSummaryDialog(stats, deletions_kept=True)
        qtbot.addWidget(dialog)

        assert tr("preview_summary.skipped_deletions").format(count=3) in (
            dialog._lbl_context.text()
        )


class TestWarnings:
    """A destructive plan says so; a plan the guard will pause says that too."""

    def test_planned_deletions_raise_a_warning(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_delete=3))
        qtbot.addWidget(dialog)

        assert dialog._lbl_warning.isVisibleTo(dialog)
        assert tr("preview_summary.warning_delete").format(count=3) in (dialog._lbl_warning.text())

    def test_the_guard_warning_takes_precedence(self, qtbot):
        stats = _stats(to_delete=3, guard_deletes=3, guard_local=10)
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        assert tr("preview_summary.warning_guard").format(deletes=3, local=10) in (
            dialog._lbl_warning.text()
        )

    def test_without_deletions_there_is_no_warning(self, qtbot):
        dialog = PreviewSummaryDialog(_stats(to_upload=2))
        qtbot.addWidget(dialog)

        assert not dialog._lbl_warning.isVisibleTo(dialog)


class TestDetails:
    """Only the sections with work appear, destructive first, transfers by size."""

    def test_only_the_populated_sections_are_listed(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("download", "a.bin", 10)
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        assert _groups(dialog) == [f"{tr('preview_summary.downloads')}: 1 · {format_bytes(10)}"]
        assert dialog._tree.isVisibleTo(dialog)

    def test_the_destructive_section_comes_first(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("download", "a.bin", 10)
        stats.record_delete("gone.bin", 4)
        stats.record_rename("old.bin", "new.bin")
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        labels = [group.split(":", 1)[0] for group in _groups(dialog)]
        assert labels == [
            tr("preview_summary.deletions"),
            tr("preview_summary.renames"),
            tr("preview_summary.downloads"),
        ]
        assert _children(dialog._tree.topLevelItem(0)) == [
            ("gone.bin", format_bytes(4)),
        ]
        assert _children(dialog._tree.topLevelItem(1)) == [("old.bin → new.bin", "")]

    def test_the_transfer_rows_are_the_largest_first(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("download", "small.bin", 1)
        stats.record_transfer("download", "big.bin", 1024)
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        assert _children(dialog._tree.topLevelItem(0)) == [
            ("big.bin", format_bytes(1024)),
            ("small.bin", format_bytes(1)),
        ]

    def test_the_truncated_rows_are_counted(self, qtbot):
        stats = PreviewStats()
        for index in range(DETAIL_CAP + 2):
            stats.record_delete(f"f{index}", 1)
        dialog = PreviewSummaryDialog(stats)
        qtbot.addWidget(dialog)

        rows = _children(dialog._tree.topLevelItem(0))
        assert rows[-1] == (tr("preview_summary.more_items").format(count=2), "")

    def test_no_details_without_work(self, qtbot):
        dialog = PreviewSummaryDialog(PreviewStats())
        qtbot.addWidget(dialog)

        assert not dialog._tree.isVisibleTo(dialog)


class TestEstimate:
    """The estimate uses the configured limit, and states its basis."""

    def test_a_limited_run_reports_the_estimate_and_the_rate(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("download", "a.bin", 5_000_000)
        dialog = PreviewSummaryDialog(stats, download_bps=1_000_000)
        qtbot.addWidget(dialog)

        header = _groups(dialog)[0]
        assert (
            tr("preview_summary.estimate").format(
                time=_format_time(5), rate=format_bytes(1_000_000)
            )
            in header
        )

    def test_without_a_limit_there_is_no_estimate(self, qtbot):
        stats = PreviewStats()
        stats.record_transfer("upload", "a.bin", 5_000_000)
        dialog = PreviewSummaryDialog(stats, upload_bps=None)
        qtbot.addWidget(dialog)

        assert "≈" not in _groups(dialog)[0]

    def test_the_time_drops_empty_sub_units(self):
        assert "0 " not in _format_time(120)
        assert _format_time(3660).startswith("1 ")

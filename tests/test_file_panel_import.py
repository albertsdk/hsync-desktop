# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for drag & drop import (import_ops, ImportWorker, table and panel)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from hsync_desktop.file_panel.import_ops import (
    CopyProgress,
    ImportItem,
    ImportPhase,
    copy_tree,
    count_tree,
    destination_for,
    target_rel_dir,
    unique_name,
    validate_sources,
)
from hsync_desktop.file_panel.models import FileTransfer, TransferStatus
from hsync_desktop.file_panel.workers import ImportWorker
from hsync_desktop.i18n import tr


class TestHelpers:
    def test_target_prefers_hovered_folder(self):
        assert target_rel_dir("docs", "photos") == "docs"

    def test_target_falls_back_to_current_folder(self):
        assert target_rel_dir(None, "photos") == "photos"

    def test_target_strips_separators(self):
        assert target_rel_dir("/docs/", "") == "docs"

    def test_destination_root_and_subdir(self, tmp_path):
        base = str(tmp_path)
        assert destination_for(base, "", os.path.join(base, "a.txt")) == os.path.join(base, "a.txt")
        assert destination_for(base, "docs", "/elsewhere/a.txt") == os.path.join(
            base, "docs", "a.txt"
        )

    def test_unique_name_free_path_unchanged(self, tmp_path):
        target = str(tmp_path / "new.txt")
        assert unique_name(target) == target

    def test_unique_name_increments(self, tmp_path):
        target = tmp_path / "report.pdf"
        target.write_text("x")
        (tmp_path / "report (1).pdf").write_text("x")
        assert unique_name(str(target)) == str(tmp_path / "report (2).pdf")

    def test_validate_accepts_a_new_file(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        accepted, rejected = validate_sources(str(base), "", [str(src)])
        assert accepted == [os.path.normpath(str(src))]
        assert rejected == []

    def test_validate_rejects_missing(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        accepted, rejected = validate_sources(str(base), "", [str(tmp_path / "gone.txt")])
        assert accepted == []
        assert rejected[0][1] == "missing"

    def test_validate_rejects_internal_name(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        src = tmp_path / ".hsyncfolder"
        src.write_text("uuid")
        accepted, rejected = validate_sources(str(base), "", [str(src)])
        assert accepted == []
        assert rejected[0][1] == "internal"

    def test_validate_rejects_same_path(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        src = base / "f.txt"
        src.write_text("x")
        accepted, rejected = validate_sources(str(base), "", [str(src)])
        assert accepted == []
        assert rejected[0][1] == "same"

    def test_validate_rejects_the_share_itself(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        accepted, rejected = validate_sources(str(base), "", [str(base)])
        assert accepted == []
        assert rejected[0][1] == "recursive"

    def test_validate_rejects_symlink_escape(self, tmp_path):
        base = tmp_path / "share"
        base.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        try:
            (base / "link").symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks not supported on this platform")
        src = tmp_path / "x.txt"
        src.write_text("x")
        accepted, rejected = validate_sources(str(base), "link", [str(src)])
        assert accepted == []
        assert rejected[0][1] == "outside"


class TestTreeHelpers:
    """The per-file progress the worker reports is computed by these two."""

    def _tree(self, root):
        (root / "sub").mkdir(parents=True)
        (root / "a.txt").write_text("abc")
        (root / "sub" / "b.txt").write_text("de")
        return root

    def test_count_tree_counts_files_and_bytes(self, tmp_path):
        tree = self._tree(tmp_path / "folder")
        assert count_tree(str(tree), budget_s=None) == (2, 5, True)

    def test_count_tree_reports_an_incomplete_walk_past_its_budget(self, tmp_path, monkeypatch):
        tree = self._tree(tmp_path / "folder")
        # Check the budget on every entry, so an already-spent one is caught on
        # the first file instead of after the default 256.
        monkeypatch.setattr("hsync_desktop.file_panel.import_ops._COUNT_CHECK_EVERY", 1)
        files, _size, complete = count_tree(str(tree), budget_s=-1)
        assert complete is False
        assert files < 2

    def test_count_tree_reports_an_incomplete_walk_when_cancelled(self, tmp_path):
        tree = self._tree(tmp_path / "folder")
        assert count_tree(str(tree), should_cancel=lambda: True) == (0, 0, False)

    def test_copy_tree_copies_and_reports_each_file(self, tmp_path):
        tree = self._tree(tmp_path / "folder")
        dest = tmp_path / "share" / "folder"
        (tmp_path / "share").mkdir()
        seen: list = []
        files, complete = copy_tree(
            str(tree), str(dest), on_file=lambda done, size: seen.append((done, size))
        )
        assert (files, complete) == (2, True)
        assert (dest / "sub" / "b.txt").read_text() == "de"
        assert seen == [(1, 3), (2, 5)]

    def test_copy_tree_refuses_an_existing_destination(self, tmp_path):
        """Same contract as ``shutil.copytree`` without ``dirs_exist_ok``."""
        tree = self._tree(tmp_path / "folder")
        dest = tmp_path / "share" / "folder"
        dest.mkdir(parents=True)
        with pytest.raises(FileExistsError):
            copy_tree(str(tree), str(dest))

    def test_copy_tree_refuses_a_source_that_vanished(self, tmp_path):
        """No empty copy is left behind when the dropped folder is gone."""
        dest = tmp_path / "share" / "folder"
        (tmp_path / "share").mkdir()
        with pytest.raises(FileNotFoundError):
            copy_tree(str(tmp_path / "gone"), str(dest))
        assert not dest.exists()

    def test_copy_tree_reports_an_incomplete_copy_when_cancelled(self, tmp_path):
        tree = self._tree(tmp_path / "folder")
        dest = tmp_path / "share" / "folder"
        (tmp_path / "share").mkdir()
        assert copy_tree(str(tree), str(dest), should_cancel=lambda: True) == (0, False)

    def test_copy_tree_keeps_directory_metadata(self, tmp_path):
        tree = self._tree(tmp_path / "folder")
        os.utime(tree / "sub", (1_000_000, 1_000_000))
        os.utime(tree, (1_000_001, 1_000_001))
        dest = tmp_path / "share" / "folder"
        (tmp_path / "share").mkdir()
        copy_tree(str(tree), str(dest))
        assert int(os.stat(dest / "sub").st_mtime) == 1_000_000
        assert int(os.stat(dest).st_mtime) == 1_000_001


class TestImportWorker:
    def test_copies_a_file(self, qtbot, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("hello")
        dest = tmp_path / "share" / "a.txt"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        results: list = []
        worker.finished.connect(lambda *args: results.append(args))
        worker.run()
        assert dest.read_text() == "hello"
        assert src.exists()  # a copy keeps the source
        assert results == [(1, 0, [], False)]

    def test_moves_a_file(self, qtbot, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("hello")
        dest = tmp_path / "share" / "a.txt"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=True)])
        worker.run()
        assert dest.read_text() == "hello"
        assert not src.exists()

    def test_copies_a_directory(self, qtbot, tmp_path):
        src = tmp_path / "folder"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "a.txt").write_text("x")
        dest = tmp_path / "share" / "folder"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        worker.run()
        assert (dest / "sub" / "a.txt").read_text() == "x"

    def test_one_failure_does_not_stop_the_rest(self, qtbot, tmp_path):
        good = tmp_path / "good.txt"
        good.write_text("x")
        missing = tmp_path / "missing.txt"  # never created
        dest_dir = tmp_path / "share"
        worker = ImportWorker(
            [
                ImportItem(str(missing), str(dest_dir / "missing.txt"), move=False),
                ImportItem(str(good), str(dest_dir / "good.txt"), move=False),
            ]
        )
        results: list = []
        worker.finished.connect(lambda *args: results.append(args))
        worker.run()
        imported, failed, errors, cancelled = results[0]
        assert (imported, failed) == (1, 1)
        assert cancelled is False
        assert (dest_dir / "good.txt").read_text() == "x"
        assert len(errors) == 1

    def test_run_reports_finished_once_even_when_every_item_fails(
        self, qtbot, tmp_path, monkeypatch
    ):
        """The batch reports failed items and still emits ``finished`` once."""
        src = tmp_path / "a.txt"
        src.write_text("x")
        dest = tmp_path / "share" / "a.txt"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        results: list = []
        worker.finished.connect(lambda *args: results.append(args))

        def boom(*_args) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(worker, "_perform", boom)

        worker.run()

        assert len(results) == 1
        assert results[0][:2] == (0, 1)

    def test_directory_import_reports_file_progress(self, qtbot, tmp_path):
        """A dropped folder is one item: its files must still move the bar."""
        src = tmp_path / "folder"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_text("abc")
        (src / "sub" / "b.txt").write_text("de")
        dest = tmp_path / "share" / "folder"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        seen: list = []
        worker.progress.connect(seen.append)
        worker.run()
        assert seen
        last = seen[-1]
        assert last.phase is ImportPhase.COPY
        assert (last.files_done, last.files_total) == (2, 2)
        assert (last.bytes_done, last.bytes_total) == (5, 5)

    def test_a_move_is_reported_as_an_indeterminate_phase(self, qtbot, tmp_path):
        src = tmp_path / "folder"
        src.mkdir()
        (src / "a.txt").write_text("abc")
        dest = tmp_path / "share" / "folder"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=True)])
        seen: list = []
        worker.progress.connect(seen.append)
        worker.run()
        assert any(entry.phase is ImportPhase.MOVE for entry in seen)
        # A move is a rename the worker cannot measure: no total is promised.
        assert all(entry.bytes_total is None for entry in seen)

    def test_cancel_before_the_first_item_imports_nothing(self, qtbot, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x")
        dest = tmp_path / "share" / "a.txt"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        results: list = []
        worker.finished.connect(lambda *args: results.append(args))
        worker.cancel()
        worker.run()
        assert not dest.exists()
        assert results == [(0, 0, [], True)]

    def test_a_tree_interrupted_by_a_cancel_is_not_counted_as_imported(
        self, qtbot, tmp_path, monkeypatch
    ):
        src = tmp_path / "folder"
        src.mkdir()
        (src / "a.txt").write_text("x")
        dest = tmp_path / "share" / "folder"
        worker = ImportWorker([ImportItem(str(src), str(dest), move=False)])
        results: list = []
        worker.finished.connect(lambda *args: results.append(args))

        def cancelled_copy(*_args, **_kwargs) -> tuple[int, bool]:
            worker.cancel()
            return 1, False

        monkeypatch.setattr("hsync_desktop.file_panel.workers.copy_tree", cancelled_copy)
        worker.run()
        # Partially written: neither imported nor failed.
        assert results == [(0, 0, [], True)]


class TestTableDrop:
    def _drop(self, table, sources, action=Qt.DropAction.CopyAction):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(s) for s in sources])
        event = QDropEvent(
            QPointF(5, 5),
            action,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        table.dropEvent(event)
        return event

    def test_drop_emits_accepted_sources_and_target(self, window, tmp_path):
        table = window._file_panel._table
        base = tmp_path / "share"
        base.mkdir()
        table.set_base_directory(str(base))
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        seen: list = []
        table.files_dropped.connect(lambda *args: seen.append(args))
        self._drop(table, [str(src)])
        assert seen == [([os.path.normpath(str(src))], "", "copy")]

    def test_move_action_is_reported(self, window, tmp_path):
        table = window._file_panel._table
        base = tmp_path / "share"
        base.mkdir()
        table.set_base_directory(str(base))
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        seen: list = []
        table.files_dropped.connect(lambda *args: seen.append(args))
        self._drop(table, [str(src)], action=Qt.DropAction.MoveAction)
        assert seen[0][2] == "move"

    def test_drop_without_base_directory_is_ignored(self, window, tmp_path):
        table = window._file_panel._table
        table.set_base_directory("")
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        seen: list = []
        table.files_dropped.connect(lambda *args: seen.append(args))
        self._drop(table, [str(src)])
        assert seen == []

    def test_drop_refused_while_disabled(self, window, tmp_path):
        table = window._file_panel._table
        base = tmp_path / "share"
        base.mkdir()
        table.set_base_directory(str(base))
        table.set_drop_enabled(False)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        seen: list = []
        table.files_dropped.connect(lambda *args: seen.append(args))
        self._drop(table, [str(src)])
        assert seen == []

    def test_folder_row_resolves_the_target(self, window):
        table = window._file_panel._table
        table.set_base_directory("/base")
        table.clear_transfers()
        table.add_transfers_batch(
            [
                FileTransfer(
                    filepath="docs/file.txt", direction="—", size=1, status=TransferStatus.LOCAL
                )
            ]
        )
        table.refresh_view()
        assert table._folder_rel_at_row(0) == "docs"
        assert table._drop_target_rel(QPoint(-10, -10)) == table.current_path


class TestPanelImport:
    def _panel(self, window):
        return window._file_panel

    def test_invalid_drop_reports_a_warning(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        started = []
        monkeypatch.setattr(panel, "_start_import", started.append)
        messages: list = []
        panel.import_finished.connect(lambda *args: messages.append(args))
        internal = tmp_path / ".hsyncfolder"
        internal.write_text("uuid")
        panel._on_files_dropped([str(internal)], "", "copy")
        assert started == []
        assert messages and messages[0][1] == "warning"

    def test_copy_requests_are_resolved_and_started(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        captured: list = []
        monkeypatch.setattr(panel, "_start_import", captured.append)
        panel._on_files_dropped([str(src)], "", "copy")
        assert len(captured) == 1
        items = captured[0]
        assert items == [
            ImportItem(os.path.normpath(str(src)), str(base / "incoming.txt"), move=False)
        ]

    def test_conflict_keep_both_uses_a_unique_name(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        (base / "incoming.txt").write_text("existing")
        panel._current_directory = str(base)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        monkeypatch.setattr(panel, "_ask_conflict", lambda *_a: ("keepboth", False))
        captured: list = []
        monkeypatch.setattr(panel, "_start_import", captured.append)
        panel._on_files_dropped([str(src)], "", "copy")
        assert captured[0] == [
            ImportItem(os.path.normpath(str(src)), str(base / "incoming (1).txt"), move=False)
        ]

    def test_conflict_skip_imports_nothing(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        (base / "incoming.txt").write_text("existing")
        panel._current_directory = str(base)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        monkeypatch.setattr(panel, "_ask_conflict", lambda *_a: ("skip", False))
        captured: list = []
        monkeypatch.setattr(panel, "_start_import", captured.append)
        panel._on_files_dropped([str(src)], "", "copy")
        assert captured == []

    def test_move_requires_confirmation(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        captured: list = []
        monkeypatch.setattr(panel, "_start_import", captured.append)
        monkeypatch.setattr(panel, "_confirm_move", lambda *_a: False)
        panel._on_files_dropped([str(src)], "", "move")
        assert captured == []
        monkeypatch.setattr(panel, "_confirm_move", lambda *_a: True)
        panel._on_files_dropped([str(src)], "", "move")
        assert captured and captured[0][0].move is True

    def test_import_runs_and_reports_success(self, window, qtbot, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        monkeypatch.setattr(panel, "load_local_files", lambda *a, **k: None)
        with qtbot.waitSignal(panel.import_finished, timeout=5000) as blocker:
            panel._on_files_dropped([str(src)], "", "copy")
        assert (base / "incoming.txt").read_text() == "hi"
        assert src.exists()
        assert blocker.args[1] == "success"

    def test_drop_ignored_while_importing(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        panel._importing = True
        captured: list = []
        monkeypatch.setattr(panel, "_start_import", captured.append)
        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        panel._on_files_dropped([str(src)], "", "copy")
        assert captured == []

    def test_import_shows_a_busy_indicator_until_it_finishes(
        self, window, qtbot, tmp_path, monkeypatch
    ):
        """The drop is acknowledged at once, not only when the copy is over."""
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        panel._current_directory = str(base)
        src = tmp_path / "folder"
        src.mkdir()
        (src / "a.txt").write_text("x")
        monkeypatch.setattr(panel, "load_local_files", lambda *a, **k: None)
        panel._loading_overlay._cancel_button.setEnabled(False)
        panel._on_files_dropped([str(src)], "", "copy")
        assert not panel._loading_overlay.isHidden()
        # A new batch re-arms Cancel, which the previous one left disabled.
        assert panel._loading_overlay._cancel_button.isEnabled()
        qtbot.waitUntil(lambda: not panel._importing, timeout=5000)
        assert panel._loading_overlay.isHidden()

    def test_a_scan_ending_mid_import_keeps_the_import_indicator(self, window):
        """The overlay is shared: the scan must not hide the import's state."""
        panel = self._panel(window)
        panel._importing = True
        panel._import_progress = CopyProgress(
            phase=ImportPhase.SCAN,
            items_done=0,
            items_total=1,
            files_done=0,
            bytes_done=0,
        )
        panel._overlay_scan_active = True
        panel._sync_loading_overlay()
        panel._on_scan_finished()
        assert not panel._loading_overlay.isHidden()
        assert panel._loading_overlay._label.text() == tr("loading.import_scan")

    def test_progress_updates_the_indicator(self, window):
        panel = self._panel(window)
        panel._importing = True
        panel._on_import_progress(
            CopyProgress(
                phase=ImportPhase.COPY,
                items_done=1,
                items_total=2,
                files_done=7,
                bytes_done=10,
                files_total=9,
                bytes_total=20,
            )
        )
        overlay = panel._loading_overlay
        assert not overlay.isHidden()
        assert overlay._label.text() == tr("loading.import_copy")
        assert (overlay._progress.value(), overlay._progress.maximum()) == (10, 20)

    def test_cancel_button_asks_the_worker_to_stop(self, window):
        panel = self._panel(window)
        worker = MagicMock()
        panel._import_worker = worker
        panel._loading_overlay._cancel_button.click()
        worker.cancel.assert_called_once_with()
        panel._import_worker = None

    def test_a_cancelled_import_reports_it_instead_of_success(self, window, tmp_path, monkeypatch):
        panel = self._panel(window)
        panel._current_directory = str(tmp_path)
        monkeypatch.setattr(panel, "load_local_files", lambda *a, **k: None)
        messages: list = []
        panel.import_finished.connect(lambda *args: messages.append(args))
        panel._import_progress = CopyProgress(
            phase=ImportPhase.COPY,
            items_done=1,
            items_total=3,
            files_done=2,
            bytes_done=10,
        )
        panel._on_import_finished(1, 0, [], True)
        assert messages == [
            (tr("dnd.import_cancelled").format(done=1, total=3), "warning"),
        ]

    def test_the_import_reload_keeps_the_other_rows_classified(self, window, qtbot, tmp_path):
        """Dropping a file must not turn the rest of the list "Local"."""
        panel = self._panel(window)
        base = tmp_path / "share"
        base.mkdir()
        (base / "already.txt").write_text("x")
        panel.load_local_files(str(base))
        qtbot.waitUntil(lambda: panel._scan_thread is None, timeout=5000)
        panel.update_file_status("already.txt", "synced")

        src = tmp_path / "incoming.txt"
        src.write_text("hi")
        with qtbot.waitSignal(panel.import_finished, timeout=5000):
            panel._on_files_dropped([str(src)], "", "copy")
        qtbot.waitUntil(lambda: panel._scan_thread is None, timeout=5000)

        # The row the engine had classified survives the reload; the path the
        # import just created is a placeholder until the next comparison.
        assert panel._table._transfers["already.txt"].status is TransferStatus.SYNCED
        assert panel._table._transfers["incoming.txt"].status is TransferStatus.LOCAL

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for drag & drop import (import_ops, ImportWorker, table and panel)."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from hsync_desktop.file_panel.import_ops import (
    ImportItem,
    destination_for,
    target_rel_dir,
    unique_name,
    validate_sources,
)
from hsync_desktop.file_panel.models import FileTransfer, TransferStatus
from hsync_desktop.file_panel.workers import ImportWorker


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
        assert results == [(1, 0, [])]

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
        imported, failed, errors = results[0]
        assert (imported, failed) == (1, 1)
        assert (dest_dir / "good.txt").read_text() == "x"
        assert len(errors) == 1


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

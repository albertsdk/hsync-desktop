# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Background workers for file panel.

Contains DirectoryScanWorker for scanning directories in background threads.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from hsync_common.ignore import IgnoreMatcher
from PySide6.QtCore import QObject, Signal, Slot

from hsync_desktop.config import FILE_BATCH_SIZE
from hsync_desktop.file_panel.filter import is_synced_entry
from hsync_desktop.file_panel.import_ops import ImportItem

# Minimum time between progress updates (seconds) to avoid flooding the UI
_PROGRESS_THROTTLE_MS = 100


class DirectoryScanWorker(QObject):
    """Worker that scans a directory in a background thread."""

    # Emits a batch of (filepath, size, mtime) tuples
    files_found = Signal(list)
    # Emits (processed_count, total_count) for progress
    progress = Signal(int, int)
    # Emits the accumulated local size in bytes (throttled, plus the final value)
    size_progress = Signal(int)
    # Emitted when scan is complete
    finished = Signal()

    def __init__(
        self,
        directory: str,
        matcher: IgnoreMatcher,
        *,
        emit_rows: bool = True,
    ) -> None:
        super().__init__()
        self._directory = directory
        self._matcher = matcher
        self._emit_rows = emit_rows
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the scan."""
        self._cancelled = True

    def _count_files(self) -> int:
        """Quick count of files and empty directories (without reading sizes).

        Uses os.scandir to skip symlinks, consistent with _scan_with_scandir.
        """
        count = 0
        try:
            count = self._count_dir(Path(self._directory), Path(self._directory))
        except OSError:
            pass
        return count

    def _synced_entries(
        self, dir_path: Path
    ) -> tuple[list[os.DirEntry[str]], list[os.DirEntry[str]]] | None:
        """Return the synced ``(dirs, files)`` of a directory, or ``None`` on I/O error.

        Shared by the counting and the row-emitting scans so the symlink and
        ignore-filter rules cannot drift between the two passes.
        """
        try:
            entries = list(os.scandir(dir_path))
        except OSError:
            return None
        dirs: list[os.DirEntry[str]] = []
        files: list[os.DirEntry[str]] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = not is_dir and entry.is_file(follow_symlinks=False)
            except OSError:
                continue
            if not (is_dir or is_file):
                continue
            if not is_synced_entry(self._matcher, entry.path, is_dir=is_dir):
                continue
            (dirs if is_dir else files).append(entry)
        return dirs, files

    def _count_dir(self, dir_path: Path, base_path: Path) -> int:
        """Recursively count real files and empty leaf dirs (no symlinks)."""
        if self._cancelled:
            return 0
        entries = self._synced_entries(dir_path)
        if entries is None:
            return 0
        dirs, files = entries

        # Leaf empty directory (not root)
        if not files and not dirs and str(dir_path) != str(base_path):
            return 1

        count = len(files)
        for d in dirs:
            if self._cancelled:
                return 0
            count += self._count_dir(Path(d.path), base_path)
        return count

    def _scan_with_scandir(self, base_path: Path, total: int) -> None:
        """Scan directory using os.scandir() for better performance."""
        batch: list[tuple[str, int, float]] = []
        processed = 0
        total_bytes = 0
        last_progress_time = 0.0

        def flush_batch() -> None:
            nonlocal batch, last_progress_time
            self.files_found.emit(batch)
            current_time = time.monotonic()
            if current_time - last_progress_time >= _PROGRESS_THROTTLE_MS / 1000:
                self.progress.emit(processed, total)
                self.size_progress.emit(total_bytes)
                last_progress_time = current_time
            batch = []

        def scan_directory(dir_path: Path) -> None:
            nonlocal processed, last_progress_time, batch, total_bytes

            if self._cancelled:
                return

            entries = self._synced_entries(dir_path)
            if entries is None:
                return
            dirs, files = entries

            # Handle empty directories (leaf dirs)
            if self._emit_rows and not files and not dirs and str(dir_path) != str(base_path):
                try:
                    stat = dir_path.stat()
                    mtime = stat.st_mtime
                except OSError:
                    mtime = 0.0
                try:
                    rel_path = str(dir_path.relative_to(base_path))
                except ValueError:
                    rel_path = str(dir_path)
                batch.append((rel_path + "/", 0, mtime))
                processed += 1

                if len(batch) >= FILE_BATCH_SIZE:
                    flush_batch()

            # Process files
            for entry in files:
                if self._cancelled:
                    return

                try:
                    stat = entry.stat(follow_symlinks=False)
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = 0.0

                total_bytes += size

                if not self._emit_rows:
                    continue

                try:
                    rel_path = str(Path(entry.path).relative_to(base_path))
                except ValueError:
                    rel_path = entry.path

                batch.append((rel_path, size, mtime))
                processed += 1

                if len(batch) >= FILE_BATCH_SIZE:
                    flush_batch()

            # Recursively scan subdirectories
            for entry in dirs:
                scan_directory(Path(entry.path))

        scan_directory(base_path)

        # Emit remaining files
        if batch and not self._cancelled:
            self.files_found.emit(batch)
            self.progress.emit(processed, total)
        if not self._cancelled:
            self.size_progress.emit(total_bytes)

    @Slot()
    def run(self) -> None:
        """Scan the directory and emit files in batches.

        With ``emit_rows=False`` the walk only accumulates the size (no counting
        pass, no ``files_found``/``progress``): the caller wants the total for the
        current folder state, not a table reload.
        """
        if not self._directory or not os.path.isdir(self._directory):
            self.finished.emit()
            return

        base_path = Path(self._directory)
        if not self._emit_rows:
            self._scan_with_scandir(base_path, 0)
            self.finished.emit()
            return

        # First pass: count files for progress
        total = self._count_files()
        if self._cancelled or total == 0:
            if not self._cancelled:
                self.size_progress.emit(0)  # empty share: a known 0 B
            self.finished.emit()
            return

        self.progress.emit(0, total)

        # Use optimized scandir-based scanner
        self._scan_with_scandir(base_path, total)

        self.finished.emit()


class ImportWorker(QObject):
    """Copy or move dropped sources into the share, off the UI thread.

    The caller resolves the target paths and the conflicts first (on the UI
    thread, where the dialogs live); this worker only performs the filesystem
    work, so it never touches a widget. Each item is isolated: one failure does
    not abort the rest, and a move never deletes a source the copy failed to
    write (``shutil.move`` handles that already).
    """

    # Emits (done, total) after each item.
    progress = Signal(int, int)
    # Emits (imported, failed, errors) once the batch is over.
    finished = Signal(int, int, list)

    def __init__(self, items: list[ImportItem]) -> None:
        super().__init__()
        self._items = list(items)
        self._cancelled = False

    def cancel(self) -> None:
        """Stop before the next item."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        imported = 0
        failed = 0
        errors: list[str] = []
        total = len(self._items)
        for index, item in enumerate(self._items, start=1):
            if self._cancelled:
                break
            try:
                self._perform(item)
                imported += 1
            except Exception as exc:  # noqa: BLE001 - report and keep going
                failed += 1
                errors.append(f"{os.path.basename(item.src)}: {exc}")
            self.progress.emit(index, total)
        self.finished.emit(imported, failed, errors)

    @staticmethod
    def _perform(item: ImportItem) -> None:
        parent = os.path.dirname(item.dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if item.move:
            shutil.move(item.src, item.dest)
        elif os.path.isdir(item.src):
            shutil.copytree(item.src, item.dest)
        else:
            shutil.copy2(item.src, item.dest)

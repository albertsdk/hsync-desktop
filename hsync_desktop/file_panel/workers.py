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
import traceback
from pathlib import Path

from hsync_common.ignore import IgnoreMatcher
from PySide6.QtCore import QObject, Signal, Slot

from hsync_desktop.config import FILE_BATCH_SIZE
from hsync_desktop.file_panel.filter import is_synced_entry
from hsync_desktop.file_panel.import_ops import (
    CopyProgress,
    ImportItem,
    ImportPhase,
    copy_tree,
    count_tree,
)

# Minimum time between progress updates (seconds) to avoid flooding the UI
_PROGRESS_THROTTLE_MS = 100


class DirectoryScanWorker(QObject):
    """Worker that scans a directory in a background thread."""

    # Emits a batch of (filepath, size, mtime) tuples
    files_found = Signal(list)
    # Emits (processed_count, total_count) for progress
    progress = Signal(int, int)
    # Emits the accumulated local size in bytes (throttled, plus the final
    # value). Carried as a Python ``int`` (via ``object``) because a share can
    # exceed the 2 GiB ceiling of a 32-bit ``Signal(int)`` — which overflowed.
    size_progress = Signal(object)
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

        ``finished`` is emitted exactly once, whatever the scan does: the caller
        joins the worker thread on it, so an unhandled error (e.g. a signal
        overflow) must never leave the thread running.
        """
        try:
            if not self._directory or not os.path.isdir(self._directory):
                return

            base_path = Path(self._directory)
            if not self._emit_rows:
                self._scan_with_scandir(base_path, 0)
                return

            # First pass: count files for progress
            total = self._count_files()
            if self._cancelled or total == 0:
                if not self._cancelled:
                    self.size_progress.emit(0)  # empty share: a known 0 B
                return

            self.progress.emit(0, total)

            # Use optimized scandir-based scanner
            self._scan_with_scandir(base_path, total)
        except Exception:
            # The scan must never strand its thread: log and still finish, so
            # the caller can join the worker. An uncaught error would escape
            # through the Qt/C++ boundary, leak a raw traceback and emit no
            # ``finished``, leaving the thread running forever.
            traceback.print_exc()
        finally:
            self.finished.emit()


class ImportWorker(QObject):
    """Copy or move dropped sources into the share, off the UI thread.

    The caller resolves the target paths and the conflicts first (on the UI
    thread, where the dialogs live); this worker only performs the filesystem
    work, so it never touches a widget. Each item is isolated: one failure does
    not abort the rest, and a move never deletes a source the copy failed to
    write (``shutil.move`` handles that already).

    Progress is reported per item *and* per file, because a dropped folder is a
    single item: a directory is counted first (within a budget) so the bar can be
    determinate when the totals are really known, and file-by-file counters keep
    it moving when they are not.
    """

    # Emits a CopyProgress carrying the advance of the whole batch.
    progress = Signal(object)
    # Emits (imported, failed, errors, cancelled) once the batch is over.
    finished = Signal(int, int, list, bool)

    def __init__(self, items: list[ImportItem]) -> None:
        super().__init__()
        self._items = list(items)
        self._cancelled = False
        self._phase = ImportPhase.SCAN
        self._items_done = 0
        self._files_done = 0
        self._bytes_done = 0
        self._files_total: int | None = None
        self._bytes_total: int | None = None
        # Counters of the tree being copied, to translate its own progress into
        # the batch's (``copy_tree`` reports per tree).
        self._tree_files = 0
        self._tree_bytes = 0
        # True when the item in flight was cut short by a cancellation: it is
        # then neither imported nor failed.
        self._interrupted = False
        self._last_emit = 0.0

    def cancel(self) -> None:
        """Stop at the next item or file boundary."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        imported = 0
        failed = 0
        errors: list[str] = []
        total = len(self._items)
        try:
            for index, item in enumerate(self._items, start=1):
                if self._cancelled:
                    break
                self._items_done = index - 1
                self._interrupted = False
                self._files_total = None
                self._bytes_total = None
                self._emit_progress(force=True)
                try:
                    self._perform(item)
                except Exception as exc:  # noqa: BLE001 - report and keep going
                    failed += 1
                    errors.append(f"{os.path.basename(item.src)}: {exc}")
                else:
                    if self._interrupted:
                        break
                    imported += 1
                # The finished item keeps its totals, so the bar stays full until
                # the next item's count resets it.
                self._items_done = index
                self._emit_progress(force=True)
        except Exception:
            # Same guarantee as DirectoryScanWorker.run: never let an unhandled
            # error escape through the Qt boundary and strand the thread.
            traceback.print_exc()
        finally:
            # Guaranteed once per run: the caller joins the thread on this.
            # "Cancelled" means the batch stopped short, not merely that a cancel
            # arrived after the last item had already been imported.
            self.finished.emit(
                imported,
                failed,
                errors,
                self._cancelled and self._items_done < total,
            )

    def _perform(self, item: ImportItem) -> None:
        parent = os.path.dirname(item.dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if item.move:
            # ``shutil.move`` is a rename while both sides share a filesystem and
            # a copy+delete otherwise, and it reports neither: the move stays an
            # indeterminate phase.
            self._set_phase(ImportPhase.MOVE)
            shutil.move(item.src, item.dest)
            self._files_done += 1
            return
        if os.path.isdir(item.src):
            self._copy_directory(item)
            return
        self._copy_file(item)

    def _copy_file(self, item: ImportItem) -> None:
        """Copy one dropped file, whose size is known up front."""
        size = os.path.getsize(item.src)
        self._files_total = 1
        self._bytes_total = size
        self._set_phase(ImportPhase.COPY)
        shutil.copy2(item.src, item.dest)
        self._files_done += 1
        self._bytes_done += size
        self._emit_progress(force=True)

    def _copy_directory(self, item: ImportItem) -> None:
        """Count a dropped folder within its budget, then copy it file by file."""
        self._set_phase(ImportPhase.SCAN)
        files, size, complete = count_tree(item.src, should_cancel=lambda: self._cancelled)
        # An incomplete count leaves the totals unknown, so the bar stays busy
        # instead of showing a percentage the worker cannot honour.
        self._files_total = files if complete else None
        self._bytes_total = size if complete else None
        self._set_phase(ImportPhase.COPY)
        self._tree_files = self._files_done
        self._tree_bytes = self._bytes_done
        _files, complete = copy_tree(
            item.src,
            item.dest,
            on_file=self._on_tree_file,
            should_cancel=lambda: self._cancelled,
        )
        if not complete:
            self._interrupted = True
        self._emit_progress(force=True)

    def _on_tree_file(self, files_done: int, bytes_done: int) -> None:
        """Translate one tree's counters into the batch's (throttled)."""
        self._files_done = self._tree_files + files_done
        self._bytes_done = self._tree_bytes + bytes_done
        self._emit_progress()

    def _set_phase(self, phase: ImportPhase) -> None:
        """Switch phase and publish it at once, so the label never lags."""
        self._phase = phase
        self._emit_progress(force=True)

    def _emit_progress(self, *, force: bool = False) -> None:
        """Report the advance of the batch, throttled unless ``force``."""
        now = time.monotonic()
        if not force and now - self._last_emit < _PROGRESS_THROTTLE_MS / 1000:
            return
        self._last_emit = now
        self.progress.emit(
            CopyProgress(
                phase=self._phase,
                items_done=self._items_done,
                items_total=len(self._items),
                files_done=self._files_done,
                bytes_done=self._bytes_done,
                files_total=self._files_total,
                bytes_total=self._bytes_total,
            )
        )

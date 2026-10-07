# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Background workers for file panel.

Contains DirectoryScanWorker for scanning directories in background threads.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from hsync_desktop.config import FILE_BATCH_SIZE

# Minimum time between progress updates (seconds) to avoid flooding the UI
_PROGRESS_THROTTLE_MS = 100


class DirectoryScanWorker(QObject):
    """Worker that scans a directory in a background thread."""

    # Emits a batch of (filepath, size, mtime) tuples
    files_found = Signal(list)
    # Emits (processed_count, total_count) for progress
    progress = Signal(int, int)
    # Emitted when scan is complete
    finished = Signal()

    def __init__(self, directory: str) -> None:
        super().__init__()
        self._directory = directory
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

    def _count_dir(self, dir_path: Path, base_path: Path) -> int:
        """Recursively count real files and empty leaf dirs (no symlinks)."""
        if self._cancelled:
            return 0
        try:
            entries = list(os.scandir(dir_path))
        except OSError:
            return 0

        dirs: list[os.DirEntry[str]] = []
        file_count = 0
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    dirs.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
            except OSError:
                continue

        # Leaf empty directory (not root)
        if not file_count and not dirs and str(dir_path) != str(base_path):
            return 1

        count = file_count
        for d in dirs:
            if self._cancelled:
                return 0
            count += self._count_dir(Path(d.path), base_path)
        return count

    def _scan_with_scandir(self, base_path: Path, total: int) -> None:
        """Scan directory using os.scandir() for better performance."""
        batch: list[tuple[str, int, float]] = []
        processed = 0
        last_progress_time = 0.0

        def scan_directory(dir_path: Path) -> None:
            nonlocal processed, last_progress_time, batch

            if self._cancelled:
                return

            try:
                entries = list(os.scandir(dir_path))
            except OSError:
                return

            # Separate files and directories
            dirs = []
            files = []

            for entry in entries:
                if entry.name.startswith("."):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        files.append(entry)
                except OSError:
                    continue

            # Handle empty directories (leaf dirs)
            if not files and not dirs and str(dir_path) != str(base_path):
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
                    self.files_found.emit(batch)
                    current_time = time.monotonic()
                    if current_time - last_progress_time >= _PROGRESS_THROTTLE_MS / 1000:
                        self.progress.emit(processed, total)
                        last_progress_time = current_time
                    batch = []

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

                try:
                    rel_path = str(Path(entry.path).relative_to(base_path))
                except ValueError:
                    rel_path = entry.path

                batch.append((rel_path, size, mtime))
                processed += 1

                if len(batch) >= FILE_BATCH_SIZE:
                    self.files_found.emit(batch)
                    current_time = time.monotonic()
                    if current_time - last_progress_time >= _PROGRESS_THROTTLE_MS / 1000:
                        self.progress.emit(processed, total)
                        last_progress_time = current_time
                    batch = []

            # Recursively scan subdirectories
            for entry in dirs:
                scan_directory(Path(entry.path))

        scan_directory(base_path)

        # Emit remaining files
        if batch and not self._cancelled:
            self.files_found.emit(batch)
            self.progress.emit(processed, total)

    @Slot()
    def run(self) -> None:
        """Scan the directory and emit files in batches."""
        if not self._directory or not os.path.isdir(self._directory):
            self.finished.emit()
            return

        # First pass: count files for progress
        total = self._count_files()
        if self._cancelled or total == 0:
            self.finished.emit()
            return

        self.progress.emit(0, total)

        base_path = Path(self._directory)

        # Use optimized scandir-based scanner
        self._scan_with_scandir(base_path, total)

        self.finished.emit()

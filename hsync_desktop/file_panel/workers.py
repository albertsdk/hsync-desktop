# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Background workers for file panel.

Contains DirectoryScanWorker for scanning directories in background threads.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from hsync_desktop.config import FILE_BATCH_SIZE


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
        """Quick count of files and empty directories (without reading sizes)."""
        count = 0
        for root, dirs, files in os.walk(self._directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if self._cancelled:
                return 0
            visible_files = [f for f in files if not f.startswith(".")]
            count += len(visible_files)
            # Count this directory as an entry if it has no visible files
            # and no visible subdirectories (i.e. it's a leaf empty dir)
            if not visible_files and not dirs:
                # Don't count the root directory itself
                if root != self._directory:
                    count += 1
        return count

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
        batch: list[tuple[str, int, float]] = []
        processed = 0

        for root, dirs, files in os.walk(self._directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            if self._cancelled:
                break

            visible_files = [f for f in files if not f.startswith(".")]

            # Emit empty directory entry (leaf dir with no visible content)
            if not visible_files and not dirs and root != self._directory:
                dir_path = Path(root)
                try:
                    rel_dir = str(dir_path.relative_to(base_path))
                except ValueError:
                    rel_dir = str(dir_path)
                try:
                    mtime = dir_path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                # Trailing "/" marks it as a directory entry
                batch.append((rel_dir + "/", 0, mtime))
                processed += 1
                if len(batch) >= FILE_BATCH_SIZE:
                    self.files_found.emit(batch)
                    self.progress.emit(processed, total)
                    batch = []
                continue

            for filename in visible_files:
                if self._cancelled:
                    break

                full_path = Path(root) / filename
                try:
                    stat = full_path.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = 0.0

                # Get relative path from base directory
                try:
                    rel_path = str(full_path.relative_to(base_path))
                except ValueError:
                    rel_path = str(full_path)

                batch.append((rel_path, size, mtime))
                processed += 1

                # Emit batch when full
                if len(batch) >= FILE_BATCH_SIZE:
                    self.files_found.emit(batch)
                    self.progress.emit(processed, total)
                    batch = []

        # Emit remaining files
        if batch and not self._cancelled:
            self.files_found.emit(batch)
            self.progress.emit(processed, total)

        self.finished.emit()

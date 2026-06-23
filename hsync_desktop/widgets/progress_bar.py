# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Transfer progress bar widget for HSYNC Desktop.

Shows aggregated transfer progress including:
- Files transferred / total
- Bytes transferred / total
- Transfer speed
- Estimated time remaining
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from hsync_desktop.i18n import tr


class TransferProgressBar(QWidget):
    """Widget showing aggregated transfer progress."""

    progress_changed = Signal(int)  # 0-100%

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setFixedWidth(120)
        layout.addWidget(self._progress_bar)

        # Files count label
        self._files_label = QLabel(f"0/0 {tr('label.files')}")
        self._files_label.setMinimumWidth(120)
        layout.addWidget(self._files_label)

        # Separator
        layout.addWidget(QLabel("|"))

        # Bytes label
        self._bytes_label = QLabel("0 B / 0 B")
        self._bytes_label.setMinimumWidth(150)
        layout.addWidget(self._bytes_label)

        # Separator
        layout.addWidget(QLabel("|"))

        # Speed label
        self._speed_label = QLabel("0 B/s")
        self._speed_label.setMinimumWidth(80)
        layout.addWidget(self._speed_label)

        # Separator
        layout.addWidget(QLabel("|"))

        # ETA label
        self._eta_label = QLabel("--:--")
        self._eta_label.setMinimumWidth(70)
        layout.addWidget(self._eta_label)

        # Stretch to push everything to the left
        layout.addStretch()

    def _format_bytes(self, n: float) -> str:
        """Format bytes into human-readable string."""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(n) < 1024:
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
            n /= 1024
        return f"{n:.1f} PB"

    def _format_eta(self, seconds: float) -> str:
        """Format seconds into ETA string."""
        if seconds < 0 or seconds > 86400 * 7:  # > 1 week
            return "--:--"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def reset(self) -> None:
        """Reset the progress display to initial state."""
        self._progress_bar.setValue(0)
        self._files_label.setText(f"0/0 {tr('label.files')}")
        self._bytes_label.setText("0 B / 0 B")
        self._speed_label.setText("0 B/s")
        self._eta_label.setText("--:--")
        self.progress_changed.emit(0)

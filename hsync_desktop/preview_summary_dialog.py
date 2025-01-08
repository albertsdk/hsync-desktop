# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Preview Summary Dialog for HSYNC Desktop.

Shows a summary of what will happen during sync, including file counts,
total sizes, and estimated transfer times based on network speed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr


@dataclass
class PreviewStats:
    """Statistics collected during preview scan."""

    to_download: int = 0
    to_upload: int = 0
    to_delete: int = 0
    synced: int = 0
    download_size: int = 0
    upload_size: int = 0

    def reset(self) -> None:
        """Reset all stats to zero."""
        self.to_download = 0
        self.to_upload = 0
        self.to_delete = 0
        self.synced = 0
        self.download_size = 0
        self.upload_size = 0


def _format_bytes(n: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _format_time(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    if seconds < 60:
        return f"{int(seconds)} {tr('preview_summary.seconds')}"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins} {tr('preview_summary.minutes')} {secs} {tr('preview_summary.seconds')}"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours} {tr('preview_summary.hours')} {mins} {tr('preview_summary.minutes')}"


class PreviewSummaryDialog(QDialog):
    """Dialog showing preview summary with sync/cancel options."""

    # Default network speed in bytes/sec (1 MB/s as fallback)
    DEFAULT_SPEED = 1_000_000

    def __init__(
        self,
        stats: PreviewStats,
        network_speed: float = DEFAULT_SPEED,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stats = stats
        self._network_speed = network_speed if network_speed > 0 else self.DEFAULT_SPEED

        self.setWindowTitle(tr("preview_summary.title"))
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel(f"<h2>{tr('preview_summary.title')}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(1, 1)

        row = 0

        # Downloads section
        dl_label = QLabel(f"<b>{tr('preview_summary.downloads')}:</b>")
        dl_count = QLabel(f"{self._stats.to_download} {tr('preview_summary.files')}")
        grid.addWidget(dl_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(dl_count, row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        dl_size_label = QLabel(f"  {tr('preview_summary.total_size')}:")
        dl_size = QLabel(_format_bytes(self._stats.download_size))
        grid.addWidget(dl_size_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(dl_size, row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        dl_time_label = QLabel(f"  {tr('preview_summary.estimated_time')}:")
        dl_time = self._stats.download_size / self._network_speed
        grid.addWidget(dl_time_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel(_format_time(dl_time)), row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        grid.addWidget(sep1, row, 0, 1, 2)
        row += 1

        # Uploads section
        ul_label = QLabel(f"<b>{tr('preview_summary.uploads')}:</b>")
        ul_count = QLabel(f"{self._stats.to_upload} {tr('preview_summary.files')}")
        grid.addWidget(ul_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(ul_count, row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        ul_size_label = QLabel(f"  {tr('preview_summary.total_size')}:")
        ul_size = QLabel(_format_bytes(self._stats.upload_size))
        grid.addWidget(ul_size_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(ul_size, row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        ul_time_label = QLabel(f"  {tr('preview_summary.estimated_time')}:")
        ul_time = self._stats.upload_size / self._network_speed
        grid.addWidget(ul_time_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel(_format_time(ul_time)), row, 1, Qt.AlignmentFlag.AlignRight)
        row += 1

        layout.addLayout(grid)

        # Buttons
        button_box = QDialogButtonBox()
        self._cancel_btn = QPushButton(tr("preview_summary.cancel"))
        self._sync_btn = QPushButton(tr("preview_summary.sync"))
        self._sync_btn.setDefault(True)
        
        button_box.addButton(self._cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        button_box.addButton(self._sync_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        
        self._cancel_btn.clicked.connect(self.reject)
        self._sync_btn.clicked.connect(self.accept)
        
        layout.addWidget(button_box)


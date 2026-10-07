# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Data models for file panel.

Contains TransferStatus enum, FileTransfer dataclass, and related constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import time

from PySide6.QtGui import QColor


class TransferStatus(Enum):
    """Status of a file transfer."""

    LOCAL = "local"  # File exists locally, status unknown
    SYNCED = "synced"  # File is in sync (no action needed)
    TO_DOWNLOAD = "to_download"  # File needs to be downloaded
    TO_UPLOAD = "to_upload"  # File needs to be uploaded
    TO_DELETE = "to_delete"  # File will be deleted
    DOWNLOADING = "downloading"  # File is being downloaded
    UPLOADING = "uploading"  # File is being uploaded
    TO_RENAME = "to_rename"  # File will be renamed (same content, different path)
    DELETED = "deleted"  # File was deleted (shown briefly before removal)
    QUEUED = "queued"  # Legacy: file is queued for transfer
    TRANSFERRING = "transferring"  # Legacy: file is being transferred
    COMPLETED = "completed"  # File transfer completed
    ERROR = "error"


# Status colors for the file table
STATUS_COLORS = {
    TransferStatus.LOCAL: QColor(128, 128, 128),  # Gray
    TransferStatus.SYNCED: QColor(76, 175, 80),  # Green (#4caf50)
    TransferStatus.TO_DOWNLOAD: QColor(0, 188, 212),  # Cyan (#00bcd4)
    TransferStatus.TO_UPLOAD: QColor(255, 152, 0),  # Orange (#ff9800)
    TransferStatus.TO_DELETE: QColor(244, 67, 54),  # Red (#f44336)
    TransferStatus.TO_RENAME: QColor(156, 39, 176),  # Purple (#9c27b0)
    TransferStatus.DOWNLOADING: QColor(33, 150, 243),  # Blue (#2196f3)
    TransferStatus.UPLOADING: QColor(255, 193, 7),  # Amber (#ffc107)
    TransferStatus.DELETED: QColor(244, 67, 54),  # Red (#f44336)
    TransferStatus.QUEUED: QColor(128, 128, 128),  # Gray
    TransferStatus.TRANSFERRING: QColor(33, 150, 243),  # Blue (#2196f3)
    TransferStatus.COMPLETED: QColor(76, 175, 80),  # Green (#4caf50)
    TransferStatus.ERROR: QColor(244, 67, 54),  # Red (#f44336)
}


# Statuses where no progress bar should be shown
_NO_PROGRESS_STATUSES = {
    TransferStatus.LOCAL,
    TransferStatus.SYNCED,
    TransferStatus.TO_DELETE,
    TransferStatus.TO_RENAME,
    TransferStatus.DELETED,
    TransferStatus.ERROR,
}


@dataclass
class FileTransfer:
    """Represents a file transfer (download or upload)."""

    filepath: str
    direction: str  # "↓" or "↑"
    size: int = 0
    bytes_transferred: int = 0
    start_time: float = field(default_factory=time)
    status: TransferStatus = TransferStatus.QUEUED
    mtime: float = 0.0  # Last modification time (epoch seconds)
    client_cid: str = ""
    client_ip: str = ""

    @property
    def filename(self) -> str:
        return Path(self.filepath).name

    @property
    def path(self) -> str:
        parent = Path(self.filepath).parent
        return str(parent) if str(parent) != "." else ""

    @property
    def remaining(self) -> int:
        return max(0, self.size - self.bytes_transferred)

    @property
    def eta_seconds(self) -> float | None:
        if self.status not in (TransferStatus.DOWNLOADING, TransferStatus.UPLOADING):
            return None
        if self.bytes_transferred == 0:
            return None
        elapsed = time() - self.start_time
        if elapsed <= 0:
            return None
        rate = self.bytes_transferred / elapsed
        if rate <= 0:
            return None
        return self.remaining / rate

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


# Transfer-rate smoothing. Progress events arrive at most every 0.5 s, so the
# displayed rate is averaged over SPEED_WINDOW_SECONDS: a per-sample rate would
# flicker, and a since-start average would stay stale across an idle pause.
SPEED_WINDOW_SECONDS = 2.0
MIN_SAMPLE_INTERVAL = 0.05


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
    # Bytes actually crossing the wire (compressed upload size, delta payload
    # size) driving the progress bar; ``size`` keeps the on-disk size for the
    # Size column. 0 means "same as size".
    progress_total: int = 0
    _speed_bps: float = field(default=0.0, repr=False, compare=False)
    _sample_bytes: int = field(default=0, repr=False, compare=False)
    _sample_ts: float = field(default=0.0, repr=False, compare=False)
    _have_sample: bool = field(default=False, repr=False, compare=False)

    @property
    def filename(self) -> str:
        return Path(self.filepath).name

    @property
    def path(self) -> str:
        parent = Path(self.filepath).parent
        return str(parent) if str(parent) != "." else ""

    @property
    def total_bytes(self) -> int:
        """Transfer total used by the progress bar and the ETA."""
        return self.progress_total or self.size

    @property
    def remaining(self) -> int:
        return max(0, self.total_bytes - self.bytes_transferred)

    def start_transfer(self, direction: str, now: float | None = None) -> None:
        """Mark a (re)started transfer and reset rate sampling."""
        ts = time() if now is None else now
        self.direction = direction
        self.status = TransferStatus.UPLOADING if direction == "↑" else TransferStatus.DOWNLOADING
        self.bytes_transferred = 0
        self.progress_total = 0
        self.start_time = ts
        self._speed_bps = 0.0
        self._sample_bytes = 0
        self._sample_ts = 0.0
        self._have_sample = False

    def stop_transfer(self) -> None:
        """Return an interrupted row to its resting state."""
        self.status = TransferStatus.LOCAL
        self.direction = "—"
        self.bytes_transferred = 0
        self.progress_total = 0
        self._speed_bps = 0.0

    def note_progress(self, transferred: int, now: float | None = None) -> None:
        """Record a progress sample and refresh the smoothed transfer rate.

        The engine throttles progress events to one every 0.5 s, so the rate is
        a time-weighted average over ``SPEED_WINDOW_SECONDS`` instead of
        ``bytes / (now - start_time)``: the since-start average overshoots on the
        first sample of a burst and stays low after an idle pause.
        """
        ts = time() if now is None else now
        self.bytes_transferred = transferred
        if not self._have_sample:
            self._sample_bytes = transferred
            self._sample_ts = ts
            self._have_sample = True
            return
        if transferred < self._sample_bytes:
            # Progress went backwards (restart/resume): start a fresh baseline.
            self._sample_bytes = transferred
            self._sample_ts = ts
            self._speed_bps = 0.0
            return
        dt = ts - self._sample_ts
        if dt < MIN_SAMPLE_INTERVAL:
            return
        instant = (transferred - self._sample_bytes) / dt
        alpha = min(1.0, dt / SPEED_WINDOW_SECONDS)
        self._speed_bps = (
            instant if self._speed_bps <= 0.0 else alpha * instant + (1.0 - alpha) * self._speed_bps
        )
        self._sample_bytes = transferred
        self._sample_ts = ts

    @property
    def speed_bps(self) -> float | None:
        """Current transfer rate in bytes/second, or None when not transferring."""
        if self.status not in (TransferStatus.DOWNLOADING, TransferStatus.UPLOADING):
            return None
        return self._speed_bps if self._speed_bps > 0 else None

    @property
    def eta_seconds(self) -> float | None:
        rate = self.speed_bps
        if rate is None:
            return None
        return self.remaining / rate

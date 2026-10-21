# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Data models for file panel.

Contains TransferStatus enum, FileTransfer dataclass, and related constants.
"""

from __future__ import annotations

from collections import deque
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


# Transfer-rate window. Progress samples arrive every 0.25 s (the client's
# PROGRESS_MIN_INTERVAL), so the displayed rate is the bytes moved over the last
# ~1 s of samples: unbiased (no ramp like an EMA), reacts within a second and
# still hides the per-chunk staircase of the limiter.
SPEED_WINDOW_SECONDS = 1.0
_SAMPLE_HISTORY = 64


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
    _samples: deque[tuple[float, int]] = field(
        default_factory=lambda: deque(maxlen=_SAMPLE_HISTORY), repr=False, compare=False
    )

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
        """Mark a (re)started transfer and restart rate sampling."""
        ts = time() if now is None else now
        self.direction = direction
        self.status = TransferStatus.UPLOADING if direction == "↑" else TransferStatus.DOWNLOADING
        self.bytes_transferred = 0
        self.progress_total = 0
        self.start_time = ts
        self._speed_bps = 0.0
        self._samples.clear()

    def stop_transfer(self) -> None:
        """Return an interrupted row to its resting state."""
        self.status = TransferStatus.LOCAL
        self.direction = "—"
        self.bytes_transferred = 0
        self.progress_total = 0
        self._speed_bps = 0.0
        self._samples.clear()

    def note_progress(self, transferred: int, now: float | None = None) -> None:
        """Record a progress sample and refresh the transfer rate.

        The rate is ``bytes moved / time elapsed`` across the samples of the
        last ``SPEED_WINDOW_SECONDS``: a since-start average would stay low
        after an idle pause and overshoot on a burst, and a per-sample rate
        would flicker with the chunk granularity of the limiter.
        """
        ts = time() if now is None else now
        self.bytes_transferred = transferred
        if self._samples and transferred < self._samples[-1][1]:
            # Progress went backwards (restart/resume): drop the history.
            self._samples.clear()
            self._speed_bps = 0.0
        self._samples.append((ts, transferred))
        if len(self._samples) < 2:
            return
        # Keep one anchor sample at (or just before) the window edge, so the
        # measured interval is the window itself, not the whole transfer.
        edge = ts - SPEED_WINDOW_SECONDS
        while len(self._samples) > 2 and self._samples[1][0] <= edge:
            self._samples.popleft()
        t0, b0 = self._samples[0]
        dt = ts - t0
        if dt > 0:
            self._speed_bps = max(0.0, (transferred - b0) / dt)

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

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

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.ui.loader import load_ui_widget


@dataclass
class PreviewStats:
    """Statistics collected during preview scan."""

    to_download: int = 0
    to_upload: int = 0
    to_delete: int = 0
    to_rename: int = 0
    synced: int = 0
    download_size: int = 0
    upload_size: int = 0

    def reset(self) -> None:
        """Reset all stats to zero."""
        self.to_download = 0
        self.to_upload = 0
        self.to_delete = 0
        self.to_rename = 0
        self.synced = 0
        self.download_size = 0
        self.upload_size = 0


from hsync_common.format import format_bytes


def _format_time(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    if seconds < 60:
        return f"{int(seconds)} {tr('preview_summary.seconds')}"
    if seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins} {tr('preview_summary.minutes')} {secs} {tr('preview_summary.seconds')}"
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

        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("preview_summary_dialog", self)

        self.setWindowTitle(tr("preview_summary.title"))

        # Get widget references from .ui
        self._lbl_title: QLabel = self.findChild(QLabel, "lblTitle")  # type: ignore[assignment]
        self._lbl_downloads: QLabel = self.findChild(QLabel, "lblDownloads")  # type: ignore[assignment]
        self._val_download_count: QLabel = self.findChild(QLabel, "valDownloadCount")  # type: ignore[assignment]
        self._lbl_download_size: QLabel = self.findChild(QLabel, "lblDownloadSize")  # type: ignore[assignment]
        self._val_download_size: QLabel = self.findChild(QLabel, "valDownloadSize")  # type: ignore[assignment]
        self._lbl_download_time: QLabel = self.findChild(QLabel, "lblDownloadTime")  # type: ignore[assignment]
        self._val_download_time: QLabel = self.findChild(QLabel, "valDownloadTime")  # type: ignore[assignment]
        self._lbl_uploads: QLabel = self.findChild(QLabel, "lblUploads")  # type: ignore[assignment]
        self._val_upload_count: QLabel = self.findChild(QLabel, "valUploadCount")  # type: ignore[assignment]
        self._lbl_upload_size: QLabel = self.findChild(QLabel, "lblUploadSize")  # type: ignore[assignment]
        self._val_upload_size: QLabel = self.findChild(QLabel, "valUploadSize")  # type: ignore[assignment]
        self._lbl_upload_time: QLabel = self.findChild(QLabel, "lblUploadTime")  # type: ignore[assignment]
        self._val_upload_time: QLabel = self.findChild(QLabel, "valUploadTime")  # type: ignore[assignment]
        self._lbl_deletions: QLabel = self.findChild(QLabel, "lblDeletions")  # type: ignore[assignment]
        self._val_delete_count: QLabel = self.findChild(QLabel, "valDeleteCount")  # type: ignore[assignment]
        self._lbl_renames: QLabel = self.findChild(QLabel, "lblRenames")  # type: ignore[assignment]
        self._val_rename_count: QLabel = self.findChild(QLabel, "valRenameCount")  # type: ignore[assignment]
        self._lbl_synced: QLabel = self.findChild(QLabel, "lblSynced")  # type: ignore[assignment]
        self._val_synced_count: QLabel = self.findChild(QLabel, "valSyncedCount")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and stats values."""
        files = tr("preview_summary.files")

        # Translated labels
        self._lbl_title.setText(f"<h2>{tr('preview_summary.title')}</h2>")
        self._lbl_downloads.setText(f"<b>{tr('preview_summary.downloads')}:</b>")
        self._lbl_download_size.setText(f"  {tr('preview_summary.total_size')}:")
        self._lbl_download_time.setText(f"  {tr('preview_summary.estimated_time')}:")
        self._lbl_uploads.setText(f"<b>{tr('preview_summary.uploads')}:</b>")
        self._lbl_upload_size.setText(f"  {tr('preview_summary.total_size')}:")
        self._lbl_upload_time.setText(f"  {tr('preview_summary.estimated_time')}:")
        self._lbl_deletions.setText(f"<b>{tr('preview_summary.deletions')}:</b>")
        self._lbl_renames.setText(f"<b>{tr('preview_summary.renames')}:</b>")
        self._lbl_synced.setText(f"<b>{tr('preview_summary.synced')}:</b>")

        # Values
        self._val_download_count.setText(f"{self._stats.to_download} {files}")
        self._val_download_size.setText(format_bytes(self._stats.download_size))
        dl_time = self._stats.download_size / self._network_speed
        self._val_download_time.setText(_format_time(dl_time))

        self._val_upload_count.setText(f"{self._stats.to_upload} {files}")
        self._val_upload_size.setText(format_bytes(self._stats.upload_size))
        ul_time = self._stats.upload_size / self._network_speed
        self._val_upload_time.setText(_format_time(ul_time))

        self._val_delete_count.setText(f"{self._stats.to_delete} {files}")
        self._val_rename_count.setText(f"{self._stats.to_rename} {files}")
        self._val_synced_count.setText(f"{self._stats.synced} {files}")

        # Buttons – show OK only when nothing to sync, else Cancel/Sync
        has_work = (
            self._stats.to_download > 0
            or self._stats.to_upload > 0
            or self._stats.to_delete > 0
            or self._stats.to_rename > 0
        )

        if has_work:
            self._cancel_btn = QPushButton(tr("preview_summary.cancel"))
            self._sync_btn = QPushButton(tr("preview_summary.sync"))
            self._sync_btn.setDefault(True)
            self._button_box.addButton(self._cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
            self._button_box.addButton(self._sync_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            self._cancel_btn.clicked.connect(self.reject)
            self._sync_btn.clicked.connect(self.accept)
        else:
            self._ok_btn = QPushButton(tr("preview_summary.ok"))
            self._ok_btn.setDefault(True)
            self._button_box.addButton(self._ok_btn, QDialogButtonBox.ButtonRole.RejectRole)
            self._ok_btn.clicked.connect(self.reject)

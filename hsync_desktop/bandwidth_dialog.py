# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Bandwidth settings dialog for HSYNC Desktop.

Allows users to configure upload and download speed limits.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.cli_args import get_bandwidth_limits, save_bandwidth_limits
from hsync_desktop.ui.loader import load_ui_widget


class BandwidthDialog(QDialog):
    """Dialog to configure bandwidth limits for file transfers."""

    def __init__(
        self,
        parent: QWidget | None = None,
        sync_active: bool = False,
    ) -> None:
        """Initialize the bandwidth dialog.

        Args:
            parent: Parent widget.
            sync_active: Whether sync is currently running (shows warning).
        """
        super().__init__(parent)
        self._sync_active = sync_active
        self._load_ui()
        self._load_settings()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("bandwidth_dialog", self)

        self.setWindowTitle(tr("bandwidth.title"))

        # Get widget references from .ui file
        self._lbl_warning: QLabel = self.findChild(QLabel, "lblWarning")  # type: ignore[assignment]
        self._lbl_upload: QLabel = self.findChild(QLabel, "lblUpload")  # type: ignore[assignment]
        self._lbl_download: QLabel = self.findChild(QLabel, "lblDownload")  # type: ignore[assignment]
        self._lbl_info: QLabel = self.findChild(QLabel, "lblInfo")  # type: ignore[assignment]
        self._upload_enabled: QCheckBox = self.findChild(QCheckBox, "chkUploadEnabled")  # type: ignore[assignment]
        self._upload_spin: QDoubleSpinBox = self.findChild(QDoubleSpinBox, "spnUpload")  # type: ignore[assignment]
        self._download_enabled: QCheckBox = self.findChild(QCheckBox, "chkDownloadEnabled")  # type: ignore[assignment]
        self._download_spin: QDoubleSpinBox = self.findChild(QDoubleSpinBox, "spnDownload")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        # Connect signals
        self._upload_enabled.toggled.connect(self._on_upload_toggled)
        self._download_enabled.toggled.connect(self._on_download_toggled)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        # Update translations
        self._apply_translations()

        # Show/hide warning based on sync state
        if self._sync_active:
            self._lbl_warning.setText("⚠️ " + tr("bandwidth.warning_active"))
            self._lbl_warning.show()
        else:
            self._lbl_warning.hide()

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._lbl_upload.setText(tr("bandwidth.upload"))
        self._lbl_download.setText(tr("bandwidth.download"))
        self._upload_enabled.setText(tr("bandwidth.limit_enabled"))
        self._download_enabled.setText(tr("bandwidth.limit_enabled"))
        self._lbl_info.setText(tr("bandwidth.info"))

        # Update button texts
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(tr("bandwidth.apply"))
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("action.cancel"))

    def _load_settings(self) -> None:
        """Load current bandwidth settings."""
        upload_bps, download_bps = get_bandwidth_limits()

        # Convert from bytes/s to MB/s
        if upload_bps is not None:
            self._upload_enabled.setChecked(True)
            self._upload_spin.setValue(upload_bps / (1024 * 1024))
        else:
            self._upload_enabled.setChecked(False)
            self._upload_spin.setValue(10.0)

        if download_bps is not None:
            self._download_enabled.setChecked(True)
            self._download_spin.setValue(download_bps / (1024 * 1024))
        else:
            self._download_enabled.setChecked(False)
            self._download_spin.setValue(10.0)

        self._on_upload_toggled(self._upload_enabled.isChecked())
        self._on_download_toggled(self._download_enabled.isChecked())

    def _on_upload_toggled(self, checked: bool) -> None:
        """Handle upload enabled toggle."""
        self._upload_spin.setEnabled(checked)

    def _on_download_toggled(self, checked: bool) -> None:
        """Handle download enabled toggle."""
        self._download_spin.setEnabled(checked)

    def _on_accept(self) -> None:
        """Save settings and accept the dialog."""
        upload_mbps = self._upload_spin.value() if self._upload_enabled.isChecked() else None
        download_mbps = self._download_spin.value() if self._download_enabled.isChecked() else None

        save_bandwidth_limits(upload_mbps, download_mbps)
        self.accept()

    def get_bandwidth_values(self) -> tuple[float | None, float | None]:
        """Return the entered bandwidth values.

        Returns:
            Tuple of (upload_mbps, download_mbps) where None means unlimited.
        """
        upload = self._upload_spin.value() if self._upload_enabled.isChecked() else None
        download = self._download_spin.value() if self._download_enabled.isChecked() else None
        return upload, download

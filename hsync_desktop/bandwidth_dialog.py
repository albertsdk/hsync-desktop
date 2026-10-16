# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Bandwidth settings dialog for HSYNC Desktop.

Configures the upload and download speed limits. Uses the same 0 = unlimited
strategy as the Advanced tab's Network section, so both entry points share one
set of values (`sync/bandwidth_upload` / `sync/bandwidth_download`).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import style_ok_cancel_button_box
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
        self._upload_spin: QDoubleSpinBox = self.findChild(QDoubleSpinBox, "spnUpload")  # type: ignore[assignment]
        self._download_spin: QDoubleSpinBox = self.findChild(QDoubleSpinBox, "spnDownload")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        # Connect signals
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
        # Same wording as the Advanced tab's Network section.
        self._lbl_upload.setText(tr("settings.bandwidth_upload"))
        self._lbl_download.setText(tr("settings.bandwidth_download"))
        self._lbl_info.setText(tr("bandwidth.info"))
        # 0 = unlimited, matching the Settings fields.
        self._upload_spin.setSpecialValueText(tr("settings.unlimited"))
        self._download_spin.setSpecialValueText(tr("settings.unlimited"))

        # Apply/Cancel with the app-theme button icons (same style as Save/Cancel).
        style_ok_cancel_button_box(self._button_box, accept_text_key="bandwidth.apply")

    def _load_settings(self) -> None:
        """Load current bandwidth settings (0 shows as unlimited)."""
        upload_bps, download_bps = get_bandwidth_limits()

        # Convert from bytes/s to MB/s; None (unlimited) shows as 0.
        self._upload_spin.setValue((upload_bps or 0) / (1024 * 1024))
        self._download_spin.setValue((download_bps or 0) / (1024 * 1024))

    def _on_accept(self) -> None:
        """Save settings and accept the dialog."""
        save_bandwidth_limits(
            self._upload_spin.value() or None,
            self._download_spin.value() or None,
        )
        self.accept()

    def get_bandwidth_values(self) -> tuple[float | None, float | None]:
        """Return the entered bandwidth values.

        Returns:
            Tuple of (upload_mbps, download_mbps) where None means unlimited.
        """
        return self._upload_spin.value() or None, self._download_spin.value() or None

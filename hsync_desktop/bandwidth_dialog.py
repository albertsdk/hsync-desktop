# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Bandwidth settings dialog for HSYNC Desktop.

Allows users to configure upload and download speed limits.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.cli_args import get_bandwidth_limits, save_bandwidth_limits


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
        """Setup the dialog UI."""
        self.setWindowTitle(tr("bandwidth.title"))
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # Warning banner if sync is active
        if self._sync_active:
            warning = QLabel("⚠️ " + tr("bandwidth.warning_active"))
            warning.setStyleSheet(
                "background-color: #fff3cd; "
                "border: 1px solid #ffc107; "
                "border-radius: 4px; "
                "padding: 8px; "
                "color: #856404;"
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        form = QFormLayout()

        # Upload settings
        self._upload_enabled = QCheckBox(tr("bandwidth.limit_enabled"))
        self._upload_enabled.toggled.connect(self._on_upload_toggled)

        self._upload_spin = QDoubleSpinBox()
        self._upload_spin.setRange(0.1, 1000.0)
        self._upload_spin.setSuffix(" MB/s")
        self._upload_spin.setDecimals(1)
        self._upload_spin.setValue(10.0)

        upload_layout = QHBoxLayout()
        upload_layout.addWidget(self._upload_enabled)
        upload_layout.addWidget(self._upload_spin)
        upload_layout.addStretch()

        form.addRow(tr("bandwidth.upload"), upload_layout)

        # Download settings
        self._download_enabled = QCheckBox(tr("bandwidth.limit_enabled"))
        self._download_enabled.toggled.connect(self._on_download_toggled)

        self._download_spin = QDoubleSpinBox()
        self._download_spin.setRange(0.1, 1000.0)
        self._download_spin.setSuffix(" MB/s")
        self._download_spin.setDecimals(1)
        self._download_spin.setValue(10.0)

        download_layout = QHBoxLayout()
        download_layout.addWidget(self._download_enabled)
        download_layout.addWidget(self._download_spin)
        download_layout.addStretch()

        form.addRow(tr("bandwidth.download"), download_layout)

        layout.addLayout(form)

        # Info text
        info = QLabel(tr("bandwidth.info"))
        info.setStyleSheet("color: #666; font-size: 10pt;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        # Set button texts
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(tr("bandwidth.apply"))
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("action.cancel"))

        layout.addWidget(self._button_box)

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

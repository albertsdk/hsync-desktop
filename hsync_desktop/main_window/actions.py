# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Main window for HSYNC Desktop.

Contains:
- Action bar: Start/Stop, Sync, Preview, path selector, Settings
- File panel: real-time file transfer table with detail panel
- Log viewer: real-time scrolling log output
- Bottom bar: status indicator, peers, transfer stats (right-aligned)

UI is loaded from ui/main_window.ui (Qt Designer).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast
from urllib.parse import urlsplit

from hsync_common.endpoint import parse_host_port
from hsync_common.format import format_bytes
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.bandwidth_dialog import BandwidthDialog
from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SERVER_TRUST,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine import (
    HsyncEngine,
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    list_bootnode_trust,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    supports_peer_trust,
)
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.settings import (
    SETTINGS_APP,
    SETTINGS_ORG,
    ApiKeyDialog,
    P2PKeyDialog,
    SettingsDialog,
    are_notifications_enabled,
    build_hsync_args,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
)
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import (
    COLOR_CONNECTED,
    COLOR_DISCONNECTED,
    COLOR_WAITING,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget

# ── Button styles ────────────────────────────────────────────────────────────
_BTN_PAD = "padding: 4px 10px; border-radius: 3px;"
_BTN_START_ACTIVE = (
    f"QPushButton {{ background-color: #2EA043; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #278a39; }"
    "QPushButton:pressed { background-color: #1f7a30; }"
)
_BTN_STOP_ACTIVE = (
    f"QPushButton {{ background-color: #CF222E; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #b71d28; }"
    "QPushButton:pressed { background-color: #a01822; }"
)
_BTN_REFRESH_ACTIVE = (
    f"QPushButton {{ background-color: #0969DA; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #0860CA; }"
    "QPushButton:pressed { background-color: #0757BA; }"
)
_BTN_IDLE = f"QPushButton {{ {_BTN_PAD} }}"


class ActionsMixin:
    @Slot(QAction)
    def _on_direction_changed(self, action: QAction) -> None:
        """Handle sync direction change from the menu."""
        direction = action.data()
        if not direction:
            return
        # Persist to QSettings
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("sync/direction", direction)
        # If the engine is running, send the command dynamically
        if self._engine.is_running:
            self._engine.set_sync_direction(direction)
        # Refresh path display to update sync direction icon
        self._update_path_display()

    @Slot(object)
    def _on_file_selection_changed(self, transfer) -> None:
        """Handle file selection change from the file panel table."""
        has_selection = transfer is not None
        self._set_file_menu_enabled(has_selection)
        # Hide "Open With" for folders
        if has_selection and hasattr(transfer, "filepath"):
            is_dir = transfer.filepath.endswith("/")
            self._act_file_open_with.setEnabled(not is_dir)

    # ── File menu action wrappers ─────────────────────────────────────────

    def _get_selected_transfer(self):
        """Return the currently selected transfer from the file panel, or None."""
        table = self._file_panel._table
        row = table._last_selected_row
        if row < 0 or row >= table.rowCount():
            return None
        transfer = table._get_transfer_at_row(row)
        if not transfer:
            # Synthesized folder — create a virtual transfer
            from hsync_desktop.file_panel import COL_NAME, FileTransfer, TransferStatus

            name_item = table.item(row, COL_NAME)
            if not name_item:
                return None
            display_name = name_item.text()
            folder_path = (
                f"{table._current_path}/{display_name}/"
                if table._current_path
                else f"{display_name}/"
            )
            transfer = FileTransfer(
                filepath=folder_path,
                direction="—",
                size=0,
                status=TransferStatus.LOCAL,
            )
        return transfer

    def _menu_file_open(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_open(t)

    def _menu_file_open_with(self) -> None:
        t = self._get_selected_transfer()
        if t and not t.filepath.endswith("/"):
            self._file_panel._table._ctx_open_with(t)

    def _menu_file_copy_to(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_copy_to(t)

    def _menu_file_rename(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_rename(t)

    def _menu_file_trash(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_trash(t)

    def _menu_file_properties(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_properties(t)

    def _open_documentation(self) -> None:
        """Open the documentation URL in the default browser."""
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(
            QUrl("https://github.com/albertsdk/hsync-desktop/blob/main/README.md")
        )

    def _open_github(self) -> None:
        """Open the project page on GitHub in the default browser."""
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl("https://github.com/albertsdk/hsync-desktop"))

    def _show_about(self) -> None:
        """Show the splash screen as an About dialog."""
        from hsync_desktop.splash_screen import SplashScreen

        about = SplashScreen(self)
        about.show_as_about()

    def _show_license(self) -> None:
        """Show the project license in a scrollable, read-only dialog."""
        from hsync_desktop.license_dialog import LicenseDialog

        LicenseDialog(self).exec()

    # ── Signal wiring ────────────────────────────────────────────────────

    def _show_preview_summary(self) -> None:
        """Show the preview summary dialog and start sync if confirmed."""
        s = self._preview_stats
        nothing_to_sync = (
            s.to_download == 0 and s.to_upload == 0 and s.to_delete == 0 and s.to_rename == 0
        )

        if nothing_to_sync:
            # Skip the dialog entirely — go straight to live sync
            self._append_log(f"ℹ {tr('preview.no_actions')}")
            if self._is_dry_run_preview:
                # Send SYNC command to switch from dry-run to real sync
                self._engine.sync()
                self._btn_refresh.setEnabled(True)
                self._apply_button_styles()
            self._is_dry_run_preview = False
            return

        dlg = PreviewSummaryDialog(self._preview_stats, parent=self)
        if dlg.exec() == PreviewSummaryDialog.DialogCode.Accepted:
            # Send SYNC command — the running process will perform
            # the actual sync without needing a restart.
            self._engine.sync()
            self._btn_refresh.setEnabled(True)
            self._apply_button_styles()
            self._is_dry_run_preview = False
        else:
            if self._is_dry_run_preview:
                # User cancelled - stop the dry-run process
                self._engine.stop()
                # Reset UI state
                self._btn_start.setEnabled(bool(self._local_path))
                self._btn_stop.setEnabled(False)
                if self._tray:
                    self._tray.set_running(False)
                self._apply_button_styles()
                self._update_menu_state()
            # If stdin preview, just close dialog - process keeps running
            self._is_dry_run_preview = False

    def _show_bandwidth_dialog(self) -> None:
        """Show the bandwidth settings dialog."""
        # Check if sync is active
        sync_active = self._engine.is_running

        # Show bandwidth dialog
        dlg = BandwidthDialog(self, sync_active=sync_active)
        if dlg.exec() == BandwidthDialog.DialogCode.Accepted:
            upload_mbps, download_mbps = dlg.get_bandwidth_values()

            # Convert MB/s to bytes/s
            upload_bps = int(upload_mbps * 1024 * 1024) if upload_mbps else None
            download_bps = int(download_mbps * 1024 * 1024) if download_mbps else None

            # Format human-readable values for log
            upload_display = f"{upload_mbps}" if upload_mbps else "∞"
            download_display = f"{download_mbps}" if download_mbps else "∞"

            # If sync is running, send the new limits via stdin command
            if self._engine.is_running:
                self._engine.set_bandwidth(upload_bps, download_bps)
                self._append_log(
                    f"ℹ {tr('bandwidth.applied').format(upload=upload_display, download=download_display)}"
                )
            else:
                # If sync is not running, just save settings for next start
                self._append_log(
                    f"ℹ {tr('bandwidth.saved').format(upload=upload_display, download=download_display)}"
                )

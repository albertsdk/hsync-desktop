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


class StartMixin:
    # Open settings dialog, if any (re-declared here so the mixin typing agrees
    # with MainWindow.__init__).
    _settings_dialog: SettingsDialog | None
    # Scoped Send/Receive target, cleared by a normal start (re-declared so the
    # mixin typing agrees with MainWindow.__init__).
    _pending_selection_sync: tuple[str, str] | None

    def _reset_ui_stopped(self) -> None:
        """Reset UI buttons to the stopped state."""
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        if self._tray:
            self._tray.set_running(False)
        self._hide_info_banner()
        self._apply_button_styles()
        self._update_menu_state()

    def _set_path(self, path: str) -> None:
        """Set the local path and update the display."""
        self._local_path = path.strip()
        # Feed the engine's distinct-file identity keys, so an absolute transfer
        # path and its bucket-relative form collapse to one key.
        self._engine.local_root = self._local_path
        self._update_path_display()
        self._update_menu_state()

    def _share_display_name(self) -> str:
        """User-facing share name shown next to the folder icon.

        Prefers the engine-detected bucket, then the saved share name, then the
        local folder's own name as a last resort.
        """
        if self._bucket:
            return self._bucket
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        bucket = str(s.value("sync/bucket", "", str)).strip()
        if bucket:
            return bucket
        from pathlib import Path as _Path

        return _Path(self._local_path).name or self._local_path

    def _update_path_display(self) -> None:
        """Update the path label, sync direction icon, and remote endpoint."""
        from hsync_desktop.icons import icon as get_icon

        if self._local_path:
            # ── Folder icon + share name (local path in the tooltip) ──────
            self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(24, 24))
            self._path_icon_label.show()
            share_name = self._share_display_name()
            # Elide the name if it's too long (max ~300px)
            max_name_px = 300
            fm = QFontMetrics(self._path_label.font())
            elided = fm.elidedText(share_name, Qt.TextElideMode.ElideMiddle, max_name_px)
            link_color = (
                self._path_label.palette().color(self._path_label.palette().ColorRole.Link).name()
            )
            self._path_label.setText(
                f'<a href="open" style="color:{link_color}; text-decoration:none;">{elided}</a>'
            )
            # The full local path is always reachable here: this tooltip is
            # intentionally exempt from the "Show tooltips" preference, which
            # only governs the settings fields.
            self._path_label.setToolTip(self._local_path)
            self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)

            # ── Sync direction icon ───────────────────────────────────
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            direction = str(s.value("sync/direction", "bidirectional", str))
            dir_icon_map = {
                "bidirectional": "sync-bidirectional",
                "upload-only": "sync-upload",
                "download-only": "sync-download",
            }
            dir_tip_map = {
                "bidirectional": tr("menu.sync.direction.bidirectional"),
                "upload-only": tr("menu.sync.direction.upload_only"),
                "download-only": tr("menu.sync.direction.download_only"),
            }
            icon_name = dir_icon_map.get(direction, "sync-bidirectional")
            self._sync_dir_icon.setPixmap(get_icon(icon_name).pixmap(24, 24))
            self._sync_dir_icon.setToolTip(dir_tip_map.get(direction, ""))
            self._sync_dir_icon.show()

            # ── Remote endpoint icon + label ──────────────────────────
            p2p_enabled = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))
            if p2p_enabled:
                self._remote_icon.setPixmap(get_icon("network-p2p").pixmap(24, 24))
                group = str(s.value("p2p/group", "", str))
                self._remote_label.setText(f"p2p ({group})" if group else "p2p")
                self._remote_icon.setToolTip(tr("label.remote_p2p_tip"))
                self._remote_label.setToolTip(tr("label.remote_p2p_tip"))
                # Group name shown next to the p2p label — hide from bottom bar
                self._group_label.hide()
            else:
                self._remote_icon.setPixmap(get_icon("network-cloud").pixmap(24, 24))
                server_ip = self._engine.server_ip if self._engine.server_ip else ""
                if not server_ip:
                    server_url = str(s.value("connection/server_url", "", str))
                    if server_url:
                        from urllib.parse import urlparse

                        parsed = urlparse(server_url)
                        server_ip = parsed.hostname or ""
                self._remote_label.setText(server_ip if server_ip else tr("label.remote_server"))
                self._remote_icon.setToolTip(tr("label.remote_server_tip"))
                self._remote_label.setToolTip(tr("label.remote_server_tip"))
                # In server mode, group label stays in bottom bar
                self._group_label.show()
            self._remote_icon.show()
            self._remote_label.show()
        else:
            self._path_icon_label.hide()
            self._sync_dir_icon.hide()
            self._remote_icon.hide()
            self._remote_label.hide()
            link_color = (
                self._path_label.palette().color(self._path_label.palette().ColorRole.Link).name()
            )
            self._path_label.setText(
                f'<a href="settings" style="color:{link_color}; text-decoration:none;">'
                f"{tr('label.path_placeholder')}</a>"
            )
            self._path_label.setToolTip(tr("label.path_placeholder_tip"))
            self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_path_clicked(self, link: str) -> None:
        """Handle clicks on the path label link."""
        if link == "settings":
            self._open_settings(initial_tab=0)
        elif self._local_path and os.path.isdir(self._local_path):
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl.fromLocalFile(self._local_path))

    def _show_disclaimer(self) -> bool:
        """Show disclaimer dialog. Returns True if user accepts."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if s.value("ui/disclaimer_accepted", False, bool):
            return True

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("disclaimer.title"))
        msg.setText(tr("disclaimer.message"))
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        cancel_btn = msg.button(QMessageBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("action.cancel"))

        checkbox = QCheckBox(tr("disclaimer.dont_show"))
        msg.setCheckBox(checkbox)

        result = msg.exec()
        if result == QMessageBox.StandardButton.Ok:
            if checkbox.isChecked():
                s.setValue("ui/disclaimer_accepted", True)
            return True
        return False

    def _check_auto_sync(self) -> None:
        """Auto-start synchronization if a saved path exists."""
        local_path = self._local_path
        if local_path:
            self._on_start()

    def _check_deletion_risk(self) -> bool:
        """Check if sync settings could cause local file deletion.

        Returns True if safe to proceed (no risk or user confirmed).
        """
        local_path = self._local_path
        if not local_path or not os.path.exists(local_path):
            return True

        # Check if directory has any content
        try:
            entries = os.listdir(local_path)
        except OSError:
            return True
        if not entries:
            return True

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        p2p_mode = s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        prefer_master = s.value("p2p/prefer_master", False, bool)
        sync_dir = s.value("sync/direction", "bidirectional", str)

        # upload-only never deletes local files
        if sync_dir == "upload-only":
            return True

        # prefer_master in p2p mode means this client is authoritative
        if p2p_mode and prefer_master:
            return True

        # Determine risk
        if p2p_mode and not prefer_master:
            reason = tr("notif.deletion_risk_p2p")
        elif sync_dir == "download-only":
            reason = tr("notif.deletion_risk_download")
        else:
            # bidirectional server mode – normal behaviour
            return True

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("notif.deletion_risk"))
        msg.setText(tr("notif.deletion_risk_msg").replace("{reason}", reason))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(tr("action.yes"))
        no_btn = msg.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(tr("action.no"))
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _check_keyless_p2p(self) -> bool:
        """Confirm keyless P2P operation before connecting.

        Without a shared key the transport hides traffic but authenticates nobody:
        reads are open and peers cannot be verified. Returns True when a key is
        set or the operator accepts the risk.
        """
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool):
            return True
        p2p_key = decrypt_value(str(s.value("p2p/key", "", str)))
        if p2p_key:
            return True

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("warn.keyless_p2p_title"))
        msg.setText(tr("warn.keyless_p2p_msg"))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(tr("action.yes"))
        no_btn = msg.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(tr("action.no"))
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _check_disk_space(self) -> bool:
        """Check if sufficient disk space is available. Returns False if insufficient."""
        from shutil import disk_usage

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        min_free_mb = cast(int, s.value("sync/min_free_disk_space", 500, int))

        if min_free_mb <= 0:
            return True

        try:
            usage = disk_usage(self._local_path)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < min_free_mb:
                QMessageBox.critical(
                    self,
                    tr("error.insufficient_disk_space"),
                    tr("error.insufficient_disk_space_msg").format(
                        required=min_free_mb,
                        available=int(free_mb),
                    ),
                )
                return False
        except OSError as e:
            self._append_log(f"⚠ Could not check disk space: {e}")
        return True

    def _on_start(self) -> None:
        # A new session may legitimately re-prompt for fingerprints dismissed in
        # the previous one.
        self._trust_prompted.clear()
        # Show disclaimer first
        if not self._show_disclaimer():
            return

        local_path = self._local_path
        if not local_path:
            self._append_log("⚠ Please select a local directory first.")
            return

        # Delay the deletion risk check to prevent accidental double-clicks
        # This gives the user time to read the disclaimer before the next dialog appears
        self._pending_sync_path = local_path
        QTimer.singleShot(500, self._continue_start_after_disclaimer)

    def _continue_start_after_disclaimer(self) -> None:
        """Continue startup after disclaimer delay - check deletion risk and start sync."""
        local_path = self._pending_sync_path
        if not local_path:
            return

        # A normal start supersedes any pending Send/Receive preview.
        self._pending_selection_sync = None

        # Check for file deletion risk
        if not self._check_deletion_risk():
            return

        # Confirm keyless P2P posture before any connection is made
        if not self._check_keyless_p2p():
            return

        # Check disk space
        if not self._check_disk_space():
            return

        # Resolve bootnode trust before the client starts (the client cannot
        # prompt without a terminal). Then the sync-server trust for server mode.
        if not self._ensure_bootnode_trust():
            return
        if not self._ensure_server_trust():
            return

        # Start in dry-run mode first to show preview
        args = build_hsync_args(local_path, force_dry_run=True)

        self._prepare_engine_run(local_path)
        # Set flags to show preview summary when dry-run completes
        self._awaiting_preview_for_sync = True
        self._is_dry_run_preview = True  # We're in dry-run mode for initial preview
        self._pending_sync_path = local_path  # Save path for actual sync
        if not self._start_engine(args):
            self._reset_ui_stopped()
            return
        self._enter_running_ui()

    def _start_engine(self, args: list[str]) -> bool:
        """Start the engine, surfacing a visible dialog when it fails.

        A failed start (missing/incompatible binary, spawn failure) used to
        leave the window unchanged and only raise a desktop notification, so the
        Start click looked like a no-op. Returns the engine result; the caller
        owns the post-success UI state and the failure reset.
        """
        self._last_engine_error = ""
        self._engine.local_root = self._local_path
        self._engine_starting = True
        try:
            started = self._engine.start(args)
        finally:
            self._engine_starting = False
        if started:
            return True
        # A scoped Send/Receive that could not launch is ended silently: the
        # start-failure dialog below is its single, more specific report.
        if self._selection_sync_active:
            self._finish_selection_sync("cancelled")
        self._report_engine_start_failure()
        return False

    def _report_engine_start_failure(self) -> None:
        """Show why the engine could not start instead of failing silently."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(tr("notif.error"))
        msg.setText(tr("notif.engine_start_failed"))
        if self._last_engine_error:
            msg.setInformativeText(self._last_engine_error)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _on_stop(self) -> None:
        self._user_stopped = True
        self._trust_prompted.clear()
        if self._notifier:
            self._notifier.user_stopped = True
        self._engine.stop()

    def _on_refresh(self) -> None:
        """Trigger a refresh (preview scan) using the running process.

        Sends a PREVIEW command via stdin to the running hsync-client process
        to get a preview of pending sync actions.  If the preview shows work
        to do, a confirmation dialog is displayed before restarting the sync.
        """
        if not self._engine.is_running:
            self._append_log("⚠ Please start synchronization first.")
            return
        self._append_log(f"--- {tr('preview.title')} ---")
        # Set flags to show preview summary when preview completes
        self._awaiting_preview_for_sync = True
        self._is_dry_run_preview = False  # stdin preview, not dry-run mode
        self._engine.preview()

    def _load_local_files(self, path: str) -> None:
        """Load files from the selected directory into the file panel."""
        if path:
            self._file_panel.load_local_files(path)

    def _open_settings(self, initial_tab: int | None = None) -> None:
        if self._settings_dialog is not None:
            if isinstance(initial_tab, int) and not isinstance(initial_tab, bool):
                self._settings_dialog.set_current_tab(initial_tab)
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog(self)
        self._settings_dialog = dlg
        try:
            # Disable connection-critical settings while sync is running
            dlg.set_connection_active(self._engine.is_running)
            # initial_tab may receive a bool from Qt signal triggered(bool) — ignore that
            if isinstance(initial_tab, int) and not isinstance(initial_tab, bool):
                dlg.set_current_tab(initial_tab)
            accepted = dlg.exec() == SettingsDialog.DialogCode.Accepted
        finally:
            self._settings_dialog = None
        if accepted:
            theme = get_saved_theme()
            app = QApplication.instance()
            if app:
                apply_theme(app, theme)  # type: ignore[arg-type]
                self._refresh_icons_for_theme()
            if self._notifier:
                self._notifier.enabled = are_notifications_enabled()
            self._apply_log_visibility()
            # Reload path in case it changed in settings
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            new_path = str(s.value("path/local", "", str))
            if new_path != self._local_path:
                self._set_path(new_path)
                if new_path:
                    self._load_local_files(new_path)
            # Refresh path display (settings may have changed p2p/server/direction)
            self._update_path_display()

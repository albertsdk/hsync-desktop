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


class EventsMixin:
    @Slot(str)
    def _on_bucket_detected(self, bucket: str) -> None:
        """Show the active share in the window title.

        The share name is persistent identity, not operational status, so it
        lives in the title rather than the bottom status bar.
        """
        self.setWindowTitle(f"{tr('app.name')} — {bucket}" if bucket else tr("app.name"))

    def _set_status_label(self, status: str) -> None:
        """Update the status dot/label/tray without the connection-loss effects."""
        i18n_map = {
            "connected": ("status.connected", COLOR_CONNECTED),
            "disconnected": ("status.disconnected", COLOR_DISCONNECTED),
            "connecting": ("status.connecting", COLOR_WAITING),
            "waiting": ("status.waiting", COLOR_WAITING),
            "error": ("status.error", COLOR_DISCONNECTED),
        }
        key, color = i18n_map.get(status, ("status.unknown", COLOR_DISCONNECTED))
        self._status_dot.setStyleSheet(f"color: {color.name()}; font-size: 14px;")
        self._status_label.setText(tr(key))
        if self._tray:
            self._tray.update_status(status)

    @Slot(str)
    def _on_status(self, status: str) -> None:
        self._set_status_label(status)

        if status in ("disconnected", "waiting"):
            # The peer count is only meaningful while connected: clear it so a
            # stale "N/M" does not outlive the link.
            self._peers_label.setText("–")
            self._file_panel.reset_all_to_local()
            if status == "disconnected" and self._notifier:
                self._notifier.connection_lost()
        elif status == "connected":
            self._hide_info_banner()
            # Refresh path display (server_ip now available)
            self._update_path_display()
            # Auto-run preview when connected to show file status
            if self._engine.is_running:
                self._engine.preview()

    # ── Info banner ──────────────────────────────────────────────────────

    @Slot(int, int)
    def _on_peers(self, connected: int, total: int) -> None:
        self._peers_label.setText(f"{connected}/{total}")
        if self._notifier:
            self._notifier.peer_joined(connected, total)

    @Slot(bool)
    def _on_master(self, is_master: bool) -> None:
        from hsync_desktop.icons import icon as get_icon

        if is_master:
            self._role_label.setText(tr("role.master"))
            self._role_label.setToolTip(tr("role.master_tip"))
            self._role_icon.setPixmap(get_icon("role-master").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.master_tip"))
            if self._notifier:
                self._notifier.became_master()
        else:
            self._role_label.setText(tr("role.client"))
            self._role_label.setToolTip(tr("role.client_tip"))
            self._role_icon.setPixmap(get_icon("role-client").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.client_tip"))

    @Slot(str)
    def _on_group_detected(self, group: str) -> None:
        """Update the group label in the bottom bar and the p2p label in the top bar."""
        self._group_label.setText(group)
        # Also update the remote label if p2p mode is active
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)):
            self._remote_label.setText(f"p2p ({group})" if group else "p2p")
            self._group_label.hide()

    @Slot(str, str)
    def _on_file_transferred(self, direction: str, filename: str) -> None:
        st = self._engine.stats
        self._sent_label.setText(f"{st.files_sent} ({format_bytes(st.bytes_sent)})")
        self._recv_label.setText(f"{st.files_received} ({format_bytes(st.bytes_received)})")
        # Convert absolute path to relative path for table lookup
        base_path = self._local_path
        rel_path = filename
        if base_path and filename.startswith(base_path):
            rel_path = filename[len(base_path) :].lstrip("/\\")
        # Read current mtime from filesystem for the transferred file
        mtime = 0.0
        if direction in ("↓", "↑") and base_path:
            try:
                full = os.path.join(base_path, rel_path)
                mtime = os.stat(full).st_mtime
            except OSError:
                pass
        # Gather CID and server IP for detail panel
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        # Update file panel with actual transfer
        if direction == "↓":
            if self._notifier:
                self._notifier.download_complete(filename)
            self._file_panel.update_file_status(
                rel_path,
                "synced",
                mtime=mtime,
                client_cid=client_cid,
                client_ip=client_ip,
            )
        elif direction == "↑":
            self._file_panel.update_file_status(
                rel_path,
                "synced",
                mtime=mtime,
                client_cid=client_cid,
                client_ip=client_ip,
            )
        elif direction == "✕":
            # File was deleted - show briefly then remove
            self._file_panel.mark_deleted(rel_path)

    @Slot(str, int, int)
    def _on_file_progress(self, filepath: str, bytes_transferred: int, total_bytes: int) -> None:
        """Handle real-time file transfer progress updates."""
        # Convert absolute path to relative path for table lookup
        base_path = self._local_path
        rel_path = filepath
        if base_path and filepath.startswith(base_path):
            rel_path = filepath[len(base_path) :].lstrip("/\\")
        # Update the file panel with the progress
        self._file_panel.update_transfer_progress(rel_path, bytes_transferred, total_bytes)

    @Slot(str, str)
    def _on_file_renamed(self, old_path: str, new_path: str) -> None:
        """Handle a file rename event from the engine."""
        base_path = self._local_path
        old_rel = old_path
        new_rel = new_path
        if base_path:
            if old_path.startswith(base_path):
                old_rel = old_path[len(base_path) :].lstrip("/\\")
            if new_path.startswith(base_path):
                new_rel = new_path[len(base_path) :].lstrip("/\\")
        # Read mtime of the renamed file from filesystem
        mtime = 0.0
        if base_path:
            try:
                full = os.path.join(base_path, new_rel)
                mtime = os.stat(full).st_mtime
            except OSError:
                pass
        # Gather CID and server IP
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        self._file_panel.rename_file(
            old_rel,
            new_rel,
            mtime=mtime,
            client_cid=client_cid,
            client_ip=client_ip,
        )

    @Slot(str)
    def _on_directory_created(self, dirpath: str) -> None:
        """Handle a directory creation event from the engine."""
        base_path = self._local_path
        rel_path = dirpath
        if base_path and dirpath.startswith(base_path):
            rel_path = dirpath[len(base_path) :].lstrip("/\\")
        # Read directory metadata from filesystem
        mtime = 0.0
        if base_path:
            try:
                full = os.path.join(base_path, rel_path)
                mtime = os.stat(full).st_mtime
            except OSError:
                pass
        # Gather CID and server IP
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        # Add directory to file panel as synced
        self._file_panel.update_file_status(
            rel_path,
            "synced",
            size=0,
            mtime=mtime,
            client_cid=client_cid,
            client_ip=client_ip,
        )

    @Slot(str, str, str)
    def _on_master_conflict(self, conflict_type: str, peer_cid: str, peer_address: str) -> None:
        """Handle a prefer_master conflict or takeover notification."""
        if conflict_type == "conflict_lost":
            msg = (
                tr("notif.master_conflict_lost")
                .replace("{cid}", peer_cid)
                .replace("{ip}", peer_address)
            )
        elif conflict_type == "conflict_won":
            msg = (
                tr("notif.master_conflict_won")
                .replace("{cid}", peer_cid)
                .replace("{ip}", peer_address)
            )
        else:  # takeover
            msg = (
                tr("notif.master_takeover").replace("{cid}", peer_cid).replace("{ip}", peer_address)
            )
        if self._notifier:
            self._notifier.warning(tr("notif.master_conflict_title"), msg)
        self._append_log(f"⚠ {msg}")

    @Slot(str, str, str)
    def _on_transfer_failed(self, op: str, filepath: str, message: str) -> None:
        """Surface a per-file transfer that gave up after retries."""
        arrow = "↑" if op == "upload" else "↓"
        self._append_log(f"✕ {arrow} {filepath}: {message}")
        if self._notifier:
            self._notifier.error(tr("notif.error"), message)

    @Slot(str, int, int)
    def _on_sync_paused(self, reason: str, deletes: int, _local: int) -> None:
        """Surface the mass-deletion guard pausing the delete phase."""
        msg = (
            tr("notif.sync_paused_msg")
            .replace("{deletes}", str(deletes))
            .replace("{reason}", reason)
        )
        if self._notifier:
            self._notifier.warning(tr("notif.sync_paused_title"), msg)
        self._append_log(f"⚠ {msg}")

    @Slot(str, str, str)
    def _on_security_rejected(self, op: str, path: str, message: str) -> None:
        """Surface an unsafe remote path refused by the client's inbound guards."""
        msg = tr("notif.security_rejected_msg").replace("{path}", path or "?")
        if self._notifier:
            self._notifier.warning(tr("notif.security_rejected_title"), msg)
        detail = f" ({op}: {message})" if message else f" ({op})"
        self._append_log(f"⚠ {msg}{detail}")

    @Slot(str)
    def _on_no_master_warning(self, _detail: str) -> None:
        """Handle the [NO MASTER] warning (no node will serve files)."""
        msg = tr("notif.no_master_msg")
        if self._notifier:
            self._notifier.warning(tr("notif.no_master_title"), msg)
        self._append_log(f"⚠ {msg}")

    @Slot(str, str)
    def _on_duplicate_identity(self, peer_cid: str, peer_address: str) -> None:
        """Handle a duplicated device identity (cloned HSYNC_DEVICE_DIR)."""
        peer = peer_address or "?"
        msg = tr("notif.duplicate_identity_msg").replace("{cid}", peer_cid).replace("{ip}", peer)
        if self._notifier:
            self._notifier.warning(tr("notif.duplicate_identity_title"), msg)
        self._append_log(f"⚠ {msg}")

    @Slot(str, str)
    def _on_conflict_resolved(self, filepath: str, conflict_copy: str) -> None:
        """Handle a file conflict resolved by keeping the remote version."""
        msg = (
            tr("notif.conflict_resolved_msg")
            .replace("{file}", filepath)
            .replace("{conflict_copy}", conflict_copy)
        )
        if self._notifier:
            self._notifier.info(tr("notif.conflict_resolved_title"), msg)
        self._append_log(f"⚠ {msg}")

    # ── Trust refusal dialogs (SSH-style, no terminal) ──────────────────────

    @Slot()
    def _on_preview_started(self) -> None:
        """Handle preview scan started."""
        self._append_log("--- Updating file status... ---")
        # Reset preview statistics
        self._preview_stats.reset()

    @Slot()
    def _on_preview_ended(self) -> None:
        """Handle preview scan ended."""
        self._append_log("--- File status updated ---")
        # Show summary dialog if awaiting sync confirmation
        if self._awaiting_preview_for_sync:
            self._awaiting_preview_for_sync = False
            self._show_preview_summary()

    @Slot(str, str, int)
    def _on_file_status(self, status: str, filepath: str, size: int) -> None:
        """Handle file status from preview."""
        # Convert absolute path to relative path for table lookup
        base_path = self._local_path
        rel_path = filepath
        if base_path and filepath.startswith(base_path):
            rel_path = filepath[len(base_path) :].lstrip("/\\")
        self._file_panel.update_file_status(rel_path, status, size)
        # Accumulate preview statistics
        if status == "to_download":
            self._preview_stats.to_download += 1
            self._preview_stats.download_size += size
        elif status == "to_upload":
            self._preview_stats.to_upload += 1
            self._preview_stats.upload_size += size
        elif status == "to_delete":
            self._preview_stats.to_delete += 1
        elif status == "synced":
            self._preview_stats.synced += 1

    @Slot(str, int)
    def _on_file_rename_status(self, old_path: str, size: int) -> None:
        """Handle file rename status from preview."""
        base_path = self._local_path
        rel_old = old_path
        if base_path and old_path.startswith(base_path):
            rel_old = old_path[len(base_path) :].lstrip("/\\")
        self._file_panel.update_file_status(rel_old, "to_rename", size)
        self._preview_stats.to_rename += 1

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        # No engine process means no live connection: drop the status out of
        # "connecting"/"connected" (the client cannot report the final state)
        # and clear the now-meaningless peer count.
        self._set_status_label("disconnected")
        self._peers_label.setText("–")
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        if self._tray:
            self._tray.set_running(False)
        self._hide_info_banner()
        self._apply_button_styles()
        self._update_menu_state()
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

        # Notify only for truly unexpected crashes (not user stop, auth error,
        # force sync, app quit, etc.)
        if desc == "crashed" and not self._user_stopped and self._notifier:
            self._notifier.error(
                tr("notif.error"),
                tr("notif.process_crashed").replace("{code}", str(code)),
            )

    @Slot(str)
    def _on_path_not_found(self, path: str) -> None:
        """Handle shared path not found error."""
        self._engine.stop()
        self._reset_ui_stopped()
        self._append_log(f"⚠ {tr('notif.path_not_found_msg').replace('{path}', path)}")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("notif.error"))
        msg.setText(tr("notif.path_not_found_msg").replace("{path}", path))
        msg.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close)
        open_btn = msg.button(QMessageBox.StandardButton.Open)
        open_btn.setText(tr("menu.settings"))
        close_btn = msg.button(QMessageBox.StandardButton.Close)
        close_btn.setText(tr("action.close"))
        msg.setDefaultButton(QMessageBox.StandardButton.Open)
        if msg.exec() == QMessageBox.StandardButton.Open:
            self._open_settings(initial_tab=0)

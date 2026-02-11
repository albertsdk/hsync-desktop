# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

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

from PySide6.QtCore import QPoint, QSettings, QTimer, Qt, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.engine import HsyncEngine
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.settings_dialog import (
    ApiKeyDialog,
    LanKeyDialog,
    SETTINGS_APP,
    SETTINGS_ORG,
    SettingsDialog,
    build_hsync_args,
    get_saved_theme,
    are_notifications_enabled,
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


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


# ── Button styles ────────────────────────────────────────────────────────────
_BTN_START_ACTIVE = (
    "QPushButton { background-color: #2EA043; color: #FFFFFF;"
    " border: none; font-weight: bold; }"
    "QPushButton:hover { background-color: #278a39; }"
    "QPushButton:pressed { background-color: #1f7a30; }"
)
_BTN_STOP_ACTIVE = (
    "QPushButton { background-color: #CF222E; color: #FFFFFF;"
    " border: none; font-weight: bold; }"
    "QPushButton:hover { background-color: #b71d28; }"
    "QPushButton:pressed { background-color: #a01822; }"
)
_BTN_REFRESH_ACTIVE = (
    "QPushButton { background-color: #0969DA; color: #FFFFFF;"
    " border: none; font-weight: bold; }"
    "QPushButton:hover { background-color: #0860CA; }"
    "QPushButton:pressed { background-color: #0757BA; }"
)
_BTN_IDLE = ""  # Reset to theme default


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self, engine: HsyncEngine, tray: SystemTray) -> None:
        super().__init__()

        self._engine = engine
        self._tray = tray
        self._notifier = NotificationManager(tray)
        self._notifier.enabled = are_notifications_enabled()
        self._user_stopped = False  # track if stop was user-initiated

        # Preview statistics tracking
        self._preview_stats = PreviewStats()
        self._awaiting_preview_for_sync = False  # True when waiting for preview before sync
        self._pending_sync_path: str = ""  # Path saved for actual sync after preview
        self._is_dry_run_preview = False  # True when running in dry-run mode for initial preview

        self._load_ui()
        self._connect_signals()

        # Restore window geometry
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        geo = s.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)

        # Schedule auto-sync check after event loop starts
        if is_auto_sync_enabled():
            QTimer.singleShot(0, self._check_auto_sync)

    # ── UI loading from .ui file ─────────────────────────────────────────

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        # Load UI into self
        load_ui_widget("main_window", self)

        # Get widget references from .ui file
        self._btn_start: QPushButton = self.findChild(QPushButton, "btnStart")  # type: ignore[assignment]
        self._btn_stop: QPushButton = self.findChild(QPushButton, "btnStop")  # type: ignore[assignment]
        self._btn_refresh: QPushButton = self.findChild(QPushButton, "btnRefresh")  # type: ignore[assignment]
        self._btn_settings: QPushButton = self.findChild(QPushButton, "btnSettings")  # type: ignore[assignment]
        self._btn_browse: QToolButton = self.findChild(QToolButton, "btnBrowse")  # type: ignore[assignment]
        self._path_label: QLabel = self.findChild(QLabel, "pathLabel")  # type: ignore[assignment]
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._path_label.setOpenExternalLinks(False)
        self._path_label.linkActivated.connect(self._on_path_clicked)
        self._local_path: str = ""

        # Add folder icon label before path label
        from hsync_desktop.icons import icon as get_icon
        self._path_icon_label = QLabel(self.centralWidget())
        self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(16, 16))
        self._path_icon_label.setFixedSize(20, 20)
        self._path_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path_icon_label.hide()  # Hidden until path is set
        # Insert icon label before path label in the actionBarLayout
        # The actionBarLayout is a nested layout inside rootLayout (centralWidget's layout)
        root_layout: QVBoxLayout | None = self.centralWidget().layout()  # type: ignore[assignment]
        if root_layout:
            # First item in rootLayout should be actionBarLayout (QHBoxLayout)
            first_item = root_layout.itemAt(0)
            if first_item:
                action_bar_layout = first_item.layout()
                if isinstance(action_bar_layout, QHBoxLayout):
                    # Find index of path_label and insert icon before it
                    for i in range(action_bar_layout.count()):
                        item = action_bar_layout.itemAt(i)
                        if item and item.widget() == self._path_label:
                            action_bar_layout.insertWidget(i, self._path_icon_label)
                            break
        self._main_splitter: QSplitter = self.findChild(QSplitter, "mainSplitter")  # type: ignore[assignment]
        self._log_view: QPlainTextEdit = self.findChild(QPlainTextEdit, "logView")  # type: ignore[assignment]
        self._log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._log_view.customContextMenuRequested.connect(self._show_log_context_menu)

        # Bottom bar widgets
        self._status_dot: QLabel = self.findChild(QLabel, "statusDot")  # type: ignore[assignment]
        self._status_label: QLabel = self.findChild(QLabel, "statusLabel")  # type: ignore[assignment]
        self._role_label: QLabel = self.findChild(QLabel, "roleLabel")  # type: ignore[assignment]
        self._bucket_label: QLabel = self.findChild(QLabel, "bucketLabel")  # type: ignore[assignment]
        self._group_label: QLabel = self.findChild(QLabel, "groupLabel")  # type: ignore[assignment]
        self._lbl_peers: QLabel = self.findChild(QLabel, "lblPeers")  # type: ignore[assignment]
        self._peers_label: QLabel = self.findChild(QLabel, "peersLabel")  # type: ignore[assignment]
        self._lbl_sent: QLabel = self.findChild(QLabel, "lblSent")  # type: ignore[assignment]
        self._sent_label: QLabel = self.findChild(QLabel, "sentLabel")  # type: ignore[assignment]
        self._lbl_recv: QLabel = self.findChild(QLabel, "lblRecv")  # type: ignore[assignment]
        self._recv_label: QLabel = self.findChild(QLabel, "recvLabel")  # type: ignore[assignment]

        # Replace filePanelPlaceholder with actual FilePanel
        placeholder: QWidget = self.findChild(QWidget, "filePanelPlaceholder")  # type: ignore[assignment]
        self._file_panel = FilePanel()
        # Replace placeholder in splitter
        self._file_panel.setMinimumHeight(150)
        idx = self._main_splitter.indexOf(placeholder)
        if idx >= 0:
            placeholder.setParent(None)
            self._main_splitter.insertWidget(idx, self._file_panel)
        # Set initial sizes (2/3 files, 1/3 log)
        self._main_splitter.setSizes([400, 200])

        # Info banner (hidden by default, shown during reconnection)
        self._info_banner = self._create_info_banner()
        root_layout: QVBoxLayout = self.findChild(QVBoxLayout, "rootLayout")  # type: ignore[assignment]
        if root_layout:
            # Insert between action bar (index 0) and mainSplitter (index 1)
            root_layout.insertWidget(1, self._info_banner)

        # Apply log panel visibility setting
        self._apply_log_visibility()

        # Restore saved path and load files
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved_path = str(s.value("path/local", "", str))
        self._set_path(saved_path)
        if saved_path:
            self._load_local_files(saved_path)

        # Apply translations
        self._apply_translations()

        # Apply initial button styles (Start green, Stop idle)
        self._apply_button_styles()

        # Register for language change notifications
        register_language_callback(self._apply_translations)

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._btn_start.setText(tr("btn.start"))
        self._btn_stop.setText(tr("btn.stop"))
        self._btn_refresh.setText(tr("btn.refresh"))
        self._btn_settings.setText(tr("btn.settings"))
        self._btn_browse.setText(tr("btn.browse"))
        self._btn_browse.setToolTip(tr("label.path_placeholder"))
        self._update_path_display()
        self._status_label.setText(tr("status.disconnected"))
        self._role_label.setText(tr("role.client"))
        self._role_label.setToolTip(tr("role.client_tip"))
        self._lbl_peers.setText(tr("label.peers"))
        self._lbl_sent.setText(tr("label.sent"))
        self._lbl_recv.setText(tr("label.received"))

    # ── Signal wiring ────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Button signals
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._btn_settings.clicked.connect(self._open_settings)
        self._btn_browse.clicked.connect(self._browse_path)

        # Engine signals
        e = self._engine
        e.log_received.connect(self._append_log)
        e.status_changed.connect(self._on_status)
        e.peers_changed.connect(self._on_peers)
        e.master_changed.connect(self._on_master)
        e.bucket_detected.connect(lambda b: self._bucket_label.setText(b))
        e.group_detected.connect(lambda g: self._group_label.setText(g))
        e.file_transferred.connect(self._on_file_transferred)
        e.file_renamed.connect(self._on_file_renamed)
        e.directory_created.connect(self._on_directory_created)
        e.sync_completed.connect(lambda: self._notifier.sync_complete())
        e.error_occurred.connect(lambda msg: self._notifier.error(tr("notif.error"), msg))
        e.auth_error_occurred.connect(self._on_auth_error)
        e.master_conflict.connect(self._on_master_conflict)
        e.process_finished.connect(self._on_process_finished)
        # Preview signals
        e.preview_started.connect(self._on_preview_started)
        e.preview_ended.connect(self._on_preview_ended)
        e.file_status.connect(self._on_file_status)
        e.file_rename_status.connect(self._on_file_rename_status)

        # Tray signals
        t = self._tray
        t.toggle_window.connect(self._toggle_visibility)
        t.start_requested.connect(self._on_start)
        t.stop_requested.connect(self._on_stop)
        t.refresh_requested.connect(self._on_refresh)
        t.settings_requested.connect(self._open_settings)
        t.quit_requested.connect(self._quit)

    # ── Slots ────────────────────────────────────────────────────────────

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)
        # Auto-scroll to bottom
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(QPoint)
    def _show_log_context_menu(self, pos: QPoint) -> None:
        """Show custom context menu for the log viewer."""
        menu = QMenu(self._log_view)
        act_select_all = menu.addAction(tr("log.select_all"))
        act_copy = menu.addAction(tr("log.copy"))
        menu.addSeparator()
        act_clear = menu.addAction(tr("log.clear"))
        # Enable/disable based on state
        act_copy.setEnabled(self._log_view.textCursor().hasSelection())
        act_select_all.setEnabled(bool(self._log_view.toPlainText()))
        act_clear.setEnabled(bool(self._log_view.toPlainText()))
        # Execute and handle
        action = menu.exec(self._log_view.mapToGlobal(pos))
        if action == act_select_all:
            self._log_view.selectAll()
        elif action == act_copy:
            self._log_view.copy()
        elif action == act_clear:
            self._log_view.clear()

    def _parse_size(self, text: str) -> int:
        """Parse human-readable size like '1.2 MB' to bytes."""
        if not text:
            return 0
        text = text.strip()
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        for suffix, mult in multipliers.items():
            if text.upper().endswith(suffix):
                try:
                    return int(float(text[: -len(suffix)].strip()) * mult)
                except ValueError:
                    return 0
        try:
            return int(float(text))
        except ValueError:
            return 0

    @Slot(str)
    def _on_status(self, status: str) -> None:
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
        self._tray.update_status(status)

        if status in ("disconnected", "waiting"):
            self._file_panel.reset_all_to_local()
            if status == "disconnected":
                self._notifier.connection_lost()
        elif status == "connected":
            self._hide_info_banner()
            # Auto-run preview when connected to show file status
            if self._engine.is_running:
                self._engine.preview()

    # ── Info banner ──────────────────────────────────────────────────────

    def _create_info_banner(self) -> QFrame:
        """Create a hidden info banner for reconnection feedback."""
        banner = QFrame()
        banner.setObjectName("infoBanner")
        banner.setStyleSheet(
            "#infoBanner {"
            "  background-color: #0d6efd;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "}"
            "#infoBannerLabel {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 13px;"
            "}"
            "#infoBannerClose {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 16px;"
            "  background: transparent;"
            "  border: none;"
            "  padding: 0 4px;"
            "}"
            "#infoBannerClose:hover { color: #ccc; }"
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 4, 8, 4)
        self._info_banner_label = QLabel("", banner)
        self._info_banner_label.setObjectName("infoBannerLabel")
        layout.addWidget(self._info_banner_label, 1)
        close_btn = QPushButton("✕", banner)
        close_btn.setObjectName("infoBannerClose")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self._hide_info_banner)
        layout.addWidget(close_btn)
        banner.hide()
        return banner

    def _show_info_banner(self, message: str, auto_hide_ms: int = 15000) -> None:
        """Show the info banner with a message and optional auto-hide timer."""
        self._info_banner_label.setText(message)
        self._info_banner.show()
        # Auto-hide after timeout
        QTimer.singleShot(auto_hide_ms, self._hide_info_banner)

    def _hide_info_banner(self) -> None:
        """Hide the info banner."""
        self._info_banner.hide()

    @Slot(int)
    def _on_peers(self, count: int) -> None:
        self._peers_label.setText(str(count))
        self._notifier.peer_joined(count)

    @Slot(bool)
    def _on_master(self, is_master: bool) -> None:
        if is_master:
            self._role_label.setText(tr("role.master"))
            self._role_label.setToolTip(tr("role.master_tip"))
            self._notifier.became_master()
        else:
            self._role_label.setText(tr("role.client"))
            self._role_label.setToolTip(tr("role.client_tip"))

    @Slot(str, str)
    def _on_file_transferred(self, direction: str, filename: str) -> None:
        st = self._engine.stats
        self._sent_label.setText(
            f"{st.files_sent} ({_format_bytes(st.bytes_sent)})"
        )
        self._recv_label.setText(
            f"{st.files_received} ({_format_bytes(st.bytes_received)})"
        )
        # Convert absolute path to relative path for table lookup
        base_path = self._local_path
        rel_path = filename
        if base_path and filename.startswith(base_path):
            rel_path = filename[len(base_path):].lstrip("/\\")
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
            self._notifier.download_complete(filename)
            self._file_panel.update_file_status(
                rel_path, "synced", mtime=mtime,
                client_cid=client_cid, client_ip=client_ip,
            )
        elif direction == "↑":
            self._file_panel.update_file_status(
                rel_path, "synced", mtime=mtime,
                client_cid=client_cid, client_ip=client_ip,
            )
        elif direction == "✕":
            # File was deleted - show briefly then remove
            self._file_panel.mark_deleted(rel_path)

    @Slot(str, str)
    def _on_file_renamed(self, old_path: str, new_path: str) -> None:
        """Handle a file rename event from the engine."""
        base_path = self._local_path
        old_rel = old_path
        new_rel = new_path
        if base_path:
            if old_path.startswith(base_path):
                old_rel = old_path[len(base_path):].lstrip("/\\")
            if new_path.startswith(base_path):
                new_rel = new_path[len(base_path):].lstrip("/\\")
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
            old_rel, new_rel, mtime=mtime,
            client_cid=client_cid, client_ip=client_ip,
        )

    @Slot(str)
    def _on_directory_created(self, dirpath: str) -> None:
        """Handle a directory creation event from the engine."""
        base_path = self._local_path
        rel_path = dirpath
        if base_path and dirpath.startswith(base_path):
            rel_path = dirpath[len(base_path):].lstrip("/\\")
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
            rel_path, "synced", size=0, mtime=mtime,
            client_cid=client_cid, client_ip=client_ip,
        )

    @Slot(str, str, str)
    def _on_master_conflict(self, conflict_type: str, peer_cid: str, peer_address: str) -> None:
        """Handle a force_master conflict or takeover notification."""
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
                tr("notif.master_takeover")
                .replace("{cid}", peer_cid)
                .replace("{ip}", peer_address)
            )
        self._notifier.warning(tr("notif.master_conflict_title"), msg)
        self._append_log(f"⚠ {msg}")

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
            rel_path = filepath[len(base_path):].lstrip("/\\")
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

    @Slot(str, str, int)
    def _on_file_rename_status(self, old_path: str, new_path: str, size: int) -> None:
        """Handle file rename status from preview."""
        base_path = self._local_path
        rel_old = old_path
        if base_path and old_path.startswith(base_path):
            rel_old = old_path[len(base_path):].lstrip("/\\")
        self._file_panel.update_file_status(rel_old, "to_rename", size)
        self._preview_stats.to_rename += 1

    def _show_preview_summary(self) -> None:
        """Show the preview summary dialog and start sync if confirmed."""
        s = self._preview_stats
        nothing_to_sync = (
            s.to_download == 0 and s.to_upload == 0 and s.to_delete == 0
            and s.to_rename == 0
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
                self._btn_start.setEnabled(True)
                self._btn_stop.setEnabled(False)
                self._tray.set_running(False)
                self._set_path_editable(True)
                self._apply_button_styles()
            # If stdin preview, just close dialog - process keeps running
            self._is_dry_run_preview = False

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._tray.set_running(False)
        self._set_path_editable(True)
        self._hide_info_banner()
        self._apply_button_styles()
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

        # Notify only for truly unexpected crashes (not user stop, auth error,
        # force sync, app quit, etc.)
        if desc == "crashed" and not self._user_stopped:
            self._notifier.error(
                tr("notif.error"),
                tr("notif.process_crashed").replace("{code}", str(code)),
            )

    @Slot(str)
    def _on_auth_error(self, _error_msg: str) -> None:
        """Handle authentication error by showing the appropriate dialog."""
        # Stop the current process
        self._engine.stop()

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        lan_enabled = bool(s.value("lan/enabled", False, bool))

        if lan_enabled:
            # LAN mode: show LAN key dialog
            self._append_log(f"⚠ {tr('lanauth.error_message')}")
            dlg = LanKeyDialog(self)
            if dlg.exec() == LanKeyDialog.DialogCode.Accepted:
                self._append_log(f"--- {tr('lanauth.retrying')} ---")
                self._retry_after_auth_fix()
            else:
                self._reset_ui_stopped()
        else:
            # Server mode: show API key dialog
            self._append_log(f"⚠ {tr('apikey.error_message')}")
            dlg = ApiKeyDialog(self)
            if dlg.exec() == ApiKeyDialog.DialogCode.Accepted:
                self._append_log("--- Retrying with new API key... ---")
                self._retry_after_auth_fix()
            else:
                self._reset_ui_stopped()

    def _retry_after_auth_fix(self) -> None:
        """Restart sync in dry-run mode after credentials have been updated."""
        # Immediately update status bar to show "connecting" state
        self._on_status("connecting")
        # Show info banner for extra visibility
        self._show_info_banner(f"🔄 {tr('banner.reconnecting')}")
        local_path = self._local_path
        if local_path:
            args = build_hsync_args(local_path, force_dry_run=True)
            if args:
                self._log_view.clear()
                self._file_panel.load_local_files(local_path)
                self._awaiting_preview_for_sync = True
                self._is_dry_run_preview = True
                self._pending_sync_path = local_path
                if self._engine.start(args):
                    self._btn_start.setEnabled(False)
                    self._btn_stop.setEnabled(True)
                    self._btn_refresh.setEnabled(False)
                    self._tray.set_running(True)
                    self._set_path_editable(False)
                    self._apply_button_styles()
                    return
        self._hide_info_banner()
        self._reset_ui_stopped()

    def _reset_ui_stopped(self) -> None:
        """Reset UI buttons to the stopped state."""
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._tray.set_running(False)
        self._hide_info_banner()
        self._set_path_editable(True)
        self._apply_button_styles()

    def _set_path_editable(self, editable: bool) -> None:
        """Enable or disable the browse button."""
        self._btn_browse.setEnabled(editable)

    def _set_path(self, path: str) -> None:
        """Set the local path and update the display."""
        self._local_path = path.strip()
        self._update_path_display()

    def _update_path_display(self) -> None:
        """Update the path label display."""
        from hsync_desktop.icons import icon as get_icon
        if self._local_path:
            # Update icon (may have changed with theme)
            self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(16, 16))
            self._path_icon_label.show()
            link_color = self._path_label.palette().color(
                self._path_label.palette().ColorRole.Link
            ).name()
            self._path_label.setText(
                f'<a href="open" style="color:{link_color}; text-decoration:none;">'
                f'{self._local_path}</a>'
            )
            self._path_label.setToolTip(self._local_path)
            self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._path_icon_label.hide()
            mid = self._path_label.palette().color(
                self._path_label.palette().ColorRole.PlaceholderText
            ).name()
            self._path_label.setText(
                f'<span style="color:{mid};">{tr("label.path_placeholder")}</span>'
            )
            self._path_label.setToolTip("")
            self._path_label.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_path_clicked(self, _link: str) -> None:
        """Open the local path directory in the system file manager."""
        if self._local_path and os.path.isdir(self._local_path):
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._local_path))

    def _apply_button_styles(self) -> None:
        """Apply colored styles to Start/Stop/Refresh buttons based on enabled state."""
        self._btn_start.setStyleSheet(
            _BTN_START_ACTIVE if self._btn_start.isEnabled() else _BTN_IDLE
        )
        self._btn_stop.setStyleSheet(
            _BTN_STOP_ACTIVE if self._btn_stop.isEnabled() else _BTN_IDLE
        )
        self._btn_refresh.setStyleSheet(
            _BTN_REFRESH_ACTIVE if self._btn_refresh.isEnabled() else _BTN_IDLE
        )

    # ── Actions ──────────────────────────────────────────────────────────

    def _show_disclaimer(self) -> bool:
        """Show disclaimer dialog. Returns True if user accepts."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if s.value("ui/disclaimer_accepted", False, bool):
            return True

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("disclaimer.title"))
        msg.setText(tr("disclaimer.message"))
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
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

    def _on_start(self) -> None:
        # Show disclaimer first
        if not self._show_disclaimer():
            return

        local_path = self._local_path
        if not local_path:
            self._append_log("⚠ Please select a local directory first.")
            return
        # Start in dry-run mode first to show preview
        args = build_hsync_args(local_path, force_dry_run=True)
        if not args:
            self._append_log("⚠ Please configure a bucket name in Settings.")
            return
        # Persist path
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("path/local", local_path)
        self._log_view.clear()
        self._file_panel.load_local_files(local_path)
        self._user_stopped = False
        self._notifier.user_stopped = False
        # Set flags to show preview summary when dry-run completes
        self._awaiting_preview_for_sync = True
        self._is_dry_run_preview = True  # We're in dry-run mode for initial preview
        self._pending_sync_path = local_path  # Save path for actual sync
        if self._engine.start(args):
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_refresh.setEnabled(False)  # Disable until preview completes
            self._tray.set_running(True)
            self._set_path_editable(False)
            self._apply_button_styles()

    def _on_stop(self) -> None:
        self._user_stopped = True
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

    def _browse_path(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("label.path_placeholder"))
        if d:
            self._set_path(d)
            self._load_local_files(d)

    def _load_local_files(self, path: str) -> None:
        """Load files from the selected directory into the file panel."""
        if path:
            self._file_panel.load_local_files(path)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        # Disable connection-critical settings while sync is running
        dlg.set_connection_active(self._engine.is_running)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            theme = get_saved_theme()
            app = QApplication.instance()
            if app:
                apply_theme(app, theme)  # type: ignore[arg-type]
                self._refresh_icons_for_theme()
            self._notifier.enabled = are_notifications_enabled()
            self._apply_log_visibility()

    def _refresh_icons_for_theme(self) -> None:
        """Refresh all icons after theme change."""
        from hsync_desktop.icons import clear_icon_cache, icon as get_icon
        clear_icon_cache()
        # Refresh path icon
        if self._local_path:
            self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(16, 16))
        # Refresh file panel icons
        self._file_panel.refresh_icons_for_theme()

    def _apply_log_visibility(self) -> None:
        """Show or hide the log panel based on settings."""
        show_log = is_log_panel_visible()
        if show_log:
            self._log_view.show()
            # Restore splitter sizes if log was hidden
            sizes = self._main_splitter.sizes()
            if sizes[1] == 0:
                self._main_splitter.setSizes([400, 200])
        else:
            self._log_view.hide()
            # Give all space to file panel
            sizes = self._main_splitter.sizes()
            total = sum(sizes)
            self._main_splitter.setSizes([total, 0])

    # ── Window management ────────────────────────────────────────────────

    def _toggle_visibility(self) -> None:
        """Toggle window visibility (show/hide)."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit(self) -> None:
        """Quit the application properly."""
        if self._engine.is_running:
            self._engine.stop()
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(
            "window/geometry", self.saveGeometry()
        )
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray instead of closing (no notification)."""
        if self._tray.isVisible():
            event.ignore()
            self.hide()
        else:
            # No tray available – actually close
            self._quit()
            event.accept()

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
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit

from hsync_common.endpoint import parse_host_port
from hsync_common.format import format_bytes
from hsync_common.logger import format_timestamp
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
    QProgressBar,
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
from hsync_desktop.fonts import log_monospace_font
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


class UiBuildMixin:
    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        # Load UI into self
        load_ui_widget("main_window", self)

        # Get widget references from .ui file
        self._btn_start: QPushButton = self.findChild(QPushButton, "btnStart")  # type: ignore[assignment]
        self._btn_stop: QPushButton = self.findChild(QPushButton, "btnStop")  # type: ignore[assignment]
        self._btn_refresh: QPushButton = self.findChild(QPushButton, "btnRefresh")  # type: ignore[assignment]
        # Set icons for action buttons (icon-only, no text)
        from PySide6.QtCore import QSize

        from hsync_desktop.icons import icon as get_icon

        icon_size = QSize(18, 18)
        for btn, ico_name in (
            (self._btn_start, "media-playback-start"),
            (self._btn_stop, "media-playback-stop"),
            (self._btn_refresh, "view-refresh"),
        ):
            btn.setIcon(get_icon(ico_name))
            btn.setIconSize(icon_size)
            btn.setText("")
        self._path_label: QLabel = self.findChild(QLabel, "pathLabel")  # type: ignore[assignment]
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._path_label.setOpenExternalLinks(False)
        self._path_label.linkActivated.connect(self._on_path_clicked)
        self._local_path: str = ""
        # Active share name (bucket) shown next to the folder icon; empty until
        # the engine detects one, then seeded from the configured share.
        self._bucket: str = ""

        # Add folder icon label before path label
        self._path_icon_label = QLabel(self.centralWidget())
        self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(16, 16))
        self._path_icon_label.setFixedSize(20, 20)
        self._path_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path_icon_label.hide()  # Hidden until path is set

        # Sync direction icon (right of path label)
        self._sync_dir_icon = QLabel(self.centralWidget())
        self._sync_dir_icon.setFixedSize(20, 20)
        self._sync_dir_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_dir_icon.hide()

        # Remote endpoint icon + label (right of sync direction icon)
        self._remote_icon = QLabel(self.centralWidget())
        self._remote_icon.setFixedSize(20, 20)
        self._remote_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._remote_icon.hide()
        self._remote_label = QLabel(self.centralWidget())
        self._remote_label.hide()

        # Insert widgets into the actionBarLayout
        # Layout order: ... [folder-icon] [path-label] [sync-dir-icon] [remote-icon] [remote-label] [browse-btn] ...
        central = self.centralWidget()
        root_layout = central.layout() if central is not None else None
        if root_layout:
            first_item = root_layout.itemAt(0)
            if first_item:
                action_bar_layout = first_item.layout()
                if isinstance(action_bar_layout, QHBoxLayout):
                    for i in range(action_bar_layout.count()):
                        item = action_bar_layout.itemAt(i)
                        if item and item.widget() == self._path_label:
                            action_bar_layout.insertWidget(i, self._path_icon_label)
                            # Insert after path_label (i+2 because we just inserted one)
                            action_bar_layout.insertWidget(i + 2, self._sync_dir_icon)
                            action_bar_layout.insertWidget(i + 3, self._remote_icon)
                            action_bar_layout.insertWidget(i + 4, self._remote_label)
                            break
        self._main_splitter: QSplitter = self.findChild(QSplitter, "mainSplitter")  # type: ignore[assignment]
        self._log_view: QPlainTextEdit = self.findChild(QPlainTextEdit, "logView")  # type: ignore[assignment]
        self._log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._log_view.customContextMenuRequested.connect(self._show_log_context_menu)
        # Limit log lines to prevent memory issues with long-running sessions
        self._log_view.setMaximumBlockCount(10000)
        # Use the desktop's monospace font, two points smaller: the log lines are
        # long, so the extra width keeps them readable without scrolling.
        self._log_view.setFont(log_monospace_font())

        # Bottom bar widgets
        self._status_dot: QLabel = self.findChild(QLabel, "statusDot")  # type: ignore[assignment]
        self._status_label: QLabel = self.findChild(QLabel, "statusLabel")  # type: ignore[assignment]
        self._role_label: QLabel = self.findChild(QLabel, "roleLabel")  # type: ignore[assignment]
        # Add role icon before roleLabel in the bottom bar layout
        self._role_icon = QLabel()
        self._role_icon.setFixedSize(16, 16)
        bottom_layout: QHBoxLayout = self.findChild(QHBoxLayout, "bottomBarLayout")  # type: ignore[assignment]
        if bottom_layout:
            role_idx = bottom_layout.indexOf(self._role_label)
            if role_idx >= 0:
                bottom_layout.insertWidget(role_idx, self._role_icon)
        self._group_label: QLabel = self.findChild(QLabel, "groupLabel")  # type: ignore[assignment]
        self._lbl_peers: QLabel = self.findChild(QLabel, "lblPeers")  # type: ignore[assignment]
        self._peers_label: QLabel = self.findChild(QLabel, "peersLabel")  # type: ignore[assignment]
        self._lbl_sent: QLabel = self.findChild(QLabel, "lblSent")  # type: ignore[assignment]
        self._sent_label: QLabel = self.findChild(QLabel, "sentLabel")  # type: ignore[assignment]
        self._lbl_recv: QLabel = self.findChild(QLabel, "lblRecv")  # type: ignore[assignment]
        self._recv_label: QLabel = self.findChild(QLabel, "recvLabel")  # type: ignore[assignment]

        # Shared-folder size (local / total of the share), right side before Peers.
        self._share_size_label = QLabel(self.centralWidget())
        self._share_size_label.setText("—")
        self._share_size_label.setForegroundRole(self.palette().ColorRole.PlaceholderText)
        self._share_local_bytes: int = -1
        self._share_total_bytes: int = -1
        if bottom_layout:
            peers_idx = bottom_layout.indexOf(self._lbl_peers)
            if peers_idx >= 0:
                bottom_layout.insertWidget(peers_idx, self._share_size_label)
                bottom_layout.insertSpacing(peers_idx + 1, 14)
            else:
                bottom_layout.addWidget(self._share_size_label)

        # Make bandwidth labels clickable (both the label header and value)
        self._lbl_sent.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl_sent.setToolTip(tr("bandwidth.click_to_edit"))
        self._sent_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sent_label.setToolTip(tr("bandwidth.click_to_edit"))
        self._lbl_recv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl_recv.setToolTip(tr("bandwidth.click_to_edit"))
        self._recv_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recv_label.setToolTip(tr("bandwidth.click_to_edit"))

        # Connect bandwidth label click handlers using event filter
        for label in [self._lbl_sent, self._sent_label, self._lbl_recv, self._recv_label]:
            label.installEventFilter(self)

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

        # Info toast: an overlay child of the central widget (never in the
        # layout, so showing/hiding it cannot move the content).
        self._info_banner = self._create_info_banner()
        self._info_banner.setParent(self.centralWidget())
        self._info_banner.hide()
        self._info_banner_kind: str | None = None
        self._info_timer = QTimer(self)
        self._info_timer.setSingleShot(True)
        self._info_timer.timeout.connect(self._hide_info_banner)

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

        # Create classic menu bar
        self._create_menu_bar()

        # Set initial button/menu/tray state (disables Start if no path)
        self._update_menu_state()

        # Register for language change notifications
        register_language_callback(self._apply_translations)

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._btn_start.setToolTip(tr("btn.start"))
        self._btn_stop.setToolTip(tr("btn.stop"))
        self._btn_refresh.setToolTip(tr("btn.refresh"))
        self._update_path_display()
        self._status_label.setText(tr("status.disconnected"))
        # Seed the active share name from the configured share; the window title
        # stays the app name (the share is shown next to the folder icon).
        self._on_bucket_detected(
            str(QSettings(SETTINGS_ORG, SETTINGS_APP).value("sync/bucket", "", str)).strip()
        )
        self._retranslate_role()
        self._update_peers_label_title()
        self._share_size_label.setToolTip(tr("tip.share_size"))
        self._render_share_size()
        self._lbl_sent.setText(tr("label.sent"))
        self._lbl_recv.setText(tr("label.received"))
        # The file table owns its column headers, so re-localize them here.
        self._file_panel.retranslate_columns()
        # Bandwidth label tooltips
        self._lbl_sent.setToolTip(tr("bandwidth.click_to_edit"))
        self._sent_label.setToolTip(tr("bandwidth.click_to_edit"))
        self._lbl_recv.setToolTip(tr("bandwidth.click_to_edit"))
        self._recv_label.setToolTip(tr("bandwidth.click_to_edit"))
        # Menu bar translations
        if hasattr(self, "_menu_sync"):
            self._menu_sync.setTitle(tr("menu.sync"))
            self._act_start.setText(tr("menu.sync.start"))
            self._act_stop.setText(tr("menu.sync.stop"))
            self._act_refresh.setText(tr("menu.sync.refresh"))
            self._menu_direction.setTitle(tr("menu.sync.direction"))
            self._act_dir_bidi.setText(tr("menu.sync.direction.bidirectional"))
            self._act_dir_upload.setText(tr("menu.sync.direction.upload_only"))
            self._act_dir_download.setText(tr("menu.sync.direction.download_only"))
            self._act_quit.setText(tr("menu.sync.quit"))
            self._menu_file.setTitle(tr("menu.file"))
            self._act_file_open.setText(tr("menu.file.open"))
            self._act_file_open_with.setText(tr("menu.file.open_with"))
            self._act_file_copy_to.setText(tr("menu.file.copy_to"))
            self._act_file_rename.setText(tr("menu.file.rename"))
            self._act_file_send.setText(tr("action.send_now"))
            self._act_file_receive.setText(tr("action.receive_now"))
            self._act_file_trash.setText(tr("menu.file.trash"))
            self._act_file_properties.setText(tr("menu.file.properties"))
            self._act_settings.setText(tr("menu.settings"))
            self._act_setup_wizard.setText(tr("menu.setup_wizard"))
            self._menu_help.setTitle(tr("menu.help"))
            self._act_help_docs.setText(tr("menu.help.docs"))
            self._act_help_github.setText(tr("menu.help.github"))
            self._act_help_license.setText(tr("menu.help.license"))
            self._act_help_about.setText(tr("menu.help.about"))

    def _update_peers_label_title(self) -> None:
        """Label the presence count for what it actually counts.

        p2p counts devices (self + peers); server mode counts the share accounts
        with a live WebSocket, so "Devices" would overstate it when two devices
        share one account.
        """
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        p2p_enabled = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))
        self._lbl_peers.setText(tr("label.peers" if p2p_enabled else "label.users"))

    # ── Menu bar ──────────────────────────────────────────────────────────

    def _create_menu_bar(self) -> None:
        """Create the classic menu bar with Sync, File, Settings, Help."""
        menubar = self.menuBar()
        # Use Qt menu bar (not native) so Alt mnemonics work on GNOME/Ubuntu
        menubar.setNativeMenuBar(False)

        # ── Sync menu ─────────────────────────────────────────────────
        self._menu_sync = menubar.addMenu(tr("menu.sync"))

        self._act_start = QAction(tr("menu.sync.start"), self)
        self._act_start.setShortcut("Ctrl+Shift+S")
        self._act_start.triggered.connect(self._on_start)
        self._menu_sync.addAction(self._act_start)

        self._act_stop = QAction(tr("menu.sync.stop"), self)
        self._act_stop.setEnabled(False)
        self._act_stop.triggered.connect(self._on_stop)
        self._menu_sync.addAction(self._act_stop)

        self._act_refresh = QAction(tr("menu.sync.refresh"), self)
        self._act_refresh.setShortcut("F5")
        self._act_refresh.setEnabled(False)
        self._act_refresh.triggered.connect(self._on_refresh)
        self._menu_sync.addAction(self._act_refresh)

        # ── Sync direction submenu ──────────────────────────────────
        self._menu_direction = self._menu_sync.addMenu(tr("menu.sync.direction"))
        self._direction_group = QActionGroup(self)
        self._direction_group.setExclusive(True)

        self._act_dir_bidi = QAction(tr("menu.sync.direction.bidirectional"), self)
        self._act_dir_bidi.setCheckable(True)
        self._act_dir_bidi.setData("bidirectional")
        self._direction_group.addAction(self._act_dir_bidi)
        self._menu_direction.addAction(self._act_dir_bidi)

        self._act_dir_upload = QAction(tr("menu.sync.direction.upload_only"), self)
        self._act_dir_upload.setCheckable(True)
        self._act_dir_upload.setData("upload-only")
        self._direction_group.addAction(self._act_dir_upload)
        self._menu_direction.addAction(self._act_dir_upload)

        self._act_dir_download = QAction(tr("menu.sync.direction.download_only"), self)
        self._act_dir_download.setCheckable(True)
        self._act_dir_download.setData("download-only")
        self._direction_group.addAction(self._act_dir_download)
        self._menu_direction.addAction(self._act_dir_download)

        # Load saved direction and check the right action
        saved_dir = QSettings(SETTINGS_ORG, SETTINGS_APP).value(
            "sync/direction", "bidirectional", str
        )
        for act in self._direction_group.actions():
            if act.data() == saved_dir:
                act.setChecked(True)
                break
        else:
            self._act_dir_bidi.setChecked(True)

        self._direction_group.triggered.connect(self._on_direction_changed)

        self._menu_sync.addSeparator()

        self._act_quit = QAction(tr("menu.sync.quit"), self)
        self._act_quit.setShortcut("Ctrl+Q")
        self._act_quit.triggered.connect(self._quit)
        self._menu_sync.addAction(self._act_quit)

        # ── File menu ─────────────────────────────────────────────────
        self._menu_file = menubar.addMenu(tr("menu.file"))

        self._act_file_open = QAction(tr("menu.file.open"), self)
        self._act_file_open.setShortcut("Return")  # Enter key
        self._act_file_open.triggered.connect(self._menu_file_open)
        self._menu_file.addAction(self._act_file_open)

        self._act_file_open_with = QAction(tr("menu.file.open_with"), self)
        self._act_file_open_with.setShortcut("Ctrl+O")
        self._act_file_open_with.triggered.connect(self._menu_file_open_with)
        self._menu_file.addAction(self._act_file_open_with)

        self._menu_file.addSeparator()

        self._act_file_copy_to = QAction(tr("menu.file.copy_to"), self)
        self._act_file_copy_to.setShortcut("Ctrl+Shift+C")
        self._act_file_copy_to.triggered.connect(self._menu_file_copy_to)
        self._menu_file.addAction(self._act_file_copy_to)

        self._act_file_rename = QAction(tr("menu.file.rename"), self)
        self._act_file_rename.setShortcut("F2")
        self._act_file_rename.triggered.connect(self._menu_file_rename)
        self._menu_file.addAction(self._act_file_rename)

        self._menu_file.addSeparator()

        self._act_file_send = QAction(tr("action.send_now"), self)
        self._act_file_send.triggered.connect(self._menu_file_send)
        self._menu_file.addAction(self._act_file_send)

        self._act_file_receive = QAction(tr("action.receive_now"), self)
        self._act_file_receive.triggered.connect(self._menu_file_receive)
        self._menu_file.addAction(self._act_file_receive)

        self._menu_file.addSeparator()

        self._act_file_trash = QAction(tr("menu.file.trash"), self)
        self._act_file_trash.setShortcut("Delete")
        self._act_file_trash.triggered.connect(self._menu_file_trash)
        self._menu_file.addAction(self._act_file_trash)

        self._menu_file.addSeparator()

        self._act_file_properties = QAction(tr("menu.file.properties"), self)
        self._act_file_properties.triggered.connect(self._menu_file_properties)
        self._menu_file.addAction(self._act_file_properties)

        # Disable all File menu actions initially (no selection)
        self._set_file_menu_enabled(False)

        # ── Settings (direct menu item) ───────────────────────────────
        self._act_settings = QAction(tr("menu.settings"), self)
        self._act_settings.triggered.connect(self._open_settings)
        menubar.addAction(self._act_settings)

        self._act_setup_wizard = QAction(tr("menu.setup_wizard"), self)
        self._act_setup_wizard.triggered.connect(self._open_setup_wizard)
        menubar.addAction(self._act_setup_wizard)

        # ── Help menu ─────────────────────────────────────────────────
        # External links first, then a separator and the local app-info
        # dialogs, with "About" kept last (the conventional position).
        self._menu_help = menubar.addMenu(tr("menu.help"))

        self._act_help_docs = QAction(tr("menu.help.docs"), self)
        self._act_help_docs.triggered.connect(self._open_documentation)
        self._menu_help.addAction(self._act_help_docs)

        self._act_help_github = QAction(tr("menu.help.github"), self)
        self._act_help_github.triggered.connect(self._open_github)
        self._menu_help.addAction(self._act_help_github)

        self._menu_help.addSeparator()

        self._act_help_license = QAction(tr("menu.help.license"), self)
        self._act_help_license.triggered.connect(self._show_license)
        self._menu_help.addAction(self._act_help_license)

        self._act_help_about = QAction(tr("menu.help.about"), self)
        self._act_help_about.triggered.connect(self._show_about)
        self._menu_help.addAction(self._act_help_about)

    def _set_file_menu_enabled(self, enabled: bool) -> None:
        """Enable or disable all File menu actions."""
        for act in (
            self._act_file_open,
            self._act_file_open_with,
            self._act_file_copy_to,
            self._act_file_rename,
            self._act_file_trash,
            self._act_file_properties,
        ):
            act.setEnabled(enabled)
        # Send/Receive also need a stopped engine.
        selection_sync = enabled and not self._engine.is_running
        self._act_file_send.setEnabled(selection_sync)
        self._act_file_receive.setEnabled(selection_sync)

    def _update_menu_state(self) -> None:
        """Update menu/button/tray enabled state based on app state."""
        if not hasattr(self, "_act_start"):
            return  # Menu bar not yet created
        is_running = self._engine.is_running
        has_path = bool(self._local_path)

        can_start = not is_running and has_path
        self._act_start.setEnabled(can_start)
        self._btn_start.setEnabled(can_start)
        if self._tray:
            self._tray.set_start_enabled(can_start)
        self._act_stop.setEnabled(is_running)
        self._act_refresh.setEnabled(is_running and self._btn_refresh.isEnabled())
        # Send/Receive of a selection are one-shot commands: only while stopped.
        self._act_file_send.setEnabled(not is_running and self._has_file_selection())
        self._act_file_receive.setEnabled(not is_running and self._has_file_selection())
        self._file_panel._table.set_sync_active(is_running)
        self._apply_button_styles()

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)
        # Auto-scroll to bottom
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_desktop_log(self, level: str, message: str) -> None:
        """Append a desktop-originated line in the client log format.

        Client lines carry ``<timestamp> - [pid] [client_id] LEVEL:``; desktop
        events have no client CID, so ``[desktop]`` takes that slot.
        """
        stamp = format_timestamp({"time": datetime.now()})
        self._append_log(f"{stamp} - [desktop] {level}: {message}")

    @Slot(str, str)
    def _on_engine_error(self, message: str, reason: str = "") -> None:
        """Record an engine error, mirror it into the log, and surface it.

        During a scoped Send/Receive the error is that operation's outcome
        (``_finish_selection_sync``); otherwise it raises the generic error
        notification. An engine launch failure is skipped here — ``_start_engine``
        reports it once with its own dialog.
        """
        self._last_engine_error = message
        if message:
            self._append_desktop_log("ERROR", message)

        # An engine launch failure has its own dialog (see ``_start_engine``);
        # ignore it here so it is never surfaced or finalized twice.
        if self._engine_starting:
            return

        if self._selection_sync_active:
            p2p_enabled = bool(
                QSettings(SETTINGS_ORG, SETTINGS_APP).value(
                    "p2p/enabled", DEFAULT_P2P_ENABLED, bool
                )
            )
            outcome = (
                "server_unreachable" if reason == "connection" and not p2p_enabled else "failed"
            )
            self._finish_selection_sync(outcome)
            return

        if message and self._notifier:
            self._notifier.error(tr("notif.error"), message)

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

    def _create_info_banner(self) -> QFrame:
        """Create a hidden overlay toast for transient feedback."""
        banner = QFrame()
        banner.setObjectName("infoBanner")
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 640px keeps the toast comfortable without spanning the window; the
        # effective width is sized in _position_info_banner (220px..this cap).
        banner.setMaximumWidth(640)
        banner.setStyleSheet(
            "#infoBanner {"
            "  background-color: #0d6efd;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "}"
            "#infoBannerLabel {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 14px;"
            "}"
            "#infoBannerClose {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 18px;"
            "  background: transparent;"
            "  border: none;"
            "  padding: 0 4px;"
            "}"
            "#infoBannerClose:hover { color: #ccc; }"
            "#infoProgress {"
            "  background: rgba(255, 255, 255, 0.35);"
            "  border: none;"
            "  border-radius: 2px;"
            "}"
            "#infoProgress::chunk {"
            "  background: #ffffff;"
            "  border-radius: 2px;"
            "}"
        )
        outer = QVBoxLayout(banner)
        outer.setContentsMargins(14, 8, 10, 8)
        outer.setSpacing(4)
        row = QHBoxLayout()
        self._info_banner_label = QLabel("", banner)
        self._info_banner_label.setObjectName("infoBannerLabel")
        self._info_banner_label.setWordWrap(True)
        row.addWidget(self._info_banner_label, 1)
        close_btn = QPushButton("✕", banner)
        close_btn.setObjectName("infoBannerClose")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self._hide_info_banner)
        row.addWidget(close_btn)
        outer.addLayout(row)
        # Indeterminate bar for ongoing work (shown only for kind="progress").
        self._info_progress = QProgressBar(banner)
        self._info_progress.setObjectName("infoProgress")
        self._info_progress.setRange(0, 0)
        self._info_progress.setFixedHeight(5)
        self._info_progress.setTextVisible(False)
        self._info_progress.hide()
        outer.addWidget(self._info_progress)
        banner.hide()
        return banner

    def _position_info_banner(self) -> None:
        """Place the toast bottom-right, above the bottom bar."""
        # isHidden() is the explicit hide state; isVisible() is also false when
        # the main window is not shown yet (startup/background), which must not
        # skip the placement.
        if self._info_banner.isHidden():
            return
        central = self.centralWidget()
        if central is None:
            return
        # Comfortably larger than the old 420px cap, but not full-width; at
        # least 220px and never wider than the window. Re-applied on resize.
        width = min(640, max(220, central.width() - 32))
        self._info_banner.setFixedWidth(width)
        self._info_banner.adjustSize()
        margin = 16
        status_top = self._status_label.mapTo(central, QPoint(0, 0)).y()
        y = status_top - self._info_banner.height() - 8
        x = central.width() - self._info_banner.width() - margin
        self._info_banner.move(max(margin, x), max(margin, y))

    def _show_info_banner(
        self, message: str, auto_hide_ms: int = 15000, kind: str = "info"
    ) -> None:
        """Show the overlay toast.

        ``kind`` is ``progress`` (persistent until hidden), ``warning``,
        ``info`` or ``outcome``. Outcome toasts survive the engine process
        finishing; run-scoped ones are cleared. ``auto_hide_ms <= 0`` keeps it
        visible until ``_hide_info_banner``.
        """
        self._info_banner_kind = kind
        self._info_banner_label.setText(message)
        self._info_progress.setVisible(kind == "progress")
        self._info_banner.adjustSize()
        self._info_banner.show()
        self._position_info_banner()
        self._info_banner.raise_()
        if auto_hide_ms > 0:
            self._info_timer.start(auto_hide_ms)
        else:
            self._info_timer.stop()

    def _hide_info_banner(self) -> None:
        """Hide the toast and stop its auto-hide timer."""
        self._info_timer.stop()
        self._info_banner.hide()
        self._info_banner_kind = None

    def _apply_button_styles(self) -> None:
        """Apply colored styles to Start/Stop/Refresh buttons based on enabled state."""
        from hsync_desktop.icons import themed_icon

        # Start button: green background when enabled
        self._btn_start.setStyleSheet(
            _BTN_START_ACTIVE if self._btn_start.isEnabled() else _BTN_IDLE
        )
        # Start icon: white when enabled, dark when disabled
        start_icon_color = "#FFFFFF" if self._btn_start.isEnabled() else "#424242"
        self._btn_start.setIcon(themed_icon("media-playback-start", start_icon_color))

        # Stop button: red background when enabled
        self._btn_stop.setStyleSheet(_BTN_STOP_ACTIVE if self._btn_stop.isEnabled() else _BTN_IDLE)
        # Stop icon: white when enabled, dark when disabled
        stop_icon_color = "#FFFFFF" if self._btn_stop.isEnabled() else "#424242"
        self._btn_stop.setIcon(themed_icon("media-playback-stop", stop_icon_color))

        self._btn_refresh.setStyleSheet(
            _BTN_REFRESH_ACTIVE if self._btn_refresh.isEnabled() else _BTN_IDLE
        )
        # Refresh icon: white when enabled, dark when disabled
        refresh_icon_color = "#FFFFFF" if self._btn_refresh.isEnabled() else "#424242"
        self._btn_refresh.setIcon(themed_icon("view-refresh", refresh_icon_color))

    # ── Actions ──────────────────────────────────────────────────────────

    def _refresh_icons_for_theme(self) -> None:
        """Refresh all icons after theme change."""
        from hsync_desktop.icons import clear_icon_cache

        clear_icon_cache()
        # Refresh button icons with theme-appropriate colors
        self._apply_button_styles()
        # Refresh role icon (neutral/known, re-coloured for the theme)
        self._retranslate_role()
        # Refresh path display (includes folder, sync direction, and remote icons)
        self._update_path_display()
        # Refresh file panel icons
        self._file_panel.refresh_icons_for_theme()

    def _retranslate_role(self) -> None:
        """Render the role icon/label from ``_is_master`` and the language.

        ``_is_master`` is None until the p2p election event: show a neutral icon
        and no text rather than a misleading "Secondary".
        """
        from hsync_desktop.icons import icon as get_icon

        if self._is_master is None:
            self._role_label.setText("")
            self._role_label.setToolTip(tr("role.unknown_tip"))
            self._role_icon.setPixmap(get_icon("role-unknown").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.unknown_tip"))
        elif self._is_master:
            self._role_label.setText(tr("role.master"))
            self._role_label.setToolTip(tr("role.master_tip"))
            self._role_icon.setPixmap(get_icon("role-master").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.master_tip"))
        else:
            self._role_label.setText(tr("role.client"))
            self._role_label.setToolTip(tr("role.client_tip"))
            self._role_icon.setPixmap(get_icon("role-client").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.client_tip"))
        self._apply_role_visibility()

    def _apply_role_visibility(self) -> None:
        """Show the role only in p2p; the text only when connected and known."""
        p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )
        self._role_icon.setVisible(p2p_enabled)
        self._role_label.setVisible(p2p_enabled and self._role_known and self._connected)

    def _render_share_size(self) -> None:
        """Render the shared-folder size as ``local / total`` (``-1`` = unknown)."""
        local = self._share_local_bytes
        total = self._share_total_bytes
        if local < 0:
            text = "—"
        else:
            total_text = format_bytes(total) if total >= 0 else "—"
            text = (
                tr("label.share_size_fmt")
                .replace("{local}", format_bytes(local))
                .replace("{total}", total_text)
            )
        self._share_size_label.setText(text)

    @Slot(int)
    def _on_share_size_changed(self, total_bytes: int) -> None:
        """Update the local size from the folder scan."""
        self._share_local_bytes = total_bytes
        self._render_share_size()

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

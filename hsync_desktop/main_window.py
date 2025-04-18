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

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QFontMetrics
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

from hsync_desktop.engine import HsyncEngine
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.settings_dialog import (
    SETTINGS_APP,
    SETTINGS_ORG,
    ApiKeyDialog,
    LanKeyDialog,
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


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


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
        root_layout: QVBoxLayout | None = self.centralWidget().layout()  # type: ignore[assignment]
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
        self._role_label.setText(tr("role.client"))
        self._role_label.setToolTip(tr("role.client_tip"))
        from hsync_desktop.icons import icon as get_icon

        self._role_icon.setPixmap(get_icon("role-client").pixmap(16, 16))
        self._role_icon.setToolTip(tr("role.client_tip"))
        self._lbl_peers.setText(tr("label.peers"))
        self._lbl_sent.setText(tr("label.sent"))
        self._lbl_recv.setText(tr("label.received"))
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
            self._act_file_trash.setText(tr("menu.file.trash"))
            self._act_file_properties.setText(tr("menu.file.properties"))
            self._act_settings.setText(tr("menu.settings"))
            self._menu_help.setTitle(tr("menu.help"))
            self._act_help_docs.setText(tr("menu.help.docs"))
            self._act_help_about.setText(tr("menu.help.about"))

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

        # ── Help menu ─────────────────────────────────────────────────
        self._menu_help = menubar.addMenu(tr("menu.help"))

        self._act_help_docs = QAction(tr("menu.help.docs"), self)
        self._act_help_docs.triggered.connect(self._open_documentation)
        self._menu_help.addAction(self._act_help_docs)

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

    def _update_menu_state(self) -> None:
        """Update menu/button/tray enabled state based on app state."""
        if not hasattr(self, "_act_start"):
            return  # Menu bar not yet created
        is_running = self._engine.is_running
        has_path = bool(self._local_path)

        can_start = not is_running and has_path
        self._act_start.setEnabled(can_start)
        self._btn_start.setEnabled(can_start)
        self._tray.set_start_enabled(can_start)
        self._act_stop.setEnabled(is_running)
        self._act_refresh.setEnabled(is_running and self._btn_refresh.isEnabled())
        self._apply_button_styles()

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

        QDesktopServices.openUrl(QUrl("https://docs.hsync.app"))

    def _show_about(self) -> None:
        """Show the splash screen as an About dialog."""
        from hsync_desktop.splash_screen import SplashScreen

        about = SplashScreen(self)
        about.show_as_about()

    # ── Signal wiring ────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Button signals
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_refresh.clicked.connect(self._on_refresh)

        # Engine signals
        e = self._engine
        e.log_received.connect(self._append_log)
        e.status_changed.connect(self._on_status)
        e.peers_changed.connect(self._on_peers)
        e.master_changed.connect(self._on_master)
        e.bucket_detected.connect(lambda b: self._bucket_label.setText(b))
        e.group_detected.connect(self._on_group_detected)
        e.file_transferred.connect(self._on_file_transferred)
        e.file_progress.connect(self._on_file_progress)
        e.file_renamed.connect(self._on_file_renamed)
        e.directory_created.connect(self._on_directory_created)
        e.sync_completed.connect(lambda: self._notifier.sync_complete())
        e.error_occurred.connect(lambda msg: self._notifier.error(tr("notif.error"), msg))
        e.path_not_found.connect(self._on_path_not_found)
        e.auth_error_occurred.connect(self._on_auth_error)
        e.master_conflict.connect(self._on_master_conflict)
        e.process_finished.connect(self._on_process_finished)
        # Preview signals
        e.preview_started.connect(self._on_preview_started)
        e.preview_ended.connect(self._on_preview_ended)
        e.file_status.connect(self._on_file_status)
        e.file_rename_status.connect(self._on_file_rename_status)

        # File panel selection signals for menu state
        self._file_panel._table.row_selected.connect(self._on_file_selection_changed)
        self._file_panel._table.row_deselected.connect(lambda: self._set_file_menu_enabled(False))

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
            # Refresh path display (server_ip now available)
            self._update_path_display()
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
        from hsync_desktop.icons import icon as get_icon

        if is_master:
            self._role_label.setText(tr("role.master"))
            self._role_label.setToolTip(tr("role.master_tip"))
            self._role_icon.setPixmap(get_icon("role-master").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.master_tip"))
            self._notifier.became_master()
        else:
            self._role_label.setText(tr("role.client"))
            self._role_label.setToolTip(tr("role.client_tip"))
            self._role_icon.setPixmap(get_icon("role-client").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.client_tip"))

    @Slot(str)
    def _on_group_detected(self, group: str) -> None:
        """Update group label in bottom bar and LAN label in top bar."""
        self._group_label.setText(group)
        # Also update the remote label if LAN mode is active
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if bool(s.value("lan/enabled", False, bool)):
            self._remote_label.setText(f"LAN ({group})" if group else "LAN")
            self._group_label.hide()

    @Slot(str, str)
    def _on_file_transferred(self, direction: str, filename: str) -> None:
        st = self._engine.stats
        self._sent_label.setText(f"{st.files_sent} ({_format_bytes(st.bytes_sent)})")
        self._recv_label.setText(f"{st.files_received} ({_format_bytes(st.bytes_received)})")
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
                tr("notif.master_takeover").replace("{cid}", peer_cid).replace("{ip}", peer_address)
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

    @Slot(str, str, int)
    def _on_file_rename_status(self, old_path: str, new_path: str, size: int) -> None:
        """Handle file rename status from preview."""
        base_path = self._local_path
        rel_old = old_path
        if base_path and old_path.startswith(base_path):
            rel_old = old_path[len(base_path) :].lstrip("/\\")
        self._file_panel.update_file_status(rel_old, "to_rename", size)
        self._preview_stats.to_rename += 1

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
                self._tray.set_running(False)
                self._set_path_editable(True)
                self._apply_button_styles()
                self._update_menu_state()
            # If stdin preview, just close dialog - process keeps running
            self._is_dry_run_preview = False

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._tray.set_running(False)
        self._set_path_editable(True)
        self._hide_info_banner()
        self._apply_button_styles()
        self._update_menu_state()
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

        # Notify only for truly unexpected crashes (not user stop, auth error,
        # force sync, app quit, etc.)
        if desc == "crashed" and not self._user_stopped:
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
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._tray.set_running(False)
        self._hide_info_banner()
        self._set_path_editable(True)
        self._apply_button_styles()
        self._update_menu_state()

    def _set_path_editable(self, editable: bool) -> None:
        """Path editing is now handled in Settings dialog — no-op."""
        pass

    def _set_path(self, path: str) -> None:
        """Set the local path and update the display."""
        self._local_path = path.strip()
        self._update_path_display()
        self._update_menu_state()

    @staticmethod
    def _simplify_path(path: str) -> str:
        """Replace the user's HOME prefix with ~ for a shorter display."""
        from pathlib import Path as _Path

        home = str(_Path.home())
        if path.startswith(home):
            return "~" + path[len(home) :]
        return path

    def _update_path_display(self) -> None:
        """Update the path label, sync direction icon, and remote endpoint."""
        from hsync_desktop.icons import icon as get_icon

        if self._local_path:
            # ── Folder icon + path label ──────────────────────────────
            self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(24, 24))
            self._path_icon_label.show()
            display_path = self._simplify_path(self._local_path)
            # Elide the path if it's too long (max ~300px)
            max_path_px = 300
            fm = QFontMetrics(self._path_label.font())
            elided = fm.elidedText(display_path, Qt.TextElideMode.ElideMiddle, max_path_px)
            link_color = (
                self._path_label.palette().color(self._path_label.palette().ColorRole.Link).name()
            )
            self._path_label.setText(
                f'<a href="open" style="color:{link_color}; text-decoration:none;">{elided}</a>'
            )
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
            lan_enabled = bool(s.value("lan/enabled", False, bool))
            if lan_enabled:
                self._remote_icon.setPixmap(get_icon("network-lan").pixmap(24, 24))
                group = str(s.value("lan/group", "", str))
                self._remote_label.setText(f"LAN ({group})" if group else "LAN")
                self._remote_icon.setToolTip(tr("label.remote_lan_tip"))
                self._remote_label.setToolTip(tr("label.remote_lan_tip"))
                # Group name shown next to LAN label — hide from bottom bar
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

    def _apply_button_styles(self) -> None:
        """Apply colored styles to Start/Stop/Refresh buttons based on enabled state."""
        self._btn_start.setStyleSheet(
            _BTN_START_ACTIVE if self._btn_start.isEnabled() else _BTN_IDLE
        )
        self._btn_stop.setStyleSheet(_BTN_STOP_ACTIVE if self._btn_stop.isEnabled() else _BTN_IDLE)
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
        lan_mode = s.value("lan/enabled", False, bool)
        force_master = s.value("lan/force_master", False, bool)
        sync_dir = s.value("sync/direction", "bidirectional", str)

        # upload-only never deletes local files
        if sync_dir == "upload-only":
            return True

        # force_master in LAN mode means this client is authoritative
        if lan_mode and force_master:
            return True

        # Determine risk
        if lan_mode and not force_master:
            reason = tr("notif.deletion_risk_lan")
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

    def _on_start(self) -> None:
        # Show disclaimer first
        if not self._show_disclaimer():
            return

        local_path = self._local_path
        if not local_path:
            self._append_log("⚠ Please select a local directory first.")
            return

        # Check for file deletion risk
        if not self._check_deletion_risk():
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
            self._update_menu_state()

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

    def _load_local_files(self, path: str) -> None:
        """Load files from the selected directory into the file panel."""
        if path:
            self._file_panel.load_local_files(path)

    def _open_settings(self, initial_tab: int | None = None) -> None:
        dlg = SettingsDialog(self)
        # Disable connection-critical settings while sync is running
        dlg.set_connection_active(self._engine.is_running)
        # initial_tab may receive a bool from Qt signal triggered(bool) — ignore that
        if isinstance(initial_tab, int) and not isinstance(initial_tab, bool):
            dlg.set_current_tab(initial_tab)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            theme = get_saved_theme()
            app = QApplication.instance()
            if app:
                apply_theme(app, theme)  # type: ignore[arg-type]
                self._refresh_icons_for_theme()
            self._notifier.enabled = are_notifications_enabled()
            self._apply_log_visibility()
            # Reload path in case it changed in settings
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            new_path = str(s.value("path/local", "", str))
            if new_path != self._local_path:
                self._set_path(new_path)
                if new_path:
                    self._load_local_files(new_path)
            # Refresh path display (settings may have changed LAN/server/direction)
            self._update_path_display()

    def _refresh_icons_for_theme(self) -> None:
        """Refresh all icons after theme change."""
        from hsync_desktop.icons import clear_icon_cache
        from hsync_desktop.icons import icon as get_icon

        clear_icon_cache()
        # Refresh button icons
        self._btn_start.setIcon(get_icon("media-playback-start"))
        self._btn_stop.setIcon(get_icon("media-playback-stop"))
        self._btn_refresh.setIcon(get_icon("view-refresh"))
        # Refresh role icon
        current_role = self._role_label.text()
        role_name = "role-master" if current_role == tr("role.master") else "role-client"
        self._role_icon.setPixmap(get_icon(role_name).pixmap(16, 16))
        # Refresh path display (includes folder, sync direction, and remote icons)
        self._update_path_display()
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
            msg = QMessageBox(
                QMessageBox.Icon.Question,
                tr("menu.sync.confirm_quit_title"),
                tr("menu.sync.confirm_quit"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self,
            )
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            yes_btn = msg.button(QMessageBox.StandardButton.Yes)
            no_btn = msg.button(QMessageBox.StandardButton.No)
            if yes_btn:
                yes_btn.setText(tr("action.yes"))
            if no_btn:
                no_btn.setText(tr("action.no"))
            if msg.exec() != QMessageBox.StandardButton.Yes:
                return
            self._engine.stop()
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("window/geometry", self.saveGeometry())
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

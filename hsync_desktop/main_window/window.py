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


from hsync_desktop.main_window.actions import ActionsMixin
from hsync_desktop.main_window.events import EventsMixin
from hsync_desktop.main_window.lifecycle import LifecycleMixin
from hsync_desktop.main_window.start import StartMixin
from hsync_desktop.main_window.trust import TrustMixin
from hsync_desktop.main_window.ui import UiBuildMixin


class MainWindow(
    UiBuildMixin, ActionsMixin, EventsMixin, TrustMixin, StartMixin, LifecycleMixin, QMainWindow
):
    """Primary application window."""

    def __init__(self, engine: HsyncEngine, tray: SystemTray | None = None) -> None:
        super().__init__()

        # Cache for findChild results to avoid repeated lookups.
        self._child_cache: dict[str, object] = {}

        self._engine = engine
        self._tray = tray
        self._notifier = NotificationManager(tray) if tray else None  # type: ignore[arg-type]
        if self._notifier:
            self._notifier.enabled = are_notifications_enabled()
        self._user_stopped = False  # track if stop was user-initiated
        # Per-(scope, identity) last-prompted fingerprint for the trust dialogs:
        # the client retries continuously, so a repeated refusal for the same
        # fingerprint must not reopen a dialog the user already dismissed. Reset
        # on start/stop so a new session prompts again.
        self._trust_prompted: dict[tuple[str, str], str] = {}

        # Preview statistics tracking
        self._preview_stats = PreviewStats()
        self._awaiting_preview_for_sync = False  # True when waiting for preview before sync
        self._pending_sync_path: str = ""  # Path saved for actual sync after preview
        self._is_dry_run_preview = False  # True when running in dry-run mode for initial preview
        # Send/Receive sync pending confirmation: (subdir, direction) or None.
        self._pending_selection_sync: tuple[str, str] | None = None
        # Scoped Send/Receive state: a user-invoked one-shot is in flight.
        self._selection_sync_active = False  # True while a scoped op runs
        self._selection_sync_phase = ""  # "preview" | "confirm" | "run"
        self._selection_result_count = 0  # successful transfers in the run phase
        self._ever_connected = False  # engine reached "connected" this process
        self._last_engine_error: str = ""  # Reason for the last failed engine start
        self._auth_prompt_active = False  # True while the auth re-prompt dialog is open
        # True only while ``HsyncEngine.start`` runs, so a launch failure is
        # reported once (by ``_start_engine``) and not also by the error slot.
        self._engine_starting = False

        # Open settings dialog, if any (tray/menu re-clicks raise it instead).
        self._settings_dialog: SettingsDialog | None = None

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
        e.bucket_detected.connect(self._on_bucket_detected)
        e.group_detected.connect(self._on_group_detected)
        e.file_transferred.connect(self._on_file_transferred)
        e.transfer_failed.connect(self._on_transfer_failed)
        e.sync_paused.connect(self._on_sync_paused)
        e.security_rejected.connect(self._on_security_rejected)
        e.file_progress.connect(self._on_file_progress)
        e.file_renamed.connect(self._on_file_renamed)
        e.directory_created.connect(self._on_directory_created)
        if self._notifier:
            notifier = self._notifier
            e.sync_completed.connect(notifier.sync_complete)
        # A completed cycle finishes a scoped Send/Receive with its counts.
        e.sync_completed.connect(self._on_sync_completed)
        # Engine errors are always mirrored into the log panel; a start failure
        # additionally raises a modal dialog (see `_start_engine`). The handler
        # also owns the outcome of a scoped Send/Receive failure.
        e.error_occurred.connect(self._on_engine_error)
        e.path_not_found.connect(self._on_path_not_found)
        e.auth_error_occurred.connect(self._on_auth_error)
        e.auth_required_occurred.connect(self._on_auth_error)
        e.master_conflict.connect(self._on_master_conflict)
        e.no_master_warning.connect(self._on_no_master_warning)
        e.no_peers_warning.connect(self._on_no_peers)
        e.duplicate_identity.connect(self._on_duplicate_identity)
        e.conflict_resolved.connect(self._on_conflict_resolved)
        e.pairing_needed.connect(self._on_pairing_needed)
        e.fingerprint_changed.connect(self._on_fingerprint_changed)
        e.process_finished.connect(self._on_process_finished)
        # Preview signals
        e.preview_started.connect(self._on_preview_started)
        e.preview_ended.connect(self._on_preview_ended)
        e.file_status.connect(self._on_file_status)
        e.file_rename_status.connect(self._on_file_rename_status)

        # File panel selection signals for menu state
        self._file_panel._table.row_selected.connect(self._on_file_selection_changed)
        self._file_panel._table.row_deselected.connect(lambda: self._set_file_menu_enabled(False))
        self._file_panel._table.send_selection_requested.connect(
            lambda filepath: self._sync_selection(filepath, "upload-only")
        )
        self._file_panel._table.receive_selection_requested.connect(
            lambda filepath: self._sync_selection(filepath, "download-only")
        )

        # Tray signals are connected in main.py after _tray is set

    # ── Slots ────────────────────────────────────────────────────────────

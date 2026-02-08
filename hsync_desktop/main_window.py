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

import re

from PySide6.QtCore import QSettings, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QWidget,
)

from hsync_desktop.engine import HsyncEngine
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.settings_dialog import (
    SETTINGS_APP,
    SETTINGS_ORG,
    SettingsDialog,
    build_hsync_args,
    get_saved_theme,
    are_notifications_enabled,
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


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self, engine: HsyncEngine, tray: SystemTray) -> None:
        super().__init__()

        self._engine = engine
        self._tray = tray
        self._notifier = NotificationManager(tray)
        self._notifier.enabled = are_notifications_enabled()
        self._user_stopped = False  # track if stop was user-initiated

        self._load_ui()
        self._connect_signals()

        # Restore window geometry
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        geo = s.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)

    # ── UI loading from .ui file ─────────────────────────────────────────

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        # Load UI into self
        load_ui_widget("main_window", self)

        # Get widget references from .ui file
        self._btn_start: QPushButton = self.findChild(QPushButton, "btnStart")  # type: ignore[assignment]
        self._btn_stop: QPushButton = self.findChild(QPushButton, "btnStop")  # type: ignore[assignment]
        self._btn_sync: QPushButton = self.findChild(QPushButton, "btnSync")  # type: ignore[assignment]
        self._btn_preview: QPushButton = self.findChild(QPushButton, "btnPreview")  # type: ignore[assignment]
        self._btn_settings: QPushButton = self.findChild(QPushButton, "btnSettings")  # type: ignore[assignment]
        self._btn_browse: QToolButton = self.findChild(QToolButton, "btnBrowse")  # type: ignore[assignment]
        self._path_edit: QLineEdit = self.findChild(QLineEdit, "pathEdit")  # type: ignore[assignment]
        self._lbl_path: QLabel = self.findChild(QLabel, "lblPath")  # type: ignore[assignment]
        self._main_splitter: QSplitter = self.findChild(QSplitter, "mainSplitter")  # type: ignore[assignment]
        self._log_view: QPlainTextEdit = self.findChild(QPlainTextEdit, "logView")  # type: ignore[assignment]

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
        self._file_panel.setMinimumHeight(150)
        # Replace placeholder in splitter
        idx = self._main_splitter.indexOf(placeholder)
        if idx >= 0:
            placeholder.setParent(None)
            self._main_splitter.insertWidget(idx, self._file_panel)
        # Set initial sizes (2/3 files, 1/3 log)
        self._main_splitter.setSizes([400, 200])

        # Restore saved path and load files
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved_path = str(s.value("path/local", "", str))
        self._path_edit.setText(saved_path)
        if saved_path:
            self._load_local_files(saved_path)

        # Apply translations
        self._apply_translations()

        # Register for language change notifications
        register_language_callback(self._apply_translations)

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._btn_start.setText(tr("btn.start"))
        self._btn_stop.setText(tr("btn.stop"))
        self._btn_sync.setText(tr("btn.sync"))
        self._btn_preview.setText(tr("btn.preview"))
        self._btn_settings.setText(tr("btn.settings"))
        self._btn_browse.setText(tr("btn.browse"))
        self._btn_browse.setToolTip(tr("btn.browse"))
        self._lbl_path.setText(tr("label.path"))
        self._path_edit.setPlaceholderText(tr("label.path"))
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
        self._btn_sync.clicked.connect(self._on_sync)
        self._btn_preview.clicked.connect(self._on_preview)
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
        e.sync_completed.connect(lambda: self._notifier.sync_complete())
        e.error_occurred.connect(lambda msg: self._notifier.error(tr("notif.error"), msg))
        e.process_finished.connect(self._on_process_finished)
        # Preview signals
        e.preview_started.connect(self._on_preview_started)
        e.preview_ended.connect(self._on_preview_ended)
        e.file_status.connect(self._on_file_status)

        # Tray signals
        t = self._tray
        t.toggle_window.connect(self._toggle_visibility)
        t.start_requested.connect(self._on_start)
        t.stop_requested.connect(self._on_stop)
        t.sync_requested.connect(self._on_sync)
        t.settings_requested.connect(self._open_settings)
        t.quit_requested.connect(self._quit)

    # ── Slots ────────────────────────────────────────────────────────────

    # Regex patterns for file transfer log lines
    _RE_DOWNLOAD = re.compile(r'↓\s*\[DOWNLOAD\s*\]\s*"?([^"]+)"?\s*(?:\(([^)]+)\))?')
    _RE_UPLOAD = re.compile(r'↑\s*\[UPLOAD\s*\]\s*"?([^"]+)"?\s*(?:\(([^)]+)\))?')

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)
        # Auto-scroll to bottom
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Parse for file transfers and update file panel
        self._parse_transfer_line(line)

    def _parse_transfer_line(self, line: str) -> None:
        """Parse log line for file transfers and update file panel."""
        # Download pattern: ↓ [DOWNLOAD ] "filepath" (size)
        m = self._RE_DOWNLOAD.search(line)
        if m:
            filepath = m.group(1).strip()
            size_str = m.group(2)
            size = self._parse_size(size_str) if size_str else 0
            self._file_panel.complete_transfer(filepath, size, direction="↓")
            return

        # Upload pattern: ↑ [UPLOAD   ] "filepath" (size)
        m = self._RE_UPLOAD.search(line)
        if m:
            filepath = m.group(1).strip()
            size_str = m.group(2)
            size = self._parse_size(size_str) if size_str else 0
            self._file_panel.complete_transfer(filepath, size, direction="↑")
            return

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

        if status == "disconnected":
            self._notifier.connection_lost()
        elif status == "connected":
            # Auto-run preview when connected to show file status
            if self._engine.is_running:
                self._engine.preview()

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
        # Update file panel with actual transfer
        if direction == "↓":
            self._notifier.download_complete(filename)
            self._file_panel.update_file_status(filename, "synced")
        elif direction == "↑":
            self._file_panel.update_file_status(filename, "synced")
        elif direction == "✕":
            # File was deleted - show briefly then remove
            self._file_panel.mark_deleted(filename)

    @Slot()
    def _on_preview_started(self) -> None:
        """Handle preview scan started."""
        self._append_log("--- Updating file status... ---")

    @Slot()
    def _on_preview_ended(self) -> None:
        """Handle preview scan ended."""
        self._append_log("--- File status updated ---")

    @Slot(str, str, int)
    def _on_file_status(self, status: str, filepath: str, size: int) -> None:
        """Handle file status from preview."""
        self._file_panel.update_file_status(filepath, status, size)

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._btn_preview.setEnabled(False)
        self._tray.set_running(False)
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

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

        checkbox = QCheckBox(tr("disclaimer.dont_show"))
        msg.setCheckBox(checkbox)

        result = msg.exec()
        if result == QMessageBox.StandardButton.Ok:
            if checkbox.isChecked():
                s.setValue("ui/disclaimer_accepted", True)
            return True
        return False

    def _on_start(self) -> None:
        # Show disclaimer first
        if not self._show_disclaimer():
            return

        local_path = self._path_edit.text().strip()
        if not local_path:
            self._append_log("⚠ Please select a local directory first.")
            return
        args = build_hsync_args(local_path)
        if not args:
            self._append_log("⚠ Please configure a bucket name in Settings.")
            return
        # Persist path
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("path/local", local_path)
        self._log_view.clear()
        self._file_panel.clear()  # Clear file panel on new sync
        self._user_stopped = False
        self._notifier.user_stopped = False
        if self._engine.start(args):
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_sync.setEnabled(True)
            self._btn_preview.setEnabled(True)
            self._tray.set_running(True)

    def _on_stop(self) -> None:
        self._user_stopped = True
        self._notifier.user_stopped = True
        self._engine.stop()

    def _on_sync(self) -> None:
        self._engine.force_sync()

    def _on_preview(self) -> None:
        """Trigger a preview (dry-run) using the running process.

        Sends SIGUSR1 to the running hsync-client process to get a preview
        of pending sync actions without starting a new process.
        """
        if not self._engine.is_running:
            self._append_log("⚠ Please start synchronization first.")
            return
        self._append_log(f"--- {tr('preview.title')} ---")
        self._engine.preview()

    def _browse_path(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("label.path"))
        if d:
            self._path_edit.setText(d)
            self._load_local_files(d)

    def _load_local_files(self, path: str) -> None:
        """Load files from the selected directory into the file panel."""
        if path:
            self._file_panel.load_local_files(path)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            theme = get_saved_theme()
            app = QApplication.instance()
            if app:
                apply_theme(app, theme)  # type: ignore[arg-type]
            self._notifier.enabled = are_notifications_enabled()

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

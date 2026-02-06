# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Main window for HSYNC Desktop.

Contains:
- Status panel: connection icon, status label, master/client indicator,
  bucket name, peer count, group name, transfer stats
- Action bar: Start/Stop, Sync, path selector, Settings
- Log viewer: real-time scrolling log output
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.engine import HsyncEngine
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
        self.setWindowTitle("HSYNC Desktop")
        self.setMinimumSize(760, 520)

        self._engine = engine
        self._tray = tray
        self._notifier = NotificationManager(tray)
        self._notifier.enabled = are_notifications_enabled()

        self._build_ui()
        self._connect_signals()

        # Restore window geometry
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        geo = s.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Status panel ─────────────────────────────────────────────────
        status_box = QGroupBox("Status")
        sg = QHBoxLayout(status_box)

        # Connection status
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {COLOR_DISCONNECTED.name()}; font-size: 18px;")
        sg.addWidget(self._status_dot)
        self._status_label = QLabel("Disconnected")
        self._status_label.setStyleSheet("font-weight: bold;")
        sg.addWidget(self._status_label)
        sg.addSpacing(16)

        # Master/client indicator
        self._role_label = QLabel("⬡ Client")
        self._role_label.setToolTip("Role in the network")
        sg.addWidget(self._role_label)
        sg.addSpacing(16)

        # Bucket
        sg.addWidget(QLabel("Bucket:"))
        self._bucket_label = QLabel("–")
        self._bucket_label.setStyleSheet("font-weight: bold;")
        sg.addWidget(self._bucket_label)
        sg.addSpacing(16)

        # Group
        sg.addWidget(QLabel("Group:"))
        self._group_label = QLabel("–")
        sg.addWidget(self._group_label)
        sg.addSpacing(16)

        # Peers
        sg.addWidget(QLabel("Peers:"))
        self._peers_label = QLabel("0")
        self._peers_label.setStyleSheet("font-weight: bold;")
        sg.addWidget(self._peers_label)

        sg.addStretch()
        root.addWidget(status_box)

        # ── Action bar ───────────────────────────────────────────────────
        action_row = QHBoxLayout()

        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("primaryButton")
        self._btn_start.clicked.connect(self._on_start)
        action_row.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        action_row.addWidget(self._btn_stop)

        self._btn_sync = QPushButton("⟳  Sync")
        self._btn_sync.setEnabled(False)
        self._btn_sync.clicked.connect(self._on_sync)
        action_row.addWidget(self._btn_sync)

        action_row.addSpacing(20)

        # Path selector
        action_row.addWidget(QLabel("Path:"))
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select local directory…")
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._path_edit.setText(s.value("path/local", "", str))
        action_row.addWidget(self._path_edit, stretch=1)
        btn_browse = QToolButton()
        btn_browse.setText("…")
        btn_browse.setToolTip("Browse")
        btn_browse.clicked.connect(self._browse_path)
        action_row.addWidget(btn_browse)

        action_row.addSpacing(20)
        btn_settings = QPushButton("⚙  Settings")
        btn_settings.clicked.connect(self._open_settings)
        action_row.addWidget(btn_settings)

        root.addLayout(action_row)

        # ── Transfer stats ───────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel("↑ Sent:"))
        self._sent_label = QLabel("0 files (0 B)")
        stats_row.addWidget(self._sent_label)
        stats_row.addSpacing(24)
        stats_row.addWidget(QLabel("↓ Received:"))
        self._recv_label = QLabel("0 files (0 B)")
        stats_row.addWidget(self._recv_label)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # ── Log viewer ───────────────────────────────────────────────────
        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("logViewer")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._log_view, stretch=1)

    # ── Signal wiring ────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        e = self._engine
        e.log_received.connect(self._append_log)
        e.status_changed.connect(self._on_status)
        e.peers_changed.connect(self._on_peers)
        e.master_changed.connect(self._on_master)
        e.bucket_detected.connect(lambda b: self._bucket_label.setText(b))
        e.group_detected.connect(lambda g: self._group_label.setText(g))
        e.file_transferred.connect(self._on_file_transferred)
        e.sync_completed.connect(lambda: self._notifier.sync_complete())
        e.error_occurred.connect(lambda msg: self._notifier.error("Error", msg))
        e.process_finished.connect(self._on_process_finished)

        # Tray signals
        t = self._tray
        t.toggle_window.connect(self._toggle_visibility)
        t.start_requested.connect(self._on_start)
        t.stop_requested.connect(self._on_stop)
        t.sync_requested.connect(self._on_sync)
        t.settings_requested.connect(self._open_settings)
        t.quit_requested.connect(self._quit)

    # ── Slots ────────────────────────────────────────────────────────────

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)

    @Slot(str)
    def _on_status(self, status: str) -> None:
        labels = {
            "connected": ("Connected", COLOR_CONNECTED),
            "disconnected": ("Disconnected", COLOR_DISCONNECTED),
            "connecting": ("Connecting…", COLOR_WAITING),
            "waiting": ("Waiting…", COLOR_WAITING),
            "error": ("Error", COLOR_DISCONNECTED),
        }
        text, color = labels.get(status, ("Unknown", COLOR_DISCONNECTED))
        self._status_dot.setStyleSheet(f"color: {color.name()}; font-size: 18px;")
        self._status_label.setText(text)
        self._tray.update_status(status)

        if status == "disconnected":
            self._notifier.connection_lost()

    @Slot(int)
    def _on_peers(self, count: int) -> None:
        self._peers_label.setText(str(count))
        self._notifier.peer_joined(count)

    @Slot(bool)
    def _on_master(self, is_master: bool) -> None:
        if is_master:
            self._role_label.setText("★ Master")
            self._role_label.setToolTip("This client is the master")
            self._notifier.became_master()
        else:
            self._role_label.setText("⬡ Client")
            self._role_label.setToolTip("This client is a slave")

    @Slot(str, str)
    def _on_file_transferred(self, direction: str, filename: str) -> None:
        st = self._engine.stats
        self._sent_label.setText(
            f"{st.files_sent} files ({_format_bytes(st.bytes_sent)})"
        )
        self._recv_label.setText(
            f"{st.files_received} files ({_format_bytes(st.bytes_received)})"
        )

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._tray.set_running(False)
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

    # ── Actions ──────────────────────────────────────────────────────────

    def _on_start(self) -> None:
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
        if self._engine.start(args):
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_sync.setEnabled(True)
            self._tray.set_running(True)

    def _on_stop(self) -> None:
        self._engine.stop()

    def _on_sync(self) -> None:
        self._engine.force_sync()

    def _browse_path(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select local directory")
        if d:
            self._path_edit.setText(d)

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
        """Minimize to tray instead of closing."""
        if self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "HSYNC Desktop",
                "Application minimized to system tray",
                self._tray.MessageIcon.Information,
                2000,
            )
        else:
            # No tray available – actually close
            self._quit()
            event.accept()

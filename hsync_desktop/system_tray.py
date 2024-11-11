# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
System tray integration for HSYNC Desktop.

Provides a tray icon with context menu for quick access to
Show/Hide, Start/Stop, Sync, Settings and Quit.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from hsync_desktop.themes import COLOR_CONNECTED, COLOR_DISCONNECTED, COLOR_WAITING


def _make_icon(color: QColor, letter: str = "H") -> QIcon:
    """Create a simple colored icon with a letter for the tray."""
    size = 64
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 12, 12)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Arial", 32, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), 0x0084, letter)  # AlignCenter
    painter.end()
    return QIcon(pix)


class SystemTray(QSystemTrayIcon):
    """System tray icon with context menu."""

    # Signals for menu actions
    toggle_window = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    sync_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icons = {
            "connected": _make_icon(COLOR_CONNECTED),
            "disconnected": _make_icon(COLOR_DISCONNECTED),
            "waiting": _make_icon(COLOR_WAITING),
        }
        self.setIcon(self._icons["disconnected"])
        self.setToolTip("HSYNC Desktop - Disconnected")

        # Context menu
        menu = QMenu()
        self._act_show = QAction("Show", menu)
        self._act_show.triggered.connect(self.toggle_window.emit)
        menu.addAction(self._act_show)
        menu.addSeparator()

        self._act_start = QAction("Start", menu)
        self._act_start.triggered.connect(self.start_requested.emit)
        menu.addAction(self._act_start)

        self._act_stop = QAction("Stop", menu)
        self._act_stop.triggered.connect(self.stop_requested.emit)
        self._act_stop.setEnabled(False)
        menu.addAction(self._act_stop)

        self._act_sync = QAction("Sync Now", menu)
        self._act_sync.triggered.connect(self.sync_requested.emit)
        self._act_sync.setEnabled(False)
        menu.addAction(self._act_sync)

        menu.addSeparator()
        self._act_settings = QAction("Settings…", menu)
        self._act_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(self._act_settings)

        menu.addSeparator()
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    # ── Public helpers ───────────────────────────────────────────────────

    def update_status(self, status: str) -> None:
        """Update tray icon and tooltip based on connection status."""
        labels = {
            "connected": "Connected",
            "disconnected": "Disconnected",
            "connecting": "Connecting…",
            "waiting": "Waiting…",
            "error": "Error",
        }
        icon_key = "connected" if status == "connected" else (
            "waiting" if status in ("connecting", "waiting") else "disconnected"
        )
        self.setIcon(self._icons[icon_key])
        self.setToolTip(f"HSYNC Desktop - {labels.get(status, status)}")

    def set_running(self, running: bool) -> None:
        """Update menu items based on running state."""
        self._act_start.setEnabled(not running)
        self._act_stop.setEnabled(running)
        self._act_sync.setEnabled(running)
        self._act_show.setText("Show" if not self.parent() or not self.parent().isVisible() else "Hide")

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window.emit()


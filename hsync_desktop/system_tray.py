# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
System tray integration for HSYNC Desktop.

Provides a tray icon with context menu for quick access to
Show/Hide, Start/Stop, Check for changes, Settings and Quit.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.themes import COLOR_CONNECTED, COLOR_DISCONNECTED, COLOR_WAITING

# Connection status → i18n key, shared by the tooltip builder.
_STATUS_KEYS = {
    "connected": "status.connected",
    "disconnected": "status.disconnected",
    "connecting": "status.connecting",
    "waiting": "status.waiting",
    "syncing": "status.syncing",
    "stopping": "status.stopping",
    "error": "status.error",
}


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
    preview_changes_requested = Signal()
    stop_requested = Signal()
    check_changes_requested = Signal()
    settings_requested = Signal()
    wizard_requested = Signal()
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

        # Track whether the main window is currently visible
        self._window_visible = False

        # Context menu
        menu = QMenu()
        self._act_show = QAction(tr("tray.show"), menu)
        self._act_show.triggered.connect(self.toggle_window.emit)
        menu.addAction(self._act_show)
        menu.addSeparator()

        self._act_start = QAction(tr("tray.start"), menu)
        self._act_start.triggered.connect(self.start_requested.emit)
        menu.addAction(self._act_start)

        self._act_preview_changes = QAction(tr("tray.preview_changes"), menu)
        self._act_preview_changes.triggered.connect(self.preview_changes_requested.emit)
        menu.addAction(self._act_preview_changes)

        self._act_stop = QAction(tr("tray.stop"), menu)
        self._act_stop.triggered.connect(self.stop_requested.emit)
        self._act_stop.setEnabled(False)
        menu.addAction(self._act_stop)

        self._act_check_changes = QAction(tr("tray.check_changes"), menu)
        self._act_check_changes.triggered.connect(self.check_changes_requested.emit)
        self._act_check_changes.setEnabled(False)
        menu.addAction(self._act_check_changes)

        menu.addSeparator()
        self._act_settings = QAction(tr("tray.settings"), menu)
        self._act_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(self._act_settings)

        self._act_setup_wizard = QAction(tr("tray.setup_wizard"), menu)
        self._act_setup_wizard.triggered.connect(self.wizard_requested.emit)
        menu.addAction(self._act_setup_wizard)

        menu.addSeparator()
        self._act_quit = QAction(tr("tray.quit"), menu)
        self._act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(self._act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        # Track current status for tooltip updates
        self._current_status = "disconnected"
        # Simulation Mode note in the tooltip (set by the main window).
        self._simulation = False

        # Register for language change notifications
        register_language_callback(self._apply_translations)

    # ── Public helpers ───────────────────────────────────────────────────

    def update_status(self, status: str) -> None:
        """Update tray icon and tooltip based on connection status."""
        self._current_status = status
        icon_key = (
            "connected"
            if status == "connected"
            else (
                "waiting"
                if status in ("connecting", "waiting", "syncing", "stopping")
                else "disconnected"
            )
        )
        self.setIcon(self._icons[icon_key])
        self._update_tooltip()

    def set_simulation(self, simulation: bool) -> None:
        """Append the Simulation Mode note to the tooltip while it is active."""
        self._simulation = simulation
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        """Tray tooltip: app, connection status and, when active, the mode."""
        key = _STATUS_KEYS.get(self._current_status, self._current_status)
        text = f"HSYNC Desktop - {tr(key)}"
        if self._simulation:
            text += f" ({tr('simulation.badge')})"
        self.setToolTip(text)

    def set_running(self, running: bool) -> None:
        """Update the run actions; the check entry is set by the window.

        ``set_check_changes_enabled`` carries the window's own rule (a comparison
        in flight disables it), so this method must not re-enable it on its own.
        """
        self._act_start.setEnabled(not running)
        self._act_preview_changes.setEnabled(not running)
        self._act_stop.setEnabled(running)

    def set_check_changes_enabled(self, enabled: bool) -> None:
        """Mirror the window's "can compare now" rule for the tray entry."""
        self._act_check_changes.setEnabled(enabled)

    def set_stopping(self) -> None:
        """Disable the run actions while a stop is in flight.

        The run is still alive until the engine reports its exit, so Start must
        stay disabled too. ``set_running(False)`` restores the menu afterwards.
        """
        self._act_start.setEnabled(False)
        self._act_preview_changes.setEnabled(False)
        self._act_stop.setEnabled(False)
        self._act_check_changes.setEnabled(False)

    def set_window_visible(self, visible: bool) -> None:
        """Update the Show/Minimize action text based on window visibility."""
        self._window_visible = visible
        self._act_show.setText(tr("tray.minimize") if visible else tr("tray.show"))

    def set_start_enabled(self, enabled: bool) -> None:
        """Enable or disable the start-or-preview entries in the tray menu.

        Preview changes shares Start's rule (both need a stopped engine and a
        configured folder), so one call keeps them from drifting apart.
        """
        self._act_start.setEnabled(enabled)
        self._act_preview_changes.setEnabled(enabled)

    def _apply_translations(self) -> None:
        """Apply i18n translations to menu items."""
        self._act_show.setText(tr("tray.minimize") if self._window_visible else tr("tray.show"))
        self._act_start.setText(tr("tray.start"))
        self._act_preview_changes.setText(tr("tray.preview_changes"))
        self._act_stop.setText(tr("tray.stop"))
        self._act_check_changes.setText(tr("tray.check_changes"))
        self._act_settings.setText(tr("tray.settings"))
        self._act_setup_wizard.setText(tr("tray.setup_wizard"))
        self._act_quit.setText(tr("tray.quit"))
        self._update_tooltip()

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window.emit()

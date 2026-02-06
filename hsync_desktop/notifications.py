# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
System notification manager for HSYNC Desktop.

Uses QSystemTrayIcon.showMessage for cross-platform desktop
notifications (balloon tips on Windows, notification centre on
macOS, libnotify on Linux).
"""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon


class NotificationManager:
    """Emits desktop push notifications via the system tray icon."""

    def __init__(self, tray_icon: QSystemTrayIcon) -> None:
        self._tray = tray_icon
        self._enabled = True

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def notify(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 5000,
    ) -> None:
        """Show a desktop notification if enabled."""
        if self._enabled and self._tray.isVisible():
            self._tray.showMessage(title, message, icon, duration_ms)

    # ── Convenience helpers ──────────────────────────────────────────────

    def info(self, title: str, message: str) -> None:
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Information)

    def warning(self, title: str, message: str) -> None:
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Warning)

    def error(self, title: str, message: str) -> None:
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Critical, 8000)

    def sync_complete(self, files: int = 0) -> None:
        msg = f"{files} file(s) synchronized" if files else "All files in sync"
        self.info("Sync Complete", msg)

    def peer_joined(self, count: int) -> None:
        self.info("Peer Update", f"{count} peer(s) connected")

    def connection_lost(self) -> None:
        self.warning("Disconnected", "Connection to peers lost")

    def became_master(self) -> None:
        self.info("Master Elected", "This client is now the master")


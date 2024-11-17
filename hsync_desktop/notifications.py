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

Policy:
- Notify only on download complete (not upload).
- Notify on errors.
- Do NOT notify when the user explicitly stops the process.
"""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from hsync_desktop.i18n import tr


class NotificationManager:
    """Emits desktop push notifications via the system tray icon."""

    def __init__(self, tray_icon: QSystemTrayIcon) -> None:
        self._tray = tray_icon
        self._enabled = True
        self.user_stopped = False  # set True when user clicks Stop

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
        """Always notify errors (unless user just stopped the process)."""
        if self.user_stopped:
            return
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Critical, 8000)

    def download_complete(self, filename: str) -> None:
        """Notify when a file has been downloaded (not uploaded)."""
        msg = tr("notif.download_complete").replace("{filename}", filename)
        self.info(tr("notif.sync_complete"), msg)

    def sync_complete(self, files: int = 0) -> None:
        msg = tr("notif.sync_complete_msg")
        self.info(tr("notif.sync_complete"), msg)

    def peer_joined(self, count: int) -> None:
        msg = tr("notif.peer_update_msg").replace("{count}", str(count))
        self.info(tr("notif.peer_update"), msg)

    def connection_lost(self) -> None:
        if self.user_stopped:
            return
        self.warning(tr("notif.connection_lost"), tr("notif.connection_lost_msg"))

    def became_master(self) -> None:
        self.info(tr("notif.master_elected"), tr("notif.master_elected_msg"))


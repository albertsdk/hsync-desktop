# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
System notification manager for HSYNC Desktop.

Uses QSystemTrayIcon.showMessage for cross-platform desktop
notifications (balloon tips on Windows, notification centre on
macOS, libnotify on Linux).

Policy:
- Notify only on download complete (not upload).
- Notify on errors.
- Do NOT notify when the user explicitly stops the process.
- While the main window is in the foreground every system notification is
  suppressed: errors and warnings are surfaced by the in-app toast, and routine
  events are already visible in the app UI.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QSystemTrayIcon

from hsync_desktop.i18n import tr


class NotificationManager:
    """Emits desktop push notifications via the system tray icon."""

    def __init__(
        self,
        tray_icon: QSystemTrayIcon,
        is_foreground: Callable[[], bool] | None = None,
    ) -> None:
        self._tray = tray_icon
        # ``True`` while the main window is focused: routine events are then
        # already on screen, so their system notification is skipped.
        self._is_foreground = is_foreground or (lambda: False)
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
        """Show a desktop notification if enabled.

        Suppressed while the main window is in the foreground: the event is
        surfaced in-app instead (the window shows a toast for errors/warnings,
        and routine events are part of the UI).
        """
        if not self._enabled or not self._tray.isVisible():
            return
        if self._is_foreground():
            return
        self._tray.showMessage(title, message, icon, duration_ms)

    # ── Convenience helpers ──────────────────────────────────────────────

    def info(self, title: str, message: str) -> None:
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Information)

    def warning(self, title: str, message: str) -> None:
        self.notify(title, message, QSystemTrayIcon.MessageIcon.Warning)

    def error(self, title: str, message: str) -> None:
        """Notify an error (unless the user just stopped the process)."""
        if self.user_stopped:
            return
        self.notify(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Critical,
            8000,
        )

    def download_complete(self, filename: str) -> None:
        """Notify when a file has been downloaded (not uploaded)."""
        msg = tr("notif.download_complete").replace("{filename}", filename)
        self.info(tr("notif.sync_complete"), msg)

    def sync_complete(self) -> None:
        msg = tr("notif.sync_complete_msg")
        self.info(tr("notif.sync_complete"), msg)

    def peer_joined(self, connected: int, total: int) -> None:
        msg = (
            tr("notif.peer_update_msg")
            .replace("{connected}", str(connected))
            .replace("{total}", str(total))
        )
        self.info(tr("notif.peer_update"), msg)

    def became_master(self) -> None:
        self.info(tr("notif.master_elected"), tr("notif.master_elected_msg"))

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Foreground detection and notification-click behaviour.

A system notification must not duplicate an in-app toast while the app already
owns the focused window — and a modal dialog holds that focus, which the old
``window.isActiveWindow()`` test did not account for. Conversely, clicking a
notification that *was* shown has to bring the app forward.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


def _with_active_window(monkeypatch, active) -> None:
    """Make the foreground check see *active* as the application's active window.

    The offscreen platform has no real focus, so the module's one accessor is
    stubbed. Patching ``QApplication.instance`` would break pytest-qt's own
    teardown, which calls ``processEvents()`` on the real application.
    """
    import hsync_desktop.foreground as foreground

    monkeypatch.setattr(foreground, "_active_window", lambda: active)


class TestAppInForeground:
    def test_a_hidden_window_is_not_in_foreground(self, qtbot, window):
        from hsync_desktop.foreground import app_in_foreground

        window.hide()

        assert app_in_foreground(window) is False

    def test_a_visible_active_window_is_in_foreground(self, qtbot, window, monkeypatch):
        from hsync_desktop.foreground import app_in_foreground

        window.show()
        qtbot.waitExposed(window)
        _with_active_window(monkeypatch, window)

        assert app_in_foreground(window) is True

    def test_an_open_dialog_keeps_the_app_in_foreground(self, qtbot, window, monkeypatch):
        """The dialog owns the focus; the app is still in front."""
        from hsync_desktop.foreground import app_in_foreground

        window.show()
        qtbot.waitExposed(window)
        dialog = QDialog(window)
        dialog.show()
        qtbot.waitExposed(dialog)
        # The active window is the dialog, a child of the main window.
        _with_active_window(monkeypatch, dialog)

        assert app_in_foreground(window) is True
        dialog.close()

    def test_a_minimised_window_is_not_in_foreground(self, qtbot, window):
        from hsync_desktop.foreground import app_in_foreground

        window.show()
        qtbot.waitExposed(window)
        window.setWindowState(Qt.WindowState.WindowMinimized)

        assert app_in_foreground(window) is False
        window.setWindowState(Qt.WindowState.WindowNoState)


class TestNotificationDoesNotDuplicateTheToast:
    def test_a_foreground_app_raises_no_system_notification(self, qtbot, window, monkeypatch):
        from unittest.mock import MagicMock

        from PySide6.QtWidgets import QSystemTrayIcon

        from hsync_desktop.foreground import app_in_foreground
        from hsync_desktop.notifications import NotificationManager

        tray = MagicMock(spec=QSystemTrayIcon)
        tray.isVisible.return_value = True
        window.show()
        qtbot.waitExposed(window)
        _with_active_window(monkeypatch, window)
        window._notifier = NotificationManager(
            tray, is_foreground=lambda: app_in_foreground(window)
        )

        window._notify_warning("Title", "Message")

        tray.showMessage.assert_not_called()
        # The in-app toast still carries the message.
        assert "Message" in window._info_banner_label.text()


class TestNotificationClickBringsTheAppForward:
    def test_clicking_a_notification_restores_and_focuses(self, qtbot, window):
        window.hide()

        window._on_notification_clicked()
        qtbot.waitExposed(window)

        assert window.isVisible()
        assert not window.isMinimized()

    def test_clicking_a_notification_restores_a_minimised_window(self, qtbot, window):
        window.show()
        qtbot.waitExposed(window)
        window.setWindowState(Qt.WindowState.WindowMinimized)

        window._on_notification_clicked()

        assert not window.isMinimized()
        assert window.isVisible()

    def test_the_tray_forwards_a_message_click(self, qtbot):
        """The tray signal exists so main.py can connect it to the window."""
        from hsync_desktop.system_tray import SystemTray

        tray = SystemTray()
        received: list[int] = []
        tray.notification_clicked.connect(lambda: received.append(1))

        tray.messageClicked.emit()

        assert received == [1]
        tray.hide()

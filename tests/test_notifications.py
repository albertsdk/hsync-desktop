# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.notifications module."""

from unittest.mock import MagicMock

from PySide6.QtWidgets import QSystemTrayIcon


class TestNotificationManager:
    """Test NotificationManager class."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        assert manager.enabled is True
        assert manager.user_stopped is False

    def test_enabled_property(self):
        """Test enabled property getter and setter."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        # Test getter
        assert manager.enabled is True

        # Test setter
        manager.enabled = False
        assert manager.enabled is False

    def test_notify_disabled(self):
        """Test that notify does nothing when disabled."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)
        manager.enabled = False

        manager.notify("Test", "Message")

        # showMessage should not be called when disabled
        tray_icon.showMessage.assert_not_called()

    def test_notify_not_visible(self):
        """Test that notify does nothing when tray is not visible."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = False

        manager = NotificationManager(tray_icon)

        manager.notify("Test", "Message")

        # showMessage should not be called when not visible
        tray_icon.showMessage.assert_not_called()

    def test_notify_enabled_and_visible(self):
        """Test that notify works when enabled and visible."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.notify("Test Title", "Test Message")

        tray_icon.showMessage.assert_called_once()
        call_args = tray_icon.showMessage.call_args
        assert call_args[0][0] == "Test Title"
        assert call_args[0][1] == "Test Message"

    def test_info_helper(self):
        """Test info() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.info("Title", "Message")

        tray_icon.showMessage.assert_called_once()

    def test_warning_helper(self):
        """Test warning() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.warning("Title", "Message")

        tray_icon.showMessage.assert_called_once()

    def test_error_helper_skips_when_user_stopped(self):
        """Test error() skips notification when user stopped."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)
        manager.user_stopped = True

        manager.error("Title", "Message")

        tray_icon.showMessage.assert_not_called()

    def test_error_helper_shows_when_not_user_stopped(self):
        """Test error() shows notification when not user stopped."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)
        manager.user_stopped = False

        manager.error("Title", "Message")

        tray_icon.showMessage.assert_called_once()

    def test_download_complete_helper(self):
        """Test download_complete() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.download_complete("test.txt")

        # Should call info which calls notify
        tray_icon.showMessage.assert_called_once()

    def test_sync_complete_helper(self):
        """Test sync_complete() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.sync_complete()

        tray_icon.showMessage.assert_called_once()

    def test_peer_joined_helper(self):
        """Test peer_joined() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.peer_joined(3, 5)

        tray_icon.showMessage.assert_called_once()

    def test_became_master_helper(self):
        """Test became_master() helper method."""
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True

        manager = NotificationManager(tray_icon)

        manager.became_master()

        tray_icon.showMessage.assert_called_once()


class TestForegroundSuppression:
    """Every system notification is suppressed while the window is in the
    foreground: errors and warnings are surfaced by the in-app toast instead."""

    @staticmethod
    def _manager(foreground: bool):
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True
        return NotificationManager(tray_icon, is_foreground=lambda: foreground), tray_icon

    def test_info_suppressed_when_foreground(self):
        manager, tray_icon = self._manager(True)

        manager.info("Title", "Message")

        tray_icon.showMessage.assert_not_called()

    def test_info_shown_when_background(self):
        manager, tray_icon = self._manager(False)

        manager.info("Title", "Message")

        tray_icon.showMessage.assert_called_once()

    def test_warning_suppressed_when_foreground(self):
        manager, tray_icon = self._manager(True)

        manager.warning("Title", "Message")

        tray_icon.showMessage.assert_not_called()

    def test_error_suppressed_when_foreground(self):
        manager, tray_icon = self._manager(True)

        manager.error("Title", "Message")

        tray_icon.showMessage.assert_not_called()

    def test_error_shown_when_background(self):
        manager, tray_icon = self._manager(False)

        manager.error("Title", "Message")

        tray_icon.showMessage.assert_called_once()


class TestNotificationCategories:
    """Per-event categories gate notifications under the master switch."""

    @staticmethod
    def _manager():
        from hsync_desktop.notifications import NotificationManager

        tray_icon = MagicMock(spec=QSystemTrayIcon)
        tray_icon.isVisible.return_value = True
        return NotificationManager(tray_icon), tray_icon

    def test_all_categories_enabled_by_default(self):
        from hsync_desktop.config import NOTIFICATION_CATEGORIES

        manager, _tray = self._manager()

        assert manager.categories == frozenset(NOTIFICATION_CATEGORIES)

    def test_disabled_category_suppresses_only_that_type(self):
        manager, tray_icon = self._manager()
        manager.categories = {"errors", "sync"}

        manager.peer_joined(1, 2)
        tray_icon.showMessage.assert_not_called()

        manager.info("Title", "Message")
        tray_icon.showMessage.assert_called_once()

    def test_error_uses_the_errors_category(self):
        manager, tray_icon = self._manager()
        manager.categories = {"sync"}

        manager.error("Title", "Message")

        tray_icon.showMessage.assert_not_called()

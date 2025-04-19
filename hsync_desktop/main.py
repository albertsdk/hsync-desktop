# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Main entry point for HSYNC Desktop.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from hsync_desktop import __version__
from hsync_desktop.engine import HsyncEngine
from hsync_desktop.i18n import init_language
from hsync_desktop.main_window import MainWindow
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.settings_dialog import are_notifications_enabled, get_saved_theme
from hsync_desktop.single_instance import SingleInstance
from hsync_desktop.splash_screen import SplashScreen
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import apply_theme


def main() -> int:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("HSYNC Desktop")
    app.setOrganizationName("HSYNC")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    # Ensure only one instance runs at a time
    single_instance = SingleInstance(app)
    if not single_instance.try_start():
        # Another instance is already running - we signaled it to activate
        return 0

    # Initialize i18n (must be done before any widget creation)
    init_language()

    # Apply saved theme
    theme = get_saved_theme()
    apply_theme(app, theme)

    # Create core components
    engine = HsyncEngine()
    # First create window, then pass it to tray
    window = MainWindow(engine, None)  # temp: no tray yet
    tray = SystemTray(window)
    # Now update window with tray and connect tray signals
    window._tray = tray
    tray.toggle_window.connect(window._toggle_visibility)
    tray.start_requested.connect(window._on_start)
    tray.stop_requested.connect(window._on_stop)
    tray.refresh_requested.connect(window._on_refresh)
    tray.settings_requested.connect(window._open_settings)
    tray.quit_requested.connect(window._quit)
    # Create the notifier now that tray is available
    window._notifier = NotificationManager(tray)
    window._notifier.enabled = are_notifications_enabled()

    # Connect single instance activation to window
    def activate_window() -> None:
        window.show()
        window.raise_()
        window.activateWindow()
        # Update tray menu text when window becomes visible
        tray._apply_translations()

    single_instance.activate_requested.connect(activate_window)

    # Show splash screen and connect to activate window when it closes
    splash = SplashScreen()
    splash.finished.connect(activate_window)
    splash.show_and_dismiss(3000)

    # Show tray (window will be shown when splash screen finishes)
    tray.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

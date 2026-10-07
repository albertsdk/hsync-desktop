# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Main entry point for HSYNC Desktop.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from hsync_desktop import __version__
from hsync_desktop.engine import BinaryVersionProbe, HsyncEngine, is_binary_version_compatible
from hsync_desktop.i18n import init_language, tr
from hsync_desktop.main_window import MainWindow
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.settings import (
    are_notifications_enabled,
    get_saved_theme,
    secure_config_file,
)
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

    # Tighten permissions on the QSettings config file (owner-only) in case a
    # previous run created it world-readable.
    secure_config_file()

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
        tray.set_window_visible(True)

    single_instance.activate_requested.connect(activate_window)

    # Show splash screen and connect to activate window when it closes
    splash = SplashScreen()
    splash.finished.connect(activate_window)
    splash.show_and_dismiss(3000)

    # Show tray (window will be shown when splash screen finishes)
    tray.show()

    # Warn if the bundled hsync-client binary is a different major version than
    # this GUI. The two are built and shipped together; a major mismatch means
    # the CLI contract the engine relies on may have changed (version coupling).
    # The probe runs asynchronously (QProcess, cached in QSettings), so it never
    # blocks startup: the warning appears once the result is available.
    probe = BinaryVersionProbe(engine.binary_path, window)

    def _warn_on_mismatch(binary_version: str) -> None:
        if binary_version and not is_binary_version_compatible(binary_version):
            QMessageBox.warning(
                None,
                tr("notif.version_mismatch"),
                tr("notif.version_mismatch_msg")
                .replace("{binary}", binary_version)
                .replace("{expected}", __version__),
            )

    probe.finished.connect(_warn_on_mismatch)
    probe.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

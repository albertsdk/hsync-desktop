# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Main entry point for HSYNC Desktop.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from hsync_desktop.config import MINIMIZED_FLAG

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from hsync_desktop.main_window import MainWindow


def _handle_early_cli_args(argv: list[str]) -> int | None:
    """Handle ``--version``/``--help`` without initialising Qt.

    Creating a ``QApplication`` loads the platform theme integration, which
    on some GNOME releases aborts the process when the bundled GLib reads a
    host ``xsettings`` schema that no longer contains the ``antialiasing``
    key. ``--version`` must never pay that price: answer directly.
    """
    if "--version" in argv or "-V" in argv:
        from hsync_desktop import __version__

        print(f"hsync-desktop {__version__}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(f"Usage: hsync-desktop [--version] [--help] [{MINIMIZED_FLAG}]")
        print("HSYNC Desktop - Cross-platform GUI for HSYNC Client.")
        return 0
    return None


def _should_start_minimized(argv: list[str], tray_available: bool) -> bool:
    """Whether to start hidden in the tray (``--minimized`` + a usable tray).

    The OS autostart entry launches the app with ``--minimized``. Starting
    hidden without a system tray would leave the process with no way to be
    reached, so the flag is ignored when no tray is available.
    """
    return MINIMIZED_FLAG in argv and tray_available


def _harden_linux_gsettings() -> None:
    """Keep Qt off the host GNOME theme integration on Linux.

    The ``gtk3`` platform-theme plugin reads the host GSettings schemas with
    the GLib bundled by PyInstaller; when the host
    ``org.gnome.settings-daemon.plugins.xsettings`` schema drops a key Qt
    expects (``antialiasing``), GLib raises a fatal ``GLib-GIO-ERROR`` that
    aborts the process before the GUI appears. Forcing the built-in
    ``generic`` theme plugin keeps Qt on its own defaults (the app applies
    its own light/dark QSS anyway). The host's configured fonts are applied
    explicitly instead (``hsync_desktop/fonts.py::apply_system_fonts``).
    Respects an explicit user value.
    """
    if sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "generic")


def _install_sigint_handler(window: MainWindow) -> None:
    """Make Ctrl+C quit through the normal path instead of interrupting a slot.

    Qt owns the main loop, so CPython's default SIGINT handling raises
    ``KeyboardInterrupt`` inside whatever slot happens to be running: PySide6
    logs a traceback and the app keeps running (Ctrl+C appears to do nothing).
    Route SIGINT to ``MainWindow._quit`` — the same path as the tray "Quit"
    action, including the confirmation while a sync is running — and keep a fast
    no-op timer so the interpreter keeps ticking and runs the handler promptly
    while the C++ event loop is busy.
    """
    import signal

    from PySide6.QtCore import QTimer

    def _on_sigint(_signum: int, _frame: object) -> None:
        window._quit()

    signal.signal(signal.SIGINT, _on_sigint)

    tick = QTimer(window)  # parented to the window so it is not garbage-collected
    tick.timeout.connect(lambda: None)
    tick.start(200)


def _configure_app(app: QApplication) -> None:
    """Set the app identity used by QSettings, the window manager and the taskbar.

    ``setDesktopFileName`` ties the window's WM_CLASS (X11) / app_id (Wayland) to
    the installed ``hsync-desktop.desktop`` (whose ``StartupWMClass`` and ``Icon``
    are ``hsync-desktop``), and ``setWindowIcon`` provides the X11 window icon, so
    the taskbar shows the app icon instead of a generic one.
    """
    from hsync_desktop import __version__
    from hsync_desktop.icons import icon

    app.setApplicationName("HSYNC Desktop")
    app.setOrganizationName("HSYNC")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("hsync-desktop")
    app.setWindowIcon(icon("hsync-desktop"))


def main(argv: list[str] | None = None) -> int:
    """Application entry point."""
    args = list(sys.argv[1:] if argv is None else argv)
    early = _handle_early_cli_args(args)
    if early is not None:
        return early

    _harden_linux_gsettings()

    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

    from hsync_desktop import __version__
    from hsync_desktop.engine import BinaryVersionProbe, HsyncEngine, is_binary_version_compatible
    from hsync_desktop.fonts import apply_system_fonts
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

    app = QApplication([sys.argv[0], *(a for a in args if a != MINIMIZED_FLAG)])
    _configure_app(app)
    # Follow the desktop's configured fonts (the generic platform theme we force
    # on Linux does not read them; see hsync_desktop/fonts.py).
    apply_system_fonts(app)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    # Launched by the OS autostart entry: show only the tray, not the window
    # (unless there is no tray, in which case the window must be shown).
    start_minimized = _should_start_minimized(args, QSystemTrayIcon.isSystemTrayAvailable())

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
    # Create the notifier now that tray is available. Routine notifications are
    # suppressed while the main window is in the foreground.
    window._notifier = NotificationManager(
        tray,
        is_foreground=lambda: window.isVisible() and window.isActiveWindow(),
    )
    window._notifier.enabled = are_notifications_enabled()

    # Ctrl+C must shut down cleanly rather than interrupt a random slot.
    _install_sigint_handler(window)

    # Connect single instance activation to window
    def activate_window() -> None:
        window.show()
        window.raise_()
        window.activateWindow()
        # Update tray menu text when window becomes visible
        tray.set_window_visible(True)

    single_instance.activate_requested.connect(activate_window)

    # Reveal the window after the splash unless the OS autostart entry launched
    # the app in the tray: then stay hidden. A later manual launch still reveals
    # the window through the single-instance activation signal above.
    if not start_minimized:
        splash = SplashScreen()
        splash.finished.connect(activate_window)
        splash.show_and_dismiss(2500)

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

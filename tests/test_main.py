# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.__main__ and main entry points."""

import os
from unittest.mock import MagicMock


class _FakeSettings:
    """Duck-typed QSettings for the pure splash-gating helper (no Qt state)."""

    def __init__(self, values: dict | None = None) -> None:
        self._values = values or {}

    def value(self, key: str, default: object = None, _type: object = None) -> object:
        return self._values.get(key, default)


class TestMainModule:
    """Test main entry point module."""

    def test_main_function_import(self):
        """Test that main function can be imported from main module."""
        from hsync_desktop.main import main

        assert callable(main)

    def test_main_module_import(self):
        """Test that __main__ module can be imported."""
        from hsync_desktop import __main__

        assert __main__ is not None


class TestMainImports:
    """Test that main module can import all required components."""

    def test_import_qapplication(self):
        """Test QApplication can be imported."""
        from PySide6.QtWidgets import QApplication

        assert QApplication is not None

    def test_import_version(self):
        """Test __version__ can be imported."""
        from hsync_desktop import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_import_hsync_engine(self):
        """Test HsyncEngine can be imported."""
        from hsync_desktop.engine import HsyncEngine

        assert HsyncEngine is not None

    def test_import_init_language(self):
        """Test init_language can be imported."""
        from hsync_desktop.i18n import init_language

        assert callable(init_language)

    def test_import_main_window(self):
        """Test MainWindow can be imported."""
        from hsync_desktop.main_window import MainWindow

        assert MainWindow is not None

    def test_import_get_saved_theme(self):
        """Test get_saved_theme can be imported."""
        from hsync_desktop.settings import get_saved_theme

        assert callable(get_saved_theme)

    def test_import_single_instance(self):
        """Test SingleInstance can be imported."""
        from hsync_desktop.single_instance import SingleInstance

        assert SingleInstance is not None

    def test_import_splash_screen(self):
        """Test SplashScreen can be imported."""
        from hsync_desktop.splash_screen import SplashScreen

        assert SplashScreen is not None

    def test_import_system_tray(self):
        """Test SystemTray can be imported."""
        from hsync_desktop.system_tray import SystemTray

        assert SystemTray is not None

    def test_import_apply_theme(self):
        """Test apply_theme can be imported."""
        from hsync_desktop.themes import apply_theme

        assert callable(apply_theme)


class TestAppMetadata:
    """Test application metadata."""

    def test_application_name_constant(self):
        """Test app name is defined in main."""
        # Just verify the main module has the expected structure
        import hsync_desktop.main as main_module

        # Check that main function exists
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

    def test_version_flag_prints_without_qt(self, monkeypatch, capsys):
        """--version answers without creating a QApplication (GLib crash guard)."""
        import PySide6.QtWidgets as qt_widgets

        import hsync_desktop
        import hsync_desktop.main as main_module

        class _NoQApp:
            def __new__(cls, *args, **kwargs):
                raise AssertionError("QApplication must not be created for --version")

            @staticmethod
            def instance():
                return None

        monkeypatch.setattr(qt_widgets, "QApplication", _NoQApp)
        assert main_module.main(["--version"]) == 0
        out = capsys.readouterr().out
        assert out.strip() == f"hsync-desktop {hsync_desktop.__version__}"

    def test_help_flag_prints_usage(self, capsys):
        """--help prints usage and exits 0 without touching Qt."""
        import hsync_desktop.main as main_module

        assert main_module.main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "Usage: hsync-desktop" in out
        assert "--minimized" in out

    def test_minimized_flag_needs_a_usable_tray(self):
        """--minimized starts hidden only when a tray is available."""
        from hsync_desktop.main import _should_start_minimized

        assert _should_start_minimized(["--minimized"], tray_available=True) is True
        assert _should_start_minimized(["--minimized"], tray_available=False) is False
        assert _should_start_minimized([], tray_available=True) is False

    def test_should_show_splash_on_first_run(self):
        """A fresh install (no flag, no folder) shows the welcome overlay."""
        from hsync_desktop.main import _should_show_splash

        assert _should_show_splash(_FakeSettings()) is True

    def test_should_show_splash_skips_after_shown(self):
        """Once shown, the welcome overlay never appears again."""
        from hsync_desktop.main import _should_show_splash

        assert _should_show_splash(_FakeSettings({"ui/splash_shown": True})) is False

    def test_should_show_splash_skips_when_configured(self):
        """An existing install (folder configured) does not re-show it on upgrade."""
        from hsync_desktop.main import _should_show_splash

        assert _should_show_splash(_FakeSettings({"path/local": "/data"})) is False

    def test_harden_gsettings_defaults_to_memory(self, monkeypatch):
        """Linux default keeps Qt off host theme plugins (xsettings abort)."""
        import hsync_desktop.main as main_module

        monkeypatch.delenv("QT_QPA_PLATFORMTHEME", raising=False)
        monkeypatch.setattr(main_module.sys, "platform", "linux")
        main_module._harden_linux_gsettings()
        assert os.environ["QT_QPA_PLATFORMTHEME"] == "generic"

    def test_harden_gsettings_respects_explicit_value(self, monkeypatch):
        """An explicit QT_QPA_PLATFORMTHEME is never overridden."""
        import hsync_desktop.main as main_module

        monkeypatch.setenv("QT_QPA_PLATFORMTHEME", "gtk3")
        monkeypatch.setattr(main_module.sys, "platform", "linux")
        main_module._harden_linux_gsettings()
        assert os.environ["QT_QPA_PLATFORMTHEME"] == "gtk3"

    def test_main_exits_when_another_instance_is_running(self, monkeypatch, qapp):
        """main() returns cleanly before creating UI when single-instance lock is held."""
        import sys as _sys

        import PySide6.QtWidgets as qt_widgets

        import hsync_desktop.icons as icons_module
        import hsync_desktop.main as main_module
        import hsync_desktop.single_instance as single_instance_module

        app = MagicMock()
        single_instance = MagicMock()
        single_instance.try_start.return_value = False

        class _FakeQApp:
            def __new__(cls, argv):
                del argv
                return app

            @staticmethod
            def instance():
                return app

        def fake_single_instance(qapp):
            del qapp
            return single_instance

        monkeypatch.setattr(qt_widgets, "QApplication", _FakeQApp)
        monkeypatch.setattr(single_instance_module, "SingleInstance", fake_single_instance)
        # The real icon() loads a QIcon, which needs a live QGuiApplication; the
        # identity path is exercised with a mock so no real app is created here.
        monkeypatch.setattr(icons_module, "icon", lambda name: MagicMock(name=name))
        monkeypatch.setattr(_sys, "argv", ["hsync-desktop"])

        assert main_module.main([]) == 0
        app.setApplicationName.assert_called_once_with("HSYNC Desktop")
        app.setOrganizationName.assert_called_once_with("HSYNC")
        app.setDesktopFileName.assert_called_once_with("hsync-desktop")
        app.setWindowIcon.assert_called_once()
        app.setQuitOnLastWindowClosed.assert_called_once_with(False)
        single_instance.try_start.assert_called_once_with()


class TestAppIdentity:
    """The window is bound to the installed desktop entry and the app icon."""

    def test_app_icon_is_bundled(self, qapp):
        from hsync_desktop.icons import icon

        assert not icon("hsync-desktop").isNull()

    def test_app_icon_svg_root_is_recognizable(self):
        """GNOME's icon loader (gdk-pixbuf) only recognizes an SVG when ``<svg``
        appears within the first bytes; a long leading comment makes the taskbar
        icon render blank, so the root element must stay at the top of the file.
        """
        from pathlib import Path

        from hsync_desktop.icons import ICONS_DIR

        root = Path(__file__).resolve().parents[1]
        icons = [
            ICONS_DIR / "hsync-desktop.svg",
            root / "packaging/deb/usr/share/icons/hicolor/scalable/apps/hsync-desktop.svg",
        ]
        for svg in icons:
            text = svg.read_text(encoding="utf-8")
            assert text.index("<svg") < 64, f"<svg must be at the top of {svg}"

    def test_configure_app_sets_desktop_file_and_icon(self, qapp):
        from hsync_desktop.main import _configure_app

        previous_name = qapp.desktopFileName()
        previous_icon = qapp.windowIcon()
        try:
            _configure_app(qapp)
            assert qapp.desktopFileName() == "hsync-desktop"
            assert not qapp.windowIcon().isNull()
            assert qapp.applicationName() == "HSYNC Desktop"
        finally:
            qapp.setDesktopFileName(previous_name)
            qapp.setWindowIcon(previous_icon)

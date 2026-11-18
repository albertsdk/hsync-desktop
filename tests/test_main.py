# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.__main__ and main entry points."""

import io
import os
import sys
from unittest.mock import MagicMock

import PySide6.QtWidgets as _qt_widgets
import pytest


class _FakeSettings:
    """Duck-typed QSettings for the pure splash-gating helper (no Qt state)."""

    def __init__(self, values: dict | None = None) -> None:
        self._values = values or {}

    def value(self, key: str, default: object = None, _type: object = None) -> object:
        return self._values.get(key, default)


def _stub_early_dialog(monkeypatch) -> list[str]:
    """Capture the early-CLI dialog texts instead of showing a modal box.

    The dialog path reuses the running ``QApplication``, so the caller requests
    pytest-qt's ``qapp`` fixture; only ``QMessageBox`` is stubbed (patching the
    ``QApplication`` class itself would break pytest-qt's event processing).
    """
    shown: list[str] = []
    monkeypatch.setattr(
        _qt_widgets.QMessageBox,
        "information",
        staticmethod(lambda _parent, _title, text, *args: shown.append(text)),
    )
    return shown


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

    @pytest.mark.parametrize("flag", ["--version", "--help"])
    def test_early_flags_survive_a_missing_stdout(self, monkeypatch, qapp, flag):
        """A windowed Windows exe launched from Explorer has ``sys.stdout = None``."""
        import hsync_desktop.main as main_module

        monkeypatch.setattr(main_module.sys, "stdout", None)
        monkeypatch.setattr(main_module, "_attach_console_stream", lambda: False)
        _stub_early_dialog(monkeypatch)

        assert main_module.main([flag]) == 0

    @pytest.mark.parametrize("flag", ["--version", "--help"])
    def test_early_flags_use_a_dialog_without_any_console(self, monkeypatch, qapp, flag):
        """Windows GUI build with no parent console: the text must still be shown."""
        import hsync_desktop.main as main_module

        monkeypatch.setattr(main_module.sys, "stdout", None)
        monkeypatch.setattr(main_module, "_attach_console_stream", lambda: False)
        shown = _stub_early_dialog(monkeypatch)

        assert main_module.main([flag]) == 0
        assert shown and ("hsync-desktop " in shown[0] or "Usage: hsync-desktop" in shown[0])

    @pytest.mark.parametrize("flag", ["--version", "--help"])
    def test_a_windowed_build_without_a_stream_shows_the_dialog(self, monkeypatch, qapp, flag):
        """A macOS ``.app`` (or any windowed build) has ``sys.stdout = None`` and no
        console to attach, so the dialog is the only way to show the text."""
        import hsync_desktop.main as main_module

        monkeypatch.setattr(main_module.sys, "stdout", None)
        monkeypatch.setattr(main_module.os, "name", "posix")
        shown = _stub_early_dialog(monkeypatch)

        assert main_module.main([flag]) == 0
        assert shown

    def test_a_closed_stream_does_not_escape_main(self, monkeypatch, qapp):
        """A closed stdout must degrade to the dialog, not raise from main()."""
        import hsync_desktop.main as main_module

        closed = open(os.devnull, "w", encoding="utf-8")
        closed.close()
        monkeypatch.setattr(main_module.sys, "stdout", closed)
        monkeypatch.setattr(main_module.os, "name", "posix")
        shown = _stub_early_dialog(monkeypatch)

        assert main_module.main(["--version"]) == 0
        assert shown

    def test_early_flags_prefer_the_stream_over_the_dialog(self, monkeypatch, capsys):
        """With a usable console no Qt object is created (scripting keeps working)."""
        import hsync_desktop.main as main_module

        monkeypatch.setattr(
            _qt_widgets.QMessageBox,
            "information",
            staticmethod(lambda *args: pytest.fail("the dialog must not be used")),
        )

        assert main_module.main(["--version"]) == 0
        assert "hsync-desktop " in capsys.readouterr().out

    def test_attach_console_stream_is_windows_only(self, monkeypatch):
        """Off Windows there is no console to attach; the caller falls back."""
        import hsync_desktop.main as main_module

        monkeypatch.setattr(main_module.os, "name", "posix")
        assert main_module._attach_console_stream() is False

    def test_attach_console_stream_rebinds_stdout_on_windows(self, monkeypatch):
        """The Windows path attaches and replaces the stream with CONOUT$."""
        import hsync_desktop.main as main_module

        attached: list[int] = []

        class _Kernel32:
            @staticmethod
            def AttachConsole(pid: int) -> int:
                attached.append(pid)
                return 1

        class _Windll:
            kernel32 = _Kernel32()

        class _Ctypes:
            windll = _Windll()

        opened: list[str] = []

        def _fake_open(name, mode="r", **_kwargs):
            opened.append(name)
            return io.StringIO()

        monkeypatch.setattr(main_module.os, "name", "nt")
        monkeypatch.setattr(main_module.sys, "stdout", None)
        monkeypatch.setitem(sys.modules, "ctypes", _Ctypes())
        monkeypatch.setattr(main_module, "open", _fake_open, raising=False)

        assert main_module._attach_console_stream() is True
        assert attached == [-1]  # ATTACH_PARENT_PROCESS
        assert opened == ["CONOUT$"]
        assert main_module._stdout_is_usable() is True

    def test_attach_console_stream_reports_failure_without_a_parent_console(self, monkeypatch):
        """Started from Explorer ``AttachConsole`` fails and the dialog takes over."""
        import hsync_desktop.main as main_module

        class _Kernel32:
            @staticmethod
            def AttachConsole(_pid: int) -> int:
                return 0

        class _Windll:
            kernel32 = _Kernel32()

        class _Ctypes:
            windll = _Windll()

        monkeypatch.setattr(main_module.os, "name", "nt")
        monkeypatch.setattr(main_module.sys, "stdout", None)
        monkeypatch.setitem(sys.modules, "ctypes", _Ctypes())

        assert main_module._attach_console_stream() is False

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

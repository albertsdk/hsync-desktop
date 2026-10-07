# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.__main__ and main entry points."""

from unittest.mock import MagicMock


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

    def test_main_exits_when_another_instance_is_running(self, monkeypatch):
        """main() returns cleanly before creating UI when single-instance lock is held."""
        import hsync_desktop.main as main_module

        app = MagicMock()
        single_instance = MagicMock()
        single_instance.try_start.return_value = False

        def fake_qapplication(argv):
            del argv
            return app

        def fake_single_instance(qapp):
            del qapp
            return single_instance

        monkeypatch.setattr(main_module, "QApplication", fake_qapplication)
        monkeypatch.setattr(main_module, "SingleInstance", fake_single_instance)

        assert main_module.main() == 0
        app.setApplicationName.assert_called_once_with("HSYNC Desktop")
        app.setOrganizationName.assert_called_once_with("HSYNC")
        app.setQuitOnLastWindowClosed.assert_called_once_with(False)
        single_instance.try_start.assert_called_once_with()

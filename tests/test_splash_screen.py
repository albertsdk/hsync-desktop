# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.splash_screen module."""


class TestSplashScreen:
    """Test SplashScreen class."""

    def test_splash_screen_import(self):
        """Test that SplashScreen can be imported."""
        from hsync_desktop.splash_screen import SplashScreen

        assert SplashScreen is not None

    def test_splash_screen_has_finished_signal(self):
        """Test that SplashScreen has finished signal."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "finished")

    def test_splash_screen_has_show_and_dismiss_method(self):
        """Test that SplashScreen has show_and_dismiss method."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "show_and_dismiss")
        assert callable(SplashScreen.show_and_dismiss)

    def test_splash_screen_has_show_as_about_method(self):
        """Test that SplashScreen has show_as_about method."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "show_as_about")
        assert callable(SplashScreen.show_as_about)

    def test_splash_screen_has_mouse_press_event(self):
        """Test that SplashScreen has mousePressEvent method."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "mousePressEvent")

    def test_splash_screen_has_key_press_event(self):
        """Test that SplashScreen has keyPressEvent method."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "keyPressEvent")

    def test_splash_screen_has_close_event(self):
        """Test that SplashScreen has closeEvent method."""
        from hsync_desktop.splash_screen import SplashScreen

        assert hasattr(SplashScreen, "closeEvent")

    def test_splash_screen_inherits_qwidget(self):
        """Test that SplashScreen inherits from QWidget."""
        from PySide6.QtWidgets import QWidget

        from hsync_desktop.splash_screen import SplashScreen

        assert issubclass(SplashScreen, QWidget)


class TestModuleImports:
    """Test module-level imports."""

    def test_version_import(self):
        """Test that __version__ can be imported."""
        from hsync_desktop import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_i18n_import(self):
        """Test that i18n functions can be imported."""
        from hsync_desktop.splash_screen import tr

        assert tr is not None
        assert callable(tr)

    def test_ui_loader_import(self):
        """Test that load_ui_widget can be imported."""
        from hsync_desktop.splash_screen import load_ui_widget

        assert load_ui_widget is not None
        assert callable(load_ui_widget)

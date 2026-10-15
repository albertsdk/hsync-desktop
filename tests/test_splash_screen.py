# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

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


class TestSplashLayoutAndAbout:
    """The redesigned splash / About surface."""

    @staticmethod
    def _make(qtbot):
        from hsync_desktop.splash_screen import SplashScreen

        splash = SplashScreen()
        qtbot.addWidget(splash)
        return splash

    def test_shows_the_horizontal_brand_logo(self, qtbot):
        splash = self._make(qtbot)
        pixmap = splash._lbl_logo.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()

    def test_app_name_is_bold_and_not_larger_than_the_other_labels(self, qtbot):
        splash = self._make(qtbot)
        font = splash._lbl_app_name.font()
        assert font.bold()
        assert font.pointSize() == splash._lbl_tagline.font().pointSize()

    def test_version_is_a_bare_number(self, qtbot):
        from hsync_desktop import __version__

        splash = self._make(qtbot)
        assert splash._lbl_version.text() == __version__
        assert "version" not in splash._lbl_version.text().lower()

    def test_tagline_copyright_and_author(self, qtbot):
        from hsync_desktop.i18n import tr

        splash = self._make(qtbot)
        assert splash._lbl_tagline.text() == tr("app.tagline")
        assert splash._lbl_copyright.text() == "Copyright © 2024-2026"
        assert splash._lbl_author.text() == "Alberto Basso"

    def test_click_dismisses_the_splash_and_reveals_the_app(self, qtbot):
        from PySide6.QtCore import Qt

        splash = self._make(qtbot)
        fired: list[bool] = []
        splash.finished.connect(lambda: fired.append(True))
        splash.show()
        qtbot.mouseClick(splash, Qt.MouseButton.LeftButton)
        assert not splash.isVisible()
        assert fired == [True]

    def test_click_closes_the_about_without_revealing_the_app(self, qtbot):
        from PySide6.QtCore import Qt

        splash = self._make(qtbot)
        fired: list[bool] = []
        splash.finished.connect(lambda: fired.append(True))
        splash.show_as_about()
        qtbot.mouseClick(splash, Qt.MouseButton.LeftButton)
        assert not splash.isVisible()
        assert fired == []

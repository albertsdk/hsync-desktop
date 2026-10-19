# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.themes module."""

import hsync_desktop.themes as themes


class TestThemeConstants:
    """Test theme constants."""

    def test_theme_light(self):
        assert themes.THEME_LIGHT == "light"

    def test_theme_dark(self):
        assert themes.THEME_DARK == "dark"


class TestStatusColors:
    """Test status color constants."""

    def test_color_connected(self):
        # QColor.name() returns lowercase hex
        assert themes.COLOR_CONNECTED.name().lower() == "#2ea043"

    def test_color_disconnected(self):
        assert themes.COLOR_DISCONNECTED.name().lower() == "#cf222e"

    def test_color_waiting(self):
        assert themes.COLOR_WAITING.name().lower() == "#bf8700"


class TestLightPalette:
    """Test light palette generation."""

    def test_light_palette_builds(self):
        """Light palette should build without errors."""
        palette = themes._build_light_palette()
        assert palette is not None
        # Check some colors (lowercase for comparison)
        assert palette.color(themes.QPalette.ColorRole.Window).name().lower() == "#f5f5f5"
        assert palette.color(themes.QPalette.ColorRole.WindowText).name().lower() == "#1e1e1e"
        assert palette.color(themes.QPalette.ColorRole.Base).name().lower() == "#ffffff"


class TestDarkPalette:
    """Test dark palette generation."""

    def test_dark_palette_builds(self):
        """Dark palette should build without errors."""
        palette = themes._build_dark_palette()
        assert palette is not None
        # Check some colors (lowercase for comparison)
        assert palette.color(themes.QPalette.ColorRole.Window).name().lower() == "#1e1e1e"
        assert palette.color(themes.QPalette.ColorRole.WindowText).name().lower() == "#d4d4d4"
        assert palette.color(themes.QPalette.ColorRole.Base).name().lower() == "#252526"


class TestQSSGeneration:
    """Test QSS stylesheet generation."""

    def test_light_qss_is_string(self):
        """Light QSS should be a non-empty string."""
        qss = themes._light_qss()
        assert isinstance(qss, str)
        assert len(qss) > 0

    def test_dark_qss_is_string(self):
        """Dark QSS should be a non-empty string."""
        qss = themes._dark_qss()
        assert isinstance(qss, str)
        assert len(qss) > 0

    def test_light_qss_contains_light_colors(self):
        """Light QSS should contain light theme colors."""
        qss = themes._light_qss()
        # Light theme border should be light gray (without extra quotes)
        assert "#D0D0D0" in qss

    def test_dark_qss_contains_dark_colors(self):
        """Dark QSS should contain dark theme colors."""
        qss = themes._dark_qss()
        # Dark theme border should be darker (without extra quotes)
        assert "#404040" in qss


class TestCommonQSS:
    """Test common QSS contains expected selectors."""

    def test_common_qss_has_qtooltip(self):
        """Common QSS should have QToolTip styles."""
        assert "QToolTip" in themes._COMMON_QSS

    def test_common_qss_has_qpushbutton(self):
        """Common QSS should have QPushButton styles."""
        assert "QPushButton" in themes._COMMON_QSS

    def test_common_qss_has_qgroupbox(self):
        """Common QSS should have QGroupBox styles."""
        assert "QGroupBox" in themes._COMMON_QSS

    def test_common_qss_has_qmenubar(self):
        """Common QSS should have QMenuBar styles."""
        assert "QMenuBar" in themes._COMMON_QSS

    def test_common_qss_has_qmenu(self):
        assert "QMenu" in themes._COMMON_QSS

    def test_common_qss_does_not_pin_a_font_family(self):
        """The font comes from the desktop (see hsync_desktop/fonts.py)."""
        assert "font-family" not in themes._COMMON_QSS


class TestSystemThemeDetection:
    """Qt's scheme first; the Linux desktop settings when Qt reports Unknown."""

    def test_qt_dark_wins(self, monkeypatch):
        monkeypatch.setattr(themes, "_qt_color_scheme", lambda: themes.Qt.ColorScheme.Dark)
        assert themes.detect_system_theme() == themes.THEME_DARK

    def test_qt_light_wins(self, monkeypatch):
        monkeypatch.setattr(themes, "_qt_color_scheme", lambda: themes.Qt.ColorScheme.Light)
        assert themes.detect_system_theme() == themes.THEME_LIGHT

    def test_unknown_uses_linux_desktop_dark(self, monkeypatch):
        monkeypatch.setattr(themes, "_qt_color_scheme", lambda: themes.Qt.ColorScheme.Unknown)
        monkeypatch.setattr(themes, "_linux_desktop_is_dark", lambda: True)
        monkeypatch.setattr(themes.sys, "platform", "linux")
        assert themes.detect_system_theme() == themes.THEME_DARK

    def test_unknown_uses_linux_desktop_light(self, monkeypatch):
        monkeypatch.setattr(themes, "_qt_color_scheme", lambda: themes.Qt.ColorScheme.Unknown)
        monkeypatch.setattr(themes, "_linux_desktop_is_dark", lambda: False)
        monkeypatch.setattr(themes.sys, "platform", "linux")
        assert themes.detect_system_theme() == themes.THEME_LIGHT

    def test_gtk_theme_env_is_honoured(self, monkeypatch):
        monkeypatch.setenv("GTK_THEME", "Adwaita:dark")
        assert themes._linux_desktop_is_dark() is True

    def test_gnome_prefer_dark(self, monkeypatch):
        import hsync_desktop.fonts as fonts

        monkeypatch.delenv("GTK_THEME", raising=False)
        monkeypatch.setattr(
            fonts,
            "_gsettings_values",
            lambda keys: {"color-scheme": "'prefer-dark'", "gtk-theme": "'Adwaita'"},
        )
        assert themes._linux_desktop_is_dark() is True

    def test_kde_dark_scheme(self, monkeypatch, tmp_path):
        import hsync_desktop.fonts as fonts

        (tmp_path / "kdeglobals").write_text(
            "[General]\nColorScheme=BreezeDark\n", encoding="utf-8"
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("GTK_THEME", raising=False)
        monkeypatch.setattr(fonts, "_gsettings_values", lambda keys: {})
        assert themes._linux_desktop_is_dark() is True

    def test_gtk_ini_dark_theme(self, monkeypatch, tmp_path):
        import hsync_desktop.fonts as fonts

        settings = tmp_path / "gtk-3.0"
        settings.mkdir()
        (settings / "settings.ini").write_text(
            "[Settings]\ngtk-application-prefer-dark-theme=1\n", encoding="utf-8"
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("GTK_THEME", raising=False)
        monkeypatch.setattr(fonts, "_gsettings_values", lambda keys: {})
        assert themes._linux_desktop_is_dark() is True

    def test_palette_fallback_is_dark(self, monkeypatch, qapp):
        monkeypatch.setattr(themes, "_qt_color_scheme", lambda: themes.Qt.ColorScheme.Unknown)
        monkeypatch.setattr(themes, "_linux_desktop_is_dark", lambda: None)
        monkeypatch.setattr(themes.sys, "platform", "linux")
        original = qapp.palette()
        try:
            qapp.setPalette(themes._build_dark_palette())
            assert themes.detect_system_theme() == themes.THEME_DARK
        finally:
            qapp.setPalette(original)

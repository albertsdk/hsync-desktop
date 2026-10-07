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

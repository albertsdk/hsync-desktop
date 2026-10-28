# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.icons module."""

import hsync_desktop.icons as icons


class TestConstants:
    """Test module constants."""

    def test_icons_dir_is_path(self):
        """ICONS_DIR should be a Path object."""
        from pathlib import Path

        assert isinstance(icons.ICONS_DIR, Path)


class TestFallbackMap:
    """Test fallback icon mapping."""

    def test_fallback_map_is_dict(self):
        """_FALLBACK_MAP should be a dictionary."""
        assert isinstance(icons._FALLBACK_MAP, dict)

    def test_fallback_map_not_empty(self):
        """_FALLBACK_MAP should contain entries."""
        assert len(icons._FALLBACK_MAP) > 0

    def test_fallback_map_has_network_cloud(self):
        """Should have network-cloud icon mapping."""
        assert "network-cloud" in icons._FALLBACK_MAP

    def test_fallback_map_has_folder(self):
        """Should have folder icon mapping."""
        assert "folder" in icons._FALLBACK_MAP

    def test_fallback_map_values_are_strings(self):
        """All fallback map values should be strings (filenames)."""
        for key, value in icons._FALLBACK_MAP.items():
            assert isinstance(value, str), f"Value for {key} is not a string"
            assert value.endswith(".svg"), f"Value for {key} is not an SVG"


class TestIconCache:
    """Test icon cache functionality."""

    def test_icon_cache_is_dict(self):
        """_icon_cache should be a dictionary."""
        assert isinstance(icons._icon_cache, dict)

    def test_clear_icon_cache_callable(self):
        """clear_icon_cache should be callable and work."""
        # Just verify it's callable and doesn't raise
        icons.clear_icon_cache()


class TestIconFunctions:
    """Test icon-related functions."""

    def test_clear_icon_cache_function_exists(self):
        """clear_icon_cache function should exist."""
        assert callable(icons.clear_icon_cache)

    def test_icon_function_exists(self):
        """icon function should exist."""
        assert callable(icons.icon)


class TestThemeDetection:
    """Test theme detection functions."""

    def test_is_dark_theme_function_exists(self):
        """_is_dark_theme function should exist."""
        assert callable(icons._is_dark_theme)

    def test_has_icon_theme_function_exists(self):
        """_has_icon_theme function should exist."""
        assert callable(icons._has_icon_theme)


class TestLoadThemedSvg:
    """Test SVG loading function."""

    def test_load_themed_svg_function_exists(self):
        """_load_themed_svg function should exist."""
        assert callable(icons._load_themed_svg)


class TestWizardModeIcons:
    """The four wizard modes use registered, loadable bundled icons."""

    def test_mode_icons_are_registered(self):
        from hsync_desktop.wizard.pages.mode import _MODE_ICONS

        assert set(_MODE_ICONS.values()) <= set(icons._FALLBACK_MAP)

    def test_mode_icons_load(self, qapp):
        from hsync_desktop.wizard.pages.mode import _MODE_ICONS

        for name in set(_MODE_ICONS.values()):
            assert not icons.icon(name).isNull(), name


class TestActionBarCompareIcon:
    """The compare action uses a refresh icon: a magnifier reads as "search"."""

    def test_the_compare_icon_is_registered(self):
        assert "view-refresh" in icons._FALLBACK_MAP

    def test_the_compare_icon_loads(self, qapp):
        assert not icons.icon("view-refresh").isNull()

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.ui.loader module."""

from pathlib import Path


class TestUiLoader:
    """Test UiLoader class."""

    def test_ui_dir_exists(self):
        """Test that UI_DIR is defined and is a Path."""
        from hsync_desktop.ui.loader import UI_DIR

        assert isinstance(UI_DIR, Path)

    def test_ui_dir_has_ui_files(self):
        """Test that UI_DIR contains .ui files."""
        from hsync_desktop.ui.loader import UI_DIR

        ui_files = list(UI_DIR.glob("*.ui"))
        assert len(ui_files) > 0


class TestLoadFunctions:
    """Test load functions exist."""

    def test_load_ui_widget_function_exists(self):
        """Test load_ui_widget function exists."""
        from hsync_desktop.ui.loader import load_ui_widget

        assert callable(load_ui_widget)


class TestUiFiles:
    """Test UI file existence."""

    def test_main_window_ui_exists(self):
        """Test main_window.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "main_window.ui").exists()

    def test_settings_dialog_ui_exists(self):
        """Test settings_dialog.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "settings_dialog.ui").exists()

    def test_file_panel_ui_exists(self):
        """Test file_panel.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "file_panel.ui").exists()

    def test_splash_screen_ui_exists(self):
        """Test splash_screen.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "splash_screen.ui").exists()

    def test_preview_summary_dialog_ui_exists(self):
        """Test preview_summary_dialog.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "preview_summary_dialog.ui").exists()

    def test_api_key_dialog_ui_exists(self):
        """Test api_key_dialog.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "api_key_dialog.ui").exists()

    def test_lan_key_dialog_ui_exists(self):
        """Test lan_key_dialog.ui exists."""
        from hsync_desktop.ui.loader import UI_DIR

        assert (UI_DIR / "lan_key_dialog.ui").exists()

    def test_all_ui_files_are_readable(self):
        """Test all .ui files are readable."""
        from hsync_desktop.ui.loader import UI_DIR

        ui_files = list(UI_DIR.glob("*.ui"))
        for ui_file in ui_files:
            assert ui_file.stat().st_size > 0, f"{ui_file.name} is empty"

    def test_ui_loader_class_exists(self):
        """Test UiLoader class exists."""
        from hsync_desktop.ui.loader import UiLoader

        assert UiLoader is not None

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Qt Designer UI files package.

This package contains:
- .ui files: XML definitions created with Qt Designer
- Compiled Python modules (ui_*.py) generated from .ui files

To compile .ui files to Python, run from the project root:
    python scripts/compile_ui.py

Or use pyside6-uic directly:
    pyside6-uic hsync_desktop/ui/main_window.ui -o hsync_desktop/ui/ui_main_window.py

To load .ui files at runtime (alternative to compilation):
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtCore import QFile

    loader = QUiLoader()
    ui_file = QFile("hsync_desktop/ui/main_window.ui")
    ui_file.open(QFile.ReadOnly)
    window = loader.load(ui_file)
    ui_file.close()
"""

from pathlib import Path

# Directory containing .ui files
UI_DIR = Path(__file__).parent

# List of available .ui files
UI_FILES = {
    "main_window": UI_DIR / "main_window.ui",
    "settings_dialog": UI_DIR / "settings_dialog.ui",
    "splash_screen": UI_DIR / "splash_screen.ui",
    "file_panel": UI_DIR / "file_panel.ui",
    "preview_summary_dialog": UI_DIR / "preview_summary_dialog.ui",
    "api_key_dialog": UI_DIR / "api_key_dialog.ui",
    "lan_key_dialog": UI_DIR / "lan_key_dialog.ui",
    "bandwidth_dialog": UI_DIR / "bandwidth_dialog.ui",
}


def get_ui_path(name: str) -> Path:
    """Get the path to a .ui file by name.

    Args:
        name: Name of the UI file (without extension).
              One of: main_window, settings_dialog, splash_screen, file_panel,
              preview_summary_dialog, api_key_dialog, lan_key_dialog,
              bandwidth_dialog

    Returns:
        Path to the .ui file.

    Raises:
        KeyError: If the UI file name is not found.
    """
    return UI_FILES[name]

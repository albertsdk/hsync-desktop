# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

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

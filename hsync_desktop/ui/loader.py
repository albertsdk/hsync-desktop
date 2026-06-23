# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Runtime loader for Qt Designer .ui files.

This module provides utilities to load .ui files at runtime without
pre-compiling them to Python. This is useful during development when
you want to see UI changes immediately without recompiling.

For production, consider pre-compiling .ui files using:
    python scripts/compile_ui.py

Example usage:
    from hsync_desktop.ui.loader import load_ui_widget

    # Load into an existing widget (for subclassing)
    class MyWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            load_ui_widget("main_window", self)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtUiTools import QUiLoader

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def _get_ui_dir() -> Path:
    """Get the directory containing .ui files.

    Handles both development mode and PyInstaller frozen executable.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle - use _MEIPASS temp directory
        # Files are stored in hsync_desktop/ui subdirectory
        meipass = getattr(sys, "_MEIPASS", "")
        base_path = Path(meipass) / "hsync_desktop" / "ui"
    else:
        # Running in development - use source directory
        base_path = Path(__file__).parent
    return base_path


# Directory containing .ui files
UI_DIR = _get_ui_dir()


class UiLoader(QUiLoader):
    """Custom UI loader that can load into an existing widget."""

    def __init__(self, base_instance: QWidget | None = None) -> None:
        super().__init__(base_instance)
        self._base_instance = base_instance

    def createWidget(
        self,
        class_name: str,
        parent: QWidget | None = None,
        name: str = "",
    ) -> QWidget:
        """Create widget, using base instance for the top-level widget."""
        if parent is None and self._base_instance is not None:
            # This is the top-level widget - return our base instance
            return self._base_instance
        return super().createWidget(class_name, parent, name)


def load_ui_widget(name: str, widget: QWidget) -> None:
    """Load a .ui file into an existing widget instance.

    This is useful when subclassing a widget and wanting to load
    the UI definition into `self`.

    Args:
        name: Name of the UI file (without .ui extension).
        widget: The widget instance to load the UI into.

    Raises:
        FileNotFoundError: If the .ui file doesn't exist.
        RuntimeError: If the .ui file couldn't be loaded.
    """
    ui_path = UI_DIR / f"{name}.ui"
    if not ui_path.exists():
        raise FileNotFoundError(f"UI file not found: {ui_path}")

    ui_file = QFile(str(ui_path))
    if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(f"Cannot open UI file: {ui_path}")

    try:
        loader = UiLoader(widget)
        loader.load(ui_file)
    finally:
        ui_file.close()

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Read-only, scrollable license viewer opened from the Help menu."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.fonts import small_monospace_font
from hsync_desktop.i18n import tr


def _license_path() -> Path | None:
    """Locate the ``LICENSE`` file in the frozen bundle or the source tree."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        candidates.append(Path(meipass) / "hsync_desktop" / "LICENSE")
    # ``hsync_desktop/license_dialog.py`` -> repo root is two levels up.
    candidates.append(Path(__file__).resolve().parent.parent / "LICENSE")
    for path in candidates:
        if path.is_file():
            return path
    return None


def license_text() -> str:
    """Return the project license text (empty when the file is unavailable)."""
    path = _license_path()
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


class LicenseDialog(QDialog):
    """Show the project license in a scrollable, read-only text box."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("menu.help.license"))
        self.resize(680, 520)

        layout = QVBoxLayout(self)
        self._view = QPlainTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._view.setFont(small_monospace_font())
        self._view.setPlainText(license_text() or tr("license.unavailable"))
        layout.addWidget(self._view)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self._buttons.rejected.connect(self.reject)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText(tr("action.close"))
        layout.addWidget(self._buttons)

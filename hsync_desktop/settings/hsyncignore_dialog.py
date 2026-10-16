# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Editor for the `.hsyncignore` file at the bucket root."""

from __future__ import annotations

from pathlib import Path

from hsync_common.constants import HSYNCIGNORE_FILENAME
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import style_ok_cancel_button_box


class HsyncIgnoreEditorDialog(QDialog):
    """Simple text editor for the `.hsyncignore` file at the bucket root."""

    def __init__(self, bucket_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bucket_root = bucket_root
        self._target = bucket_root / HSYNCIGNORE_FILENAME

        self.setWindowTitle(tr("hsyncignore.title"))
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        self._lbl_desc = QLabel(tr("hsyncignore.description"), self)
        self._lbl_desc.setWordWrap(True)
        layout.addWidget(self._lbl_desc)

        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("# Example:\n# /build/\n# *.log\n# !important.log\n")
        layout.addWidget(self._editor, 1)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        # Save/Cancel with the app-theme button icons (SettingsDialog style).
        style_ok_cancel_button_box(button_box)
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._load_file()

    def _load_file(self) -> None:
        """Load the existing .hsyncignore content, if any."""
        if not self._target.exists():
            return
        try:
            self._editor.setPlainText(self._target.read_text(encoding="utf-8"))
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("hsyncignore.title"),
                tr("hsyncignore.read_error").format(error=exc),
            )

    def _on_save(self) -> None:
        """Write the editor content to the .hsyncignore file."""
        try:
            self._bucket_root.mkdir(parents=True, exist_ok=True)
            self._target.write_text(self._editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("hsyncignore.title"),
                tr("hsyncignore.write_error").format(error=exc),
            )
            return
        self.accept()

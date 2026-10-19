# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Step 2 — choose the folder to sync."""

from __future__ import annotations

from pathlib import Path

from hsync_common.format import format_bytes
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.validators import validate_sync_folder
from hsync_desktop.wizard.defaults import suggested_folders
from hsync_desktop.wizard.model import WizardDraft
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import InlineError, muted_label, set_field_error

__all__ = ["FolderPage"]

# Suggestion that creates its target folder on click (the others only select an
# existing, localized user directory).
_CREATE_KEY = "wizard.folder.suggest_home"


class FolderPage(WizardPage):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        self._why = muted_label()
        layout.addWidget(self._why)

        self._label = QLabel()
        layout.addWidget(self._label)

        row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.textChanged.connect(self._on_text_changed)
        row.addWidget(self.path, 1)
        self.browse = QPushButton()
        self.browse.clicked.connect(self._on_browse)
        row.addWidget(self.browse)
        layout.addLayout(row)

        self.error = InlineError()
        layout.addWidget(self.error)

        self._suggestions = QGridLayout()
        self._suggestion_buttons: list[QPushButton] = []
        for index, (key, path) in enumerate(suggested_folders()):
            button = QPushButton()
            target = path or ""
            button.setProperty("wizardPath", target)
            button.setProperty("wizardKey", key)
            button.setProperty("wizardCreate", key == _CREATE_KEY)
            button.clicked.connect(self._on_suggestion)
            # Never offer a path that would immediately fail validation.
            button.setEnabled(bool(target) and (key == _CREATE_KEY or Path(target).is_dir()))
            self._suggestion_buttons.append(button)
            if index < 2:
                self._suggestions.addWidget(button, 0, index)
            else:
                # The "create" suggestion spans the row so long labels fit.
                self._suggestions.addWidget(button, 1, 0, 1, 2)
        layout.addLayout(self._suggestions)

        self.free_space = muted_label()
        layout.addWidget(self.free_space)
        layout.addStretch(1)
        self.apply_translations()

    def _on_text_changed(self, _text: str) -> None:
        self._refresh_free_space()
        self.changed.emit()

    def _on_browse(self) -> None:
        current = self.path.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, tr("settings.shared_path"), current)
        if chosen:
            self.path.setText(chosen)

    def _on_suggestion(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        path = str(button.property("wizardPath"))
        if button.property("wizardCreate"):
            try:
                Path(path).expanduser().mkdir(parents=True, exist_ok=True)
            except OSError:
                set_field_error(self.path, self.error, tr("wizard.folder.create_error"))
                return
        self.path.setText(path)

    def _refresh_free_space(self) -> None:
        check = validate_sync_folder(self.path.text())
        if check.free_bytes is None:
            self.free_space.setText("")
            return
        self.free_space.setText(
            tr("wizard.folder.free_space").format(free=format_bytes(check.free_bytes))
        )

    def apply_translations(self) -> None:
        self._why.setText(tr("wizard.folder.why"))
        self._label.setText(tr("settings.shared_path"))
        self.path.setPlaceholderText(tr("settings.shared_path"))
        self.browse.setText(tr("settings.shared_path_browse"))
        for button in self._suggestion_buttons:
            button.setText(tr(str(button.property("wizardKey"))))
        self._refresh_free_space()

    def load(self, draft: WizardDraft) -> None:
        self.path.setText(draft.local_path)

    def store(self, draft: WizardDraft) -> None:
        draft.local_path = self.path.text().strip()

    def field_error_targets(self) -> dict[str, tuple[QWidget, InlineError]]:
        return {"local_path": (self.path, self.error)}

    def focus_first(self) -> None:
        self.path.setFocus()

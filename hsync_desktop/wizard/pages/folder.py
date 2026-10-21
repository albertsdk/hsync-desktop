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
from hsync_desktop.icons import icon
from hsync_desktop.settings.validators import validate_sync_folder
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.wizard.defaults import suggested_folders
from hsync_desktop.wizard.model import WizardDraft
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import InlineError, set_field_error

__all__ = ["FolderPage"]

# Suggestion that creates its target folder on click (the others only select an
# existing, localized user directory).
_CREATE_KEY = "wizard.folder.suggest_home"

_SUGGESTION_ICONS = {
    "wizard.folder.suggest_documents": "x-office-document",
    "wizard.folder.suggest_pictures": "image-x-generic",
    "wizard.folder.suggest_music": "audio-x-generic",
    "wizard.folder.suggest_videos": "video-x-generic",
    "wizard.folder.suggest_home": "folder-open",
}


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
        entries = suggested_folders()
        standard = [(key, path) for key, path in entries if key != _CREATE_KEY]
        create = [(key, path) for key, path in entries if key == _CREATE_KEY]
        for index, (key, path) in enumerate(standard):
            button = self._make_suggestion(key, path)
            self._suggestions.addWidget(button, index // 2, index % 2)
            self._suggestion_buttons.append(button)
        for key, path in create:
            button = self._make_suggestion(key, path)
            # The "create" suggestion spans the row so long labels fit.
            self._suggestions.addWidget(button, (len(standard) + 1) // 2, 0, 1, 2)
            self._suggestion_buttons.append(button)
        layout.addLayout(self._suggestions)

        self.free_space = muted_label()
        layout.addWidget(self.free_space)
        layout.addStretch(1)
        self.apply_translations()

    def _make_suggestion(self, key: str, path: str | None) -> QPushButton:
        button = QPushButton()
        target = path or ""
        button.setProperty("wizardPath", target)
        button.setProperty("wizardKey", key)
        button.setProperty("wizardCreate", key == _CREATE_KEY)
        button.clicked.connect(self._on_suggestion)
        icon_name = _SUGGESTION_ICONS.get(key)
        if icon_name:
            button.setIcon(icon(icon_name))
        # Never offer a path that would immediately fail validation.
        button.setEnabled(bool(target) and (key == _CREATE_KEY or Path(target).is_dir()))
        return button

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

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""SharesDialog: the "manage shares" list (new/duplicate/rename/delete).

The dialog is a thin view: every mutation is delegated to the window
(``SharesMixin``), which owns the store, the engine and the switch flow.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon


class SharesDialog(QDialog):
    def __init__(self, host, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._host = host
        self.setWindowTitle(tr("shares.manage.title"))
        self._build()
        self._refresh()
        self.resize(420, 360)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self._list = QListWidget(self)
        self._list.itemDoubleClicked.connect(self._on_activate)
        self._list.currentItemChanged.connect(lambda *_: self._update_buttons())
        layout.addWidget(self._list)

        row = QHBoxLayout()
        self._btn_new = QPushButton(tr("shares.manage.new"), self)
        self._btn_duplicate = QPushButton(tr("shares.manage.duplicate"), self)
        self._btn_rename = QPushButton(tr("shares.manage.rename"), self)
        self._btn_delete = QPushButton(tr("shares.manage.delete"), self)
        for button in (self._btn_new, self._btn_duplicate, self._btn_rename, self._btn_delete):
            row.addWidget(button)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._btn_new.clicked.connect(self._on_new)
        self._btn_duplicate.clicked.connect(self._on_duplicate)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_delete.clicked.connect(self._on_delete)

    def _refresh(self) -> None:
        store = self._host._share_store
        active = store.active_id()
        self._list.clear()
        for share in sorted(store.shares(), key=lambda s: s.name.casefold()):
            item = QListWidgetItem(share.name or tr("shares.untitled"), self._list)
            item.setData(Qt.ItemDataRole.UserRole, share.id)
            p2p = bool(share.values.get("p2p/enabled", True))
            item.setIcon(icon("network-p2p" if p2p else "network-cloud"))
            if share.id == active:
                item.setSelected(True)
        self._update_buttons()

    def _current_id(self) -> str:
        item = self._list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""

    def _current_name(self) -> str:
        item = self._list.currentItem()
        return item.text() if item is not None else ""

    def _update_buttons(self) -> None:
        has_selection = self._list.currentItem() is not None
        for button in (self._btn_duplicate, self._btn_rename, self._btn_delete):
            button.setEnabled(has_selection)

    def _on_activate(self, *_args) -> None:
        share_id = self._current_id()
        if share_id:
            self._host._switch_to_share(share_id)
            self._refresh()

    def _ask_name_and_folder(self, title_key: str) -> tuple[str, str] | None:
        name, ok = QInputDialog.getText(self, tr(title_key), tr("shares.new.name"))
        if not ok or not name.strip():
            return None
        folder = QFileDialog.getExistingDirectory(self, tr("shares.new.folder"))
        if not folder:
            return None
        return name, folder

    def _on_new(self) -> None:
        answer = self._ask_name_and_folder("shares.new.title")
        if answer and self._host._create_share(*answer):
            self._refresh()

    def _on_duplicate(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        answer = self._ask_name_and_folder("shares.duplicate.title")
        if answer and self._host._duplicate_share(share_id, *answer):
            self._refresh()

    def _on_rename(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        name, ok = QInputDialog.getText(
            self, tr("shares.rename.title"), tr("shares.new.name"), text=self._current_name()
        )
        if ok and self._host._rename_share(share_id, name):
            self._refresh()

    def _on_delete(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("shares.delete.title"))
        box.setText(tr("shares.delete.message").format(name=self._current_name()))
        clear = QCheckBox(tr("shares.delete.clear_state"), box)
        clear.setChecked(True)
        box.setCheckBox(clear)
        delete = box.addButton(tr("shares.manage.delete"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not delete:
            return
        if self._host._delete_share(share_id, clear.isChecked()):
            self._refresh()

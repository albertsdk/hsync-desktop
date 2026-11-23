# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""SharesDialog: the "manage shares" list (new/duplicate/rename/delete).

The dialog is a thin view: every mutation is delegated to the window
(``SharesMixin``), which owns the store, the engine and the switch flow.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from hsync_desktop.docs_links import SHARES
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon
from hsync_desktop.widgets.dialogs import build_destructive_confirm_box
from hsync_desktop.widgets.links import insert_help_link_above
from hsync_desktop.widgets.name_dialog import ask_name


class SharesDialog(QDialog):
    def __init__(self, host, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._host = host
        # (button, label) of the action whose server check is running, if any.
        self._busy_source: tuple[QPushButton, str] | None = None
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
        # The labels carry no ellipsis unlike the header menu: a row of four
        # trailing "…" reads as noise, and the icon already says the click opens
        # a dialog (the HIG reserves the ellipsis for menus).
        self._btn_new = QPushButton(icon("list-add"), tr("shares.manage.new"), self)
        self._btn_duplicate = QPushButton(icon("edit-copy"), tr("shares.manage.duplicate"), self)
        self._btn_rename = QPushButton(icon("edit-rename"), tr("shares.manage.rename"), self)
        self._btn_delete = QPushButton(icon("edit-delete"), tr("shares.manage.delete"), self)
        for button in (self._btn_new, self._btn_duplicate, self._btn_rename, self._btn_delete):
            row.addWidget(button)
        layout.addLayout(row)

        buttons = QDialogButtonBox(self)
        close = buttons.addButton(tr("action.close"), QDialogButtonBox.ButtonRole.RejectRole)
        close.setIcon(icon("window-close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        insert_help_link_above(buttons, "help.open_guide", SHARES)

        self._btn_new.clicked.connect(self._on_new)
        self._btn_duplicate.clicked.connect(self._on_duplicate)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_delete.clicked.connect(self._on_delete)

    def _refresh(self, select_id: str = "") -> None:
        """Rebuild the list and make *select_id* (default: the active share) current.

        ``setSelected`` alone leaves ``currentItem`` unset, and Qt then makes the
        first row current as soon as the list takes focus: the highlight says one
        share while every action reads another. ``setCurrentItem`` sets both.
        """
        store = self._host._share_store
        target = select_id or store.active_id()
        self._list.clear()
        current: QListWidgetItem | None = None
        for share in store.shares_sorted():
            item = QListWidgetItem(share.name or tr("shares.untitled"), self._list)
            item.setData(Qt.ItemDataRole.UserRole, share.id)
            p2p = bool(share.values.get("p2p/enabled", True))
            item.setIcon(icon("network-p2p" if p2p else "network-cloud"))
            if share.id == target:
                current = item
        if current is None and self._list.count():
            current = self._list.item(0)
        if current is not None:
            self._list.setCurrentItem(current)
        self._update_buttons()

    def _current_item(self) -> QListWidgetItem | None:
        """The row the user sees selected, falling back to the current one."""
        selected = self._list.selectedItems()
        return selected[0] if selected else self._list.currentItem()

    def _current_id(self) -> str:
        item = self._current_item()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""

    def _current_name(self) -> str:
        item = self._current_item()
        return item.text() if item is not None else ""

    def _neighbour_id(self, share_id: str) -> str:
        """The row that takes *share_id*'s place once it is deleted."""
        ids = [
            str(self._list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self._list.count())
        ]
        if share_id not in ids:
            return ""
        index = ids.index(share_id)
        if index + 1 < len(ids):
            return ids[index + 1]
        return ids[index - 1] if index > 0 else ""

    def _update_buttons(self) -> None:
        has_selection = self._current_item() is not None
        for button in (self._btn_duplicate, self._btn_rename, self._btn_delete):
            button.setEnabled(has_selection)

    def _on_activate(self, *_args) -> None:
        share_id = self._current_id()
        if share_id:
            self._host._switch_to_share(share_id)
            self._refresh()

    def _ask_name_and_folder(self, title_key: str, accept_key: str) -> tuple[str, str] | None:
        name = ask_name(
            self,
            title=tr(title_key),
            label=tr("shares.new.name"),
            accept_text_key=accept_key,
        )
        if not name:
            return None
        folder = QFileDialog.getExistingDirectory(self, tr("shares.new.folder"))
        if not folder:
            return None
        return name, folder

    def _on_new(self) -> None:
        answer = self._ask_name_and_folder("shares.new.title", "shares.manage.new")
        if not answer:
            return
        self._set_pending(True, source=self._btn_new)
        if not self._host._create_share(*answer, on_done=self._after_creation):
            self._set_pending(False)

    def _on_duplicate(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        answer = self._ask_name_and_folder("shares.duplicate.title", "shares.manage.duplicate")
        if not answer:
            return
        self._set_pending(True, source=self._btn_duplicate)
        if not self._host._duplicate_share(share_id, *answer, on_done=self._after_creation):
            self._set_pending(False)

    def _set_pending(self, busy: bool, *, source: QPushButton | None = None) -> None:
        """Report a creation waiting for the server, like the Settings dialog does.

        A server-mode share is written only after the bucket check answers, so the
        actions are held (a second click would start a second check) and the button
        that started it reads ``common.checking`` until the outcome arrives.
        """
        for button in (self._btn_new, self._btn_duplicate, self._btn_rename, self._btn_delete):
            button.setEnabled(not busy)
        if busy:
            if source is not None:
                self._busy_source = (source, source.text())
                source.setText(tr("common.checking"))
            return
        if self._busy_source is not None:
            button, label = self._busy_source
            button.setText(label)
            self._busy_source = None
        self._update_buttons()

    def _after_creation(self, created: bool) -> None:
        """Refresh the list: the host may finish the creation after a server check."""
        self._set_pending(False)
        if created:
            self._refresh()

    def _on_rename(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        name = ask_name(
            self,
            title=tr("shares.rename.title"),
            label=tr("shares.new.name"),
            accept_text_key="shares.manage.rename",
            initial=self._current_name(),
        )
        if name and self._host._rename_share(share_id, name):
            self._refresh()

    def _on_delete(self) -> None:
        share_id = self._current_id()
        if not share_id:
            return
        neighbour = self._neighbour_id(share_id)
        box, delete, clear = build_destructive_confirm_box(
            self,
            title=tr("shares.delete.title"),
            text=tr("shares.delete.message").format(name=self._current_name()),
            accept_text=tr("shares.manage.delete"),
            checkbox_text=tr("shares.delete.clear_state"),
        )
        box.exec()
        if box.clickedButton() is not delete:
            return
        if self._host._delete_share(share_id, bool(clear and clear.isChecked()), neighbour):
            self._refresh(select_id=neighbour)

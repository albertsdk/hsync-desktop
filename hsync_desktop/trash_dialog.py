# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The trash view: restore or empty the files this device deleted (ADR-0056).

The store is client-owned, so the dialog is a thin view: listing, restore and
empty go through ``hsync trash ...`` (``hsync_desktop/engine/cli.py``) and the
dialog only renders the outcome. Both commands take no folder lock, so the view
works while a sync runs.

Consumers: ``hsync_desktop/main_window/actions.py::ActionsMixin._show_trash_dialog``.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from hsync_common.format import format_bytes
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.engine import TrashActionResult, TrashListResult
from hsync_desktop.i18n import tr
from hsync_desktop.widgets.labels import muted_label

__all__ = ["TrashDialog"]

# Row role holding whether the entry's bytes are still in the store (UserRole
# carries the path the client expects back on restore).
_RESTORABLE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def _deleted_label(stamp: int) -> str:
    """Render a deletion timestamp in the host's locale format."""
    if stamp <= 0:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp))
    except (OSError, ValueError, OverflowError):
        return ""


class TrashDialog(QDialog):
    """List the restorable files, with restore and empty.

    The three collaborators are injected so the dialog is testable without a
    subprocess: *load* returns the listing, *restore* takes one path and *empty*
    clears the store. A refusal is surfaced with the client's own wording.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        load: Callable[[], TrashListResult],
        restore: Callable[[str], TrashActionResult],
        empty: Callable[[], TrashActionResult],
    ) -> None:
        super().__init__(parent)
        self._load = load
        self._restore = restore
        self._empty = empty

        self.setWindowTitle(tr("trash.title"))
        self.resize(640, 420)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._lbl_hint = muted_label()
        layout.addWidget(self._lbl_hint)

        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(
            [tr("trash.col.path"), tr("trash.col.deleted"), tr("trash.col.size")]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._sync_buttons)
        layout.addWidget(self._table, 1)

        self._lbl_status = QLabel("", self)
        self._lbl_status.setWordWrap(True)
        layout.addWidget(self._lbl_status)

        row = QHBoxLayout()
        self._btn_restore = QPushButton(tr("trash.restore"), self)
        self._btn_restore.clicked.connect(self._on_restore)
        self._btn_empty = QPushButton(tr("trash.empty"), self)
        self._btn_empty.clicked.connect(self._on_empty)
        row.addWidget(self._btn_restore)
        row.addWidget(self._btn_empty)
        row.addStretch(1)
        layout.addLayout(row)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_button = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        close_button.setText(tr("action.close"))
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # ── data ──────────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Refresh the listing from the client's store."""
        result = self._load()
        self._table.setRowCount(0)
        if not result.ok:
            self._lbl_hint.setText(tr("trash.list_failed"))
            self._lbl_status.setText(result.message)
            self._sync_buttons()
            return
        self._lbl_hint.setText(tr("trash.empty_state") if not result.entries else tr("trash.hint"))
        for entry in result.entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            # The store can keep a record whose bytes are gone (a crash or a
            # hand-edit): say so on the row and make it unselectable for restore.
            label = (
                entry.path
                if entry.payload_present
                else f"{entry.path}  ({tr('trash.not_restorable')})"
            )
            path_item = QTableWidgetItem(label)
            path_item.setData(Qt.ItemDataRole.UserRole, entry.path)
            path_item.setData(_RESTORABLE_ROLE, entry.payload_present)
            if not entry.payload_present:
                path_item.setToolTip(tr("trash.not_restorable_tip"))
            self._table.setItem(row, 0, path_item)
            self._table.setItem(row, 1, QTableWidgetItem(_deleted_label(entry.deleted_at)))
            size_item = QTableWidgetItem(format_bytes(entry.size))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 2, size_item)
        self._lbl_status.setText("")
        self._sync_buttons()

    def selected_path(self) -> str:
        """Path of the selected row, or ``""`` when nothing is selected."""
        model = self._table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        if not rows:
            return ""
        item = self._table.item(rows[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def _sync_buttons(self) -> None:
        self._btn_restore.setEnabled(self._selected_restorable())
        self._btn_empty.setEnabled(self._table.rowCount() > 0)

    def _selected_restorable(self) -> bool:
        """True when a row is selected and its bytes are still in the store."""
        model = self._table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        if not rows:
            return False
        item = self._table.item(rows[0].row(), 0)
        return bool(item.data(_RESTORABLE_ROLE)) if item is not None else False

    # ── actions ───────────────────────────────────────────────────────────

    def _on_restore(self) -> None:
        path = self.selected_path()
        if not path:
            return
        result = self._restore(path)
        if result.ok:
            # Reload first: it clears the status line.
            self.reload()
            self._lbl_status.setText(tr("trash.restored").format(path=path))
            return
        QMessageBox.warning(
            self,
            tr("notif.error"),
            result.message or tr("trash.restore_failed").format(path=path),
        )

    def _on_empty(self) -> None:
        if self._table.rowCount() == 0:
            return
        answer = QMessageBox.question(
            self,
            tr("trash.confirm_empty_title"),
            tr("trash.confirm_empty"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = self._empty()
        if not result.ok:
            QMessageBox.warning(self, tr("notif.error"), result.message or tr("trash.list_failed"))
            return
        self.reload()
        self._lbl_status.setText(result.message or tr("trash.empty_done"))

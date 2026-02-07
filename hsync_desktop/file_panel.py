# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
File transfer panel for HSYNC Desktop.

Shows real-time file transfers in a sortable table with:
- Direction icon (download/upload)
- Path and filename in separate columns
- Size, remaining, ETA, status
- Queued files shown in gray
- Collapsible detail panel on row click
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import time
from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr


class TransferStatus(Enum):
    """Status of a file transfer."""
    QUEUED = "queued"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class FileTransfer:
    """Represents a file transfer (download or upload)."""
    filepath: str
    direction: str  # "↓" or "↑"
    size: int = 0
    bytes_transferred: int = 0
    start_time: float = field(default_factory=time)
    status: TransferStatus = TransferStatus.QUEUED
    client_cid: str = ""
    client_ip: str = ""

    @property
    def filename(self) -> str:
        return Path(self.filepath).name

    @property
    def path(self) -> str:
        parent = Path(self.filepath).parent
        return str(parent) if str(parent) != "." else ""

    @property
    def remaining(self) -> int:
        return max(0, self.size - self.bytes_transferred)

    @property
    def eta_seconds(self) -> Optional[float]:
        if self.status != TransferStatus.TRANSFERRING or self.bytes_transferred == 0:
            return None
        elapsed = time() - self.start_time
        if elapsed <= 0:
            return None
        rate = self.bytes_transferred / elapsed
        if rate <= 0:
            return None
        return self.remaining / rate


def _format_size(n: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _format_eta(seconds: Optional[float]) -> str:
    """Format ETA as human-readable string."""
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


# Column indices
COL_DIRECTION = 0
COL_PATH = 1
COL_NAME = 2
COL_SIZE = 3
COL_REMAINING = 4
COL_ETA = 5
COL_STATUS = 6


class FileDetailPanel(QFrame):
    """Collapsible panel showing detailed file information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        self._build_ui()
        self.hide()  # Hidden by default

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QLabel(tr("detail.title"))
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Form layout for details
        form = QFormLayout()
        form.setSpacing(8)

        self._lbl_filepath = QLabel("—")
        self._lbl_filepath.setWordWrap(True)
        form.addRow(tr("detail.filepath"), self._lbl_filepath)

        self._lbl_filename = QLabel("—")
        form.addRow(tr("detail.filename"), self._lbl_filename)

        self._lbl_size = QLabel("—")
        form.addRow(tr("detail.size"), self._lbl_size)

        self._lbl_direction = QLabel("—")
        form.addRow(tr("detail.direction"), self._lbl_direction)

        self._lbl_status = QLabel("—")
        form.addRow(tr("detail.status"), self._lbl_status)

        # Client info section
        self._lbl_cid = QLabel("—")
        form.addRow(tr("detail.client_cid"), self._lbl_cid)

        self._lbl_ip = QLabel("—")
        form.addRow(tr("detail.client_ip"), self._lbl_ip)

        layout.addLayout(form)
        layout.addStretch()

    def show_transfer(self, transfer: FileTransfer) -> None:
        """Display details for the given transfer."""
        self._lbl_filepath.setText(transfer.filepath)
        self._lbl_filename.setText(transfer.filename)
        self._lbl_size.setText(_format_size(transfer.size) if transfer.size else "—")

        dir_key = "detail.download" if transfer.direction == "↓" else "detail.upload"
        self._lbl_direction.setText(f"{transfer.direction} {tr(dir_key)}")

        status_map = {
            TransferStatus.QUEUED: "detail.pending",
            TransferStatus.TRANSFERRING: "detail.transferring",
            TransferStatus.COMPLETED: "detail.completed",
            TransferStatus.ERROR: "status.error",
        }
        self._lbl_status.setText(tr(status_map.get(transfer.status, "status.unknown")))

        self._lbl_cid.setText(transfer.client_cid or "—")
        self._lbl_ip.setText(transfer.client_ip or "—")
        self.show()

    def clear(self) -> None:
        """Clear and hide the panel."""
        self.hide()


class FileTransferTable(QTableWidget):
    """Sortable table showing file transfers."""

    row_selected = Signal(object)  # Emits FileTransfer or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transfers: Dict[str, FileTransfer] = {}  # filepath -> transfer
        self._setup_table()

    def _setup_table(self) -> None:
        headers = [
            tr("file.direction"),
            tr("file.path"),
            tr("file.name"),
            tr("file.size"),
            tr("file.remaining"),
            tr("file.eta"),
            tr("file.status"),
        ]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)

        # Column sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_DIRECTION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_REMAINING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ETA, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self) -> None:
        rows = self.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            filepath_item = self.item(row, COL_PATH)
            name_item = self.item(row, COL_NAME)
            if filepath_item and name_item:
                path = filepath_item.text()
                name = name_item.text()
                full_path = f"{path}/{name}" if path else name
                transfer = self._transfers.get(full_path)
                self.row_selected.emit(transfer)
        else:
            self.row_selected.emit(None)

    def add_transfer(self, transfer: FileTransfer) -> None:
        """Add or update a transfer in the table."""
        self._transfers[transfer.filepath] = transfer
        self._refresh_row(transfer)

    def update_transfer_status(self, filepath: str, status: TransferStatus) -> None:
        """Update the status of a transfer."""
        if filepath in self._transfers:
            self._transfers[filepath].status = status
            self._refresh_row(self._transfers[filepath])

    def mark_completed(self, filepath: str, size: int = 0, direction: str = "↓") -> None:
        """Mark a transfer as completed, creating it if it doesn't exist."""
        if filepath in self._transfers:
            t = self._transfers[filepath]
            t.status = TransferStatus.COMPLETED
            if size:
                t.size = size
                t.bytes_transferred = size
        else:
            # Create a new transfer entry for the completed file
            t = FileTransfer(
                filepath=filepath,
                direction=direction,
                size=size,
                bytes_transferred=size,
                status=TransferStatus.COMPLETED,
            )
            self._transfers[filepath] = t
        self._refresh_row(t)

    def clear_transfers(self) -> None:
        """Clear all transfers from the table."""
        self._transfers.clear()
        self.setRowCount(0)

    def _refresh_row(self, transfer: FileTransfer) -> None:
        """Refresh or create a row for the given transfer."""
        # Find existing row
        row = -1
        for r in range(self.rowCount()):
            path_item = self.item(r, COL_PATH)
            name_item = self.item(r, COL_NAME)
            if path_item and name_item:
                full = f"{path_item.text()}/{name_item.text()}" if path_item.text() else name_item.text()
                if full == transfer.filepath:
                    row = r
                    break

        if row < 0:
            row = self.rowCount()
            self.insertRow(row)

        # Direction with color
        dir_item = QTableWidgetItem(transfer.direction)
        dir_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        color = QColor("#00bcd4") if transfer.direction == "↓" else QColor("#4caf50")
        dir_item.setForeground(color)
        self.setItem(row, COL_DIRECTION, dir_item)

        # Path and name
        self.setItem(row, COL_PATH, QTableWidgetItem(transfer.path))
        self.setItem(row, COL_NAME, QTableWidgetItem(transfer.filename))

        # Size
        size_text = _format_size(transfer.size) if transfer.size else "—"
        self.setItem(row, COL_SIZE, QTableWidgetItem(size_text))

        # Remaining
        if transfer.status == TransferStatus.COMPLETED:
            remain_text = "—"
        elif transfer.remaining > 0:
            remain_text = _format_size(transfer.remaining)
        else:
            remain_text = "—"
        self.setItem(row, COL_REMAINING, QTableWidgetItem(remain_text))

        # ETA
        self.setItem(row, COL_ETA, QTableWidgetItem(_format_eta(transfer.eta_seconds)))

        # Status
        status_map = {
            TransferStatus.QUEUED: tr("detail.pending"),
            TransferStatus.TRANSFERRING: tr("detail.transferring"),
            TransferStatus.COMPLETED: tr("detail.completed"),
            TransferStatus.ERROR: tr("status.error"),
        }
        self.setItem(row, COL_STATUS, QTableWidgetItem(status_map.get(transfer.status, "?")))

        # Gray text for queued items
        if transfer.status == TransferStatus.QUEUED:
            gray = QColor(128, 128, 128)
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setForeground(gray)


class FilePanel(QWidget):
    """
    Complete file transfer panel with table and collapsible detail panel.

    Contains:
    - Sortable file transfer table (left)
    - Collapsible detail panel (right, shown on row click)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter for table + detail panel
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # File table
        self._table = FileTransferTable()
        self._splitter.addWidget(self._table)

        # Detail panel (collapsible)
        self._detail = FileDetailPanel()
        self._splitter.addWidget(self._detail)

        # Set initial sizes (table takes most space)
        self._splitter.setSizes([800, 0])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        layout.addWidget(self._splitter)

    def _connect_signals(self) -> None:
        self._table.row_selected.connect(self._on_row_selected)

    @Slot(object)
    def _on_row_selected(self, transfer: FileTransfer | None) -> None:
        if transfer:
            self._detail.show_transfer(transfer)
            # Show detail panel if hidden
            sizes = self._splitter.sizes()
            if sizes[1] == 0:
                self._splitter.setSizes([600, 250])
        else:
            self._detail.clear()

    # ── Public API ────────────────────────────────────────────────────────

    def add_transfer(self, filepath: str, direction: str, size: int = 0) -> None:
        """Add a new transfer to the panel."""
        transfer = FileTransfer(
            filepath=filepath,
            direction=direction,
            size=size,
            status=TransferStatus.QUEUED,
        )
        self._table.add_transfer(transfer)

    def start_transfer(self, filepath: str) -> None:
        """Mark a transfer as started (transferring)."""
        self._table.update_transfer_status(filepath, TransferStatus.TRANSFERRING)

    def complete_transfer(self, filepath: str, size: int = 0, direction: str = "↓") -> None:
        """Mark a transfer as completed."""
        self._table.mark_completed(filepath, size, direction)

    def clear(self) -> None:
        """Clear all transfers."""
        self._table.clear_transfers()
        self._detail.clear()

    @property
    def table(self) -> FileTransferTable:
        """Access the underlying table widget."""
        return self._table


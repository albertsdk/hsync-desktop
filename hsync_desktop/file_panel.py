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

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import time
from typing import Dict, Optional

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr


class TransferStatus(Enum):
    """Status of a file transfer."""
    LOCAL = "local"              # File exists locally, status unknown
    SYNCED = "synced"            # File is in sync (no action needed)
    TO_DOWNLOAD = "to_download"  # File needs to be downloaded
    TO_UPLOAD = "to_upload"      # File needs to be uploaded
    TO_DELETE = "to_delete"      # File will be deleted
    DOWNLOADING = "downloading"  # File is being downloaded
    UPLOADING = "uploading"      # File is being uploaded
    DELETED = "deleted"          # File was deleted (shown briefly before removal)
    QUEUED = "queued"            # Legacy: file is queued for transfer
    TRANSFERRING = "transferring"  # Legacy: file is being transferred
    COMPLETED = "completed"      # File transfer completed
    ERROR = "error"


# Status colors for the file table
STATUS_COLORS = {
    TransferStatus.LOCAL: QColor(128, 128, 128),       # Gray
    TransferStatus.SYNCED: QColor(76, 175, 80),        # Green (#4caf50)
    TransferStatus.TO_DOWNLOAD: QColor(0, 188, 212),   # Cyan (#00bcd4)
    TransferStatus.TO_UPLOAD: QColor(255, 152, 0),     # Orange (#ff9800)
    TransferStatus.TO_DELETE: QColor(244, 67, 54),     # Red (#f44336)
    TransferStatus.DOWNLOADING: QColor(33, 150, 243),  # Blue (#2196f3)
    TransferStatus.UPLOADING: QColor(255, 193, 7),     # Amber (#ffc107)
    TransferStatus.DELETED: QColor(244, 67, 54),       # Red (#f44336)
    TransferStatus.QUEUED: QColor(128, 128, 128),      # Gray
    TransferStatus.TRANSFERRING: QColor(33, 150, 243), # Blue (#2196f3)
    TransferStatus.COMPLETED: QColor(76, 175, 80),     # Green (#4caf50)
    TransferStatus.ERROR: QColor(244, 67, 54),         # Red (#f44336)
}


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


# Column indices and translation keys
COL_DIRECTION = 0
COL_PATH = 1
COL_NAME = 2
COL_SIZE = 3
COL_REMAINING = 4
COL_ETA = 5
COL_STATUS = 6

# Column translation keys (in order)
_COLUMN_KEYS = [
    "file.direction",
    "file.path",
    "file.name",
    "file.size",
    "file.remaining",
    "file.eta",
    "file.status",
]

# Batch size for async file loading
_FILE_BATCH_SIZE = 50


class DirectoryScanWorker(QObject):
    """Worker that scans a directory in a background thread."""

    # Emits a batch of (filepath, size) tuples
    files_found = Signal(list)
    # Emits (processed_count, total_count) for progress
    progress = Signal(int, int)
    # Emitted when scan is complete
    finished = Signal()

    def __init__(self, directory: str) -> None:
        super().__init__()
        self._directory = directory
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the scan."""
        self._cancelled = True

    def _count_files(self) -> int:
        """Quick count of files (without reading sizes)."""
        count = 0
        for root, dirs, files in os.walk(self._directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if self._cancelled:
                return 0
            for f in files:
                if not f.startswith("."):
                    count += 1
        return count

    @Slot()
    def run(self) -> None:
        """Scan the directory and emit files in batches."""
        if not self._directory or not os.path.isdir(self._directory):
            self.finished.emit()
            return

        # First pass: count files for progress
        total = self._count_files()
        if self._cancelled or total == 0:
            self.finished.emit()
            return

        self.progress.emit(0, total)

        base_path = Path(self._directory)
        batch: list[tuple[str, int]] = []
        processed = 0

        for root, dirs, files in os.walk(self._directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            if self._cancelled:
                break

            for filename in files:
                if self._cancelled:
                    break

                # Skip hidden files
                if filename.startswith("."):
                    continue

                full_path = Path(root) / filename
                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = 0

                # Get relative path from base directory
                try:
                    rel_path = str(full_path.relative_to(base_path))
                except ValueError:
                    rel_path = str(full_path)

                batch.append((rel_path, size))
                processed += 1

                # Emit batch when full
                if len(batch) >= _FILE_BATCH_SIZE:
                    self.files_found.emit(batch)
                    self.progress.emit(processed, total)
                    batch = []

        # Emit remaining files
        if batch and not self._cancelled:
            self.files_found.emit(batch)
            self.progress.emit(processed, total)

        self.finished.emit()


class LoadingOverlay(QWidget):
    """Semi-transparent overlay with progress indicator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(True)

        # Semi-transparent background
        palette = self.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        bg_color.setAlpha(200)
        palette.setColor(palette.ColorRole.Window, bg_color)
        self.setPalette(palette)

        # Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container for centered content
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.setSpacing(10)

        # Loading label
        self._label = QLabel(tr("loading.files"))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._label.font()
        font.setPointSize(12)
        self._label.setFont(font)
        container_layout.addWidget(self._label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._progress.setMinimumWidth(250)
        self._progress.setMaximumWidth(350)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p% (%v / %m)")
        container_layout.addWidget(self._progress)

        layout.addWidget(container)
        self.hide()

    def set_progress(self, current: int, total: int) -> None:
        """Update progress bar."""
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        # Update label with count
        self._label.setText(f"{tr('loading.files')} ({current}/{total})")

    def show_loading(self) -> None:
        """Show the overlay."""
        self._progress.setValue(0)
        self._label.setText(tr("loading.files"))
        self.show()
        self.raise_()

    def hide_loading(self) -> None:
        """Hide the overlay."""
        self.hide()


class FileDetailPanel(QFrame):
    """Collapsible panel showing detailed file information."""

    close_requested = Signal()  # Emitted when close button is clicked

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

        # Header with title and close button
        header = QHBoxLayout()
        title = QLabel(tr("detail.title"))
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()

        # Close button with standard icon
        close_btn = QToolButton()
        close_btn.setAutoRaise(True)
        style = self.style()
        if style:
            close_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setToolTip(tr("action.close"))
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)

        layout.addLayout(header)

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
            TransferStatus.LOCAL: "detail.local",
            TransferStatus.SYNCED: "detail.synced",
            TransferStatus.TO_DOWNLOAD: "detail.to_download",
            TransferStatus.TO_UPLOAD: "detail.to_upload",
            TransferStatus.TO_DELETE: "detail.to_delete",
            TransferStatus.DOWNLOADING: "detail.downloading",
            TransferStatus.UPLOADING: "detail.uploading",
            TransferStatus.DELETED: "detail.deleted",
            TransferStatus.QUEUED: "detail.pending",
            TransferStatus.TRANSFERRING: "detail.transferring",
            TransferStatus.COMPLETED: "detail.completed",
            TransferStatus.ERROR: "status.error",
        }
        self._lbl_status.setText(tr(status_map.get(transfer.status, "status.unknown")))

        self._lbl_cid.setText(transfer.client_cid or "—")
        self._lbl_ip.setText(transfer.client_ip or "—")
        self.show()

    def _on_close(self) -> None:
        """Handle close button click."""
        self.close_requested.emit()

    def clear(self) -> None:
        """Clear and hide the panel."""
        self.hide()


class FileTransferTable(QTableWidget):
    """Sortable table showing file transfers."""

    row_selected = Signal(object)  # Emits FileTransfer or None
    row_deselected = Signal()      # Emitted when clicking on already selected row

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transfers: Dict[str, FileTransfer] = {}  # filepath -> transfer
        self._row_index: Dict[str, int] = {}  # filepath -> row index for fast lookup
        self._last_selected_row: int = -1
        self._setup_table()

    def _setup_table(self) -> None:
        headers = [tr(key) for key in _COLUMN_KEYS]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)

        # Column sizing and behavior
        header = self.horizontalHeader()
        header.setSectionsMovable(True)  # Allow drag-and-drop column reordering
        header.setSectionResizeMode(COL_DIRECTION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_REMAINING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ETA, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)

        # Enable context menu on header for column visibility
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.cellClicked.connect(self._on_cell_clicked)

    def _show_header_context_menu(self, pos) -> None:
        """Show context menu to toggle column visibility."""
        menu = QMenu(self)
        header = self.horizontalHeader()

        for col, key in enumerate(_COLUMN_KEYS):
            action = QAction(tr(key), menu)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(col))
            # Use default argument to capture col value
            action.toggled.connect(lambda checked, c=col: self._toggle_column(c, checked))
            menu.addAction(action)

        menu.exec(header.mapToGlobal(pos))

    def _toggle_column(self, col: int, visible: bool) -> None:
        """Toggle visibility of a column."""
        self.horizontalHeader().setSectionHidden(col, not visible)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        """Handle cell click to detect re-click on same row."""
        if row == self._last_selected_row:
            # Clicking on already selected row - deselect and hide panel
            self._last_selected_row = -1
            self.clearSelection()
            self.row_deselected.emit()
        else:
            # Clicking on a different row - update tracking
            self._last_selected_row = row

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
        self._row_index.clear()
        self.setRowCount(0)

    def add_transfers_batch(self, transfers: list[FileTransfer]) -> None:
        """Add multiple transfers efficiently with UI updates disabled."""
        if not transfers:
            return

        self.setUpdatesEnabled(False)
        self.setSortingEnabled(False)
        try:
            for transfer in transfers:
                self._transfers[transfer.filepath] = transfer
                self._add_row_fast(transfer)
        finally:
            self.setSortingEnabled(True)
            self.setUpdatesEnabled(True)

    def _add_row_fast(self, transfer: FileTransfer) -> None:
        """Add a new row without searching for existing (for batch insert)."""
        row = self.rowCount()
        self.insertRow(row)
        self._row_index[transfer.filepath] = row
        self._populate_row(row, transfer)

    def update_file_status(self, filepath: str, status: str, size: int = 0) -> None:
        """
        Update or add a file with the given status from preview.

        Args:
            filepath: Path of the file
            status: Status string ("synced", "to_download", "to_upload", "to_delete")
            size: File size in bytes
        """
        status_mapping = {
            "synced": TransferStatus.SYNCED,
            "to_download": TransferStatus.TO_DOWNLOAD,
            "to_upload": TransferStatus.TO_UPLOAD,
            "to_delete": TransferStatus.TO_DELETE,
        }
        transfer_status = status_mapping.get(status, TransferStatus.LOCAL)

        # Determine direction based on status
        if status == "to_download":
            direction = "↓"
        elif status == "to_upload":
            direction = "↑"
        elif status == "to_delete":
            direction = "✕"
        else:
            direction = "—"

        if filepath in self._transfers:
            # Update existing transfer
            t = self._transfers[filepath]
            t.status = transfer_status
            t.direction = direction
            if size:
                t.size = size
        else:
            # Create new transfer entry
            t = FileTransfer(
                filepath=filepath,
                direction=direction,
                size=size,
                status=transfer_status,
            )
            self._transfers[filepath] = t
        self._refresh_row(t)

    def mark_deleted(self, filepath: str) -> None:
        """
        Mark a file as deleted and schedule its removal from the table.

        The row will be shown with DELETED status for 3 seconds before being removed.
        """
        if filepath in self._transfers:
            t = self._transfers[filepath]
            t.status = TransferStatus.DELETED
            t.direction = "✕"
            self._refresh_row(t)
            # Schedule removal after 3 seconds
            QTimer.singleShot(3000, lambda: self._remove_file(filepath))

    def _remove_file(self, filepath: str) -> None:
        """Remove a file from the table."""
        if filepath not in self._transfers:
            return

        row = self._row_index.get(filepath, -1)
        if row >= 0:
            self.removeRow(row)
            # Update indices for rows after the removed one
            del self._row_index[filepath]
            for path, r in self._row_index.items():
                if r > row:
                    self._row_index[path] = r - 1

        # Remove from internal dict
        del self._transfers[filepath]

    def remove_transfer(self, filepath: str) -> None:
        """Remove a transfer from the table immediately."""
        self._remove_file(filepath)

    def _refresh_row(self, transfer: FileTransfer) -> None:
        """Refresh or create a row for the given transfer."""
        # Use index for fast lookup
        row = self._row_index.get(transfer.filepath, -1)

        if row < 0:
            row = self.rowCount()
            self.insertRow(row)
            self._row_index[transfer.filepath] = row

        self._populate_row(row, transfer)

    def _populate_row(self, row: int, transfer: FileTransfer) -> None:
        """Populate a row with transfer data."""
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
            TransferStatus.LOCAL: tr("detail.local"),
            TransferStatus.SYNCED: tr("detail.synced"),
            TransferStatus.TO_DOWNLOAD: tr("detail.to_download"),
            TransferStatus.TO_UPLOAD: tr("detail.to_upload"),
            TransferStatus.TO_DELETE: tr("detail.to_delete"),
            TransferStatus.DOWNLOADING: tr("detail.downloading"),
            TransferStatus.UPLOADING: tr("detail.uploading"),
            TransferStatus.DELETED: tr("detail.deleted"),
            TransferStatus.QUEUED: tr("detail.pending"),
            TransferStatus.TRANSFERRING: tr("detail.transferring"),
            TransferStatus.COMPLETED: tr("detail.completed"),
            TransferStatus.ERROR: tr("status.error"),
        }
        self.setItem(row, COL_STATUS, QTableWidgetItem(status_map.get(transfer.status, "?")))

        # Apply status color to all cells in the row
        color = STATUS_COLORS.get(transfer.status, QColor(128, 128, 128))
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setForeground(color)


class FilePanel(QWidget):
    """
    Complete file transfer panel with table and collapsible detail panel.

    Contains:
    - Sortable file transfer table (left)
    - Collapsible detail panel (right, shown on row click)
    - Periodic directory consistency check
    """

    # Interval for directory consistency check (in milliseconds)
    CONSISTENCY_CHECK_INTERVAL_MS = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_thread: QThread | None = None
        self._scan_worker: DirectoryScanWorker | None = None
        self._current_directory: str = ""
        # Timer for periodic directory consistency check
        self._consistency_timer = QTimer(self)
        self._consistency_timer.timeout.connect(self._check_directory_consistency)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter for table + detail panel
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Container for table + overlay
        self._table_container = QWidget()
        table_layout = QVBoxLayout(self._table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # File table
        self._table = FileTransferTable()
        table_layout.addWidget(self._table)

        # Loading overlay (positioned over table)
        self._loading_overlay = LoadingOverlay(self._table_container)

        # Install event filter to resize overlay when container resizes
        self._table_container.installEventFilter(self)

        self._splitter.addWidget(self._table_container)

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
        self._table.row_deselected.connect(self._hide_detail_panel)
        self._detail.close_requested.connect(self._hide_detail_panel)

    @Slot(object)
    def _on_row_selected(self, transfer: FileTransfer | None) -> None:
        if transfer:
            self._detail.show_transfer(transfer)
            # Show detail panel if hidden
            sizes = self._splitter.sizes()
            if sizes[1] == 0:
                self._splitter.setSizes([600, 250])

    @Slot()
    def _hide_detail_panel(self) -> None:
        """Hide the detail panel and clear selection."""
        self._detail.clear()
        self._splitter.setSizes([800, 0])
        self._table.clearSelection()
        self._table._last_selected_row = -1

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
        """Clear all transfers and stop any ongoing scan."""
        self._consistency_timer.stop()
        self._stop_scan()
        self._table.clear_transfers()
        self._detail.clear()

    def load_local_files(self, directory: str) -> None:
        """Load all files from a local directory into the table.

        Recursively scans the directory in a background thread and adds
        files with LOCAL status in batches to avoid blocking the UI.

        Args:
            directory: Path to the local directory to scan.
        """
        # Cancel any ongoing scan and stop consistency timer
        self._stop_scan()
        self._consistency_timer.stop()
        self.clear()

        if not directory or not os.path.isdir(directory):
            self._current_directory = ""
            return

        # Save current directory for consistency checks
        self._current_directory = directory

        # Show loading overlay
        self._show_loading()

        # Create worker and thread
        self._scan_thread = QThread()
        self._scan_worker = DirectoryScanWorker(directory)
        self._scan_worker.moveToThread(self._scan_thread)

        # Connect signals
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.files_found.connect(self._on_files_found)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)

        # Start scanning
        self._scan_thread.start()

    def _stop_scan(self) -> None:
        """Stop any ongoing directory scan."""
        self._hide_loading()
        if self._scan_worker:
            self._scan_worker.cancel()
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(1000)  # Wait up to 1 second
        self._scan_thread = None
        self._scan_worker = None

    @Slot(list)
    def _on_files_found(self, files: list[tuple[str, int]]) -> None:
        """Handle a batch of files from the scanner."""
        transfers = [
            FileTransfer(
                filepath=filepath,
                direction="—",  # No direction for local files
                size=size,
                bytes_transferred=0,
                status=TransferStatus.LOCAL,
            )
            for filepath, size in files
        ]
        self._table.add_transfers_batch(transfers)

    @Slot()
    def _on_scan_finished(self) -> None:
        """Handle scan completion."""
        self._hide_loading()
        if self._scan_thread:
            self._scan_thread.quit()
            self._scan_thread.wait()
        self._scan_thread = None
        self._scan_worker = None
        # Start periodic consistency check
        if self._current_directory:
            self._consistency_timer.start(self.CONSISTENCY_CHECK_INTERVAL_MS)

    @Slot(int, int)
    def _on_scan_progress(self, current: int, total: int) -> None:
        """Update the loading overlay progress."""
        self._loading_overlay.set_progress(current, total)

    def _show_loading(self) -> None:
        """Show the loading overlay."""
        # Resize overlay to match table container
        self._loading_overlay.setGeometry(self._table_container.rect())
        self._loading_overlay.show_loading()

    def _hide_loading(self) -> None:
        """Hide the loading overlay."""
        self._loading_overlay.hide_loading()

    def eventFilter(self, watched: QObject, event) -> bool:
        """Filter events to resize overlay when container resizes."""
        from PySide6.QtCore import QEvent

        if watched == self._table_container and event.type() == QEvent.Type.Resize:
            if self._loading_overlay.isVisible():
                self._loading_overlay.setGeometry(self._table_container.rect())
        return super().eventFilter(watched, event)

    @Slot()
    def _check_directory_consistency(self) -> None:
        """Check if table contents match the actual directory.

        Adds new files and removes deleted files from the table.
        Runs periodically via timer to keep the table in sync with filesystem.
        """
        if not self._current_directory or not os.path.isdir(self._current_directory):
            self._consistency_timer.stop()
            return

        # Get current files in directory (quick scan without sizes for comparison)
        current_files: set[str] = set()
        base_path = Path(self._current_directory)
        try:
            for root, dirs, files in os.walk(self._current_directory):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if f.startswith("."):
                        continue
                    full_path = Path(root) / f
                    try:
                        rel_path = str(full_path.relative_to(base_path))
                        current_files.add(rel_path)
                    except ValueError:
                        pass
        except OSError:
            # Directory may have been deleted or become inaccessible
            return

        # Get files currently in table
        table_files = set(self._table._transfers.keys())

        # Find new files (in directory but not in table)
        new_files = current_files - table_files
        for rel_path in new_files:
            full_path = base_path / rel_path
            try:
                size = full_path.stat().st_size
            except OSError:
                size = 0
            transfer = FileTransfer(
                filepath=rel_path,
                direction="—",
                size=size,
                bytes_transferred=0,
                status=TransferStatus.LOCAL,
            )
            self._table.add_transfer(transfer)

        # Find deleted files (in table but not in directory)
        deleted_files = table_files - current_files
        for rel_path in deleted_files:
            # Only remove if status is LOCAL (not being transferred)
            transfer = self._table._transfers.get(rel_path)
            if transfer and transfer.status == TransferStatus.LOCAL:
                self._table.remove_transfer(rel_path)

    def update_file_status(self, filepath: str, status: str, size: int = 0) -> None:
        """Update or add a file with status from preview."""
        self._table.update_file_status(filepath, status, size)

    def mark_deleted(self, filepath: str) -> None:
        """Mark a file as deleted (will be removed after delay)."""
        self._table.mark_deleted(filepath)

    @property
    def table(self) -> FileTransferTable:
        """Access the underlying table widget."""
        return self._table


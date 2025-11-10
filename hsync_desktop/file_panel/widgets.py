# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Qt widgets for file panel.

Contains custom delegates, loading overlay, detail panel, transfer table, and main file panel.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from hsync_common.format import format_bytes, format_duration
from PySide6.QtCore import (
    QLocale,
    QMutex,
    QMutexLocker,
    QObject,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.file_panel.models import (
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
    FileTransfer,
    TransferStatus,
)
from hsync_desktop.file_panel.utils import (
    _COLUMN_KEYS,
    COL_ETA,
    COL_ICON,
    COL_MODIFIED,
    COL_NAME,
    COL_PROGRESS,
    COL_SIZE,
    COL_STATUS,
    COL_TYPE,
    _classify_file,
    format_mtime,
)
from hsync_desktop.file_panel.workers import DirectoryScanWorker
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.icons import icon as get_icon
from hsync_desktop.ui.loader import load_ui_widget

# ── Custom Delegates ───────────────────────────────────────────────────────


class ProgressBarDelegate(QStyledItemDelegate):
    """Custom delegate that renders a progress bar with centered percentage."""

    def paint(self, painter, option, index):
        progress = index.data(Qt.ItemDataRole.UserRole)
        if progress is None or progress < 0:
            return  # Nothing to paint

        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = progress
        opt.text = f"{progress}%"
        opt.textVisible = True

        style = QApplication.style()
        if style:
            style.drawControl(QStyle.ControlElement.CE_ProgressBar, opt, painter)


class CenteredIconDelegate(QStyledItemDelegate):
    """Custom delegate that centers the icon in the cell."""

    def paint(self, painter, option, index):
        # Draw selection background if selected
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Get the icon from the item
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon and not icon.isNull():
            # Calculate centered position
            icon_size = option.decorationSize
            x = option.rect.x() + (option.rect.width() - icon_size.width()) // 2
            y = option.rect.y() + (option.rect.height() - icon_size.height()) // 2
            icon.paint(painter, x, y, icon_size.width(), icon_size.height())


# ── Helper Functions ──────────────────────────────────────────────────────


def _confirm_dialog(
    parent: QWidget,
    title: str,
    message: str,
    default_no: bool = True,
) -> bool:
    """Show a confirmation dialog with translated Yes/No buttons.

    Returns True if user clicked Yes, False otherwise.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QMessageBox.Icon.Question)

    btn_yes = msg.addButton(tr("btn.yes"), QMessageBox.ButtonRole.YesRole)
    btn_no = msg.addButton(tr("btn.no"), QMessageBox.ButtonRole.NoRole)

    if default_no:
        msg.setDefaultButton(btn_no)
    else:
        msg.setDefaultButton(btn_yes)

    msg.exec()
    return msg.clickedButton() == btn_yes


# ── Loading Overlay ────────────────────────────────────────────────────────


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


# ── File Detail Panel ─────────────────────────────────────────────────────


class FileDetailPanel:
    """Wrapper around the detail panel QFrame loaded from .ui file."""

    def __init__(self, frame: QFrame) -> None:
        self._frame = frame
        self._frame.hide()  # Hidden by default
        self._base_directory: str = ""

        # Get widget references from .ui
        self._lbl_title: QLabel = frame.findChild(QLabel, "lblDetailTitle")  # type: ignore[assignment]
        self._btn_close: QToolButton = frame.findChild(QToolButton, "btnDetailClose")  # type: ignore[assignment]
        self._lbl_filepath: QLabel = frame.findChild(QLabel, "valFilepath")  # type: ignore[assignment]
        self._lbl_filename: QLabel = frame.findChild(QLabel, "valFilename")  # type: ignore[assignment]
        self._lbl_size: QLabel = frame.findChild(QLabel, "valSize")  # type: ignore[assignment]
        self._lbl_modified: QLabel = frame.findChild(QLabel, "valModified")  # type: ignore[assignment]
        self._lbl_status: QLabel = frame.findChild(QLabel, "valStatus")  # type: ignore[assignment]
        self._lbl_cid: QLabel = frame.findChild(QLabel, "valCid")  # type: ignore[assignment]
        self._lbl_ip: QLabel = frame.findChild(QLabel, "valIp")  # type: ignore[assignment]

        # Label widgets for translation
        self._lbl_filepath_label: QLabel = frame.findChild(QLabel, "lblFilepath")  # type: ignore[assignment]
        self._lbl_filename_label: QLabel = frame.findChild(QLabel, "lblFilename")  # type: ignore[assignment]
        self._lbl_size_label: QLabel = frame.findChild(QLabel, "lblSize")  # type: ignore[assignment]
        self._lbl_modified_label: QLabel = frame.findChild(QLabel, "lblModified")  # type: ignore[assignment]
        self._lbl_status_label: QLabel = frame.findChild(QLabel, "lblStatus")  # type: ignore[assignment]
        self._lbl_cid_label: QLabel = frame.findChild(QLabel, "lblCid")  # type: ignore[assignment]
        self._lbl_ip_label: QLabel = frame.findChild(QLabel, "lblIp")  # type: ignore[assignment]

        # Make filepath label clickable via <a href> + linkActivated signal
        self._lbl_filepath.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._lbl_filepath.setOpenExternalLinks(False)
        self._lbl_filepath.linkActivated.connect(self._on_filepath_clicked)

        # Set close button icon (use bundled icon for cross-platform consistency)
        self._btn_close.setIcon(get_icon("window-close"))

        # Apply translations
        self._apply_translations()
        register_language_callback(self._apply_translations)

    def _apply_translations(self) -> None:
        """Apply i18n translations to detail panel labels."""
        self._lbl_title.setText(tr("detail.title"))
        self._btn_close.setToolTip(tr("action.close"))
        self._lbl_filepath_label.setText(tr("detail.filepath"))
        self._lbl_filename_label.setText(tr("detail.filename"))
        self._lbl_size_label.setText(tr("detail.size"))
        self._lbl_modified_label.setText(tr("detail.modified"))
        self._lbl_status_label.setText(tr("detail.status"))
        self._lbl_cid_label.setText(tr("detail.client_cid"))
        self._lbl_ip_label.setText(tr("detail.client_ip"))

    def set_base_directory(self, directory: str) -> None:
        """Set the base directory for resolving absolute file paths."""
        self._base_directory = directory

    def show_transfer(self, transfer: FileTransfer) -> None:
        """Display details for the given transfer."""
        rel_path = transfer.path
        # Determine the directory to open on click
        if rel_path:
            abs_dir = os.path.join(self._base_directory, rel_path)
            display = rel_path
        else:
            abs_dir = self._base_directory
            display = "."
        self._current_abs_dir = abs_dir
        # Render as clickable HTML link (Qt handles underline + color)
        escaped = display.replace("&", "&").replace("<", "<")
        self._lbl_filepath.setText(f'<a href="file://{abs_dir}">{escaped}</a>')

        self._lbl_filename.setText(transfer.filename)
        self._lbl_size.setText(format_bytes(transfer.size))
        self._lbl_modified.setText(format_mtime(transfer.mtime))

        status_map = {
            TransferStatus.LOCAL: "detail.local",
            TransferStatus.SYNCED: "detail.synced",
            TransferStatus.TO_DOWNLOAD: "detail.to_download",
            TransferStatus.TO_UPLOAD: "detail.to_upload",
            TransferStatus.TO_DELETE: "detail.to_delete",
            TransferStatus.TO_RENAME: "detail.to_rename",
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
        self._frame.show()

    def _on_filepath_clicked(self, _link: str) -> None:
        """Open the file's directory in the system file manager."""
        abs_dir = getattr(self, "_current_abs_dir", "")
        if abs_dir and os.path.isdir(abs_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir))

    def clear(self) -> None:
        """Clear and hide the panel."""
        self._current_abs_dir = ""
        self._lbl_filepath.setText("—")
        self._frame.hide()


# ── File Transfer Table ──────────────────────────────────────────────────


class FileTransferTable(QTableWidget):
    """Sortable table showing file transfers with hierarchical folder navigation."""

    row_selected = Signal(object)  # Emits FileTransfer or None
    row_deselected = Signal()  # Emitted when clicking on already selected row
    properties_requested = Signal(object)  # Emits FileTransfer for properties panel
    path_changed = Signal(str)  # Emitted when current navigation path changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transfers: dict[str, FileTransfer] = {}  # filepath -> transfer (flat)
        self._transfers_mutex = QMutex()  # Protects _transfers dict
        self._row_index: dict[str, int] = {}  # display key -> row index
        self._last_selected_row: int = -1
        self._base_directory: str = ""

        # Hierarchical navigation state
        self._current_path: str = ""  # Current folder (relative to base, "" = root)
        self._nav_history: list[str] = [""]  # Navigation history stack
        self._nav_index: int = 0  # Current position in history

        # Timer to distinguish single-click from double-click
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(QApplication.doubleClickInterval())
        self._click_timer.timeout.connect(self._on_single_click_confirmed)
        self._pending_click_row: int = -1

        # Debounce timer for refresh_view during batch loading
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(100)  # 100ms debounce
        self._refresh_timer.timeout.connect(self._do_refresh_view)
        self._refresh_pending = False

        # Cache for computed items at current level to avoid redundant computation
        self._cached_items: list[tuple[str, FileTransfer | None, dict]] | None = None
        self._cached_path: str = ""

        self._setup_table()

    def _setup_table(self) -> None:
        headers = [tr(key) if key else "" for key in _COLUMN_KEYS]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        from PySide6.QtCore import QSize

        self.setIconSize(QSize(16, 16))

        # Column sizing and behavior
        header = self.horizontalHeader()
        header.setHighlightSections(False)  # Prevent bold header on row selection
        header.setSectionsMovable(True)  # Allow drag-and-drop column reordering
        header.setSectionResizeMode(COL_ICON, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_MODIFIED, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PROGRESS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_ETA, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)

        # Icon column: centered icon with fixed width
        self.setItemDelegateForColumn(COL_ICON, CenteredIconDelegate(self))
        header.resizeSection(COL_ICON, 32)

        # Progress bar delegate and default column width
        self.setItemDelegateForColumn(COL_PROGRESS, ProgressBarDelegate(self))
        header.resizeSection(COL_PROGRESS, 130)

        # Enable context menu on header for column visibility
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)

        # Enable context menu on table rows
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_file_context_menu)

        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _show_header_context_menu(self, pos) -> None:
        """Show context menu to toggle column visibility."""
        menu = QMenu(self)
        header = self.horizontalHeader()

        for col, key in enumerate(_COLUMN_KEYS):
            if not key:
                continue  # Skip icon column (no header text, always visible)
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
        """Defer single-click action to distinguish from double-click."""
        self._pending_click_row = row
        self._click_timer.start()

    def _on_single_click_confirmed(self) -> None:
        """Handle confirmed single click: toggle selection on re-click."""
        row = self._pending_click_row
        if row == self._last_selected_row:
            # Re-click on same row → deselect
            self._last_selected_row = -1
            self.clearSelection()
            self.row_deselected.emit()
        else:
            # New row clicked → keep it selected
            self._last_selected_row = row
            # Notify that a new row was selected (used to update open panel)
            transfer = self._get_transfer_at_row(row)
            if transfer:
                self.row_selected.emit(transfer)

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        """Handle double-click: navigate into folder or open file."""
        self._click_timer.stop()
        self._last_selected_row = row
        name_item = self.item(row, COL_NAME)
        if not name_item:
            return
        display_name = name_item.text()
        # Check if it's a synthesized folder (exists in current level)
        full_path = f"{self._current_path}/{display_name}" if self._current_path else display_name
        # Check if any transfer has this as a prefix (folder)
        is_folder = any(
            t.filepath == full_path + "/" or t.filepath.startswith(full_path + "/")
            for t in self._transfers.values()
        )
        if is_folder:
            self.navigate_to(full_path)
        else:
            # It's a file - open it
            transfer = self._get_transfer_at_row(row)
            if transfer:
                self._ctx_open(transfer)

    def set_base_directory(self, directory: str) -> None:
        """Set the base directory for resolving absolute file paths."""
        self._base_directory = directory
        # Reset navigation when base directory changes
        self._current_path = ""
        self._nav_history = [""]
        self._nav_index = 0

    # ── Hierarchical navigation ───────────────────────────────────────────

    @property
    def current_path(self) -> str:
        """Current folder path (relative to base directory)."""
        return self._current_path

    def navigate_to(self, path: str) -> None:
        """Navigate to a folder path (relative to base directory)."""
        path = path.strip("/")
        if path == self._current_path:
            return
        # Add to history (truncate forward history if navigating from middle)
        self._nav_index += 1
        self._nav_history = self._nav_history[: self._nav_index] + [path]
        self._current_path = path
        self.refresh_view()
        self.path_changed.emit(path)

    def navigate_back(self) -> None:
        """Navigate to the previous folder in history."""
        if self._nav_index > 0:
            self._nav_index -= 1
            self._current_path = self._nav_history[self._nav_index]
            self.refresh_view()
            self.path_changed.emit(self._current_path)

    def navigate_forward(self) -> None:
        """Navigate to the next folder in history."""
        if self._nav_index < len(self._nav_history) - 1:
            self._nav_index += 1
            self._current_path = self._nav_history[self._nav_index]
            self.refresh_view()
            self.path_changed.emit(self._current_path)

    def navigate_up(self) -> None:
        """Navigate to parent folder."""
        if self._current_path:
            parent = str(Path(self._current_path).parent)
            self.navigate_to("" if parent == "." else parent)

    def can_go_back(self) -> bool:
        """Check if back navigation is possible."""
        return self._nav_index > 0

    def can_go_forward(self) -> bool:
        """Check if forward navigation is possible."""
        return self._nav_index < len(self._nav_history) - 1

    def _get_items_at_current_level(self) -> list[tuple[str, FileTransfer | None, dict]]:
        """Get items to display at the current navigation level."""
        prefix = f"{self._current_path}/" if self._current_path else ""
        prefix_len = len(prefix)

        items: dict[str, tuple[FileTransfer | None, dict]] = {}
        folder_files: dict[str, list[FileTransfer]] = {}

        for filepath, transfer in self._transfers.items():
            if prefix and not filepath.startswith(prefix):
                continue
            if not prefix and "/" in filepath.rstrip("/"):
                top_part = filepath.split("/")[0]
                if top_part not in folder_files:
                    folder_files[top_part] = []
                folder_files[top_part].append(transfer)
                continue
            if prefix:
                remainder = filepath[prefix_len:]
            else:
                remainder = filepath
            remainder_clean = remainder.rstrip("/")
            if not remainder_clean:
                continue
            if "/" in remainder_clean:
                subfolder = remainder_clean.split("/")[0]
                if subfolder not in folder_files:
                    folder_files[subfolder] = []
                folder_files[subfolder].append(transfer)
            else:
                items[remainder_clean] = (transfer, {})

        for folder_name, files in folder_files.items():
            folder_data = self._aggregate_folder(files)
            if folder_name in items:
                existing_transfer, _ = items[folder_name]
                items[folder_name] = (existing_transfer, folder_data)
            else:
                items[folder_name] = (None, folder_data)

        def sort_key(item: tuple[str, tuple[FileTransfer | None, dict]]) -> tuple[int, str]:
            name, (transfer, folder_data) = item
            is_folder = transfer is None or transfer.filepath.endswith("/")
            return (0 if is_folder else 1, name.lower())

        sorted_items = sorted(items.items(), key=sort_key)
        return [(name, t, fd) for name, (t, fd) in sorted_items]

    def _aggregate_folder(self, files: list[FileTransfer]) -> dict:
        """Aggregate data for a folder from its contained files."""
        count = len(files)
        total_size = 0
        total_transferred = 0
        max_mtime = 0.0
        status_priority = 100

        priority_map = {
            TransferStatus.ERROR: 1,
            TransferStatus.DOWNLOADING: 2,
            TransferStatus.UPLOADING: 2,
            TransferStatus.TO_DOWNLOAD: 3,
            TransferStatus.TO_UPLOAD: 3,
            TransferStatus.TO_DELETE: 3,
            TransferStatus.TO_RENAME: 3,
            TransferStatus.COMPLETED: 4,
            TransferStatus.SYNCED: 5,
            TransferStatus.LOCAL: 6,
        }
        status_key_map = {
            1: "folder.status.error",
            2: "folder.status.syncing",
            3: "folder.status.to_sync",
            4: "folder.status.completed",
            5: "folder.status.synced",
            6: "folder.status.local",
        }

        for f in files:
            if not f.filepath.endswith("/"):
                total_size += f.size
                total_transferred += f.bytes_transferred
            if f.mtime > max_mtime:
                max_mtime = f.mtime
            p = priority_map.get(f.status, 100)
            if p < status_priority:
                status_priority = p

        status_key = status_key_map.get(status_priority, "folder.status.local")
        progress = int(total_transferred / total_size * 100) if total_size > 0 else -1

        return {
            "count": count,
            "total_size": total_size,
            "mtime": max_mtime,
            "progress": progress,
            "status_key": status_key,
            "status_priority": status_priority,
        }

    def _schedule_refresh(self) -> None:
        """Schedule a debounced refresh of the view."""
        self._refresh_pending = True
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _do_refresh_view(self) -> None:
        """Execute the pending refresh."""
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh_view()

    def refresh_view(self) -> None:
        """Refresh the table to show items at the current navigation level."""
        self._refresh_timer.stop()
        self._refresh_pending = False

        # Use cached items if path hasn't changed and cache is valid
        if self._cached_path != self._current_path or self._cached_items is None:
            self._cached_path = self._current_path
            self._cached_items = self._get_items_at_current_level()

        items = self._cached_items
        if items is None:
            return

        self.setUpdatesEnabled(False)
        self.setSortingEnabled(False)
        try:
            self.setRowCount(0)
            self._row_index.clear()
            self._last_selected_row = -1

            for display_name, transfer, folder_data in items:
                row = self.rowCount()
                self.insertRow(row)
                self._row_index[display_name] = row
                self._populate_row_hierarchical(row, display_name, transfer, folder_data)
        finally:
            self.setSortingEnabled(True)
            self.setUpdatesEnabled(True)

    def _populate_row_hierarchical(
        self, row: int, display_name: str, transfer: FileTransfer | None, folder_data: dict | None
    ) -> None:
        """Populate a row for hierarchical view."""
        is_folder = transfer is None or transfer.filepath.endswith("/")

        # Icon
        if is_folder:
            icon_name, type_key = "folder", "ftype.folder"
        elif transfer is not None:
            icon_name, type_key = _classify_file(transfer.filepath)
        else:
            icon_name, type_key = "folder", "ftype.folder"
        icon_item = QTableWidgetItem()
        icon_item.setIcon(get_icon(icon_name))
        icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_ICON, icon_item)

        # Name
        self.setItem(row, COL_NAME, QTableWidgetItem(display_name))

        # Type
        self.setItem(row, COL_TYPE, QTableWidgetItem(tr(type_key)))

        # Size / Item count
        if is_folder and folder_data:
            count = folder_data.get("count", 0)
            size_text = tr("folder.items").format(count=count)
        elif transfer and not is_folder:
            size_text = format_bytes(transfer.size)
        else:
            size_text = ""
        size_item = QTableWidgetItem(size_text)
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_SIZE, size_item)

        # Modified
        mtime = (
            folder_data.get("mtime", 0.0) if folder_data else (transfer.mtime if transfer else 0.0)
        )
        mtime_item = QTableWidgetItem(format_mtime(mtime))
        mtime_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_MODIFIED, mtime_item)

        # Progress
        progress_item = QTableWidgetItem()
        if is_folder:
            if folder_data:
                status_priority = folder_data.get("status_priority", 100)
                if status_priority == 2:
                    progress = folder_data.get("progress", -1)
                else:
                    progress = -1
            else:
                progress = -1
            progress_item.setData(Qt.ItemDataRole.UserRole, progress)
        elif transfer:
            if transfer.status in _NO_PROGRESS_STATUSES:
                progress_item.setData(Qt.ItemDataRole.UserRole, -1)
            elif transfer.size > 0:
                pct = int(transfer.bytes_transferred / transfer.size * 100)
                progress_item.setData(Qt.ItemDataRole.UserRole, pct)
            else:
                progress_item.setData(Qt.ItemDataRole.UserRole, -1)
        else:
            progress_item.setData(Qt.ItemDataRole.UserRole, -1)
        self.setItem(row, COL_PROGRESS, progress_item)

        # ETA
        eta = transfer.eta_seconds if transfer else None
        eta_item = QTableWidgetItem(format_duration(eta, style="compact"))
        eta_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_ETA, eta_item)

        # Status
        if is_folder and folder_data:
            status_key = folder_data.get("status_key", "folder.status.local")
            status_text = tr(status_key)
            status_priority = folder_data.get("status_priority", 6)
            priority_to_status = {
                1: TransferStatus.ERROR,
                2: TransferStatus.DOWNLOADING,
                3: TransferStatus.TO_DOWNLOAD,
                4: TransferStatus.COMPLETED,
                5: TransferStatus.SYNCED,
                6: TransferStatus.LOCAL,
            }
            status_for_color = priority_to_status.get(status_priority, TransferStatus.LOCAL)
        elif transfer:
            status_map = {
                TransferStatus.LOCAL: tr("detail.local"),
                TransferStatus.SYNCED: tr("detail.synced"),
                TransferStatus.TO_DOWNLOAD: tr("detail.to_download"),
                TransferStatus.TO_UPLOAD: tr("detail.to_upload"),
                TransferStatus.TO_DELETE: tr("detail.to_delete"),
                TransferStatus.TO_RENAME: tr("detail.to_rename"),
                TransferStatus.DOWNLOADING: tr("detail.downloading"),
                TransferStatus.UPLOADING: tr("detail.uploading"),
                TransferStatus.DELETED: tr("detail.deleted"),
                TransferStatus.QUEUED: tr("detail.pending"),
                TransferStatus.TRANSFERRING: tr("detail.transferring"),
                TransferStatus.COMPLETED: tr("detail.completed"),
                TransferStatus.ERROR: tr("status.error"),
            }
            status_text = status_map.get(transfer.status, "?")
            status_for_color = transfer.status
        else:
            status_text = ""
            status_for_color = TransferStatus.LOCAL
        self.setItem(row, COL_STATUS, QTableWidgetItem(status_text))

        # Apply status color
        color = STATUS_COLORS.get(status_for_color, QColor(128, 128, 128))
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setForeground(color)

    def _get_transfer_at_row(self, row: int) -> FileTransfer | None:
        """Return the FileTransfer for the given row."""
        name_item = self.item(row, COL_NAME)
        if not name_item:
            return None
        display_name = name_item.text()
        full_path = f"{self._current_path}/{display_name}" if self._current_path else display_name
        return self._transfers.get(full_path) or self._transfers.get(full_path + "/")

    def _absolute_path(self, transfer: FileTransfer) -> str:
        """Build the absolute path of a transfer's file."""
        return os.path.join(self._base_directory, transfer.filepath)

    # ── File context menu ─────────────────────────────────────────────────

    def _show_file_context_menu(self, pos) -> None:
        """Show right-click context menu for a file row."""
        index = self.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        transfer = self._get_transfer_at_row(row)

        if not transfer:
            name_item = self.item(row, COL_NAME)
            if not name_item:
                return
            display_name = name_item.text()
            folder_path = (
                f"{self._current_path}/{display_name}/"
                if self._current_path
                else f"{display_name}/"
            )
            transfer = FileTransfer(
                filepath=folder_path, direction="—", size=0, status=TransferStatus.LOCAL
            )

        is_dir = transfer.filepath.endswith("/")

        menu = QMenu(self)
        menu.addAction(tr("ctx.open"), lambda: self._ctx_open(transfer))
        if not is_dir:
            menu.addAction(tr("ctx.open_with"), lambda: self._ctx_open_with(transfer))
        menu.addSeparator()
        menu.addAction(tr("ctx.copy_to"), lambda: self._ctx_copy_to(transfer))
        menu.addAction(tr("ctx.rename"), lambda: self._ctx_rename(transfer))
        menu.addSeparator()
        menu.addAction(tr("ctx.trash"), lambda: self._ctx_trash(transfer))
        menu.addSeparator()
        menu.addAction(tr("ctx.properties"), lambda: self._ctx_properties(transfer))
        menu.exec(self.viewport().mapToGlobal(pos))

    def _ctx_open(self, transfer: FileTransfer) -> None:
        """Open the file with the system default application."""
        abs_path = self._absolute_path(transfer)
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_open").format(error=str(exc))
            )

    def _ctx_open_with(self, transfer: FileTransfer) -> None:
        """Open the system 'Open With' dialog for the file."""
        abs_path = self._absolute_path(transfer)
        system = platform.system()
        try:
            if system == "Linux":
                self._open_with_linux(abs_path)
            elif system == "Darwin":
                script = f'set theFile to POSIX file "{abs_path}"\nset theApp to choose application with prompt "Open With" as alias\ntell application (POSIX path of (theApp as text))\n  open theFile\nend tell'
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif system == "Windows":
                subprocess.Popen(
                    ["rundll32.exe", "shell32.dll,OpenAs_RunDLL", abs_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_open_with").format(error=str(exc))
            )

    @staticmethod
    def _open_with_linux(abs_path: str) -> None:
        """Open the 'Open With' app chooser via XDG Desktop Portal."""
        from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusUnixFileDescriptor

        fd = os.open(abs_path, os.O_RDONLY)
        try:
            descriptor = QDBusUnixFileDescriptor(fd)
        finally:
            os.close(fd)

        msg = QDBusMessage.createMethodCall(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.OpenURI",
            "OpenFile",
        )
        msg.setArguments(["", descriptor, {"ask": True}])
        bus = QDBusConnection.sessionBus()
        reply = bus.call(msg)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            raise RuntimeError(reply.errorMessage())

    def _ctx_copy_to(self, transfer: FileTransfer) -> None:
        """Copy the file or directory to a user-chosen directory."""
        abs_path = self._absolute_path(transfer)
        dest_dir = QFileDialog.getExistingDirectory(
            self, tr("ctx.copy_dialog_title"), os.path.dirname(abs_path)
        )
        if not dest_dir:
            return

        display_name = transfer.filepath.rstrip("/")
        if not _confirm_dialog(
            self,
            tr("ctx.confirm_copy_title"),
            tr("ctx.confirm_copy").format(name=display_name, dest=dest_dir),
        ):
            return

        is_dir = os.path.isdir(abs_path)
        item_name = os.path.basename(abs_path.rstrip("/"))
        dest_path = os.path.join(dest_dir, item_name)

        if os.path.exists(dest_path):
            if not _confirm_dialog(
                self,
                tr("ctx.confirm_overwrite_title"),
                tr("ctx.confirm_overwrite").format(name=item_name, dest=dest_dir),
            ):
                return
            try:
                if os.path.isdir(dest_path):
                    shutil.rmtree(dest_path)
                else:
                    os.remove(dest_path)
            except Exception as exc:
                QMessageBox.warning(
                    self, tr("ctx.error_title"), tr("ctx.error_copy").format(error=str(exc))
                )
                return

        try:
            if is_dir:
                shutil.copytree(abs_path, dest_path)
            else:
                shutil.copy2(abs_path, dest_dir)
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_copy").format(error=str(exc))
            )

    def _ctx_rename(self, transfer: FileTransfer) -> None:
        """Show a rename dialog and rename the file on disk."""
        abs_path = self._absolute_path(transfer)
        old_name = transfer.filename

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("ctx.rename_title"))
        form = QFormLayout(dlg)
        line_edit = QLineEdit(old_name)
        form.addRow(tr("ctx.rename_label"), line_edit)
        buttons = QDialogButtonBox()
        rename_btn = buttons.addButton(tr("ctx.rename_btn"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr("action.cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(dlg.reject)
        rename_btn.clicked.connect(dlg.accept)
        form.addRow(buttons)

        dot_idx = old_name.rfind(".")
        if dot_idx > 0:
            line_edit.setSelection(0, dot_idx)
        else:
            line_edit.selectAll()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = line_edit.text().strip()
        if not new_name or new_name == old_name:
            return
        # Fix: rstrip trailing slash from abs_path before dirname
        # Otherwise for directories, dirname removes the slash and join creates wrong path
        abs_path_rstripped = abs_path.rstrip("/")
        new_abs = os.path.join(os.path.dirname(abs_path_rstripped), new_name)
        try:
            os.rename(abs_path, new_abs)
            # Handle directories: filepath ends with "/"
            is_dir = transfer.filepath.endswith("/")
            parent = transfer.path
            new_rel = (
                (parent + new_name + "/")
                if is_dir
                else (os.path.join(parent, new_name) if parent else new_name)
            )
            old_rel = transfer.filepath
            del self._transfers[old_rel]
            transfer.filepath = new_rel
            self._transfers[new_rel] = transfer
            self._cached_items = None  # Invalidate cache
            self.refresh_view()
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_rename").format(error=str(exc))
            )

    def _ctx_trash(self, transfer: FileTransfer) -> None:
        """Move the file to the system trash."""
        display_name = transfer.filepath.rstrip("/")
        if not _confirm_dialog(
            self, tr("ctx.confirm_trash_title"), tr("ctx.confirm_trash").format(name=display_name)
        ):
            return

        abs_path = self._absolute_path(transfer)
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.run(
                    ["gio", "trash", abs_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            elif system == "Darwin":
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'tell application "Finder" to delete (POSIX file "{abs_path}" as alias)',
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            elif system == "Windows":
                ps_cmd = f'Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("{abs_path}", "OnlyErrorDialogs", "SendToRecycleBin")'
                subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            else:
                raise OSError("Unsupported platform for trash operation")
            self._remove_file(transfer.filepath)
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_trash").format(error=str(exc))
            )

    def _ctx_properties(self, transfer: FileTransfer) -> None:
        """Open the properties panel."""
        self.properties_requested.emit(transfer)

    def add_transfer(self, transfer: FileTransfer) -> None:
        """Add or update a transfer in the table."""
        with QMutexLocker(self._transfers_mutex):
            self._transfers[transfer.filepath] = transfer
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def update_transfer_status(self, filepath: str, status: TransferStatus) -> None:
        """Update the status of a transfer."""
        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                self._transfers[filepath].status = status
        self.refresh_view()

    def mark_completed(self, filepath: str, size: int = 0, direction: str = "↓") -> None:
        """Mark a transfer as completed."""
        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                t = self._transfers[filepath]
                t.status = TransferStatus.COMPLETED
                if size:
                    t.size = size
                    t.bytes_transferred = size
            else:
                t = FileTransfer(
                    filepath=filepath,
                    direction=direction,
                    size=size,
                    bytes_transferred=size,
                    status=TransferStatus.COMPLETED,
                )
                self._transfers[filepath] = t
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def clear_transfers(self) -> None:
        """Clear all transfers from the table."""
        with QMutexLocker(self._transfers_mutex):
            self._transfers.clear()
        self._cached_items = None  # Invalidate cache
        self._row_index.clear()
        self._current_path = ""
        self._nav_history = [""]
        self._nav_index = 0
        self.setRowCount(0)

    def reset_all_to_local(self) -> None:
        """Reset every file's status to LOCAL."""
        with QMutexLocker(self._transfers_mutex):
            for transfer in self._transfers.values():
                transfer.status = TransferStatus.LOCAL
                transfer.direction = "—"
                transfer.bytes_transferred = 0
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def add_transfers_batch(self, transfers: list[FileTransfer]) -> None:
        """Add multiple transfers efficiently."""
        if not transfers:
            return
        with QMutexLocker(self._transfers_mutex):
            for transfer in transfers:
                self._transfers[transfer.filepath] = transfer
        self._cached_items = None  # Invalidate cache
        self._schedule_refresh()

    def update_file_status(
        self,
        filepath: str,
        status: str,
        size: int = 0,
        mtime: float = 0.0,
        client_cid: str = "",
        client_ip: str = "",
    ) -> None:
        """Update or add a file with the given status."""
        status_mapping = {
            "synced": TransferStatus.SYNCED,
            "to_download": TransferStatus.TO_DOWNLOAD,
            "to_upload": TransferStatus.TO_UPLOAD,
            "to_delete": TransferStatus.TO_DELETE,
            "to_rename": TransferStatus.TO_RENAME,
        }
        transfer_status = status_mapping.get(status, TransferStatus.LOCAL)

        if status == "to_download":
            direction = "↓"
        elif status == "to_upload":
            direction = "↑"
        elif status == "to_delete":
            direction = "✕"
        elif status == "to_rename":
            direction = "⇄"
        else:
            direction = "—"

        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                t = self._transfers[filepath]
                t.status = transfer_status
                t.direction = direction
                if size:
                    t.size = size
                if mtime:
                    t.mtime = mtime
                if client_cid:
                    t.client_cid = client_cid
                if client_ip:
                    t.client_ip = client_ip
            else:
                t = FileTransfer(
                    filepath=filepath,
                    direction=direction,
                    size=size,
                    status=transfer_status,
                    mtime=mtime,
                    client_cid=client_cid,
                    client_ip=client_ip,
                )
                self._transfers[filepath] = t
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def mark_deleted(self, filepath: str) -> None:
        """Mark a file as deleted."""
        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                t = self._transfers[filepath]
                t.status = TransferStatus.DELETED
                t.direction = "✕"
        self.refresh_view()
        QTimer.singleShot(3000, lambda: self._remove_file(filepath))

    def _remove_file(self, filepath: str) -> None:
        """Remove a file from the table."""
        with QMutexLocker(self._transfers_mutex):
            if filepath not in self._transfers:
                return
            del self._transfers[filepath]
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def rename_file(
        self,
        old_path: str,
        new_path: str,
        mtime: float = 0.0,
        client_cid: str = "",
        client_ip: str = "",
    ) -> None:
        """Handle a file rename."""
        old_size = 0
        with QMutexLocker(self._transfers_mutex):
            if old_path in self._transfers:
                old_size = self._transfers[old_path].size
                del self._transfers[old_path]
            if new_path in self._transfers:
                t = self._transfers[new_path]
                t.status = TransferStatus.SYNCED
                t.direction = "⇄"
                if old_size:
                    t.size = old_size
                if mtime:
                    t.mtime = mtime
                if client_cid:
                    t.client_cid = client_cid
                if client_ip:
                    t.client_ip = client_ip
            else:
                t = FileTransfer(
                    filepath=new_path,
                    direction="⇄",
                    size=old_size,
                    status=TransferStatus.SYNCED,
                    mtime=mtime,
                    client_cid=client_cid,
                    client_ip=client_ip,
                )
                self._transfers[new_path] = t
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def remove_transfer(self, filepath: str) -> None:
        """Remove a transfer immediately."""
        self._remove_file(filepath)

    def update_transfer_progress(
        self, filepath: str, bytes_transferred: int, total_bytes: int
    ) -> None:
        """Update the progress of a transfer in real-time.

        Args:
            filepath: The file path to update
            bytes_transferred: Number of bytes transferred so far
            total_bytes: Total size of the file in bytes
        """
        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                t = self._transfers[filepath]
                t.bytes_transferred = bytes_transferred
                t.size = total_bytes
                # Set status to transferring if not already set
                if t.status not in (TransferStatus.DOWNLOADING, TransferStatus.UPLOADING):
                    t.status = TransferStatus.DOWNLOADING
        self._schedule_refresh()


# ── Main File Panel ───────────────────────────────────────────────────────


class FilePanel(QWidget):
    """Complete file transfer panel with table and collapsible detail panel."""

    CONSISTENCY_CHECK_INTERVAL_MS = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_thread: QThread | None = None
        self._scan_worker: DirectoryScanWorker | None = None
        self._current_directory: str = ""
        self._scan_generation: int = 0
        self._consistency_timer = QTimer(self)
        self._consistency_timer.timeout.connect(self._check_directory_consistency)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        load_ui_widget("file_panel", self)
        self._splitter: QSplitter = self.findChild(QSplitter, "splitter")  # type: ignore[assignment]
        ui_table: QTableWidget = self.findChild(QTableWidget, "transferTable")  # type: ignore[assignment]
        self._table = FileTransferTable()
        table_idx = self._splitter.indexOf(ui_table)

        self._table_container = QWidget()
        table_layout = QVBoxLayout(self._table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        nav_bar = QWidget()
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(4)

        self._btn_back = QToolButton()
        self._btn_back.setIcon(get_icon("go-previous"))
        self._btn_back.setToolTip(tr("nav.back"))
        self._btn_back.setEnabled(False)
        self._btn_back.setAutoRaise(True)

        self._btn_forward = QToolButton()
        self._btn_forward.setIcon(get_icon("go-next"))
        self._btn_forward.setToolTip(tr("nav.forward"))
        self._btn_forward.setEnabled(False)
        self._btn_forward.setAutoRaise(True)

        self._btn_up = QToolButton()
        self._btn_up.setIcon(get_icon("go-up"))
        self._btn_up.setToolTip(tr("nav.up"))
        self._btn_up.setEnabled(False)
        self._btn_up.setAutoRaise(True)

        nav_layout.addWidget(self._btn_back)
        nav_layout.addWidget(self._btn_forward)
        nav_layout.addWidget(self._btn_up)

        self._breadcrumb_icon = QLabel(nav_bar)
        self._breadcrumb_icon.setPixmap(get_icon("folder-open").pixmap(16, 16))
        self._breadcrumb_icon.setFixedSize(20, 20)
        self._breadcrumb_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._breadcrumb_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._breadcrumb_icon.setToolTip(tr("nav.root"))
        self._breadcrumb_icon.mousePressEvent = lambda _: self._table.navigate_to("")  # type: ignore[method-assign]
        nav_layout.addWidget(self._breadcrumb_icon)

        self._breadcrumb_label = QLabel()
        self._breadcrumb_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._breadcrumb_label.setOpenExternalLinks(False)
        self._breadcrumb_label.linkActivated.connect(self._on_breadcrumb_clicked)
        nav_layout.addWidget(self._breadcrumb_label, 1)

        table_layout.addWidget(nav_bar)
        table_layout.addWidget(self._table)

        ui_table.setParent(None)
        self._splitter.insertWidget(table_idx, self._table_container)

        self._loading_overlay = LoadingOverlay(self._table_container)
        self._table_container.installEventFilter(self)

        detail_frame: QFrame = self.findChild(QFrame, "detailPanel")  # type: ignore[assignment]
        self._detail = FileDetailPanel(detail_frame)

        self._splitter.setSizes([800, 0])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

    def _connect_signals(self) -> None:
        self._table.row_deselected.connect(self._hide_detail_panel)
        self._table.row_selected.connect(self._on_row_selected)
        self._table.properties_requested.connect(self._on_properties_requested)
        self._detail._btn_close.clicked.connect(self._on_detail_close)
        self._btn_back.clicked.connect(self._table.navigate_back)
        self._btn_forward.clicked.connect(self._table.navigate_forward)
        self._btn_up.clicked.connect(self._table.navigate_up)
        self._table.path_changed.connect(self._update_nav_buttons)
        self._update_breadcrumb()

    @Slot()
    def _on_detail_close(self) -> None:
        self._hide_detail_panel()

    @Slot(object)
    def _on_row_selected(self, transfer: FileTransfer | None) -> None:
        if transfer and self._splitter.sizes()[1] > 0:
            self._detail.show_transfer(transfer)

    @Slot(object)
    def _on_properties_requested(self, transfer: FileTransfer | None) -> None:
        if transfer:
            self._detail.show_transfer(transfer)
            sizes = self._splitter.sizes()
            if sizes[1] == 0:
                self._splitter.setSizes([600, 250])

    @Slot()
    def _hide_detail_panel(self) -> None:
        self._detail.clear()
        self._splitter.setSizes([800, 0])
        self._table.clearSelection()
        self._table._last_selected_row = -1

    @Slot(str)
    def _update_nav_buttons(self, _path: str) -> None:
        self._btn_back.setEnabled(self._table.can_go_back())
        self._btn_forward.setEnabled(self._table.can_go_forward())
        self._btn_up.setEnabled(bool(self._table.current_path))
        self._update_breadcrumb()

    def _update_breadcrumb(self) -> None:
        self._breadcrumb_icon.setPixmap(get_icon("folder-open").pixmap(16, 16))
        current_folder = self._table.current_path
        if not current_folder:
            self._breadcrumb_label.setText("")
            self._breadcrumb_label.setCursor(Qt.CursorShape.ArrowCursor)
            return
        link_color = (
            self._breadcrumb_label.palette()
            .color(self._breadcrumb_label.palette().ColorRole.Link)
            .name()
        )
        parts = []
        segments = current_folder.split("/")
        path_so_far = ""
        for seg in segments:
            path_so_far = f"{path_so_far}/{seg}" if path_so_far else seg
            parts.append(
                f'<a href="nav:{path_so_far}" style="color:{link_color}; text-decoration:none;">{seg}</a>'
            )
        breadcrumb = " › " + " › ".join(parts)
        self._breadcrumb_label.setText(breadcrumb)
        self._breadcrumb_label.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_breadcrumb_clicked(self, link: str) -> None:
        if link.startswith("nav:"):
            folder_path = link[4:]
            self._table.navigate_to(folder_path)

    # ── Public API ────────────────────────────────────────────────────────

    def add_transfer(self, filepath: str, direction: str, size: int = 0) -> None:
        transfer = FileTransfer(
            filepath=filepath, direction=direction, size=size, status=TransferStatus.QUEUED
        )
        self._table.add_transfer(transfer)

    def clear(self) -> None:
        self._consistency_timer.stop()
        self._stop_scan()
        self._table.clear_transfers()
        self._detail.clear()

    def reset_all_to_local(self) -> None:
        self._table.reset_all_to_local()
        self._detail.clear()

    def load_local_files(self, directory: str) -> None:
        self._stop_scan()
        self._consistency_timer.stop()
        self.clear()
        if not directory or not os.path.isdir(directory):
            self._current_directory = ""
            return
        self._current_directory = directory
        self._table.set_base_directory(directory)
        self._detail.set_base_directory(directory)
        self._scan_generation += 1
        self._show_loading()
        self._scan_thread = QThread()
        self._scan_worker = DirectoryScanWorker(directory)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.files_found.connect(
            self._on_files_found, Qt.ConnectionType.QueuedConnection
        )
        self._scan_worker.progress.connect(
            self._on_scan_progress, Qt.ConnectionType.QueuedConnection
        )
        self._scan_worker.finished.connect(
            self._on_scan_finished, Qt.ConnectionType.QueuedConnection
        )
        self._scan_thread.start()

    def _stop_scan(self) -> None:
        self._hide_loading()
        if self._scan_worker:
            try:
                self._scan_worker.files_found.disconnect()
            except RuntimeError:
                pass
            try:
                self._scan_worker.progress.disconnect()
            except RuntimeError:
                pass
            try:
                self._scan_worker.finished.disconnect()
            except RuntimeError:
                pass
            self._scan_worker.cancel()
            self._scan_worker.deleteLater()
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(1000)
            self._scan_thread.deleteLater()
        self._scan_thread = None
        self._scan_worker = None

    @Slot(list)
    def _on_files_found(self, files: list[tuple[str, int, float]]) -> None:
        if self._scan_worker is None:
            return
        transfers = [
            FileTransfer(
                filepath=filepath,
                direction="—",
                size=size,
                bytes_transferred=0,
                status=TransferStatus.LOCAL,
                mtime=mtime,
            )
            for filepath, size, mtime in files
        ]
        self._table.add_transfers_batch(transfers)

    @Slot()
    def _on_scan_finished(self) -> None:
        self._hide_loading()
        if self._scan_thread:
            self._scan_thread.quit()
            self._scan_thread.wait()
        self._scan_thread = None
        self._scan_worker = None
        self._table.refresh_view()
        if self._current_directory:
            self._consistency_timer.start(self.CONSISTENCY_CHECK_INTERVAL_MS)

    @Slot(int, int)
    def _on_scan_progress(self, current: int, total: int) -> None:
        self._loading_overlay.set_progress(current, total)

    def _show_loading(self) -> None:
        self._loading_overlay.setGeometry(self._table_container.rect())
        self._loading_overlay.show_loading()

    def _hide_loading(self) -> None:
        self._loading_overlay.hide_loading()

    def eventFilter(self, watched: QObject, event) -> bool:
        from PySide6.QtCore import QEvent

        if watched == self._table_container and event.type() == QEvent.Type.Resize:
            if self._loading_overlay.isVisible():
                self._loading_overlay.setGeometry(self._table_container.rect())
        return super().eventFilter(watched, event)

    @Slot()
    def _check_directory_consistency(self) -> None:
        if not self._current_directory or not os.path.isdir(self._current_directory):
            self._consistency_timer.stop()
            return
        current_files: set[str] = set()
        base_path = Path(self._current_directory)
        try:
            for root, dirs, files in os.walk(self._current_directory):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                visible_files = [f for f in files if not f.startswith(".")]
                if not visible_files and not dirs and root != self._current_directory:
                    try:
                        rel_dir = str(Path(root).relative_to(base_path))
                        current_files.add(rel_dir + "/")
                    except ValueError:
                        pass
                for f in visible_files:
                    full_path = Path(root) / f
                    try:
                        rel_path = str(full_path.relative_to(base_path))
                        current_files.add(rel_path)
                    except ValueError:
                        pass
        except OSError:
            return
        table_files = set(self._table._transfers.keys())
        new_files = current_files - table_files
        for rel_path in new_files:
            full_path = base_path / rel_path
            is_dir_entry = rel_path.endswith("/")
            try:
                stat = full_path.stat()
                size = 0 if is_dir_entry else stat.st_size
                mtime = stat.st_mtime
            except OSError:
                size = 0
                mtime = 0.0
            transfer = FileTransfer(
                filepath=rel_path,
                direction="—",
                size=size,
                bytes_transferred=0,
                status=TransferStatus.LOCAL,
                mtime=mtime,
            )
            self._table.add_transfer(transfer)
        deleted_files = table_files - current_files
        for rel_path in deleted_files:
            existing = self._table._transfers.get(rel_path)
            if existing and existing.status == TransferStatus.LOCAL:
                self._table.remove_transfer(rel_path)

    def update_file_status(
        self,
        filepath: str,
        status: str,
        size: int = 0,
        mtime: float = 0.0,
        client_cid: str = "",
        client_ip: str = "",
    ) -> None:
        self._table.update_file_status(filepath, status, size, mtime, client_cid, client_ip)

    def mark_deleted(self, filepath: str) -> None:
        self._table.mark_deleted(filepath)

    def rename_file(
        self,
        old_path: str,
        new_path: str,
        mtime: float = 0.0,
        client_cid: str = "",
        client_ip: str = "",
    ) -> None:
        self._table.rename_file(old_path, new_path, mtime, client_cid, client_ip)

    def update_transfer_progress(
        self, filepath: str, bytes_transferred: int, total_bytes: int
    ) -> None:
        """Update the progress of a transfer in real-time.

        Args:
            filepath: The file path to update
            bytes_transferred: Number of bytes transferred so far
            total_bytes: Total size of the file in bytes
        """
        self._table.update_transfer_progress(filepath, bytes_transferred, total_bytes)

    @property
    def table(self) -> FileTransferTable:
        return self._table

    def refresh_icons_for_theme(self) -> None:
        self._btn_back.setIcon(get_icon("go-previous"))
        self._btn_forward.setIcon(get_icon("go-next"))
        self._btn_up.setIcon(get_icon("go-up"))
        self._breadcrumb_icon.setPixmap(get_icon("folder-open").pixmap(16, 16))
        self._detail._btn_close.setIcon(get_icon("window-close"))
        self._table.refresh_view()

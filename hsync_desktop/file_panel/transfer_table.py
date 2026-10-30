# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Sortable transfer table with hierarchical folder navigation."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from time import localtime, strftime, time

from hsync_common.format import format_bytes, format_duration
from PySide6.QtCore import (
    QAbstractTableModel,
    QByteArray,
    QModelIndex,
    QMutex,
    QMutexLocker,
    QPersistentModelIndex,
    QSettings,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QGuiApplication,
    QHideEvent,
    QKeyEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableView,
    QWidget,
)

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.file_panel.delegates import ProgressBarDelegate
from hsync_desktop.file_panel.dialogs import _confirm_dialog
from hsync_desktop.file_panel.filter import has_dot_segment
from hsync_desktop.file_panel.import_ops import validate_sources
from hsync_desktop.file_panel.models import (
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
    STATUS_COLORS_DARK,
    FileTransfer,
    TransferStatus,
)
from hsync_desktop.file_panel.utils import (
    _COLUMN_KEYS,
    COL_DIRECTION,
    COL_ETA,
    COL_MODIFIED,
    COL_NAME,
    COL_PROGRESS,
    COL_SIZE,
    COL_SPEED,
    COL_STATUS,
    COL_TYPE,
    _classify_file,
    format_mtime,
)
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon as get_icon

# Folder aggregation status priority (lower wins) and the matching i18n keys.
_STATUS_PRIORITY = {
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
_FOLDER_STATUS_KEYS = {
    1: "folder.status.error",
    2: "folder.status.syncing",
    3: "folder.status.to_sync",
    4: "folder.status.completed",
    5: "folder.status.synced",
    6: "folder.status.local",
}
_PRIORITY_TO_STATUS = {
    1: TransferStatus.ERROR,
    2: TransferStatus.DOWNLOADING,
    3: TransferStatus.TO_DOWNLOAD,
    4: TransferStatus.COMPLETED,
    5: TransferStatus.SYNCED,
    6: TransferStatus.LOCAL,
}
# Per-file status label i18n keys, resolved with ``tr()`` per row so a live
# language change is reflected without rebuilding the table.
_STATUS_TEXT_KEYS = {
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

# Statuses in which the engine still owns the path: a user rename, move or
# delete would race a running or planned transfer (a finished download would
# recreate the renamed-away entry, a tombstone and an in-flight apply fight for
# ordering, a source rename aborts an upload). The context menu keeps the
# destructive actions disabled for these rows and for folders that contain one.
_BUSY_STATUSES = {
    TransferStatus.TO_DOWNLOAD,
    TransferStatus.TO_UPLOAD,
    TransferStatus.TO_DELETE,
    TransferStatus.TO_RENAME,
    TransferStatus.DOWNLOADING,
    TransferStatus.UPLOADING,
    TransferStatus.QUEUED,
    TransferStatus.TRANSFERRING,
    TransferStatus.DELETED,
}

# Statuses in which the entry is not a complete local file on disk: a download
# commits at the end and a DELETED row is already gone, so read-only actions
# that need the actual file (Copy to) have nothing to work with.
_UNMATERIALIZED_STATUSES = {
    TransferStatus.TO_DOWNLOAD,
    TransferStatus.DOWNLOADING,
    TransferStatus.DELETED,
}

# Minimum width a data column keeps when fitted, restored or dragged, in px. It
# is also the header's global minimum section size, so Qt enforces the floor on
# an interactive drag.
_MIN_COLUMN_WIDTH = 48
# Readable floor for the stretch Name column, in px. A stretch column is
# shrunk to the global minimum section size instead of extending the scroll
# range, so a narrow window silently crushes file names and the horizontal
# scrollbar reports no deficit: the window fit asks for this width instead.
_MIN_NAME_WIDTH = 320
# A profile that never saved column widths has no layout to honour, so the very
# first launch reserves a roomier Name column (the window fit widens the window
# to fit it). Once the widths are persisted the standard floor applies again:
# from then on the saved layout is the user's choice.
_MIN_NAME_FIRST_RUN = 460

# Idle time after the last column adjustment before the layout is persisted.
_STATE_SAVE_DELAY_MS = 300

# Data columns whose width is fitted to the content once (Name stretches and
# Progress keeps its explicit default width).
_FITTED_COLUMNS = (COL_DIRECTION, COL_SIZE, COL_TYPE, COL_MODIFIED, COL_STATUS, COL_ETA, COL_SPEED)


class FileTransferModel(QAbstractTableModel):
    """Row data for :class:`FileTransferTable`, rendered on demand.

    The view computes one ``(display_name, transfer, folder_data)`` entry per
    visible folder/file and hands the list over with :meth:`set_rows`; cells are
    produced through ``data()`` roles instead of retained ``QTableWidgetItem``
    objects. That removes the per-cell item duplicate, lets the view virtualize
    its rows, and makes a single changed value repaint without a full rebuild.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, FileTransfer | None, dict]] = []
        self._connected = False
        self._default_text_color = QColor()
        self._status_palette: dict = STATUS_COLORS
        self._direction_font: QFont | None = None
        # ``None`` keeps the natural folders-first order produced by the view;
        # a column/order is set only when the user sorts by a header.
        self._sort_column: int | None = None
        self._sort_order = Qt.SortOrder.AscendingOrder
        # When the rows were last compared with the remote (epoch seconds).
        # ``None`` means this session never completed a comparison.
        self._verified_at: float | None = None

    # ── Population ────────────────────────────────────────────────────────

    def set_rows(
        self,
        rows: list[tuple[str, FileTransfer | None, dict]],
        *,
        connected: bool,
        default_text_color: QColor,
        status_palette: dict,
        direction_font: QFont | None,
        verified_at: float | None = None,
    ) -> None:
        """Replace every row, re-applying the current user sort if any."""
        self.beginResetModel()
        self._connected = connected
        self._default_text_color = default_text_color
        self._status_palette = status_palette
        self._direction_font = direction_font
        self._verified_at = verified_at if verified_at is not None else self._verified_at
        self._rows = self._sorted(rows)
        self.endResetModel()

    def clear_sort(self) -> None:
        """Drop the user sort so the view keeps the natural folders-first order."""
        self._sort_column = None

    def retranslate(self) -> None:
        """Re-emit the header after a language change (even with no rows)."""
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.columnCount() - 1)

    def set_direction_font(self, font: QFont) -> None:
        self._direction_font = font
        if self._rows:
            self.dataChanged.emit(
                self.index(0, COL_DIRECTION),
                self.index(len(self._rows) - 1, COL_DIRECTION),
                [Qt.ItemDataRole.FontRole],
            )

    def rows(self) -> list[tuple[str, FileTransfer | None, dict]]:
        return self._rows

    def display_name(self, row: int) -> str | None:
        if 0 <= row < len(self._rows):
            return self._rows[row][0]
        return None

    # ── QAbstractTableModel ───────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMN_KEYS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            key = _COLUMN_KEYS[section]
            return tr(key) if key else ""
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        display_name, transfer, folder_data = self._rows[row]
        is_folder = transfer is None or transfer.filepath.endswith("/")

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(display_name, transfer, folder_data, is_folder, col)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._icon(transfer, is_folder) if col == COL_NAME else None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._alignment(col)
        if role == Qt.ItemDataRole.UserRole:
            return (
                self._row_progress(transfer, folder_data, is_folder)
                if col == COL_PROGRESS
                else None
            )
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(transfer, folder_data, is_folder)
        if role == Qt.ItemDataRole.FontRole:
            if col == COL_DIRECTION and self._direction_text(transfer, is_folder):
                return self._direction_font
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(transfer, folder_data, is_folder, col)
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self._sort_column = column
        self._sort_order = order
        self.beginResetModel()
        self._rows = self._sorted(self._rows)
        self.endResetModel()

    # ── Rendering helpers ─────────────────────────────────────────────────

    def _sorted(self, rows: list[tuple[str, FileTransfer | None, dict]]):
        """Apply the recorded sort (DisplayRole text, like QTableWidgetItem)."""
        if self._sort_column is None:
            return rows
        column = self._sort_column
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder

        def key(item: tuple[str, FileTransfer | None, dict]) -> str:
            name, transfer, folder_data = item
            is_folder = transfer is None or transfer.filepath.endswith("/")
            value = self._display_value(name, transfer, folder_data, is_folder, column)
            return "" if value is None else str(value)

        return sorted(rows, key=key, reverse=reverse)

    def _display_value(
        self,
        display_name: str,
        transfer: FileTransfer | None,
        folder_data: dict | None,
        is_folder: bool,
        col: int,
    ) -> str:
        if col == COL_PROGRESS:
            return ""
        if col == COL_NAME:
            return display_name
        if col == COL_TYPE:
            if is_folder:
                return tr("ftype.folder")
            return tr(_classify_file(transfer.filepath)[1]) if transfer else ""
        if col == COL_SIZE:
            if is_folder and folder_data:
                return tr("folder.items").format(count=folder_data.get("count", 0))
            if transfer and not is_folder:
                return format_bytes(transfer.size)
            return ""
        if col == COL_MODIFIED:
            mtime = (
                folder_data.get("mtime", 0.0)
                if folder_data
                else (transfer.mtime if transfer else 0.0)
            )
            return format_mtime(mtime)
        if col == COL_ETA:
            return format_duration(transfer.eta_seconds if transfer else None, style="compact")
        if col == COL_STATUS:
            return self._row_status(transfer, folder_data, is_folder)[0]
        if col == COL_SPEED:
            if is_folder:
                rate = folder_data.get("speed") if folder_data else None
            else:
                rate = transfer.speed_bps if transfer else None
            return f"{format_bytes(rate)}/s" if rate else ""
        if col == COL_DIRECTION:
            return self._direction_text(transfer, is_folder)
        return ""

    @staticmethod
    def _direction_text(transfer: FileTransfer | None, is_folder: bool) -> str:
        # Empty at rest: the dash placeholder is noise in a dense column, and
        # the Status column already carries the state.
        if transfer is None or is_folder or transfer.direction in ("", "—"):
            return ""
        return transfer.direction

    @staticmethod
    def _icon(transfer: FileTransfer | None, is_folder: bool):
        if is_folder or transfer is None:
            return get_icon("folder")
        return get_icon(_classify_file(transfer.filepath)[0])

    @staticmethod
    def _alignment(col: int) -> int | None:
        right = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if col == COL_DIRECTION:
            return int(Qt.AlignmentFlag.AlignCenter)
        if col in (COL_SIZE, COL_MODIFIED, COL_ETA, COL_SPEED):
            return right
        return None

    def _foreground(
        self, transfer: FileTransfer | None, folder_data: dict | None, is_folder: bool
    ) -> QColor:
        # "Local" is the resting state, not a status: only grey it while a
        # connection can compare the file.
        _, status = self._row_status(transfer, folder_data, is_folder)
        if status is TransferStatus.LOCAL and not self._connected:
            return self._default_text_color
        if self._synced_is_stale(status):
            return self._status_palette.get(TransferStatus.LOCAL, QColor(128, 128, 128))
        return self._status_palette.get(status, QColor(128, 128, 128))

    def _tooltip(
        self,
        transfer: FileTransfer | None,
        folder_data: dict | None,
        is_folder: bool,
        col: int,
    ) -> str | None:
        if col == COL_STATUS and self._synced_is_stale(
            self._row_status(transfer, folder_data, is_folder)[1]
        ):
            return self._stale_synced_tooltip()
        # A folder's neutral aggregate status hides the mix of planned
        # operations, so spell out what will actually happen.
        if col not in (COL_NAME, COL_STATUS) or not is_folder or not folder_data:
            return None
        ops = folder_data.get("ops") or {}
        parts = []
        for op_status, label_key in (
            (TransferStatus.TO_UPLOAD, "detail.to_upload"),
            (TransferStatus.TO_DOWNLOAD, "detail.to_download"),
            (TransferStatus.TO_DELETE, "detail.to_delete"),
            (TransferStatus.TO_RENAME, "detail.to_rename"),
        ):
            count = ops.get(op_status, 0)
            if count:
                parts.append(tr("folder.ops_item").format(operation=tr(label_key), count=count))
        return ", ".join(parts) if parts else None

    @staticmethod
    def _row_progress(
        transfer: FileTransfer | None, folder_data: dict | None, is_folder: bool
    ) -> int:
        """Progress percentage for a row (-1 = no measurable progress)."""
        if is_folder:
            if not folder_data:
                return -1
            status_priority = folder_data.get("status_priority", 100)
            return folder_data.get("progress", -1) if status_priority == 2 else -1
        if not transfer or transfer.status in _NO_PROGRESS_STATUSES:
            return -1
        if transfer.total_bytes <= 0:
            return -1
        return max(0, min(100, int(transfer.bytes_transferred / transfer.total_bytes * 100)))

    def _row_status(
        self, transfer: FileTransfer | None, folder_data: dict | None, is_folder: bool
    ) -> tuple[str, TransferStatus]:
        """Localized status text and its colour key for a row.

        ``SYNCED`` is a claim about the remote copy, so it is only asserted while
        a link exists. Offline the row keeps the last known state but says it is
        unverified: flipping it to ``LOCAL`` would be a different (and wrong)
        statement, since "Local" means the remote side was never compared.
        """
        if is_folder:
            if folder_data:
                status_priority = folder_data.get("status_priority", 6)
                status_key = folder_data.get("status_key", "folder.status.local")
            elif transfer is not None:
                # Empty folder: use its own status. A folder created by a remote
                # peer is marked SYNCED by _on_directory_created; without this it
                # would default to "Local" because it has no children to aggregate.
                status_priority = _STATUS_PRIORITY.get(transfer.status, 6)
                status_key = _FOLDER_STATUS_KEYS.get(status_priority, "folder.status.local")
            else:
                status_priority = 6
                status_key = "folder.status.local"
            status = _PRIORITY_TO_STATUS.get(status_priority, TransferStatus.LOCAL)
            text = tr(status_key)
        elif transfer:
            status = transfer.status
            status_key = _STATUS_TEXT_KEYS.get(status)
            text = tr(status_key) if status_key is not None else "?"
        else:
            return "", TransferStatus.LOCAL
        if status is TransferStatus.SYNCED and not self._connected:
            text = tr("detail.synced_stale")
        elif (
            not is_folder
            and transfer is not None
            and status is TransferStatus.SYNCED
            and 0 <= transfer.holders < transfer.devices
        ):
            # Partial coverage: the content is here and on some devices, not on
            # all of them. Numbers only, so the suffix needs no translation.
            text = f"{text} · {transfer.holders}/{transfer.devices}"
        return text, status

    def _synced_is_stale(self, status: TransferStatus) -> bool:
        """True when a ``SYNCED`` row currently has no link to back the claim."""
        return status is TransferStatus.SYNCED and not self._connected

    def _stale_synced_tooltip(self) -> str:
        """Explain that the "synced" label is the last known, unverified state."""
        if self._verified_at is None:
            return tr("tip.synced_stale_unverified")
        stamp = strftime("%H:%M", localtime(self._verified_at))
        return tr("tip.synced_stale_verified").format(time=stamp)


class FileTransferTable(QTableView):
    """Sortable table showing file transfers with hierarchical folder navigation."""

    row_selected = Signal(object)  # Emits FileTransfer or None
    row_deselected = Signal()  # Emitted when clicking on already selected row
    properties_requested = Signal(object)  # Emits FileTransfer for properties panel
    path_changed = Signal(str)  # Emitted when current navigation path changes
    send_selection_requested = Signal(str)  # Send the selected subtree (filepath)
    receive_selection_requested = Signal(str)  # Receive the selected subtree (filepath)
    # Emitted when files are dropped from the OS file manager: the accepted
    # absolute source paths, the destination folder relative to the share root,
    # and the requested action ("copy" or "move").
    files_dropped = Signal(list, str, str)

    # Persisted header layout: one QHeaderView state blob carrying the section
    # widths, the visual order and the hidden sections. Bump the version suffix
    # whenever the column set changes: restoreState does not validate the section
    # count and would apply a stale blob to the wrong sections.
    _HEADER_STATE_SETTINGS_KEY = "ui/file_table_header_state_v2"
    # Persisted "show hidden files" view option (display only).
    _SHOW_HIDDEN_SETTINGS_KEY = "ui/show_hidden_files"
    # Optional columns that start hidden: the row icon already conveys the type,
    # and the live rate matters only while a transfer runs.
    _DEFAULT_HIDDEN = (COL_TYPE, COL_SPEED)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transfers: dict[str, FileTransfer] = {}  # filepath -> transfer (flat)
        self._transfers_mutex = QMutex()  # Protects _transfers dict
        self._row_index: dict[str, int] = {}  # display key -> row index
        self._last_selected_row: int = -1
        # Restored across a file-panel reload (scoped Send/Receive): keeps the
        # user's row selected while the fresh scan fills the table.
        self._sticky_selection: str | None = None
        self._sticky_applied_row: int = -1
        self._base_directory: str = ""
        self._sync_active: bool = False  # A sync is running: Send/Receive disabled
        self._connected: bool = False  # A connection is active: "Local" rows are grey
        self._drop_enabled: bool = True  # Drops accepted (off while importing)
        # Last completed comparison with the remote (epoch seconds): the
        # unverified tooltip reports it. Kept across a disconnect on purpose.
        self._last_verified_at: float | None = None
        self._show_hidden: bool = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value(self._SHOW_HIDDEN_SETTINGS_KEY, False, bool)
        )
        # Column-layout state: the first populated refresh seeds sensible widths
        # from the content until the user saves a layout; `_restoring_columns`
        # suppresses the save handler while the layout is applied (it starts on
        # so the setup-time resizeSection calls are not persisted).
        self._columns_sized: bool = False
        self._restoring_columns: bool = True

        # Debounced layout save: a drag resizes (and emits) on every pixel.
        self._state_save_timer = QTimer(self)
        self._state_save_timer.setSingleShot(True)
        self._state_save_timer.setInterval(_STATE_SAVE_DELAY_MS)
        self._state_save_timer.timeout.connect(self._save_header_state)

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

        self._direction_font: QFont | None = None
        # Read before the header lays out: see has_saved_layout.
        self._saved_layout_on_start = self._has_persisted_state()
        self._model = FileTransferModel(self)
        self.setModel(self._model)

        self._setup_table()
        self._setup_drop()

    def retranslate(self) -> None:
        """Re-apply the localized column headers after a language change."""
        self._model.retranslate()
        self._ensure_readable_headers()

    def set_sync_active(self, active: bool) -> None:
        """Enable/disable the Send/Receive context entries (sync running)."""
        self._sync_active = active

    def set_connected(self, connected: bool) -> None:
        """Grey "Local" rows only while a connection is active.

        Without a connection every row is local, so the grey would read as a
        disabled list rather than as a status; use the default text colour.
        Disconnecting also re-renders the "Synced" rows as unverified (the
        timestamp is kept, so the tooltip can still say when they were checked).
        """
        if connected == self._connected:
            return
        self._connected = connected
        self.refresh_view()

    def mark_verified(self) -> None:
        """Record that the rows were just compared with the remote.

        Called when a preview or a sync cycle completes. Only the timestamp is
        stored: the rendered text follows the link state (``set_connected``) and
        every status change already refreshes the view.
        """
        self._last_verified_at = time()

    def refresh_fonts(self) -> None:
        """Re-apply the table, header and direction-glyph fonts."""
        from hsync_desktop.fonts import table_font, table_row_height

        self.setFont(table_font())
        self.verticalHeader().setDefaultSectionSize(table_row_height())
        self._direction_font = table_font()
        self._direction_font.setBold(True)
        self.horizontalHeader().setFont(table_font())
        self._ensure_readable_headers()
        self._model.set_direction_font(self._direction_font)

    def _setup_table(self) -> None:
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.refresh_fonts()
        from PySide6.QtCore import QSize

        self.setIconSize(QSize(16, 16))

        # Column sizing and behavior
        header = self.horizontalHeader()
        header.setHighlightSections(False)  # Prevent bold header on row selection
        header.setSectionsMovable(True)  # Allow drag-and-drop column reordering
        # Name is the row identity: keep it leading whatever the user drags.
        header.setFirstSectionMovable(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DIRECTION, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_MODIFIED, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_PROGRESS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_ETA, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_SPEED, QHeaderView.ResizeMode.Interactive)
        # Keep every column wide enough to stay readable when dragged narrow.
        header.setMinimumSectionSize(_MIN_COLUMN_WIDTH)

        # Progress bar delegate and default column width
        self.setItemDelegateForColumn(COL_PROGRESS, ProgressBarDelegate(self))
        header.resizeSection(COL_PROGRESS, 130)

        # Enable context menu on header for column visibility
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)
        # Persist the user's layout: a drag resizes, a header drag reorders, a
        # handle double-click fits one column.
        header.sectionResized.connect(self._on_section_resized)
        header.sectionMoved.connect(self._schedule_header_state_save)
        header.sectionHandleDoubleClicked.connect(self._fit_column_to_contents)

        # Enable context menu on table rows
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_file_context_menu)

        # QTableView has no cell(row, col) convenience signals: adapt the
        # QModelIndex-based ones to the row/column handlers.
        self.clicked.connect(self._on_index_clicked)
        self.doubleClicked.connect(self._on_index_double_clicked)

        # Header-click sorting, but keep the natural folders-first order until
        # the user actually sorts: ``setSortingEnabled`` immediately sorts by the
        # current indicator, which is discarded right after.
        self.setSortingEnabled(True)

        # Optional columns start hidden and the widths are seeded from the content
        # on the first populated refresh, unless the user already saved a layout.
        self._restore_header_state()
        self._restore_sort_indicator()
        # A saved layout can predate a translation or a font change: never show a
        # header clipped on both sides.
        self._ensure_readable_headers()
        # From here on, user-driven layout changes are persisted.
        self._restoring_columns = False

    def _apply_default_columns(self) -> None:
        """Default column set of a profile that never saved a layout."""
        header = self.horizontalHeader()
        hidden = {_COLUMN_KEYS[col] for col in self._DEFAULT_HIDDEN}
        for col, key in enumerate(_COLUMN_KEYS):
            if key:
                header.setSectionHidden(col, key in hidden)

    def _restore_header_state(self) -> None:
        """Apply the saved header layout: widths, order, hidden sections.

        Falls back to the defaults when nothing is stored or the blob cannot be
        restored. Name is always shown: it carries the row identity and hiding it
        would leave no stretch section.
        """
        raw = QSettings(SETTINGS_ORG, SETTINGS_APP).value(
            self._HEADER_STATE_SETTINGS_KEY, QByteArray()
        )
        if isinstance(raw, QByteArray):
            state = raw
        elif isinstance(raw, (bytes, bytearray)):
            state = QByteArray(bytes(raw))
        else:
            state = QByteArray()
        restored = False
        if not state.isEmpty():
            restored = self.horizontalHeader().restoreState(state)
        if not restored:
            self._apply_default_columns()
        self.horizontalHeader().showSection(COL_NAME)

    def _restore_sort_indicator(self) -> None:
        """Start unsorted even when the restored blob carries a sort indicator.

        ``restoreState`` re-applies the indicator without sorting the model, so it
        has to be cleared: no order is applied until the user clicks a header.
        """
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        # The view reacts to the -1 indicator by sorting on section -1: clear the
        # recorded sort again so the model really keeps the natural order.
        self._model.clear_sort()

    def _save_header_state(self) -> None:
        """Persist the whole header layout in one blob."""
        if self._restoring_columns:
            return
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(
            self._HEADER_STATE_SETTINGS_KEY, self.horizontalHeader().saveState()
        )

    def _schedule_header_state_save(self, *_args) -> None:
        """Coalesce the writes of a drag, which resizes on every pixel."""
        if not self._restoring_columns:
            self._state_save_timer.start()

    def _on_section_resized(self, logical: int, old: int, new: int) -> None:
        """Persist the new layout after a user drag.

        Name is ``Stretch``: it also resizes when the window grows, which is not a
        layout the user chose. Skipping it (on top of the debounce) keeps a plain
        window resize from creating a saved layout, so the first-run Name floor
        survives the whole session. The data floor needs no clamp here: it is the
        header's minimum section size.
        """
        if self._restoring_columns or logical == COL_NAME:
            return
        self._schedule_header_state_save()

    def _fit_column_to_contents(self, logical: int) -> None:
        """Fit one data column to its content (header handle double-click)."""
        if logical == COL_NAME:
            return
        header = self.horizontalHeader()
        width = max(self.sizeHintForColumn(logical), header.sectionSizeHint(logical)) + 8
        header.resizeSection(logical, max(width, _MIN_COLUMN_WIDTH))

    @staticmethod
    def _has_persisted_state() -> bool:
        """Whether this profile already stored a header layout."""
        raw = QSettings(SETTINGS_ORG, SETTINGS_APP).value(
            FileTransferTable._HEADER_STATE_SETTINGS_KEY, QByteArray()
        )
        if isinstance(raw, QByteArray):
            return not raw.isEmpty()
        return isinstance(raw, (bytes, bytearray)) and bool(raw)

    def has_saved_layout(self) -> bool:
        """True when this profile already had a persisted header layout.

        Captured at construction: the first layout pass resizes sections (and can
        therefore save) before any user interaction, so reading the key later
        cannot tell a first run from a saved one.
        """
        return self._saved_layout_on_start

    def name_floor(self) -> int:
        """Minimum width the Name column keeps when the window is sized."""
        return _MIN_NAME_WIDTH if self.has_saved_layout() else _MIN_NAME_FIRST_RUN

    def required_viewport_width(self) -> int:
        """Viewport width the table needs to keep its columns readable.

        Used by the window's one-shot startup fit
        (``hsync_desktop.main_window.window::MainWindow._fit_table_width``).
        Qt absorbs a shortage by shrinking the stretch column (Name) down to
        the global minimum section size instead of widening the scroll range,
        so ``horizontalScrollBar`` reports almost no deficit even when file
        names are unusable. The requirement is therefore built from the
        visible fixed-width sections plus the Name floor.
        """
        header = self.horizontalHeader()
        total = 0
        for col in range(self._model.columnCount()):
            if header.isSectionHidden(col) or col == COL_NAME:
                continue
            total += header.sectionSize(col)
        if not header.isSectionHidden(COL_NAME):
            total += max(header.sectionSize(COL_NAME), self.name_floor())
        return total

    def _ensure_readable_headers(self) -> None:
        """Widen any section that cannot show its own header label.

        Header labels are centred, so a section narrower than its text clips the
        label on both sides. Interactive columns start at the style default and
        a persisted layout may predate a translation, so every visible section
        is clamped to its header hint; the user can still narrow it afterwards.
        """
        header = self.horizontalHeader()
        for col in range(self._model.columnCount()):
            if col == COL_NAME or header.isSectionHidden(col):
                continue
            needed = header.sectionSizeHint(col) + 8
            if header.sectionSize(col) < needed:
                header.resizeSection(col, needed)

    def _size_columns_to_contents(self) -> None:
        """Seed sensible widths from the content, once, before user resizing.

        ``Interactive`` columns have no default width, so the first populated
        refresh fits them to their contents (like the old ``ResizeToContents``
        behaviour); afterwards the user's widths are kept. Only the data columns
        are touched: Icon stays fixed, Name stretches and Progress keeps its
        default width.
        """
        if self._columns_sized or self._model.rowCount() == 0:
            return
        header = self.horizontalHeader()
        was_restoring = self._restoring_columns
        self._restoring_columns = True
        try:
            for col in _FITTED_COLUMNS:
                width = max(self.sizeHintForColumn(col), header.sectionSizeHint(col)) + 8
                header.resizeSection(col, max(width, _MIN_COLUMN_WIDTH))
            self._columns_sized = True
        finally:
            self._restoring_columns = was_restoring

    def _show_header_context_menu(self, pos) -> None:
        """Show context menu to toggle column visibility."""
        menu = QMenu(self)
        header = self.horizontalHeader()

        for col, key in enumerate(_COLUMN_KEYS):
            if col == COL_NAME:
                # Name is the row identity: it never hides.
                continue
            action = QAction(tr(key), menu)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(col))
            # Use default argument to capture col value
            action.toggled.connect(lambda checked, c=col: self._toggle_column(c, checked))
            menu.addAction(action)

        menu.addSeparator()
        reset_action = QAction(tr("file.reset_columns"), menu)
        reset_action.setToolTip(tr("tip.reset_columns"))
        reset_action.triggered.connect(self._reset_columns)
        menu.addAction(reset_action)

        menu.addSeparator()
        hidden_action = QAction(tr("file.show_hidden"), menu)
        hidden_action.setCheckable(True)
        hidden_action.setChecked(self._show_hidden)
        hidden_action.setToolTip(tr("tip.show_hidden"))
        hidden_action.toggled.connect(self.set_show_hidden)
        menu.addAction(hidden_action)

        menu.exec(header.mapToGlobal(pos))

    def _toggle_column(self, col: int, visible: bool) -> None:
        """Toggle visibility of a column, keeping its header readable when shown."""
        header = self.horizontalHeader()
        header.setSectionHidden(col, not visible)
        if visible:
            if header.sectionSize(col) < _MIN_COLUMN_WIDTH:
                self._fit_column_to_contents(col)
            # A hidden section keeps whatever width it had when it was hidden, so
            # a stale narrow one would clip its (centred) label on both sides.
            self._ensure_readable_headers()
        self._save_header_state()

    def _reset_columns(self) -> None:
        """Restore the default column layout: order, visibility and widths."""
        QSettings(SETTINGS_ORG, SETTINGS_APP).remove(self._HEADER_STATE_SETTINGS_KEY)
        header = self.horizontalHeader()
        was_restoring = self._restoring_columns
        self._restoring_columns = True
        try:
            self._apply_default_columns()
            for col in range(self._model.columnCount()):
                header.moveSection(header.visualIndex(col), col)
        finally:
            self._restoring_columns = was_restoring
        # Re-fit the widths from the current content, once. Nothing is re-saved:
        # the next launch must start again from the defaults plus this fit, exactly
        # what a reset asks for (and the roomier first-run Name floor returns).
        self._columns_sized = False
        self._size_columns_to_contents()

    def set_show_hidden(self, show: bool) -> None:
        """Show or hide dot-prefixed entries (view only, never sync state)."""
        if show == self._show_hidden:
            return
        self._show_hidden = show
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(self._SHOW_HIDDEN_SETTINGS_KEY, show)
        self._cached_items = None
        self.refresh_view()

    def _on_index_clicked(self, index: QModelIndex) -> None:
        if index.isValid():
            self._on_cell_clicked(index.row(), index.column())

    def _on_index_double_clicked(self, index: QModelIndex) -> None:
        if index.isValid():
            self._on_cell_double_clicked(index.row(), index.column())

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        """Defer single-click action to distinguish from double-click."""
        self._pending_click_row = row
        self._click_timer.start()

    def _on_single_click_confirmed(self) -> None:
        """Handle confirmed single click: toggle selection on re-click."""
        self._clear_sticky_selection()
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
        self._clear_sticky_selection()
        self._last_selected_row = row
        display_name = self._model.display_name(row)
        if display_name is None:
            return
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

    def hideEvent(self, event: QHideEvent) -> None:
        """Flush a layout save still waiting out its debounce."""
        if self._state_save_timer.isActive():
            self._state_save_timer.stop()
            self._save_header_state()
        super().hideEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Enter/Return opens the selected row (reliable folder navigation).

        Double-click keeps working, but a rebuild during a busy sync can swallow
        it; the keyboard path always opens the folder under the cursor.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            row = self.currentIndex().row()
            if row >= 0:
                self._on_cell_double_clicked(row, COL_NAME)
                event.accept()
                return
        super().keyPressEvent(event)

    def set_base_directory(self, directory: str) -> None:
        """Set the base directory for resolving absolute file paths."""
        self._base_directory = directory
        # Reset navigation when base directory changes
        self._current_path = ""
        self._nav_history = [""]
        self._nav_index = 0

    # ── Drag & drop import ────────────────────────────────────────────────

    def set_drop_enabled(self, enabled: bool) -> None:
        """Accept or refuse drops (refused while an import is running)."""
        self._drop_enabled = enabled

    def _setup_drop(self) -> None:
        """Accept drops from the OS file manager (drop-only, no internal drag).

        The table is not a drag source: only external drops are accepted, and the
        destination is resolved from the row under the cursor (a folder row) or
        the folder currently shown.
        """
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def _folder_rel_at_row(self, row: int) -> str | None:
        """The folder path of ``row`` when it is a folder, else ``None``.

        Folders are not first-class rows: a row is a folder when any tracked
        path sits under it (the same test the double-click navigation uses).
        """
        display_name = self._model.display_name(row)
        if display_name is None:
            return None
        full_path = f"{self._current_path}/{display_name}" if self._current_path else display_name
        for transfer in self._transfers.values():
            if transfer.filepath == full_path + "/" or transfer.filepath.startswith(
                full_path + "/"
            ):
                return full_path
        return None

    def _drop_target_rel(self, pos) -> str:
        """Destination folder (relative to the share root) for a drop at ``pos``."""
        index = self.indexAt(pos)
        if index.isValid():
            folder = self._folder_rel_at_row(index.row())
            if folder is not None:
                return folder
        return self._current_path

    @staticmethod
    def _drop_sources(event) -> list[str]:
        """Local filesystem paths carried by the drop (empty when none)."""
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        sources: list[str] = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                sources.append(local)
        return sources

    def _accepts_drop(self, event) -> bool:
        """True when this drop can be imported where it is being released."""
        if not self._drop_enabled or not self._base_directory:
            return False
        sources = self._drop_sources(event)
        if not sources:
            return False
        target = self._drop_target_rel(event.position().toPoint())
        accepted, _ = validate_sources(self._base_directory, target, sources)
        return bool(accepted)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._accepts_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._accepts_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        if not self._drop_enabled or not self._base_directory:
            event.ignore()
            return
        sources = self._drop_sources(event)
        target = self._drop_target_rel(event.position().toPoint())
        accepted, _ = validate_sources(self._base_directory, target, sources)
        if not accepted:
            event.ignore()
            return
        action = "move" if event.proposedAction() == Qt.DropAction.MoveAction else "copy"
        self.files_dropped.emit(accepted, target, action)
        # The import performs the move itself, so a "move" is reported to the
        # source as a copy: that stops a file manager from deleting a source we
        # already moved away (and a plain copy keeps the original in place).
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

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
        self._clear_sticky_selection()
        # Add to history (truncate forward history if navigating from middle)
        self._nav_index += 1
        self._nav_history = [*self._nav_history[: self._nav_index], path]
        self._current_path = path
        self.refresh_view()
        self.path_changed.emit(path)

    def navigate_back(self) -> None:
        if self._nav_index > 0:
            self._clear_sticky_selection()
            self._nav_index -= 1
            self._current_path = self._nav_history[self._nav_index]
            self.refresh_view()
            self.path_changed.emit(self._current_path)

    def navigate_forward(self) -> None:
        """Navigate to the next folder in history."""
        if self._nav_index < len(self._nav_history) - 1:
            self._clear_sticky_selection()
            self._nav_index += 1
            self._current_path = self._nav_history[self._nav_index]
            self.refresh_view()
            self.path_changed.emit(self._current_path)

    def navigate_up(self) -> None:
        """Navigate to parent folder."""
        if self._current_path:
            parent = str(Path(self._current_path).parent)
            self.navigate_to("" if parent == "." else parent)

    def restore_view(self, path: str, selected: str | None) -> None:
        """Reopen ``path`` and select ``selected`` after a panel reload.

        ``Send now`` / ``Receive now`` reload the local tree before starting the
        one-shot; this puts the user back where they were instead of jumping to
        the root. The selection stays applied across the asynchronous scan's
        refreshes until the user navigates or selects another row.
        """
        if path and path != self._current_path:
            self.navigate_to(path)  # clears any previous sticky selection
        self._sticky_selection = selected
        self._sticky_applied_row = -1
        self.refresh_view()

    def _clear_sticky_selection(self) -> None:
        self._sticky_selection = None
        self._sticky_applied_row = -1

    def _apply_sticky_selection(self) -> None:
        """Re-select the restored row once it is present at the current level."""
        if self._sticky_selection is None:
            return
        # Resolve from the visible rows (model order), not _row_index: the map is
        # rebuilt with the rows, but the display name is the stable key the user
        # restored.
        row = None
        for candidate in range(self._model.rowCount()):
            if self._model.display_name(candidate) == self._sticky_selection:
                row = candidate
                break
        if row is None:
            return
        self._last_selected_row = row
        self.selectRow(row)
        if row != self._sticky_applied_row:
            self._sticky_applied_row = row
            transfer = self._get_transfer_at_row(row)
            if transfer:
                self.row_selected.emit(transfer)

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
            remainder = filepath[prefix_len:] if prefix else filepath
            remainder_clean = remainder.rstrip("/")
            if not remainder_clean:
                continue
            head, sep, _rest = remainder_clean.partition("/")
            if not self._show_hidden and head.startswith("."):
                # Dot-prefixed item: hidden by name, together with its subtree.
                continue
            if sep:
                # The folder row exists even when every child is view-hidden;
                # only visible children contribute to its counts and size.
                children = folder_files.setdefault(head, [])
                if self._show_hidden or not has_dot_segment(remainder_clean):
                    children.append(transfer)
            else:
                items[head] = (transfer, {})

        for folder_name, files in folder_files.items():
            folder_data = self._aggregate_folder(files)
            if folder_name in items:
                existing_transfer, _ = items[folder_name]
                items[folder_name] = (existing_transfer, folder_data)
            else:
                items[folder_name] = (None, folder_data)

        def sort_key(item: tuple[str, tuple[FileTransfer | None, dict]]) -> tuple[int, str]:
            name, (transfer, _folder_data) = item
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
        ops = {
            TransferStatus.TO_UPLOAD: 0,
            TransferStatus.TO_DOWNLOAD: 0,
            TransferStatus.TO_DELETE: 0,
            TransferStatus.TO_RENAME: 0,
        }

        for f in files:
            if not f.filepath.endswith("/"):
                total_size += f.total_bytes
                total_transferred += f.bytes_transferred
            max_mtime = max(max_mtime, f.mtime)
            p = _STATUS_PRIORITY.get(f.status, 100)
            status_priority = min(status_priority, p)
            if f.status in ops:
                ops[f.status] += 1

        status_key = _FOLDER_STATUS_KEYS.get(status_priority, "folder.status.local")
        progress = int(total_transferred / total_size * 100) if total_size > 0 else -1
        # Aggregate throughput of the folder's in-flight children
        # (speed_bps is None for anything not transferring).
        speed = sum(f.speed_bps or 0.0 for f in files)

        return {
            "count": count,
            "total_size": total_size,
            "mtime": max_mtime,
            "progress": progress,
            "status_key": status_key,
            "status_priority": status_priority,
            "speed": speed,
            # Planned-operation breakdown for the folder tooltip: a folder can
            # mix uploads/downloads/deletes, so the neutral aggregate status
            # alone does not say what will actually happen.
            "ops": {status: n for status, n in ops.items() if n},
        }

    def _schedule_refresh(self) -> None:
        """Schedule a debounced refresh of the view."""
        self._refresh_pending = True
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _do_refresh_view(self) -> None:
        """Execute the pending refresh, unless a click is pending.

        During an active sync the table is rebuilt every few hundred ms.
        Replacing the item under the pointer between the two clicks of a
        double-click defeats folder navigation, so the rebuild waits for the
        click window to close.
        """
        if self._click_timer.isActive():
            self._refresh_pending = True
            self._refresh_timer.start(QApplication.doubleClickInterval())
            return
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

        # Constants for the whole refresh: the model renders every row from them.
        default_text_color = self.palette().color(QPalette.ColorRole.Text)
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        status_palette = STATUS_COLORS_DARK if dark else STATUS_COLORS

        self._model.set_rows(
            items,
            connected=self._connected,
            default_text_color=default_text_color,
            status_palette=status_palette,
            direction_font=self._direction_font,
            verified_at=self._last_verified_at,
        )
        # Rebuild the display-key index from the model's final (possibly sorted)
        # row order so it never disagrees with what is on screen.
        self._row_index = {
            name: index for index, (name, _transfer, _folder) in enumerate(self._model.rows())
        }
        self._last_selected_row = -1

        # Fit the columns to their content once, before any user resizing.
        self._size_columns_to_contents()
        self._apply_sticky_selection()

    def _get_transfer_at_row(self, row: int) -> FileTransfer | None:
        """Return the FileTransfer for the given row."""
        display_name = self._model.display_name(row)
        if display_name is None:
            return None
        full_path = f"{self._current_path}/{display_name}" if self._current_path else display_name
        return self._transfers.get(full_path) or self._transfers.get(full_path + "/")

    def _absolute_path(self, transfer: FileTransfer) -> str:
        """Build the absolute path of a transfer's file."""
        return os.path.join(self._base_directory, transfer.filepath)

    def copy_path(self, transfer: FileTransfer, *, relative: bool = False) -> str:
        """Copy the entry's path to the clipboard and return the copied text.

        ``relative`` copies the path inside the shared folder (the table's base
        directory); the default copies the absolute one. Both go through
        ``os.path.normpath`` because the wire keys use ``/`` separators and a
        folder key ends with ``/``: without it the host would get mixed
        separators and a trailing one.

        Used by the context menu and by the window's File menu
        (``main_window/actions.py::ActionsMixin._menu_file_copy_path``).
        """
        text = os.path.normpath(transfer.filepath if relative else self._absolute_path(transfer))
        QGuiApplication.clipboard().setText(text)
        return text

    # ── Safety gating for file actions ───────────────────────────────────

    def _entry_is_busy(self, transfer: FileTransfer) -> bool:
        """True when the engine owns ``transfer``'s path, or any below a folder.

        Resting rows (``LOCAL``/``SYNCED``/``ERROR``/``COMPLETED``) are safe to
        mutate; planned (``TO_*``), in-flight (``DOWNLOADING``/``UPLOADING``)
        and legacy (``QUEUED``/``TRANSFERRING``) ones must wait for the engine.
        A folder row's transfer carries an aggregate status that can look
        resting while a descendant is transferring, so a folder is checked
        against every entry below it.
        """
        if transfer.status in _BUSY_STATUSES:
            return True
        # Child keys all start with the folder key (``dir/f`` vs ``folder2/f``
        # cannot collide), so a prefix scan over the flat map is the whole test.
        return transfer.filepath.endswith("/") and self._subtree_is_busy(transfer.filepath)

    def _subtree_is_busy(self, folder_key: str) -> bool:
        """True when any row under the folder is busy (prefix scan)."""
        return any(
            path.startswith(folder_key) and path != folder_key
            for path, transfer in self._transfers.items()
            if transfer.status in _BUSY_STATUSES
        )

    def _entry_materialized(self, transfer: FileTransfer) -> bool:
        """True when the entry is expected to exist on disk right now.

        Incoming rows have no local file until the transfer commits and a
        DELETED row is already gone, so Copy to cannot work on them.
        """
        return transfer.status not in _UNMATERIALIZED_STATUSES

    def _copy_enabled(self, transfer: FileTransfer) -> bool:
        """True when Copy to can produce a real snapshot of the entry.

        The source must exist on disk (see ``_entry_materialized``) and a
        folder must not be busy below it: the copy would sweep the engine's
        ``.part`` staging files and export an incomplete tree. A busy *file*
        row stays copyable — the local file it reads is the snapshot asked for.
        """
        if not self._entry_materialized(transfer):
            return False
        return not (transfer.filepath.endswith("/") and self._entry_is_busy(transfer))

    # ── File context menu ─────────────────────────────────────────────────

    def _show_file_context_menu(self, pos) -> None:
        """Show right-click context menu for a file row."""
        menu = self._build_file_context_menu(pos)
        if menu is not None:
            menu.exec(self.viewport().mapToGlobal(pos))

    def _build_file_context_menu(self, pos) -> QMenu | None:
        """Build the row context menu (``None`` when the click misses a row).

        Split from the ``exec`` so the entry order can be asserted in tests.
        """
        index = self.indexAt(pos)
        if not index.isValid():
            return None
        row = index.row()
        transfer = self._get_transfer_at_row(row)

        if not transfer:
            display_name = self._model.display_name(row)
            if display_name is None:
                return None
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
        menu.addAction(tr("ctx.open_containing"), lambda: self._ctx_open_containing(transfer))
        if not is_dir:
            menu.addAction(tr("ctx.open_with"), lambda: self._ctx_open_with(transfer))
        menu.addSeparator()
        send_action = menu.addAction(
            tr("action.send_now"), lambda: self.send_selection_requested.emit(transfer.filepath)
        )
        receive_action = menu.addAction(
            tr("action.receive_now"),
            lambda: self.receive_selection_requested.emit(transfer.filepath),
        )
        send_action.setEnabled(not self._sync_active)
        receive_action.setEnabled(not self._sync_active)
        menu.addSeparator()
        entry_busy = self._entry_is_busy(transfer)
        copy_to_action = menu.addAction(tr("ctx.copy_to"), lambda: self._ctx_copy_to(transfer))
        copy_to_action.setEnabled(self._copy_enabled(transfer))
        menu.addAction(tr("ctx.copy_path"), lambda: self.copy_path(transfer))
        menu.addAction(
            tr("ctx.copy_path_relative"), lambda: self.copy_path(transfer, relative=True)
        )
        rename_action = menu.addAction(tr("ctx.rename"), lambda: self._ctx_rename(transfer))
        rename_action.setEnabled(not entry_busy)
        menu.addSeparator()
        trash_action = menu.addAction(tr("ctx.trash"), lambda: self._ctx_trash(transfer))
        trash_action.setEnabled(not entry_busy)
        menu.addSeparator()
        menu.addAction(tr("ctx.properties"), lambda: self._ctx_properties(transfer))
        return menu

    def _ctx_open(self, transfer: FileTransfer) -> None:
        """Open the entry: navigate into a folder, open a file with the default app."""
        if transfer.filepath.endswith("/"):
            # A folder is opened by navigating into it inside the file panel
            # (same as a double-click), not by launching the OS file manager.
            self.navigate_to(transfer.filepath)
            return
        abs_path = self._absolute_path(transfer)
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))
        except Exception as exc:
            QMessageBox.warning(
                self, tr("ctx.error_title"), tr("ctx.error_open").format(error=str(exc))
            )

    def _ctx_open_containing(self, transfer: FileTransfer) -> None:
        """Reveal the entry in the OS file manager (its containing folder)."""
        abs_path = self._absolute_path(transfer)
        containing = os.path.dirname(abs_path.rstrip("/"))
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(containing))
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
        """Copy the file or directory to a user-chosen directory.

        Guarded like the context menu (``_copy_enabled``): the window File menu
        also lands here, whose enabled state can lag a transfer that only just
        started, so the snapshot is never taken off a missing or incomplete
        entry.
        """
        if not self._copy_enabled(transfer):
            return
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
        """Show a rename dialog and rename the file on disk.

        No-op while the engine owns the path (see ``_entry_is_busy``): the
        context menu greys the action and the window File menu shares the
        guard, so a rename can never race a transfer on the same path.
        """
        if self._entry_is_busy(transfer):
            return
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
        # Reject names that contain path separators or traversal components
        # (slash, backslash, "..", null byte), preventing arbitrary filesystem
        # escape from the sync directory.
        if (
            os.path.sep in new_name
            or (os.path.altsep is not None and os.path.altsep in new_name)
            or ".." in new_name
            or "\x00" in new_name
        ):
            QMessageBox.warning(
                self,
                "Invalid Name",
                "The file name cannot contain path separators or traversal sequences.",
            )
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
        """Move the file to the system trash.

        No-op while the engine owns the path: trashing a file with a transfer
        in flight resurrects it at the next commit, and deleting a folder with
        transfers inside would orphan the in-flight rows.
        """
        if self._entry_is_busy(transfer):
            return
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

    def clear_transfers(self) -> None:
        """Clear all transfers from the table."""
        with QMutexLocker(self._transfers_mutex):
            self._transfers.clear()
        self._cached_items = None  # Invalidate cache
        self._row_index.clear()
        self._clear_sticky_selection()
        self._current_path = ""
        self._nav_history = [""]
        self._nav_index = 0
        self._model.set_rows(
            [],
            connected=self._connected,
            default_text_color=self.palette().color(QPalette.ColorRole.Text),
            status_palette=STATUS_COLORS,
            direction_font=self._direction_font,
        )

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
        *,
        holders: int = -1,
        devices: int = -1,
        preview: bool = False,
    ) -> None:
        """Update or add a file with the given status.

        ``holders``/``devices`` carry the device coverage a serving pass reports
        (-1 when the pass has no per-device view). ``preview`` marks a dry-run
        status from the preview pass: it must never downgrade a row that is
        actively transferring, or a preview triggered by a reconnect would hide
        the live progress of an in-flight transfer.
        """
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
                if preview and t.status in (
                    TransferStatus.DOWNLOADING,
                    TransferStatus.UPLOADING,
                ):
                    return
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
                t.holders = holders
                t.devices = devices
            else:
                t = FileTransfer(
                    filepath=filepath,
                    direction=direction,
                    size=size,
                    status=transfer_status,
                    mtime=mtime,
                    client_cid=client_cid,
                    client_ip=client_ip,
                    holders=holders,
                    devices=devices,
                )
                self._transfers[filepath] = t
        self._cached_items = None  # Invalidate cache
        # Preview/status events arrive one per file; together with the O(rows)
        # rebuild this was quadratic (one full refresh per file). Coalesce them
        # through the same debounce the batch/progress paths already use.
        self._schedule_refresh()

    def mark_deleted(self, filepath: str) -> None:
        """Mark a file as deleted."""
        with QMutexLocker(self._transfers_mutex):
            if filepath in self._transfers:
                t = self._transfers[filepath]
                t.status = TransferStatus.DELETED
                t.direction = "✕"
        self.refresh_view()
        # Show the marker for a moment, then remove the row. The timer is
        # parented to the table so it is destroyed with the widget instead of
        # firing into a deleted C++ object (window closed or test teardown
        # before the delay elapses).
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._remove_file(filepath))
        timer.start(3000)

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
        old_mtime = 0.0
        with QMutexLocker(self._transfers_mutex):
            if old_path in self._transfers:
                old_size = self._transfers[old_path].size
                old_mtime = self._transfers[old_path].mtime
                del self._transfers[old_path]
            if new_path in self._transfers:
                t = self._transfers[new_path]
                t.status = TransferStatus.SYNCED
                t.direction = "⇄"
                if old_size:
                    t.size = old_size
                if mtime:
                    t.mtime = mtime
                elif old_mtime:
                    # Preserve the previous mtime when the filesystem read
                    # failed (a rename does not change it).
                    t.mtime = old_mtime
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
                    mtime=mtime or old_mtime,
                    client_cid=client_cid,
                    client_ip=client_ip,
                )
                self._transfers[new_path] = t
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def remove_transfer(self, filepath: str) -> None:
        """Remove a transfer immediately."""
        self._remove_file(filepath)

    def remove_transfers(self, filepaths: Iterable[str]) -> None:
        """Remove many rows under one lock with a single debounced rebuild.

        The consistency pass detects local deletions in a loop; removing them
        one by one would rebuild the whole table per row.
        """
        changed = False
        with QMutexLocker(self._transfers_mutex):
            for filepath in filepaths:
                if filepath in self._transfers:
                    del self._transfers[filepath]
                    changed = True
        if changed:
            self._cached_items = None  # Invalidate cache
            self._schedule_refresh()

    def update_transfer_progress(
        self, filepath: str, bytes_transferred: int, total_bytes: int, op: str = ""
    ) -> None:
        """Update — or create — the row of an in-flight transfer.

        A download writes a file that does not exist locally yet, so no scan
        row exists for it: without creating the row here every progress event
        of a received file would be dropped and the file would only appear
        once completed.

        Args:
            filepath: The file path to update
            bytes_transferred: Number of bytes transferred so far
            total_bytes: Bytes the transfer moves in total (compressed size for
                a compressed upload, payload size for a delta download)
            op: ``download``/``upload`` from the client; empty when unknown
        """
        direction = "↑" if op == "upload" else "↓"
        with QMutexLocker(self._transfers_mutex):
            t = self._transfers.get(filepath)
            if t is None:
                t = FileTransfer(filepath=filepath, direction=direction)
                self._transfers[filepath] = t
            if op:
                t.direction = direction
            elif t.direction not in ("↓", "↑"):
                # Older clients send no ``op``: fall back to the row's arrow.
                t.direction = direction
            if t.status not in (TransferStatus.DOWNLOADING, TransferStatus.UPLOADING):
                t.start_transfer(t.direction)
            if total_bytes > 0:
                t.progress_total = total_bytes
                # Never overwrite a known on-disk size: a compressed upload
                # reports the smaller wire size as its total.
                if t.size <= 0:
                    t.size = total_bytes
            t.note_progress(bytes_transferred)
        self._cached_items = None  # Invalidate cache
        self._schedule_refresh()

    def mark_failed(self, filepath: str) -> None:
        """Flag a row whose transfer gave up, so no stale progress bar remains."""
        with QMutexLocker(self._transfers_mutex):
            t = self._transfers.get(filepath)
            if t is None:
                t = FileTransfer(filepath=filepath, direction="—")
                self._transfers[filepath] = t
            t.status = TransferStatus.ERROR
        self._cached_items = None  # Invalidate cache
        self.refresh_view()

    def clear_transient_progress(self, base_path: str = "") -> None:
        """Drop in-flight markers left behind when the engine stops.

        A transfer interrupted by Stop or a crash never reports an outcome, so
        its row would keep showing a progress bar. Rows whose file reached the
        disk fall back to LOCAL; the others are removed — there is nothing to
        show once the partial file is gone.
        """
        with QMutexLocker(self._transfers_mutex):
            stale = [
                key
                for key, t in self._transfers.items()
                if t.status in (TransferStatus.DOWNLOADING, TransferStatus.UPLOADING)
            ]
            for key in stale:
                exists = False
                if base_path:
                    try:
                        exists = os.path.exists(os.path.join(base_path, key))
                    except (OSError, ValueError):
                        exists = False
                if not exists:
                    del self._transfers[key]
                    continue
                self._transfers[key].stop_transfer()
        if stale:
            self._cached_items = None  # Invalidate cache
            self.refresh_view()

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Top-level file transfer panel: navigation bar, transfer table and detail panel."""

from __future__ import annotations

import html
import os
import sys
from pathlib import Path

from hsync_common.ignore import IgnoreMatcher
from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import CONSISTENCY_CHECK_INTERVAL_MS
from hsync_desktop.file_panel.detail_panel import FileDetailPanel
from hsync_desktop.file_panel.filter import ignore_file_stamp, is_synced_entry
from hsync_desktop.file_panel.models import FileTransfer, TransferStatus
from hsync_desktop.file_panel.overlay import LoadingOverlay
from hsync_desktop.file_panel.transfer_table import FileTransferTable
from hsync_desktop.file_panel.workers import DirectoryScanWorker
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon as get_icon
from hsync_desktop.ui.loader import load_ui_widget

# Explorer's breadcrumb separates segments with ">", while GNOME Files and
# macOS textual paths use "/". The separator never leads the breadcrumb: the
# root icon is the first segment, so a leading "/" would read as an absolute
# path.
_BREADCRUMB_SEPARATORS = {"win32": " > ", "default": " / "}
_NAV_ICON_PX = 20
# Click target around the glyph, at the WCAG 2.2 target-size minimum.
_NAV_ICON_BOX_PX = 24


def _platform() -> str:
    """The current platform string (a seam for tests)."""
    return sys.platform


def _breadcrumb_separator() -> str:
    """The breadcrumb separator matching the host file manager."""
    return _BREADCRUMB_SEPARATORS.get(_platform(), _BREADCRUMB_SEPARATORS["default"])


def _scandir_child_prefix(
    base: str,
    sep: str = os.sep,
    altsep: str | None = os.altsep,
) -> str:
    """The prefix ``os.scandir(base)`` puts in front of every child name.

    ``DirEntry.path`` equals ``os.path.join(base, name)``, which appends a
    separator only when ``base`` does not already end with one — including the
    Windows alt separator. On Windows a share path ending in ``/`` (or a drive
    root ending in ``:``) therefore yields ``"C:/share/name"``, not
    ``"C:/share\\name"``; slicing the raw ``entry.path`` after a prefix that
    wrongly appended ``os.sep`` shifts every relative key by one character.
    """
    separators = (sep,) if altsep is None else (sep, altsep, ":")
    if base.endswith(separators):
        return base
    return base + sep


class FilePanel(QWidget):
    """Complete file transfer panel with table and collapsible detail panel."""

    # Emits the scanned local size in bytes (-1 = unknown, 0 = empty share).
    share_size_changed = Signal(int)
    # Emits when the consistency scan added paths that were not tracked (a
    # missed live event, e.g. a remote rename): the window refreshes statuses.
    scan_found_new_files = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_thread: QThread | None = None
        self._scan_worker: DirectoryScanWorker | None = None
        self._share_size_bytes: int = -1
        self._current_directory: str = ""
        self._matcher: IgnoreMatcher | None = None
        self._ignore_stamp: tuple[int, int] | None = None
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
        self._btn_back.setIconSize(QSize(_NAV_ICON_PX, _NAV_ICON_PX))
        self._btn_back.setToolTip(tr("nav.back"))
        self._btn_back.setEnabled(False)
        self._btn_back.setAutoRaise(True)

        self._btn_forward = QToolButton()
        self._btn_forward.setIcon(get_icon("go-next"))
        self._btn_forward.setIconSize(QSize(_NAV_ICON_PX, _NAV_ICON_PX))
        self._btn_forward.setToolTip(tr("nav.forward"))
        self._btn_forward.setEnabled(False)
        self._btn_forward.setAutoRaise(True)

        self._btn_up = QToolButton()
        self._btn_up.setIcon(get_icon("go-up"))
        self._btn_up.setIconSize(QSize(_NAV_ICON_PX, _NAV_ICON_PX))
        self._btn_up.setToolTip(tr("nav.up"))
        self._btn_up.setEnabled(False)
        self._btn_up.setAutoRaise(True)

        nav_layout.addWidget(self._btn_back)
        nav_layout.addWidget(self._btn_forward)
        nav_layout.addWidget(self._btn_up)

        self._breadcrumb_icon = QLabel(nav_bar)
        self._refresh_breadcrumb_icon()
        self._breadcrumb_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._breadcrumb_icon.setCursor(Qt.CursorShape.ArrowCursor)
        self._breadcrumb_icon.setToolTip(tr("nav.root"))
        self._breadcrumb_icon.mousePressEvent = lambda _: self._navigate_to_root()  # type: ignore[method-assign]
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

    def _navigate_to_root(self) -> None:
        """Open the share root, unless the visible list already shows it."""
        if self._table.current_path:
            self._table.navigate_to("")

    def _refresh_breadcrumb_icon(self) -> None:
        """Re-render the root icon at the navigation icon size."""
        self._breadcrumb_icon.setPixmap(get_icon("folder-open").pixmap(_NAV_ICON_PX, _NAV_ICON_PX))
        self._breadcrumb_icon.setFixedSize(_NAV_ICON_BOX_PX, _NAV_ICON_BOX_PX)

    def _update_breadcrumb(self) -> None:
        self._refresh_breadcrumb_icon()
        current_folder = self._table.current_path
        if not current_folder:
            self._breadcrumb_label.setText("")
            self._breadcrumb_label.setCursor(Qt.CursorShape.ArrowCursor)
            self._breadcrumb_icon.setCursor(Qt.CursorShape.ArrowCursor)
            return
        # The root icon is an ancestor from a subfolder, so it navigates.
        self._breadcrumb_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        text_color = (
            self._breadcrumb_label.palette()
            .color(self._breadcrumb_label.palette().ColorRole.WindowText)
            .name()
        )
        parts = []
        segments = current_folder.split("/")
        path_so_far = ""
        for index, seg in enumerate(segments):
            path_so_far = f"{path_so_far}/{seg}" if path_so_far else seg
            safe_seg = html.escape(seg, quote=True)
            if index == len(segments) - 1:
                # The current folder is what the list already shows: plain
                # text, never a link that would do nothing when clicked.
                parts.append(f'<span style="color:{text_color};">{safe_seg}</span>')
            else:
                safe_path = html.escape(path_so_far, quote=True)
                parts.append(
                    f'<a href="nav:{safe_path}" '
                    f'style="color:{text_color}; text-decoration:underline;">{safe_seg}</a>'
                )
        breadcrumb = _breadcrumb_separator().join(parts)
        self._breadcrumb_label.setText(breadcrumb)
        # QLabel shows the hand over the links and the arrow over the plain
        # current segment, so leave the cursor to it.
        self._breadcrumb_label.setCursor(Qt.CursorShape.ArrowCursor)

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

    def set_connected(self, connected: bool) -> None:
        """Forward the connection state so "Local" rows use the default colour."""
        self._table.set_connected(connected)

    @property
    def current_path(self) -> str:
        """Current folder shown by the table (relative to the sync root)."""
        return self._table.current_path

    def load_local_files(
        self,
        directory: str,
        *,
        restore_view: tuple[str, str | None] | None = None,
    ) -> None:
        self._stop_scan()
        self._consistency_timer.stop()
        self.clear()
        # A new scan invalidates the previous size until the first batch arrives.
        self._share_size_bytes = -1
        self.share_size_changed.emit(-1)
        if not directory or not os.path.isdir(directory):
            self._current_directory = ""
            self._matcher = None
            self._ignore_stamp = None
            return
        self._current_directory = directory
        self._matcher = IgnoreMatcher(directory)
        self._ignore_stamp = ignore_file_stamp(directory)
        self._table.set_base_directory(directory)
        self._detail.set_base_directory(directory)
        if restore_view is not None:
            # Keep the folder/row the user acted on after the reload clears them.
            self._table.restore_view(*restore_view)
        self._show_loading()
        self._start_scan(directory, emit_rows=True)

    def _start_scan(self, directory: str, *, emit_rows: bool) -> None:
        """Run a scan worker in its own thread (table rows and/or the size)."""
        self._scan_thread = QThread()
        self._scan_worker = DirectoryScanWorker(directory, self._matcher, emit_rows=emit_rows)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        if emit_rows:
            self._scan_worker.files_found.connect(
                self._on_files_found, Qt.ConnectionType.QueuedConnection
            )
            self._scan_worker.progress.connect(
                self._on_scan_progress, Qt.ConnectionType.QueuedConnection
            )
        self._scan_worker.size_progress.connect(
            self._on_scan_size, Qt.ConnectionType.QueuedConnection
        )
        self._scan_worker.finished.connect(
            self._on_scan_finished, Qt.ConnectionType.QueuedConnection
        )
        self._scan_thread.start()

    def refresh_share_size(self) -> None:
        """Recompute the local size without reloading the file table.

        The size a run reports describes the folder as of the *start* of its
        cycle (the client emits ``folder_size`` before transferring) and nothing
        rescanned the folder when the run ended, so the status bar kept the
        pre-sync value until the next run. Skipped while a full scan is already
        computing the same number.
        """
        if not self._current_directory or self._matcher is None:
            return
        if self._scan_worker is not None:
            return
        self._start_scan(self._current_directory, emit_rows=False)

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
                self._scan_worker.size_progress.disconnect()
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

    @Slot(int)
    def _on_scan_size(self, total_bytes: int) -> None:
        """Forward the accumulated local size from the scan worker."""
        self._share_size_bytes = total_bytes
        self.share_size_changed.emit(total_bytes)

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
            self._consistency_timer.start(CONSISTENCY_CHECK_INTERVAL_MS)

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

        if (
            watched == self._table_container
            and event.type() == QEvent.Type.Resize
            and self._loading_overlay.isVisible()
        ):
            self._loading_overlay.setGeometry(self._table_container.rect())
        return super().eventFilter(watched, event)

    def _refresh_matcher(self) -> IgnoreMatcher:
        """Return the bucket matcher, reloading it when .hsyncignore changed."""
        directory = self._current_directory
        if self._matcher is None:
            self._matcher = IgnoreMatcher(directory)
            self._ignore_stamp = ignore_file_stamp(directory)
            return self._matcher
        stamp = ignore_file_stamp(directory)
        if stamp != self._ignore_stamp:
            self._ignore_stamp = stamp
            self._matcher.reload()
        return self._matcher

    @Slot()
    def _check_directory_consistency(self) -> None:
        if not self._current_directory or not os.path.isdir(self._current_directory):
            self._consistency_timer.stop()
            return
        base = self._current_directory
        prefix = _scandir_child_prefix(base)
        matcher = self._refresh_matcher()
        current_files: set[str] = set()
        # Iterative scandir: no Path object per entry and no Path.relative_to
        # per file. ``entry.path`` is already absolute and the relative key is a
        # plain prefix slice, keeping the native separators the scan worker also
        # produces.
        stack = [base]
        while stack:
            root = stack.pop()
            has_dir = False
            visible: list[os.DirEntry[str]] = []
            recurse: list[str] = []
            try:
                with os.scandir(root) as it:
                    for entry in it:
                        try:
                            # Mirror os.walk's dir/file split (symlinks follow
                            # for classification), but only real directories
                            # are recursed, exactly like os.walk(followlinks=False).
                            is_dir = entry.is_dir()
                            is_dir_real = entry.is_dir(follow_symlinks=False)
                        except OSError:
                            continue
                        if not is_synced_entry(matcher, entry.path, is_dir=is_dir):
                            continue
                        if is_dir:
                            has_dir = True
                            if is_dir_real:
                                recurse.append(entry.path)
                        else:
                            visible.append(entry)
            except OSError:
                if root == base:
                    # The share root itself is unreadable: abort rather than
                    # diff an empty set, which would drop every row.
                    return
                # A nested directory vanished or is unreadable: skip that
                # subtree only, like os.walk(onerror=None).
                continue
            if not visible and not has_dir and root != base:
                current_files.add(root[len(prefix) :] + "/")
            for entry in visible:
                current_files.add(entry.path[len(prefix) :])
            stack.extend(recurse)
        table_files = set(self._table._transfers)
        new_files = current_files - table_files
        if new_files:
            # Batch the additions: one rebuild instead of one per new path.
            new_transfers: list[FileTransfer] = []
            for rel_path in new_files:
                full_path = Path(base) / rel_path
                is_dir_entry = rel_path.endswith("/")
                try:
                    stat = full_path.stat()
                    size = 0 if is_dir_entry else stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = 0.0
                new_transfers.append(
                    FileTransfer(
                        filepath=rel_path,
                        direction="—",
                        size=size,
                        bytes_transferred=0,
                        status=TransferStatus.LOCAL,
                        mtime=mtime,
                    )
                )
            self._table.add_transfers_batch(new_transfers)
        deleted_files = table_files - current_files
        removed: list[str] = []
        remove_now: list[str] = []
        for rel_path in deleted_files:
            existing = self._table._transfers.get(rel_path)
            if existing is None:
                continue
            if existing.status in (
                TransferStatus.DOWNLOADING,
                TransferStatus.UPLOADING,
                TransferStatus.DELETED,
            ):
                # In flight (the final file is not on disk yet) or already
                # showing the deletion marker: leave it alone.
                continue
            # The path is gone from disk. A resting LOCAL row is a stale scan
            # entry, while a SYNCED/ERROR/... row was a real file deleted
            # locally after a previous sync: it must disappear from the view
            # too, even when the structured delete event was missed.
            removed.append(rel_path)
            if existing.status == TransferStatus.LOCAL:
                # Never-synced scan entry: nothing to announce, remove at once.
                remove_now.append(rel_path)
            else:
                # Mirror the remote-deletion UX (red "Deleted" for 3 s) even
                # when the scan is the one detecting the local deletion.
                self._table.mark_deleted(rel_path)
        if remove_now:
            # Batch the removals into a single rebuild too.
            self._table.remove_transfers(remove_now)
        if new_files:
            # A path appeared on disk that the event flow never reported (e.g. a
            # rename destination whose live event was lost). Let the window
            # refresh the statuses so it stops reading as a stale "Local".
            self.scan_found_new_files.emit()
        if new_files or removed:
            from hsync_desktop import debug_events

            debug_events.log("consistency", added=sorted(new_files), removed=removed)

    def update_file_status(
        self,
        filepath: str,
        status: str,
        size: int = 0,
        mtime: float = 0.0,
        client_cid: str = "",
        client_ip: str = "",
        *,
        preview: bool = False,
    ) -> None:
        self._table.update_file_status(
            filepath, status, size, mtime, client_cid, client_ip, preview=preview
        )

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
        self, filepath: str, bytes_transferred: int, total_bytes: int, op: str = ""
    ) -> None:
        """Update — or create — the row of an in-flight transfer."""
        self._table.update_transfer_progress(filepath, bytes_transferred, total_bytes, op)

    def mark_failed(self, filepath: str) -> None:
        """Flag a row whose transfer gave up after retries."""
        self._table.mark_failed(filepath)

    def clear_transient_progress(self, base_path: str = "") -> None:
        """Drop in-flight markers left behind when the engine stops."""
        self._table.clear_transient_progress(base_path)

    @property
    def table(self) -> FileTransferTable:
        return self._table

    def retranslate_columns(self) -> None:
        """Re-apply the localized table column headers (on language change)."""
        self._table.retranslate()

    def refresh_fonts(self) -> None:
        """Re-apply the table fonts after a global font-size change."""
        self._table.refresh_fonts()

    def refresh_icons_for_theme(self) -> None:
        self._btn_back.setIcon(get_icon("go-previous"))
        self._btn_forward.setIcon(get_icon("go-next"))
        self._btn_up.setIcon(get_icon("go-up"))
        self._detail._btn_close.setIcon(get_icon("window-close"))
        # Link colours are baked into the rich text: rebuild them for the theme.
        self._update_breadcrumb()
        self._detail.refresh_link_color()
        self._table.refresh_view()

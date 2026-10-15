# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Top-level file transfer panel: navigation bar, transfer table and detail panel."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Slot
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
from hsync_desktop.file_panel.models import FileTransfer, TransferStatus
from hsync_desktop.file_panel.overlay import LoadingOverlay
from hsync_desktop.file_panel.transfer_table import FileTransferTable
from hsync_desktop.file_panel.workers import DirectoryScanWorker
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon as get_icon
from hsync_desktop.ui.loader import load_ui_widget


class FilePanel(QWidget):
    """Complete file transfer panel with table and collapsible detail panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_thread: QThread | None = None
        self._scan_worker: DirectoryScanWorker | None = None
        self._current_directory: str = ""
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

    def retranslate_columns(self) -> None:
        """Re-apply the localized table column headers (on language change)."""
        self._table.retranslate()

    def refresh_icons_for_theme(self) -> None:
        self._btn_back.setIcon(get_icon("go-previous"))
        self._btn_forward.setIcon(get_icon("go-next"))
        self._btn_up.setIcon(get_icon("go-up"))
        self._breadcrumb_icon.setPixmap(get_icon("folder-open").pixmap(16, 16))
        self._detail._btn_close.setIcon(get_icon("window-close"))
        self._table.refresh_view()

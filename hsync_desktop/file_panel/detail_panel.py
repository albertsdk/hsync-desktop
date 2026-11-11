# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Detail panel showing the selected transfer's metadata."""

from __future__ import annotations

import html
import os

from hsync_common.format import format_bytes
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QToolButton

from hsync_desktop.file_panel.models import FileTransfer, TransferStatus
from hsync_desktop.file_panel.utils import folder_count_text, format_mtime
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.icons import icon as get_icon


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
        self._lbl_devices: QLabel = frame.findChild(QLabel, "valDevices")  # type: ignore[assignment]
        self._lbl_last_synced: QLabel = frame.findChild(QLabel, "valLastSynced")  # type: ignore[assignment]
        self._lbl_elements: QLabel = frame.findChild(QLabel, "valElements")  # type: ignore[assignment]

        # Label widgets for translation
        self._lbl_filepath_label: QLabel = frame.findChild(QLabel, "lblFilepath")  # type: ignore[assignment]
        self._lbl_filename_label: QLabel = frame.findChild(QLabel, "lblFilename")  # type: ignore[assignment]
        self._lbl_size_label: QLabel = frame.findChild(QLabel, "lblSize")  # type: ignore[assignment]
        self._lbl_modified_label: QLabel = frame.findChild(QLabel, "lblModified")  # type: ignore[assignment]
        self._lbl_status_label: QLabel = frame.findChild(QLabel, "lblStatus")  # type: ignore[assignment]
        self._lbl_devices_label: QLabel = frame.findChild(QLabel, "lblDevices")  # type: ignore[assignment]
        self._lbl_last_synced_label: QLabel = frame.findChild(QLabel, "lblLastSynced")  # type: ignore[assignment]
        self._lbl_elements_label: QLabel = frame.findChild(QLabel, "lblElements")  # type: ignore[assignment]

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
        self._lbl_devices_label.setText(tr("detail.devices"))
        self._lbl_devices.setToolTip(tr("detail.devices_tip"))
        self._lbl_devices_label.setToolTip(tr("detail.devices_tip"))
        self._lbl_last_synced_label.setText(tr("detail.last_synced"))
        self._lbl_elements_label.setText(tr("detail.elements"))

    def refresh_fonts(self) -> None:
        """Keep the panel title bold after a global font reset.

        ``fonts.reset_widget_fonts`` clears every widget font (the stylesheet
        pins them at polish time), which also dropped the title's bold declared
        in the ``.ui``; re-apply it after that reset.
        """
        font = self._lbl_title.font()
        font.setBold(True)
        self._lbl_title.setFont(font)

    def set_base_directory(self, directory: str) -> None:
        """Set the base directory for resolving absolute file paths."""
        self._base_directory = directory

    def show_transfer(self, transfer: FileTransfer, folder: dict | None = None) -> None:
        """Display details for the given transfer.

        ``folder`` carries the aggregated metadata of a directory row (size,
        last modification, device coverage, last sync and status): a directory
        has no single file to read those from, and its aggregate status is what
        the table already shows.
        """
        rel_path = transfer.path
        # Determine the directory to open on click
        if rel_path:
            abs_dir = os.path.join(self._base_directory, rel_path)
            display = rel_path
        else:
            abs_dir = self._base_directory
            display = "."
        self._current_abs_dir = abs_dir
        self._current_display = display
        self._render_filepath_link()

        self._lbl_filename.setText(transfer.filename)
        size = folder["size_bytes"] if folder is not None else transfer.size
        mtime = folder["mtime"] if folder is not None else transfer.mtime
        self._lbl_size.setText(format_bytes(size))
        self._lbl_modified.setText(format_mtime(mtime))

        if folder is not None:
            self._lbl_status.setText(tr(folder["status_key"]))
        else:
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
        holders = folder["holders"] if folder is not None else transfer.holders
        devices = folder["devices"] if folder is not None else transfer.devices
        if devices > 0 and 0 <= holders <= devices:
            self._lbl_devices.setText(f"{holders}/{devices}")
        else:
            self._lbl_devices.setText("—")
        last_synced = folder["last_synced_at"] if folder is not None else transfer.last_synced_at
        self._lbl_last_synced.setText(format_mtime(last_synced))
        if folder is not None:
            self._lbl_elements.setText(folder_count_text(folder.get("count", 0)))
            self._lbl_elements_label.show()
            self._lbl_elements.show()
        else:
            # A single file (or a selection) has no item count.
            self._lbl_elements_label.hide()
            self._lbl_elements.hide()
        self._frame.show()

    def _render_filepath_link(self) -> None:
        """Render the clickable path with the current palette colour."""
        display = getattr(self, "_current_display", "")
        if not display:
            return
        escaped = html.escape(display)
        safe_dir = html.escape(getattr(self, "_current_abs_dir", ""), quote=True)
        text_color = (
            self._lbl_filepath.palette()
            .color(self._lbl_filepath.palette().ColorRole.WindowText)
            .name()
        )
        self._lbl_filepath.setText(
            f'<a href="file://{safe_dir}" '
            f'style="color:{text_color}; text-decoration:underline;">{escaped}</a>'
        )

    def refresh_link_color(self) -> None:
        """Rebuild the filepath link after a theme change."""
        self._render_filepath_link()

    def _on_filepath_clicked(self, _link: str) -> None:
        """Open the file's directory in the system file manager."""
        abs_dir = getattr(self, "_current_abs_dir", "")
        if abs_dir and os.path.isdir(abs_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir))

    def clear(self) -> None:
        """Clear and hide the panel."""
        self._current_abs_dir = ""
        self._current_display = ""
        self._lbl_filepath.setText("—")
        self._frame.hide()

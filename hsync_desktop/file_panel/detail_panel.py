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
from hsync_desktop.file_panel.utils import format_mtime
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
        self._current_display = display
        self._render_filepath_link()

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

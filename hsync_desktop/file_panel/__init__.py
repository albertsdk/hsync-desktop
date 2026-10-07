# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
File panel module for HSYNC Desktop.

This module provides the file transfer panel functionality, split into:
- models: Data structures (TransferStatus, FileTransfer)
- widgets: Custom Qt widgets (FilePanel, FileTransferTable, delegates)
- workers: Background workers (DirectoryScanWorker)
- utils: Utility functions (formatting, classification)
"""

from hsync_desktop.file_panel.models import (
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
    FileTransfer,
    TransferStatus,
)
from hsync_desktop.file_panel.utils import (
    _FILE_TYPE_MAP,
    COL_ETA,
    COL_ICON,
    COL_MODIFIED,
    COL_NAME,
    COL_PROGRESS,
    COL_SIZE,
    COL_STATUS,
    COL_TYPE,
    _classify_file,
)
from hsync_desktop.file_panel.utils import (
    format_mtime as _format_mtime,
)
from hsync_desktop.file_panel.widgets import FilePanel, FileTransferTable
from hsync_desktop.file_panel.workers import DirectoryScanWorker

__all__ = [
    "COL_ETA",
    "COL_ICON",
    "COL_MODIFIED",
    "COL_NAME",
    "COL_PROGRESS",
    "COL_SIZE",
    "COL_STATUS",
    "COL_TYPE",
    "STATUS_COLORS",
    "_FILE_TYPE_MAP",
    "_NO_PROGRESS_STATUSES",
    "DirectoryScanWorker",
    "FilePanel",
    "FileTransfer",
    "FileTransferTable",
    "TransferStatus",
    "_classify_file",
    "_format_mtime",
]

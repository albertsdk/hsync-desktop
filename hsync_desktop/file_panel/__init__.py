# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
File panel module for HSYNC Desktop.

This module provides the file transfer panel functionality, split into:
- models: Data structures (TransferStatus, FileTransfer)
- panel: Top-level FilePanel (navigation bar, table, detail panel)
- transfer_table: FileTransferTable (hierarchical transfer view)
- detail_panel: FileDetailPanel
- overlay: LoadingOverlay
- delegates: ProgressBarDelegate / CenteredIconDelegate
- dialogs: shared confirmation dialog
- filter: engine-aligned scan predicate and hidden-name view helper
- workers: Background workers (DirectoryScanWorker)
- utils: Utility functions (formatting, classification)
"""

from hsync_desktop.file_panel.models import (
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
    STATUS_COLORS_DARK,
    FileTransfer,
    TransferStatus,
)
from hsync_desktop.file_panel.panel import FilePanel
from hsync_desktop.file_panel.transfer_table import FileTransferTable
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
    "STATUS_COLORS_DARK",
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

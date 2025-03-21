# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

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
    format_eta as _format_eta,
)
from hsync_desktop.file_panel.utils import (
    format_mtime as _format_mtime,
)
from hsync_desktop.file_panel.utils import (
    format_size as _format_size,
)
from hsync_desktop.file_panel.widgets import FilePanel, FileTransferTable
from hsync_desktop.file_panel.workers import DirectoryScanWorker

__all__ = [
    "FilePanel",
    "FileTransferTable",
    "FileTransfer",
    "TransferStatus",
    "STATUS_COLORS",
    "_NO_PROGRESS_STATUSES",
    "_FILE_TYPE_MAP",
    "_classify_file",
    "_format_size",
    "_format_eta",
    "_format_mtime",
    "COL_ICON",
    "COL_NAME",
    "COL_SIZE",
    "COL_TYPE",
    "COL_MODIFIED",
    "COL_PROGRESS",
    "COL_ETA",
    "COL_STATUS",
    "DirectoryScanWorker",
]

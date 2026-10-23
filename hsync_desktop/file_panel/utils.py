# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Utility functions for file panel.

Contains formatting functions and file type classification.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLocale

from hsync_desktop.i18n import get_language, tr

# Column indices and translation keys
COL_ICON = 0
COL_NAME = 1
COL_SIZE = 2
COL_TYPE = 3
COL_MODIFIED = 4
COL_PROGRESS = 5
COL_ETA = 6
COL_STATUS = 7
# Optional columns, hidden by default (see FileTransferTable._DEFAULT_HIDDEN).
COL_SPEED = 8
COL_DIRECTION = 9

# Column translation keys (in order)
_COLUMN_KEYS = [
    "",  # icon column — no header text
    "file.name",
    "file.size",
    "file.type",
    "file.modified",
    "file.progress",
    "file.eta",
    "file.status",
    "file.speed",
    "file.direction",
]


# ── File type classification ──────────────────────────────────────────
# Maps file extensions to (icon_name, translation_key) pairs.
# icon_name is a FreeDesktop icon name used with QIcon.fromTheme().
# Directories are handled separately.

_FILE_TYPE_MAP: dict[str, tuple[str, str]] = {}

_TYPE_DEFINITIONS: list[tuple[str, str, list[str]]] = [
    (
        "image-x-generic",
        "ftype.image",
        [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".svg",
            ".webp",
            ".ico",
            ".tiff",
            ".tif",
            ".heic",
            ".heif",
            ".avif",
            ".raw",
            ".cr2",
            ".nef",
        ],
    ),
    (
        "audio-x-generic",
        "ftype.audio",
        [
            ".mp3",
            ".wav",
            ".flac",
            ".ogg",
            ".aac",
            ".wma",
            ".m4a",
            ".opus",
            ".aiff",
            ".alac",
            ".mid",
            ".midi",
        ],
    ),
    (
        "video-x-generic",
        "ftype.video",
        [
            ".mp4",
            ".avi",
            ".mkv",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
            ".mpeg",
            ".mpg",
            ".3gp",
            ".ts",
        ],
    ),
    (
        "x-office-spreadsheet",
        "ftype.spreadsheet",
        [
            ".xls",
            ".xlsx",
            ".ods",
            ".csv",
            ".tsv",
            ".numbers",
        ],
    ),
    (
        "x-office-presentation",
        "ftype.presentation",
        [
            ".ppt",
            ".pptx",
            ".odp",
            ".key",
        ],
    ),
    (
        "x-office-document",
        "ftype.document",
        [
            ".pdf",
            ".doc",
            ".docx",
            ".odt",
            ".rtf",
            ".txt",
            ".md",
            ".tex",
            ".epub",
            ".pages",
            ".log",
        ],
    ),
    (
        "package-x-generic",
        "ftype.archive",
        [
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".rar",
            ".7z",
            ".zst",
            ".tgz",
            ".tbz2",
            ".iso",
            ".dmg",
            ".deb",
            ".rpm",
        ],
    ),
    (
        "text-x-script",
        "ftype.code",
        [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".scss",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".lua",
            ".sh",
            ".bash",
            ".zsh",
            ".ps1",
            ".sql",
            ".r",
            ".m",
            ".pl",
            ".scala",
            ".zig",
            ".nim",
            ".dart",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
        ],
    ),
    (
        "application-certificate",
        "ftype.key",
        [
            ".pem",
            ".crt",
            ".cer",
            ".key",
            ".p12",
            ".pfx",
            ".jks",
        ],
    ),
    (
        "font-x-generic",
        "ftype.font",
        [
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
            ".eot",
        ],
    ),
    (
        "application-x-executable",
        "ftype.executable",
        [
            ".exe",
            ".msi",
            ".app",
            ".bin",
            ".run",
            ".appimage",
        ],
    ),
]

for _icon_name, _key, _exts in _TYPE_DEFINITIONS:
    for _ext in _exts:
        _FILE_TYPE_MAP[_ext] = (_icon_name, _key)


def _classify_file(filepath: str) -> tuple[str, str]:
    """Return (icon_name, type_translation_key) for a filepath.

    icon_name is a FreeDesktop icon name suitable for get_icon().
    """
    if filepath.endswith("/"):
        return ("folder", "ftype.folder")
    ext = Path(filepath).suffix.lower()
    return _FILE_TYPE_MAP.get(ext, ("text-x-generic", "ftype.other"))


# ── Formatting functions ────────────────────────────────────────────────

# Locale and month-name caches. format_mtime runs once per Modified cell on
# every rebuild; constructing a QLocale and resolving the month name per cell
# dominated that column. Both caches are keyed by language so a live language
# change is still reflected.
_LOCALE_CACHE: dict[str, QLocale] = {}
_MONTH_NAME_CACHE: dict[tuple[str, int], str] = {}


def _locale_for(language: str) -> QLocale:
    locale = _LOCALE_CACHE.get(language)
    if locale is None:
        locale = _LOCALE_CACHE[language] = QLocale(language)
    return locale


def _short_month_name(language: str, month: int) -> str:
    key = (language, month)
    name = _MONTH_NAME_CACHE.get(key)
    if name is None:
        name = _locale_for(language).monthName(month, QLocale.FormatType.ShortFormat).lower()
        _MONTH_NAME_CACHE[key] = name
    return name


def format_mtime(epoch: float) -> str:
    """Format modification time as locale-aware human-readable string.

    * Today → "oggi 14:30" (or translated equivalent)
    * Yesterday → "ieri 09:15"
    * Other dates → "8 feb 2026 11:00" using locale month abbreviations
    * Time part is always HH:MM in 24-hour format.
    """
    if epoch <= 0:
        return "—"
    dt = datetime.fromtimestamp(epoch)
    now = datetime.now()
    time_str = dt.strftime("%H:%M")

    days_ago = (now.date() - dt.date()).days
    if days_ago == 0:
        return f"{tr('date.today')} {time_str}"
    if days_ago == 1:
        return f"{tr('date.yesterday')} {time_str}"

    # Locale-aware abbreviated month name, resolved through the per-language
    # caches above instead of building a QLocale for every row.
    month = _short_month_name(get_language(), dt.month)
    return f"{dt.day} {month} {dt.year} {time_str}"

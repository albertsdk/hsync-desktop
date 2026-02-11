# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Icon management for HSYNC Desktop.

Provides cross-platform icon support with consistent appearance:
- Always uses bundled SVG icons when available for uniformity across platforms
- Falls back to system theme icons only when no bundled icon exists

Usage:
    from hsync_desktop.icons import icon

    btn.setIcon(icon("network-wired"))
    tab.setIcon(icon("emblem-synchronizing"))
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication


def _is_dark_theme() -> bool:
    """Check if the current application theme is dark.

    Compares the text color luminance with the background color luminance.
    """
    app = QApplication.instance()
    if not app or not isinstance(app, QApplication):
        return False
    palette = app.palette()
    bg = palette.color(QPalette.ColorRole.Window)
    # Use luminance formula: darker backgrounds have lower luminance
    luminance = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return luminance < 128


def _load_themed_svg(svg_path: Path) -> QIcon:
    """Load an SVG file and replace 'currentColor' with theme-appropriate color.

    Args:
        svg_path: Path to the SVG file

    Returns:
        QIcon with the themed SVG
    """
    try:
        svg_content = svg_path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()

    # Choose color based on theme
    # Light theme: dark gray (#424242), Dark theme: light gray (#e0e0e0)
    color = "#e0e0e0" if _is_dark_theme() else "#424242"

    # Replace currentColor with the appropriate color
    themed_svg = svg_content.replace("currentColor", color)

    # Create QIcon from the modified SVG content
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(themed_svg.encode("utf-8")))
    if pixmap.isNull():
        # Fallback: try loading the original file
        return QIcon(str(svg_path))

    return QIcon(pixmap)

# Directory containing fallback icons
ICONS_DIR = Path(__file__).parent / "resources" / "icons"

# Mapping of FreeDesktop icon names to fallback filenames
# Add entries here when you add custom fallback icons
_FALLBACK_MAP: dict[str, str] = {
    # Tab icons
    "network-wired": "network-wired.svg",
    "emblem-synchronizing": "emblem-synchronizing.svg",
    "network-workgroup": "network-workgroup.svg",
    "utilities-log-viewer": "utilities-log-viewer.svg",
    "preferences-desktop-theme": "preferences-desktop-theme.svg",
    # Action icons
    "folder-open": "folder-open.svg",
    "document-save": "document-save.svg",
    "application-exit": "application-exit.svg",
    "view-refresh": "view-refresh.svg",
    "media-playback-start": "media-playback-start.svg",
    "media-playback-stop": "media-playback-stop.svg",
    "preferences-system": "preferences-system.svg",
    # Navigation icons
    "go-previous": "go-previous.svg",
    "go-next": "go-next.svg",
    "go-up": "go-up.svg",
    # Window icons
    "window-close": "window-close.svg",
    # File type icons (FreeDesktop MIME type names)
    "folder": "folder.svg",
    "image-x-generic": "image-x-generic.svg",
    "audio-x-generic": "audio-x-generic.svg",
    "video-x-generic": "video-x-generic.svg",
    "x-office-spreadsheet": "x-office-spreadsheet.svg",
    "x-office-presentation": "x-office-presentation.svg",
    "x-office-document": "x-office-document.svg",
    "package-x-generic": "package-x-generic.svg",
    "text-x-script": "text-x-script.svg",
    "application-certificate": "application-certificate.svg",
    "font-x-generic": "font-x-generic.svg",
    "application-x-executable": "application-x-executable.svg",
    "text-x-generic": "text-x-generic.svg",
}


def _has_icon_theme() -> bool:
    """Check if the system has a usable icon theme.
    
    Returns True on Linux with a desktop environment,
    False on Windows/macOS or headless Linux.
    """
    # Windows and macOS don't have FreeDesktop icon themes
    if sys.platform in ("win32", "darwin"):
        return False
    
    # On Linux, check if there's a theme set
    theme = QIcon.themeName()
    if not theme or theme == "hicolor":
        # hicolor is the fallback theme with minimal icons
        return False
    
    return True


# Cache for icons, keyed by (name, is_dark_theme)
_icon_cache: dict[tuple[str, bool], QIcon] = {}


def icon(name: str) -> QIcon:
    """Get an icon by FreeDesktop name.

    Always uses bundled icons when available for cross-platform consistency.
    SVG icons are themed based on the current application theme (light/dark).
    Falls back to system theme icons if no bundled icon exists.

    Args:
        name: FreeDesktop icon name (e.g., "network-wired")

    Returns:
        QIcon instance (may be null if no icon found)

    Example:
        btn.setIcon(icon("network-wired"))
    """
    is_dark = _is_dark_theme()
    cache_key = (name, is_dark)

    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    # Always prefer bundled icons for cross-platform uniformity
    fallback_name = _FALLBACK_MAP.get(name)
    if fallback_name:
        fallback_path = ICONS_DIR / fallback_name
        if fallback_path.exists():
            result = _load_themed_svg(fallback_path)
            _icon_cache[cache_key] = result
            return result

    # Fallback to system theme if no bundled icon
    if _has_icon_theme():
        theme_icon = QIcon.fromTheme(name)
        if not theme_icon.isNull():
            _icon_cache[cache_key] = theme_icon
            return theme_icon

    # Last resort: try fromTheme anyway (might work on some systems)
    result = QIcon.fromTheme(name)
    _icon_cache[cache_key] = result
    return result


def clear_icon_cache() -> None:
    """Clear the icon cache. Call this when the theme changes."""
    _icon_cache.clear()


def has_icon(name: str) -> bool:
    """Check if an icon is available (either from theme or fallback).
    
    Args:
        name: FreeDesktop icon name
    
    Returns:
        True if the icon exists and can be loaded
    """
    return not icon(name).isNull()


def set_fallback_theme_path() -> None:
    """Add the bundled icons directory to the icon theme search path.
    
    Call this once at application startup to ensure fallback icons
    are found even when using QIcon.fromTheme() directly.
    """
    if ICONS_DIR.exists():
        paths = QIcon.themeSearchPaths()
        icons_str = str(ICONS_DIR)
        if icons_str not in paths:
            paths.append(icons_str)
            QIcon.setThemeSearchPaths(paths)


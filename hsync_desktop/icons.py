# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Icon management for HSYNC Desktop.

Provides cross-platform icon support:
- On Linux with icon themes: uses system icons via QIcon.fromTheme()
- On Windows/macOS or when theme icons unavailable: uses bundled fallback icons

Usage:
    from hsync_desktop.icons import icon
    
    btn.setIcon(icon("network-wired"))
    tab.setIcon(icon("emblem-synchronizing"))
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon

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


@lru_cache(maxsize=64)
def icon(name: str) -> QIcon:
    """Get an icon by FreeDesktop name with automatic fallback.
    
    On platforms with icon themes (Linux/KDE/GNOME), uses the system icon.
    On other platforms, uses bundled fallback icons if available.
    
    Args:
        name: FreeDesktop icon name (e.g., "network-wired")
    
    Returns:
        QIcon instance (may be null if no icon found)
    
    Example:
        btn.setIcon(icon("network-wired"))
    """
    # Try system theme first (fast path on Linux)
    if _has_icon_theme():
        theme_icon = QIcon.fromTheme(name)
        if not theme_icon.isNull():
            return theme_icon
    
    # Fallback to bundled icon
    fallback_name = _FALLBACK_MAP.get(name)
    if fallback_name:
        fallback_path = ICONS_DIR / fallback_name
        if fallback_path.exists():
            return QIcon(str(fallback_path))
    
    # Last resort: try fromTheme anyway (might work on some systems)
    return QIcon.fromTheme(name)


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


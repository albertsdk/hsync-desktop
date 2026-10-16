# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Icon management for HSYNC Desktop.

Provides cross-platform icon support with consistent appearance:
- Always uses bundled SVG icons when available for uniformity across platforms
- Falls back to system theme icons only when no bundled icon exists

Usage:
    from hsync_desktop.icons import icon

    btn.setIcon(icon("network-cloud"))
    tab.setIcon(icon("emblem-synchronizing"))
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QDialogButtonBox


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


def _load_themed_svg(svg_path: Path, custom_color: str | None = None) -> QIcon:
    """Load an SVG file and replace 'currentColor' with theme-appropriate color.

    Args:
        svg_path: Path to the SVG file
        custom_color: Optional custom color (e.g., "#FF0000"). If provided, overrides theme color.

    Returns:
        QIcon with the themed SVG
    """
    try:
        svg_content = svg_path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()

    # Use custom color if provided, otherwise fall back to theme-based color
    # Light theme: dark gray (#424242), Dark theme: light gray (#e0e0e0)
    color = ("#e0e0e0" if _is_dark_theme() else "#424242") if custom_color is None else custom_color

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
    "network-cloud": "network-cloud.svg",
    "emblem-synchronizing": "emblem-synchronizing.svg",
    "network-p2p": "network-p2p.svg",
    "utilities-log-viewer": "utilities-log-viewer.svg",
    "preferences-desktop-theme": "preferences-desktop-theme.svg",
    "preferences-other": "preferences-other.svg",
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
    # Sync direction icons
    "sync-bidirectional": "sync-bidirectional.svg",
    "sync-upload": "sync-upload.svg",
    "sync-download": "sync-download.svg",
    # Window icons
    "window-close": "window-close.svg",
    # Dialog action icons
    "dialog-cancel": "dialog-cancel.svg",
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
    # Role icons
    "role-master": "role-master.svg",
    "role-client": "role-client.svg",
    # Application icon (bundled brand icon; full-colour, not themed)
    "hsync-desktop": "hsync-desktop.svg",
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
    # hicolor is the fallback theme with minimal icons
    return bool(theme and theme != "hicolor")


# Cache for icons, keyed by (name, is_dark_theme, custom_color)
_icon_cache: dict[tuple[str, bool, str | None], QIcon] = {}

# Maximum cache size to prevent memory issues
_MAX_CACHE_SIZE = 256


def icon(name: str) -> QIcon:
    """Get an icon by FreeDesktop name.

    Always uses bundled icons when available for cross-platform consistency.
    SVG icons are themed based on the current application theme (light/dark).
    Falls back to system theme icons if no bundled icon exists.

    Args:
        name: FreeDesktop icon name (e.g., "network-cloud")

    Returns:
        QIcon instance (may be null if no icon found)

    Example:
        btn.setIcon(icon("network-cloud"))
    """
    return _get_icon_impl(name, None)


def themed_icon(name: str, color: str) -> QIcon:
    """Get an icon with a custom color.

    Args:
        name: FreeDesktop icon name (e.g., "media-playback-start")
        color: Custom color in hex format (e.g., "#FFFFFF" or "#2EA043")

    Returns:
        QIcon instance with the custom color applied

    Example:
        btn.setIcon(themed_icon("media-playback-start", "#FFFFFF"))
    """
    return _get_icon_impl(name, color)


def _get_icon_impl(name: str, custom_color: str | None) -> QIcon:
    """Internal implementation for getting icons with optional custom color."""
    is_dark = _is_dark_theme()
    cache_key = (name, is_dark, custom_color)

    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    # If cache is too large, clear old entries (FIFO-style approximation)
    if len(_icon_cache) >= _MAX_CACHE_SIZE:
        # Remove approximately 25% of oldest entries
        keys_to_remove = list(_icon_cache.keys())[: _MAX_CACHE_SIZE // 4]
        for key in keys_to_remove:
            del _icon_cache[key]

    # Always prefer bundled icons for cross-platform uniformity
    fallback_name = _FALLBACK_MAP.get(name)
    if fallback_name:
        fallback_path = ICONS_DIR / fallback_name
        if fallback_path.exists():
            result = _load_themed_svg(fallback_path, custom_color)
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


def style_ok_cancel_button_box(
    button_box: QDialogButtonBox, *, accept_text_key: str = "settings.save"
) -> None:
    """Label and icon a standard OK/Cancel ``QDialogButtonBox`` with the app theme.

    The accept button is presented as Save (or the label named by
    ``accept_text_key``) and Cancel with the translated labels, both using the
    bundled app-theme icons, so the buttons never fall back to the platform
    theme's icons or the (untranslated) Qt standard labels.
    """
    from hsync_desktop.i18n import tr

    ok = button_box.button(QDialogButtonBox.StandardButton.Ok)
    if ok is not None:
        ok.setText(tr(accept_text_key))
        ok.setIcon(icon("document-save"))
    cancel = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel is not None:
        cancel.setText(tr("settings.cancel"))
        cancel.setIcon(icon("dialog-cancel"))

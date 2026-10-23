# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Resolve the desktop's configured fonts and apply them to the application.

The packaged app forces Qt's built-in ``generic`` platform theme on Linux
(``main.py::_harden_linux_gsettings``) because the GTK3 theme plugin crashes
against the host GSettings schemas when GLib is bundled. The ``generic`` theme
does not read the desktop's font configuration, so this module reads it directly
(GNOME/Ubuntu through ``gsettings``, KDE through ``kdeglobals``) and applies it
with ``QApplication.setFont`` — no fonts are bundled.
"""

from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QApplication

from hsync_desktop.config import FONT_SCALE_COMPACT, FONT_SCALE_STANDARD

# GNOME settings that hold the UI font, the monospace font and the text scale.
_GSETTINGS_SCHEMA = "org.gnome.desktop.interface"
_GNOME_UI_KEY = "font-name"
_GNOME_MONO_KEY = "monospace-font-name"
_GNOME_SCALE_KEY = "text-scaling-factor"

# Keep the text-scaling factor in a sane range (a corrupt value must not make
# the UI unusable).
_MIN_SCALE = 0.5
_MAX_SCALE = 3.0

# Dense text (log viewer, license) is one point smaller than the desktop
# monospace, never below this floor.
_SMALL_FONT_DELTA = -1.0
_MIN_SMALL_POINT_SIZE = 8.0

# The log viewer carries the longest lines (timestamp + level + paths), so it
# goes one point further down than the other dense text.
_LOG_FONT_DELTA = -2.0
_MIN_LOG_POINT_SIZE = 7.0

# Compact appearance: one point smaller across the UI and monospace bases.
_COMPACT_FONT_DELTA = -1.0
_MIN_COMPACT_POINT_SIZE = 8.0
# Minimum row height in device-independent pixels: WCAG 2.2 target size (24 px)
# with a little breathing room.
_MIN_TABLE_ROW_HEIGHT = 26

# Environment variables that must not leak the PyInstaller/AppImage libraries
# into the host ``gsettings`` binary (it would then load the bundled GLib/schemas
# and can crash or misread the settings).
_LIBRARY_ENV_KEYS = (
    "LD_LIBRARY_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "GI_TYPELIB_PATH",
    "GDK_PIXBUF_MODULE_FILE",
)

# Pango font description: "<family> <size>", family may contain spaces.
_PANGO_FONT_RE = re.compile(r"^(?P<family>.+?)\s+(?P<size>\d+(?:[.,]\d+)?)$")
_PANGO_STYLE_SUFFIXES = (" Bold Italic", " Bold", " Italic", " Regular")

# Cached monospace font (set by apply_system_fonts, read by monospace_font).
_mono_font: QFont | None = None

# Cached UI font (set by apply_system_fonts, read by ui_font).
_ui_font: QFont | None = None


@dataclass(frozen=True)
class SystemFonts:
    """The resolved UI and monospace fonts for the current desktop."""

    ui: QFont
    mono: QFont


# ── Parsers ──────────────────────────────────────────────────────────────────


def _strip_style(family: str) -> str:
    """Drop a trailing Pango style word so the family matches an installed name."""
    for suffix in _PANGO_STYLE_SUFFIXES:
        if family.endswith(suffix):
            return family[: -len(suffix)].strip()
    return family


def parse_pango_font(value: str) -> tuple[str, float | None] | None:
    """Parse a Pango font description (GNOME ``font-name`` style).

    ``"'Ubuntu Sans 11'"`` -> ``("Ubuntu Sans", 11.0)``.  A description without a
    trailing size keeps the family and returns ``None`` as the size.
    """
    text = value.strip().strip("'").strip()
    if not text:
        return None
    match = _PANGO_FONT_RE.match(text)
    if match:
        family = match.group("family").strip()
        size: float | None = float(match.group("size").replace(",", "."))
    else:
        family = text
        size = None
    family = _strip_style(family)
    if not family:
        return None
    return family, size


def parse_kde_font(value: str) -> tuple[str, float | None] | None:
    """Parse a ``kdeglobals`` font value (``"Noto Sans,10,-1,5,..."``)."""
    text = value.strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split(",")]
    family = parts[0]
    if not family:
        return None
    size: float | None = None
    if len(parts) > 1:
        try:
            candidate = float(parts[1])
        except ValueError:
            candidate = 0.0
        if candidate > 0:
            size = candidate
    return family, size


# ── Desktop probes ───────────────────────────────────────────────────────────


def _host_env() -> dict[str, str]:
    """Environment for host tools: drop the bundled-library overrides."""
    env = os.environ.copy()
    for key in _LIBRARY_ENV_KEYS:
        env.pop(key, None)
    return env


def _gsettings_values(keys: tuple[str, ...]) -> dict[str, str]:
    """Read several keys from ``org.gnome.desktop.interface`` in one call.

    One ``gsettings list-recursively`` spawn replaces three ``get`` calls, so
    startup pays one process (and one timeout budget) instead of three.
    """
    if shutil.which("gsettings") is None:
        return {}
    try:
        result = subprocess.run(
            ["gsettings", "list-recursively", _GSETTINGS_SCHEMA],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
            env=_host_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0:
        return {}
    wanted = set(keys)
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[1] in wanted:
            values[parts[1]] = parts[2].strip()
    return values


def _parse_scale(raw: str | None) -> float:
    """Return the GNOME text-scaling factor, clamped, defaulting to 1.0."""
    if raw is None:
        return 1.0
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    if not _MIN_SCALE <= value <= _MAX_SCALE:
        return 1.0
    return value


def _kde_font(key: str) -> str | None:
    """Read a ``[General]`` font value from ``kdeglobals``."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(config_home) / "kdeglobals"
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    if parser.has_option("General", key):
        return parser.get("General", key)
    return None


def _desktop() -> str:
    """Classify the current desktop from ``XDG_CURRENT_DESKTOP``."""
    value = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if any(name in value for name in ("gnome", "unity", "ubuntu")):
        return "gnome"
    if any(name in value for name in ("kde", "plasma")):
        return "kde"
    return ""


# ── Resolution ───────────────────────────────────────────────────────────────


def _scaled(font: QFont, scale: float) -> QFont:
    """Return ``font`` with its point size multiplied by ``scale``."""
    result = QFont(font)
    if scale != 1.0 and result.pointSizeF() > 0:
        result.setPointSizeF(result.pointSizeF() * scale)
    return result


def _offset_font(font: QFont, delta: float, floor: float) -> QFont:
    """Return ``font`` shifted by ``delta`` points, never below ``floor``."""
    result = QFont(font)
    size = result.pointSizeF()
    if size > 0:
        result.setPointSizeF(max(size + delta, floor))
    return result


def _resolve_font(
    choice: tuple[str, float | None] | None,
    fallback: QFont,
    scale: float,
) -> QFont:
    """Build a font from a parsed choice, falling back to the Qt system font.

    A configured family that is not installed is left to Qt/fontconfig to
    substitute — the same substitution a native GNOME/KDE app gets — while the
    configured size is preserved. Only a missing choice falls back to the Qt
    system font (which would otherwise lose the desktop's size, the visible
    difference on Ubuntu where the schema default ``Cantarell`` is not installed).
    """
    if choice is None:
        return _scaled(fallback, scale)
    family, size = choice
    font = QFont(family)
    point = size if (size is not None and size > 0) else fallback.pointSizeF()
    font.setPointSizeF(point * scale)
    return font


def resolve_system_fonts(font_scale: str = FONT_SCALE_STANDARD) -> SystemFonts:
    """Resolve the desktop UI/monospace fonts, falling back to Qt's defaults."""
    base_ui = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    base_mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    if not sys.platform.startswith("linux"):
        ui, mono = QFont(base_ui), QFont(base_mono)
    else:
        desktop = _desktop()
        scale = 1.0
        ui_choice: tuple[str, float | None] | None = None
        mono_choice: tuple[str, float | None] | None = None
        if desktop == "gnome":
            values = _gsettings_values((_GNOME_UI_KEY, _GNOME_MONO_KEY, _GNOME_SCALE_KEY))
            ui_choice = parse_pango_font(values.get(_GNOME_UI_KEY, ""))
            mono_choice = parse_pango_font(values.get(_GNOME_MONO_KEY, ""))
            scale = _parse_scale(values.get(_GNOME_SCALE_KEY))
        elif desktop == "kde":
            ui_choice = parse_kde_font(_kde_font("font") or "")
            mono_choice = parse_kde_font(_kde_font("fixed") or "")
        ui = _resolve_font(ui_choice, base_ui, scale)
        mono = _resolve_font(mono_choice, base_mono, scale)
    if font_scale == FONT_SCALE_COMPACT:
        ui = _offset_font(ui, _COMPACT_FONT_DELTA, _MIN_COMPACT_POINT_SIZE)
        mono = _offset_font(mono, _COMPACT_FONT_DELTA, _MIN_COMPACT_POINT_SIZE)
    return SystemFonts(ui, mono)


def apply_system_fonts(app: QApplication, font_scale: str = FONT_SCALE_STANDARD) -> None:
    """Apply the desktop fonts (with the chosen scale) and cache them."""
    global _mono_font, _ui_font
    fonts = resolve_system_fonts(font_scale)
    app.setFont(fonts.ui)
    _ui_font = fonts.ui
    _mono_font = fonts.mono


def ui_font() -> QFont:
    """Return the resolved UI font (the application font before resolution)."""
    if _ui_font is not None:
        return QFont(_ui_font)
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)


def monospace_font() -> QFont:
    """Return the resolved monospace font (Qt's fixed font before resolution)."""
    if _mono_font is not None:
        return QFont(_mono_font)
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def _point_smaller_monospace(delta: float, floor: float) -> QFont:
    """Return the monospace font *delta* points smaller, never below *floor*."""

    font = monospace_font()
    size = font.pointSizeF()
    if size > 0:
        font.setPointSizeF(max(size + delta, floor))
    return font


def table_font() -> QFont:
    """Return the file-table font, which follows the global font scale.

    Standard uses the desktop size; Compact already reduced the UI base by one
    point. Keeping the table on the same base as the UI avoids a second size
    knob. Consumers: the file-panel table.
    """

    return ui_font()


def table_row_height() -> int:
    """Minimum file-table row height in device-independent pixels.

    Keeps the click target comfortable (WCAG 2.2 target size) for the table font.
    """

    metrics = QFontMetrics(table_font())
    return max(metrics.height() + 8, _MIN_TABLE_ROW_HEIGHT)


def small_monospace_font() -> QFont:
    """Return the monospace font one point smaller for dense text (floor 8 pt).

    Consumers: the license dialog.
    """

    return _point_smaller_monospace(_SMALL_FONT_DELTA, _MIN_SMALL_POINT_SIZE)


def log_monospace_font() -> QFont:
    """Return the log-viewer font: two points below the desktop monospace (floor 7 pt).

    The log lines are long, so the panel spends one extra point of size to fit
    more characters per line without horizontal scrolling. Consumers:
    the main window log panel.
    """

    return _point_smaller_monospace(_LOG_FONT_DELTA, _MIN_LOG_POINT_SIZE)

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Theme management for HSYNC Desktop.

Provides light and dark themes using QPalette and QSS stylesheets
for a modern, consistent look across platforms.
"""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

# Theme identifiers
THEME_LIGHT = "light"
THEME_DARK = "dark"
# Follow the desktop colour scheme (resolved at launch and on live changes).
THEME_SYSTEM = "system"


def _qt_color_scheme() -> Qt.ColorScheme | None:
    """Qt's view of the desktop scheme, or ``None`` when unavailable."""
    if QApplication.instance() is None:
        return None
    try:
        return QGuiApplication.styleHints().colorScheme()
    except (AttributeError, RuntimeError):
        return None


def _strip_gvariant(value: str | None) -> str:
    return (value or "").strip().strip("'\"").lower()


def _kde_color_scheme() -> str | None:
    """Read ``[General] ColorScheme`` from ``kdeglobals`` (KDE/Plasma)."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(config_home) / "kdeglobals"
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    scheme = parser.get("General", "ColorScheme", fallback="").strip().lower()
    return scheme or None


def _gtk_ini_prefers_dark() -> bool | None:
    """Read the GTK 3/4 ``settings.ini`` preference, if present."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    for directory in ("gtk-4.0", "gtk-3.0"):
        path = Path(config_home) / directory / "settings.ini"
        if not path.is_file():
            continue
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        prefer = parser.get("Settings", "gtk-application-prefer-dark-theme", fallback="")
        if prefer.strip().lower() in {"1", "true", "yes"}:
            return True
        theme = parser.get("Settings", "gtk-theme-name", fallback="").strip().lower()
        if theme:
            return "dark" in theme
    return None


def _linux_desktop_is_dark() -> bool | None:
    """Best-effort Linux scheme when Qt's platform theme reports ``Unknown``.

    The app forces ``QT_QPA_PLATFORMTHEME=generic`` on Linux (see
    ``main.py::_harden_linux_gsettings``) to avoid a GTK plugin crash, which
    also hides the desktop scheme from ``styleHints()``. Read the host settings
    directly instead: an explicit ``GTK_THEME``, GNOME gsettings, KDE
    ``kdeglobals``, then the GTK ``settings.ini``.
    """
    gtk_theme = os.environ.get("GTK_THEME", "").strip().lower()
    if gtk_theme:
        return "dark" in gtk_theme

    # Reuse the host gsettings reader (it strips the bundled-library env so the
    # host binary and schemas are used); the local import avoids a cycle.
    from hsync_desktop.fonts import _gsettings_values

    values = _gsettings_values(("color-scheme", "gtk-theme"))
    scheme = _strip_gvariant(values.get("color-scheme"))
    if scheme == "prefer-dark":
        return True
    if scheme == "prefer-light":
        return False
    theme = _strip_gvariant(values.get("gtk-theme"))
    if theme:
        return "dark" in theme

    kde = _kde_color_scheme()
    if kde:
        return "dark" in kde

    return _gtk_ini_prefers_dark()


def detect_system_theme() -> str:
    """Detect the system's color scheme (light or dark).

    Qt's ``styleHints().colorScheme()`` is the primary source. When it reports
    ``Unknown`` (Linux with the hardened generic platform theme), the desktop
    settings are read directly; the host palette is the last fallback.
    """
    scheme = _qt_color_scheme()
    if scheme == Qt.ColorScheme.Dark:
        return THEME_DARK
    if scheme == Qt.ColorScheme.Light:
        return THEME_LIGHT
    if sys.platform.startswith("linux"):
        desktop = _linux_desktop_is_dark()
        if desktop is not None:
            return THEME_DARK if desktop else THEME_LIGHT
    app = QApplication.instance()
    if isinstance(app, QApplication):
        window = app.palette().color(QPalette.ColorRole.Window)
        if window.lightness() < 128:
            return THEME_DARK
    return THEME_LIGHT


# ─── Color Palette ───────────────────────────────────────────────────────────

# System accent color - will be initialized from system palette
_system_accent: QColor | None = None


def _get_system_accent() -> QColor:
    """Get the system's accent/highlight color, with fallback to blue."""
    global _system_accent
    if _system_accent is None:
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            # Get highlight color from system palette before we override it
            _system_accent = app.palette().color(QPalette.ColorRole.Highlight)
        else:
            _system_accent = QColor("#0078D4")  # Fallback blue
    return _system_accent


def _get_accent_hover() -> QColor:
    """Get a darker version of the accent color for hover states."""
    accent = _get_system_accent()
    return accent.darker(115)


# Status colors
COLOR_CONNECTED = QColor("#2EA043")
COLOR_DISCONNECTED = QColor("#CF222E")
COLOR_WAITING = QColor("#BF8700")


def _build_light_palette() -> QPalette:
    """Build the light theme palette."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor("#F5F5F5"))
    p.setColor(QPalette.ColorRole.WindowText, QColor("#1E1E1E"))
    p.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#F0F0F0"))
    p.setColor(QPalette.ColorRole.Text, QColor("#1E1E1E"))
    p.setColor(QPalette.ColorRole.Button, QColor("#E8E8E8"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor("#1E1E1E"))
    p.setColor(QPalette.ColorRole.Highlight, _get_system_accent())
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#1E1E1E"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#888888"))
    p.setColor(QPalette.ColorRole.Light, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Midlight, QColor("#E0E0E0"))
    p.setColor(QPalette.ColorRole.Mid, QColor("#C0C0C0"))
    p.setColor(QPalette.ColorRole.Dark, QColor("#A0A0A0"))
    p.setColor(QPalette.ColorRole.Shadow, QColor("#707070"))
    return p


def _build_dark_palette() -> QPalette:
    """Build the dark theme palette."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor("#1E1E1E"))
    p.setColor(QPalette.ColorRole.WindowText, QColor("#D4D4D4"))
    p.setColor(QPalette.ColorRole.Base, QColor("#252526"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#2D2D2D"))
    p.setColor(QPalette.ColorRole.Text, QColor("#D4D4D4"))
    p.setColor(QPalette.ColorRole.Button, QColor("#333333"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor("#D4D4D4"))
    p.setColor(QPalette.ColorRole.Highlight, _get_system_accent())
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2D2D2D"))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#D4D4D4"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666666"))
    p.setColor(QPalette.ColorRole.Light, QColor("#404040"))
    p.setColor(QPalette.ColorRole.Midlight, QColor("#353535"))
    p.setColor(QPalette.ColorRole.Mid, QColor("#2A2A2A"))
    p.setColor(QPalette.ColorRole.Dark, QColor("#1A1A1A"))
    p.setColor(QPalette.ColorRole.Shadow, QColor("#0A0A0A"))
    return p


# ─── Global QSS ─────────────────────────────────────────────────────────────

_COMMON_QSS = """
/* The splash is the only plain QWidget top-level window; it opts into
   WA_StyledBackground so this frame is painted at all. */
QWidget#SplashScreen {{
    background-color: {window_bg};
    border: 1px solid {window_border};
}}
QToolTip {{
    background-color: #FFFFC8;
    color: #1E1E1E;
    padding: 4px 8px;
    border: 1px solid #C0A000;
    border-radius: 4px;
}}
QPushButton {{
    padding: 6px 16px;
    border: 1px solid {button_border};
    border-radius: 6px;
    min-height: 28px;
}}
QPushButton:disabled {{
    color: {disabled_text};
}}
QPushButton:hover {{
    background-color: {btn_hover};
}}
QPushButton:pressed {{
    background-color: {btn_pressed};
}}
QToolButton:disabled {{
    color: {disabled_text};
}}
QPushButton#primaryButton {{
    background-color: {accent};
    color: #FFFFFF;
    border: none;
}}
QPushButton#primaryButton:hover {{
    background-color: {accent_hover};
}}
QGroupBox {{
    font-weight: bold;
    background-color: transparent;
    border: 1px solid {group_border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QFrame#radioCard {{
    border: 1px solid {border};
    border-radius: 8px;
    background-color: transparent;
}}
QFrame#radioCard:hover {{
    border-color: {accent};
}}
QFrame#radioCard[selected="true"] {{
    border: 2px solid {accent};
    background-color: {card_selected};
}}
QLabel#stepBadgeCurrent {{
    background-color: {accent};
    color: #FFFFFF;
    border-radius: 11px;
    font-weight: bold;
}}
QLabel#stepBadgeDone {{
    background-color: {card_selected};
    color: {muted_text};
    border: 1px solid {border};
    border-radius: 11px;
}}
QLabel#stepBadgeTodo {{
    color: {muted_text};
    border: 1px solid {border};
    border-radius: 11px;
}}
QPlainTextEdit#logView {{
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px;
}}
QLabel#simulationBadge {{
    background-color: {simulation_bg};
    color: {simulation_fg};
    border: 1px solid {simulation_border};
    border-radius: 4px;
    padding: 1px 8px;
}}
QStatusBar {{
    border-top: 1px solid {border};
}}
QMenuBar {{
    padding: 2px 0px;
}}
QMenuBar::item {{
    padding: 6px 10px;
    border: none;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {menu_hover};
}}
QMenuBar::item:pressed {{
    background-color: {accent};
    color: #FFFFFF;
}}
QMenuBar::item:disabled {{
    color: {disabled_text};
}}
QMenu {{
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 6px 24px;
    border: none;
    border-radius: 4px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    background-color: {menu_hover};
}}
QMenu::item:disabled {{
    color: {disabled_text};
}}
QLineEdit:disabled {{
    color: {disabled_text};
}}
QSpinBox:disabled {{
    color: {disabled_text};
}}
QComboBox:disabled {{
    color: {disabled_text};
}}
QCheckBox:disabled {{
    color: {disabled_text};
}}
QRadioButton:disabled {{
    color: {disabled_text};
}}
QLabel:disabled {{
    color: {disabled_text};
}}
QLabel#inlineError {{
    color: {error_text};
}}
QLabel#statusOk {{
    color: {success_text};
}}
QLabel#statusError {{
    color: {error_text};
}}
QLabel#mutedHint {{
    color: {muted_text};
}}
QLineEdit[error="true"], QComboBox[error="true"], QSpinBox[error="true"] {{
    border: 1px solid {error_text};
}}
"""


def _light_qss() -> str:
    return _COMMON_QSS.format(
        border="#D0D0D0",
        group_border="#D0D0D0",
        button_border="#D0D0D0",
        btn_hover="#DCDCDC",
        btn_pressed="#C8C8C8",
        accent=_get_system_accent().name(),
        accent_hover=_get_accent_hover().name(),
        disabled_text="#A0A0A0",
        menu_hover="#E0E0E0",
        error_text="#C0392B",
        muted_text="#6A6A6A",
        success_text="#2EA043",
        card_selected="#EAF5EE",
        # Window frame of the frameless splash/About overlay: a step stronger
        # than the in-app frames (#D0D0D0) so it reads against any desktop.
        window_bg="#F5F5F5",
        window_border="#C0C0C0",
        # Simulation Mode badge: the warning tone of the info banners, so the
        # "nothing is applied" state reads the same everywhere.
        simulation_bg="#FFF3CD",
        simulation_fg="#856404",
        simulation_border="#FFC107",
    )


def _dark_qss() -> str:
    return _COMMON_QSS.format(
        border="#404040",
        # Lighter than the shared border: #404040 sat at ~1.6:1 against the
        # #1E1E1E window and the Settings section frames disappeared.
        group_border="#555555",
        # The button surface is #333333, so the shared #404040 border was
        # invisible; keep the section-frame tone but a step lighter.
        button_border="#666666",
        btn_hover="#3A3A3A",
        btn_pressed="#454545",
        accent=_get_system_accent().name(),
        accent_hover=_get_accent_hover().name(),
        disabled_text="#606060",
        menu_hover="#3A3A3A",
        error_text="#FF6B6B",
        muted_text="#9A9A9A",
        success_text="#3FB950",
        card_selected="#1F2A23",
        window_bg="#1E1E1E",
        window_border="#555555",
        simulation_bg="#3A3000",
        simulation_fg="#FFD866",
        simulation_border="#8A6D00",
    )


# ─── Public API ──────────────────────────────────────────────────────────────


def apply_theme(app: QApplication, theme: str = THEME_LIGHT) -> None:
    """Apply the specified theme to the application."""
    if theme == THEME_DARK:
        app.setPalette(_build_dark_palette())
        app.setStyleSheet(_dark_qss())
    else:
        app.setPalette(_build_light_palette())
        app.setStyleSheet(_light_qss())

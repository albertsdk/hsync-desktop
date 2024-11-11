# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Theme management for HSYNC Desktop.

Provides light and dark themes using QPalette and QSS stylesheets
for a modern, consistent look across platforms.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Theme identifiers
THEME_LIGHT = "light"
THEME_DARK = "dark"

# ─── Color Palette ───────────────────────────────────────────────────────────

# Accent color used across both themes
ACCENT = QColor("#0078D4")
ACCENT_HOVER = QColor("#106EBE")

# Status colors
COLOR_CONNECTED = QColor("#2EA043")
COLOR_DISCONNECTED = QColor("#CF222E")
COLOR_WAITING = QColor("#BF8700")
COLOR_ERROR = QColor("#CF222E")


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
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
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
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
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
QToolTip {{
    padding: 4px 8px;
    border: 1px solid {border};
    border-radius: 4px;
}}
QPushButton {{
    padding: 6px 16px;
    border: 1px solid {border};
    border-radius: 6px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {btn_hover};
}}
QPushButton:pressed {{
    background-color: {btn_pressed};
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
    border: 1px solid {border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QPlainTextEdit#logViewer {{
    font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px;
}}
QStatusBar {{
    border-top: 1px solid {border};
}}
"""


def _light_qss() -> str:
    return _COMMON_QSS.format(
        border="#D0D0D0", btn_hover="#DCDCDC", btn_pressed="#C8C8C8",
        accent=ACCENT.name(), accent_hover=ACCENT_HOVER.name(),
    )


def _dark_qss() -> str:
    return _COMMON_QSS.format(
        border="#404040", btn_hover="#3A3A3A", btn_pressed="#454545",
        accent=ACCENT.name(), accent_hover=ACCENT_HOVER.name(),
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


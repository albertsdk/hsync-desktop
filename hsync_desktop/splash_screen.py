# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Welcome splash screen shown at application startup.

Displays the application name, version, and auto-dismisses after a few seconds.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from hsync_desktop import __version__
from hsync_desktop.i18n import tr


class SplashScreen(QWidget):
    """Small frameless welcome window that auto-dismisses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(380, 200)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        # Application name
        name_label = QLabel(tr("app.name"))
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        layout.addSpacing(8)

        # Welcome message
        welcome_label = QLabel(tr("app.welcome"))
        welcome_font = QFont()
        welcome_font.setPointSize(11)
        welcome_label.setFont(welcome_font)
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_label)

        layout.addSpacing(12)

        # Version
        version_text = tr("app.version").format(version=__version__)
        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: gray;")
        layout.addWidget(version_label)

        self.setStyleSheet(
            "SplashScreen {"
            "  background-color: palette(window);"
            "  border: 1px solid palette(mid);"
            "  border-radius: 10px;"
            "}"
        )

    def show_and_dismiss(self, duration_ms: int = 3000) -> None:
        """Show the splash screen and auto-close after *duration_ms* ms."""
        self.show()
        # Center on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        QTimer.singleShot(duration_ms, self.close)


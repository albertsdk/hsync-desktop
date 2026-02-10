# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Welcome splash screen shown at application startup.

Displays the application name, version, and auto-dismisses after a few seconds.
UI is loaded from ui/splash_screen.ui (Qt Designer).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QWidget

from hsync_desktop import __version__
from hsync_desktop.i18n import tr
from hsync_desktop.ui.loader import load_ui_widget


class SplashScreen(QWidget):
    """Small frameless welcome window that auto-dismisses."""

    # Emitted when the splash screen is closed
    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(380, 200)

        # Load UI from .ui file
        load_ui_widget("splash_screen", self)

        # Get widget references
        self._lbl_app_name: QLabel = self.findChild(QLabel, "lblAppName")  # type: ignore[assignment]
        self._lbl_welcome: QLabel = self.findChild(QLabel, "lblWelcome")  # type: ignore[assignment]
        self._lbl_version: QLabel = self.findChild(QLabel, "lblVersion")  # type: ignore[assignment]

        # Set translated texts
        self._apply_translations()

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._lbl_app_name.setText(tr("app.name"))
        self._lbl_welcome.setText(tr("app.welcome"))
        self._lbl_version.setText(tr("app.version").format(version=__version__))

    def show_and_dismiss(self, duration_ms: int = 2500) -> None:
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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Emit finished signal when closing."""
        self.finished.emit()
        super().closeEvent(event)


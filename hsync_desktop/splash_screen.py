# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Welcome splash screen shown at application startup.

Displays the application name, version, and auto-dismisses after a few seconds.
UI is loaded from ui/splash_screen.ui (Qt Designer).
"""

from __future__ import annotations

import sys

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
        # On production (frozen) builds, do not advertise the exact version on
        # the auto-shown splash. The About dialog (show_as_about) still shows it
        # on explicit user request.
        if getattr(sys, "frozen", False):
            self._lbl_version.hide()
        self.show()
        # Center on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        QTimer.singleShot(duration_ms, self.close)

    def show_as_about(self) -> None:
        """Show the splash screen as an About dialog (no auto-dismiss)."""
        self._is_about = True
        self.show()
        # Center on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Close on click when shown as About dialog."""
        if getattr(self, "_is_about", False):
            self.close()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Close on Esc when shown as About dialog."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Emit finished signal when closing (only for splash, not About)."""
        if not getattr(self, "_is_about", False):
            self.finished.emit()
        super().closeEvent(event)

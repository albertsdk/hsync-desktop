# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Welcome splash screen shown at application startup.

Shows the brand logo, the app name, the version line (app and engine), a short
tagline and the copyright. UI is loaded from ui/splash_screen.ui (Qt Designer).
The Help → About window is a separate dialog (``hsync_desktop/about_dialog.py``).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QWidget

from hsync_desktop import __version__
from hsync_desktop.about_text import version_text
from hsync_desktop.branding import LOGO_PATH, LOGO_WIDTH
from hsync_desktop.engine import BinaryVersionProbe
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
        # A plain QWidget does not paint its stylesheet background/border
        # without this; the splash frame comes from the theme's
        # ``QWidget#SplashScreen`` rule.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(420, 330)

        # Load UI from .ui file
        load_ui_widget("splash_screen", self)

        # Get widget references
        self._lbl_logo: QLabel = self.findChild(QLabel, "lblLogo")  # type: ignore[assignment]
        self._lbl_app_name: QLabel = self.findChild(QLabel, "lblAppName")  # type: ignore[assignment]
        self._lbl_version: QLabel = self.findChild(QLabel, "lblVersion")  # type: ignore[assignment]
        self._lbl_tagline: QLabel = self.findChild(QLabel, "lblTagline")  # type: ignore[assignment]
        self._lbl_copyright: QLabel = self.findChild(QLabel, "lblCopyright")  # type: ignore[assignment]
        self._lbl_author: QLabel = self.findChild(QLabel, "lblAuthor")  # type: ignore[assignment]

        self._set_logo()
        self._apply_translations()
        self._start_engine_version_probe()

    def _set_logo(self) -> None:
        """Show the horizontal brand logo above the app name."""
        if LOGO_PATH.is_file():
            self._lbl_logo.setPixmap(QIcon(str(LOGO_PATH)).pixmap(QSize(LOGO_WIDTH, LOGO_WIDTH)))

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._lbl_app_name.setText(tr("app.name"))
        self._lbl_version.setText(version_text(__version__, "…"))
        self._lbl_tagline.setText(tr("app.tagline"))
        self._lbl_copyright.setText(tr("about.copyright"))
        self._lbl_author.setText(tr("about.author"))

    def _start_engine_version_probe(self) -> None:
        """Resolve the bundled engine's version without blocking startup.

        The probe emits immediately on a cache hit and otherwise runs
        ``hsync --version`` through a ``QProcess``, so the splash never delays
        the window while the binary is queried.
        """
        self._engine_probe = BinaryVersionProbe(None, self)
        self._engine_probe.finished.connect(self._apply_engine_version)
        self._engine_probe.start()

    @Slot(str)
    def _apply_engine_version(self, version: str) -> None:
        """Fill the engine part of the version line, or an em dash when unknown."""
        self._lbl_version.setText(version_text(__version__, version or "—"))

    def show_and_dismiss(self, duration_ms: int = 2500) -> None:
        """Show the splash screen and auto-close after *duration_ms* ms."""
        self.show()
        self._center_on_screen()
        QTimer.singleShot(duration_ms, self.close)

    def _center_on_screen(self) -> None:
        """Center the window on the current screen."""
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Dismiss the splash on click."""
        self.close()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Close the splash on Esc."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Emit finished when the splash closes."""
        self.finished.emit()
        super().closeEvent(event)

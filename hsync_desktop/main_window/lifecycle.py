# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value, misc"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""LifecycleMixin: startup, shutdown, tray and single-instance handling."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast
from urllib.parse import urlsplit

from hsync_common.endpoint import parse_host_port
from hsync_common.format import format_bytes
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QFontMetrics,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.bandwidth_dialog import BandwidthDialog
from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SERVER_TRUST,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine import (
    HsyncEngine,
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    list_bootnode_trust,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    supports_peer_trust,
)
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.settings import (
    SETTINGS_APP,
    SETTINGS_ORG,
    ApiKeyDialog,
    P2PKeyDialog,
    SettingsDialog,
    are_notifications_enabled,
    build_hsync_args,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
)
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import (
    COLOR_CONNECTED,
    COLOR_DISCONNECTED,
    COLOR_WAITING,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.dialogs import confirm


class LifecycleMixin:
    def eventFilter(self, obj, event) -> bool:  # type: ignore[no-untyped-def]
        """Event filter to handle clicks on bandwidth labels."""
        from PySide6.QtCore import QEvent

        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Check if the clicked widget is one of our bandwidth labels
            bandwidth_labels = [
                self._lbl_sent,
                self._sent_label,
                self._lbl_recv,
                self._recv_label,
            ]
            if obj in bandwidth_labels:
                self._show_bandwidth_dialog()
                return True
        return super().eventFilter(obj, event)

    def _toggle_visibility(self) -> None:
        """Toggle window visibility (show/hide)."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
        # Update tray menu text after visibility change
        if self._tray:
            self._tray.set_window_visible(self.isVisible())

    def _quit(self) -> None:
        """Quit the application, confirming first while a sync is running."""
        if self._engine.is_running:
            if not confirm(
                self,
                title=tr("menu.sync.confirm_quit_title"),
                text=tr("menu.sync.confirm_quit"),
                icon_name=QMessageBox.Icon.Question,
            ):
                return
        self._shutdown()

    def _shutdown(self) -> None:
        """Stop the engine and close the app once the user has confirmed."""
        if self._engine.is_running:
            self._engine.stop()
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("window/geometry", self.saveGeometry())
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray instead of closing (no notification)."""
        if self._tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            # Update tray menu to show "Show" instead of "Minimize"
            self._tray.set_window_visible(False)
        else:
            # No tray available – actually close
            self._quit()
            event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the overlay toast anchored when the window is resized."""
        super().resizeEvent(event)
        if getattr(self, "_info_banner", None) is not None and not self._info_banner.isHidden():
            self._position_info_banner()

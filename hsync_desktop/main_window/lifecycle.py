# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value, misc"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""LifecycleMixin: startup, shutdown, tray and single-instance handling."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import (
    QCloseEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings import (
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.widgets.dialogs import confirm


class LifecycleMixin:
    def eventFilter(self, obj, event) -> bool:  # type: ignore[no-untyped-def]
        """Event filter for the clickable status-bar labels."""
        from PySide6.QtCore import QEvent

        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if obj in (getattr(self, "_remote_icon", None), getattr(self, "_remote_label", None)):
                self._show_connection_badge_menu()
                return True
            # The folder icon opens the share's folder; the name opens the share
            # selector (or Settings while nothing is configured).
            if obj is getattr(self, "_path_icon_label", None):
                self._open_active_folder()
                return True
            if obj is getattr(self, "_path_label", None):
                self._on_share_name_clicked()
                return True
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
            # The sync state names the pending work, so its click shows the plan
            # that would apply it instead of sending the user to the menu. Any
            # other state keeps the label inert.
            if obj is getattr(self, "_sync_state_label", None):
                if (
                    self._sync_state[0] in ("pending", "pending_other")
                    and self._can_preview_changes()
                ):
                    self._on_preview_changes()
                return True
        return super().eventFilter(obj, event)

    def _bring_to_front(self) -> None:
        """Show, restore and focus the window (a notification or tray click).

        ``showNormal`` also clears a minimised state, ``raise_`` moves the window
        above the others and ``activateWindow`` gives it the keyboard focus: a
        single call so every entry point behaves the same. A window that is
        already on screen and focused is left as it is (no flicker).
        """
        if self.isMinimized():
            self.showNormal()
        elif not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        if self._tray:
            self._tray.set_window_visible(True)

    def _on_notification_clicked(self) -> None:
        """A system notification was clicked: bring the app forward.

        The notification is only raised while the window is hidden, minimised or
        behind another application, so this is the user asking for the app.
        """
        self._bring_to_front()

    def _toggle_visibility(self) -> None:
        """Toggle window visibility (show/hide)."""
        if self.isVisible():
            self.hide()
            # Update tray menu text after visibility change
            if self._tray:
                self._tray.set_window_visible(False)
        else:
            self._bring_to_front()

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
            self._engine.stop_and_wait()
        # A scan/import still in flight must never outlive the panel: joining
        # them here keeps a later window teardown from destroying a live
        # ``QThread`` (which aborts the process).
        self._file_panel.stop_background_work()
        # Capture any settings edits made since the last switch before quitting.
        self._share_store.snapshot_active()
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

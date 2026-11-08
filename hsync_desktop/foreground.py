# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Foreground detection shared by every surface that decides "is the app in front".

Two rules depend on it: a system notification is suppressed while the app is
already in front (the in-app toast conveys the same message), and an *important*
result opens a modal dialog instead of a notification.

The naive test — ``window.isActiveWindow()`` — is wrong whenever a dialog is
open: the dialog owns the focus, so the main window reports ``False`` and the app
would notify the user about something it is showing on screen at that very
moment. A window is "in front" when the application's active window is the main
window itself or one of its children (a modal dialog, the settings window, a
wizard page), and the main window is not minimised.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QApplication, QWidget

__all__ = ["app_in_foreground"]

# Guard against a window that was already deleted (a late callback from a tray
# notification must not raise).
_is_valid: Any = None
try:  # pragma: no cover - import-only compatibility
    from shiboken6 import isValid as _is_valid
except ImportError:  # pragma: no cover - shiboken is a PySide6 dependency
    _is_valid = None


def _active_window() -> QWidget | None:
    """The application's active window (one indirection, so a test can stub it).

    The offscreen platform used by the test suite has no real focus, so patching
    ``QApplication.instance`` would break the Qt test plugin's own teardown.
    """
    app: Any = QApplication.instance()
    return app.activeWindow() if app is not None else None


def _owned_by(window: QWidget, widget: Any) -> bool:
    """True when *widget* is *window* or one of its (possibly dialog) children.

    ``QWidget.isAncestorOf`` returns False for a top-level dialog even when the
    dialog's parent is the window, because Qt classifies it as a window rather
    than a child widget. The ``QObject`` parent chain has no such distinction.
    """
    node = widget
    while node is not None:
        if node is window:
            return True
        if _is_valid is not None and not _is_valid(node):
            return False
        node = node.parent()
    return False


def app_in_foreground(window: QWidget) -> bool:
    """True when *window* (or one of its dialogs) is the focused, visible window."""
    if _is_valid is not None and not _is_valid(window):
        return False
    if not window.isVisible() or window.isMinimized():
        return False
    active = _active_window()
    if active is None:
        # Some window managers report no active window for a fraction of a
        # second (or on platforms where the concept does not exist): fall back
        # to the widget's own state instead of assuming "background".
        return window.isActiveWindow()
    return _owned_by(window, active)

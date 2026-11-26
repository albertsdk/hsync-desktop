# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tooltip wrapping at display time.

Qt word-wraps a tooltip only when its text looks like rich text:
``QTipLabel::updateSize`` calls ``setWordWrap(Qt::mightBeRichText(text))`` and
falls back to wrapping only when the single line is wider than the screen. A
plain-text tooltip therefore stays on one line, and the ``QToolTip`` QSS
``max-width`` cap merely clips the overflow: the tip's width is bounded but the
text does not wrap. :class:`TooltipWrapFilter` rewrites the text as rich text
just before Qt shows it, so every tip wraps while ``QWidget.toolTip()`` /
``QAction.toolTip()`` keep returning the plain, localized string (the contract
the tests and the "show tooltips" preference rely on).
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QAbstractItemView, QMenu, QToolTip, QWidget

__all__ = ["TooltipWrapFilter", "install_tooltip_wrap_filter", "rich_tooltip"]

# ``installEventFilter`` does not take ownership; keep the installed filters
# referenced so Python does not collect them while the app runs.
_installed_filters: list[TooltipWrapFilter] = []


def rich_tooltip(text: str) -> str:
    """Return *text* as minimal rich text so Qt word-wraps the shown tooltip.

    Markup is escaped and ``white-space: pre-wrap`` keeps runs of spaces and
    explicit line breaks, so the rendered text equals *text*. An empty string
    is returned unchanged (no empty tooltip markup).
    """
    if not text:
        return ""
    return f'<span style="white-space:pre-wrap">{escape(text, quote=False)}</span>'


def _tooltip(obj: QObject, event: QHelpEvent) -> tuple[str, QRect]:
    """The plain tooltip text and bounding rect Qt would show for *obj*.

    A ``QMenu`` shows its *actions'* tooltips (only when ``toolTipsVisible``) and
    a view's viewport shows a *cell's* ``ToolTipRole``; both pass a rect so the
    tip hides when the pointer leaves the item, which the filter must preserve.
    An empty rect means "the whole widget".
    """
    view = obj.parent()
    if isinstance(view, QAbstractItemView) and view.viewport() is obj:
        index = view.indexAt(event.pos())
        if index.isValid():
            data = view.model().data(index, Qt.ItemDataRole.ToolTipRole)
            if isinstance(data, str):
                return data, view.visualRect(index)
        return "", QRect()
    if isinstance(obj, QMenu):
        # Qt suppresses action tooltips unless the menu opts in.
        if not obj.toolTipsVisible():
            return "", QRect()
        action = obj.actionAt(event.pos())
        if action is None:
            return "", QRect()
        return action.toolTip(), obj.actionGeometry(action)
    if isinstance(obj, QWidget):
        return obj.toolTip(), QRect()
    return "", QRect()


class TooltipWrapFilter(QObject):
    """Application event filter that rich-textizes tooltips before display.

    Installed on the ``QApplication``, it intercepts the ``QEvent.ToolTip`` Qt
    delivers to the hovered widget, a menu or a view's viewport, resolves the
    plain text, and re-shows it as rich text so it word-wraps. The rect (menu
    action, view cell) is forwarded so the tip still hides on leaving the item.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt naming)
        if event.type() != QEvent.Type.ToolTip or not isinstance(event, QHelpEvent):
            return False
        text, rect = _tooltip(obj, event)
        if not text:
            return False
        widget = obj if isinstance(obj, QWidget) else None
        QToolTip.showText(event.globalPos(), rich_tooltip(text), widget, rect)
        event.accept()
        return True


def install_tooltip_wrap_filter(app: QObject) -> TooltipWrapFilter:
    """Install the tooltip filter on *app* and keep a reference to it.

    ``installEventFilter`` does not take ownership, so the filter is kept alive
    by a module-level list rather than by parenting it to *app* (which callers
    may pass as a stand-in).
    """
    event_filter = TooltipWrapFilter()
    app.installEventFilter(event_filter)
    _installed_filters.append(event_filter)
    return event_filter

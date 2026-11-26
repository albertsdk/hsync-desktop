# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for display-time tooltip wrapping (``hsync_desktop.widgets.tooltips``).

Qt only word-wraps rich text, so a plain-text tooltip stays on one line and the
QSS ``max-width`` cap clips it. The filter rewrites the shown tip as rich text
without changing the stored ``toolTip()`` string.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QLabel, QMenu, QTableWidget, QTableWidgetItem, QToolTip

from hsync_desktop.widgets import tooltips
from hsync_desktop.widgets.tooltips import (
    TooltipWrapFilter,
    _tooltip,
    install_tooltip_wrap_filter,
    rich_tooltip,
)


def _shown_tooltip(qapp, *hovered):
    """The visible tooltip label Qt is currently showing, if any.

    The tooltip is a top-level ``QLabel`` carrying the ``Qt::ToolTip`` window
    flag; the hovered widget is excluded explicitly because a plain top-level
    label shares that flag.
    """
    return next(
        (
            w
            for w in qapp.topLevelWidgets()
            if isinstance(w, QLabel)
            and w.isVisible()
            and all(w is not h for h in hovered)
            and bool(w.windowFlags() & Qt.WindowType.ToolTip)
        ),
        None,
    )


def _help_event(pos: QPoint) -> QHelpEvent:
    return QHelpEvent(QEvent.Type.ToolTip, pos, pos)


class TestRichTooltip:
    def test_escapes_markup_so_it_renders_literally(self):
        assert rich_tooltip("a & b < c > d") == (
            '<span style="white-space:pre-wrap">a &amp; b &lt; c &gt; d</span>'
        )

    def test_preserves_runs_of_spaces_and_newlines(self):
        assert rich_tooltip("a  b\nc") == ('<span style="white-space:pre-wrap">a  b\nc</span>')

    def test_empty_stays_empty(self):
        assert rich_tooltip("") == ""


class TestTooltipText:
    """``_tooltip`` resolves the text (and rect) Qt would show for each host."""

    def test_widget_uses_its_own_tooltip(self, qtbot):
        widget = QLabel("x")
        qtbot.addWidget(widget)
        widget.setToolTip("hello")
        text, rect = _tooltip(widget, _help_event(QPoint(1, 1)))
        assert text == "hello"
        assert rect.isEmpty()

    def test_item_view_uses_the_cell_tooltip_role_and_rect(self, qtbot, qapp):
        table = QTableWidget(1, 1)
        qtbot.addWidget(table)
        item = QTableWidgetItem("cell")
        item.setToolTip("cell tip")
        table.setItem(0, 0, item)
        table.resize(200, 80)
        table.show()
        qapp.processEvents()
        rect = table.visualItemRect(item)
        if rect.isEmpty():
            pytest.skip("table layout unavailable on this platform")
        text, tip_rect = _tooltip(table.viewport(), _help_event(rect.center()))
        assert text == "cell tip"
        # The cell rect is forwarded so the tip hides when leaving the cell.
        assert tip_rect == table.visualRect(table.model().index(0, 0))

    def test_menu_uses_the_hovered_action_tooltip(self, qtbot, qapp):
        menu = QMenu()
        qtbot.addWidget(menu)
        menu.setToolTipsVisible(True)
        action = menu.addAction("Do it")
        action.setToolTip("menu tip")
        menu.show()
        qapp.processEvents()
        geometry = menu.actionGeometry(action)
        if geometry.isEmpty():
            pytest.skip("menu layout unavailable on this platform")
        text, _ = _tooltip(menu, _help_event(geometry.center()))
        assert text == "menu tip"

    def test_menu_tooltips_are_suppressed_unless_visible(self, qtbot, qapp):
        """Qt suppresses menu action tooltips by default; the filter must too."""
        menu = QMenu()
        qtbot.addWidget(menu)
        action = menu.addAction("Do it")
        action.setToolTip("menu tip")
        menu.show()
        qapp.processEvents()
        geometry = menu.actionGeometry(action)
        if geometry.isEmpty():
            pytest.skip("menu layout unavailable on this platform")
        event = _help_event(geometry.center())
        assert menu.toolTipsVisible() is False
        text, rect = _tooltip(menu, event)
        assert text == ""
        assert rect.isEmpty()
        assert TooltipWrapFilter().eventFilter(menu, event) is False


class TestTooltipWrapFilter:
    def test_event_filter_rewrites_a_widget_tooltip_to_rich_text(self, qtbot, qapp):
        widget = QLabel("hover")
        qtbot.addWidget(widget)
        widget.resize(200, 40)
        widget.show()
        widget.setToolTip("long " * 40)
        event_filter = TooltipWrapFilter()
        try:
            assert event_filter.eventFilter(widget, _help_event(QPoint(5, 5))) is True
            tip = _shown_tooltip(qapp, widget)
            assert tip is not None
            # Qt accepts the rewritten text as rich text and wraps it.
            assert tip.wordWrap() is True
            assert tip.text().startswith('<span style="white-space:pre-wrap">')
        finally:
            QToolTip.hideText()

    def test_event_filter_ignores_an_empty_tooltip(self, qtbot):
        widget = QLabel("hover")
        qtbot.addWidget(widget)
        event_filter = TooltipWrapFilter()
        assert event_filter.eventFilter(widget, _help_event(QPoint(1, 1))) is False

    def test_installed_filter_wraps_on_real_event_dispatch(self, qtbot, qapp):
        event_filter = install_tooltip_wrap_filter(qapp)
        try:
            assert event_filter in tooltips._installed_filters
            widget = QLabel("hover")
            qtbot.addWidget(widget)
            widget.resize(120, 30)
            widget.show()
            widget.setToolTip("plain tip text")
            qapp.sendEvent(widget, _help_event(QPoint(5, 5)))
            tip = _shown_tooltip(qapp, widget)
            assert tip is not None
            assert tip.text().startswith('<span style="white-space:pre-wrap">')
        finally:
            QToolTip.hideText()
            qapp.removeEventFilter(event_filter)
            tooltips._installed_filters.remove(event_filter)

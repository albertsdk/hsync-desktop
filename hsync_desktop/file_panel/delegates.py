# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Item delegates that draw the transfer table's progress bar and centered icons."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
)


class ProgressBarDelegate(QStyledItemDelegate):
    """Custom delegate that renders a progress bar with centered percentage."""

    def paint(self, painter, option, index):
        progress = index.data(Qt.ItemDataRole.UserRole)
        if progress is None or progress < 0:
            return  # Nothing to paint

        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = progress
        opt.text = f"{progress}%"
        opt.textVisible = True

        style = QApplication.style()
        if style:
            style.drawControl(QStyle.ControlElement.CE_ProgressBar, opt, painter)


class CenteredIconDelegate(QStyledItemDelegate):
    """Custom delegate that centers the icon in the cell."""

    def paint(self, painter, option, index):
        # Draw selection background if selected
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Get the icon from the item
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon and not icon.isNull():
            # Calculate centered position
            icon_size = option.decorationSize
            x = option.rect.x() + (option.rect.width() - icon_size.width()) // 2
            y = option.rect.y() + (option.rect.height() - icon_size.height()) // 2
            icon.paint(painter, x, y, icon_size.width(), icon_size.height())

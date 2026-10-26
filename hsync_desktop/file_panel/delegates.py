# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Item delegate that draws the transfer table's progress bar."""

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

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Toggle Switch widget for Qt applications.

A modern iOS/Android-style toggle switch that can be used as a replacement
for QCheckBox when a more visual on/off control is desired.

Based on: https://stackoverflow.com/questions/14780517/toggle-switch-in-qt
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget


class ToggleSwitch(QAbstractButton):
    """
    A toggle switch widget with smooth animation.

    Signals:
        toggled(bool): Emitted when the switch state changes.

    Properties:
        checked: Whether the switch is on (True) or off (False).
        track_color_off: Background color when off.
        track_color_on: Background color when on.
        thumb_color: Color of the sliding thumb.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Colors
        self._track_color_off = QColor("#B0B0B0")
        self._track_color_on = QColor("#0078D4")
        self._thumb_color = QColor("#FFFFFF")
        self._track_opacity = 1.0

        # Animation
        self._thumb_position = 0.0
        self._animation = QPropertyAnimation(self, b"thumb_position", self)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setDuration(150)

        # Connect signals
        self.toggled.connect(self._on_toggled)

    # ── Size ────────────────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def minimumSizeHint(self) -> QSize:
        return QSize(36, 20)

    # ── Properties ──────────────────────────────────────────────────────────

    def get_thumb_position(self) -> float:
        return self._thumb_position

    def set_thumb_position(self, pos: float) -> None:
        self._thumb_position = pos
        self.update()

    thumb_position = Property(float, get_thumb_position, set_thumb_position)

    @property
    def track_color_off(self) -> QColor:
        return self._track_color_off

    @track_color_off.setter
    def track_color_off(self, color: QColor) -> None:
        self._track_color_off = color
        self.update()

    @property
    def track_color_on(self) -> QColor:
        return self._track_color_on

    @track_color_on.setter
    def track_color_on(self, color: QColor) -> None:
        self._track_color_on = color
        self.update()

    @property
    def thumb_color(self) -> QColor:
        return self._thumb_color

    @thumb_color.setter
    def thumb_color(self, color: QColor) -> None:
        self._thumb_color = color
        self.update()

    # ── Slots ───────────────────────────────────────────────────────────────

    def _on_toggled(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._thumb_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    # ── Painting ────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dimensions
        w = self.width()
        h = self.height()
        track_height = h * 0.6
        track_radius = track_height / 2
        thumb_diameter = h * 0.8
        thumb_radius = thumb_diameter / 2
        margin = (h - track_height) / 2

        # Track rectangle
        track_rect = QRect(
            0,
            int(margin),
            w,
            int(track_height),
        )

        # Interpolate track color based on thumb position
        t = self._thumb_position
        track_color = QColor(
            int(self._track_color_off.red() + t * (self._track_color_on.red() - self._track_color_off.red())),
            int(self._track_color_off.green() + t * (self._track_color_on.green() - self._track_color_off.green())),
            int(self._track_color_off.blue() + t * (self._track_color_on.blue() - self._track_color_off.blue())),
        )

        # Draw track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, track_radius, track_radius)

        # Calculate thumb position
        thumb_margin = (h - thumb_diameter) / 2
        thumb_travel = w - thumb_diameter - 2 * thumb_margin
        thumb_x = thumb_margin + self._thumb_position * thumb_travel
        thumb_y = (h - thumb_diameter) / 2

        # Draw thumb shadow
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(QBrush(shadow_color))
        painter.drawEllipse(int(thumb_x + 1), int(thumb_y + 1), int(thumb_diameter), int(thumb_diameter))

        # Draw thumb
        painter.setBrush(QBrush(self._thumb_color))
        painter.drawEllipse(int(thumb_x), int(thumb_y), int(thumb_diameter), int(thumb_diameter))

        painter.end()

    # ── Mouse Events ────────────────────────────────────────────────────────

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self.isChecked())
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)


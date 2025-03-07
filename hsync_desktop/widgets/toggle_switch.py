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
)
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget


class ToggleSwitch(QAbstractButton):
    """
    A toggle switch widget with smooth animation.

    Uses system palette colors for theme compatibility:
    - Track off: Mid color from palette
    - Track on: Highlight (accent) color from palette
    - Thumb: Base color from palette

    Signals:
        toggled(bool): Emitted when the switch state changes.

    Properties:
        checked: Whether the switch is on (True) or off (False).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

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

    def _get_palette_colors(self) -> tuple[QColor, QColor, QColor]:
        """Get colors from the current palette for theme compatibility."""
        palette = self.palette()
        # Track off: use Mid color (gray)
        track_off = palette.color(QPalette.ColorRole.Mid)
        # Track on: use Highlight color (accent/selection color)
        track_on = palette.color(QPalette.ColorRole.Highlight)
        # Thumb: use Base color (white in light theme, dark in dark theme)
        # But we want the thumb to always be visible, so use Light color
        thumb = palette.color(QPalette.ColorRole.Light)
        return track_off, track_on, thumb

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

        # Get colors from palette
        track_color_off, track_color_on, thumb_color = self._get_palette_colors()

        # Dimensions
        w = self.width()
        h = self.height()
        track_height = h * 0.8
        track_radius = track_height / 4
        thumb_diameter = h * 0.8
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
            int(track_color_off.red() + t * (track_color_on.red() - track_color_off.red())),
            int(track_color_off.green() + t * (track_color_on.green() - track_color_off.green())),
            int(track_color_off.blue() + t * (track_color_on.blue() - track_color_off.blue())),
        )

        # Draw track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, track_radius, track_radius)

        # Calculate thumb position
        thumb_margin = (h - thumb_diameter) / 2
        thumb_travel = w - thumb_diameter - 2 * thumb_margin
        thumb_x = thumb_margin + self._thumb_position * thumb_travel

        # Thumb dimensions: slightly wider rectangle with rounded corners
        thumb_width = thumb_diameter * 0.9
        thumb_height = thumb_diameter * 0.7
        thumb_radius = thumb_height / 3
        thumb_y_centered = (h - thumb_height) / 2

        # Draw thumb shadow
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(QBrush(shadow_color))
        painter.drawRoundedRect(
            int(thumb_x + 1),
            int(thumb_y_centered + 1),
            int(thumb_width),
            int(thumb_height),
            thumb_radius,
            thumb_radius,
        )

        # Draw thumb
        painter.setBrush(QBrush(thumb_color))
        painter.drawRoundedRect(
            int(thumb_x),
            int(thumb_y_centered),
            int(thumb_width),
            int(thumb_height),
            thumb_radius,
            thumb_radius,
        )

        painter.end()

    # ── Mouse Events ────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

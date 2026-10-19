# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The wizard step indicator: numbered badges plus the per-step labels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from hsync_desktop.i18n import tr

__all__ = ["StepIndicator"]

_STEP_KEYS = (
    "wizard.step.mode",
    "wizard.step.folder",
    "wizard.step.connection",
    "wizard.step.review",
)

_BADGE = 22
_INNER_SPACING = 6


class StepIndicator(QWidget):
    """Numbered progress bar: done = check, current = accent, todo = muted.

    Labels are elided to the available width so long translations do not clip;
    the accessible name carries the "Step N of M: <label>" orientation.
    """

    def __init__(self, count: int) -> None:
        super().__init__()
        self._count = count
        self._current = 0
        self._badges: list[QLabel] = []
        self._labels: list[QLabel] = []
        self._full_texts: list[str] = [""] * count
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        for _ in range(count):
            step = QWidget()
            step_layout = QHBoxLayout(step)
            step_layout.setContentsMargins(0, 0, 0, 0)
            step_layout.setSpacing(_INNER_SPACING)
            badge = QLabel()
            badge.setFixedSize(_BADGE, _BADGE)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_layout.addWidget(badge)
            label = QLabel()
            step_layout.addWidget(label)
            self._badges.append(badge)
            self._labels.append(label)
            layout.addWidget(step, 1)
        self.apply_translations()

    def apply_translations(self) -> None:
        for index in range(self._count):
            self._full_texts[index] = tr(_STEP_KEYS[index]) if index < len(_STEP_KEYS) else ""
        self._apply_elision()
        self.set_current(self._current)

    def set_current(self, index: int) -> None:
        self._current = index
        for position in range(self._count):
            badge = self._badges[position]
            label = self._labels[position]
            if position < index:
                badge.setText("✓")
                badge.setObjectName("stepBadgeDone")
                label.setObjectName("")
                label.setEnabled(True)
            elif position == index:
                badge.setText(str(position + 1))
                badge.setObjectName("stepBadgeCurrent")
                label.setObjectName("")
                label.setEnabled(True)
            else:
                badge.setText(str(position + 1))
                badge.setObjectName("stepBadgeTodo")
                label.setObjectName("mutedHint")
                label.setEnabled(False)
            badge.style().unpolish(badge)
            badge.style().polish(badge)
            label.style().unpolish(label)
            label.style().polish(label)
        self._update_accessible_text()

    def _update_accessible_text(self) -> None:
        if self._current < self._count:
            label = self._full_texts[self._current] if self._full_texts else ""
            current = self._current + 1
        else:
            label = ""
            current = self._count
        self.setAccessibleName(tr("wizard.step_counter").format(current=current, total=self._count))
        self.setAccessibleDescription(label)

    def _apply_elision(self) -> None:
        """Elide every label to its share of the available width."""
        metrics = self.fontMetrics()
        layout = self.layout()
        spacing = layout.spacing() if layout is not None else 0
        per_step = max(24, (self.width() - spacing * (self._count - 1)) // self._count)
        label_width = max(24, per_step - _BADGE - _INNER_SPACING)
        for index, label in enumerate(self._labels):
            label.setText(
                metrics.elidedText(
                    self._full_texts[index], Qt.TextElideMode.ElideRight, label_width
                )
            )

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._apply_elision()

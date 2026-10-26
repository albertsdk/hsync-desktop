# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Reusable widgets for the setup wizard.

Small, focused helpers (inline errors, a selectable mode card, a masked secret
field, a label+switch row) shared by the wizard pages. They deliberately mirror
existing patterns (``settings/form_helpers`` labels, the ``#primaryButton``
style, the Settings ``ToggleSwitch``) instead of inventing a second visual
language.
"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.toggle_switch import ToggleSwitch

__all__ = [
    "InlineError",
    "PrimaryButton",
    "RadioCard",
    "SecretField",
    "char_class_validator",
    "section_title",
    "set_field_error",
]


def char_class_validator(allowed: str) -> QRegularExpressionValidator:
    """A keystroke validator that admits only characters from *allowed*.

    Structural rules (start/end characters, length) stay in the on-Continue
    validation; this only stops disallowed characters from being typed.
    """
    return QRegularExpressionValidator(QRegularExpression(rf"^[{allowed}]*$"))


class InlineError(QLabel):
    """An inline error label tied to one field (hidden when empty)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inlineError")
        self.setWordWrap(True)
        self.setVisible(False)

    def show_message(self, message: str) -> None:
        self.setText(message)
        self.setVisible(bool(message))


def set_field_error(field: QWidget, error: InlineError, message: str) -> None:
    """Mark *field* invalid and render *message* (empty clears the state)."""
    field.setProperty("error", bool(message))
    field.style().unpolish(field)
    field.style().polish(field)
    error.show_message(message)


class PrimaryButton(QPushButton):
    """Accent button whose optional icon sits *after* the text.

    ``QPushButton`` always places ``setIcon`` on the leading side, so the label
    and the trailing icon are laid out explicitly. The text still comes from
    :meth:`setText` (and is exposed as the accessible name).
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("primaryButton")
        self._label = QLabel()
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._icon_label = QLabel()
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._icon_label.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self._label)
        layout.addWidget(self._icon_label)
        layout.addStretch(1)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._label.setText(text)
        self.setAccessibleName(text)

    def text(self) -> str:
        return self._label.text()

    def setTrailingIcon(self, icon: QIcon) -> None:  # noqa: N802 (Qt naming)
        """Show *icon* after the text (pass a null icon to hide it)."""
        self._icon_label.setPixmap(icon.pixmap(16, 16))
        self._icon_label.setVisible(not icon.isNull())

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        layout = self.layout()
        if layout is None:
            return base
        hint = layout.sizeHint()
        # Account for the QSS padding (6px vertical, 16px per side).
        return QSize(
            max(base.width(), hint.width() + 32),
            max(base.height(), hint.height() + 12),
        )


class RadioCard(QFrame):
    """A selectable card wrapping a real ``QRadioButton`` (keyboard/AT friendly).

    The whole card forwards a click to the radio button; the radio keeps the
    accessible name/description so screen readers and the tab order behave
    normally. Cards are made mutually exclusive by the owning page's
    ``QButtonGroup``. The ``selected`` dynamic property drives the QSS state.
    """

    selected = Signal(object)  # the card's value

    def __init__(self, value: object, title: str, description: str, icon_name: str = "") -> None:
        super().__init__()
        self.value = value
        self.setObjectName("radioCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self._icon = QLabel()
        if icon_name:
            self._icon.setPixmap(icon(icon_name).pixmap(24, 24))
        self._icon.setFixedSize(28, 28)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.radio = QRadioButton(title)
        self.radio.toggled.connect(self._on_toggled)
        text.addWidget(self.radio)

        self._description = muted_label(description)
        text.addWidget(self._description)
        layout.addLayout(text, 1)

        self.radio.setAccessibleDescription(description)
        self._refresh_selected()

    def _on_toggled(self, checked: bool) -> None:
        self._refresh_selected()
        if checked:
            self.selected.emit(self.value)

    def _refresh_selected(self) -> None:
        self.setProperty("selected", self.radio.isChecked())
        self.style().unpolish(self)
        self.style().polish(self)

    def set_selected(self, value: bool) -> None:
        self.radio.setChecked(value)

    def is_selected(self) -> bool:
        return self.radio.isChecked()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.radio.setChecked(True)
        super().mousePressEvent(event)

    def retranslate(self, title: str, description: str) -> None:
        self.radio.setText(title)
        self.radio.setAccessibleName(title)
        self.radio.setAccessibleDescription(description)
        self._description.setText(description)
        self._sync_description_height()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._sync_description_height()

    def _sync_description_height(self) -> None:
        """Keep the wrapped caption at the height its text needs.

        A word-wrapped ``QLabel`` reports one line as its minimum height, so a
        short wizard page used to squeeze the cards until the description was
        clipped top and bottom. Pinning the minimum to the wrapped height makes
        the card refuse to shrink that far; the page then scrolls instead.
        """
        width = self._description.width()
        if width <= 0:
            return
        self._description.setMinimumHeight(self._description.heightForWidth(width))


class SecretField(QWidget):
    """A masked secret line edit with a show/hide icon toggle (+ optional regenerate)."""

    def __init__(self, *, allow_regenerate: bool = False) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit, 1)

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setIcon(icon("view-hidden"))
        self.toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self.toggle)

        self.regenerate: QToolButton | None = None
        if allow_regenerate:
            self.regenerate = QToolButton()
            layout.addWidget(self.regenerate)

    def _on_toggle(self, shown: bool) -> None:
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        self.toggle.setIcon(icon("view-visible" if shown else "view-hidden"))
        self._refresh_toggle_tooltip()

    def _refresh_toggle_tooltip(self) -> None:
        text = tr("wizard.action.hide") if self.toggle.isChecked() else tr("wizard.action.show")
        self.toggle.setToolTip(text)
        self.toggle.setAccessibleName(text)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, value: str) -> None:  # noqa: N802 (Qt naming)
        self.edit.setText(value)

    def apply_translations(self) -> None:
        self._refresh_toggle_tooltip()
        if self.regenerate is not None:
            self.regenerate.setText(tr("wizard.action.regenerate"))
            self.regenerate.setToolTip(tr("wizard.action.regenerate"))


def section_title(text: str) -> QLabel:
    """A bold section heading used in the review and success pages."""
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""QFormLayout/QWidget construction helpers shared by the settings dialogs."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.widgets.forms import add_row
from hsync_desktop.widgets.toggle_switch import ToggleSwitch


def _paired_label(widget: QWidget) -> QLabel | None:
    """Return the form label shown next to *widget*, to mirror its tooltip.

    Handles form rows (the ``QFormLayout`` label of the field, where the field
    may itself be a layout or a container holding the widget).
    """
    parent = widget.parentWidget()
    if parent is None:
        return None
    layout = parent.layout()
    if isinstance(layout, QFormLayout):
        for row in range(layout.rowCount()):
            field_item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if field_item is None:
                continue
            field = field_item.widget()
            field_layout = field_item.layout()
            holds = field is widget or field is parent
            if not holds and field_layout is not None and field_layout.indexOf(widget) >= 0:
                holds = True
            if holds:
                label_item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                label = label_item.widget() if label_item is not None else None
                return label if isinstance(label, QLabel) else None
    return None


def _set_field_tooltip(widget: QWidget, text: str) -> None:
    """Set *text* as the tooltip of *widget* and of its paired label."""
    widget.setToolTip(text)
    label = _paired_label(widget)
    if label is not None:
        label.setToolTip(text)


def _maybe_tip(widget: QWidget, key: str, enabled: bool) -> None:
    """Set tooltip on *widget* (and its paired label) from *key* when *enabled*."""
    _set_field_tooltip(widget, tr(key) if enabled else "")


def _insert_row_after(anchor: QWidget, label: QWidget, field: QWidget) -> bool:
    """Insert a QFormLayout row right after the row holding ``anchor``."""
    container = anchor.parent()
    layout = container.layout() if isinstance(container, QWidget) else None
    if not isinstance(layout, QFormLayout):
        return False
    for row in range(layout.rowCount()):
        item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
        if item and item.widget() is anchor:
            if isinstance(label, QLabel):
                add_row(layout, label, field, row + 1)
            else:
                layout.insertRow(row + 1, label, field)
            return True
    return False


class _ActionRow(QWidget):
    """A row of action buttons that stacks when one row cannot show the labels.

    ``QPushButton`` clips its text instead of eliding it, so a pair of long
    localized labels would lose characters in a narrow column. The row starts
    side by side and switches to a vertical stack once the available width drops
    below the buttons' own size hints (a large system font does that).
    """

    def __init__(self, *buttons: QWidget) -> None:
        super().__init__()
        self._buttons = buttons
        self._box = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._box.setContentsMargins(0, 0, 0, 0)
        for button in buttons:
            self._box.addWidget(button)
        self._box.addStretch()

    def _needs_stack(self) -> bool:
        if self.width() <= 0:
            return False
        widths = [button.sizeHint().width() for button in self._buttons if not button.isHidden()]
        return self.width() < sum(widths) + self._box.spacing() * max(0, len(widths) - 1)

    def _apply_direction(self) -> None:
        direction = (
            QBoxLayout.Direction.TopToBottom
            if self._needs_stack()
            else QBoxLayout.Direction.LeftToRight
        )
        if self._box.direction() != direction:
            self._box.setDirection(direction)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_direction()

    def event(self, event) -> bool:
        # A retranslation or a font change moves the labels without resizing the
        # row, so re-evaluate on the resulting layout request.
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Show):
            self._apply_direction()
        return super().event(event)


def _action_row(*buttons: QWidget) -> QWidget:
    """Pack related action buttons into one left-aligned row.

    Two narrow secondary actions (open the trust stores / probe the endpoint)
    read as a pair and take less vertical space than two stacked form rows; the
    trailing stretch keeps them left-aligned.

    The row must be added with the *single-widget* ``QFormLayout`` overload
    (``addRow(container)``): that spans both columns. ``addRow("", container)``
    would put the pair back in the field column, which is only as wide as the
    caption column leaves it, and the localized labels get clipped there. When
    even the spanned width cannot hold both labels (a large system font), the
    row stacks them instead of clipping.
    """
    return _ActionRow(*buttons)


def _replace_checkbox_with_combo(parent: QWidget, checkbox_name: str) -> tuple[QComboBox, QLabel]:
    """Replace a ``QCheckBox`` field with an empty ``QComboBox`` form row.

    Same row surgery as :func:`_replace_checkbox_with_toggle`: the caption moves
    to the label column and the combo becomes the field, so a policy selector
    shares the one control column. The caller fills the items.
    """
    checkbox: QCheckBox | None = parent.findChild(QCheckBox, checkbox_name)  # type: ignore[assignment]
    combo = QComboBox(parent)
    label = QLabel(parent)
    if checkbox is None:
        return combo, label

    label.setText(checkbox.text())
    combo.setObjectName(checkbox.objectName())

    container = checkbox.parentWidget()
    layout = container.layout() if container is not None else None
    if isinstance(layout, QFormLayout):
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() == checkbox:
                layout.removeRow(row)
                add_row(layout, label, combo, row)
                return combo, label

    checkbox.deleteLater()
    return combo, label


def _replace_checkbox_with_toggle(
    parent: QWidget, checkbox_name: str
) -> tuple[ToggleSwitch, QLabel]:
    """Replace a ``QCheckBox`` field with a ``ToggleSwitch`` form row.

    The ``.ui`` forms carry the options as checkboxes whose text doubles as the
    caption. The replacement moves that caption into the form's label column and
    makes the switch the field of the same row, so every option shares the one
    control column instead of floating in it.

    Args:
        parent: The parent widget containing the checkbox.
        checkbox_name: The object name of the checkbox to replace.

    Returns:
        A tuple of (ToggleSwitch, QLabel) for the new widgets.
    """
    checkbox: QCheckBox | None = parent.findChild(QCheckBox, checkbox_name)  # type: ignore[assignment]
    toggle = ToggleSwitch(parent)
    label = QLabel(parent)
    if checkbox is None:
        return toggle, label

    text = checkbox.text()
    checked = checkbox.isChecked()
    toggle.setChecked(checked)
    toggle.setObjectName(checkbox.objectName())
    label.setText(text)

    container = checkbox.parentWidget()
    layout = container.layout() if container is not None else None
    if isinstance(layout, QFormLayout):
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() == checkbox:
                # removeRow deletes the checkbox, so its state was read above.
                layout.removeRow(row)
                add_row(layout, label, toggle, row)
                return toggle, label

    checkbox.deleteLater()
    return toggle, label

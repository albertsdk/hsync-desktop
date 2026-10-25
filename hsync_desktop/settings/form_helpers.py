# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""QFormLayout/QWidget construction helpers shared by the settings dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.widgets.toggle_switch import ToggleSwitch


def _paired_label(widget: QWidget) -> QLabel | None:
    """Return the label shown next to *widget*, to mirror its tooltip.

    Handles toggle rows (the label is a sibling inside the toggle's container)
    and form rows (the ``QFormLayout`` label of the field, where the field may
    itself be a layout or a container holding the widget).
    """
    parent = widget.parentWidget()
    if parent is None:
        return None
    if isinstance(widget, ToggleSwitch):
        layout = parent.layout()
        if layout is not None:
            for index in range(layout.count()):
                item = layout.itemAt(index)
                candidate = item.widget() if item is not None else None
                if isinstance(candidate, QLabel):
                    return candidate
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
            layout.insertRow(row + 1, label, field)
            return True
    return False


def _action_row(*buttons: QWidget) -> QWidget:
    """Pack related action buttons into one left-aligned row.

    Two narrow secondary actions (open the trust stores / probe the endpoint)
    read as a pair and take less vertical space than two stacked form rows; the
    trailing stretch keeps them left-aligned under the field column.
    """
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    for button in buttons:
        row.addWidget(button)
    row.addStretch()
    return container


def switch_row(toggle: QWidget, label: QLabel, parent: QWidget) -> QWidget:
    """Pack a switch and its caption into one left-aligned row.

    Every switch in the settings dialog uses this shape (``[toggle] caption``
    flush left, stretch after), so the toggle column and the caption column line
    up across the form, the "Notifications for" block and the advanced options.
    """
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(toggle)
    row.addWidget(label)
    row.addStretch()
    container = QWidget(parent)
    container.setLayout(row)
    return container


def _replace_checkbox_with_toggle(
    parent: QWidget, checkbox_name: str
) -> tuple[ToggleSwitch, QLabel]:
    """Replace a QCheckBox with a ToggleSwitch in a QFormLayout.

    Finds the checkbox by name, creates a ToggleSwitch with the same text,
    and replaces it in the parent layout.

    Args:
        parent: The parent widget containing the checkbox.
        checkbox_name: The object name of the checkbox to replace.

    Returns:
        A tuple of (ToggleSwitch, QLabel) for the new widgets.
    """
    checkbox: QCheckBox | None = parent.findChild(QCheckBox, checkbox_name)  # type: ignore[assignment]
    if checkbox is None:
        # Fallback: return a new toggle switch with empty label
        return ToggleSwitch(parent), QLabel(parent)

    # Get the checkbox text for the label
    text = checkbox.text()

    # Find the parent layout
    parent_layout = checkbox.parentWidget()
    if parent_layout is None:
        checkbox.deleteLater()
        return ToggleSwitch(parent), QLabel(parent)

    # Find the form layout containing this checkbox
    layout = parent_layout.layout()
    if isinstance(layout, QFormLayout):
        # Find the row containing the checkbox
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() == checkbox:
                # Create toggle switch with label
                toggle = ToggleSwitch(parent)
                label = QLabel(text, parent)
                # Replace in form layout with the shared switch row
                layout.removeRow(row)
                layout.insertRow(row, "", switch_row(toggle, label, parent))
                return toggle, label

    # Fallback: just delete and return new toggle
    checkbox.deleteLater()
    return ToggleSwitch(parent), QLabel(parent)

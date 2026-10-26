# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Form-row helpers shared by the Settings dialog and the setup wizard.

Consumers: ``settings/tab_layout.py``, ``settings/tab_builders.py`` and
``wizard/pages/connection.py``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

__all__ = ["add_row"]


def add_row(form: QFormLayout, label: QLabel, field: QWidget, row: int | None = None) -> None:
    """Add a labelled form row and link the caption to its field.

    ``setBuddy`` gives the field the caption's mnemonic/focus target on every
    platform (keyboard and assistive-tech accessibility), while ``QFormLayout``
    keeps the platform's own label alignment and field-growth hints: the dialog
    follows the host OS (right-aligned captions on macOS, left on Windows/Linux)
    instead of hard-coding one desktop's convention.

    ``row`` inserts at that index (after a removal) instead of appending.
    """
    label.setWordWrap(False)
    label.setBuddy(field)
    if row is None:
        form.addRow(label, field)
    else:
        form.insertRow(row, label, field)

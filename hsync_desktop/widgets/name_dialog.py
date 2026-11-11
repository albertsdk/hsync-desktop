# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Single-field name prompt shared by the rename/new/duplicate flows.

A dedicated dialog rather than ``QInputDialog``: Qt's prompt sizes itself to the
line edit, so a long window title is clipped by the frame, and its OK/Cancel are
Qt-owned strings that the app never sees and cannot translate.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.icons import style_ok_cancel_button_box

# Wide enough for the longest title in the supported languages without the window
# manager eliding it; the file rename dialog shares this floor.
NAME_DIALOG_MIN_WIDTH = 440


def ask_name(
    parent: QWidget | None,
    *,
    title: str,
    label: str,
    accept_text_key: str,
    initial: str = "",
    accept_icon_key: str = "dialog-ok",
    selection: tuple[int, int] | None = None,
) -> str | None:
    """Ask for a name and return it stripped, or ``None`` when cancelled.

    ``accept_text_key`` names the verb the accept button carries ("Rename",
    "Duplicate"): a generic OK would not say what is about to happen.
    ``selection`` is a ``(start, length)`` range of ``initial`` to pre-select (the
    file rename dialog selects the stem); by default the whole text is selected,
    so typing replaces it.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(NAME_DIALOG_MIN_WIDTH)

    layout = QVBoxLayout(dialog)
    caption = QLabel(label, dialog)
    caption.setWordWrap(True)
    layout.addWidget(caption)

    field = QLineEdit(initial, dialog)
    layout.addWidget(field)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    style_ok_cancel_button_box(
        buttons,
        accept_text_key=accept_text_key,
        accept_icon_key=accept_icon_key,
        cancel_text_key="action.cancel",
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if selection is None:
        field.selectAll()
    else:
        field.setSelection(*selection)
    field.setFocus()

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return field.text().strip()

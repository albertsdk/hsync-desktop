# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the shared single-field name prompt."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit

from hsync_desktop.i18n import tr
from hsync_desktop.widgets.name_dialog import NAME_DIALOG_MIN_WIDTH, ask_name


def _on_open(callback) -> None:  # type: ignore[no-untyped-def]
    """Run *callback* with the modal dialog as soon as ``ask_name`` shows it."""

    def run() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QDialog), dialog
        callback(dialog)

    QTimer.singleShot(0, run)


def _ask(qtbot, **kwargs):  # type: ignore[no-untyped-def]
    options = {
        "title": tr("shares.rename.title"),
        "label": tr("shares.new.name"),
        "accept_text_key": "shares.manage.rename",
    }
    options.update(kwargs)
    return ask_name(None, **options)


def test_returns_the_typed_name(qtbot):
    def accept(dialog: QDialog) -> None:
        dialog.findChild(QLineEdit).setText("  Beta  ")
        dialog.accept()

    _on_open(accept)
    assert _ask(qtbot) == "Beta"


def test_cancel_returns_none(qtbot):
    _on_open(lambda dialog: dialog.reject())
    assert _ask(qtbot) is None


def test_a_blank_name_comes_back_empty(qtbot):
    def accept(dialog: QDialog) -> None:
        dialog.findChild(QLineEdit).setText("   ")
        dialog.accept()

    _on_open(accept)
    assert _ask(qtbot) == ""


def test_the_window_is_wide_enough_for_the_title(qtbot):
    seen: dict[str, object] = {}

    def inspect(dialog: QDialog) -> None:
        seen["minimum_width"] = dialog.minimumWidth()
        seen["title"] = dialog.windowTitle()
        dialog.reject()

    _on_open(inspect)
    _ask(qtbot)

    assert seen["minimum_width"] == NAME_DIALOG_MIN_WIDTH
    assert seen["title"] == tr("shares.rename.title")


def test_the_buttons_are_localized_and_iconed(qtbot):
    seen: dict[str, object] = {}

    def inspect(dialog: QDialog) -> None:
        box = dialog.findChild(QDialogButtonBox)
        accept = box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        seen.update(
            accept=accept.text(),
            cancel=cancel.text(),
            accept_icon=accept.icon().isNull(),
            cancel_icon=cancel.icon().isNull(),
        )
        dialog.reject()

    _on_open(inspect)
    _ask(qtbot, accept_text_key="shares.manage.duplicate")

    assert seen["accept"] == tr("shares.manage.duplicate")
    assert seen["cancel"] == tr("action.cancel")
    assert seen["accept_icon"] is False
    assert seen["cancel_icon"] is False


def test_the_selection_preselects_the_given_range(qtbot):
    seen: dict[str, object] = {}

    def inspect(dialog: QDialog) -> None:
        seen["selected"] = dialog.findChild(QLineEdit).selectedText()
        dialog.reject()

    _on_open(inspect)
    _ask(qtbot, accept_text_key="ctx.rename_btn", initial="report.txt", selection=(0, 6))

    assert seen["selected"] == "report"


def test_everything_is_selected_by_default(qtbot):
    seen: dict[str, object] = {}

    def inspect(dialog: QDialog) -> None:
        seen["selected"] = dialog.findChild(QLineEdit).selectedText()
        dialog.reject()

    _on_open(inspect)
    _ask(qtbot, initial="report.txt")

    assert seen["selected"] == "report.txt"

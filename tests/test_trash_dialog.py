# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The trash view: listing, restore and empty over injected collaborators.

The dialog never touches the store itself — it renders ``hsync trash list`` and
forwards the two actions — so the tests drive it with fakes and pin the three
behaviours a user depends on: what is listed, what a refusal shows, and when a
button is reachable.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from hsync_desktop.engine import TrashActionResult, TrashEntrySummary, TrashListResult
from hsync_desktop.i18n import tr
from hsync_desktop.trash_dialog import TrashDialog


class _Fake:
    """One fake engine: a queue of listings and the recorded actions."""

    def __init__(self, listings: list[TrashListResult], *, restore_ok: bool = True) -> None:
        self.listings = listings
        self.restore_ok = restore_ok
        self.loads = 0
        self.restored: list[str] = []
        self.emptied = 0

    def load(self) -> TrashListResult:
        self.loads += 1
        if not self.listings:
            return TrashListResult(ok=True, entries=())
        return self.listings.pop(0)

    def restore(self, path: str) -> TrashActionResult:
        self.restored.append(path)
        return TrashActionResult(ok=self.restore_ok, message="" if self.restore_ok else "refused")

    def empty(self) -> TrashActionResult:
        self.emptied += 1
        return TrashActionResult(ok=True, message="")


def _entries(*paths: str, missing_copy: tuple[str, ...] = ()) -> TrashListResult:
    return TrashListResult(
        ok=True,
        entries=tuple(
            TrashEntrySummary(
                path=path,
                size=1024,
                deleted_at=1_700_000_000,
                payload_present=path not in missing_copy,
            )
            for path in paths
        ),
    )


def _dialog(qtbot, fake: _Fake) -> TrashDialog:
    dlg = TrashDialog(
        None,
        load=fake.load,
        restore=fake.restore,
        empty=fake.empty,
    )
    qtbot.addWidget(dlg)
    return dlg


def test_it_lists_what_the_client_reports(qtbot):
    fake = _Fake([_entries("docs/report.pdf", "b.txt")])

    dlg = _dialog(qtbot, fake)

    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0).text() == "docs/report.pdf"
    assert dlg._btn_empty.isEnabled() is True
    assert dlg._btn_restore.isEnabled() is False


def test_an_empty_store_says_so_and_disables_both_actions(qtbot):
    dlg = _dialog(qtbot, _Fake([TrashListResult(ok=True, entries=())]))

    assert dlg._table.rowCount() == 0
    assert dlg._lbl_hint.text() == tr("trash.empty_state")
    assert dlg._btn_empty.isEnabled() is False
    assert dlg._btn_restore.isEnabled() is False


def test_selecting_a_row_enables_the_restore(qtbot):
    fake = _Fake([_entries("docs/report.pdf"), _entries()])
    dlg = _dialog(qtbot, fake)

    dlg._table.selectRow(0)

    assert dlg.selected_path() == "docs/report.pdf"
    assert dlg._btn_restore.isEnabled() is True


def test_a_row_without_a_stored_copy_cannot_be_restored(qtbot):
    """The record can outlive its bytes: the row says so and stays unselectable."""
    fake = _Fake(
        [
            _entries("docs/report.pdf", "gone.txt", missing_copy=("gone.txt",)),
            _entries(),
        ]
    )
    dlg = _dialog(qtbot, fake)

    assert tr("trash.not_restorable") in dlg._table.item(1, 0).text()
    assert dlg._table.item(1, 0).toolTip() == tr("trash.not_restorable_tip")
    assert tr("trash.not_restorable") not in dlg._table.item(0, 0).text()

    dlg._table.selectRow(1)
    assert dlg.selected_path() == "gone.txt"
    assert dlg._btn_restore.isEnabled() is False

    dlg._table.selectRow(0)
    assert dlg._btn_restore.isEnabled() is True


def test_restore_forwards_the_path_and_reloads(qtbot):
    fake = _Fake([_entries("docs/report.pdf"), _entries()])
    dlg = _dialog(qtbot, fake)
    dlg._table.selectRow(0)

    dlg._on_restore()

    assert fake.restored == ["docs/report.pdf"]
    assert fake.loads == 2
    assert fake.listings == []
    assert dlg._table.rowCount() == 0
    assert tr("trash.restored").format(path="docs/report.pdf") in dlg._lbl_status.text()


def test_a_refusal_is_shown_with_the_clients_wording(qtbot, monkeypatch):
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text, *a, **k: shown.append((title, text))),
    )
    fake = _Fake([_entries("docs/report.pdf")], restore_ok=False)
    dlg = _dialog(qtbot, fake)
    dlg._table.selectRow(0)

    dlg._on_restore()

    assert shown == [(tr("notif.error"), "refused")]
    assert dlg._table.rowCount() == 1  # the refusal keeps the entry


def test_empty_needs_a_confirmation(qtbot, monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_a, **_k: QMessageBox.StandardButton.No),
    )
    fake = _Fake([_entries("a.txt"), _entries()])
    dlg = _dialog(qtbot, fake)

    dlg._on_empty()

    assert fake.emptied == 0
    assert dlg._table.rowCount() == 1


def test_confirmed_empty_clears_and_reloads(qtbot, monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_a, **_k: QMessageBox.StandardButton.Yes),
    )
    fake = _Fake([_entries("a.txt"), _entries()])
    dlg = _dialog(qtbot, fake)

    dlg._on_empty()

    assert fake.emptied == 1
    assert dlg._table.rowCount() == 0
    assert dlg._lbl_status.text() == tr("trash.empty_done")


def test_an_unreadable_store_reports_the_client_message(qtbot):
    dlg = _dialog(qtbot, _Fake([TrashListResult(ok=False, message="boom")]))

    assert dlg._lbl_hint.text() == tr("trash.list_failed")
    assert dlg._lbl_status.text() == "boom"
    assert dlg._btn_empty.isEnabled() is False


@pytest.mark.parametrize("stamp", [0, -1])
def test_a_missing_timestamp_renders_empty(qtbot, stamp):
    from hsync_desktop.trash_dialog import _deleted_label

    assert _deleted_label(stamp) == ""

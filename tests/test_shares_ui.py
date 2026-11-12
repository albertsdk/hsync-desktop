# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""UI tests for named shares: the header selector and the switch/manage flows."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from hsync_desktop.i18n import tr


@pytest.fixture(autouse=True)
def _no_message_boxes(monkeypatch):
    """Replace QMessageBox in the shares mixin so warnings never block tests."""

    class _StubQMessageBox:
        @staticmethod
        def warning(*_args, **_kwargs):
            return None

    monkeypatch.setattr("hsync_desktop.main_window.shares.QMessageBox", _StubQMessageBox)


@contextmanager
def _running(monkeypatch):
    """Make the real engine report a live run without spawning anything."""
    from hsync_desktop.engine import HsyncEngine

    with monkeypatch.context() as scope:
        scope.setattr(HsyncEngine, "is_running", property(lambda self: True))
        scope.setattr(HsyncEngine, "stop_and_wait", lambda self: None)
        yield


def _configure(window, tmp_path, bucket="team"):
    """Create + project a first share from the isolated settings."""
    s = window._share_store._s
    s.setValue("path/local", str(tmp_path / bucket))
    s.setValue("sync/bucket", bucket)
    window._share_store.sync_from_flat()
    window._set_log_share(window._share_store.active_id())
    window._apply_settings_changes()


def _add_share(window, name, folder):
    share = window._share_store.create_from_active(name, str(folder))
    return next(s for s in window._share_store.shares() if s.id == share.id)


def _accepting_confirm(monkeypatch, *, clear_state: bool = False) -> None:
    """Make the destructive share-delete box confirm itself."""
    import types

    accept = object()
    checkbox = types.SimpleNamespace(isChecked=lambda: clear_state)

    class _Box:
        def exec(self) -> int:
            return 0

        def clickedButton(self):  # noqa: N802 - Qt spelling
            return accept

    monkeypatch.setattr(
        "hsync_desktop.shares.dialog.build_destructive_confirm_box",
        lambda *_args, **_kwargs: (_Box(), accept, checkbox),
    )


class TestSharesMenu:
    def test_selector_is_hidden_without_shares(self, window):
        assert not window._share_store.has_shares()
        assert window._shares_button.isHidden()

    def test_selector_is_visible_once_a_share_exists(self, window, tmp_path):
        _configure(window, tmp_path)
        assert not window._shares_button.isHidden()

    def test_menu_lists_shares_sorted_with_the_active_checked(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        _add_share(window, "Zeta", tmp_path / "zeta")
        _add_share(window, "Alfa", tmp_path / "alfa")

        window._rebuild_shares_menu()

        actions = [a for a in window._shares_menu.actions() if a.isCheckable()]
        assert [a.text() for a in actions] == ["Alfa", "team", "Zeta"]
        assert [a.text() for a in actions if a.isChecked()] == ["team"]


class TestSwitch:
    def test_switch_applies_the_target_and_stays_stopped(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        beta = _add_share(window, "Beta", tmp_path / "beta")

        window._switch_to_share(beta.id)

        assert window._share_store.active_id() == beta.id
        assert window._local_path == str(tmp_path / "beta")
        assert window._share_store._s.value("path/local") == str(tmp_path / "beta")
        assert "Beta" in window._path_label.text()
        assert not window._engine.is_running

    def test_switch_while_running_needs_confirmation(self, window, tmp_path, monkeypatch):
        _configure(window, tmp_path, bucket="team")
        beta = _add_share(window, "Beta", tmp_path / "beta")
        first_id = window._share_store.active_id()

        with _running(monkeypatch):
            monkeypatch.setattr("hsync_desktop.main_window.shares.confirm", lambda *a, **k: False)
            window._switch_to_share(beta.id)
            assert window._share_store.active_id() == first_id

            monkeypatch.setattr("hsync_desktop.main_window.shares.confirm", lambda *a, **k: True)
            window._switch_to_share(beta.id)
            assert window._share_store.active_id() == beta.id


class TestCreateRenameDelete:
    def test_create_copies_values_but_uses_the_new_folder_and_bucket(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        window._share_store._s.setValue("sync/direction", "upload-only")
        window._share_store.snapshot_active()

        assert window._create_share("Backup casa", str(tmp_path / "backup"))

        share = window._share_store.active()
        assert share.name == "Backup casa"
        assert share.values["sync/bucket"] == "backup-casa"
        assert share.values["path/local"] == str(tmp_path / "backup")
        assert share.values["sync/direction"] == "upload-only"

    def test_create_rejects_a_duplicate_name(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        assert window._create_share("team", str(tmp_path / "other")) is False
        assert len(window._share_store.shares()) == 1

    def test_create_rejects_a_duplicate_folder(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        assert window._create_share("Other", str(tmp_path / "team")) is False
        assert len(window._share_store.shares()) == 1

    def test_rename_changes_the_label_only(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        share = window._share_store.active()

        assert window._rename_share(share.id, "Renamed")

        assert window._share_store.get(share.id).name == "Renamed"
        assert window._share_store.get(share.id).values["sync/bucket"] == "team"
        assert "Renamed" in window._path_label.text()

    def test_delete_refuses_the_last_share(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        assert window._delete_share(window._share_store.active_id(), False) is False
        assert len(window._share_store.shares()) == 1

    def test_deleting_the_active_share_applies_the_visible_neighbour(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        team_id = window._share_store.active_id()
        beta = _add_share(window, "Beta", tmp_path / "beta")
        window._switch_to_share(beta.id)
        # Display order is Beta, team: the row after Beta is "team".

        assert window._delete_share(beta.id, False, team_id) is True

        assert window._share_store.active_id() == team_id
        assert window._local_path == str(tmp_path / "team")

    def test_deleting_the_active_share_without_a_hint_uses_the_display_order(
        self, window, tmp_path
    ):
        """The neighbour is passed in, but the store must stay deterministic."""
        _configure(window, tmp_path, bucket="Mike")
        mike_id = window._share_store.active_id()
        alfa = _add_share(window, "Alfa", tmp_path / "alfa")
        _add_share(window, "Zeta", tmp_path / "zeta")

        assert window._delete_share(mike_id, False) is True

        # Insertion order would pick nothing sensible; the first row shown wins.
        assert window._share_store.active_id() == alfa.id

    def test_deleting_the_active_last_row_lands_on_the_previous_one(self, window, tmp_path):
        _configure(window, tmp_path, bucket="Alfa")
        mike = _add_share(window, "Mike", tmp_path / "mike")
        zeta = _add_share(window, "Zeta", tmp_path / "zeta")
        window._switch_to_share(zeta.id)

        assert window._delete_share(zeta.id, False, mike.id) is True

        assert window._share_store.active_id() == mike.id
        assert window._local_path == str(tmp_path / "mike")


class TestLogsAndIdentity:
    def test_logs_are_kept_per_share(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        first_id = window._share_store.active_id()
        window._append_log("line-team")
        beta = _add_share(window, "Beta", tmp_path / "beta")

        window._switch_to_share(beta.id)
        assert "line-team" not in window._log_view.toPlainText()
        window._append_log("line-beta")

        window._switch_to_share(first_id)
        assert "line-team" in window._log_view.toPlainText()
        assert "line-beta" not in window._log_view.toPlainText()

    def test_the_header_shows_the_share_name_and_a_rich_tooltip(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")

        assert window._path_label.text() == "team"
        tip = window._path_label.toolTip()
        assert str(tmp_path / "team") in tip
        assert tr("shares.tip.bucket") in tip
        assert tr("shares.tip.mode_p2p") in tip or tr("shares.tip.mode_server") in tip


class TestManageDialog:
    @staticmethod
    def _dialog(window, qtbot):
        """Open the dialog like the app does: shown, with the list focused."""
        from PySide6.QtWidgets import QApplication

        from hsync_desktop.shares.dialog import SharesDialog

        dialog = SharesDialog(window, window)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog._list.setFocus()
        QApplication.processEvents()
        return dialog

    def test_dialog_lists_the_shares_sorted(self, window, tmp_path, qtbot):
        from hsync_desktop.shares.dialog import SharesDialog

        _configure(window, tmp_path, bucket="team")
        _add_share(window, "Beta", tmp_path / "beta")

        dialog = SharesDialog(window, window)
        qtbot.addWidget(dialog)

        names = [dialog._list.item(i).text() for i in range(dialog._list.count())]
        assert names == ["Beta", "team"]

    def test_current_row_follows_the_active_share(self, window, tmp_path, qtbot):
        """Qt makes row 0 current on focus: the highlight and the action must agree."""
        _configure(window, tmp_path, bucket="alberto")
        barbara = _add_share(window, "barbara", tmp_path / "barbara")
        window._switch_to_share(barbara.id)

        dialog = self._dialog(window, qtbot)

        assert dialog._list.item(0).text() == "alberto"
        assert dialog._current_id() == barbara.id
        assert dialog._current_name() == "barbara"

    def test_delete_acts_on_the_row_the_user_sees(self, window, tmp_path, qtbot, monkeypatch):
        _configure(window, tmp_path, bucket="alberto")
        barbara = _add_share(window, "barbara", tmp_path / "barbara")
        window._switch_to_share(barbara.id)
        dialog = self._dialog(window, qtbot)
        _accepting_confirm(monkeypatch)

        dialog._on_delete()

        assert [s.name for s in window._share_store.shares()] == ["alberto"]
        assert window._share_store.active_id() != barbara.id

    def test_dialog_selects_the_next_row_after_delete(self, window, tmp_path, qtbot, monkeypatch):
        _configure(window, tmp_path, bucket="Mike")
        alfa = _add_share(window, "Alfa", tmp_path / "alfa")
        _add_share(window, "Zeta", tmp_path / "zeta")
        window._switch_to_share(alfa.id)
        dialog = self._dialog(window, qtbot)
        _accepting_confirm(monkeypatch)

        dialog._on_delete()

        # Display order is Alfa, Mike, Zeta: the row after Alfa is Mike.
        assert dialog._current_name() == "Mike"
        assert window._share_store.active().name == "Mike"


class TestDialogStacking:
    """A box raised from a modal dialog must sit on top of that dialog."""

    def test_dialog_parent_falls_back_to_the_caller(self, window):
        from hsync_desktop.widgets.dialogs import dialog_parent

        assert dialog_parent(window) is window

    def test_dialog_parent_prefers_the_active_modal(self, window, qtbot):
        from PySide6.QtWidgets import QApplication, QDialog

        from hsync_desktop.widgets.dialogs import dialog_parent

        modal = QDialog(window)
        qtbot.addWidget(modal)
        modal.setModal(True)
        modal.show()
        QApplication.processEvents()
        try:
            if QApplication.activeModalWidget() is None:
                pytest.skip("this platform reports no active modal widget")
            assert dialog_parent(window) is modal
        finally:
            modal.close()


class TestReviewFixes:
    """Regressions for the review findings on the multi-share change."""

    def test_create_copies_live_edits_not_the_stale_record(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        # A live flat write with no snapshot trigger (like the direction menu).
        window._share_store._s.setValue("sync/direction", "upload-only")

        assert window._create_share("Beta", str(tmp_path / "beta"))

        assert window._share_store.active().values["sync/direction"] == "upload-only"

    def test_the_first_share_adopts_the_log_identity(self, window, tmp_path):
        assert not window._share_store.has_shares()
        s = window._share_store._s
        s.setValue("path/local", str(tmp_path / "team"))
        s.setValue("sync/bucket", "team")

        window._apply_settings_changes()  # creates share #1 via sync_from_flat

        share_id = window._share_store.active_id()
        assert share_id
        assert window._log_active_share == share_id
        window._append_log("first-run-line")
        assert "first-run-line" in window._log_buffers[share_id]

    def test_enforce_unique_folder_reverts_a_wizard_collision(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        _add_share(window, "Beta", tmp_path / "beta")
        # Simulate the wizard writing path/local directly to Beta's folder.
        window._share_store._s.setValue("path/local", str(tmp_path / "beta"))

        assert window._share_store.enforce_unique_folder() is True

        assert window._share_store._s.value("path/local") == str(tmp_path / "team")

    def test_create_declined_stop_creates_nothing(self, window, tmp_path, monkeypatch):
        _configure(window, tmp_path, bucket="team")
        before = len(window._share_store.shares())
        monkeypatch.setattr("hsync_desktop.main_window.shares.confirm", lambda *a, **k: False)

        with _running(monkeypatch):
            assert window._create_share("Beta", str(tmp_path / "beta")) is False

        assert len(window._share_store.shares()) == before

    def test_delete_non_active_with_clear_state_requires_stopping(
        self, window, tmp_path, monkeypatch
    ):
        _configure(window, tmp_path, bucket="team")
        beta = _add_share(window, "Beta", tmp_path / "beta")
        reset: list[str] = []
        monkeypatch.setattr(window, "_reset_sync_state", lambda folder: reset.append(folder))
        monkeypatch.setattr("hsync_desktop.main_window.shares.confirm", lambda *a, **k: False)

        with _running(monkeypatch):
            assert window._delete_share(beta.id, True) is False
            assert window._share_store.get(beta.id) is not None

            monkeypatch.setattr("hsync_desktop.main_window.shares.confirm", lambda *a, **k: True)
            assert window._delete_share(beta.id, True) is True

        assert reset == [str(tmp_path / "beta")]

    def test_the_state_reset_runs_while_the_share_still_exists(self, window, tmp_path, monkeypatch):
        """A failed reset must leave the share in place so it can be retried."""
        _configure(window, tmp_path, bucket="team")
        beta = _add_share(window, "Beta", tmp_path / "beta")
        seen: list[bool] = []
        monkeypatch.setattr(
            window,
            "_reset_sync_state",
            lambda _folder: seen.append(window._share_store.get(beta.id) is not None),
        )

        assert window._delete_share(beta.id, True) is True

        assert seen == [True]
        assert window._share_store.get(beta.id) is None

    def test_delete_reclaims_the_log_buffer(self, window, tmp_path):
        _configure(window, tmp_path, bucket="team")
        beta = _add_share(window, "Beta", tmp_path / "beta")
        window._switch_to_share(beta.id)
        window._append_log("beta-line")
        assert beta.id in window._log_buffers

        window._delete_share(beta.id, False)

        assert beta.id not in window._log_buffers


class TestSelectorChrome:
    """The header selector draws one chevron, from the app's own styling."""

    def test_the_selector_keeps_a_single_arrow(self, window):
        from PySide6.QtCore import Qt

        from hsync_desktop.themes import _dark_qss, _light_qss

        # The arrow comes from the arrowType; the style must not paint its own
        # menu indicator as well, or some styles show two chevrons.
        assert window._shares_button.objectName() == "sharesButton"
        assert window._shares_button.arrowType() == Qt.ArrowType.DownArrow
        for qss in (_light_qss(), _dark_qss()):
            assert "QToolButton#sharesButton::menu-indicator" in qss


class TestManageDialogChrome:
    """The manager dialog labels its actions with app icons, not Qt's defaults."""

    def test_the_action_buttons_carry_icons_and_no_ellipsis(self, window, tmp_path, qtbot):
        from hsync_desktop.shares.dialog import SharesDialog

        _configure(window, tmp_path, bucket="team")
        dialog = SharesDialog(window, window)
        qtbot.addWidget(dialog)

        expected = {
            dialog._btn_new: tr("shares.manage.new"),
            dialog._btn_duplicate: tr("shares.manage.duplicate"),
            dialog._btn_rename: tr("shares.manage.rename"),
            dialog._btn_delete: tr("shares.manage.delete"),
        }
        for button, label in expected.items():
            assert button.text() == label
            assert "…" not in button.text()
            assert not button.icon().isNull()

    def test_close_is_localized_and_iconed(self, window, tmp_path, qtbot):
        from PySide6.QtWidgets import QDialogButtonBox

        from hsync_desktop.shares.dialog import SharesDialog

        _configure(window, tmp_path, bucket="team")
        dialog = SharesDialog(window, window)
        qtbot.addWidget(dialog)

        box = dialog.findChild(QDialogButtonBox)
        assert box is not None
        buttons = box.buttons()
        assert len(buttons) == 1
        assert buttons[0].text() == tr("action.close")
        assert not buttons[0].icon().isNull()
        assert box.button(QDialogButtonBox.StandardButton.Close) is None

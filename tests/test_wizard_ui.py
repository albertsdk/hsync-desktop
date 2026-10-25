# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Setup wizard UI tests (navigation, validation, apply, resume)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel

import hsync_desktop.wizard.apply as apply_mod
from hsync_desktop.i18n import tr
from hsync_desktop.wizard.dialog import SetupWizard
from hsync_desktop.wizard.model import WizardDraft, WizardMode, save_draft
from hsync_desktop.wizard.validation import STEP_REVIEW


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture(autouse=True)
def fake_autostart(monkeypatch):
    class _Autostart:
        @staticmethod
        def is_supported() -> bool:
            return True

        @staticmethod
        def set_enabled(_value: bool) -> None:
            pass

    monkeypatch.setattr(apply_mod, "autostart", _Autostart)


@pytest.fixture
def wizard(qtbot, settings):
    dlg = SetupWizard(settings=settings)
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


def _select_backup(wizard):
    wizard.mode_page._cards[WizardMode.BACKUP].set_selected(True)


class TestFirstRun:
    def test_opens_at_purpose(self, wizard):
        assert wizard._step == 0
        assert wizard._draft.mode is None

    def test_inferred_mode_preselects(self, qtbot, settings, tmp_path):
        settings.setValue("path/local", str(tmp_path))
        settings.setValue("p2p/enabled", False)
        settings.setValue("sync/direction", "upload-only")
        dlg = SetupWizard(settings=settings)
        qtbot.addWidget(dlg)
        assert dlg._draft.mode == WizardMode.BACKUP
        dlg.close()


class TestNavigation:
    def test_purpose_requires_a_mode(self, wizard):
        wizard._on_primary()
        assert wizard._step == 0
        assert not wizard._general_error.isHidden()

    def test_folder_step_blocks_on_missing(self, wizard):
        _select_backup(wizard)
        wizard._on_primary()  # -> folder
        assert wizard._step == 1
        wizard._on_primary()  # empty folder -> blocked
        assert wizard._step == 1

    def test_back_returns_to_purpose(self, wizard):
        _select_backup(wizard)
        wizard._on_primary()
        wizard._on_back()
        assert wizard._step == 0


class TestBackupFlow:
    def test_full_flow_applies(self, wizard, settings, tmp_path):
        _select_backup(wizard)
        wizard._on_primary()  # -> folder
        wizard.folder_page.path.setText(str(tmp_path))
        wizard._on_primary()  # -> connection
        assert wizard._step == 2
        wizard.connection_page.server_url.setText("host.example.com")
        wizard.connection_page.api_key.setText("api-secret")
        wizard.connection_page.bucket.setText("data")
        wizard._on_primary()  # -> review
        assert wizard._step == STEP_REVIEW
        wizard._on_primary()  # finish
        assert wizard.applied is True
        assert wizard._stack.currentIndex() == 4  # success
        assert settings.value("p2p/enabled", True, bool) is False
        assert settings.value("connection/server_url") == "https://host.example.com:9753"
        assert settings.value("path/local") == str(tmp_path)

    def test_dashboard_closes(self, wizard, tmp_path):
        _select_backup(wizard)
        wizard._on_primary()
        wizard.folder_page.path.setText(str(tmp_path))
        wizard._on_primary()
        wizard.connection_page.server_url.setText("host")
        wizard.connection_page.api_key.setText("k")
        wizard.connection_page.bucket.setText("data")
        wizard._on_primary()
        wizard._on_primary()  # finish
        wizard.success_page.dashboard_requested.emit()
        assert wizard.result() == SetupWizard.DialogCode.Accepted
        assert wizard.start_requested is False


class TestLanFlow:
    def test_group_and_password_defaults(self, wizard, tmp_path):
        wizard.mode_page._cards[WizardMode.LAN_SYNC].set_selected(True)
        wizard._on_primary()
        wizard.folder_page.path.setText(str(tmp_path))
        wizard._on_primary()
        assert wizard._draft.p2p_group
        assert wizard._draft.p2p_key
        assert wizard._draft.direction == "bidirectional"


class TestResume:
    def test_resumes_from_draft(self, qtbot, settings):
        save_draft(settings, WizardDraft(mode=WizardMode.LAN_SYNC, local_path="/data"), step=2)
        dlg = SetupWizard(settings=settings)
        qtbot.addWidget(dlg)
        assert dlg._step == 2
        assert not dlg._resume.isHidden()
        dlg.close()


class TestHelpDialog:
    def test_team_path_needs_only_the_first_answer(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        assert not dlg._ok.isEnabled()
        dlg._team.setChecked(True)
        assert dlg._ok.isEnabled()
        assert dlg.mode() == WizardMode.TEAM_SHARE
        dlg.close()

    def test_copy_needs_no_network_answer(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        dlg._personal.setChecked(True)
        assert not dlg._ok.isEnabled()  # copy/edits still unanswered
        dlg._copy_only.setChecked(True)
        assert dlg._ok.isEnabled()
        assert dlg.mode() == WizardMode.BACKUP
        # A backup copy is server-side, so the network question never applies.
        assert not dlg._same_box.isEnabled()
        assert dlg._note.text() == tr("wizard.help.note_backup")
        dlg.close()

    def test_personal_same_network_maps_to_lan(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        dlg._personal.setChecked(True)
        dlg._edits_both.setChecked(True)
        assert not dlg._ok.isEnabled()  # network still unanswered
        dlg._same_yes.setChecked(True)
        assert dlg._ok.isEnabled()
        assert dlg.mode() == WizardMode.LAN_SYNC
        dlg.close()

    def test_edits_across_networks_maps_to_remote(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        dlg._personal.setChecked(True)
        dlg._edits_both.setChecked(True)
        dlg._same_no.setChecked(True)
        assert dlg._ok.isEnabled()
        assert dlg.mode() == WizardMode.REMOTE_SYNC
        dlg.close()

    def test_network_question_follows_the_copy_choice(self, qtbot):
        """The network question is asked only for sync, never for a backup copy."""
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        assert not dlg._need_box.isEnabled() and not dlg._same_box.isEnabled()
        dlg._personal.setChecked(True)
        assert dlg._need_box.isEnabled()
        assert not dlg._same_box.isEnabled()  # direction not chosen yet
        dlg._copy_only.setChecked(True)
        assert not dlg._same_box.isEnabled()  # a copy needs no network
        dlg._edits_both.setChecked(True)
        assert dlg._same_box.isEnabled()  # syncing needs the network answer
        dlg.close()

    def test_all_four_modes_are_reachable(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        reached = set()
        for mode in WizardMode:
            dlg = HelpChoiceDialog(mode)
            qtbot.addWidget(dlg)
            reached.add(dlg.mode())
            dlg.close()
        assert reached == set(WizardMode)

    def test_follow_ups_stay_visible_but_are_disabled_with_a_note(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        # Nothing is hidden: the follow-ups exist and are merely disabled.
        assert not dlg._need_box.isHidden() and not dlg._same_box.isHidden()
        assert not dlg._need_box.isEnabled() and not dlg._same_box.isEnabled()
        assert dlg._note.isHidden()
        dlg._personal.setChecked(True)
        assert dlg._need_box.isEnabled()
        assert not dlg._same_box.isEnabled()
        dlg._copy_only.setChecked(True)
        assert not dlg._note.isHidden()
        assert dlg._note.text() == tr("wizard.help.note_backup")
        dlg._edits_both.setChecked(True)
        assert dlg._note.isHidden()
        dlg._team.setChecked(True)
        assert not dlg._need_box.isEnabled() and not dlg._same_box.isEnabled()
        assert not dlg._note.isHidden()
        assert dlg._note.text() == tr("wizard.help.note_team")
        dlg.close()

    def test_buttons_are_translated(self, qtbot):
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        assert dlg._q_share.text() == tr("wizard.help.q_share")
        assert dlg._team.text() == tr("wizard.help.team")
        assert dlg._personal.text() == tr("wizard.help.personal")
        assert dlg._copy_only.text() == tr("wizard.help.copy_only")
        assert dlg._edits_both.text() == tr("wizard.help.edits_both")
        assert dlg._same_yes.text() == tr("action.yes")
        dlg.close()


class TestModeExclusivity:
    def test_only_one_card_selected(self, wizard):
        wizard.mode_page._cards[WizardMode.BACKUP].set_selected(True)
        wizard.mode_page._cards[WizardMode.LAN_SYNC].set_selected(True)
        assert wizard.mode_page._cards[WizardMode.LAN_SYNC].is_selected()
        assert not wizard.mode_page._cards[WizardMode.BACKUP].is_selected()
        assert wizard.mode_page._current_mode() == WizardMode.LAN_SYNC


class TestTestGating:
    def test_server_test_needs_url_and_key(self, wizard):
        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        assert not page.test_server.isEnabled()
        page.server_url.setText("host.example.com")
        assert not page.test_server.isEnabled()
        page.api_key.setText("key")
        assert page.test_server.isEnabled()

    def test_discovery_server_test_needs_discovery_server(self, wizard):
        page = wizard.connection_page
        page.set_mode(WizardMode.REMOTE_SYNC)
        assert not page.test_discovery_server.isEnabled()
        page.discovery_server.setText("boot.example.net")
        assert page.test_discovery_server.isEnabled()


class TestSwitches:
    def test_switches_store_into_draft(self, wizard):
        page = wizard.connection_page
        page.continuous.setChecked(False)
        page.auto_sync.setChecked(False)
        page.start_at_login.setChecked(True)
        page.receive_only.setChecked(True)
        page.cert_switch.setChecked(True)
        draft = WizardDraft(mode=WizardMode.LAN_SYNC)
        page.store(draft)
        assert draft.continuous is False
        assert draft.auto_sync is False
        assert draft.start_at_login is True
        assert draft.accept_server_cert is True
        assert draft.direction == "download-only"


class TestCharValidators:
    def test_bucket_and_group_reject_disallowed_chars(self, wizard):
        from PySide6.QtGui import QValidator

        page = wizard.connection_page
        assert page.bucket.validator().validate("ok-123_", 0)[0] == QValidator.State.Acceptable
        assert page.bucket.validator().validate("bad name!", 0)[0] == QValidator.State.Invalid
        assert page.group.validator().validate("grp.1-x", 0)[0] == QValidator.State.Acceptable
        assert page.group.validator().validate("bad/name", 0)[0] == QValidator.State.Invalid


class TestFreeSpaceFormat:
    def test_shows_human_readable_unit(self, wizard, tmp_path):
        from hsync_common.format import format_bytes

        from hsync_desktop.settings.validators import validate_sync_folder

        wizard.folder_page.path.setText(str(tmp_path))
        check = validate_sync_folder(str(tmp_path))
        expected = tr("wizard.folder.free_space").format(free=format_bytes(check.free_bytes))
        assert wizard.folder_page.free_space.text() == expected


class TestProbeStatus:
    def test_server_success_lands_on_server_status(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        page._active_target = "server"
        page._on_probe_done(ProbeOutcome(True, 200))
        assert not page.server_status.isHidden()
        assert page.server_status.text() == tr("settings.test_connection_success")
        assert page.discovery_server_status.isHidden()

    def test_server_error_lands_on_server_status(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        page._active_target = "server"
        page._on_probe_done(ProbeOutcome(False, None, reason="unreachable"))
        assert page.server_status.text() == tr("wizard.probe.unreachable")
        assert page.discovery_server_status.isHidden()

    def test_discovery_server_success_lands_on_discovery_server_status(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.REMOTE_SYNC)
        page._active_target = "discovery_server"
        page._on_probe_done(ProbeOutcome(True, fingerprint="AA:BB"))
        assert page.discovery_server_status.text() == tr(
            "wizard.connection.test_discovery_server_ok"
        ).format(fingerprint="AA:BB")
        assert not page.discovery_server_trust_box.isHidden()
        assert page.server_status.isHidden()

    def test_discovery_server_error_uses_discovery_server_message(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.REMOTE_SYNC)
        page._active_target = "discovery_server"
        page._on_probe_done(ProbeOutcome(False, reason="unreachable"))
        assert page.discovery_server_status.text() == tr(
            "wizard.connection.discovery_server_unreachable"
        )

    def test_result_ignored_when_section_hidden(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.LAN_SYNC)  # server section hidden
        page._active_target = "server"
        page._on_probe_done(ProbeOutcome(True, 200))
        assert page.server_status.isHidden()

    def test_editing_server_clears_status_and_fingerprint(self, wizard):
        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        page.server_status.setVisible(True)
        page.server_status.setText("ok")
        page._server_fingerprint = "AA:BB"
        page.server_url.setText("host.example.com")
        assert page.server_status.isHidden()
        assert page._server_fingerprint == ""

    def test_editing_discovery_server_clears_status_fingerprint_and_trust(self, wizard):
        page = wizard.connection_page
        page.set_mode(WizardMode.REMOTE_SYNC)
        page.discovery_server_status.setVisible(True)
        page.discovery_server_status.setText("ok")
        page.discovery_server_trust_box.setVisible(True)
        page.trust_save.setChecked(True)
        page._discovery_server_fingerprint = "AA:BB"
        page.discovery_server.setText("boot.example.net")
        assert page.discovery_server_status.isHidden()
        assert page._discovery_server_fingerprint == ""
        assert page.discovery_server_trust_box.isHidden()
        assert not page.trust_save.isChecked()


class TestReviewChecks:
    def _checks(self, wizard) -> str:
        return wizard.review_page._sections["checks"][1].text()

    def test_unverified_by_default(self, wizard):
        wizard.review_page.load(WizardDraft(mode=WizardMode.BACKUP))
        assert self._checks(wizard) == tr("wizard.review.not_verified")

    def test_server_verified_shows_time(self, wizard):
        wizard.review_page.load(
            WizardDraft(
                mode=WizardMode.BACKUP,
                server_verified=True,
                server_verified_at="2026-01-02T10:00:00+00:00",
            )
        )
        text = self._checks(wizard)
        assert text and text != tr("wizard.review.not_verified")

    def test_remote_verified_shows_fingerprint(self, wizard):
        wizard.review_page.load(
            WizardDraft(
                mode=WizardMode.REMOTE_SYNC,
                discovery_server_verified=True,
                discovery_server_fingerprint="AA:BB",
            )
        )
        assert "AA:BB" in self._checks(wizard)

    def test_lan_reports_no_prestart_test(self, wizard):
        wizard.review_page.load(WizardDraft(mode=WizardMode.LAN_SYNC))
        assert self._checks(wizard) == tr("wizard.connection.lan_no_test")

    def test_probe_success_sets_verification_and_edit_clears_it(self, wizard):
        from hsync_desktop.wizard.probes import ProbeOutcome

        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        page._active_target = "server"
        page._on_probe_done(ProbeOutcome(True, 200))
        draft = WizardDraft(mode=WizardMode.BACKUP)
        page.store(draft)
        assert draft.server_verified is True and draft.server_verified_at
        page.server_url.setText("edited.example.com")
        page.store(draft)
        assert draft.server_verified is False and draft.server_verified_at == ""


class TestLayoutImprovements:
    def test_mode_card_exposes_selected_property(self, wizard):
        backup = wizard.mode_page._cards[WizardMode.BACKUP]
        lan = wizard.mode_page._cards[WizardMode.LAN_SYNC]
        backup.set_selected(True)
        assert backup.property("selected") is True
        lan.set_selected(True)
        assert backup.property("selected") is False
        assert lan.property("selected") is True

    def test_connection_uses_a_subpage_per_topology(self, wizard):
        page = wizard.connection_page
        page.set_mode(WizardMode.BACKUP)
        assert page._stack.currentWidget() is page._server_page
        page.set_mode(WizardMode.REMOTE_SYNC)
        assert page._stack.currentWidget() is page._network_page

    def test_invite_is_selectable(self, wizard):
        wizard.success_page.load(
            WizardDraft(
                mode=WizardMode.LAN_SYNC,
                bucket="share-a",
                p2p_group="grp",
                p2p_key="pw",
            )
        )
        text = wizard.success_page._invite_text.toPlainText()
        assert wizard.success_page._invite_text.isReadOnly()
        assert "share-a" in text
        assert "grp" in text

    def test_invite_uses_the_connection_labels(self, wizard):
        """The invite names each value exactly as the Connection step does."""
        wizard.success_page.load(
            WizardDraft(
                mode=WizardMode.LAN_SYNC,
                bucket="share-a",
                p2p_group="grp",
                p2p_key="pw",
            )
        )
        text = wizard.success_page._invite_text.toPlainText()
        for key in (
            "wizard.connection.share",
            "wizard.connection.group",
            "wizard.connection.password",
        ):
            assert tr(key) in text, key

    def test_invite_height_fits_all_lines(self, wizard):
        """Three lines (share, group, password) must fit without clipping."""
        invite = wizard.success_page._invite_text
        assert invite.height() >= invite.fontMetrics().lineSpacing() * 3

    def test_stepper_exposes_progress(self, wizard):
        wizard._set_step(1)
        assert "2" in wizard._stepper.accessibleName()

    def test_page_title_follows_the_step(self, wizard):
        wizard._set_step(2)
        assert wizard._page_title.text() == tr("wizard.step.connection")

    def test_stepper_labels_keep_equal_weight(self, wizard):
        wizard._set_step(2)
        assert all(not label.font().bold() for label in wizard._stepper._labels)

    def test_footer_arrows(self, wizard):
        assert not wizard._back.icon().isNull()
        wizard._set_step(1)
        assert not wizard._primary._icon_label.isHidden()  # Continue: trailing arrow
        wizard._set_step(3)  # review
        assert wizard._primary._icon_label.isHidden()  # Finish: no arrow

    def test_connection_fields_have_tooltips(self, wizard):
        page = wizard.connection_page
        assert page.server_url.toolTip() == tr("wizard.tip.server_url")
        assert page.api_key.edit.toolTip() == tr("wizard.tip.api_key")
        assert page.bucket.toolTip() == tr("wizard.tip.share_name")
        assert page.discovery_server.toolTip() == tr("wizard.tip.discovery_server")
        assert page.continuous.toolTip() == tr("wizard.tip.continuous")

    def test_folder_suggestions_have_icons(self, wizard):
        assert wizard.folder_page._suggestion_buttons
        for button in wizard.folder_page._suggestion_buttons:
            assert not button.icon().isNull(), button.property("wizardKey")

    def test_connection_placeholders(self, wizard):
        page = wizard.connection_page
        assert page.server_url.placeholderText() == "https://hsync.example.com:9753"
        assert page.discovery_server.placeholderText() == "boot.example.net"
        assert page.bucket.placeholderText() == "my-share"
        assert page.group.placeholderText() == "my-devices"

    def test_success_hides_the_progress_header(self, wizard):
        wizard._resume.setText("resume")
        wizard._set_step(1)
        assert not wizard._subtitle.isHidden()
        assert not wizard._stepper.isHidden()
        assert not wizard._resume.isHidden()
        wizard._set_step(4)  # success screen
        assert wizard._subtitle.isHidden()
        assert wizard._stepper.isHidden()
        assert wizard._resume.isHidden()

    def test_form_labels_have_no_trailing_colon(self, wizard):
        for _container, _field, _error, label in wizard.connection_page._rows.values():
            text = label.text()
            assert not text.endswith((":", "：")), text

    def test_share_field_shares_the_label_column(self, wizard):
        rows = wizard.connection_page._rows
        widths = {
            name: rows[name][3].minimumWidth()
            for name in ("bucket", "server_url", "p2p_group", "p2p_key")
        }
        assert len(set(widths.values())) == 1
        assert next(iter(widths.values())) > 0

    def test_review_uses_the_same_colon_free_labels(self, wizard):
        wizard.review_page.load(
            WizardDraft(mode=WizardMode.BACKUP, bucket="data", server_url="h", api_key="k")
        )
        connection = wizard.review_page._sections["connection"][1].text()
        assert connection.startswith(f"{tr('wizard.connection.share')}: ")
        assert ":" not in tr("wizard.connection.share")


class TestModeDocumentationLink:
    """The mode step links to the desktop connection-modes guide."""

    def test_the_mode_page_links_to_the_modes_guide(self, wizard):
        from hsync_desktop import docs_links

        label = wizard.mode_page._modes_link
        assert label.objectName() == "helpLink"
        assert label.property("docsUrl") == docs_links.CONNECTION_MODES
        assert docs_links.CONNECTION_MODES in label.text()
        assert tr("help.connection_modes") in label.text()

    def test_the_help_choice_dialog_links_to_the_modes_guide(self, qtbot):
        from hsync_desktop import docs_links
        from hsync_desktop.wizard.pages.mode import HelpChoiceDialog

        dlg = HelpChoiceDialog()
        qtbot.addWidget(dlg)
        label = dlg.findChild(QLabel, "helpLink")
        assert label is not None
        assert label.property("docsUrl") == docs_links.CONNECTION_MODES


class TestModePageFitsWithoutClipping:
    """The mode cards keep their wrapped caption readable on a short window."""

    def test_the_pages_are_hosted_in_a_scroll_area(self, wizard):
        from PySide6.QtWidgets import QScrollArea

        assert isinstance(wizard._stack_scroll, QScrollArea)
        assert wizard._stack_scroll.widget() is wizard._stack

    def test_no_card_description_is_clipped_at_the_minimum_size(self, wizard, qtbot):
        wizard.resize(wizard.minimumWidth(), wizard.minimumHeight())
        wizard.show()
        qtbot.wait(20)

        for mode, card in wizard.mode_page._cards.items():
            description = card._description
            needed = description.heightForWidth(description.width())
            assert description.height() >= needed, (mode, description.height(), needed)

    def test_a_short_window_scrolls_instead_of_squeezing(self, wizard, qtbot):
        wizard.resize(wizard.minimumWidth(), wizard.minimumHeight())
        wizard.show()
        qtbot.wait(20)

        page = wizard.mode_page
        assert page.height() >= page.minimumSizeHint().height()
        assert wizard._stack_scroll.verticalScrollBar().maximum() > 0

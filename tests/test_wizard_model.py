# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Wizard model tests: profiles, inference, first-run gate, draft round-trip."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from hsync_desktop.wizard import model
from hsync_desktop.wizard.model import (
    DRAFT_VERSION,
    ChoiceAnswers,
    ChoiceAudience,
    WizardDraft,
    WizardMode,
    infer_mode_from_settings,
    load_draft,
    mark_auto_shown,
    mark_completed,
    profile_for,
    resolve_mode,
    save_draft,
    should_auto_open,
)


@pytest.fixture
def store(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


class TestProfiles:
    def test_backup_defaults(self):
        p = profile_for(WizardMode.BACKUP)
        assert p.p2p_enabled is False
        assert p.direction == "upload-only"
        assert p.deletion_policy == "keep"
        assert p.start_at_login is True
        assert p.requires_rendezvous_server is False

    def test_lan_defaults(self):
        p = profile_for(WizardMode.LAN_SYNC)
        assert p.p2p_enabled is True
        assert p.requires_rendezvous_server is False
        assert p.server_trust is None

    def test_remote_requires_rendezvous_server(self):
        assert profile_for(WizardMode.REMOTE_SYNC).requires_rendezvous_server is True

    def test_team_is_server_mode(self):
        assert profile_for(WizardMode.TEAM_SHARE).p2p_enabled is False


class TestResolveMode:
    """The pure help-chooser mapping: answers to a mode, ``None`` while incomplete."""

    def test_incomplete_answers_resolve_to_none(self):
        assert resolve_mode(ChoiceAnswers()) is None
        assert resolve_mode(ChoiceAnswers(audience=ChoiceAudience.PERSONAL)) is None
        unresolved_edits = ChoiceAnswers(audience=ChoiceAudience.PERSONAL, copy_only=False)
        assert resolve_mode(unresolved_edits) is None

    def test_team_share_resolves_on_the_first_answer(self):
        # A team answer wins even if a stale direction remains selected.
        answers = ChoiceAnswers(audience=ChoiceAudience.TEAM, copy_only=False)
        assert resolve_mode(answers) == WizardMode.TEAM_SHARE

    def test_copy_is_backup_regardless_of_the_network_answer(self):
        for same_network in (None, True, False):
            answers = ChoiceAnswers(
                audience=ChoiceAudience.PERSONAL,
                copy_only=True,
                same_network=same_network,
            )
            assert resolve_mode(answers) == WizardMode.BACKUP

    def test_edits_split_on_the_network_answer(self):
        same = ChoiceAnswers(audience=ChoiceAudience.PERSONAL, copy_only=False, same_network=True)
        different = ChoiceAnswers(
            audience=ChoiceAudience.PERSONAL, copy_only=False, same_network=False
        )
        assert resolve_mode(same) == WizardMode.LAN_SYNC
        assert resolve_mode(different) == WizardMode.REMOTE_SYNC


class TestInference:
    def test_none_without_path(self, store):
        assert infer_mode_from_settings(store) is None

    def test_lan_when_p2p_without_rendezvous_server(self, store):
        store.setValue("path/local", "/data")
        store.setValue("p2p/enabled", True)
        store.setValue("p2p/rendezvous_server_endpoints", "")
        assert infer_mode_from_settings(store) == WizardMode.LAN_SYNC

    def test_remote_when_rendezvous_server_set(self, store):
        store.setValue("path/local", "/data")
        store.setValue("p2p/enabled", True)
        store.setValue("p2p/rendezvous_server_endpoints", "rdv.example.net")
        assert infer_mode_from_settings(store) == WizardMode.REMOTE_SYNC

    def test_backup_on_upload_only(self, store):
        store.setValue("path/local", "/data")
        store.setValue("p2p/enabled", False)
        store.setValue("sync/direction", "upload-only")
        assert infer_mode_from_settings(store) == WizardMode.BACKUP

    def test_team_otherwise(self, store):
        store.setValue("path/local", "/data")
        store.setValue("p2p/enabled", False)
        store.setValue("sync/direction", "bidirectional")
        assert infer_mode_from_settings(store) == WizardMode.TEAM_SHARE


class TestAutoOpen:
    def test_opens_on_fresh_install(self, store):
        assert should_auto_open(store) is True

    def test_not_after_shown(self, store):
        mark_auto_shown(store)
        assert should_auto_open(store) is False

    def test_not_when_configured(self, store):
        store.setValue("path/local", "/data")
        assert should_auto_open(store) is False


class TestDraft:
    def test_round_trip_encrypts_secrets(self, store):
        draft = WizardDraft(
            mode=WizardMode.BACKUP,
            local_path="/data",
            bucket="data",
            server_url="https://host:9753",
            api_key="secret-api",
            p2p_key="secret-p2p",
            start_at_login=True,
        )
        save_draft(store, draft, step=2)
        assert store.value("wizard/draft/api_key") != "secret-api"
        assert store.value("wizard/draft/api_key").startswith("enc::")
        loaded, step = load_draft(store)
        assert step == 2
        assert loaded.mode == WizardMode.BACKUP
        assert loaded.api_key == "secret-api"
        assert loaded.p2p_key == "secret-p2p"
        assert loaded.start_at_login is True

    def test_absent_draft(self, store):
        assert load_draft(store) is None

    def test_stale_version_is_discarded(self, store):
        save_draft(store, WizardDraft(mode=WizardMode.LAN_SYNC), step=0)
        store.setValue("wizard/version", DRAFT_VERSION + 1)
        assert load_draft(store) is None
        assert store.value("wizard/in_progress", False, bool) is False

    def test_completed_clears_draft(self, store):
        save_draft(store, WizardDraft(mode=WizardMode.LAN_SYNC), step=1)
        mark_completed(store)
        assert store.value("wizard/completed", False, bool) is True
        assert store.value("wizard/in_progress", False, bool) is False
        assert load_draft(store) is None

    def test_model_helper_defaults_to_global_settings(self, monkeypatch, store):
        monkeypatch.setattr(model, "QSettings", lambda *a, **k: store)
        assert model.infer_mode_from_settings() is None

    def test_round_trip_verification_fields(self, store):
        draft = WizardDraft(
            mode=WizardMode.BACKUP,
            server_verified=True,
            server_verified_at="2026-01-02T10:00:00+00:00",
            rendezvous_server_verified=True,
            rendezvous_server_verified_at="2026-01-02T11:00:00+00:00",
        )
        save_draft(store, draft, step=3)
        loaded, _step = load_draft(store)
        assert loaded.server_verified is True
        assert loaded.server_verified_at == "2026-01-02T10:00:00+00:00"
        assert loaded.rendezvous_server_verified is True
        assert loaded.rendezvous_server_verified_at == "2026-01-02T11:00:00+00:00"

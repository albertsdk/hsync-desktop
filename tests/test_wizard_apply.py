# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Wizard apply tests: key mapping, secrets, discovery-server clearing, trust pinning."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

import hsync_desktop.wizard.apply as apply_mod
from hsync_desktop.wizard.apply import apply_draft
from hsync_desktop.wizard.model import WizardDraft, WizardMode


@pytest.fixture
def store(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture(autouse=True)
def fake_autostart(monkeypatch):
    calls: list[bool] = []

    class _Autostart:
        @staticmethod
        def is_supported() -> bool:
            return True

        @staticmethod
        def set_enabled(value: bool) -> None:
            calls.append(value)

    monkeypatch.setattr(apply_mod, "autostart", _Autostart)
    return calls


class TestServerModeMapping:
    def test_backup_mapping(self, store):
        store.setValue("advanced/autotune", False)
        draft = WizardDraft(
            mode=WizardMode.BACKUP,
            local_path="/data",
            bucket="data",
            server_url="host.example.com",
            api_key="api-secret",
            direction="upload-only",
            ignore_delete=True,
            start_at_login=True,
        )
        apply_draft(store, draft)
        assert store.value("p2p/enabled", True, bool) is False
        assert store.value("connection/server_url") == "https://host.example.com:9753"
        assert store.value("connection/api_key").startswith("enc::")
        assert store.value("sync/direction") == "upload-only"
        assert store.value("sync/ignore_delete", False, bool) is True
        assert store.value("appearance/start_at_login", False, bool) is True
        # advanced keys are untouched
        assert store.value("advanced/autotune", True, bool) is False

    def test_stale_discovery_server_cleared_in_server_mode(self, store):
        store.setValue("p2p/bootnode", "old.boot.example.net")
        apply_draft(store, WizardDraft(mode=WizardMode.BACKUP, bucket="b"))
        assert store.value("p2p/bootnode", "x", str) == ""

    def test_team_keeps_bidirectional_by_default(self, store):
        draft = WizardDraft(
            mode=WizardMode.TEAM_SHARE,
            bucket="shared",
            server_url="host:9753",
            api_key="k",
            direction="bidirectional",
        )
        apply_draft(store, draft)
        assert store.value("sync/direction") == "bidirectional"


class TestP2pModeMapping:
    def test_lan_clears_discovery_server_and_disables_server_fields(self, store):
        store.setValue("p2p/bootnode", "old.boot.example.net")
        draft = WizardDraft(
            mode=WizardMode.LAN_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="pw",
        )
        apply_draft(store, draft)
        assert store.value("p2p/enabled", False, bool) is True
        assert store.value("p2p/group") == "grp"
        assert store.value("p2p/key").startswith("enc::")
        assert store.value("p2p/bootnode", "x", str) == ""
        assert store.value("p2p/bootnode_trust") == "ask"

    def test_remote_sets_normalized_discovery_server(self, store):
        draft = WizardDraft(
            mode=WizardMode.REMOTE_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="pw",
            discovery_server="[::1]:8443",
        )
        apply_draft(store, draft)
        assert store.value("p2p/bootnode") == "[::1]:8443"


class TestTrustPinning:
    def _draft(self):
        return WizardDraft(
            mode=WizardMode.REMOTE_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="pw",
            discovery_server="boot.example.net",
            discovery_server_fingerprint="AA:BB",
            discovery_server_pin=True,
        )

    def test_pin_success(self, store, monkeypatch):
        monkeypatch.setattr(apply_mod, "find_hsync_binary", lambda: "/bin/hsync")
        monkeypatch.setattr(apply_mod, "add_bootnode_trust", lambda *a, **k: True)
        assert apply_draft(store, self._draft()).pin_error == ""

    def test_pin_without_binary(self, store, monkeypatch):
        monkeypatch.setattr(apply_mod, "find_hsync_binary", lambda: None)
        assert apply_draft(store, self._draft()).pin_error == "no_binary"

    def test_pin_failure(self, store, monkeypatch):
        monkeypatch.setattr(apply_mod, "find_hsync_binary", lambda: "/bin/hsync")
        monkeypatch.setattr(apply_mod, "add_bootnode_trust", lambda *a, **k: False)
        assert apply_draft(store, self._draft()).pin_error == "failed"

    def test_pin_fetched_when_missing(self, store, monkeypatch):
        monkeypatch.setattr(apply_mod, "find_hsync_binary", lambda: "/bin/hsync")
        monkeypatch.setattr(apply_mod, "fetch_bootnode_fingerprint", lambda *a, **k: "CC:DD")
        captured: dict = {}

        def fake_add(_binary, host, fingerprint, port=None):
            captured.update(host=host, fingerprint=fingerprint, port=port)
            return True

        monkeypatch.setattr(apply_mod, "add_bootnode_trust", fake_add)
        draft = self._draft()
        draft.discovery_server_fingerprint = ""
        assert apply_draft(store, draft).pin_error == ""
        assert captured == {"host": "boot.example.net", "fingerprint": "CC:DD", "port": 443}

    def test_skip_pinning(self, store, monkeypatch):
        monkeypatch.setattr(apply_mod, "find_hsync_binary", lambda: None)
        assert apply_draft(store, self._draft(), pin=False).pin_error == ""

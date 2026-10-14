# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the TrustedKeysDialog (known-hosts / known-peers management)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.trusted_keys import TrustedKeysDialog, _PeerAddDialog


def _patch_store(monkeypatch, *, bootnodes=(), servers=(), peers=(), supports_peer=True):
    """Point the dialog's module-level helpers at in-memory fakes."""
    import hsync_desktop.trusted_keys as mod

    monkeypatch.setattr(mod, "find_hsync_binary", lambda: "/fake/hsync")
    monkeypatch.setattr(mod, "list_bootnode_trust", lambda binary: list(bootnodes))
    monkeypatch.setattr(mod, "list_server_trust", lambda binary: list(servers))
    monkeypatch.setattr(mod, "list_peer_pins", lambda binary: list(peers))
    monkeypatch.setattr(mod, "supports_peer_trust", lambda binary: supports_peer)


class TestTrustedKeysDialog:
    def test_bootnode_list_is_populated(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            bootnodes=[
                {
                    "host": "boot.example.net",
                    "port": 443,
                    "fingerprint": "a" * 64,
                    "source": "cli",
                    "first_seen": "2026",
                }
            ],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._bootnode_table.rowCount() == 1
        assert dlg._bootnode_table.item(0, 0).text() == "boot.example.net:443"
        assert dlg._bootnode_table.item(0, 1).text() == "a" * 64

    def test_peer_list_is_populated(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            peers=[{"cid": "master-1", "bucket": "photos", "fingerprint": "b" * 64}],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._peer_table.rowCount() == 1
        assert dlg._peer_table.item(0, 0).text() == "master-1|photos"

    def test_peer_tab_shows_capability_missing(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, supports_peer=False)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._peer_table.item(0, 0).text() == tr("trusted_keys.capability_missing")

    def test_remove_bootnode_flow(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            bootnodes=[
                {
                    "host": "boot.example.net",
                    "port": 443,
                    "fingerprint": "a" * 64,
                    "source": "cli",
                    "first_seen": "2026",
                }
            ],
        )
        removed: list[tuple[str, int | None]] = []
        monkeypatch.setattr(
            "hsync_desktop.trusted_keys.remove_bootnode_trust",
            lambda binary, host, port: removed.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        dlg._bootnode_table.selectRow(0)
        dlg._remove_bootnode()
        assert removed == [("boot.example.net", 443)]

    def test_peer_add_rejects_an_invalid_fingerprint(self, qtbot, monkeypatch):
        _patch_store(monkeypatch)
        added: list[tuple] = []
        monkeypatch.setattr(
            "hsync_desktop.trusted_keys.add_peer_pin",
            lambda binary, cid, bucket, fp: added.append((cid, bucket, fp)) or True,
        )
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
        dlg = _PeerAddDialog()
        qtbot.addWidget(dlg)
        dlg.cid_edit.setText("master-1")
        dlg.bucket_edit.setText("photos")
        dlg.fingerprint_edit.setText("not-a-fingerprint")
        dlg._on_accept()
        assert added == []


class TestServerTrustTab:
    """The Servers tab mirrors the bootnode tab for the sync-server store."""

    def test_server_list_is_populated(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            servers=[
                {
                    "host": "server.example.com",
                    "port": 9753,
                    "fingerprint": "c" * 64,
                    "source": "cli",
                    "first_seen": "2026",
                }
            ],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._server_table.rowCount() == 1
        assert dlg._server_table.item(0, 0).text() == "server.example.com:9753"

    def test_remove_server_flow(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            servers=[
                {
                    "host": "server.example.com",
                    "port": 9753,
                    "fingerprint": "c" * 64,
                    "source": "cli",
                    "first_seen": "2026",
                }
            ],
        )
        removed: list[tuple] = []
        monkeypatch.setattr(
            "hsync_desktop.trusted_keys.remove_server_trust",
            lambda binary, host, port: removed.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        dlg._server_table.selectRow(0)
        dlg._remove_server()
        assert removed == [("server.example.com", 9753)]


class TestTrustedKeysInitialTab:
    """``initial_tab`` opens the dialog on the panel that launched it."""

    def test_default_is_bootnodes(self, qtbot, monkeypatch):
        _patch_store(monkeypatch)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._tabs.currentIndex() == 0

    def test_servers_selects_the_server_tab(self, qtbot, monkeypatch):
        _patch_store(monkeypatch)
        dlg = TrustedKeysDialog(initial_tab="servers")
        qtbot.addWidget(dlg)
        assert dlg._tabs.currentIndex() == 1


class TestTrustedKeysCloseButton:
    """The Close button carries the app icon and a translated label."""

    def test_close_button_is_translated_and_themed(self, qtbot, monkeypatch):
        from PySide6.QtWidgets import QDialogButtonBox

        from hsync_desktop.icons import icon

        _patch_store(monkeypatch)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        box = dlg.findChild(QDialogButtonBox)
        assert box is not None
        close = box.button(QDialogButtonBox.StandardButton.Close)
        assert close is not None
        assert close.text() == tr("action.close")
        assert close.icon().cacheKey() == icon("window-close").cacheKey()


class TestAddDialogButtons:
    """The Add dialogs use the app Save/Cancel labels and icons."""

    @staticmethod
    def _assert_buttons(dialog):
        from PySide6.QtWidgets import QDialogButtonBox

        from hsync_desktop.icons import icon

        box = dialog.findChild(QDialogButtonBox)
        assert box is not None
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and cancel is not None
        assert ok.text() == tr("settings.save")
        assert ok.icon().cacheKey() == icon("document-save").cacheKey()
        assert cancel.text() == tr("settings.cancel")
        assert cancel.icon().cacheKey() == icon("dialog-cancel").cacheKey()

    def test_host_add_dialog_buttons(self, qtbot):
        from hsync_desktop.trusted_keys import _HostAddDialog

        dlg = _HostAddDialog(
            fetch_fingerprint=lambda *a, **k: None,
            add_trust=lambda *a, **k: False,
            placeholder="boot.example.net:443",
        )
        qtbot.addWidget(dlg)
        self._assert_buttons(dlg)

    def test_peer_add_dialog_buttons(self, qtbot):
        from hsync_desktop.trusted_keys import _PeerAddDialog

        dlg = _PeerAddDialog()
        qtbot.addWidget(dlg)
        self._assert_buttons(dlg)

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the TrustedKeysDialog (known-hosts / known-peers management)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.trusted_keys import TrustedKeysDialog, _format_local_time, _PeerAddDialog


def _patch_store(
    monkeypatch, *, rendezvouss=(), servers=(), peers=(), supports_peer=True, p2p_enabled=True
):
    """Point the dialog's module-level helpers at in-memory fakes."""
    import hsync_desktop.trusted_keys as mod

    class _FakeSettings:
        def value(self, key, default=None, _type=None):
            return p2p_enabled if key == "p2p/enabled" else default

    monkeypatch.setattr(mod, "QSettings", lambda *a, **k: _FakeSettings())
    monkeypatch.setattr(mod, "find_hsync_binary", lambda: "/fake/hsync")
    monkeypatch.setattr(mod, "list_rendezvous_trust", lambda binary: list(rendezvouss))
    monkeypatch.setattr(mod, "list_server_trust", lambda binary: list(servers))
    monkeypatch.setattr(mod, "list_peer_pins", lambda binary: list(peers))
    monkeypatch.setattr(mod, "supports_peer_trust", lambda binary: supports_peer)


class TestTrustedKeysDialog:
    def test_rendezvous_list_is_populated(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            rendezvouss=[
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
        assert dlg._rendezvous_table.rowCount() == 1
        assert dlg._rendezvous_table.item(0, 0).text() == "boot.example.net:443"
        assert dlg._rendezvous_table.item(0, 1).text() == "a" * 64

    def test_peer_list_is_populated(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            peers=[
                {
                    "cid": "master-1",
                    "bucket": "photos",
                    "fingerprint": "b" * 64,
                    "first_seen": "2026-10-16T13:57:49.852Z",
                }
            ],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._peer_table.rowCount() == 1
        assert dlg._peer_table.item(0, 0).text() == "master-1|photos"
        assert dlg._peer_table.item(0, 1).text() == "b" * 64
        assert dlg._peer_table.item(0, 2).text() == _format_local_time("2026-10-16T13:57:49.852Z")

    def test_peer_table_has_an_added_column(self, qtbot, monkeypatch):
        _patch_store(monkeypatch)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._peer_table.horizontalHeaderItem(2).text() == tr("trusted_keys.first_seen")

    def test_peer_tab_shows_capability_missing(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, supports_peer=False)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._peer_table.item(0, 0).text() == tr("trusted_keys.capability_missing")

    def test_remove_rendezvous_flow(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            rendezvouss=[
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
            "hsync_desktop.trusted_keys.remove_rendezvous_trust",
            lambda binary, host, port: removed.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        dlg._rendezvous_table.selectRow(0)
        dlg._remove_rendezvous()
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
    """The Servers tab mirrors the rendezvous tab for the sync-server store."""

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

    def test_default_is_rendezvouss(self, qtbot, monkeypatch):
        _patch_store(monkeypatch)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._tabs.currentIndex() == 0

    def test_servers_selects_the_server_tab(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, p2p_enabled=False)
        dlg = TrustedKeysDialog(initial_tab="servers")
        qtbot.addWidget(dlg)
        assert dlg._tabs.currentIndex() == 1

    def test_p2p_mode_hides_the_server_store(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, p2p_enabled=True)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert not dlg._tabs.isTabVisible(1)
        assert dlg._tabs.isTabVisible(0)
        assert dlg._tabs.isTabVisible(2)

    def test_server_mode_hides_the_p2p_stores(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, p2p_enabled=False)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._tabs.isTabVisible(1)
        assert not dlg._tabs.isTabVisible(0)
        assert not dlg._tabs.isTabVisible(2)

    def test_a_hidden_initial_tab_falls_back_to_a_visible_one(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, p2p_enabled=True)
        dlg = TrustedKeysDialog(initial_tab="servers")
        qtbot.addWidget(dlg)
        assert dlg._tabs.currentIndex() == 0

    def test_the_server_tab_is_labelled_hsync_server(self, qtbot, monkeypatch):
        _patch_store(monkeypatch, p2p_enabled=False)
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._tabs.tabText(1) == tr("trusted_keys.tabs_servers")
        assert dlg._tabs.tabText(1) == "Server HSYNC"


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


class TestHostAddReadFromNode:
    """'Read from server' probes off the UI thread and fills the fingerprint."""

    @staticmethod
    def _dialog(qtbot, fetch):
        from hsync_desktop.trusted_keys import _HostAddDialog

        dlg = _HostAddDialog(
            fetch_fingerprint=fetch,
            add_trust=lambda *a, **k: True,
            placeholder="boot.example.net:443",
        )
        dlg._binary = "/fake/hsync"
        qtbot.addWidget(dlg)
        return dlg

    def test_fills_the_field_with_the_fingerprint(self, qtbot):
        fingerprint = "sha256:" + "b" * 64
        dlg = self._dialog(qtbot, lambda *a, **k: fingerprint)
        dlg.host_edit.setText("boot.example.net:443")
        dlg._read_from_node()
        # Off the UI thread: the button reports the wait instead of freezing.
        assert not dlg.fetch_btn.isEnabled()
        assert dlg.fetch_btn.text() == tr("common.checking")
        qtbot.waitUntil(lambda: dlg.fingerprint_edit.text() != "", timeout=5000)
        assert dlg.fingerprint_edit.text() == fingerprint
        assert dlg.fetch_btn.isEnabled()
        assert dlg.fetch_btn.text() == tr("trusted_keys.read_from_node")

    def test_unreachable_host_warns(self, qtbot, monkeypatch):
        warned: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2]))
        )
        dlg = self._dialog(qtbot, lambda *a, **k: None)
        dlg.host_edit.setText("boot.example.net:443")
        dlg._read_from_node()
        qtbot.waitUntil(lambda: bool(warned), timeout=5000)
        assert warned == [tr("trusted_keys.failed")]
        assert dlg.fetch_btn.isEnabled()

    def test_empty_host_warns_without_probing(self, qtbot, monkeypatch):
        probed: list[tuple] = []
        warned: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2]))
        )
        dlg = self._dialog(qtbot, lambda *a, **k: probed.append(a))
        dlg.host_edit.setText("")
        dlg._read_from_node()
        assert warned == [tr("trusted_keys.failed")]
        assert probed == []


class TestSourceLabel:
    """The known-hosts ``source`` column is humanized for users."""

    def test_known_sources_are_humanized(self):
        from hsync_desktop.trusted_keys import _source_label

        assert _source_label("cli") == tr("trusted_keys.source_cli")
        assert _source_label("tofu") == tr("trusted_keys.source_tofu")
        assert _source_label("prompt") == tr("trusted_keys.source_prompt")
        assert _source_label("flag") == tr("trusted_keys.source_flag")

    def test_unknown_source_passes_through(self):
        from hsync_desktop.trusted_keys import _source_label

        assert _source_label("future-mode") == "future-mode"
        assert _source_label("") == ""

    def test_rendezvous_server_source_column_is_humanized(self, qtbot, monkeypatch):
        _patch_store(
            monkeypatch,
            rendezvouss=[
                {
                    "host": "boot.example.net",
                    "port": 443,
                    "fingerprint": "a" * 64,
                    "source": "tofu",
                    "first_seen": "2026",
                }
            ],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._rendezvous_table.item(0, 2).text() == tr("trusted_keys.source_tofu")


class TestLocalTimeFormatting:
    """Stored UTC timestamps are shown in the user's local time."""

    def test_utc_is_converted_to_local(self):
        from datetime import datetime

        from hsync_desktop.file_panel.utils import format_mtime

        iso = "2020-01-02T03:04:05.000Z"
        expected = format_mtime(
            datetime.fromisoformat("2020-01-02T03:04:05+00:00").astimezone().timestamp()
        )
        assert _format_local_time(iso) == expected

    def test_output_drops_the_raw_utc_markers(self):
        shown = _format_local_time("2020-01-02T03:04:05.000Z")
        assert "T" not in shown
        assert "Z" not in shown

    def test_empty_and_invalid_pass_through(self):
        assert _format_local_time("") == ""
        assert _format_local_time("not-a-date") == "not-a-date"

    def test_rendezvous_server_added_column_is_localized(self, qtbot, monkeypatch):
        iso = "2020-01-02T03:04:05.000Z"
        _patch_store(
            monkeypatch,
            rendezvouss=[
                {
                    "host": "boot.example.net",
                    "port": 443,
                    "fingerprint": "a" * 64,
                    "source": "cli",
                    "first_seen": iso,
                }
            ],
        )
        dlg = TrustedKeysDialog()
        qtbot.addWidget(dlg)
        assert dlg._rendezvous_table.item(0, 3).text() == _format_local_time(iso)


class TestDevicesTerminology:
    """The peers tab reads 'Devices' and the fingerprint term is localized."""

    def test_english_uses_devices(self):
        from hsync_desktop.locales import en

        assert en.translations["trusted_keys.tabs_peers"] == "Devices"
        assert en.translations["trusted_keys.peer"] == "Device"

    def test_first_seen_column_is_user_friendly(self):
        from hsync_desktop.locales import en, it

        assert en.translations["trusted_keys.first_seen"] == "Added on"
        assert it.translations["trusted_keys.first_seen"] == "Aggiunto il"

    def test_fingerprint_is_localized(self):
        from hsync_desktop.locales import de, es, fr, it, ja, nl, pl, pt, ru, zh

        assert it.translations["trusted_keys.fingerprint"] == "Impronta"
        assert de.translations["trusted_keys.fingerprint"] == "Fingerabdruck"
        assert es.translations["trusted_keys.fingerprint"] == "Huella"
        assert fr.translations["trusted_keys.fingerprint"] == "Empreinte"
        assert pt.translations["trusted_keys.fingerprint"] == "Fingerprint"
        assert zh.translations["trusted_keys.fingerprint"] == "指纹"
        assert ru.translations["trusted_keys.fingerprint"] == "Отпечаток"
        assert nl.translations["trusted_keys.fingerprint"] == "Vingerafdruk"
        assert pl.translations["trusted_keys.fingerprint"] == "Odcisk"
        assert ja.translations["trusted_keys.fingerprint"] == "フィンガープリント"

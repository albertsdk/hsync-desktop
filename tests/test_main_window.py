# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for the MainWindow bootnode-trust pre-flight and trust dialogs."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from hsync_desktop.engine import HsyncEngine
from hsync_desktop.i18n import tr
from hsync_desktop.main_window import MainWindow


def _settings(tmp_path) -> QSettings:
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    s.setValue("p2p/enabled", True)
    s.setValue("p2p/bootnode", "boot.example.net")
    s.setValue("p2p/bootnode_trust", "ask")
    return s


def _resolve_dialog(monkeypatch, label: str | None) -> list[int]:
    """Make QMessageBox.exec a no-op recording the call and clickedButton pick *label*.

    *label* None simulates a dialog dismissed without pressing a button (window
    close), for which ``clickedButton()`` is None. Returns the exec-call counter.
    """
    calls: list[int] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: calls.append(1) or 0)

    def fake_clicked(self):
        if label is None:
            return None
        for button in self.buttons():
            if button.text() == label:
                return button
        return None

    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked)
    return calls


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    import hsync_desktop.main_window as mw

    s = _settings(tmp_path)
    monkeypatch.setattr(mw, "QSettings", lambda *a, **k: s)
    monkeypatch.setattr(mw, "find_hsync_binary", lambda: "/fake/hsync")
    engine = HsyncEngine(binary_path="/fake/hsync")
    win = MainWindow(engine)
    qtbot.addWidget(win)
    return win


class TestEnsureBootnodeTrust:
    def test_skips_when_the_host_is_already_trusted(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        monkeypatch.setattr(
            mw,
            "list_bootnode_trust",
            lambda binary: [{"host": "boot.example.net", "port": 443, "fingerprint": "f" * 64}],
        )
        fetched: list[tuple] = []
        monkeypatch.setattr(
            mw, "fetch_bootnode_fingerprint", lambda *a, **k: fetched.append(a) or "f" * 64
        )
        assert window._ensure_bootnode_trust() is True
        assert fetched == []

    def test_prompts_and_pins_when_unknown(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        monkeypatch.setattr(mw, "list_bootnode_trust", lambda binary: [])
        fetched: list[tuple] = []
        monkeypatch.setattr(
            mw, "fetch_bootnode_fingerprint", lambda *a, **k: fetched.append(a) or "a" * 64
        )
        added: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "add_bootnode_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        assert window._ensure_bootnode_trust() is True
        # The client dials 443 (bare HSYNC_BOOTNODE): the LAN listen port must
        # never be passed to the bootnode trust commands.
        assert fetched[0][1:] == ("boot.example.net", 443)
        assert added == [("boot.example.net", 443)]

    def test_aborts_when_the_user_declines(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        monkeypatch.setattr(mw, "list_bootnode_trust", lambda binary: [])
        monkeypatch.setattr(mw, "fetch_bootnode_fingerprint", lambda *a, **k: "a" * 64)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
        assert window._ensure_bootnode_trust() is False


class TestTrustDialogs:
    def test_bootnode_changed_trust_calls_add(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        added: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "add_bootnode_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        window._on_fingerprint_changed("bootnode", "", "boot.example.net:443", "a" * 64)
        assert added == [("boot.example.net", 443)]

    def test_bootnode_changed_forget_removes(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        _resolve_dialog(monkeypatch, tr("dialogs.trust_forget"))
        removed: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "remove_bootnode_trust",
            lambda binary, host, port=None: removed.append((host, port)) or True,
        )
        window._on_fingerprint_changed("bootnode", "", "boot.example.net:443", "a" * 64)
        assert removed == [("boot.example.net", 443)]

    def test_bootnode_changed_dismiss_leaves_the_pin(self, window, monkeypatch):
        # Regression: dismissing the dialog (window close → no clicked button)
        # must never run the destructive "forget" on the stored pin.
        import hsync_desktop.main_window as mw

        _resolve_dialog(monkeypatch, None)
        touched: list[str] = []
        monkeypatch.setattr(mw, "add_bootnode_trust", lambda *a, **k: touched.append("add") or True)
        monkeypatch.setattr(
            mw, "remove_bootnode_trust", lambda *a, **k: touched.append("remove") or True
        )
        window._on_fingerprint_changed("bootnode", "", "boot.example.net:443", "a" * 64)
        assert touched == []

    def test_master_pairing_trust_pins_the_peer(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        monkeypatch.setattr(mw, "supports_peer_trust", lambda *a, **k: True)
        pinned: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "add_peer_pin",
            lambda binary, cid, bucket, fingerprint: pinned.append((cid, fingerprint)) or True,
        )
        window._on_pairing_needed("master", "master-1", "10.0.0.2", "b" * 64)
        assert pinned == [("master-1", "b" * 64)]

    def test_pairing_needed_is_deduped_and_reprompts_on_change(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        calls = _resolve_dialog(monkeypatch, tr("dialogs.trust_ignore"))
        monkeypatch.setattr(mw, "supports_peer_trust", lambda *a, **k: True)
        monkeypatch.setattr(mw, "add_peer_pin", lambda *a, **k: True)
        window._on_pairing_needed("master", "master-1", "10.0.0.2", "b" * 64)
        window._on_pairing_needed("master", "master-1", "10.0.0.2", "b" * 64)
        assert len(calls) == 1  # repeated identical refusal is suppressed
        window._on_pairing_needed("master", "master-1", "10.0.0.2", "c" * 64)
        assert len(calls) == 2  # a changed fingerprint re-prompts

    def test_stop_clears_the_dedupe(self, window):
        window._should_prompt_trust("master", "master-1", "10.0.0.2", "b" * 64)
        assert window._trust_prompted
        window._on_stop()
        assert window._trust_prompted == {}


class TestEnsureServerTrust:
    """Server-mode pre-flight (ADR-0036)."""

    def test_skips_in_p2p_mode(self, window):
        # The fixture enables p2p: server trust is not consulted.
        assert window._ensure_server_trust() is True

    def test_prompts_and_pins_when_unknown(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        s = mw.QSettings()
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "https://server.example.com:9753")
        s.setValue("connection/server_trust", "ask")
        monkeypatch.setattr(mw, "list_server_trust", lambda binary: [])
        fetched: list[tuple] = []
        monkeypatch.setattr(
            mw, "fetch_server_fingerprint", lambda *a, **k: fetched.append(a) or "d" * 64
        )
        added: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "add_server_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        assert window._ensure_server_trust() is True
        assert fetched[0][1:] == ("server.example.com", 9753)
        assert added == [("server.example.com", 9753)]

    def test_no_url_skips(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        s = mw.QSettings()
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "")
        s.setValue("connection/server_trust", "ask")
        monkeypatch.setattr(mw, "list_server_trust", lambda binary: pytest.fail("must not probe"))
        assert window._ensure_server_trust() is True

    def test_server_changed_trust_calls_add(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        added: list[tuple] = []
        monkeypatch.setattr(
            mw,
            "add_server_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        window._on_fingerprint_changed("server", "", "server.example.com:9753", "d" * 64)
        assert added == [("server.example.com", 9753)]

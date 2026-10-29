# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the MainWindow trust pre-flight and trust dialogs."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings import SettingsDialog
from tests._helpers import _patch_all, _resolve_dialog


class TestEnsureRendezvousTrust:
    @staticmethod
    def _run(window, started: list[int]) -> None:
        window._ensure_trust(lambda: started.append(1))

    def test_skips_when_the_host_is_already_trusted(self, window, monkeypatch):

        _patch_all(
            monkeypatch,
            "list_rendezvous_trust",
            lambda binary: [{"host": "rdv.example.net", "port": 443, "fingerprint": "f" * 64}],
        )
        fetched: list[tuple] = []
        _patch_all(
            monkeypatch,
            "fetch_rendezvous_fingerprint",
            lambda *a, **k: fetched.append(a) or "f" * 64,
        )
        started: list[int] = []
        self._run(window, started)
        # A pinned host needs no network probe: the run continues immediately.
        assert started == [1]
        assert fetched == []

    def test_prompts_and_pins_when_unknown(self, window, qtbot, monkeypatch):

        _patch_all(monkeypatch, "list_rendezvous_trust", lambda binary: [])
        fetched: list[tuple] = []
        _patch_all(
            monkeypatch,
            "fetch_rendezvous_fingerprint",
            lambda *a, **k: fetched.append(a) or "a" * 64,
        )
        added: list[tuple] = []
        _patch_all(
            monkeypatch,
            "add_rendezvous_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        started: list[int] = []
        self._run(window, started)
        qtbot.waitUntil(lambda: bool(started), timeout=5000)
        # The client dials 443 (bare HSYNC_RENDEZVOUS_SERVER_ENDPOINTS): the p2p listen port must
        # never be passed to the rendezvous trust commands.
        assert fetched[0][1:] == ("rdv.example.net", 443)
        assert added == [("rdv.example.net", 443)]

    def test_aborts_when_the_user_declines(self, window, qtbot, monkeypatch):

        _patch_all(monkeypatch, "list_rendezvous_trust", lambda binary: [])
        _patch_all(monkeypatch, "fetch_rendezvous_fingerprint", lambda *a, **k: "a" * 64)
        asked: list = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: asked.append(a) or QMessageBox.StandardButton.No,
        )
        started: list[int] = []
        self._run(window, started)
        qtbot.waitUntil(lambda: bool(asked), timeout=5000)
        assert started == []

    def test_unreachable_host_continues_on_the_local_network(self, window, qtbot, monkeypatch):
        """An unreachable discovery servers degrades the run, never cancels it.

        Regression: the pre-flight abandoned every start when the configured
        rendezvous could not be probed, so a desktop client with a stale rendezvous
        server never synced even with peers on the local network.
        """

        _patch_all(monkeypatch, "list_rendezvous_trust", lambda binary: [])
        _patch_all(monkeypatch, "fetch_rendezvous_fingerprint", lambda *a, **k: None)
        warned: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2]))
        )
        logged: list[tuple] = []
        monkeypatch.setattr(
            window, "_append_desktop_log", lambda level, message: logged.append((level, message))
        )
        started: list[int] = []
        self._run(window, started)
        qtbot.waitUntil(lambda: bool(started), timeout=5000)
        assert started == [1], "the run must continue without the discovery server"
        assert warned == []
        assert logged and "rdv.example.net" in logged[0][1]

    def test_a_second_request_while_probing_is_ignored(self, window, qtbot, monkeypatch):

        _patch_all(monkeypatch, "list_rendezvous_trust", lambda binary: [])
        _patch_all(monkeypatch, "fetch_rendezvous_fingerprint", lambda *a, **k: "a" * 64)
        _patch_all(monkeypatch, "add_rendezvous_trust", lambda *a, **k: True)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        started: list[int] = []
        window._ensure_trust(lambda: started.append(1))
        second: list[int] = []
        self._run(window, second)
        assert second == []
        qtbot.waitUntil(lambda: bool(started), timeout=5000)


class TestTrustDialogs:
    def test_rendezvous_changed_trust_calls_add(self, window, monkeypatch):

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        added: list[tuple] = []
        _patch_all(
            monkeypatch,
            "add_rendezvous_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        window._on_fingerprint_changed("rendezvous", "", "rdv.example.net:443", "a" * 64)
        assert added == [("rdv.example.net", 443)]

    def test_rendezvous_changed_forget_removes(self, window, monkeypatch):

        _resolve_dialog(monkeypatch, tr("dialogs.trust_forget"))
        removed: list[tuple] = []
        _patch_all(
            monkeypatch,
            "remove_rendezvous_trust",
            lambda binary, host, port=None: removed.append((host, port)) or True,
        )
        window._on_fingerprint_changed("rendezvous", "", "rdv.example.net:443", "a" * 64)
        assert removed == [("rdv.example.net", 443)]

    def test_rendezvous_changed_dismiss_leaves_the_pin(self, window, monkeypatch):
        # Regression: dismissing the dialog (window close → no clicked button)
        # must never run the destructive "forget" on the stored pin.

        _resolve_dialog(monkeypatch, None)
        touched: list[str] = []
        _patch_all(
            monkeypatch, "add_rendezvous_trust", lambda *a, **k: touched.append("add") or True
        )
        _patch_all(
            monkeypatch, "remove_rendezvous_trust", lambda *a, **k: touched.append("remove") or True
        )
        window._on_fingerprint_changed("rendezvous", "", "rdv.example.net:443", "a" * 64)
        assert touched == []

    def test_master_pairing_trust_pins_the_peer(self, window, monkeypatch):

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        _patch_all(monkeypatch, "supports_peer_trust", lambda *a, **k: True)
        pinned: list[tuple] = []
        _patch_all(
            monkeypatch,
            "add_peer_pin",
            lambda binary, cid, bucket, fingerprint: pinned.append((cid, fingerprint)) or True,
        )
        window._on_pairing_needed("master", "master-1", "10.0.0.2", "b" * 64)
        assert pinned == [("master-1", "b" * 64)]

    def test_pairing_needed_is_deduped_and_reprompts_on_change(self, window, monkeypatch):

        calls = _resolve_dialog(monkeypatch, tr("dialogs.trust_ignore"))
        _patch_all(monkeypatch, "supports_peer_trust", lambda *a, **k: True)
        _patch_all(monkeypatch, "add_peer_pin", lambda *a, **k: True)
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

    def test_skips_in_p2p_mode(self, window, monkeypatch):
        # The fixture enables p2p: server trust is not consulted. The rendezvous is
        # already pinned, so the pre-flight has nothing to probe.
        _patch_all(
            monkeypatch,
            "list_rendezvous_trust",
            lambda binary: [{"host": "rdv.example.net", "port": 443, "fingerprint": "f" * 64}],
        )
        _patch_all(monkeypatch, "list_server_trust", lambda binary: pytest.fail("must not probe"))
        started: list[int] = []
        window._ensure_trust(lambda: started.append(1))
        assert started == [1]

    def test_prompts_and_pins_when_unknown(self, window, qtbot, settings, monkeypatch):

        s = settings
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "https://server.example.com:9753")
        s.setValue("connection/server_trust", "ask")
        _patch_all(monkeypatch, "list_server_trust", lambda binary: [])
        fetched: list[tuple] = []
        _patch_all(
            monkeypatch, "fetch_server_fingerprint", lambda *a, **k: fetched.append(a) or "d" * 64
        )
        added: list[tuple] = []
        _patch_all(
            monkeypatch,
            "add_server_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        started: list[int] = []
        window._ensure_trust(lambda: started.append(1))
        qtbot.waitUntil(lambda: bool(started), timeout=5000)
        assert fetched[0][1:] == ("server.example.com", 9753)
        assert added == [("server.example.com", 9753)]

    def test_no_url_skips(self, window, settings, monkeypatch):

        s = settings
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "")
        s.setValue("connection/server_trust", "ask")
        _patch_all(monkeypatch, "list_server_trust", lambda binary: pytest.fail("must not probe"))
        started: list[int] = []
        window._ensure_trust(lambda: started.append(1))
        assert started == [1]

    def test_unreachable_server_warns_and_aborts(self, window, qtbot, settings, monkeypatch):
        """The sync server is mandatory: a dead one still cancels the run.

        Only the optional discovery servers degrades; server mode has no
        alternative path, so a refused or unreachable server keeps the run from
        starting instead of syncing nothing.
        """
        s = settings
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "https://server.example.com:9753")
        s.setValue("connection/server_trust", "ask")
        _patch_all(monkeypatch, "list_server_trust", lambda binary: [])
        _patch_all(monkeypatch, "fetch_server_fingerprint", lambda *a, **k: None)
        warned: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2]))
        )
        started: list[int] = []
        window._ensure_trust(lambda: started.append(1))
        qtbot.waitUntil(lambda: bool(warned), timeout=5000)
        assert warned == [tr("dialogs.rendezvous_unreachable").format(host="server.example.com")]
        assert started == []

    def test_server_changed_trust_calls_add(self, window, monkeypatch):

        _resolve_dialog(monkeypatch, tr("dialogs.trust_accept"))
        added: list[tuple] = []
        _patch_all(
            monkeypatch,
            "add_server_trust",
            lambda binary, host, fingerprint, port=None: added.append((host, port)) or True,
        )
        window._on_fingerprint_changed("server", "", "server.example.com:9753", "d" * 64)
        assert added == [("server.example.com", 9753)]


class TestAuthErrorPrompt:
    """A missing/incorrect p2p password re-prompts for it (never a dead-end),
    and the prompt is guarded against re-entrant events."""

    @staticmethod
    def _fake_dialog(result: int, on_exec=None):
        class _Dialog:
            DialogCode = type("DialogCode", (), {"Accepted": 1})

            def __init__(self, parent=None):
                pass

            def exec(self):
                if on_exec:
                    on_exec()
                return result

        return _Dialog

    def test_accept_retries_with_the_new_password(self, window, monkeypatch):
        import hsync_desktop.main_window.trust as trust

        monkeypatch.setattr(trust, "P2PKeyDialog", self._fake_dialog(1))
        retried: list[int] = []
        monkeypatch.setattr(window, "_retry_after_auth_fix", lambda: retried.append(1))
        window._on_auth_error("Invalid API key")
        assert retried == [1]
        assert window._auth_prompt_active is False

    def test_cancel_resets_the_ui(self, window, monkeypatch):
        import hsync_desktop.main_window.trust as trust

        monkeypatch.setattr(trust, "P2PKeyDialog", self._fake_dialog(0))
        reset: list[int] = []
        monkeypatch.setattr(window, "_reset_ui_stopped", lambda: reset.append(1))
        window._on_auth_error("Invalid API key")
        assert reset == [1]
        assert window._auth_prompt_active is False

    def test_reentrant_events_are_ignored(self, window, monkeypatch):
        import hsync_desktop.main_window.trust as trust

        opened: list[int] = []

        def _nested():
            opened.append(1)
            window._on_auth_error("nested while the prompt is open")

        monkeypatch.setattr(trust, "P2PKeyDialog", self._fake_dialog(0, on_exec=_nested))
        monkeypatch.setattr(window, "_reset_ui_stopped", lambda: None)
        window._on_auth_error("first")
        assert opened == [1]  # the nested call was ignored while the prompt was open

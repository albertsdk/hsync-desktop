# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

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


class TestOpenSettings:
    def test_second_open_raises_existing_dialog(self, window, monkeypatch, qtbot):
        """A tray re-click raises the open dialog instead of stacking a new one."""
        import hsync_desktop.main_window as mw

        created: list[object] = []
        real_dialog = mw.SettingsDialog

        class _SpyDialog(real_dialog):  # type: ignore[misc]
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                created.append(self)

        raised: list[str] = []
        monkeypatch.setattr(mw, "SettingsDialog", _SpyDialog)
        monkeypatch.setattr(_SpyDialog, "raise_", lambda self: raised.append("raise"))
        monkeypatch.setattr(_SpyDialog, "activateWindow", lambda self: raised.append("activate"))
        monkeypatch.setattr(_SpyDialog, "exec", lambda self: 0)

        # Simulate a dialog already open (non-blocking show instead of exec).
        window._settings_dialog = _SpyDialog(window)
        qtbot.addWidget(window._settings_dialog)
        window._open_settings()
        assert len(created) == 1
        assert raised == ["raise", "activate"]

    def test_reference_cleared_after_exec(self, window, monkeypatch):
        """The guard resets once the modal dialog closes."""
        import hsync_desktop.main_window as mw

        monkeypatch.setattr(mw.SettingsDialog, "exec", lambda self: 0)
        window._open_settings()
        assert window._settings_dialog is None


class TestRemoteIcon:
    @staticmethod
    def _run_and_record(window, monkeypatch) -> list[str]:
        """Call _update_path_display recording every icon name it requests."""
        import hsync_desktop.icons as icons_mod

        names: list[str] = []
        orig = icons_mod.icon

        def spy(name: str):
            names.append(name)
            return orig(name)

        monkeypatch.setattr(icons_mod, "icon", spy)
        window._update_path_display()
        return names

    def test_p2p_without_bootnode_uses_p2p_icon(self, window, monkeypatch, tmp_path):
        """p2p + no bootnode shows the peer icon."""
        import hsync_desktop.main_window as mw

        s = _settings(tmp_path)
        s.setValue("p2p/bootnode", "")
        monkeypatch.setattr(mw, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)
        names = self._run_and_record(window, monkeypatch)
        assert "network-p2p" in names
        assert "network-cloud" not in names
        assert window._remote_label.text() == "p2p"

    def test_server_mode_uses_cloud_icon(self, window, monkeypatch, tmp_path):
        """Server mode always shows the cloud icon."""
        import hsync_desktop.main_window as mw

        s = _settings(tmp_path)
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "https://srv.example.com:9753")
        monkeypatch.setattr(mw, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)
        names = self._run_and_record(window, monkeypatch)
        assert "network-cloud" in names
        assert window._remote_label.text() == "srv.example.com"


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
        # The client dials 443 (bare HSYNC_BOOTNODE): the p2p listen port must
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


class TestShutdown:
    """Quit paths: the tray action confirms while syncing, Ctrl+C never prompts."""

    @staticmethod
    def _record_quit(monkeypatch, mw) -> list[int]:
        calls: list[int] = []
        monkeypatch.setattr(mw.QApplication, "quit", staticmethod(lambda: calls.append(1)))
        return calls

    @staticmethod
    def _answer(monkeypatch, answer: QMessageBox.StandardButton) -> None:
        monkeypatch.setattr(QMessageBox, "exec", lambda self: answer)

    @pytest.fixture(autouse=True)
    def _tray(self, window):
        """Tray stub that keeps ``MainWindow.closeEvent`` on the minimise branch.

        pytest-qt closes the window at teardown; ``isVisible()`` always True keeps
        that path (and ``_shutdown``) from touching a real tray or a modal dialog.
        """

        class _Tray:
            def __init__(self) -> None:
                self.hidden = 0

            def hide(self) -> None:
                self.hidden += 1

            def isVisible(self) -> bool:
                return True

            def set_window_visible(self, _visible: bool) -> None:
                pass

        tray = _Tray()
        window._tray = tray  # type: ignore[assignment]
        return tray

    def test_shutdown_quits_without_prompt(self, window, monkeypatch, _tray):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)
        prompts: list[int] = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: prompts.append(1) or 0)

        window._shutdown()

        assert prompts == []  # never blocks on a dialog
        assert _tray.hidden == 1
        assert quit_calls == [1]

    def test_quit_while_syncing_can_be_cancelled(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)
        window._engine._running = True
        self._answer(monkeypatch, QMessageBox.StandardButton.No)

        window._quit()

        assert quit_calls == []  # user declined; nothing shut down

    def test_quit_while_syncing_stops_engine_and_quits(self, window, monkeypatch):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)
        window._engine._running = True
        stopped: list[int] = []
        monkeypatch.setattr(window._engine, "stop", lambda: stopped.append(1))
        self._answer(monkeypatch, QMessageBox.StandardButton.Yes)

        window._quit()

        assert stopped == [1]
        assert quit_calls == [1]

    @staticmethod
    def _fire_sigint(window) -> None:
        import signal as signal_mod

        import hsync_desktop.main as main_mod

        previous = signal_mod.getsignal(signal_mod.SIGINT)
        try:
            main_mod._install_sigint_handler(window)
            handler = signal_mod.getsignal(signal_mod.SIGINT)
            assert callable(handler)
            handler(signal_mod.SIGINT, None)
        finally:
            signal_mod.signal(signal_mod.SIGINT, previous)

    def test_sigint_quits_when_idle(self, window, monkeypatch, _tray):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)

        self._fire_sigint(window)

        assert quit_calls == [1]

    def test_sigint_confirms_while_syncing_and_can_be_cancelled(self, window, monkeypatch, _tray):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)
        window._engine._running = True
        self._answer(monkeypatch, QMessageBox.StandardButton.No)

        self._fire_sigint(window)

        assert quit_calls == []  # user declined; sync keeps running

    def test_sigint_confirms_while_syncing_and_quits_on_yes(self, window, monkeypatch, _tray):
        import hsync_desktop.main_window as mw

        quit_calls = self._record_quit(monkeypatch, mw)
        window._engine._running = True
        stopped: list[int] = []
        monkeypatch.setattr(window._engine, "stop", lambda: stopped.append(1))
        self._answer(monkeypatch, QMessageBox.StandardButton.Yes)

        self._fire_sigint(window)

        assert stopped == [1]
        assert quit_calls == [1]


class TestEngineStartFailure:
    """A failed engine start must be visible, not a silent no-op."""

    @staticmethod
    def _capture_dialogs(monkeypatch) -> list[QMessageBox]:
        shown: list[QMessageBox] = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self) or 0)
        return shown

    def test_start_engine_shows_dialog_and_logs_error(self, window, monkeypatch):
        shown = self._capture_dialogs(monkeypatch)

        def failing_start(_args):
            window._engine.error_occurred.emit("hsync binary not found.")
            return False

        monkeypatch.setattr(window._engine, "start", failing_start)

        assert window._start_engine(["p2p"]) is False
        assert len(shown) == 1
        assert shown[0].text() == tr("notif.engine_start_failed")
        assert "hsync binary not found." in shown[0].informativeText()
        assert "hsync binary not found." in window._log_view.toPlainText()

    def test_start_engine_success_shows_no_dialog(self, window, monkeypatch):
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        assert shown == []

    def test_continue_after_disclaimer_reports_start_failure(self, window, monkeypatch, tmp_path):
        import hsync_desktop.main_window as mw

        shown = self._capture_dialogs(monkeypatch)
        # Skip the pre-flight prompts so the start attempt is reached directly.
        monkeypatch.setattr(window, "_check_deletion_risk", lambda: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_bootnode_trust", lambda: True)
        monkeypatch.setattr(window, "_ensure_server_trust", lambda: True)
        monkeypatch.setattr(mw, "build_hsync_args", lambda *a, **k: ["p2p"])
        window._local_path = str(tmp_path)
        window._pending_sync_path = str(tmp_path)

        def failing_start(_args):
            window._engine.error_occurred.emit("Failed to start hsync process.")
            return False

        monkeypatch.setattr(window._engine, "start", failing_start)

        window._continue_start_after_disclaimer()

        assert len(shown) == 1
        assert shown[0].text() == tr("notif.engine_start_failed")
        # The window is left usable (start re-enabled), not stuck mid-start.
        assert window._btn_start.isEnabled()
        assert not window._btn_stop.isEnabled()


class TestAboutMenu:
    """The Help > About entry is just 'About' / 'Informazioni', not the app name."""

    def test_about_action_uses_the_short_label(self, window):
        assert window._act_help_about.text() == tr("menu.help.about")
        assert "HSYNC" not in window._act_help_about.text()

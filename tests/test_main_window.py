# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the MainWindow core flows (settings, start, quit)."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings import SettingsDialog
from tests._helpers import _patch_all, _resolve_dialog, _settings


class TestOpenSettings:
    def test_second_open_raises_existing_dialog(self, window, monkeypatch, qtbot):
        """A tray re-click raises the open dialog instead of stacking a new one."""

        created: list[object] = []
        real_dialog = SettingsDialog

        class _SpyDialog(real_dialog):  # type: ignore[misc]
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                created.append(self)

        raised: list[str] = []
        _patch_all(monkeypatch, "SettingsDialog", _SpyDialog)
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

        monkeypatch.setattr(SettingsDialog, "exec", lambda self: 0)
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

        s = _settings(tmp_path)
        s.setValue("p2p/bootnode", "")
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)
        names = self._run_and_record(window, monkeypatch)
        assert "network-p2p" in names
        assert "network-cloud" not in names
        assert window._remote_label.text() == "p2p"

    def test_server_mode_uses_cloud_icon(self, window, monkeypatch, tmp_path):
        """Server mode always shows the cloud icon."""

        s = _settings(tmp_path)
        s.setValue("p2p/enabled", False)
        s.setValue("connection/server_url", "https://srv.example.com:9753")
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)
        names = self._run_and_record(window, monkeypatch)
        assert "network-cloud" in names
        assert window._remote_label.text() == "srv.example.com"


class TestShutdown:
    """Quit paths: the tray action confirms while syncing, Ctrl+C never prompts."""

    @staticmethod
    def _record_quit(monkeypatch) -> list[int]:
        calls: list[int] = []
        monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: calls.append(1)))
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

        quit_calls = self._record_quit(monkeypatch)
        prompts: list[int] = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: prompts.append(1) or 0)

        window._shutdown()

        assert prompts == []  # never blocks on a dialog
        assert _tray.hidden == 1
        assert quit_calls == [1]

    def test_quit_while_syncing_can_be_cancelled(self, window, monkeypatch):

        quit_calls = self._record_quit(monkeypatch)
        window._engine._running = True
        self._answer(monkeypatch, QMessageBox.StandardButton.No)

        window._quit()

        assert quit_calls == []  # user declined; nothing shut down

    def test_quit_while_syncing_stops_engine_and_quits(self, window, monkeypatch):

        quit_calls = self._record_quit(monkeypatch)
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

        quit_calls = self._record_quit(monkeypatch)

        self._fire_sigint(window)

        assert quit_calls == [1]

    def test_sigint_confirms_while_syncing_and_can_be_cancelled(self, window, monkeypatch, _tray):

        quit_calls = self._record_quit(monkeypatch)
        window._engine._running = True
        self._answer(monkeypatch, QMessageBox.StandardButton.No)

        self._fire_sigint(window)

        assert quit_calls == []  # user declined; sync keeps running

    def test_sigint_confirms_while_syncing_and_quits_on_yes(self, window, monkeypatch, _tray):

        quit_calls = self._record_quit(monkeypatch)
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

        shown = self._capture_dialogs(monkeypatch)
        # Skip the pre-flight prompts so the start attempt is reached directly.
        monkeypatch.setattr(window, "_check_deletion_risk", lambda: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_bootnode_trust", lambda: True)
        monkeypatch.setattr(window, "_ensure_server_trust", lambda: True)
        _patch_all(monkeypatch, "build_hsync_args", lambda *a, **k: ["p2p"])
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


class TestSecurityRejectedLog:
    """An unsafe remote path refused by the client is surfaced to the user."""

    def test_logs_the_refusal_with_detail(self, window):
        window._on_security_rejected("download", "../../etc/passwd", "unsafe remote path rejected")
        text = window._log_view.toPlainText()
        assert "../../etc/passwd" in text
        assert "unsafe remote path rejected" in text


class TestStatusLifecycle:
    """The bottom-left status follows the engine lifecycle instead of sticking."""

    @staticmethod
    def _bypass_start_prompts(monkeypatch, window, tmp_path):
        monkeypatch.setattr(window, "_check_deletion_risk", lambda: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_bootnode_trust", lambda: True)
        monkeypatch.setattr(window, "_ensure_server_trust", lambda: True)
        _patch_all(monkeypatch, "build_hsync_args", lambda *a, **k: ["p2p"])
        window._local_path = str(tmp_path)
        window._pending_sync_path = str(tmp_path)

    def test_start_shows_connecting(self, window, monkeypatch, tmp_path):
        self._bypass_start_prompts(monkeypatch, window, tmp_path)
        monkeypatch.setattr(window, "_start_engine", lambda _args: True)

        window._continue_start_after_disclaimer()

        assert window._status_label.text() == tr("status.connecting")

    def test_process_finished_drops_to_disconnected(self, window):
        window._on_status("connecting")

        window._on_process_finished(0, "stopped")

        assert window._status_label.text() == tr("status.disconnected")

    def test_process_finished_avoids_the_connection_lost_side_effects(self, window, monkeypatch):
        called: list[str] = []
        monkeypatch.setattr(window, "_on_status", lambda status: called.append(status))

        window._on_process_finished(0, "stopped")

        # The terminal status is set through the side-effect-free helper, so a
        # normal stop never fires the "connection lost" notification.
        assert called == []
        assert window._status_label.text() == tr("status.disconnected")


class TestPeerCountLifecycle:
    """The device count is cleared when the link drops (no stale "N/M")."""

    def test_disconnected_clears_the_peer_count(self, window):
        window._on_peers(1, 2)
        assert window._peers_label.text() == "1/2"

        window._on_status("disconnected")

        assert window._peers_label.text() == "–"

    def test_waiting_clears_the_peer_count(self, window):
        window._on_peers(2, 2)

        window._on_status("waiting")

        assert window._peers_label.text() == "–"

    def test_process_finished_clears_the_peer_count(self, window):
        window._on_peers(1, 2)

        window._on_process_finished(0, "stopped")

        assert window._peers_label.text() == "–"


class TestShareNameInTitle:
    """The share name (persistent identity) lives in the window title, not the
    bottom status bar."""

    def test_bucket_sets_the_window_title(self, window):
        window._on_bucket_detected("demo-p2p")

        assert window.windowTitle() == f"{tr('app.name')} — demo-p2p"

    def test_empty_bucket_resets_the_title(self, window):
        window._on_bucket_detected("demo-p2p")

        window._on_bucket_detected("")

        assert window.windowTitle() == tr("app.name")

    def test_status_bar_no_longer_hosts_the_share_name(self, window):
        assert window.findChild(QLabel, "bucketLabel") is None


class TestLanguageChangeRetranslatesTable:
    """The file table column headers must follow a live language change."""

    def test_apply_translations_refreshes_table_columns(self, window, monkeypatch):
        called: list[int] = []
        monkeypatch.setattr(window._file_panel, "retranslate_columns", lambda: called.append(1))

        window._apply_translations()

        assert called == [1]


class TestHelpMenu:
    """Help menu: external links first, then License and About (About last)."""

    def test_order_is_links_then_license_then_about(self, window):
        from hsync_desktop.i18n import tr

        assert [action.text() for action in window._menu_help.actions()] == [
            tr("menu.help.docs"),
            tr("menu.help.github"),
            "",
            tr("menu.help.license"),
            tr("menu.help.about"),
        ]

    def test_license_action_opens_the_dialog(self, window, monkeypatch):
        from hsync_desktop.license_dialog import LicenseDialog

        opened: list[int] = []
        monkeypatch.setattr(LicenseDialog, "exec", lambda self: opened.append(1))

        window._act_help_license.trigger()

        assert opened == [1]


class TestSelectionSync:
    """File/context menu "Send now" / "Receive now" act on a selection."""

    @staticmethod
    def _stub_preflight(window, monkeypatch):
        for name in (
            "_check_keyless_p2p",
            "_check_disk_space",
            "_ensure_bootnode_trust",
            "_ensure_server_trust",
        ):
            monkeypatch.setattr(window, name, lambda: True)

    def test_subdir_mapping_folders_and_files(self, window):
        assert window._selection_subdir("media/") == "media"
        assert window._selection_subdir("media/sub/file.txt") == "media/sub"
        assert window._selection_subdir("top.txt") == ""

    def test_send_starts_a_scoped_dry_run_preview(self, window, monkeypatch, tmp_path):
        self._stub_preflight(window, monkeypatch)
        # Avoid the panel's worker thread: this test only checks args/start.
        monkeypatch.setattr(window._file_panel, "load_local_files", lambda _p: None)
        seen: dict[str, object] = {}
        monkeypatch.setattr(
            "hsync_desktop.main_window.actions.build_selection_args",
            lambda local, subdir, direction, dry_run=False: (
                seen.update(subdir=subdir, direction=direction, dry_run=dry_run) or ["--once"]
            ),
        )
        started: list[list[str]] = []
        monkeypatch.setattr(window, "_start_engine", lambda args: started.append(args) or True)
        window._local_path = str(tmp_path)

        window._sync_selection("media/sub/", "upload-only")

        assert (seen["subdir"], seen["direction"], seen["dry_run"]) == (
            "media/sub",
            "upload-only",
            True,
        )
        assert started == [["--once"]]
        assert window._pending_selection_sync == ("media/sub", "upload-only")

    def test_receive_keeps_the_deletion_risk_gate(self, window, monkeypatch, tmp_path):
        self._stub_preflight(window, monkeypatch)
        monkeypatch.setattr(window, "_check_deletion_risk", lambda: False)
        started: list[list[str]] = []
        monkeypatch.setattr(window, "_start_engine", lambda args: started.append(args) or True)
        window._local_path = str(tmp_path)

        window._sync_selection("media/", "download-only")

        assert started == []  # declined the deletion-risk prompt → never starts

    def test_accepting_the_preview_runs_the_selection(self, window, monkeypatch):
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        started: list[tuple] = []
        monkeypatch.setattr(
            window,
            "_start_selection_run",
            lambda subdir, direction: started.append((subdir, direction)),
        )
        window._pending_selection_sync = ("media", "upload-only")
        window._preview_stats.to_upload = 1
        monkeypatch.setattr(
            PreviewSummaryDialog, "exec", lambda self: PreviewSummaryDialog.DialogCode.Accepted
        )

        window._show_preview_summary()

        assert started == [("media", "upload-only")]
        assert window._pending_selection_sync is None

    def test_cancelling_the_preview_runs_nothing(self, window, monkeypatch):
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        started: list[tuple] = []
        monkeypatch.setattr(window, "_start_selection_run", lambda *a: started.append(a))
        window._pending_selection_sync = ("media", "download-only")
        window._preview_stats.to_download = 1
        monkeypatch.setattr(
            PreviewSummaryDialog, "exec", lambda self: PreviewSummaryDialog.DialogCode.Rejected
        )

        window._show_preview_summary()

        assert started == []
        assert window._pending_selection_sync is None


class TestSelectionSyncMenu:
    """Send/Receive are enabled only with a selection and while stopped."""

    def test_enabled_with_selection_when_idle(self, window):
        assert not window._engine.is_running

        window._set_file_menu_enabled(True)

        assert window._act_file_send.isEnabled()
        assert window._act_file_receive.isEnabled()

    def test_disabled_while_running(self, window):
        # Force ``is_running`` True and restore it *within* the test so the
        # window teardown never runs against the patched property.
        engine_cls = type(window._engine)
        original = engine_cls.is_running
        engine_cls.is_running = property(lambda self: True)
        try:
            window._set_file_menu_enabled(True)

            assert not window._act_file_send.isEnabled()
            assert not window._act_file_receive.isEnabled()
            assert window._act_file_open.isEnabled()
        finally:
            engine_cls.is_running = original


class TestRemoteRenameMtime:
    """The rename event must not blank out the row's modified date."""

    def test_reads_the_source_mtime_before_the_local_rename_lands(
        self, window, tmp_path, monkeypatch
    ):
        old = tmp_path / "old.txt"
        old.write_text("x")
        os.utime(old, (1000, 1000))
        captured: dict = {}
        monkeypatch.setattr(
            window._file_panel, "rename_file", lambda *a, **k: captured.update(kwargs=k)
        )
        window._local_path = str(tmp_path)

        # Destination missing (event fired before the local rename): the source
        # still carries the mtime.
        window._on_file_renamed(str(old), str(tmp_path / "new.txt"))

        assert captured["kwargs"]["mtime"] == 1000.0

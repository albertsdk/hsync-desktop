# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the MainWindow core flows (settings, start, quit)."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager

import pytest
from hsync_common.protocol.events import UiEventName, build_event
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QMessageBox

from hsync_desktop.docs_links import TROUBLESHOOTING, WATCHER_LIMITS
from hsync_desktop.fonts import ui_font
from hsync_desktop.i18n import tr
from hsync_desktop.settings import SettingsDialog
from tests._helpers import _patch_all, _resolve_dialog, _settings


def _stop_the_deferred_timer(monkeypatch) -> None:
    """Neutralise ``QTimer.singleShot`` in the start mixin.

    ``_on_start`` defers the run by half a second; tests drive the deferred slot
    explicitly so they stay deterministic.
    """

    class _NoTimer:
        @staticmethod
        def singleShot(*_args, **_kwargs) -> None:
            return None

    import hsync_desktop.main_window.start as start_module

    monkeypatch.setattr(start_module, "QTimer", _NoTimer)


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

            def set_check_changes_enabled(self, _enabled: bool) -> None:
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
        monkeypatch.setattr(window._engine, "stop_and_wait", lambda: stopped.append(1))
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
        monkeypatch.setattr(window._engine, "stop_and_wait", lambda: stopped.append(1))
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
            window._engine.error_occurred.emit("hsync binary not found.", "start")
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
        monkeypatch.setattr(window, "_check_deletion_risk", lambda **_: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_trust", lambda continuation: continuation())
        _patch_all(monkeypatch, "build_hsync_args", lambda *a, **k: ["p2p"])
        window._local_path = str(tmp_path)
        window._pending_sync_path = str(tmp_path)

        def failing_start(_args):
            window._engine.error_occurred.emit("Failed to start hsync process.", "start")
            return False

        monkeypatch.setattr(window._engine, "start", failing_start)

        window._continue_start_after_disclaimer()

        assert len(shown) == 1
        assert shown[0].text() == tr("notif.engine_start_failed")
        # The window is left usable (start re-enabled), not stuck mid-start.
        assert window._btn_start.isEnabled()
        assert not window._btn_stop.isEnabled()

    def test_startup_exit_before_ready_reports_once(self, window, monkeypatch):
        """A config error exits normally with code 1: it must still be reported."""
        shown = self._capture_dialogs(monkeypatch)
        notified: list[tuple[str, str]] = []
        monkeypatch.setattr(window, "_notify_error", lambda t, m: notified.append((t, m)))
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        # Started, then died before readiness (the exit-time safety net).
        window._engine.startup_failed.emit(1, "ERROR: No API key configured")
        window._on_process_finished(1, "normal")

        assert len(shown) == 1
        assert tr("notif.engine_startup_failed").replace("{code}", "1") in shown[0].text()
        assert "No API key configured" in shown[0].informativeText()
        assert "No API key configured" in window._log_view.toPlainText()
        assert notified == []  # a manual start is modal, not a tray-only notice

    def test_structured_startup_error_is_reported_with_the_exit_code(self, window, monkeypatch):
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        # Structured event first, then the process exit carries the code.
        window._on_engine_error("No API key configured.", "startup")
        window._on_process_finished(1, "normal")

        assert len(shown) == 1
        assert shown[0].informativeText() == "No API key configured."
        assert tr("notif.engine_startup_failed").replace("{code}", "1") in shown[0].text()

    def test_automatic_startup_failure_uses_the_banner_not_a_modal(self, window, monkeypatch):
        """An autostart in the tray must not raise an invisible blocking modal."""
        shown = self._capture_dialogs(monkeypatch)
        notified: list[tuple[str, str]] = []
        monkeypatch.setattr(window, "_notify_error", lambda t, m: notified.append((t, m)))
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        window._start_is_automatic = True
        try:
            assert window._start_engine(["p2p"]) is True
            window._engine.startup_failed.emit(1, "ERROR: bad config")
        finally:
            window._start_is_automatic = False

        assert shown == []
        assert notified and "bad config" in notified[0][1]

    def test_ready_then_exit_is_not_a_startup_failure(self, window, monkeypatch):
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        window._engine._handle_event(build_event(UiEventName.ready))
        window._on_process_finished(0, "normal")

        assert shown == []

    def test_a_fatal_exit_after_ready_reports_the_client_reason(self, window, monkeypatch):
        """A refusal after readiness (the folder's instance lock) used to be silent."""
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        window._engine._handle_event(build_event(UiEventName.ready))
        window._engine.fatal_exit.emit(
            1, "Another hsync process is already syncing '/data/photos' (pid 42)."
        )

        assert len(shown) == 1
        assert shown[0].text() == tr("notif.engine_stopped").replace("{code}", "1")
        assert "already syncing" in shown[0].informativeText()
        assert "already syncing" in window._log_view.toPlainText()

    def test_a_fatal_exit_is_not_reported_twice(self, window, monkeypatch):
        """An error the client already explained must not raise a second report."""
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)
        monkeypatch.setattr(window, "_notify_error", lambda *_args: None)

        assert window._start_engine(["p2p"]) is True
        window._engine._handle_event(
            build_event(UiEventName.error, message="Connection lost", reason="connection")
        )
        window._engine.fatal_exit.emit(1, "Connection lost")

        assert shown == []

    def test_a_fatal_exit_after_a_user_stop_is_not_reported(self, window, monkeypatch):
        shown = self._capture_dialogs(monkeypatch)
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        assert window._start_engine(["p2p"]) is True
        window._user_stopped = True
        window._engine.fatal_exit.emit(1, "whatever")

        assert shown == []

    def test_an_automatic_fatal_exit_uses_the_banner(self, window, monkeypatch):
        """An autostart in the tray must not raise an invisible blocking modal."""
        shown = self._capture_dialogs(monkeypatch)
        notified: list[tuple[str, str]] = []
        monkeypatch.setattr(window, "_notify_error", lambda t, m: notified.append((t, m)))
        monkeypatch.setattr(window._engine, "start", lambda _args: True)

        window._start_is_automatic = True
        try:
            assert window._start_engine(["p2p"]) is True
            window._engine.fatal_exit.emit(1, "Another hsync process is already syncing")
        finally:
            window._start_is_automatic = False

        assert shown == []
        assert notified and "already syncing" in notified[0][1]


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
        monkeypatch.setattr(window, "_check_deletion_risk", lambda **_: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_trust", lambda continuation: continuation())
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


class TestPeerLabelSemantics:
    """The title says what the counter counts: devices (p2p) or members (server)."""

    def test_p2p_mode_labels_devices(self, window, settings, monkeypatch):
        settings.setValue("p2p/enabled", True)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)

        window._update_peers_label_title()

        assert window._lbl_peers.text() == tr("label.peers")

    def test_server_mode_labels_connected_members(self, window, settings, monkeypatch):
        settings.setValue("p2p/enabled", False)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)

        window._update_peers_label_title()

        assert window._lbl_peers.text() == tr("label.users")

    def test_applying_settings_relabels_the_presence_title(self, window, settings, monkeypatch):
        settings.setValue("p2p/enabled", False)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)

        window._apply_settings_changes()

        assert window._lbl_peers.text() == tr("label.users")


class TestShareNameInActionBar:
    """The share name labels the local folder (next to the folder icon); the
    window title stays the app name and the path lives in the tooltip."""

    def test_title_stays_the_app_name(self, window):
        window._on_bucket_detected("demo-p2p")

        assert window.windowTitle() == tr("app.name")

    def test_empty_bucket_keeps_the_app_name_title(self, window):
        window._on_bucket_detected("demo-p2p")

        window._on_bucket_detected("")

        assert window.windowTitle() == tr("app.name")

    def test_bucket_name_labels_the_folder_with_path_tooltip(self, window, tmp_path):
        window._local_path = str(tmp_path)

        window._on_bucket_detected("demo-p2p")

        assert "demo-p2p" in window._path_label.text()
        assert window._path_label.toolTip() == str(tmp_path)

    def test_saved_share_name_is_used_before_detection(self, window, monkeypatch, tmp_path):
        s = _settings(tmp_path)
        s.setValue("sync/bucket", "saved-share")
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)
        window._bucket = ""

        window._update_path_display()

        assert "saved-share" in window._path_label.text()

    def test_status_bar_no_longer_hosts_the_share_name(self, window):
        assert window.findChild(QLabel, "bucketLabel") is None


class TestRoleVisibility:
    """The role exists only in p2p; its text appears once connected and known."""

    def test_indicator_hidden_before_the_election(self, window, monkeypatch, tmp_path):
        s = _settings(tmp_path)
        s.setValue("p2p/enabled", True)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)

        window._update_path_display()

        assert window._role_icon.isHidden()
        assert window._role_label.isHidden()

    def test_text_appears_once_connected_and_known(self, window, monkeypatch, tmp_path):
        s = _settings(tmp_path)
        s.setValue("p2p/enabled", True)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)

        window._on_master(True)
        window._on_status("connected")

        assert not window._role_icon.isHidden()
        assert not window._role_label.isHidden()

    def test_role_is_hidden_in_server_mode(self, window, monkeypatch, tmp_path):
        s = _settings(tmp_path)
        s.setValue("p2p/enabled", False)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)

        window._update_path_display()

        assert window._role_label.isHidden()
        assert window._role_icon.isHidden()


class TestFilePanelConnectionState:
    """The file table grays "Local" rows only while a link is active."""

    def test_status_updates_the_table_connection_state(self, window, monkeypatch):
        seen: list[bool] = []
        monkeypatch.setattr(window._file_panel, "set_connected", seen.append)

        window._on_status("connected")
        window._on_status("disconnected")

        assert seen == [True, False]

    def test_process_finished_returns_the_table_to_idle(self, window, monkeypatch):
        seen: list[bool] = []
        monkeypatch.setattr(window._file_panel, "set_connected", seen.append)

        window._on_process_finished(0, "normal")

        assert seen == [False]


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
        ):
            monkeypatch.setattr(window, name, lambda: True)
        monkeypatch.setattr(window, "_ensure_trust", lambda continuation: continuation())

    def test_subdir_mapping_folders_and_files(self, window):
        assert window._selection_subdir("media/") == "media"
        assert window._selection_subdir("media/sub/file.txt") == "media/sub"
        assert window._selection_subdir("top.txt") == ""

    def test_display_name_maps_to_the_visible_row(self, window):
        assert window._selection_display_name("top.txt", "") == "top.txt"
        assert window._selection_display_name("media/file.txt", "media") == "file.txt"
        assert window._selection_display_name("media/sub/", "media") == "sub"
        assert window._selection_display_name("media/sub/file.txt", "media/sub") == "file.txt"

    def test_send_keeps_the_current_folder_and_row(self, window, monkeypatch, tmp_path):
        self._stub_preflight(window, monkeypatch)
        recorded: dict[str, object] = {}
        monkeypatch.setattr(
            window._file_panel,
            "load_local_files",
            lambda path, **kw: recorded.update(path=path, **kw),
        )
        monkeypatch.setattr(window, "_start_engine", lambda args: True)
        window._local_path = str(tmp_path)
        window._file_panel._table._current_path = "media"

        window._sync_selection("media/sub/file.txt", "upload-only")

        assert recorded["restore_view"] == ("media", "sub")

    def test_confirming_the_preview_keeps_the_view(self, window, monkeypatch, tmp_path):
        recorded: dict[str, object] = {}
        monkeypatch.setattr(
            window._file_panel,
            "load_local_files",
            lambda path, **kw: recorded.update(path=path, **kw),
        )
        monkeypatch.setattr(window, "_start_engine", lambda args: True)
        window._local_path = str(tmp_path)
        window._selection_sync_view = ("media", "sub")

        window._start_selection_run("media/sub", "upload-only")

        assert recorded["restore_view"] == ("media", "sub")

    def test_send_starts_a_scoped_dry_run_preview(self, window, monkeypatch, tmp_path):
        self._stub_preflight(window, monkeypatch)
        # Avoid the panel's worker thread: this test only checks args/start.
        monkeypatch.setattr(window._file_panel, "load_local_files", lambda _p, **_kw: None)
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
        monkeypatch.setattr(window, "_check_deletion_risk", lambda **_: False)
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
        window._selection_sync_active = True
        window._selection_sync_phase = "preview"
        window._pending_selection_sync = ("media", "upload-only")
        window._preview_stats.to_upload = 1
        monkeypatch.setattr(
            PreviewSummaryDialog, "exec", lambda self: PreviewSummaryDialog.DialogCode.Accepted
        )

        window._show_preview_summary()

        assert started == [("media", "upload-only")]
        # The confirmed op stays in flight until its result arrives.
        assert window._selection_sync_active is True
        assert window._pending_selection_sync == ("media", "upload-only")

    def test_cancelling_the_preview_runs_nothing(self, window, monkeypatch):
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        started: list[tuple] = []
        monkeypatch.setattr(window, "_start_selection_run", lambda *a: started.append(a))
        window._selection_sync_active = True
        window._selection_sync_phase = "preview"
        window._pending_selection_sync = ("media", "download-only")
        window._preview_stats.to_download = 1
        monkeypatch.setattr(
            PreviewSummaryDialog, "exec", lambda self: PreviewSummaryDialog.DialogCode.Rejected
        )

        window._show_preview_summary()

        assert started == []
        assert window._selection_sync_active is False
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


class TestLogViewerFont:
    """The log viewer uses the dedicated log font, not a QSS family."""

    def test_log_view_uses_the_log_monospace_font(self, qtbot, monkeypatch, settings):
        from PySide6.QtGui import QFont

        import hsync_desktop.main_window.ui as ui_module
        from hsync_desktop.engine import HsyncEngine
        from hsync_desktop.main_window import MainWindow

        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)
        _patch_all(monkeypatch, "find_hsync_binary", lambda: "/fake/hsync")
        monkeypatch.setattr(ui_module, "log_monospace_font", lambda: QFont("Probe Log Mono"))

        win = MainWindow(HsyncEngine(binary_path="/fake/hsync"))
        qtbot.addWidget(win)

        assert win._log_view.font().family() == "Probe Log Mono"


class TestLinkStyling:
    """Clickable share/path labels use the default colour and are underlined."""

    def test_share_placeholder_link(self, window):
        from PySide6.QtGui import QPalette

        window._bucket = ""
        window._update_path_display()

        text = window._path_label.text()
        colour = window._path_label.palette().color(QPalette.ColorRole.WindowText).name()
        assert "text-decoration:underline" in text
        assert f"color:{colour}" in text

    def test_breadcrumb_links(self, window):
        from PySide6.QtGui import QPalette

        window._file_panel._table._current_path = "sub/dir"
        window._file_panel._update_breadcrumb()

        label = window._file_panel._breadcrumb_label
        colour = label.palette().color(QPalette.ColorRole.WindowText).name()
        assert "text-decoration:underline" in label.text()
        assert f"color:{colour}" in label.text()

    def test_detail_panel_filepath_link(self, window):
        from PySide6.QtGui import QPalette

        from hsync_desktop.file_panel import FileTransfer, TransferStatus

        window._file_panel._detail.show_transfer(
            FileTransfer(
                filepath="sub/f.txt",
                direction="↓",
                size=1,
                status=TransferStatus.LOCAL,
            )
        )

        label = window._file_panel._detail._lbl_filepath
        colour = label.palette().color(QPalette.ColorRole.WindowText).name()
        assert "text-decoration:underline" in label.text()
        assert f"color:{colour}" in label.text()

    def test_breadcrumb_escapes_folder_names(self, window):
        window._file_panel._table._current_path = 'a<b>&"c'

        window._file_panel._update_breadcrumb()

        text = window._file_panel._breadcrumb_label.text()
        assert "<b>" not in text
        assert "&lt;" in text
        assert "&quot;" in text

    def test_current_breadcrumb_segment_is_not_a_link(self, window):
        """The folder already shown must not look clickable."""
        window._file_panel._table._current_path = "sub/dir"

        window._file_panel._update_breadcrumb()

        text = window._file_panel._breadcrumb_label.text()
        assert 'href="nav:sub/dir"' not in text
        assert 'href="nav:sub"' in text
        assert '<span style="color:' in text

    def test_single_segment_breadcrumb_has_no_link(self, window):
        from PySide6.QtCore import Qt

        window._file_panel._table._current_path = "dir"

        window._file_panel._update_breadcrumb()

        label = window._file_panel._breadcrumb_label
        assert "<a " not in label.text()
        assert label.cursor().shape() == Qt.CursorShape.ArrowCursor

    def test_root_icon_is_inert_at_root(self, window):
        from PySide6.QtCore import Qt

        panel = window._file_panel
        panel._table._current_path = ""
        panel._update_breadcrumb()
        assert panel._breadcrumb_icon.cursor().shape() == Qt.CursorShape.ArrowCursor

        panel._table._current_path = "sub"
        panel._update_breadcrumb()
        assert panel._breadcrumb_icon.cursor().shape() == Qt.CursorShape.PointingHandCursor

    def test_breadcrumb_uses_slashes_on_posix(self, window, monkeypatch):
        from hsync_desktop.file_panel import panel as panel_mod

        monkeypatch.setattr(panel_mod, "_platform", lambda: "linux")
        window._file_panel._table._current_path = "sub/dir"

        window._file_panel._update_breadcrumb()

        text = window._file_panel._breadcrumb_label.text()
        assert " / " in text
        assert "›" not in text
        # The root is the icon, so a leading slash would read as an absolute path.
        assert not text.startswith("/")

    def test_breadcrumb_uses_explorer_separator_on_windows(self, window, monkeypatch):
        from hsync_desktop.file_panel import panel as panel_mod

        monkeypatch.setattr(panel_mod, "_platform", lambda: "win32")
        window._file_panel._table._current_path = "sub/dir"

        window._file_panel._update_breadcrumb()

        text = window._file_panel._breadcrumb_label.text()
        assert " > " in text
        assert not text.startswith(">")

    def test_nav_buttons_use_the_larger_icon_size(self, window):
        from PySide6.QtCore import QSize

        panel = window._file_panel
        for button in (panel._btn_back, panel._btn_forward, panel._btn_up):
            assert button.iconSize() == QSize(20, 20)

    def test_root_icon_uses_the_larger_icon_size(self, window):
        from PySide6.QtCore import QSize

        panel = window._file_panel
        panel._table._current_path = "sub"

        panel._update_breadcrumb()

        pixmap = panel._breadcrumb_icon.pixmap()
        assert not pixmap.isNull()
        assert pixmap.size() == QSize(20, 20)
        assert panel._breadcrumb_icon.size() == QSize(24, 24)

    def test_detail_href_is_escaped(self, window):
        from hsync_desktop.file_panel import FileTransfer, TransferStatus

        window._file_panel._detail.set_base_directory("/base")
        window._file_panel._detail.show_transfer(
            FileTransfer(
                filepath='a"b/c.txt',
                direction="↓",
                size=1,
                status=TransferStatus.LOCAL,
            )
        )

        text = window._file_panel._detail._lbl_filepath.text()
        assert "&quot;" in text
        assert 'a"b' not in text

    def test_theme_refresh_rebuilds_both_link_labels(self, window, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            window._file_panel, "_update_breadcrumb", lambda: calls.append("breadcrumb")
        )
        monkeypatch.setattr(
            window._file_panel._detail,
            "refresh_link_color",
            lambda: calls.append("detail"),
        )

        window._file_panel.refresh_icons_for_theme()

        assert calls == ["breadcrumb", "detail"]


class TestSystemThemeFollow:
    """With the "system" theme, a desktop scheme change re-applies it live."""

    def test_system_setting_reapplies_on_scheme_change(self, window, monkeypatch):
        import hsync_desktop.main_window.window as window_mod

        applied: list[str] = []
        monkeypatch.setattr(window_mod, "get_theme_setting", lambda: "system")
        monkeypatch.setattr(window_mod, "detect_system_theme", lambda: "dark")
        monkeypatch.setattr(window_mod, "apply_theme", lambda app, theme: applied.append(theme))
        monkeypatch.setattr(window, "_refresh_icons_for_theme", lambda: None)

        window._on_system_color_scheme_changed()

        assert applied == ["dark"]

    def test_fixed_theme_ignores_scheme_change(self, window, monkeypatch):
        import hsync_desktop.main_window.window as window_mod

        applied: list[str] = []
        monkeypatch.setattr(window_mod, "get_theme_setting", lambda: "dark")
        monkeypatch.setattr(window_mod, "apply_theme", lambda app, theme: applied.append(theme))

        window._on_system_color_scheme_changed()

        assert applied == []


class TestInfoToast:
    """The transient feedback is an overlay: it never reflows the window."""

    def test_banner_is_not_in_the_root_layout(self, window):
        from PySide6.QtWidgets import QVBoxLayout

        root = window.findChild(QVBoxLayout, "rootLayout")
        assert root is not None
        assert root.indexOf(window._info_banner) == -1
        assert window._info_banner.parent() is window.centralWidget()

    def test_showing_the_toast_does_not_reflow_the_splitter(self, window):
        sizes_before = window._main_splitter.sizes()

        window._show_info_banner("searching", auto_hide_ms=0, kind="progress")

        assert not window._info_banner.isHidden()
        assert window._main_splitter.sizes() == sizes_before
        assert not window._info_progress.isHidden()

    def test_toast_is_positioned_bottom_right_on_first_show(self, window):
        window.resize(900, 600)
        window.show()

        window._show_info_banner("searching", auto_hide_ms=0, kind="progress")

        central = window.centralWidget()
        pos = window._info_banner.pos()
        assert pos.x() >= 16
        assert pos.x() + window._info_banner.width() <= central.width()
        assert pos.y() >= 16

    def test_banner_is_enlarged_and_fits_the_window(self, window):
        window.resize(900, 600)
        window.show()

        window._show_info_banner("Invia e ricevi ora", auto_hide_ms=0, kind="progress")

        central = window.centralWidget()
        expected = min(640, max(220, central.width() - 32))
        assert window._info_banner.width() == expected
        assert window._info_banner.width() > 420  # clearly larger than the old cap
        assert window._info_banner.pos().x() + window._info_banner.width() <= central.width()

    def test_progress_bar_is_only_for_progress(self, window):
        window._show_info_banner("searching", kind="progress")
        assert not window._info_progress.isHidden()

        window._show_info_banner("done", kind="success")
        assert window._info_progress.isHidden()

    def test_success_survives_process_finish(self, window):
        window._show_info_banner("done", kind="success")

        window._on_process_finished(0, "normal")

        assert not window._info_banner.isHidden()

    def test_progress_is_cleared_on_process_finish(self, window):
        window._show_info_banner("working", kind="progress")

        window._on_process_finished(0, "normal")

        assert window._info_banner.isHidden()

    def test_a_new_run_clears_the_toast(self, window, monkeypatch, tmp_path):
        window._show_info_banner("done", kind="success")
        monkeypatch.setattr(window._file_panel, "load_local_files", lambda *a, **k: None)

        window._prepare_engine_run(str(tmp_path))

        assert window._info_banner.isHidden()

    def test_banner_background_is_translucent(self, window):
        """The toast background is semi-transparent; the text stays opaque."""
        sheet = window._info_banner.styleSheet()
        match = re.search(
            r"#infoBanner\s*\{[^}]*background-color:\s*rgba\([^)]*,\s*([\d.]+)\)",
            sheet,
        )
        assert match is not None, sheet
        assert float(match.group(1)) < 1.0
        assert "color: #ffffff" in sheet

    def test_error_toast_uses_the_error_severity(self, window):
        window._notify_error(tr("notif.error"), "boom")

        assert window._info_banner_kind == "error"
        assert window._info_banner.property("severity") == "error"
        assert "rgba(220, 53, 69, 0.85)" in window._info_banner.styleSheet()
        text = window._info_banner_label.text()
        assert text.startswith("⛔")
        assert tr("notif.error") in text and "boom" in text

    def test_warning_toast_uses_the_warning_severity(self, window):
        window._notify_warning(tr("notif.no_master_title"), "no master")

        assert window._info_banner_kind == "warning"
        assert window._info_banner.property("severity") == "warning"
        assert "rgba(180, 83, 9, 0.85)" in window._info_banner.styleSheet()
        assert window._info_banner_label.text().startswith("⚠")

    def test_an_engine_warning_uses_the_warning_channel(self, window, monkeypatch):
        """A non-fatal engine condition is a warning, never an error."""
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning("Bootnode node:443 unreachable", "bootnode")

        assert len(calls) == 1
        assert calls[0][1]["category"] == "warnings"
        assert "unreachable" in calls[0][0][1]

    def test_a_transient_warning_shows_an_ephemeral_toast(self, window, monkeypatch):
        """A self-healing warning must not persist nor reach the OS."""
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning(
            "Some real-time changes were queued faster than they could be sent",
            "events",
            True,
        )

        assert calls == []
        assert window._info_banner_kind == "notice"
        assert window._info_banner.property("severity") == "warning"
        assert window._info_timer.isActive()  # auto-hides

    def test_an_engine_warning_is_ignored_after_a_user_stop(self, window, monkeypatch):
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = True

        window._on_engine_warning("File watcher degraded to polling", "watcher")

        assert calls == []

    def test_a_watcher_warning_carries_the_remedy_and_the_guide(self, window, monkeypatch):
        """A degraded watcher is actionable: cause, numbers and the guide link."""
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning(
            "The shared folder needs more watches",
            "watcher",
            False,
            {"reason": "inotify_watches", "needed": 12000, "limit": 8192},
        )

        message = calls[0][0][1]
        assert tr("notif.remedy_inotify_watches") in message
        assert tr("notif.remedy_numbers").format(needed=12000, limit=8192) in message
        assert calls[0][1]["help_url"] == WATCHER_LIMITS

    def test_a_remedy_warning_shows_the_guide_link_in_the_banner(self, window):
        window._user_stopped = False

        window._on_engine_warning(
            "The shared folder needs more watches",
            "watcher",
            False,
            {"reason": "inotify_watches", "needed": 3, "limit": 2},
        )

        assert not window._info_banner_link.isHidden()
        assert window._info_banner_link.toolTip() == WATCHER_LIMITS
        assert window._info_banner_link.accessibleName() == tr("notif.open_guide")

    def test_a_non_watcher_warning_keeps_the_guide_without_a_remedy(self, window, monkeypatch):
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning("Bootnode unreachable", "bootnode", False, {"reason": ""})

        assert calls[0][0][1] == "Bootnode unreachable"  # no remedy text invented
        assert calls[0][1]["help_url"] == TROUBLESHOOTING

    def test_a_descriptor_limit_warning_also_deep_links(self, window, monkeypatch):
        """Every watcher remedy lives on the client page, not only inotify."""
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning(
            "Too many open files", "watcher", False, {"reason": "fd_exhaustion"}
        )

        assert calls[0][1]["help_url"] == WATCHER_LIMITS

    def test_an_unclassified_watcher_downgrade_keeps_the_desktop_guide(self, window, monkeypatch):
        """A downgrade with no actionable reason must not claim a remedy page."""
        calls: list[tuple] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda *a, **k: calls.append((a, k)), raising=False
        )
        window._user_stopped = False

        window._on_engine_warning(
            "File watcher degraded to polling",
            "watcher",
            False,
            {"reason": "polling_fallback"},
        )

        assert calls[0][1]["help_url"] == TROUBLESHOOTING

    def test_a_transient_warning_has_no_guide_link(self, window):
        window._user_stopped = False

        window._on_engine_warning(
            "Some changes were dropped", "events", True, {"reason": "transient"}
        )

        assert window._info_banner_link.isHidden()

    def test_a_plain_toast_hides_the_guide_link(self, window):
        window._show_info_banner("plain info")

        assert window._info_banner_link.isHidden()

    def test_success_toast_is_green_and_auto_hides(self, window):
        window._report_result("sent")

        assert window._info_banner_kind == "success"
        assert window._info_banner.property("severity") == "success"
        assert "rgba(25, 135, 84, 0.85)" in window._info_banner.styleSheet()
        assert window._info_timer.isActive()

    def test_error_is_persistent_until_dismissed(self, window):
        window._notify_error(tr("notif.error"), "boom")

        assert not window._info_timer.isActive()
        assert not window._info_banner.isHidden()

    def test_error_and_warning_survive_finish_and_new_run(self, window, monkeypatch, tmp_path):
        window._notify_error(tr("notif.error"), "boom")

        window._on_process_finished(0, "normal")
        assert window._info_banner_kind == "error"
        assert not window._info_banner.isHidden()

        monkeypatch.setattr(window._file_panel, "load_local_files", lambda *a, **k: None)
        window._prepare_engine_run(str(tmp_path))
        assert window._info_banner_kind == "error"
        assert not window._info_banner.isHidden()

    def test_engine_error_shows_in_app_even_when_notifications_disabled(self, window):
        from unittest.mock import MagicMock

        from PySide6.QtWidgets import QSystemTrayIcon

        from hsync_desktop.notifications import NotificationManager

        tray = MagicMock(spec=QSystemTrayIcon)
        tray.isVisible.return_value = True
        window._notifier = NotificationManager(tray, is_foreground=lambda: True)
        window._notifier.enabled = False

        window._engine.error_occurred.emit("boom", "process")

        assert window._info_banner_kind == "error"
        assert not window._info_banner.isHidden()

    def test_aggregated_transfer_failures_surface_one_error_toast(self, window):
        window._transfer_failure_count = 2

        window._on_process_finished(0, "normal")

        assert window._info_banner_kind == "error"
        expected = tr("notif.transfers_failed").replace("{count}", "2")
        assert expected in window._info_banner_label.text()

    def test_aggregated_transfer_failures_skipped_after_user_stop(self, window):
        window._transfer_failure_count = 2
        window._user_stopped = True

        window._on_process_finished(0, "stopped")

        assert window._info_banner.isHidden()

    def test_a_transfer_failure_shows_an_in_app_error_toast(self, window, tmp_path):
        """A failed per-file transfer is visible in-window (continuous runs never
        reach _on_process_finished), consolidated into one updated toast."""
        window._on_transfer_failed("upload", str(tmp_path / "big.bin"), "boom")

        assert window._info_banner_kind == "error"
        assert not window._info_banner.isHidden()
        assert (
            tr("notif.transfers_failed").replace("{count}", "1") in window._info_banner_label.text()
        )

        window._on_transfer_failed("upload", str(tmp_path / "other.bin"), "boom")

        assert (
            tr("notif.transfers_failed").replace("{count}", "2") in window._info_banner_label.text()
        )


class TestInFlightRowsSurviveStatusFlap:
    """A link flap keeps an in-flight transfer visible (no progress wipe)."""

    def test_upload_progress_is_kept_across_a_waiting_status(self, window, tmp_path):
        from hsync_desktop.file_panel.models import TransferStatus

        window._local_path = str(tmp_path)
        window._file_panel._table.set_base_directory(str(tmp_path))

        window._on_file_progress(str(tmp_path / "big.bin"), 262144, 6924474, "upload")
        window._on_status("waiting")

        row = window._file_panel.table._transfers["big.bin"]
        assert row.status is TransferStatus.UPLOADING

    def test_preview_status_keeps_an_in_flight_row(self, window, tmp_path):
        from hsync_desktop.file_panel.models import TransferStatus

        window._local_path = str(tmp_path)
        window._file_panel._table.set_base_directory(str(tmp_path))

        window._on_file_progress(str(tmp_path / "big.bin"), 262144, 6924474, "upload")
        window._on_file_status("synced", str(tmp_path / "big.bin"), 6924474)

        row = window._file_panel.table._transfers["big.bin"]
        assert row.status is TransferStatus.UPLOADING


class TestLogViewScrolling:
    """New log lines must not steal the user's scroll position."""

    def test_a_long_line_keeps_the_horizontal_position(self, window, qtbot):
        window.resize(900, 600)
        window.show()

        window._append_log("x" * 20_000)
        qtbot.wait(20)

        bar = window._log_view.horizontalScrollBar()
        assert bar.maximum() > 0
        assert bar.value() == 0  # left-aligned by default

        bar.setValue(10)
        window._append_log("y" * 20_000)
        qtbot.wait(20)
        assert bar.value() == 10  # the user's position is preserved

    def test_a_reader_scrolled_up_keeps_the_vertical_position(self, window, qtbot):
        window.resize(900, 600)
        window.show()
        for i in range(500):
            window._append_log(f"line {i}")
        qtbot.wait(20)

        bar = window._log_view.verticalScrollBar()
        assert bar.maximum() > 0
        bar.setValue(5)
        window._append_log("new line")
        qtbot.wait(20)

        assert bar.value() == 5


class TestInitialReconcile:
    """The first connect after the initial sync runs one real catch-up cycle."""

    @staticmethod
    def _stub(p2p: bool):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from hsync_desktop.main_window.events import EventsMixin
        from hsync_desktop.preview_summary_dialog import PreviewStats

        stub = SimpleNamespace(
            _engine=MagicMock(is_running=True),
            _file_panel=MagicMock(),
            _p2p_enabled=p2p,
            _is_master=None,  # role unknown yet: not a serving device
            _initial_reconcile_done=False,
            _pending_initial_reconcile=False,
            _awaiting_preview_for_sync=False,
            _preview_stats=PreviewStats(),
            _append_log=lambda *_a, **_k: None,
            _append_desktop_log=lambda *_a, **_k: None,
            _sync_state=("idle", 0, 0, 0),
            _sync_state_label=None,
            _set_sync_state=lambda *_a, **_k: None,
            _sync_state_after_preview=lambda: ("in_sync", 0, 0, 0),
            _device_stats={},
            _pending_inventory=None,
            _comparison_in_flight=False,
            _comparison_errored=False,
            _preparing_plan=False,
            _exit_preparing_plan_ui=lambda: None,
            _last_check_at=None,
            _peers_total=0,
            _update_menu_state=lambda: None,
        )
        # The comparison helpers stay real: the slots under test delegate to them.
        stub._begin_comparison = EventsMixin._begin_comparison.__get__(stub)
        stub._finish_comparison = EventsMixin._finish_comparison.__get__(stub)
        stub._stamp_last_check = EventsMixin._stamp_last_check.__get__(stub)
        stub._end_comparison = EventsMixin._end_comparison.__get__(stub)
        return stub

    def test_first_connect_runs_preview_then_sync(self):
        from hsync_desktop.main_window.events import EventsMixin

        stub = self._stub(p2p=True)
        EventsMixin._on_connected_refresh(stub)

        stub._engine.preview.assert_called_once()
        stub._engine.sync.assert_called_once()

    def test_the_catch_up_is_credited_only_when_the_preview_answers(self):
        """A command the client never consumed must not burn the one-shot."""
        from hsync_desktop.main_window.events import EventsMixin

        stub = self._stub(p2p=True)
        EventsMixin._on_connected_refresh(stub)
        assert stub._pending_initial_reconcile is True
        assert stub._initial_reconcile_done is False

        # A reconnect before the preview answers still asks for the catch-up.
        EventsMixin._on_connected_refresh(stub)
        assert stub._engine.sync.call_count == 2

        EventsMixin._on_preview_ended(stub)
        assert stub._initial_reconcile_done is True
        assert stub._pending_initial_reconcile is False

        # Once credited, a later reconnect only refreshes the preview.
        EventsMixin._on_connected_refresh(stub)
        assert stub._engine.preview.call_count == 3
        assert stub._engine.sync.call_count == 2

    def test_no_catch_up_in_server_mode(self):
        from hsync_desktop.main_window.events import EventsMixin

        stub = self._stub(p2p=False)
        EventsMixin._on_connected_refresh(stub)

        stub._engine.preview.assert_called_once()
        stub._engine.sync.assert_not_called()


class TestSyncingStatus:
    """The initial full sync reports "Syncing…", not "Connecting…"."""

    def test_the_syncing_status_has_its_own_label_and_colour(self, window):
        from hsync_desktop.themes import COLOR_SYNCING

        window._on_status("syncing")

        assert window._status_label.text() == tr("status.syncing")
        assert COLOR_SYNCING.name() in window._status_dot.styleSheet()


class TestPostSyncStatusRefresh:
    """A completed cycle refreshes the file statuses (self-heals a stale Local)."""

    def test_a_completed_cycle_triggers_a_preview(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from hsync_desktop.main_window.events import EventsMixin

        stub = SimpleNamespace(
            _selection_sync_active=False,
            _selection_sync_phase="run",
            _engine=MagicMock(is_running=True),
            _file_panel=MagicMock(),
        )

        EventsMixin._on_sync_completed(stub, {})

        stub._file_panel.refresh_share_size.assert_called_once()
        stub._engine.preview.assert_called_once()


class TestScanStatusRefresh:
    """A path found on disk outside the event flow triggers a preview."""

    @staticmethod
    def _stub(**overrides):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        values = {
            "_engine": MagicMock(is_running=True),
            "_connected": True,
            "_p2p_enabled": True,
            "_selection_sync_active": False,
            "_last_scan_preview_at": 0.0,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_a_new_on_disk_path_refreshes_the_statuses(self):
        from hsync_desktop.main_window.events import EventsMixin

        stub = self._stub()
        EventsMixin._on_files_added_on_disk(stub)
        stub._engine.preview.assert_called_once()

    def test_no_preview_while_disconnected_or_scoped(self):
        from hsync_desktop.main_window.events import EventsMixin

        for overrides in ({"_connected": False}, {"_selection_sync_active": True}):
            stub = self._stub(**overrides)
            EventsMixin._on_files_added_on_disk(stub)
            stub._engine.preview.assert_not_called()

    def test_the_scan_preview_is_rate_limited(self):
        """A burst of batches within the cooldown yields one extra scan."""
        from hsync_desktop.main_window.events import EventsMixin

        stub = self._stub()
        EventsMixin._on_files_added_on_disk(stub)
        stub._engine.preview.assert_called_once()

        EventsMixin._on_files_added_on_disk(stub)
        stub._engine.preview.assert_called_once()


class TestHelpMenuLinks:
    """Help menu targets are the centralised documentation constants."""

    def test_documentation_opens_the_docs_index(self, window):
        from unittest.mock import patch

        from hsync_desktop import docs_links

        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            window._open_documentation()

        open_url.assert_called_once()
        assert open_url.call_args.args[0].toString() == docs_links.DOCS_INDEX

    def test_github_opens_the_repository(self, window):
        from unittest.mock import patch

        from hsync_desktop import docs_links

        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            window._open_github()

        open_url.assert_called_once()
        assert open_url.call_args.args[0].toString() == docs_links.GITHUB_REPO


class TestMasterRoleNotification:
    """A prefer_master takeover is the expected outcome; only a real conflict warns."""

    def test_takeover_is_logged_without_a_toast(self, window):
        window._on_master_conflict("takeover", "peerCID", "10.0.0.9")

        expected = (
            tr("notif.master_takeover").replace("{cid}", "peerCID").replace("{ip}", "10.0.0.9")
        )
        log = window._log_view.toPlainText()
        assert expected in log
        assert "[desktop] INFO:" in log
        assert window._info_banner.isHidden()

    def test_conflict_lost_still_warns(self, window):
        window._on_master_conflict("conflict_lost", "peerCID", "10.0.0.9")

        assert window._info_banner_kind == "warning"
        assert not window._info_banner.isHidden()

    def test_conflict_won_still_warns(self, window):
        window._on_master_conflict("conflict_won", "peerCID", "10.0.0.9")

        assert window._info_banner_kind == "warning"
        assert not window._info_banner.isHidden()


class TestDesktopLogFormat:
    def test_desktop_line_has_the_client_layout(self, window):
        window._append_desktop_log("WARNING", "probe")

        line = window._log_view.toPlainText().splitlines()[-1]
        # Same grammar as the client: <ts> - [pid] [correlation field] LEVEL: msg
        # (the desktop has no CID, so "desktop" takes that slot).
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
            r" - \[\d+\] \[desktop\] WARNING: probe$",
            line,
        )

    def test_desktop_line_is_parseable_by_the_shared_grammar(self, window):
        from hsync_common.logger import LOG_LINE_RE

        window._append_desktop_log("ERROR", "[EVENT ERROR] boom")

        line = window._log_view.toPlainText().splitlines()[-1]
        parsed = LOG_LINE_RE.match(line)
        assert parsed is not None
        assert parsed.group("level") == "ERROR"
        assert parsed.group("message") == "[EVENT ERROR] boom"

    def test_timestamp_is_utc_like_the_client(self, window):
        from datetime import UTC, datetime

        from hsync_common.logger import LOG_LINE_RE

        window._append_desktop_log("INFO", "probe")

        line = window._log_view.toPlainText().splitlines()[-1]
        parsed = LOG_LINE_RE.match(line)
        assert parsed is not None
        # A local wall clock labelled "Z" would read hours off next to the
        # engine's own lines in the same panel.
        stamp = datetime.fromisoformat(parsed.group("timestamp"))
        assert abs((datetime.now(UTC) - stamp).total_seconds()) < 5

    def test_phase_marker_obeys_the_grammar(self, window):
        from hsync_common.logger import LOG_LINE_RE

        window._on_status_pass_started()

        line = window._log_view.toPlainText().splitlines()[-1]
        parsed = LOG_LINE_RE.match(line)
        assert parsed is not None
        assert parsed.group("level") == "INFO"
        assert parsed.group("message") == "--- Updating file status... ---"

    def test_malformed_engine_event_is_logged_under_the_desktop_identity(self, window):
        from hsync_common.logger import LOG_LINE_RE

        window._on_engine_event_error("{'event': 'peers', 'connected': 'NaN'}")

        line = window._log_view.toPlainText().splitlines()[-1]
        parsed = LOG_LINE_RE.match(line)
        assert parsed is not None
        assert parsed.group("level") == "ERROR"
        assert parsed.group("fields").endswith("[desktop] ")
        assert parsed.group("message").startswith("[EVENT ERROR] ")

    def test_selection_busy_logs_and_warns(self, window, monkeypatch):
        engine_cls = type(window._engine)
        original = engine_cls.is_running
        engine_cls.is_running = property(lambda self: True)
        try:
            window._sync_selection("file.txt", "upload-only")
        finally:
            engine_cls.is_running = original

        assert window._info_banner_kind == "info"
        assert not window._info_banner.isHidden()
        assert "[desktop] WARNING:" in window._log_view.toPlainText()

    def test_preview_with_no_actions_surfaces_an_info_result(self, window):
        window._selection_sync_active = False
        window._is_dry_run_preview = False
        window._preview_stats.reset()

        window._show_preview_summary()

        assert window._info_banner_kind == "info"
        assert not window._info_banner.isHidden()
        assert "[desktop] INFO:" in window._log_view.toPlainText()


class TestDirectoryCreatedStatus:
    def test_uses_the_trailing_slash_key(self, window, tmp_path, monkeypatch):
        window._local_path = str(tmp_path)
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            window._file_panel,
            "update_file_status",
            lambda path, status, **kwargs: captured.update(path=path, status=status),
        )

        window._on_directory_created(str(tmp_path / "newdir"))

        assert captured == {"path": "newdir/", "status": "synced"}

    def test_a_trailing_slash_is_not_duplicated(self, window, tmp_path, monkeypatch):
        window._local_path = str(tmp_path)
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            window._file_panel,
            "update_file_status",
            lambda path, status, **kwargs: captured.update(path=path, status=status),
        )

        window._on_directory_created(str(tmp_path / "newdir") + "/")

        assert captured["path"] == "newdir/"


class TestPeersLabel:
    def test_is_not_bold(self, window):
        assert window._peers_label.styleSheet() == ""


class TestShareSizeLabel:
    """The status-bar label renders the shared-folder size as ``local / total``."""

    def test_renders_dash_when_the_local_size_is_unknown(self, window):
        window._share_local_bytes = -1
        window._share_total_bytes = -1

        window._render_share_size()

        assert window._share_size_label.text() == "—"

    def test_renders_dash_when_the_total_is_unknown(self, window):
        from hsync_common.format import format_bytes

        from hsync_desktop.i18n import tr

        window._share_local_bytes = 1024
        window._share_total_bytes = -1

        window._render_share_size()

        expected = (
            tr("label.share_size_fmt")
            .replace("{local}", format_bytes(1024))
            .replace("{total}", "—")
        )
        assert window._share_size_label.text() == expected

    def test_renders_local_and_total(self, window):
        from hsync_common.format import format_bytes

        from hsync_desktop.i18n import tr

        window._share_local_bytes = 1024
        window._share_total_bytes = 4096

        window._render_share_size()

        expected = (
            tr("label.share_size_fmt")
            .replace("{local}", format_bytes(1024))
            .replace("{total}", format_bytes(4096))
        )
        assert window._share_size_label.text() == expected

    def test_folder_size_event_updates_both_values(self, window):
        from hsync_common.format import format_bytes

        window._on_folder_size(1024, 4096)

        assert window._share_local_bytes == 1024
        assert window._share_total_bytes == 4096
        assert format_bytes(4096) in window._share_size_label.text()

    def test_process_finish_clears_the_total(self, window):
        from hsync_common.format import format_bytes

        window._on_folder_size(1024, 4096)

        window._on_process_finished(0, "normal")

        assert window._share_total_bytes == -1
        assert format_bytes(4096) not in window._share_size_label.text()

    def test_scan_updates_the_local_size(self, window):
        window._file_panel._on_scan_size(2048)

        assert window._share_local_bytes == 2048

    def test_cycle_completion_rescans_the_local_size(self, window, monkeypatch):
        """A finished cycle must not leave the pre-transfer size on screen."""
        refreshes: list[str] = []
        monkeypatch.setattr(
            window._file_panel, "refresh_share_size", lambda: refreshes.append("refresh")
        )

        window._on_sync_completed({})

        assert refreshes == ["refresh"]

    def test_process_finish_rescans_the_local_size(self, window, monkeypatch):
        refreshes: list[str] = []
        monkeypatch.setattr(
            window._file_panel, "refresh_share_size", lambda: refreshes.append("refresh")
        )

        window._on_folder_size(1024, 4096)
        window._on_process_finished(0, "normal")

        assert refreshes == ["refresh"]
        assert window._share_total_bytes == -1


class _SpyWizard:
    """Stand-in for SetupWizard recording its lifecycle in the MainWindow."""

    def __init__(self, parent=None, settings=None):
        self.applied = False
        self.start_requested = False
        self.raised = 0
        self.activated = 0

    def exec(self):
        return 1

    def raise_(self):
        self.raised += 1

    def activateWindow(self):
        self.activated += 1


class TestSetupWizardIntegration:
    def _install_spy(self, monkeypatch) -> list[_SpyWizard]:
        import hsync_desktop.main_window.start as start_mod

        created: list[_SpyWizard] = []

        def factory(parent=None, settings=None):
            wizard = _SpyWizard(parent)
            created.append(wizard)
            return wizard

        monkeypatch.setattr(start_mod, "SetupWizard", factory, raising=False)
        return created

    def test_menu_action_present(self, window):
        assert window._act_setup_wizard.text() == tr("menu.setup_wizard")

    def test_open_runs_and_clears_reference(self, window, monkeypatch):
        created = self._install_spy(monkeypatch)
        monkeypatch.setattr(window, "_apply_settings_changes", lambda: None)
        window._open_setup_wizard()
        assert len(created) == 1
        assert window._setup_wizard is None

    def test_second_open_raises_existing(self, window, monkeypatch):
        created = self._install_spy(monkeypatch)
        monkeypatch.setattr(window, "_apply_settings_changes", lambda: None)
        window._open_setup_wizard()
        first = created[0]
        window._setup_wizard = first  # simulate an open dialog
        window._open_setup_wizard()
        assert len(created) == 1
        assert first.raised == 1 and first.activated == 1

    def test_running_sync_prompts_and_can_abort(self, window, monkeypatch):
        created = self._install_spy(monkeypatch)
        # A fake engine + a no-op quit keep the teardown close from prompting.
        monkeypatch.setattr(window, "_quit", lambda: None)
        monkeypatch.setattr(window, "_engine", type("_Engine", (), {"is_running": True})())
        monkeypatch.setattr(window, "_confirm_stop_sync", lambda: False)
        window._open_setup_wizard()
        assert created == []

    def test_start_requested_triggers_start(self, window, monkeypatch):
        created = self._install_spy(monkeypatch)
        started: list[bool] = []
        monkeypatch.setattr(window, "_apply_settings_changes", lambda: None)
        monkeypatch.setattr(window, "_on_start", lambda: started.append(True))

        def factory(parent=None, settings=None):
            wizard = _SpyWizard(parent)
            wizard.applied = True
            wizard.start_requested = True
            created.append(wizard)
            return wizard

        import hsync_desktop.main_window.start as start_mod

        monkeypatch.setattr(start_mod, "SetupWizard", factory, raising=False)
        window._open_setup_wizard()
        assert started == [True]

    def test_stop_confirm_has_translated_labels_and_icons(self, window):
        msg = window._build_stop_sync_dialog()
        yes = msg.button(QMessageBox.StandardButton.Yes)
        no = msg.button(QMessageBox.StandardButton.No)
        assert yes is not None and yes.text() == tr("action.yes")
        assert no is not None and no.text() == tr("action.no")
        assert not yes.icon().isNull()
        assert not no.icon().isNull()

    def test_maybe_show_opens_once_on_first_run(self, window, monkeypatch, settings):
        created = self._install_spy(monkeypatch)
        monkeypatch.setattr(window, "_apply_settings_changes", lambda: None)
        settings.remove("path/local")
        settings.setValue("wizard/auto_shown", False)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)
        window.maybe_show_setup_wizard()
        assert len(created) == 1
        assert settings.value("wizard/auto_shown", False, bool) is True

    def test_maybe_show_skips_when_configured(self, window, monkeypatch, settings):
        created = self._install_spy(monkeypatch)
        settings.setValue("path/local", "/data")
        settings.setValue("wizard/auto_shown", False)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)
        window.maybe_show_setup_wizard()
        assert created == []

    def test_placeholder_routes_to_wizard_when_unconfigured(self, window, monkeypatch):
        window._local_path = ""
        opened: list[str] = []
        monkeypatch.setattr(window, "_open_setup_wizard", lambda: opened.append("wizard"))
        monkeypatch.setattr(window, "_open_settings", lambda *a, **k: opened.append("settings"))
        window._on_path_clicked("settings")
        assert opened == ["wizard"]

    def test_placeholder_opens_settings_when_configured(self, window, monkeypatch, tmp_path):
        window._local_path = str(tmp_path)
        opened: list[str] = []
        monkeypatch.setattr(window, "_open_setup_wizard", lambda: opened.append("wizard"))
        monkeypatch.setattr(window, "_open_settings", lambda *a, **k: opened.append("settings"))
        window._on_path_clicked("settings")
        assert opened == ["settings"]


class TestResetSyncState:
    """The window runs the client's `state reset` for the folder the dialog asked for."""

    @staticmethod
    def _patch_dialogs(monkeypatch, *, warning=None, information=None):
        if warning is not None:
            monkeypatch.setattr(QMessageBox, "warning", staticmethod(warning))
        if information is not None:
            monkeypatch.setattr(QMessageBox, "information", staticmethod(information))

    def test_runs_the_client_and_logs_the_outcome(self, window, monkeypatch):
        from hsync_desktop.engine import ResetStateResult

        calls: list[tuple[str, str]] = []
        info: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: (
                calls.append((binary, folder))
                or ResetStateResult(ok=True, found=True, versions=7, tombstones=2)
            ),
        )
        self._patch_dialogs(monkeypatch, information=lambda *a: info.append(a[2]))

        window._reset_sync_state("/data/photos")

        assert calls == [(window._engine.binary_path, "/data/photos")]
        assert info == [
            tr("settings.reset_state.done").replace("{versions}", "7").replace("{tombstones}", "2")
        ]
        assert "[STATE RESET]" in window._log_view.toPlainText()

    def test_reports_an_empty_folder_as_a_noop(self, window, monkeypatch):
        from hsync_desktop.engine import ResetStateResult

        info: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: ResetStateResult(ok=True, found=False),
        )
        self._patch_dialogs(monkeypatch, information=lambda *a: info.append(a[2]))

        window._reset_sync_state("/data/photos")

        assert info == [tr("settings.reset_state.nothing")]

    def test_reports_a_quarantined_database(self, window, monkeypatch):
        from hsync_desktop.engine import ResetStateResult

        info: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: ResetStateResult(ok=True, found=True, quarantined=True),
        )
        self._patch_dialogs(monkeypatch, information=lambda *a: info.append(a[2]))

        window._reset_sync_state("/data/photos")

        assert info == [tr("settings.reset_state.quarantined")]

    def test_shows_the_client_error(self, window, monkeypatch):
        from hsync_desktop.engine import ResetStateResult

        warnings: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: ResetStateResult(
                ok=False, message="Another hsync process is already syncing '/data/photos'"
            ),
        )
        self._patch_dialogs(monkeypatch, warning=lambda *a: warnings.append(a[2]))

        window._reset_sync_state("/data/photos")

        assert warnings == ["Another hsync process is already syncing '/data/photos'"]
        assert "[STATE RESET]" in window._log_view.toPlainText()

    def test_refuses_while_a_sync_is_running(self, window, monkeypatch):
        called: list[str] = []
        warnings: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: called.append(folder),
        )
        self._patch_dialogs(monkeypatch, warning=lambda *a: warnings.append(a[2]))
        monkeypatch.setattr(type(window._engine), "is_running", property(lambda self: True))
        try:
            window._reset_sync_state("/data/photos")
        finally:
            # Teardown closes the window, which waits for a stop: restore the
            # real property first or the close would never complete.
            monkeypatch.undo()

        assert called == []
        assert warnings == [tr("settings.reset_state.stop_first")]

    def test_warns_when_no_binary_is_configured(self, window, monkeypatch):
        """A broken install (no client binary) must warn, not raise out of the slot."""
        called: list[str] = []
        warnings: list[str] = []
        monkeypatch.setattr(
            "hsync_desktop.main_window.start.reset_sync_state",
            lambda binary, folder: called.append(folder),
        )
        self._patch_dialogs(monkeypatch, warning=lambda *a: warnings.append(a[2]))
        monkeypatch.setattr(type(window._engine), "binary_path", property(lambda self: None))

        window._reset_sync_state("/data/photos")

        assert called == []
        assert warnings == [tr("settings.reset_state.failed")]


class TestSimulationModePreview:
    """Simulation Mode shows the preview and never asks the client to apply it."""

    @staticmethod
    def _spy_sync(window, monkeypatch) -> list[str]:
        sent: list[str] = []
        monkeypatch.setattr(type(window._engine), "sync", lambda self: sent.append("sync"))
        return sent

    @staticmethod
    def _answer_preview(monkeypatch, *, accepted: bool) -> None:
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        code = (
            PreviewSummaryDialog.DialogCode.Accepted
            if accepted
            else PreviewSummaryDialog.DialogCode.Rejected
        )
        monkeypatch.setattr(PreviewSummaryDialog, "exec", lambda self: int(code))

    def test_accepted_preview_is_not_applied(self, window, monkeypatch):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: True)
        self._answer_preview(monkeypatch, accepted=True)
        sent = self._spy_sync(window, monkeypatch)
        window._preview_stats.reset()
        window._preview_stats.to_upload = 2
        window._is_dry_run_preview = True

        window._show_preview_summary()

        assert sent == []
        assert window._info_banner_label.text() == tr("preview.simulation_no_changes")
        assert window._is_dry_run_preview is False

    def test_accepted_preview_is_applied_when_simulation_is_off(self, window, monkeypatch):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: False)
        self._answer_preview(monkeypatch, accepted=True)
        sent = self._spy_sync(window, monkeypatch)
        window._preview_stats.reset()
        window._preview_stats.to_download = 1
        window._is_dry_run_preview = True

        window._show_preview_summary()

        assert sent == ["sync"]

    def test_nothing_to_sync_does_not_start_a_sync_either(self, window, monkeypatch):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: True)
        sent = self._spy_sync(window, monkeypatch)
        window._preview_stats.reset()
        window._is_dry_run_preview = True

        window._show_preview_summary()

        assert sent == []
        assert window._info_banner_label.text() == tr("preview.no_actions")


class TestPreviewChanges:
    """Explicit "Preview changes": show the plan, apply only when asked."""

    @staticmethod
    def _answer(monkeypatch, *, accepted: bool) -> list[str]:
        """Answer the dialog and record the intent it was built with."""
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        seen: list[str] = []
        code = (
            PreviewSummaryDialog.DialogCode.Accepted
            if accepted
            else PreviewSummaryDialog.DialogCode.Rejected
        )

        def _exec(dialog):
            seen.append(dialog._intent)
            return int(code)

        monkeypatch.setattr(PreviewSummaryDialog, "exec", _exec)
        return seen

    @staticmethod
    def _spy_engine(window, monkeypatch) -> tuple[list, list]:
        sent: list = []
        stops: list = []
        monkeypatch.setattr(type(window._engine), "sync", lambda self: sent.append("sync"))
        monkeypatch.setattr(
            type(window._engine), "stop_and_wait", lambda self: stops.append("stop")
        )
        return sent, stops

    def test_the_action_follows_start_when_stopped_with_a_folder(self, window, tmp_path):
        window._local_path = ""
        window._update_menu_state()
        assert not window._act_preview_changes.isEnabled()

        window._local_path = str(tmp_path)
        window._update_menu_state()
        assert window._act_preview_changes.isEnabled()

        # A running or stopping engine disables it exactly like Start.
        engine_cls = type(window._engine)
        original = engine_cls.is_running
        engine_cls.is_running = property(lambda self: True)
        try:
            window._update_menu_state()
            assert not window._act_preview_changes.isEnabled()
        finally:
            engine_cls.is_running = original

        window._stop_requested = True
        window._update_menu_state()
        assert not window._act_preview_changes.isEnabled()
        window._stop_requested = False

    def test_the_action_sits_next_to_start_in_the_sync_menu(self, window):
        texts = [act.text() for act in window._menu_sync.actions() if not act.isSeparator()]

        assert texts.index(tr("menu.sync.preview")) == texts.index(tr("menu.sync.start")) + 1

    def test_the_action_carries_a_shortcut_and_a_tooltip(self, window):
        """The menu names the action; the tooltip says what it will not do.

        Without it "Preview changes" sits one row below "Start" with no visible
        difference, and the dialog it opens looks like the one a Start shows.
        QMenu hides tooltips by default, so the menu has to ask for them.
        """
        assert window._act_preview_changes.shortcut().toString() == "Ctrl+Shift+P"
        assert window._act_preview_changes.toolTip() == tr("tip.preview_changes")
        assert window._menu_sync.toolTipsVisible()

    def test_it_starts_the_dry_run_with_the_preview_intent(self, window, monkeypatch, tmp_path):
        _stop_the_deferred_timer(monkeypatch)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        monkeypatch.setattr(window, "_check_deletion_risk", lambda **_: True)
        for name in ("_check_keyless_p2p", "_check_disk_space"):
            monkeypatch.setattr(window, name, lambda: True)
        monkeypatch.setattr(window, "_ensure_trust", lambda continuation: continuation())
        started: list[str] = []
        monkeypatch.setattr(window, "_start_preview_run", lambda path: started.append(path))
        window._local_path = str(tmp_path)

        window._on_preview_changes()
        window._continue_start_after_disclaimer()

        assert started == [str(tmp_path)]
        assert window._preview_intent == "preview"

    def test_start_keeps_the_start_intent(self, window, monkeypatch, tmp_path):
        _stop_the_deferred_timer(monkeypatch)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        monkeypatch.setattr(window, "_start_preview_run", lambda path: None)
        window._local_path = str(tmp_path)

        window._on_start()

        assert window._preview_intent == "start"

    def test_the_dialog_offers_sync_now_for_a_preview_run(self, window, monkeypatch):
        seen = self._answer(monkeypatch, accepted=False)
        self._spy_engine(window, monkeypatch)
        window._preview_stats.reset()
        window._preview_stats.to_upload = 1
        window._is_dry_run_preview = True
        window._preview_intent = "preview"

        window._show_preview_summary()

        assert seen == ["preview"]

    def test_the_preparing_state_is_visible_and_ends_with_the_plan(self, window, monkeypatch):
        window._enter_preparing_plan_ui()

        assert window._preparing_plan is True
        assert window._info_banner_kind == "progress"
        assert tr("notif.preparing_plan") in window._info_banner_label.text()
        assert tr("notif.preparing_plan") in window._log_view.toPlainText()

        self._answer(monkeypatch, accepted=True)
        self._spy_engine(window, monkeypatch)
        window._preview_stats.reset()
        window._preview_stats.to_upload = 1
        window._is_dry_run_preview = True

        window._show_preview_summary()

        assert window._preparing_plan is False
        # The toast must not survive into the real sync.
        assert window._info_banner_kind is None

    def test_a_connect_keeps_the_preparing_toast(self, window):
        window._enter_preparing_plan_ui()

        window._on_status("connected")

        assert window._preparing_plan is True
        assert window._info_banner_kind == "progress"

    def test_a_preview_without_the_plan_still_ends_the_toast(self, window):
        """The dry-run phase can end without a summary: the toast must go too."""
        window._enter_preparing_plan_ui()
        window._awaiting_preview_for_sync = False

        window._on_preview_ended()

        assert window._preparing_plan is False
        assert window._info_banner_kind is None

    def test_an_empty_preview_plan_ends_the_run_without_syncing(self, window, monkeypatch):
        sent, stops = self._spy_engine(window, monkeypatch)
        window._preview_stats.reset()
        window._is_dry_run_preview = True
        window._preview_intent = "preview"

        window._show_preview_summary()

        assert sent == []
        assert stops == ["stop"]
        assert window._is_dry_run_preview is False
        assert tr("preview.no_actions") in window._info_banner_label.text()

    def test_an_accepted_preview_applies_in_the_same_session(self, window, monkeypatch):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: False)
        self._answer(monkeypatch, accepted=True)
        sent, _stops = self._spy_engine(window, monkeypatch)
        started: list[list[str]] = []
        monkeypatch.setattr(window, "_start_engine", lambda args: started.append(args) or True)
        window._preview_stats.reset()
        window._preview_stats.to_download = 1
        window._is_dry_run_preview = True
        window._preview_intent = "preview"

        window._show_preview_summary()

        assert sent == ["sync"]
        # Applying must reuse the running session: a restart would re-handshake
        # and could produce a plan different from the confirmed one.
        assert started == []


class TestAutomaticPlan:
    """An unattended run applies a plan only when it deletes nothing."""

    @staticmethod
    def _stub(window, monkeypatch, *, to_delete: int) -> tuple[list, list, list]:
        import hsync_desktop.main_window.actions as actions_module
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: False)
        opened: list = []
        monkeypatch.setattr(PreviewSummaryDialog, "exec", lambda self: opened.append(self) or 0)
        sent: list = []
        stops: list = []
        monkeypatch.setattr(type(window._engine), "sync", lambda self: sent.append("sync"))
        monkeypatch.setattr(
            type(window._engine), "stop_and_wait", lambda self: stops.append("stop")
        )
        window._preview_stats.reset()
        window._preview_stats.to_delete = to_delete
        window._preview_stats.to_upload = 1
        window._is_dry_run_preview = True
        window._start_is_automatic = True
        # The gate reads the per-dry-run origin, not the run's.
        window._dry_run_unattended = True
        return opened, sent, stops

    def test_a_plan_with_deletions_stops_and_asks_for_confirmation(self, window, monkeypatch):
        opened, sent, stops = self._stub(window, monkeypatch, to_delete=1)
        warned: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            window,
            "_notify_warning",
            lambda title, message, category="connection", **kw: warned.append(
                (title, message, category)
            ),
        )

        window._show_preview_summary()

        assert opened == []  # never a modal on an unattended run
        assert sent == []  # and nothing applied
        assert stops == ["stop"]
        # The synchronisation category, not the connection one: a user who muted
        # connection problems still needs to learn the run stopped.
        assert warned == [(tr("notif.warning"), tr("notif.plan_needs_confirmation"), "sync")]
        assert tr("notif.plan_needs_confirmation") in window._log_view.toPlainText()

    def test_a_plan_without_deletions_is_applied(self, window, monkeypatch):
        opened, sent, _stops = self._stub(window, monkeypatch, to_delete=0)
        notified: list[tuple[str, str, str]] = []

        class _Notifier:
            def info(self, title, message, category="sync"):
                notified.append((title, message, category))

        window._notifier = _Notifier()  # type: ignore[assignment]
        expected = tr("preview_summary.summary_changes").format(count=1)

        window._show_preview_summary()

        assert opened == []
        assert sent == ["sync"]
        assert window._info_banner_label.text() == expected
        # An unattended apply must reach the user while the window is in the tray.
        assert notified == [(tr("app.name"), expected, "sync")]


class TestAuthRetryPlan:
    """A dry-run restarted after a credential prompt is watched again."""

    def test_the_retried_plan_is_confirmed_not_applied(self, window, monkeypatch, tmp_path):
        import hsync_desktop.main_window.actions as actions_module
        from hsync_desktop.preview_summary_dialog import PreviewSummaryDialog

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: False)
        monkeypatch.setattr(window._file_panel, "load_local_files", lambda *a, **k: None)
        monkeypatch.setattr(window, "_start_engine", lambda args: True)
        shown: list[int] = []
        monkeypatch.setattr(
            PreviewSummaryDialog,
            "exec",
            lambda self: shown.append(1) or int(PreviewSummaryDialog.DialogCode.Rejected),
        )
        sent: list[str] = []
        monkeypatch.setattr(type(window._engine), "sync", lambda self: sent.append("sync"))
        stops: list[str] = []
        monkeypatch.setattr(
            type(window._engine), "stop_and_wait", lambda self: stops.append("stop")
        )
        # The run began unattended (auto-sync on startup) and hit an auth error.
        window._start_is_automatic = True
        window._dry_run_unattended = True
        window._local_path = str(tmp_path)

        window._retry_after_auth_fix()

        # The user just answered the credential prompt: this plan is theirs.
        assert window._dry_run_unattended is False
        assert window._preparing_plan is True

        window._preview_stats.reset()
        window._preview_stats.to_upload = 1
        window._show_preview_summary()

        assert shown == [1]  # the confirmation is offered, not skipped
        assert sent == []  # Close applies nothing
        assert stops == ["stop"]


class TestDeletionRiskGate:
    """The "File Deletion Risk" prompt only guards a run that can delete."""

    @staticmethod
    def _risky_folder(window, settings, tmp_path, name: str = "shared") -> str:
        """A non-empty folder with the one posture that can delete local files."""

        folder = tmp_path / name
        folder.mkdir()
        (folder / "file.txt").write_text("x", encoding="utf-8")
        settings.setValue("p2p/enabled", False)
        settings.setValue("sync/direction", "download-only")
        settings.setValue("sync/dry_run", False)
        settings.setValue("sync/deletion_policy", "propagate")
        window._local_path = str(folder)
        return str(folder)

    @staticmethod
    def _answer(monkeypatch, *, confirm: bool, dont_show: bool = False) -> list[QMessageBox]:
        """Answer the dialog, ticking the opt-out checkbox when asked to."""

        shown: list[QMessageBox] = []

        def fake_exec(box: QMessageBox) -> int:
            shown.append(box)
            checkbox = box.checkBox()
            if checkbox is not None:
                checkbox.setChecked(dont_show)
            answer = QMessageBox.StandardButton.Yes if confirm else QMessageBox.StandardButton.No
            return int(answer)

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        return shown

    def test_simulation_mode_skips_the_prompt(self, window, settings, monkeypatch, tmp_path):
        """--dry-run only previews, so nothing can be deleted: no confirmation."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: True)
        shown = self._answer(monkeypatch, confirm=True)

        assert window._check_deletion_risk() is True
        assert shown == []

    def test_keep_policy_skips_the_prompt(self, window, settings, monkeypatch, tmp_path):
        """Keep deleted files never removes anything: no confirmation."""
        self._risky_folder(window, settings, tmp_path)
        settings.setValue("sync/deletion_policy", "keep")
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        shown = self._answer(monkeypatch, confirm=True)

        assert window._check_deletion_risk() is True
        assert window._check_deletion_risk(interactive=False) is True
        assert shown == []

    def test_p2p_without_primary_role_does_not_prompt(
        self, window, settings, monkeypatch, tmp_path
    ):
        """Bidirectional p2p uploads the local-only files, it never deletes them."""
        folder = tmp_path / "shared"
        folder.mkdir()
        (folder / "file.txt").write_text("x", encoding="utf-8")
        settings.setValue("p2p/enabled", True)
        settings.setValue("p2p/prefer_master", False)
        settings.setValue("sync/direction", "bidirectional")
        window._local_path = str(folder)
        shown = self._answer(monkeypatch, confirm=True)

        assert window._check_deletion_risk() is True
        assert window._check_deletion_risk(interactive=False) is True
        assert shown == []

    def test_a_folder_with_only_sync_artefacts_does_not_prompt(
        self, window, settings, monkeypatch, tmp_path
    ):
        """The sentinel and the ignored entries are not data the user could lose."""
        folder = tmp_path / "shared"
        folder.mkdir()
        (folder / ".hsynckeep").write_text("", encoding="utf-8")
        (folder / "Thumbs.db").write_text("x", encoding="utf-8")
        settings.setValue("sync/direction", "download-only")
        settings.setValue("sync/dry_run", False)
        settings.setValue("sync/deletion_policy", "propagate")
        window._local_path = str(folder)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        shown = self._answer(monkeypatch, confirm=True)

        assert window._check_deletion_risk() is True
        assert shown == []

    def test_risky_configuration_still_prompts(self, window, settings, monkeypatch, tmp_path):
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        shown = self._answer(monkeypatch, confirm=True)

        assert window._check_deletion_risk() is True
        assert len(shown) == 1
        assert shown[0].windowTitle() == tr("notif.deletion_risk")
        # Silence is always an explicit act: the opt-out starts unchecked.
        checkbox = shown[0].checkBox()
        assert checkbox is not None
        assert checkbox.text() == tr("notif.deletion_risk_dont_show")
        assert checkbox.isChecked() is False
        # The Yes/No buttons use the app theme icons, not the system ones.
        from hsync_desktop.icons import icon

        yes = shown[0].button(QMessageBox.StandardButton.Yes)
        no = shown[0].button(QMessageBox.StandardButton.No)
        assert yes.icon().cacheKey() == icon("dialog-ok").cacheKey()
        assert no.icon().cacheKey() == icon("dialog-cancel").cacheKey()

    def test_declining_never_silences_the_notice(self, window, settings, monkeypatch, tmp_path):
        """Only an explicit Yes can hide the notice, whatever the checkbox says."""
        from hsync_desktop.deletion_risk import _ACK_KEY

        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        shown = self._answer(monkeypatch, confirm=False, dont_show=True)

        assert window._check_deletion_risk() is False
        assert len(shown) == 1
        assert not settings.contains(_ACK_KEY)

    def test_an_acknowledged_risk_skips_the_prompt(self, window, settings, monkeypatch, tmp_path):
        """Yes plus the checkbox silences the notice for this folder and posture."""
        from hsync_desktop.deletion_risk import _ACK_KEY

        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        self._answer(monkeypatch, confirm=True, dont_show=True)
        assert window._check_deletion_risk() is True
        assert settings.contains(_ACK_KEY)

        shown = self._answer(monkeypatch, confirm=True)
        assert window._check_deletion_risk() is True
        assert window._check_deletion_risk(interactive=False) is True
        assert shown == []

    def test_the_acknowledgement_is_scoped_to_the_folder(
        self, window, settings, monkeypatch, tmp_path
    ):
        """A share the user never confirmed asks on its own."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        self._answer(monkeypatch, confirm=True, dont_show=True)
        assert window._check_deletion_risk() is True

        self._risky_folder(window, settings, tmp_path, name="other")
        shown = self._answer(monkeypatch, confirm=True)
        assert window._check_deletion_risk() is True
        assert len(shown) == 1

    def test_a_changed_posture_asks_again(self, window, settings, monkeypatch, tmp_path):
        """The acknowledgement covers the settings it was given for, not more."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        self._answer(monkeypatch, confirm=True, dont_show=True)
        assert window._check_deletion_risk() is True

        settings.setValue("p2p/enabled", True)
        shown = self._answer(monkeypatch, confirm=True)
        assert window._check_deletion_risk() is True
        assert len(shown) == 1

    def test_a_new_notice_version_asks_again(self, window, settings, monkeypatch, tmp_path):
        """An acknowledgement never covers a wording the user did not read."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.deletion_risk as deletion_risk_module
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        self._answer(monkeypatch, confirm=True, dont_show=True)
        assert window._check_deletion_risk() is True

        monkeypatch.setattr(
            deletion_risk_module,
            "DELETION_RISK_NOTICE_VERSION",
            deletion_risk_module.DELETION_RISK_NOTICE_VERSION + 1,
        )
        shown = self._answer(monkeypatch, confirm=True)
        assert window._check_deletion_risk() is True
        assert len(shown) == 1

    def test_an_automatic_start_reports_the_risk_instead_of_prompting(
        self, window, settings, monkeypatch, tmp_path
    ):
        """A startup run must never start from a dialog nobody was asked to answer."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        _stop_the_deferred_timer(monkeypatch)
        shown = self._answer(monkeypatch, confirm=True)
        warned: list[tuple[str, str]] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda title, message: warned.append((title, message))
        )
        started: list[str] = []
        monkeypatch.setattr(window, "_start_preview_run", lambda path: started.append(path))

        window._on_auto_start()  # the startup path, flag included
        window._continue_start_after_disclaimer()  # the deferred continuation

        assert shown == []  # no blocking modal on a run the user did not trigger
        assert started == []  # and no destructive run either
        assert warned == [(tr("notif.deletion_risk"), tr("notif.deletion_risk_manual"))]
        assert tr("notif.deletion_risk_manual") in window._log_view.toPlainText()

    def test_an_acknowledged_risk_lets_the_automatic_start_preview(
        self, window, settings, monkeypatch, tmp_path
    ):
        """The acknowledgement replaces the pre-flight gate, not the per-run one."""
        self._risky_folder(window, settings, tmp_path)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        _stop_the_deferred_timer(monkeypatch)
        self._answer(monkeypatch, confirm=True, dont_show=True)
        assert window._check_deletion_risk() is True

        shown = self._answer(monkeypatch, confirm=True)
        started: list[str] = []
        monkeypatch.setattr(window, "_start_preview_run", lambda path: started.append(path))
        window._pending_sync_path = window._local_path
        window._start_is_automatic = True

        window._continue_start_after_disclaimer()

        assert shown == []
        assert started == [window._local_path]

    def test_an_automatic_start_proceeds_when_nothing_is_at_risk(
        self, window, settings, monkeypatch, tmp_path
    ):
        """Without a deletion risk the startup run follows the normal path."""
        folder = tmp_path / "shared"
        folder.mkdir()
        (folder / "file.txt").write_text("x", encoding="utf-8")
        settings.setValue("sync/direction", "bidirectional")
        window._local_path = str(folder)
        window._pending_sync_path = str(folder)
        shown = self._answer(monkeypatch, confirm=True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_trust", lambda continuation: continuation())
        started: list[str] = []
        monkeypatch.setattr(window, "_start_preview_run", lambda path: started.append(path))
        window._start_is_automatic = True

        window._continue_start_after_disclaimer()

        assert shown == []
        assert started == [str(folder)]


class TestStartupAutoSync:
    """Auto-sync on startup is opt-in: the wizard must not enable it silently."""

    @staticmethod
    def _build(qtbot, monkeypatch, settings, scheduled: list[int]):
        from hsync_desktop.engine import HsyncEngine
        from hsync_desktop.main_window import MainWindow

        _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)
        import hsync_desktop.settings.cli_args as cli_args_module

        monkeypatch.setattr(cli_args_module, "QSettings", lambda *a, **k: settings)
        _patch_all(monkeypatch, "find_hsync_binary", lambda: "/fake/hsync")
        monkeypatch.setattr(MainWindow, "_check_auto_sync", lambda self: scheduled.append(1))
        win = MainWindow(HsyncEngine(binary_path="/fake/hsync"))
        qtbot.addWidget(win)
        return win

    def test_a_disabled_setting_schedules_no_startup_run(self, qtbot, monkeypatch, settings):
        settings.setValue("sync/auto_sync", False)
        scheduled: list[int] = []

        self._build(qtbot, monkeypatch, settings, scheduled)
        qtbot.wait(50)

        assert scheduled == []

    def test_an_enabled_setting_schedules_the_startup_run(self, qtbot, monkeypatch, settings):
        settings.setValue("sync/auto_sync", True)
        scheduled: list[int] = []

        self._build(qtbot, monkeypatch, settings, scheduled)
        qtbot.waitUntil(lambda: bool(scheduled), timeout=1000)

        assert scheduled == [1]

    def test_the_automatic_origin_survives_the_deferred_start(self, window, monkeypatch, tmp_path):
        """``_on_start`` defers the run: the origin must survive that delay."""
        _stop_the_deferred_timer(monkeypatch)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        window._local_path = str(tmp_path)

        window._on_auto_start()

        assert window._start_is_automatic is True
        assert window._pending_start_automatic is False

    def test_a_manual_start_clears_a_stale_automatic_origin(self, window, monkeypatch, tmp_path):
        _stop_the_deferred_timer(monkeypatch)
        monkeypatch.setattr(window, "_show_disclaimer", lambda **_: True)
        window._local_path = str(tmp_path)
        window._start_is_automatic = True  # left over from an automatic run

        window._on_start()

        assert window._start_is_automatic is False

    def test_an_automatic_start_does_not_raise_the_disclaimer(self, window, monkeypatch, tmp_path):
        """A one-time notice must not appear on a window nobody opened."""
        _stop_the_deferred_timer(monkeypatch)
        shown: list[QMessageBox] = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self) or 0)
        warned: list[tuple[str, str]] = []
        monkeypatch.setattr(
            window, "_notify_warning", lambda title, message: warned.append((title, message))
        )
        started: list[str] = []
        monkeypatch.setattr(window, "_start_preview_run", lambda path: started.append(path))
        window._local_path = str(tmp_path)

        window._on_auto_start()

        assert shown == []
        assert started == []
        assert window._pending_sync_path == ""
        assert warned == [(tr("disclaimer.title"), tr("notif.disclaimer_manual"))]
        assert tr("notif.disclaimer_manual") in window._log_view.toPlainText()


class TestKeylessP2pPrompt:
    """The keyless-P2P confirmation uses the app theme icons too."""

    def test_yes_no_buttons_use_the_app_icons(self, window, settings, monkeypatch):
        settings.setValue("p2p/enabled", True)
        shown: list[QMessageBox] = []
        monkeypatch.setattr(
            QMessageBox,
            "exec",
            lambda self: shown.append(self) or int(QMessageBox.StandardButton.Yes),
        )

        assert window._check_keyless_p2p() is True

        assert len(shown) == 1
        assert shown[0].windowTitle() == tr("warn.keyless_p2p_title")
        from hsync_desktop.icons import icon

        yes = shown[0].button(QMessageBox.StandardButton.Yes)
        no = shown[0].button(QMessageBox.StandardButton.No)
        assert yes.icon().cacheKey() == icon("dialog-ok").cacheKey()
        assert no.icon().cacheKey() == icon("dialog-cancel").cacheKey()


class TestDeletionPolicyBadge:
    """The keep policy is visible from the main window, not only in Settings."""

    @staticmethod
    def _set_policy(monkeypatch, policy: str) -> None:
        import hsync_desktop.main_window.ui as ui_module

        monkeypatch.setattr(ui_module, "get_deletion_policy", lambda: policy)

    def test_badge_is_hidden_with_the_default_policy(self, window, monkeypatch):
        self._set_policy(monkeypatch, "propagate")
        window._refresh_deletion_badge()

        assert window._deletion_badge.isHidden()
        assert window._deletion_badge.toolTip() == ""

    def test_badge_appears_while_deletions_are_kept(self, window, monkeypatch):
        self._set_policy(monkeypatch, "keep")
        window._refresh_deletion_badge()

        assert not window._deletion_badge.isHidden()
        assert window._deletion_badge.text() == tr("deletion.badge")
        assert window._deletion_badge.toolTip() == tr("deletion.tip")

    def test_turning_the_policy_off_clears_the_badge(self, window, monkeypatch):
        self._set_policy(monkeypatch, "keep")
        window._refresh_deletion_badge()
        self._set_policy(monkeypatch, "propagate")
        window._refresh_deletion_badge()

        assert window._deletion_badge.isHidden()
        assert window._deletion_badge.toolTip() == ""

    def test_settings_save_refreshes_the_badge(self, window, monkeypatch):
        self._set_policy(monkeypatch, "propagate")
        window._refresh_deletion_badge()
        self._set_policy(monkeypatch, "keep")

        window._apply_settings_changes()

        assert not window._deletion_badge.isHidden()

    def test_the_two_badges_are_independent(self, window, monkeypatch):
        import hsync_desktop.main_window.ui as ui_module

        self._set_policy(monkeypatch, "keep")
        monkeypatch.setattr(ui_module, "is_simulation_mode", lambda: True)
        window._refresh_simulation_state()
        window._refresh_deletion_badge()

        assert not window._simulation_badge.isHidden()
        assert not window._deletion_badge.isHidden()


class TestSimulationIndicator:
    """Simulation Mode is visible from the main window, not only in Settings."""

    @staticmethod
    def _set_simulation(monkeypatch, enabled: bool) -> None:
        import hsync_desktop.main_window.ui as ui_module

        monkeypatch.setattr(ui_module, "is_simulation_mode", lambda: enabled)

    def test_badge_is_hidden_when_the_mode_is_off(self, window, monkeypatch):
        self._set_simulation(monkeypatch, False)
        window._refresh_simulation_state()

        assert window._simulation_badge.isHidden()
        assert window.windowTitle() == tr("app.name")
        assert window._btn_start.toolTip() == tr("tip.start")

    def test_badge_title_and_hints_appear_with_the_mode(self, window, monkeypatch):
        self._set_simulation(monkeypatch, True)
        window._refresh_simulation_state()

        assert not window._simulation_badge.isHidden()
        assert window._simulation_badge.text() == tr("simulation.badge")
        assert window._simulation_badge.toolTip() == tr("simulation.tip")
        assert window.windowTitle() == tr("app.name") + tr("simulation.window_title_suffix")
        assert window._btn_start.toolTip() == tr("tip.start_simulation")

    def test_turning_the_mode_off_clears_the_indicator(self, window, monkeypatch):
        self._set_simulation(monkeypatch, True)
        window._refresh_simulation_state()
        self._set_simulation(monkeypatch, False)
        window._refresh_simulation_state()

        assert window._simulation_badge.isHidden()
        assert window._simulation_badge.toolTip() == ""
        assert window.windowTitle() == tr("app.name")
        assert window._btn_start.toolTip() == tr("tip.start")

    def test_settings_save_refreshes_the_indicator(self, window, monkeypatch):
        import hsync_desktop.main_window.ui as ui_module

        self._set_simulation(monkeypatch, False)
        window._refresh_simulation_state()
        monkeypatch.setattr(ui_module, "is_simulation_mode", lambda: True)

        window._apply_settings_changes()

        assert not window._simulation_badge.isHidden()

    def test_run_start_logs_the_simulation_delimiter(self, window, monkeypatch, tmp_path):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: True)
        folder = tmp_path / "shared"
        folder.mkdir()
        window._log_view.clear()

        window._prepare_engine_run(str(folder))

        assert tr("simulation.log_start") in window._log_view.toPlainText()

    def test_run_start_has_no_delimiter_when_the_mode_is_off(self, window, monkeypatch, tmp_path):
        import hsync_desktop.main_window.actions as actions_module

        monkeypatch.setattr(actions_module, "is_simulation_mode", lambda: False)
        folder = tmp_path / "shared"
        folder.mkdir()
        window._log_view.clear()

        window._prepare_engine_run(str(folder))

        assert tr("simulation.log_start") not in window._log_view.toPlainText()


class TestColoredLog:
    """The log panel renders the client palette and recolors on a theme change."""

    @staticmethod
    def _first_line_colors(window) -> dict[str, str]:
        block = window._log_view.document().firstBlock()
        colors: dict[str, str] = {}
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.text().strip():
                colors[fragment.text()] = fragment.charFormat().foreground().color().name()
            iterator += 1
        return colors

    def test_client_sgr_is_rendered_and_stripped(self, window):
        from PySide6.QtGui import QColor

        from hsync_desktop.log_style import LOG_COLORS
        from hsync_desktop.themes import THEME_LIGHT

        window._log_view.clear()
        window._log_theme = THEME_LIGHT
        window._append_log(
            "\x1b[2m2026-10-21T14:48:07Z\x1b[0m - [1] [N/A] \x1b[33mWARNING\x1b[0m: x"
        )

        assert window._log_view.toPlainText() == "2026-10-21T14:48:07Z - [1] [N/A] WARNING: x"
        colors = self._first_line_colors(window)
        assert colors["WARNING"] == QColor(LOG_COLORS[THEME_LIGHT]["yellow"]).name()

    def test_desktop_lines_use_the_shared_categories(self, window):
        from PySide6.QtGui import QColor

        from hsync_desktop.log_style import LOG_COLORS
        from hsync_desktop.themes import THEME_LIGHT

        window._log_view.clear()
        window._log_theme = THEME_LIGHT
        window._append_log("2026-10-21T14:48:08Z - [41234] [desktop] ERROR: [EVENT ERROR] boom")

        colors = self._first_line_colors(window)
        assert colors["ERROR"] == QColor(LOG_COLORS[THEME_LIGHT]["red"]).name()

    def test_theme_change_recolors_the_existing_lines(self, window):
        from hsync_desktop.themes import THEME_DARK, THEME_LIGHT

        window._log_view.clear()
        window._log_theme = THEME_LIGHT
        window._append_log("2026-10-21T14:48:08Z - [41234] [desktop] ERROR: boom")
        light = self._first_line_colors(window)["ERROR"]

        window._log_theme = THEME_DARK
        window._rerender_log()
        dark = self._first_line_colors(window)["ERROR"]

        assert light != dark
        assert (
            window._log_view.toPlainText() == "2026-10-21T14:48:08Z - [41234] [desktop] ERROR: boom"
        )


class TestMenuFontRefresh:
    """A live font-size change must reach the menu bar and its popups."""

    def test_menu_and_popups_follow_the_resolved_font(self, window):
        bogus = QFont(window.menuBar().font())
        bogus.setPointSizeF(5.0)
        window.menuBar().setFont(bogus)
        popups = window.menuBar().findChildren(QMenu)
        for menu in popups:
            menu.setFont(bogus)

        window._refresh_menu_fonts()

        expected = ui_font().pointSizeF()
        assert window.menuBar().font().pointSizeF() == pytest.approx(expected)
        for menu in popups:
            assert menu.font().pointSizeF() == pytest.approx(expected)


class TestTableWidthFit:
    """A narrow window grows once so the file-table columns stay readable."""

    @staticmethod
    def _narrow_window_with_a_row(window, qtbot):
        """Show the window with one row, with the automatic fit suppressed."""
        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        window._table_width_fitted = True  # keep the startup fit out of the way
        table = window._file_panel.table
        table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=10, status=TransferStatus.LOCAL)
        )
        window.show()
        qtbot.wait(1)
        window.resize(window.minimumWidth(), window.minimumHeight())
        window._table_width_fitted = False
        return table

    def test_fit_grows_the_window_by_the_column_deficit(self, window, qtbot, monkeypatch):
        """The deficit comes from the columns, never from the scrollbar."""
        table = self._narrow_window_with_a_row(window, qtbot)
        monkeypatch.setattr(window, "screen", lambda: None)
        monkeypatch.setattr(
            table, "required_viewport_width", lambda: table.viewport().width() + 300
        )
        before = window.width()

        window._fit_table_width()

        assert window.width() == before + 300
        assert window._table_width_fitted is True

    def test_the_growth_is_clamped_to_the_screen(self, window, qtbot, monkeypatch):
        from types import SimpleNamespace

        table = self._narrow_window_with_a_row(window, qtbot)
        monkeypatch.setattr(
            table, "required_viewport_width", lambda: table.viewport().width() + 300
        )
        limit = window.width() + 100
        screen = SimpleNamespace(availableGeometry=lambda: SimpleNamespace(width=lambda: limit))
        monkeypatch.setattr(window, "screen", lambda: screen)

        window._fit_table_width()

        assert window.width() == limit
        assert window._table_width_fitted is True

    def test_no_deficit_marks_the_fit_done_without_resizing(self, window, qtbot, monkeypatch):
        table = self._narrow_window_with_a_row(window, qtbot)
        monkeypatch.setattr(window, "screen", lambda: None)
        monkeypatch.setattr(table, "required_viewport_width", lambda: table.viewport().width())
        before = window.size().toTuple()

        window._fit_table_width()

        assert window.size().toTuple() == before
        assert window._table_width_fitted is True

    def test_an_empty_table_keeps_the_fit_retryable(self, window, qtbot):
        """Measuring before the share is loaded must not consume the fit."""
        window._table_width_fitted = True
        window.show()
        qtbot.wait(1)
        window._table_width_fitted = False
        window._file_panel.table.clear_transfers()

        window._fit_table_width()

        assert window._table_width_fitted is False

    def test_a_hidden_window_keeps_the_fit_retryable(self, window, monkeypatch):
        """A fit measured before the window is shown cannot be trusted."""
        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        window._table_width_fitted = True
        window._file_panel.table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=10, status=TransferStatus.LOCAL)
        )
        window._table_width_fitted = False
        before = window.width()

        window._fit_table_width()

        assert window.width() == before
        assert window._table_width_fitted is False

    def test_a_maximized_window_is_left_alone(self, window, qtbot, monkeypatch):
        self._narrow_window_with_a_row(window, qtbot)
        monkeypatch.setattr(window, "isMaximized", lambda: True)
        before = window.width()

        window._fit_table_width()

        assert window.width() == before
        assert window._table_width_fitted is False


class TestSyncState:
    """The bottom bar answers "are my files in sync?" separately from the link."""

    def test_a_new_link_asks_for_a_comparison(self, window):
        window._on_status("connected")

        assert window._sync_state_label.text() == tr("sync.state.checking")

    def test_a_running_preview_reads_checking(self, window):
        window._on_preview_started()

        assert window._sync_state_label.text() == tr("sync.state.checking")

    def test_an_all_synced_preview_reads_in_sync(self, window):
        window._on_preview_started()
        window._preview_stats.synced = 4

        window._on_preview_ended()

        assert window._sync_state_label.text() == tr("sync.state.in_sync")

    def test_pending_transfers_are_counted(self, window):
        window._on_preview_started()
        window._preview_stats.to_download = 2
        window._preview_stats.to_upload = 1

        window._on_preview_ended()

        expected = tr("sync.state.pending").replace("{download}", "2").replace("{upload}", "1")
        assert window._sync_state_label.text() == expected

    def test_only_deletes_and_renames_read_as_pending_changes(self, window):
        window._on_preview_started()
        window._preview_stats.to_delete = 1
        window._preview_stats.to_rename = 2

        window._on_preview_ended()

        expected = tr("sync.state.pending_other").replace("{count}", "3")
        assert window._sync_state_label.text() == expected

    def test_a_lone_device_has_nothing_to_compare(self, window):
        window._p2p_enabled = True

        window._on_peers(1, 1)

        assert window._sync_state_label.text() == tr("sync.state.no_devices")

    def test_the_client_reporting_no_device_sets_the_label(self, window):
        window._on_no_peers("no device")

        assert window._sync_state_label.text() == tr("sync.state.no_devices")

    def test_no_devices_survives_the_preview_it_closes(self, window):
        """``no_peers`` is followed by `preview_end`: the reason must not be lost."""
        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        window._file_panel.table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=1, status=TransferStatus.LOCAL)
        )
        window._on_preview_started()
        window._on_no_peers("no device")

        window._on_preview_ended()

        assert window._sync_state_label.text() == tr("sync.state.no_devices")

    def test_a_joined_device_waits_for_its_inventory(self, window):
        """A preview that classifies nothing is not "in sync"."""
        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        window._p2p_enabled = True
        window._file_panel.table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=1, status=TransferStatus.LOCAL)
        )
        window._on_peers(1, 1)
        window._on_peers(2, 2)

        assert window._sync_state_label.text() == tr("sync.state.checking")

        window._on_preview_started()
        window._on_preview_ended()

        assert window._sync_state_label.text() == tr("sync.state.checking")

    def test_a_connected_device_without_inventory_reads_waiting_inventory(self, window):
        """A device that has not published its inventory is "waiting", not "no device"."""
        window._on_sync_pending("awaiting_inventory")

        assert window._sync_state[0] == "waiting_inventory"
        assert window._sync_state_label.text() == tr("sync.state.waiting_inventory")

    def test_no_device_pending_reads_no_devices(self, window):
        window._on_sync_pending("no_device")

        assert window._sync_state[0] == "no_devices"
        assert window._sync_state_label.text() == tr("sync.state.no_devices")

    def test_a_dropped_link_keeps_the_last_known_file_status(self, window):
        """Losing the link makes the comparison stale; it does not reset rows to Local."""
        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        window._on_status("connected")
        window._file_panel.table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=4, status=TransferStatus.SYNCED)
        )

        window._on_status("disconnected")

        assert window._file_panel.table._transfers["a.bin"].status is TransferStatus.SYNCED
        assert window._sync_state[0] == "offline"
        assert window._sync_state_label.text() == tr("sync.state.offline")

    def test_a_lost_link_clears_the_state(self, window):
        window._on_preview_started()

        window._on_status("disconnected")

        assert window._sync_state_label.text() == tr("sync.state.idle")

    def test_a_language_change_rerenders_the_state(self, window):
        import hsync_desktop.i18n as i18n
        from hsync_desktop.locales import de

        window._on_preview_started()
        previous = i18n.get_language()
        try:
            i18n.set_language("de")
            window._apply_translations()
            assert window._sync_state_label.text() == de.translations["sync.state.checking"]
        finally:
            i18n.set_language(previous)

    def test_a_serving_device_classification_is_rendered(self, window):
        """A primary node answers with the per-device rows of its pass."""
        window._p2p_enabled = True
        window._on_status("connected")

        window._on_status_pass_started()
        assert window._sync_state_label.text() == tr("sync.state.checking")
        window._on_device_status("A" * 21, 0, 0, 1)
        window._on_file_status("synced", "/share/a.bin", 4)
        window._on_status_pass_ended()

        assert window._sync_state_label.text() == tr("sync.state.in_sync")


class TestDryRunSyncRetry:
    """The SYNC that ends the initial dry-run is retried until the link is up."""

    def test_nothing_to_sync_keeps_the_phase_armed(self, window, monkeypatch):
        """A SYNC written while the client served as master is not lost."""
        from unittest.mock import MagicMock

        sync = MagicMock()
        monkeypatch.setattr(window._engine, "sync", sync)
        window._is_dry_run_preview = True
        window._awaiting_preview_for_sync = True

        window._show_preview_summary()

        assert sync.call_count == 1
        assert window._is_dry_run_preview is True
        assert window._awaiting_preview_for_sync is True

        # The next preview of the same phase sends it again.
        window._show_preview_summary()
        assert sync.call_count == 2

        # A live link ends the phase: no further retry.
        window._on_status("connected")
        assert window._is_dry_run_preview is False
        assert window._awaiting_preview_for_sync is False
        window._show_preview_summary()
        assert sync.call_count == 2


class TestFileMenuCopyPath:
    """The copy-path commands are in the File menu, with conventional keys."""

    def test_the_copy_actions_are_grouped_in_the_file_menu(self, window):
        texts = [a.text() for a in window._menu_file.actions() if not a.isSeparator()]

        assert texts.index(tr("menu.file.copy_to")) + 1 == texts.index(tr("menu.file.copy_path"))
        assert texts.index(tr("menu.file.copy_path")) + 1 == texts.index(
            tr("menu.file.copy_path_relative")
        )
        assert texts.index(tr("menu.file.copy_path_relative")) + 1 == texts.index(
            tr("menu.file.rename")
        )
        # "Open containing folder" follows Open; Properties stays last.
        assert texts.index(tr("menu.file.open")) + 1 == texts.index(tr("menu.file.open_containing"))
        assert texts[-1] == tr("menu.file.properties")

    def test_the_shortcuts_follow_the_platform_conventions(self, window):
        from PySide6.QtGui import QKeySequence

        assert window._act_file_copy_path.shortcut().toString() == "Ctrl+Shift+C"
        assert window._act_file_copy_path_relative.shortcut().isEmpty()
        assert window._act_file_copy_to.shortcut().toString() == "Ctrl+Alt+C"
        assert window._act_file_properties.shortcut().toString() == "Alt+Return"
        assert window._act_help_docs.shortcut().toString() == "F1"

        open_keys = {shortcut.toString() for shortcut in window._act_file_open.shortcuts()}
        assert open_keys == {"Return", "Ctrl+O"}
        assert window._act_file_open_with.shortcut().isEmpty()

        # Platform-native chords: Qt maps them to Cmd on macOS and keeps the
        # conventional Ctrl chord when the platform theme reports no binding.
        assert {s.toString() for s in window._act_settings.shortcuts()} == {"Ctrl+,"}
        assert {s.toString() for s in window._act_quit.shortcuts()} == {"Ctrl+Q"}

    def test_copy_path_writes_the_selected_row(self, window):
        import os

        from PySide6.QtGui import QGuiApplication

        from hsync_desktop.file_panel.models import FileTransfer, TransferStatus

        table = window._file_panel.table
        table.set_base_directory("/share")
        # A root-level file: a nested path would add a folder row above it.
        table.add_transfer(
            FileTransfer(filepath="report.bin", direction="—", size=1, status=TransferStatus.LOCAL)
        )
        table._last_selected_row = 0

        window._set_file_menu_enabled(True)
        assert window._act_file_copy_path.isEnabled()
        assert window._act_file_copy_path_relative.isEnabled()
        assert window._act_file_open_containing.isEnabled()

        window._menu_file_copy_path()
        assert QGuiApplication.clipboard().text() == os.path.normpath("/share/report.bin")

        window._menu_file_copy_path_relative()
        assert QGuiApplication.clipboard().text() == os.path.normpath("report.bin")


class TestServingSideClassification:
    """A serving node answers a refresh with its own pass, not the preview cycle."""

    def test_a_status_pass_never_consumes_the_confirmation(self, window, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(window, "_show_preview_summary", lambda: calls.append("summary"))
        window._p2p_enabled = True
        window._is_master = True
        window._awaiting_preview_for_sync = True
        window._pending_initial_reconcile = True

        window._on_status_pass_started()
        window._on_device_status("A" * 21, 0, 3, 0)
        window._on_status_pass_ended()

        assert calls == []
        assert window._awaiting_preview_for_sync is True
        assert window._pending_initial_reconcile is True
        # The label still follows the pass.
        assert window._sync_state[0] == "pending"

    def test_the_preview_cycle_consumes_the_confirmation(self, window, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(window, "_show_preview_summary", lambda: calls.append("summary"))
        window._p2p_enabled = True
        window._is_master = False
        window._awaiting_preview_for_sync = True
        window._pending_initial_reconcile = True

        window._on_preview_ended()

        assert calls == ["summary"]
        assert window._awaiting_preview_for_sync is False
        assert window._pending_initial_reconcile is False

    def test_the_devices_restart_at_every_pass(self, window):
        """A device that left must not keep its backlog from a previous pass."""
        window._p2p_enabled = True

        window._on_status_pass_started()
        window._on_device_status("A" * 21, 0, 2, 0)
        window._on_status_pass_ended()
        assert window._sync_state[0] == "pending"

        window._on_status_pass_started()  # the device left: no row this time
        window._on_status_pass_ended()

        assert window._sync_state_label.text() == tr("sync.state.no_devices")


class TestPerDeviceSyncState:
    """The bar reports the device furthest behind, never a set union."""

    def test_the_worst_device_sets_the_counts(self, window):
        window._on_status_pass_started()
        window._on_device_status("A" * 21, 0, 1, 4)
        window._on_device_status("B" * 21, 2, 4, 4)
        window._on_status_pass_ended()

        expected = tr("sync.state.pending").replace("{download}", "2").replace("{upload}", "4")
        assert window._sync_state_label.text() == expected

    def test_every_device_converged_reads_in_sync(self, window):
        window._on_status_pass_started()
        window._on_device_status("A" * 21, 0, 0, 4)
        window._on_device_status("B" * 21, 0, 0, 7)
        window._on_status_pass_ended()

        assert window._sync_state_label.text() == tr("sync.state.in_sync")

    def test_the_tooltip_names_every_device(self, window):
        window._on_status_pass_started()
        window._on_device_status("A" * 21, 0, 1, 4)
        window._on_device_status("B" * 21, 2, 0, 4)
        window._on_status_pass_ended()

        tooltip = window._sync_state_label.toolTip()
        assert tooltip.startswith(tr("tip.sync_state"))
        assert "A" * 8 in tooltip and "B" * 8 in tooltip
        assert "↓ 2" in tooltip and "↑ 1" in tooltip

    def test_the_waiting_state_names_the_inventory_gap(self, window):
        from hsync_desktop.i18n import tr as translate

        window._on_sync_pending("awaiting_inventory", 1, 2)

        assert window._sync_state[0] == "waiting_inventory"
        assert f"{translate('label.peers')} 1/2" in window._sync_state_label.toolTip()

    def test_a_partially_synced_row_states_its_coverage(self, window):
        """A file only some devices hold is not plain "Synced"."""
        from hsync_desktop.file_panel.models import TransferStatus

        table = window._file_panel.table
        table.set_connected(True)
        window._on_file_status("synced", "/share/a.bin", 4, holders=2, devices=3)

        row = table._transfers["/share/a.bin"]
        text, status = table.model()._row_status(row, None, False)
        assert status is TransferStatus.SYNCED
        assert text == f"{tr('detail.synced')} · 2/3"

    def test_a_fully_covered_row_stays_plain_synced(self, window):
        table = window._file_panel.table
        table.set_connected(True)
        window._on_file_status("synced", "/share/a.bin", 4, holders=3, devices=3)

        row = table._transfers["/share/a.bin"]
        text, _status = table.model()._row_status(row, None, False)
        assert text == tr("detail.synced")


class TestCheckChangesAction:
    """Refresh asks the engine for a comparison, in both roles."""

    @staticmethod
    @contextmanager
    def _running_engine(window, preview=None):
        """A running engine, restored on exit so teardown cannot prompt.

        ``closeEvent`` asks for confirmation while the engine reports a running
        sync: a fake that outlives the test would block the widget teardown.
        """
        from unittest.mock import MagicMock, patch

        spy = preview or MagicMock()
        with (
            patch.object(window._engine, "preview", spy),
            patch.object(type(window._engine), "is_running", property(lambda self: True)),
        ):
            yield spy

    def test_the_action_is_available_while_the_engine_runs(self, window):
        with self._running_engine(window):
            window._enter_running_ui()

            assert window._btn_check_changes.isEnabled()
            assert window._act_check_changes.isEnabled()

        window._reset_ui_stopped()

        assert not window._btn_check_changes.isEnabled()
        assert not window._act_check_changes.isEnabled()

    def test_a_serving_device_refresh_asks_for_a_classification(self, window):
        window._p2p_enabled = True
        window._is_master = True
        window._connected = True
        window._awaiting_preview_for_sync = False

        with self._running_engine(window) as preview:
            window._on_check_changes()

            assert preview.call_count == 1
            # No summary dialog: there is nothing for the serving device to pull.
            assert window._awaiting_preview_for_sync is False

    def test_a_secondary_refresh_arms_the_sync_confirmation(self, window):
        window._p2p_enabled = True
        window._is_master = False
        window._connected = True

        with self._running_engine(window) as preview:
            window._on_check_changes()

            assert preview.call_count == 1
            assert window._awaiting_preview_for_sync is True

    def test_a_refresh_while_stopped_only_logs(self, window, monkeypatch):
        from unittest.mock import MagicMock

        preview = MagicMock()
        monkeypatch.setattr(window._engine, "preview", preview)

        window._on_check_changes()

        assert preview.call_count == 0

    def test_a_click_without_a_link_explains_instead_of_failing(self, window):
        """A PREVIEW before the link exists can only fail, and its end marker
        would read as "everything in sync": answer the click instead."""
        window._connected = False
        window._awaiting_preview_for_sync = False

        with self._running_engine(window) as preview:
            window._on_check_changes()

            assert preview.call_count == 0
            assert window._awaiting_preview_for_sync is False
            assert window._info_banner.isHidden() is False
            assert tr("tip.check_changes_waiting") in window._log_view.toPlainText()

    def test_a_comparison_in_flight_disables_the_action(self, window):
        """A click must not queue a second full scan behind the running one."""
        with self._running_engine(window):
            window._enter_running_ui()
            window._on_preview_started()

            assert not window._btn_check_changes.isEnabled()
            assert not window._act_check_changes.isEnabled()

            window._on_preview_ended()

            assert window._btn_check_changes.isEnabled()
            assert window._act_check_changes.isEnabled()

        window._reset_ui_stopped()

    def test_a_serving_pass_disables_and_re_enables_the_action(self, window):
        """The serving-side pair owns the same window as a requester preview."""
        with self._running_engine(window):
            window._enter_running_ui()
            window._on_status_pass_started()

            assert not window._btn_check_changes.isEnabled()

            window._on_status_pass_ended()

            assert window._btn_check_changes.isEnabled()

        window._reset_ui_stopped()

    def test_a_dead_engine_cannot_leave_the_action_disabled(self, window):
        with self._running_engine(window):
            window._enter_running_ui()
            window._on_preview_started()

        window._on_process_finished(0, "stopped")

        assert not window._comparison_in_flight
        assert not window._btn_check_changes.isEnabled()

    def test_the_tooltip_names_the_last_check(self, window):
        window._connected = True
        window._on_preview_started()
        window._on_preview_ended()

        assert window._last_check_at is not None
        last = tr("tip.check_changes_last").split("{time}")[0]
        assert last in window._btn_check_changes.toolTip()

    def test_a_failed_comparison_is_not_a_last_check(self, window):
        window._connected = True
        window._on_preview_started()
        window._on_engine_error("preview failed")

        window._on_preview_ended()

        assert window._last_check_at is None

    def test_a_lone_device_is_not_reported_as_in_sync(self, window):
        """Nothing was compared, so the result must not claim "everything in sync"."""
        window._preview_stats.reset()
        window._p2p_enabled = True
        window._on_peers(1, 1)

        window._show_preview_summary()

        assert window._info_banner_label.text() == tr("check_changes.no_devices")

    def test_a_failed_preview_opens_no_summary(self, window, monkeypatch):
        """The error already surfaced: a plan that was never computed is not offered."""
        calls: list[str] = []
        monkeypatch.setattr(window, "_show_preview_summary", lambda: calls.append("summary"))
        window._awaiting_preview_for_sync = True
        window._pending_initial_reconcile = True
        window._is_dry_run_preview = False

        window._on_preview_started()
        window._on_engine_error("preview failed")
        window._on_preview_ended()

        assert calls == []
        assert window._awaiting_preview_for_sync is False
        # A failed preview is not an answer: the catch-up is not burned.
        assert window._pending_initial_reconcile is True
        assert window._last_check_at is None

    def test_the_button_is_icon_only_with_an_explanatory_tooltip(self, window):
        """The action-bar button is icon-only, so the tooltip has to explain the action."""
        assert window._btn_check_changes.text() == ""
        assert not window._btn_check_changes.icon().isNull()
        # Idle: the tooltip says when the check can run, names the shortcut and
        # points at the action that shows a plan while the app is stopped.
        tooltip = window._btn_check_changes.toolTip()
        assert tooltip.startswith(tr("tip.check_changes_waiting"))
        assert tr("tip.check_changes_preview_hint") in tooltip
        assert "F5" in tooltip

    def test_the_waiting_hint_stays_out_of_the_click_toast(self, window):
        """The pointer belongs to the tooltip: a toast must stay a short message."""
        window._connected = False

        with self._running_engine(window):
            window._on_check_changes()

        assert window._info_banner_label.text() == tr("tip.check_changes_waiting")

    def test_the_stopped_hint_is_not_offered_while_a_run_starts(self, window):
        """While starting, Preview changes is greyed out: do not advertise it."""
        window._connected = False

        with self._running_engine(window):
            window._update_check_changes_tooltip()

            tooltip = window._btn_check_changes.toolTip()
            assert tr("tip.check_changes_preview_hint") not in tooltip


class TestStoppingFeedback:
    """Stop is non-blocking and visible at once (no frozen window)."""

    @pytest.fixture(autouse=True)
    def _tray(self, window):
        """Tray stub that keeps ``MainWindow.closeEvent`` on the minimise branch.

        These tests mark the engine running to reach the stopping state; without
        a tray, pytest-qt closing the window at teardown would take the quit path
        and block on its modal confirmation dialog.
        """

        class _Tray:
            def hide(self) -> None:
                pass

            def isVisible(self) -> bool:
                return True

            def set_window_visible(self, _visible: bool) -> None:
                pass

            def update_status(self, _status: str) -> None:
                pass

            def set_running(self, _running: bool) -> None:
                pass

            def set_stopping(self) -> None:
                pass

            def set_start_enabled(self, _enabled: bool) -> None:
                pass

            def set_check_changes_enabled(self, _enabled: bool) -> None:
                pass

        tray = _Tray()
        window._tray = tray  # type: ignore[assignment]
        return tray

    @staticmethod
    def _running(window, monkeypatch) -> list[int]:
        window._local_path = "/some/share"
        window._engine._running = True
        requested: list[int] = []
        monkeypatch.setattr(window._engine, "request_stop", lambda: requested.append(1))
        return requested

    def test_stop_shows_the_stopping_state_immediately(self, window, monkeypatch):
        requested = self._running(window, monkeypatch)

        window._on_stop()

        assert requested == [1]
        assert window._status_label.text() == tr("status.stopping")
        assert not window._btn_stop.isEnabled()
        assert not window._btn_start.isEnabled()
        assert not window._btn_check_changes.isEnabled()
        assert not window._info_banner.isHidden()
        assert tr("status.stopping") in window._log_view.toPlainText()

    def test_a_second_stop_while_stopping_is_ignored(self, window, monkeypatch):
        requested = self._running(window, monkeypatch)

        window._on_stop()
        window._on_stop()

        assert requested == [1]

    def test_process_finished_leaves_the_stopping_state(self, window, monkeypatch):
        from PySide6.QtCore import QProcess

        self._running(window, monkeypatch)
        window._on_stop()
        window._engine._stopping = True

        # The engine reports the exit before the window slot runs.
        window._engine._on_finished(0, QProcess.ExitStatus.NormalExit)

        assert window._stop_requested is False
        assert window._status_label.text() == tr("status.disconnected")
        assert window._btn_start.isEnabled()
        assert window._info_banner.isHidden()  # the progress toast is run-scoped

    def test_stop_timeout_restores_the_ui_with_a_warning(self, window, monkeypatch):
        self._running(window, monkeypatch)
        window._on_stop()

        # The kill escalation produced no "finished": the engine declares it.
        window._engine._on_stop_safety_elapsed()

        assert window._stop_requested is False
        assert window._status_label.text() == tr("status.disconnected")
        assert window._btn_start.isEnabled()
        assert not window._btn_stop.isEnabled()
        assert not window._info_banner.isHidden()
        assert tr("notif.stop_timeout") in window._log_view.toPlainText()

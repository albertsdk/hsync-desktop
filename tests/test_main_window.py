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
        monkeypatch.setattr(window, "_check_deletion_risk", lambda: True)
        monkeypatch.setattr(window, "_check_keyless_p2p", lambda: True)
        monkeypatch.setattr(window, "_check_disk_space", lambda: True)
        monkeypatch.setattr(window, "_ensure_bootnode_trust", lambda: True)
        monkeypatch.setattr(window, "_ensure_server_trust", lambda: True)
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

    def test_icon_only_before_the_election(self, window, monkeypatch, tmp_path):
        s = _settings(tmp_path)
        s.setValue("p2p/enabled", True)
        _patch_all(monkeypatch, "QSettings", lambda *a, **k: s)
        window._local_path = str(tmp_path)

        window._update_path_display()

        assert not window._role_icon.isHidden()
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
            "_ensure_bootnode_trust",
            "_ensure_server_trust",
        ):
            monkeypatch.setattr(window, name, lambda: True)

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

        window._show_info_banner("done", kind="outcome")
        assert window._info_progress.isHidden()

    def test_outcome_survives_process_finish(self, window):
        window._show_info_banner("done", kind="outcome")

        window._on_process_finished(0, "normal")

        assert not window._info_banner.isHidden()

    def test_progress_is_cleared_on_process_finish(self, window):
        window._show_info_banner("working", kind="progress")

        window._on_process_finished(0, "normal")

        assert window._info_banner.isHidden()

    def test_a_new_run_clears_the_toast(self, window, monkeypatch, tmp_path):
        window._show_info_banner("done", kind="outcome")
        monkeypatch.setattr(window._file_panel, "load_local_files", lambda *a, **k: None)

        window._prepare_engine_run(str(tmp_path))

        assert window._info_banner.isHidden()


class TestDesktopLogFormat:
    def test_desktop_line_uses_the_client_timestamp_shape(self, window):
        import re

        window._append_desktop_log("WARNING", "probe")

        line = window._log_view.toPlainText().splitlines()[-1]
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z - \[desktop\] WARNING: probe$",
            line,
        )

    def test_selection_busy_logs_and_warns(self, window, monkeypatch):
        engine_cls = type(window._engine)
        original = engine_cls.is_running
        engine_cls.is_running = property(lambda self: True)
        try:
            window._sync_selection("file.txt", "upload-only")
        finally:
            engine_cls.is_running = original

        assert window._info_banner_kind == "warning"
        assert not window._info_banner.isHidden()
        assert "[desktop] WARNING:" in window._log_view.toPlainText()

    def test_preview_with_no_actions_surfaces_an_outcome(self, window):
        window._selection_sync_active = False
        window._is_dry_run_preview = False
        window._preview_stats.reset()

        window._show_preview_summary()

        assert window._info_banner_kind == "outcome"
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

        window._on_sync_completed()

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


class TestDeletionRiskGate:
    """The "File Deletion Risk" prompt only guards a run that can delete."""

    @staticmethod
    def _risky_folder(window, settings, tmp_path) -> str:
        """A non-empty folder with the p2p configuration that risks deletions."""

        folder = tmp_path / "shared"
        folder.mkdir()
        (folder / "file.txt").write_text("x", encoding="utf-8")
        settings.setValue("p2p/enabled", True)
        settings.setValue("p2p/prefer_master", False)
        settings.setValue("sync/direction", "bidirectional")
        window._local_path = str(folder)
        return str(folder)

    def test_simulation_mode_skips_the_prompt(self, window, settings, monkeypatch, tmp_path):
        """--dry-run only previews, so nothing can be deleted: no confirmation."""
        self._risky_folder(window, settings, tmp_path)
        settings.setValue("sync/dry_run", True)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: True)
        shown: list[QMessageBox] = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self) or 0)

        assert window._check_deletion_risk() is True
        assert shown == []

    def test_risky_configuration_still_prompts(self, window, settings, monkeypatch, tmp_path):
        self._risky_folder(window, settings, tmp_path)
        settings.setValue("sync/dry_run", False)
        import hsync_desktop.main_window.start as start_module

        monkeypatch.setattr(start_module, "is_simulation_mode", lambda: False)
        shown: list[QMessageBox] = []
        monkeypatch.setattr(
            QMessageBox,
            "exec",
            lambda self: shown.append(self) or int(QMessageBox.StandardButton.Yes),
        )

        assert window._check_deletion_risk() is True
        assert len(shown) == 1
        assert shown[0].windowTitle() == tr("notif.deletion_risk")


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
        assert window._btn_start.toolTip() == tr("btn.start")

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
        assert window._btn_start.toolTip() == tr("btn.start")

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

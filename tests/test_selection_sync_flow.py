# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Scoped Send/Receive outcome flow.

A user-invoked "Send now" / "Receive now" is a one-shot whose result is
surfaced exactly once: a modal dialog when the window is focused, an OS
notification otherwise, or a transient banner for non-critical results.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from hsync_desktop.i18n import tr


class _FakeNotifier:
    """Records NotificationManager calls without touching the OS."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def info(self, title: str, message: str) -> None:
        self.calls.append(("info", title, message))

    def warning(self, title: str, message: str) -> None:
        self.calls.append(("warning", title, message))

    def error(self, title: str, message: str) -> None:
        self.calls.append(("error", title, message))

    def connection_lost(self) -> None:
        self.calls.append(("connection_lost",))

    def peer_joined(self, connected: int, total: int) -> None:
        self.calls.append(("peer_joined", connected, total))


def _arm(window, direction: str = "upload-only", phase: str = "preview") -> None:
    """Put the window into an active scoped-op state."""
    window._selection_sync_active = True
    window._selection_sync_phase = phase
    window._selection_result_count = 0
    window._pending_selection_sync = ("media", direction)


def _capture_important(monkeypatch, window) -> list[tuple]:
    recorded: list[tuple] = []
    monkeypatch.setattr(
        window,
        "_important_selection_outcome",
        lambda title, message: recorded.append((title, message)),
    )
    return recorded


def _capture_info(monkeypatch, window) -> list[str]:
    recorded: list[str] = []
    monkeypatch.setattr(window, "_info_selection_outcome", lambda message: recorded.append(message))
    return recorded


def _count_dialogs(monkeypatch) -> list[QMessageBox]:
    shown: list[QMessageBox] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self) or 0)
    return shown


class TestProgressBanner:
    def test_begin_shows_a_persistent_banner(self, window):
        window._begin_selection_sync("media", "upload-only")

        assert window._selection_sync_active is True
        assert not window._info_banner.isHidden()
        # p2p is enabled in the test settings → the search phase text.
        assert window._info_banner_label.text() == tr("sync.sel_search")

    def test_peers_update_shows_the_other_device_count(self, window):
        _arm(window)

        window._on_peers(2, 3)

        assert window._info_banner_label.text() == tr("sync.sel_peers_fmt").replace("{count}", "2")

    def test_a_lone_peer_keeps_the_searching_banner(self, window):
        window._begin_selection_sync("media", "upload-only")

        window._on_peers(1, 1)

        # No other device to name yet: keep the phase text, don't say "0 devices".
        assert window._info_banner_label.text() == tr("sync.sel_search")

    def test_connected_during_a_scoped_op_keeps_the_banner(self, window, monkeypatch):
        _arm(window)
        hidden: list[int] = []
        monkeypatch.setattr(window, "_hide_info_banner", lambda: hidden.append(1))
        previewed: list[int] = []
        monkeypatch.setattr(window._engine, "preview", lambda: previewed.append(1))
        engine_cls = type(window._engine)
        original = engine_cls.is_running
        engine_cls.is_running = property(lambda self: True)
        try:
            window._on_status("connected")
        finally:
            engine_cls.is_running = original

        assert hidden == []
        assert previewed == []


class TestImportantOutcomes:
    def test_no_devices_shows_a_dialog_when_focused(self, window, monkeypatch):
        notifier = _FakeNotifier()
        window._notifier = notifier
        monkeypatch.setattr(window, "_is_window_foreground", lambda: True)
        shown = _count_dialogs(monkeypatch)
        _arm(window)

        window._on_no_peers("No other device was found")

        assert len(shown) == 1
        assert shown[0].informativeText() == tr("sync.sel_no_devices_msg")
        assert notifier.calls == []
        assert window._selection_sync_active is False

    def test_no_devices_notifies_when_in_the_background(self, window, monkeypatch):
        notifier = _FakeNotifier()
        window._notifier = notifier
        monkeypatch.setattr(window, "_is_window_foreground", lambda: False)
        _arm(window)

        window._on_no_peers("No other device was found")

        assert notifier.calls == [
            ("warning", tr("sync.sel_no_devices_title"), tr("sync.sel_no_devices_msg"))
        ]

    def test_connection_error_in_server_mode_reports_unreachable(
        self, window, monkeypatch, settings
    ):
        settings.setValue("p2p/enabled", False)
        monkeypatch.setattr(window, "_is_window_foreground", lambda: False)
        notifier = _FakeNotifier()
        window._notifier = notifier
        _arm(window)

        window._on_engine_error("Could not reach the server", "connection")

        assert notifier.calls[0][0] == "warning"
        assert notifier.calls[0][1] == tr("sync.sel_server_unreachable_title")

    def test_a_connection_error_in_p2p_mode_stays_generic(self, window, monkeypatch):
        recorded = _capture_important(monkeypatch, window)
        _arm(window)

        window._on_engine_error("boom", "connection")

        assert recorded == [(tr("sync.sel_failed_title"), tr("sync.sel_failed_msg"))]

    def test_a_generic_error_reports_failure(self, window, monkeypatch):
        recorded = _capture_important(monkeypatch, window)
        _arm(window)

        window._on_engine_error("boom", "")

        assert recorded == [(tr("sync.sel_failed_title"), tr("sync.sel_failed_msg"))]


class TestSuccessOutcomes:
    def test_completed_run_reports_the_transfer_count(self, window, monkeypatch):
        recorded = _capture_info(monkeypatch, window)
        _arm(window, direction="upload-only", phase="run")
        window._selection_result_count = 3

        window._on_sync_completed()

        assert recorded == [tr("sync.sel_sent_fmt").replace("{count}", "3")]
        assert window._selection_sync_active is False

    def test_a_receive_run_uses_the_received_text(self, window, monkeypatch):
        recorded = _capture_info(monkeypatch, window)
        _arm(window, direction="download-only", phase="run")
        window._selection_result_count = 1

        window._on_sync_completed()

        assert recorded == [tr("sync.sel_received_fmt").replace("{count}", "1")]

    def test_a_run_with_no_transfers_reports_already_synced(self, window, monkeypatch):
        recorded = _capture_info(monkeypatch, window)
        _arm(window, phase="run")

        window._on_sync_completed()

        assert recorded == [tr("sync.sel_already_synced")]

    def test_transfers_are_counted_only_while_running(self, window):
        _arm(window, phase="preview")
        window._on_file_transferred("↓", "a.txt")
        assert window._selection_result_count == 0

        window._selection_sync_phase = "run"
        window._on_file_transferred("↓", "a.txt")
        window._on_file_transferred("↑", "b.txt")
        assert window._selection_result_count == 2

    def test_finishing_twice_surfaces_the_result_once(self, window, monkeypatch):
        recorded = _capture_info(monkeypatch, window)
        _arm(window, phase="run")
        window._selection_result_count = 1

        assert window._finish_selection_sync("done") is True
        assert window._finish_selection_sync("done") is False
        assert recorded == [tr("sync.sel_sent_fmt").replace("{count}", "1")]


class TestProcessLifecycle:
    def test_process_finished_finalizes_a_running_op(self, window, monkeypatch):
        recorded = _capture_important(monkeypatch, window)
        _arm(window, phase="run")

        window._on_process_finished(1, "stopped")

        assert recorded == [(tr("sync.sel_failed_title"), tr("sync.sel_failed_msg"))]
        assert window._selection_sync_active is False

    def test_process_finished_keeps_a_confirming_op_alive(self, window):
        _arm(window, phase="confirm")

        window._on_process_finished(0, "stopped")

        assert window._selection_sync_active is True

    def test_engine_start_failure_reports_once_and_ends_the_op(self, window, monkeypatch):
        recorded = _capture_important(monkeypatch, window)
        shown = _count_dialogs(monkeypatch)
        _arm(window)

        def failing_start(_args):
            window._engine.error_occurred.emit("hsync binary not found.", "start")
            return False

        monkeypatch.setattr(window._engine, "start", failing_start)

        assert window._start_engine(["p2p"]) is False
        # One dialog (the specific start failure), no scoped-op outcome.
        assert len(shown) == 1
        assert shown[0].text() == tr("notif.engine_start_failed")
        assert recorded == []
        assert window._selection_sync_active is False


class TestConnectionLost:
    def test_a_link_that_never_connected_reports_no_loss(self, window):
        notifier = _FakeNotifier()
        window._notifier = notifier

        window._on_status("disconnected")

        assert ("connection_lost",) not in notifier.calls

    def test_a_dropped_link_after_connecting_reports_the_loss(self, window):
        notifier = _FakeNotifier()
        window._notifier = notifier
        window._on_status("connected")

        window._on_status("disconnected")

        assert ("connection_lost",) in notifier.calls

    def test_a_lone_waiting_master_never_reports_a_loss(self, window):
        notifier = _FakeNotifier()
        window._notifier = notifier

        window._on_status("waiting")

        assert ("connection_lost",) not in notifier.calls

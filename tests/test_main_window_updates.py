# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Help → Check for Updates: how the release-probe result is rendered."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from hsync_desktop import updates
from hsync_desktop.engine.async_probe import ProbeOutcome
from hsync_desktop.main_window import actions

NEWER = "99.0.0"


@pytest.fixture
def update_store(tmp_path, monkeypatch):
    """Redirect the persisted update state to a throwaway INI file."""
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(updates, "_settings", lambda: store)
    return store


def _outcome(value: str = "", ok: bool = True) -> ProbeOutcome:
    return ProbeOutcome(ok=ok, value=value, reason="" if ok else "unreachable")


class TestManualCheck:
    """The Help-menu path always answers: newer, up to date, or failed."""

    def test_a_newer_release_offers_the_download(self, window, update_store, monkeypatch):
        offered: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            window, "_offer_update", lambda latest, manual: offered.append((latest, manual))
        )
        window._update_manual = True

        window._on_update_checked(_outcome(NEWER))

        assert offered == [(NEWER, True)]

    def test_an_up_to_date_build_reports_the_running_version(
        self, window, update_store, monkeypatch
    ):
        from hsync_desktop import __version__

        shown: list[str] = []
        monkeypatch.setattr(window, "_show_up_to_date", lambda current: shown.append(current))
        window._update_manual = True

        window._on_update_checked(_outcome(__version__))

        assert shown == [__version__]

    def test_a_failure_is_reported_to_the_operator(self, window, update_store, monkeypatch):
        warnings: list[tuple] = []
        monkeypatch.setattr(
            actions.QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args)
        )
        window._update_manual = True

        window._on_update_checked(_outcome(""))

        assert len(warnings) == 1


class TestStartupCheck:
    """The opt-in path stays silent unless a new release is worth reporting."""

    def test_a_failure_is_silent(self, window, update_store, monkeypatch):
        warnings: list[tuple] = []
        monkeypatch.setattr(
            actions.QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args)
        )
        window._update_manual = False

        window._on_update_checked(_outcome(""))

        assert warnings == []

    def test_a_dismissed_release_is_not_reported_again(self, window, update_store, monkeypatch):
        offered: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            window, "_offer_update", lambda latest, manual: offered.append((latest, manual))
        )
        updates.set_dismissed_version(NEWER)
        window._update_manual = False

        window._on_update_checked(_outcome(NEWER))

        assert offered == []
        # The check still runs: only the reminder for that release is suppressed.
        assert updates.last_check_epoch() is not None

    def test_the_startup_check_runs_only_when_opted_in(self, window, update_store, monkeypatch):
        started: list[bool] = []
        monkeypatch.setattr(window, "_start_update_check", lambda manual: started.append(manual))

        window.maybe_check_updates_on_startup()
        assert started == []  # opt-in, off by default

        updates.set_enabled(True)
        window.maybe_check_updates_on_startup()
        assert started == [False]  # automatic, not a manual click

    def test_the_check_is_not_repeated_within_the_interval(self, window, update_store, monkeypatch):
        started: list[bool] = []
        monkeypatch.setattr(window, "_start_update_check", started.append)
        updates.set_enabled(True)
        updates.record_check(None)

        window.maybe_check_updates_on_startup()

        assert started == []

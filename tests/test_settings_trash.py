# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The trash retention setting: storage, emission and the promise it backs.

The Settings spin stores ``sync/trash_retention``; ``build_hsync_args`` emits it
only once it exists, and the plan dialog's promise reads the same resolution
order, so the GUI cannot promise a window the engine does not use (ADR-0056).
"""

from __future__ import annotations

from hsync_desktop.config import (
    DEFAULT_TRASH_ENABLED,
    DEFAULT_TRASH_MAX_SIZE_GB,
    DEFAULT_TRASH_RETENTION_DAYS,
)
from hsync_desktop.settings.cli_args import (
    build_hsync_args,
    get_trash_enabled,
    get_trash_max_size_gb,
    get_trash_retention_days,
    trash_retention_days,
)
from tests._helpers import _patch_settings_qsettings, _settings


def _flag_values(args: list[str], flag: str) -> list[str]:
    return [args[i + 1] for i, value in enumerate(args[:-1]) if value == flag]


class TestStoredValue:
    def test_the_trash_is_on_by_default(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        assert get_trash_enabled() is DEFAULT_TRASH_ENABLED is True

    def test_the_default_is_the_shared_window(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        assert get_trash_retention_days() == DEFAULT_TRASH_RETENTION_DAYS

    def test_the_stored_value_wins_over_the_environment(self, monkeypatch, tmp_path):
        store = _settings(tmp_path)
        store.setValue("sync/trash_retention", 7)
        _patch_settings_qsettings(monkeypatch, store)
        monkeypatch.setenv("HSYNC_TRASH_RETENTION_DAYS", "90")

        assert trash_retention_days() == 7

    def test_the_environment_applies_until_the_setting_is_stored(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))
        monkeypatch.setenv("HSYNC_TRASH_RETENTION_DAYS", "7")

        assert trash_retention_days() == 7

    def test_a_disabled_trash_makes_no_promise(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))
        monkeypatch.setenv("HSYNC_TRASH_ENABLED", "false")

        assert trash_retention_days() == 0


class TestEmission:
    def test_nothing_is_emitted_before_the_user_stores_it(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        args = build_hsync_args(str(tmp_path))

        assert _flag_values(args, "--trash-retention") == []

    def test_a_stored_window_reaches_the_engine(self, monkeypatch, tmp_path):
        store = _settings(tmp_path)
        store.setValue("sync/trash_retention", 7)
        _patch_settings_qsettings(monkeypatch, store)

        args = build_hsync_args(str(tmp_path))

        assert _flag_values(args, "--trash-retention") == ["7"]
        assert "--no-trash" not in args

    def test_the_disabled_switch_turns_the_trash_off(self, monkeypatch, tmp_path):
        """The switch is the only "off": the client still reads 0 as "forever"."""
        store = _settings(tmp_path)
        store.setValue("sync/trash_enabled", False)
        _patch_settings_qsettings(monkeypatch, store)

        args = build_hsync_args(str(tmp_path))

        assert "--no-trash" in args
        assert _flag_values(args, "--trash-retention") == []

    def test_a_stored_zero_window_clamps_to_one_day(self, monkeypatch, tmp_path):
        """An older build could store 0; the client would read it as forever."""
        store = _settings(tmp_path)
        store.setValue("sync/trash_retention", 0)
        _patch_settings_qsettings(monkeypatch, store)

        assert get_trash_retention_days() == 1
        assert _flag_values(build_hsync_args(str(tmp_path)), "--trash-retention") == ["1"]

    def test_the_environment_disable_applies_until_the_user_stores_it(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))
        monkeypatch.setenv("HSYNC_TRASH_ENABLED", "false")

        assert get_trash_enabled() is False
        assert trash_retention_days() == 0
        # Nothing stored: the client's own environment decides, so no flag.
        assert _flag_values(build_hsync_args(str(tmp_path)), "--trash-retention") == []


class TestBudget:
    def test_the_default_hands_the_cap_to_the_client(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        assert get_trash_max_size_gb() == DEFAULT_TRASH_MAX_SIZE_GB == 0

    def test_a_stored_budget_reaches_the_engine_as_a_size(self, monkeypatch, tmp_path):
        store = _settings(tmp_path)
        store.setValue("sync/trash_max_size_gb", 4)
        _patch_settings_qsettings(monkeypatch, store)

        args = build_hsync_args(str(tmp_path))

        assert get_trash_max_size_gb() == 4
        assert _flag_values(args, "--trash-max-size") == ["4GB"]

    def test_an_unstored_budget_emits_nothing(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        args = build_hsync_args(str(tmp_path))

        assert _flag_values(args, "--trash-max-size") == []

    def test_the_auto_choice_emits_nothing(self, monkeypatch, tmp_path):
        """A stored 0 is the dialog's "Auto": the client derives the cap itself."""
        store = _settings(tmp_path)
        store.setValue("sync/trash_max_size_gb", 0)
        _patch_settings_qsettings(monkeypatch, store)

        args = build_hsync_args(str(tmp_path))

        assert _flag_values(args, "--trash-max-size") == []

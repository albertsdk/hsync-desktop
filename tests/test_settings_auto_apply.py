# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Contract of the *Apply changes that delete nothing* setting.

The setting is on by default, but it never applies the first plan of an
installation: ``has_seen_plan_confirmation`` gates the skip until a confirmation
has been shown, so a fresh install always sees what the dialog reports.
"""

from __future__ import annotations

from hsync_desktop.settings.cli_args import (
    has_seen_plan_confirmation,
    is_auto_apply_enabled,
    mark_plan_confirmation_seen,
)
from tests._helpers import _patch_settings_qsettings, _settings


class TestAutoApplyDefault:
    def test_the_setting_is_on_by_default(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        assert is_auto_apply_enabled() is True

    def test_the_user_can_turn_it_off(self, monkeypatch, tmp_path):
        store = _settings(tmp_path)
        store.setValue("sync/auto_apply", False)
        _patch_settings_qsettings(monkeypatch, store)

        assert is_auto_apply_enabled() is False


class TestPlanConfirmationGate:
    def test_the_first_plan_of_an_installation_is_not_skipped(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        assert has_seen_plan_confirmation() is False

    def test_showing_a_plan_is_remembered(self, monkeypatch, tmp_path):
        _patch_settings_qsettings(monkeypatch, _settings(tmp_path))

        mark_plan_confirmation_seen()

        assert has_seen_plan_confirmation() is True

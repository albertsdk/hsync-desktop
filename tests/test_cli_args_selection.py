# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for build_selection_args (Send/Receive now on a selection)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


class _FakeQSettings:
    """Minimal QSettings stand-in driven by a plain dict."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def value(self, key: str, default: Any = None, type_: Any = None) -> Any:
        return self._values.get(key, default)

    def contains(self, key: str) -> bool:
        return key in self._values


def _selection_args(values: dict[str, Any], subdir: str, direction: str) -> list[str]:
    from hsync_desktop.settings import cli_args

    with (
        patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings(values)),
        patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
    ):
        return cli_args.build_selection_args("", subdir, direction)


class TestBuildSelectionArgs:
    """A selection sync is a one-shot run in a single direction and scope."""

    def test_forces_one_shot_direction_and_subdir(self):
        args = _selection_args({}, "media", "upload-only")

        assert args.count("--once") == 1
        assert args[args.index("--sync-direction") + 1] == "upload-only"
        assert args[args.index("--subdir") + 1] == "media"

    def test_overrides_the_saved_direction_and_filter(self):
        values = {
            "sync/continuous": True,
            "sync/direction": "download-only",
            "sync/filter_path": "old",
        }

        args = _selection_args(values, "media", "upload-only")

        assert args.count("--sync-direction") == 1
        assert args[args.index("--sync-direction") + 1] == "upload-only"
        assert args.count("--subdir") == 1
        assert args[args.index("--subdir") + 1] == "media"
        assert args.count("--once") == 1

    def test_receive_maps_to_download_only(self):
        args = _selection_args({}, "media", "download-only")

        assert args[args.index("--sync-direction") + 1] == "download-only"

    def test_empty_subdir_emits_no_flag(self):
        args = _selection_args({}, "", "upload-only")

        assert "--subdir" not in args

    def test_continuous_setting_does_not_leak(self):
        args = _selection_args({"sync/continuous": True}, "", "upload-only")

        assert args.count("--once") == 1

    def test_preview_adds_dry_run_and_keeps_one_shot(self):
        from hsync_desktop.settings import cli_args

        with (
            patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings({})),
            patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
        ):
            args = cli_args.build_selection_args("", "media", "upload-only", dry_run=True)

        assert "--dry-run" in args
        assert args.count("--once") == 1

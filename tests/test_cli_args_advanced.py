# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the Advanced-tab CLI emission (engine tuning knobs).

These pin the contract between the Advanced settings tab and the ``hsync`` CLI:
values matching the client default are omitted so the engine keeps its own
default/auto behaviour, and the mass-deletion thresholds are always clamped.
"""

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

    def setValue(self, key: str, value: Any) -> None:  # noqa: N802 (Qt name)
        self._values[key] = value

    def remove(self, key: str) -> None:
        self._values.pop(key, None)

    def sync(self) -> None:
        pass


def _build_args(values: dict[str, Any], *, p2p: bool = False) -> list[str]:
    from hsync_desktop.settings import cli_args

    vals = dict(values)
    vals.setdefault("p2p/enabled", p2p)
    with (
        patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings(vals)),
        patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
    ):
        return cli_args.build_hsync_args(local_path="")


def _value_after(args: list[str], flag: str) -> str | None:
    """Return the value following *flag*, or None when the flag is absent."""
    if flag not in args:
        return None
    return args[args.index(flag) + 1]


class TestDefaults:
    """Client-matching defaults are omitted from the CLI."""

    def test_defaults_omit_tuning_flags(self):
        args = _build_args({})
        for flag in (
            "--no-autotune",
            "--max-concurrent-transfers",
            "--no-delta",
            "--delta-min-file-size",
            "--delta-min-file-size-p2p",
            "--no-mass-delete-guard",
        ):
            assert flag not in args

    def test_guard_thresholds_are_always_sent(self):
        args = _build_args({})
        assert _value_after(args, "--mass-delete-threshold") == "50"
        assert _value_after(args, "--mass-delete-percent") == "50"


class TestPerformance:
    def test_autotune_off_emits_no_autotune(self):
        assert "--no-autotune" in _build_args({"advanced/autotune": False})

    def test_max_concurrent_only_when_set(self):
        args = _build_args({"advanced/max_concurrent_transfers": 3})
        assert _value_after(args, "--max-concurrent-transfers") == "3"
        assert "--max-concurrent-transfers" not in _build_args(
            {"advanced/max_concurrent_transfers": 0}
        )

    def test_max_concurrent_is_clamped(self):
        assert (
            _value_after(
                _build_args({"advanced/max_concurrent_transfers": 99}), "--max-concurrent-transfers"
            )
            == "20"
        )


class TestDelta:
    def test_delta_off_emits_no_delta(self):
        assert "--no-delta" in _build_args({"advanced/delta_enabled": False})

    def test_delta_min_sizes_are_kb_to_bytes(self):
        args = _build_args(
            {
                "advanced/delta_min_file_size_kb": 512,
                "advanced/delta_min_file_size_p2p_kb": 2048,
            }
        )
        assert _value_after(args, "--delta-min-file-size") == str(512 * 1024)
        assert _value_after(args, "--delta-min-file-size-p2p") == str(2048 * 1024)

    def test_delta_min_default_size_is_omitted(self):
        args = _build_args({"advanced/delta_min_file_size_kb": 256})
        assert "--delta-min-file-size" not in args


class TestDeletionProtection:
    def test_guard_off_emits_no_mass_delete_guard(self):
        assert "--no-mass-delete-guard" in _build_args({"advanced/mass_delete_guard": False})

    def test_thresholds_are_clamped(self):
        args = _build_args(
            {
                "advanced/mass_delete_threshold": 9_999_999,
                "advanced/mass_delete_percent": 200,
            }
        )
        assert _value_after(args, "--mass-delete-threshold") == "1000000"
        assert _value_after(args, "--mass-delete-percent") == "100"

    def test_zero_disables_a_rule(self):
        args = _build_args({"advanced/mass_delete_threshold": 0})
        assert _value_after(args, "--mass-delete-threshold") == "0"


class TestPeerDownload:
    def test_peer_download_off_emits_flag_in_p2p(self):
        args = _build_args({"p2p/peer_download": False}, p2p=True)
        assert "--no-peer-download" in args

    def test_peer_download_flag_absent_when_on(self):
        assert "--no-peer-download" not in _build_args({"p2p/peer_download": True}, p2p=True)

    def test_peer_download_flag_not_emitted_in_server_mode(self):
        assert "--no-peer-download" not in _build_args({"p2p/peer_download": False}, p2p=False)


class TestBandwidthClamp:
    """Bandwidth limits are clamped to the client's [1 KB/s, 100 MB/s] range."""

    def test_save_clamps_above_the_engine_maximum(self):
        from hsync_desktop.config import BANDWIDTH_MAX_MBPS
        from hsync_desktop.settings import cli_args

        values: dict[str, Any] = {}
        with patch.object(cli_args, "QSettings", lambda *a, **k: _FakeQSettings(values)):
            cli_args.save_bandwidth_limits(1000.0, 5.0)
        assert values["sync/bandwidth_upload"] == BANDWIDTH_MAX_MBPS
        assert values["sync/bandwidth_download"] == 5.0

    def test_read_clamps_a_legacy_value(self):
        from hsync_desktop.config import BANDWIDTH_MAX_BPS
        from hsync_desktop.settings import cli_args

        values = {"sync/bandwidth_upload": 1000.0, "sync/bandwidth_download": 5.0}
        with patch.object(cli_args, "QSettings", lambda *a, **k: _FakeQSettings(values)):
            upload, download = cli_args.get_bandwidth_limits()
        assert upload == BANDWIDTH_MAX_BPS
        assert download == 5 * 1024 * 1024


class TestSelectionInheritance:
    """A scoped Send/Receive now inherits the tuning flags (no incompatibility)."""

    def test_selection_keeps_advanced_flags(self):
        from hsync_desktop.settings import cli_args

        values = {
            "p2p/enabled": True,
            "advanced/autotune": False,
            "advanced/mass_delete_guard": False,
        }
        with (
            patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings(values)),
            patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
            patch.object(cli_args, "build_hsync_args", wraps=cli_args.build_hsync_args) as _wrapped,
        ):
            args = cli_args.build_selection_args("", "sub", "upload-only")

        assert "--no-autotune" in args
        assert "--no-mass-delete-guard" in args
        assert "--prefer-master" not in args


class TestLoggingFlags:
    """The Advanced-tab logging toggles map onto the client's output flags."""

    def test_verbose_emits_the_short_flag(self):
        """Detailed log output is the client's ``-v`` (DEBUG level)."""
        assert "-v" in _build_args({"output/verbose": True})

    def test_verbose_is_off_by_default(self):
        assert "-v" not in _build_args({})

    def test_log_file_and_verbose_travel_together(self):
        """The file mirrors the log; the panel keeps reading stdout."""
        args = _build_args({"output/verbose": True, "output/logfile": "/tmp/hsync.log"})

        assert "-v" in args
        assert _value_after(args, "--log-file") == "/tmp/hsync.log"

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.settings.cli_args LAN argument emission.

These tests cover the contract between the desktop settings UI and the
``hsync`` CLI binary, with a focus on the ``LAN_PERSISTENT`` flag whose
behaviour was clarified as a result of the slave one-shot / continuous
sync alignment across all clients (CLI, Desktop, Android).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


class _FakeQSettings:
    """Minimal QSettings stand-in driven by a plain dict."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def value(self, key: str, default: Any = None, type_: Any = None) -> Any:
        # QSettings(key, default, type) coerces to *type_*; for our tests the
        # stored value already has the right Python type, so just return it.
        return self._values.get(key, default)

    def contains(self, key: str) -> bool:
        return key in self._values


def _build_args(values: dict[str, Any], local_path: str = "") -> list[str]:
    """Run build_hsync_args with QSettings backed by *values*.

    *local_path* is empty by default so that the path validation branch is
    skipped (we are only interested in the LAN section).
    """
    from hsync_desktop.settings import cli_args

    with (
        patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings(values)),
        patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
    ):
        return cli_args.build_hsync_args(local_path=local_path)


class TestLanPersistentFlag:
    """Regression tests for the LAN_PERSISTENT user-facing setting."""

    def test_persistent_default_true_omits_flag(self):
        """With LAN enabled and persistent left at default (True) no flag is emitted."""
        args = _build_args(
            {
                "lan/enabled": True,
                # lan/persistent intentionally omitted -> default True
            }
        )

        assert "--lan-mode" in args
        assert "--no-lan-persistent" not in args, (
            "Default persistent=True must not emit --no-lan-persistent"
        )

    def test_persistent_true_omits_flag(self):
        """Explicit persistent=True must not emit --no-lan-persistent."""
        args = _build_args({"lan/enabled": True, "lan/persistent": True})

        assert "--no-lan-persistent" not in args

    def test_persistent_false_emits_no_lan_persistent(self):
        """Explicit persistent=False must emit --no-lan-persistent."""
        args = _build_args({"lan/enabled": True, "lan/persistent": False})

        assert "--no-lan-persistent" in args

    def test_persistent_flag_not_emitted_when_lan_disabled(self):
        """LAN disabled: persistent flag must be skipped along with all other LAN args."""
        args = _build_args({"lan/enabled": False, "lan/persistent": False})

        assert "--lan-mode" not in args
        assert "--no-lan-persistent" not in args, (
            "LAN section must not emit any flag when lan/enabled is False"
        )


class TestLanSectionConsistency:
    """Cross-flag consistency of the LAN argument block."""

    def test_lan_block_emits_expected_flags_when_fully_enabled(self):
        """A fully populated LAN config produces all expected flags exactly once."""
        args = _build_args(
            {
                "lan/enabled": True,
                "lan/port": 9000,
                "lan/discovery_timeout": 15,
                "lan/group": "test-group",
                "lan/https": False,  # emits --no-lan-https
                "lan/persistent": False,  # emits --no-lan-persistent
                "lan/force_master": True,  # emits --force-master
            }
        )

        # Each LAN flag appears exactly once.
        for flag in (
            "--lan-mode",
            "--lan-port",
            "--discovery-timeout",
            "--lan-group",
            "--no-lan-https",
            "--no-lan-persistent",
            "--force-master",
        ):
            assert args.count(flag) == 1, f"Expected exactly one occurrence of {flag}"

        # Argument values follow their flag.
        assert args[args.index("--lan-port") + 1] == "9000"
        assert args[args.index("--discovery-timeout") + 1] == "15"
        assert args[args.index("--lan-group") + 1] == "test-group"

    def test_lan_https_and_persistent_are_independent(self):
        """The --no-lan-https and --no-lan-persistent flags do not influence each other."""
        # https disabled, persistent enabled
        args_a = _build_args({"lan/enabled": True, "lan/https": False, "lan/persistent": True})
        assert "--no-lan-https" in args_a
        assert "--no-lan-persistent" not in args_a

        # https enabled, persistent disabled
        args_b = _build_args({"lan/enabled": True, "lan/https": True, "lan/persistent": False})
        assert "--no-lan-https" not in args_b
        assert "--no-lan-persistent" in args_b

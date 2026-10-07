# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.settings.cli_args p2p argument emission.

These tests cover the contract between the desktop settings UI and the
``hsync`` CLI binary, including the one-shot / continuous sync alignment
across all clients (CLI, Desktop, Android): ``--once`` is the single
one-shot selector emitted when continuous sync is disabled.
"""

from __future__ import annotations

import os
import stat
from typing import Any
from unittest.mock import patch

import pytest


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
    skipped (we are only interested in the p2p section).
    """
    from hsync_desktop.settings import cli_args

    with (
        patch.object(cli_args, "QSettings", lambda *a, **kw: _FakeQSettings(values)),
        patch.object(cli_args, "get_bandwidth_limits", return_value=(None, None)),
    ):
        return cli_args.build_hsync_args(local_path=local_path)


class TestContinuousMapping:
    """Continuous mode is the client default: no -w exists anymore."""

    def test_continuous_default_emits_no_flag(self):
        """sync/continuous True (default) must not emit any mode flag."""
        args = _build_args({"sync/continuous": True})

        assert "-w" not in args
        assert "--once" not in args

    def test_continuous_false_emits_once(self):
        """sync/continuous False maps to the one-shot --once flag."""
        args = _build_args({"sync/continuous": False})

        assert "--once" in args
        assert "-w" not in args


class TestP2PSectionConsistency:
    """Cross-flag consistency of the p2p argument block."""

    def test_p2p_block_emits_expected_flags_when_fully_enabled(self):
        """A fully populated p2p config produces all expected flags exactly once."""
        args = _build_args(
            {
                "p2p/enabled": True,
                "p2p/port": 9000,
                "p2p/discovery_timeout": 15,
                "p2p/group": "test-group",
                "sync/continuous": False,  # emits --once
                "p2p/force_master": True,  # emits --force-master
            }
        )

        # Each p2p flag appears exactly once.
        for flag in (
            "p2p",
            "--listen-port",
            "--discovery-timeout",
            "--group",
            "--once",
            "--force-master",
        ):
            assert args.count(flag) == 1, f"Expected exactly one occurrence of {flag}"

        # Argument values follow their flag.
        assert args[args.index("--listen-port") + 1] == "9000"
        assert args[args.index("--discovery-timeout") + 1] == "15"
        assert args[args.index("--group") + 1] == "test-group"

    def test_one_shot_and_force_master_are_independent(self):
        """The --once and --force-master flags do not influence each other."""
        # one-shot enabled, force_master off
        args_a = _build_args(
            {"p2p/enabled": True, "sync/continuous": False, "p2p/force_master": False}
        )
        assert "--once" in args_a
        assert "--force-master" not in args_a

        # continuous enabled, force_master on
        args_b = _build_args(
            {"p2p/enabled": True, "sync/continuous": True, "p2p/force_master": True}
        )
        assert "--once" not in args_b
        assert "--force-master" in args_b


class TestNeverMasterFlag:
    """Coverage for the --never-master user-facing setting."""

    def test_never_master_default_omits_flag(self):
        """With p2p enabled and never_master left at default, no flag is emitted."""
        args = _build_args({"p2p/enabled": True})

        assert "--never-master" not in args

    def test_never_master_false_omits_flag(self):
        """Explicit never_master=False must not emit --never-master."""
        args = _build_args({"p2p/enabled": True, "p2p/never_master": False})

        assert "--never-master" not in args

    def test_never_master_true_emits_flag(self):
        """Explicit never_master=True must emit --never-master exactly once."""
        args = _build_args({"p2p/enabled": True, "p2p/never_master": True})

        assert args.count("--never-master") == 1

    def test_never_master_flag_not_emitted_when_p2p_disabled(self):
        """p2p disabled: never-master flag must be skipped with the rest of the block."""
        args = _build_args({"p2p/enabled": False, "p2p/never_master": True})

        assert args[0] == "server"
        assert "--never-master" not in args


class TestRequirePairingFlag:
    """Coverage for the --require-pairing (strict pairing) user-facing setting."""

    def test_require_pairing_default_omits_flag(self):
        """With p2p enabled and require_pairing left at default, no flag is emitted."""
        args = _build_args({"p2p/enabled": True})

        assert "--require-pairing" not in args

    def test_require_pairing_false_omits_flag(self):
        """Explicit require_pairing=False must not emit --require-pairing."""
        args = _build_args({"p2p/enabled": True, "p2p/require_pairing": False})

        assert "--require-pairing" not in args

    def test_require_pairing_true_emits_flag(self):
        """Explicit require_pairing=True must emit --require-pairing exactly once."""
        args = _build_args({"p2p/enabled": True, "p2p/require_pairing": True})

        assert args.count("--require-pairing") == 1

    def test_require_pairing_flag_not_emitted_when_p2p_disabled(self):
        """p2p disabled: require-pairing flag must be skipped with the rest of the block."""
        args = _build_args({"p2p/enabled": False, "p2p/require_pairing": True})

        assert args[0] == "server"
        assert "--require-pairing" not in args


class TestIgnorePatterns:
    """Coverage for --ignore-pattern emission."""

    def test_ignore_patterns_default_omits_flag(self):
        """Empty/missing ignore patterns must not emit --ignore-pattern."""
        args = _build_args({})

        assert "--ignore-pattern" not in args

    def test_ignore_patterns_empty_string_omits_flag(self):
        """Whitespace-only patterns must not emit --ignore-pattern."""
        args = _build_args({"sync/ignore_patterns": "   "})

        assert "--ignore-pattern" not in args

    def test_ignore_patterns_value_emits_flag(self):
        """A non-empty patterns string is emitted as repeated --ignore-pattern flags."""
        args = _build_args({"sync/ignore_patterns": "*.log,/build/,/dist/"})

        assert args.count("--ignore-pattern") == 3
        values = [args[i + 1] for i, a in enumerate(args) if a == "--ignore-pattern"]
        assert values == ["*.log", "/build/", "/dist/"]


class TestMaxDownloadSizeFlag:
    """--max-inbound-size passthrough (absolute anti-bomb cap)."""

    def test_default_value_emitted(self):
        """Without a stored value the desktop default (10 GB) is passed."""
        args = _build_args({})

        idx = args.index("--max-inbound-size")
        assert args[idx + 1] == "10240"

    def test_stored_value_emitted(self):
        args = _build_args({"sync/max_inbound_size": 51200})

        idx = args.index("--max-inbound-size")
        assert args[idx + 1] == "51200"

    def test_value_clamped_to_valid_range(self):
        args = _build_args({"sync/max_inbound_size": 99_000_000})

        idx = args.index("--max-inbound-size")
        assert args[idx + 1] == "10000000"


class TestServerUrlViaEnvOnly:
    """The server endpoint is env-only: the client CLI takes the bare host and
    has no URL flag, so a stored server_url must never hit the command line
    (engine.apply_settings_env exports it as HSYNC_SERVER instead)."""

    def test_server_mode_emits_no_url_flag(self):
        """p2p disabled + stored URL: neither the URL nor any -s/--server flag
        is emitted (the endpoint travels via HSYNC_SERVER)."""
        args = _build_args(
            {
                "p2p/enabled": False,
                "connection/server_url": "https://hsync.example.com:9753",
            }
        )

        assert args[0] == "server"
        assert "https://hsync.example.com:9753" not in args

    def test_zero_means_disabled_and_is_emitted(self):
        args = _build_args({"sync/max_inbound_size": 0})

        idx = args.index("--max-inbound-size")
        assert args[idx + 1] == "0"


@pytest.mark.skipif(os.name != "posix", reason="0600 enforcement is POSIX-only")
class TestSecureConfigFile:
    """Coverage for secure_config_file() (QSettings world-readable hardening)."""

    def test_secure_config_file_restricts_to_owner_only(self, qapp, tmp_path):
        """After secure_config_file() the native config file is mode 0600."""
        from PySide6.QtCore import QSettings

        from hsync_desktop.settings import cli_args

        fmt = QSettings.Format.NativeFormat
        scope = QSettings.Scope.UserScope
        # Redirect native QSettings storage into the temp dir for isolation.
        QSettings.setPath(fmt, scope, str(tmp_path))
        try:
            s = QSettings(cli_args.SETTINGS_ORG, cli_args.SETTINGS_APP)
            s.setValue("probe", "value")
            s.sync()
            path = s.fileName()
            assert path and os.path.exists(path)
            # Simulate the umask-derived world-readable default.
            os.chmod(path, 0o644)

            cli_args.secure_config_file()

            mode = stat.S_IMODE(os.stat(path).st_mode)
            assert mode == 0o600
        finally:
            # Restore the platform default search path for UserScope/Native.
            QSettings.setPath(fmt, scope, os.path.expanduser("~/.config"))

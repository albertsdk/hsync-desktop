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
            "--no-lan-persistent",
            "--force-master",
        ):
            assert args.count(flag) == 1, f"Expected exactly one occurrence of {flag}"

        # Argument values follow their flag.
        assert args[args.index("--lan-port") + 1] == "9000"
        assert args[args.index("--discovery-timeout") + 1] == "15"
        assert args[args.index("--lan-group") + 1] == "test-group"

    def test_persistent_and_force_master_are_independent(self):
        """The --no-lan-persistent and --force-master flags do not influence each other."""
        # persistent disabled, force_master off
        args_a = _build_args(
            {"lan/enabled": True, "lan/persistent": False, "lan/force_master": False}
        )
        assert "--no-lan-persistent" in args_a
        assert "--force-master" not in args_a

        # persistent enabled, force_master on
        args_b = _build_args(
            {"lan/enabled": True, "lan/persistent": True, "lan/force_master": True}
        )
        assert "--no-lan-persistent" not in args_b
        assert "--force-master" in args_b


class TestNeverMasterFlag:
    """Coverage for the --never-master user-facing setting."""

    def test_never_master_default_omits_flag(self):
        """With LAN enabled and never_master left at default, no flag is emitted."""
        args = _build_args({"lan/enabled": True})

        assert "--never-master" not in args

    def test_never_master_false_omits_flag(self):
        """Explicit never_master=False must not emit --never-master."""
        args = _build_args({"lan/enabled": True, "lan/never_master": False})

        assert "--never-master" not in args

    def test_never_master_true_emits_flag(self):
        """Explicit never_master=True must emit --never-master exactly once."""
        args = _build_args({"lan/enabled": True, "lan/never_master": True})

        assert args.count("--never-master") == 1

    def test_never_master_flag_not_emitted_when_lan_disabled(self):
        """LAN disabled: never-master flag must be skipped with the rest of the block."""
        args = _build_args({"lan/enabled": False, "lan/never_master": True})

        assert "--lan-mode" not in args
        assert "--never-master" not in args


class TestRequirePairingFlag:
    """Coverage for the --require-pairing (strict pairing) user-facing setting."""

    def test_require_pairing_default_omits_flag(self):
        """With LAN enabled and require_pairing left at default, no flag is emitted."""
        args = _build_args({"lan/enabled": True})

        assert "--require-pairing" not in args

    def test_require_pairing_false_omits_flag(self):
        """Explicit require_pairing=False must not emit --require-pairing."""
        args = _build_args({"lan/enabled": True, "lan/require_pairing": False})

        assert "--require-pairing" not in args

    def test_require_pairing_true_emits_flag(self):
        """Explicit require_pairing=True must emit --require-pairing exactly once."""
        args = _build_args({"lan/enabled": True, "lan/require_pairing": True})

        assert args.count("--require-pairing") == 1

    def test_require_pairing_flag_not_emitted_when_lan_disabled(self):
        """LAN disabled: require-pairing flag must be skipped with the rest of the block."""
        args = _build_args({"lan/enabled": False, "lan/require_pairing": True})

        assert "--lan-mode" not in args
        assert "--require-pairing" not in args


class TestSyncHiddenAndIgnorePatterns:
    """Coverage for --sync-hidden and --ignore-patterns emission."""

    def test_sync_hidden_default_omits_flag(self):
        """Without an explicit value, --sync-hidden must not be emitted."""
        args = _build_args({})

        assert "--sync-hidden" not in args

    def test_sync_hidden_false_omits_flag(self):
        """Explicit False must not emit --sync-hidden."""
        args = _build_args({"sync/sync_hidden": False})

        assert "--sync-hidden" not in args

    def test_sync_hidden_true_emits_flag(self):
        """Explicit True must emit --sync-hidden."""
        args = _build_args({"sync/sync_hidden": True})

        assert "--sync-hidden" in args
        assert args.count("--sync-hidden") == 1

    def test_ignore_patterns_default_omits_flag(self):
        """Empty/missing ignore patterns must not emit --ignore-patterns."""
        args = _build_args({})

        assert "--ignore-patterns" not in args

    def test_ignore_patterns_empty_string_omits_flag(self):
        """Whitespace-only patterns must not emit --ignore-patterns."""
        args = _build_args({"sync/ignore_patterns": "   "})

        assert "--ignore-patterns" not in args

    def test_ignore_patterns_value_emits_flag(self):
        """A non-empty patterns string is passed verbatim to --ignore-patterns."""
        args = _build_args({"sync/ignore_patterns": "*.log,/build/,/dist/"})

        assert "--ignore-patterns" in args
        assert args[args.index("--ignore-patterns") + 1] == "*.log,/build/,/dist/"


class TestMaxDownloadSizeFlag:
    """--max-download-size passthrough (absolute anti-bomb cap)."""

    def test_default_value_emitted(self):
        """Without a stored value the desktop default (10 GB) is passed."""
        args = _build_args({})

        idx = args.index("--max-download-size")
        assert args[idx + 1] == "10240"

    def test_stored_value_emitted(self):
        args = _build_args({"sync/max_download_size": 51200})

        idx = args.index("--max-download-size")
        assert args[idx + 1] == "51200"

    def test_value_clamped_to_valid_range(self):
        args = _build_args({"sync/max_download_size": 99_000_000})

        idx = args.index("--max-download-size")
        assert args[idx + 1] == "10000000"

    def test_zero_means_disabled_and_is_emitted(self):
        args = _build_args({"sync/max_download_size": 0})

        idx = args.index("--max-download-size")
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

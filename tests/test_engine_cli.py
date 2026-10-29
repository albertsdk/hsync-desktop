# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.engine module."""

import os

import pytest
from hsync_common.protocol.events import UiEventName, build_event
from PySide6.QtCore import QProcessEnvironment

from hsync_desktop.engine import (
    _EXPECTED_VERSION,
    _HSYNCKEEP,
    HsyncEngine,
    TransferStats,
    add_peer_pin,
    add_rendezvous_trust,
    add_server_trust,
    apply_settings_env,
    fetch_rendezvous_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_version,
    is_binary_version_compatible,
    list_peer_pins,
    list_rendezvous_trust,
    list_server_trust,
    remove_peer_pin,
    remove_rendezvous_trust,
    remove_server_trust,
    supports_peer_trust,
    write_secret_pipe,
)
from tests._helpers import _capture, _FakeCompleted

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.engine module."""


class TestFindHsyncBinary:
    """Test find_hsync_binary function."""

    def test_returns_string_or_none(self):
        """Should return string or None."""
        result = find_hsync_binary()
        # Either returns a path string or None
        assert result is None or isinstance(result, str)

    def test_returns_executable_path(self):
        """If not None, should be an executable path."""
        result = find_hsync_binary()
        if result:
            assert isinstance(result, str)
            # Just verify it's a non-empty string
            assert len(result) > 0

    def test_finds_binary_in_the_package_bin_dir(self, tmp_path, monkeypatch):
        """Regression: after the engine split, ``__file__`` is one level deeper
        (``hsync_desktop/engine/cli.py``); the bundled client still lives in
        ``hsync_desktop/bin/`` (the PyInstaller ``--add-data`` target), so the
        lookup must resolve against the package root, not ``engine/``."""
        from hsync_desktop.engine import cli as engine

        pkg_root = tmp_path / "hsync_desktop"
        (pkg_root / "engine").mkdir(parents=True)
        bundled = pkg_root / "bin" / "hsync"
        bundled.parent.mkdir(parents=True)
        bundled.write_text("#!/bin/sh\n", encoding="utf-8")
        bundled.chmod(0o755)

        monkeypatch.setattr(engine, "__file__", str(pkg_root / "engine" / "cli.py"))
        monkeypatch.setattr(engine.shutil, "which", lambda _name: None)

        assert find_hsync_binary() == str(bundled)


class TestHsyncKeepConstant:
    """Test _HSYNCKEEP constant."""

    def test_hsynckeep_is_string(self):
        """Should be a string."""
        assert isinstance(_HSYNCKEEP, str)

    def test_hsynckeep_value(self):
        """Should match expected value."""
        assert _HSYNCKEEP == ".hsynckeep"


class TestGetBinaryVersion:
    """Test get_binary_version function."""

    def test_parses_stdout(self, monkeypatch):
        """Should extract X.Y.Z from `hsync --version` stdout."""
        from hsync_desktop.engine import cli as engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="hsync 1.2.3\n")
        )
        assert get_binary_version("/fake/hsync") == "1.2.3"

    def test_parses_stderr(self, monkeypatch):
        """Should also look in stderr for the version string."""
        from hsync_desktop.engine import cli as engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stderr="hsync 2.0.5")
        )
        assert get_binary_version("/fake/hsync") == "2.0.5"

    def test_unparseable_returns_none(self, monkeypatch):
        """Output without a version returns None."""
        from hsync_desktop.engine import cli as engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="no version here")
        )
        assert get_binary_version("/fake/hsync") is None

    def test_os_error_returns_none(self, monkeypatch):
        """A failure to execute the binary returns None."""
        from hsync_desktop.engine import cli as engine

        def _raise(*a, **k):
            raise OSError("cannot exec")

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_version("/fake/hsync") is None

    def test_timeout_returns_none(self, monkeypatch):
        """A timeout while querying the binary returns None."""
        from hsync_desktop.engine import cli as engine

        def _raise(*a, **k):
            raise engine.subprocess.TimeoutExpired(cmd="hsync", timeout=5)

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_version("/fake/hsync") is None


class TestIsBinaryVersionCompatible:
    """Test the is_binary_version_compatible predicate."""

    def test_same_major_is_compatible(self):
        """A version sharing the desktop's major is compatible."""
        major = _EXPECTED_VERSION.split(".")[0]
        assert is_binary_version_compatible(f"{major}.99.99") is True

    def test_different_major_is_incompatible(self):
        """A different major version is incompatible."""
        bumped = f"{int(_EXPECTED_VERSION.split('.')[0]) + 1}.0.0"
        assert is_binary_version_compatible(bumped) is False


class TestBinaryProbeCache:
    """QSettings-backed caching for the binary version/capabilities probes."""

    def _patch_settings(self, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.engine import cli as engine

        settings = QSettings(str(tmp_path / "probe.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(engine, "_probe_settings", lambda: settings)
        return settings

    def _make_binary(self, tmp_path, content: str = "x") -> str:
        bin_path = tmp_path / "hsync"
        bin_path.write_text(content)
        return str(bin_path)

    def test_version_cache_miss_then_hit(self, tmp_path, monkeypatch):
        """A stable binary is probed once; the second call is a cache hit."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        calls = {"n": 0}

        def fake_version(p):
            calls["n"] += 1
            return "1.2.3"

        monkeypatch.setattr(engine, "get_binary_version", fake_version)
        assert engine.get_binary_version_cached(path) == "1.2.3"
        assert calls["n"] == 1
        assert engine.get_binary_version_cached(path) == "1.2.3"
        assert calls["n"] == 1

    def test_version_cache_invalidated_on_size_change(self, tmp_path, monkeypatch):
        """Replacing the binary (size change) forces a fresh probe."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        calls = {"n": 0}

        def fake_version(p):
            calls["n"] += 1
            return "1.2.3"

        monkeypatch.setattr(engine, "get_binary_version", fake_version)
        engine.get_binary_version_cached(path)
        with open(path, "a") as fh:
            fh.write("more")
        engine.get_binary_version_cached(path)
        assert calls["n"] == 2

    def test_version_cache_does_not_store_none(self, tmp_path, monkeypatch):
        """A failed probe (None) is never cached."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        calls = {"n": 0}

        def fake_version(p):
            calls["n"] += 1
            return None

        monkeypatch.setattr(engine, "get_binary_version", fake_version)
        assert engine.get_binary_version_cached(path) is None
        assert engine.get_binary_version_cached(path) is None
        assert calls["n"] == 2

    def test_capabilities_cache_hit_skips_probe(self, tmp_path, monkeypatch):
        """A parsed capabilities document is cached; a hit skips the subprocess."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        raw = '{"schema_version": 1, "app_version": "1.0.0"}'
        doc = {"schema_version": 1, "app_version": "1.0.0"}
        calls = {"n": 0}

        def fake_raw(p):
            calls["n"] += 1
            return raw

        monkeypatch.setattr(engine, "_get_binary_capabilities_raw", fake_raw)
        monkeypatch.setattr(engine, "parse_capabilities", lambda text: doc if text == raw else None)
        assert engine.get_binary_capabilities_cached(path) == doc
        assert calls["n"] == 1
        assert engine.get_binary_capabilities_cached(path) == doc
        assert calls["n"] == 1

    def test_binary_version_probe_cache_hit_emits_synchronously(self, tmp_path, monkeypatch):
        """A cache hit resolves without spawning a QProcess."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        monkeypatch.setattr(engine, "get_binary_version", lambda p: "3.1.4")
        engine.get_binary_version_cached(path)  # prime the cache
        received = []
        probe = engine.BinaryVersionProbe(path)
        probe.finished.connect(received.append)
        probe.start()
        assert received == ["3.1.4"]

    def test_binary_version_probe_qprocess(self, tmp_path, monkeypatch, qtbot):
        """A cache miss spawns a QProcess and emits the parsed version."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        stub = tmp_path / "stub"
        stub.write_text("#!/bin/sh\necho 'hsync 9.8.7'\n")
        stub.chmod(0o755)
        probe = engine.BinaryVersionProbe(str(stub))
        with qtbot.waitSignal(probe.finished, timeout=5000) as blocker:
            probe.start()
        assert blocker.args == ["9.8.7"]

    def test_binary_version_probe_timeout(self, tmp_path, monkeypatch, qtbot):
        """A hung binary is killed and the probe degrades to an empty version."""
        from hsync_desktop.engine import cli as engine

        self._patch_settings(tmp_path, monkeypatch)
        stub = tmp_path / "stub"
        stub.write_text("#!/bin/sh\nsleep 10\n")
        stub.chmod(0o755)
        monkeypatch.setattr(engine.BinaryVersionProbe, "_VERSION_PROBE_TIMEOUT_MS", 100)
        probe = engine.BinaryVersionProbe(str(stub))
        with qtbot.waitSignal(probe.finished, timeout=3000) as blocker:
            probe.start()
        assert blocker.args == [""]


class TestGetBinaryCapabilities:
    """Test get_binary_capabilities function."""

    def test_parses_valid_document(self, monkeypatch):
        """A well-formed --capabilities-json payload is parsed into a document."""
        import json

        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop.engine import cli as engine

        doc = build_capabilities(
            app_version="1.2.3",
            subcommands=["p2p"],
            cli_options_by_subcommand={"p2p": ["--prefer-master"]},
        )
        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout=json.dumps(doc))
        )
        parsed = get_binary_capabilities("/fake/hsync")
        assert parsed is not None
        assert parsed["cli_options"] == {"p2p": ["--prefer-master"]}

    def test_no_binary_returns_none(self, monkeypatch):
        """Missing binary yields no capabilities."""
        from hsync_desktop.engine import cli as engine

        monkeypatch.setattr(engine, "find_hsync_binary", lambda: None)
        assert get_binary_capabilities() is None

    def test_malformed_output_returns_none(self, monkeypatch):
        """Unparseable output degrades to None."""
        from hsync_desktop.engine import cli as engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="not json")
        )
        assert get_binary_capabilities("/fake/hsync") is None

    def test_os_error_returns_none(self, monkeypatch):
        """A failure to execute the binary returns None."""
        from hsync_desktop.engine import cli as engine

        def _raise(*a, **k):
            raise OSError("cannot exec")

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_capabilities("/fake/hsync") is None

    def test_timeout_returns_none(self, monkeypatch):
        """A timeout while querying the binary returns None."""
        from hsync_desktop.engine import cli as engine

        def _raise(*a, **k):
            raise engine.subprocess.TimeoutExpired(cmd="hsync", timeout=5)

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_capabilities("/fake/hsync") is None


class TestFetchRendezvousFingerprint:
    """The GUI pre-flight reads a rendezvous fingerprint without trusting it."""

    def test_returns_the_last_stdout_line_on_success(self, monkeypatch):
        import types

        calls: dict[str, list[str]] = {}

        def fake_run(args, **kwargs):
            calls["args"] = args
            return types.SimpleNamespace(returncode=0, stdout="noise line\nsha256:abc\n")

        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", fake_run)
        assert fetch_rendezvous_fingerprint("/bin/hsync", "boot.example.net") == "sha256:abc"
        assert calls["args"] == [
            "/bin/hsync",
            "trust",
            "rendezvous-server",
            "fingerprint",
            "boot.example.net",
        ]

    def test_passes_the_port_when_given(self, monkeypatch):
        import types

        calls: dict[str, list[str]] = {}

        def fake_run(args, **kwargs):
            calls["args"] = args
            return types.SimpleNamespace(returncode=0, stdout="sha256:abc\n")

        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", fake_run)
        fetch_rendezvous_fingerprint("/bin/hsync", "boot.example.net", 1443)
        assert calls["args"][-1] == "boot.example.net:1443"

    def test_returns_none_on_failure_or_empty_output(self, monkeypatch):
        import types

        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: types.SimpleNamespace(returncode=1, stdout=""),
        )
        assert fetch_rendezvous_fingerprint("/bin/hsync", "h") is None

        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="  \n"),
        )
        assert fetch_rendezvous_fingerprint("/bin/hsync", "h") is None

    def test_returns_none_when_the_binary_cannot_be_run(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("missing binary")

        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", boom)
        assert fetch_rendezvous_fingerprint("/bin/hsync", "h") is None


class TestTrustSubprocessHelpers:
    """The known-hosts / known-peers subprocess helpers (SSH-style trust)."""

    @staticmethod
    def _ok(stdout: str) -> object:
        import types

        return types.SimpleNamespace(returncode=0, stdout=stdout)

    def test_list_rendezvous_trust_returns_entries(self, monkeypatch):
        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: self._ok('[{"host": "b", "port": 443, "fingerprint": "f"}]'),
        )
        assert list_rendezvous_trust("/bin/hsync") == [
            {"host": "b", "port": 443, "fingerprint": "f"}
        ]

    def test_list_peer_pins_returns_entries(self, monkeypatch):
        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: self._ok('[{"cid": "c", "bucket": "bk", "fingerprint": "f"}]'),
        )
        assert list_peer_pins("/bin/hsync") == [{"cid": "c", "bucket": "bk", "fingerprint": "f"}]

    def test_list_returns_none_on_bad_json(self, monkeypatch):
        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: self._ok("not json"),
        )
        assert list_rendezvous_trust("/bin/hsync") is None
        assert list_peer_pins("/bin/hsync") is None

    def test_add_and_remove_return_success_flag(self, monkeypatch):
        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", lambda *a, **k: self._ok(""))
        assert add_rendezvous_trust("/bin/hsync", "b", "f" * 64) is True
        assert remove_rendezvous_trust("/bin/hsync", "b") is True
        assert add_peer_pin("/bin/hsync", "c", "bk", "f" * 64) is True
        assert remove_peer_pin("/bin/hsync", "c", "bk") is True

        import types

        monkeypatch.setattr(
            "hsync_desktop.engine.cli.subprocess.run",
            lambda *a, **k: types.SimpleNamespace(returncode=1, stdout=""),
        )
        assert add_rendezvous_trust("/bin/hsync", "b", "f" * 64) is False
        assert remove_peer_pin("/bin/hsync", "c", "bk") is False

    def test_supports_peer_trust_is_permissive_without_capabilities(self, monkeypatch):
        monkeypatch.setattr(
            "hsync_desktop.engine.cli.get_binary_capabilities_cached", lambda *a: None
        )
        assert supports_peer_trust("/bin/hsync") is True

    def test_supports_peer_trust_reads_subcommands(self, monkeypatch):
        doc = {"app": "hsync", "app_version": "1.0.0", "subcommands": ["server", "p2p"]}
        monkeypatch.setattr(
            "hsync_desktop.engine.cli.get_binary_capabilities_cached", lambda *a: doc
        )
        assert supports_peer_trust("/bin/hsync") is False

        doc["subcommands"].append("trust")
        assert supports_peer_trust("/bin/hsync") is True


class TestServerTrustSubprocessHelpers:
    """The server trust helpers use the ``hsync trust server`` namespace (ADR-0036)."""

    @staticmethod
    def _ok(stdout: str = "") -> object:
        import types

        return types.SimpleNamespace(returncode=0, stdout=stdout)

    def test_list_uses_the_trust_server_namespace(self, monkeypatch):
        import types

        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return self._ok("[]")

        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", fake_run)
        assert list_server_trust("/bin/hsync") == []
        assert calls[0] == ["/bin/hsync", "trust", "server", "list", "--json"]

    def test_add_and_remove_include_the_port(self, monkeypatch):
        import types

        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return self._ok("")

        monkeypatch.setattr("hsync_desktop.engine.cli.subprocess.run", fake_run)
        assert add_server_trust("/bin/hsync", "h", "f" * 64, 9753) is True
        assert remove_server_trust("/bin/hsync", "h", 9753) is True
        assert calls[0] == [
            "/bin/hsync",
            "trust",
            "server",
            "add",
            "h:9753",
            "f" * 64,
        ]
        assert calls[1] == [
            "/bin/hsync",
            "trust",
            "server",
            "remove",
            "h:9753",
        ]


class TestResetSyncState:
    """`hsync state reset` wrapper: JSON parsing, error text, capability gate."""

    def _patch(self, monkeypatch, result):
        from hsync_desktop.engine import cli as engine

        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return result

        monkeypatch.setattr(engine.subprocess, "run", fake_run)
        return calls

    def test_parses_the_json_summary(self, monkeypatch):
        calls = self._patch(
            monkeypatch,
            _FakeCompleted(
                stdout=(
                    '{"found": true, "versions_deleted": 12, '
                    '"tombstones_deleted": 3, "quarantined": ""}'
                )
            ),
        )

        from hsync_desktop.engine import reset_sync_state

        result = reset_sync_state("/bin/hsync", "/data/photos")

        assert calls[0] == [
            "/bin/hsync",
            "state",
            "reset",
            "--folder",
            "/data/photos",
            "--quarantine",
            "--json",
        ]
        assert result.ok is True
        assert result.found is True
        assert (result.versions, result.tombstones) == (12, 3)
        assert result.quarantined is False

    def test_empty_state_is_a_successful_noop(self, monkeypatch):
        self._patch(monkeypatch, _FakeCompleted(stdout='{"found": false}'))

        from hsync_desktop.engine import reset_sync_state

        result = reset_sync_state("/bin/hsync", "/data/photos")

        assert result.ok is True
        assert result.found is False

    def test_failure_carries_the_client_message(self, monkeypatch):
        self._patch(
            monkeypatch,
            _FakeCompleted(
                stderr="Another hsync process is already syncing '/data/photos' (pid 42).",
                returncode=1,
            ),
        )

        from hsync_desktop.engine import reset_sync_state

        result = reset_sync_state("/bin/hsync", "/data/photos")

        assert result.ok is False
        assert "already syncing" in result.message

    def test_malformed_json_is_a_failure(self, monkeypatch):
        self._patch(monkeypatch, _FakeCompleted(stdout="not json"))

        from hsync_desktop.engine import reset_sync_state

        assert reset_sync_state("/bin/hsync", "/data/photos").ok is False

    def test_quarantined_db_is_reported(self, monkeypatch):
        """An unreadable DB moved aside (``--quarantine``) is a successful reset."""
        self._patch(
            monkeypatch,
            _FakeCompleted(
                stdout=(
                    '{"found": true, "versions_deleted": 0, "tombstones_deleted": 0, '
                    '"quarantined": "/data/photos/.hsync-state.corrupt"}'
                )
            ),
        )

        from hsync_desktop.engine import reset_sync_state

        result = reset_sync_state("/bin/hsync", "/data/photos")

        assert result.ok is True
        assert result.quarantined is True

    def test_os_error_is_a_failure(self, monkeypatch):
        from hsync_desktop.engine import cli as engine

        def _raise(*a, **k):
            raise OSError("cannot exec")

        monkeypatch.setattr(engine.subprocess, "run", _raise)

        from hsync_desktop.engine import reset_sync_state

        assert reset_sync_state("/bin/hsync", "/data/photos").ok is False

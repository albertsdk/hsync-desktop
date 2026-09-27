# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

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
    apply_settings_env,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_version,
    is_binary_version_compatible,
    write_secret_pipe,
)


class TestTransferStats:
    """Test TransferStats dataclass."""

    def test_create_stats(self):
        """Test creating TransferStats with defaults."""
        stats = TransferStats()
        assert stats.files_sent == 0
        assert stats.files_received == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0

    def test_create_stats_with_values(self):
        """Test creating TransferStats with custom values."""
        stats = TransferStats(
            files_sent=10,
            files_received=5,
            bytes_sent=1000,
            bytes_received=2000,
        )
        assert stats.files_sent == 10
        assert stats.files_received == 5
        assert stats.bytes_sent == 1000
        assert stats.bytes_received == 2000

    def test_reset(self):
        """Test reset method."""
        stats = TransferStats(
            files_sent=10,
            files_received=5,
            bytes_sent=1000,
            bytes_received=2000,
        )
        stats.reset()
        assert stats.files_sent == 0
        assert stats.files_received == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0


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


class TestHsyncKeepConstant:
    """Test _HSYNCKEEP constant."""

    def test_hsynckeep_is_string(self):
        """Should be a string."""
        assert isinstance(_HSYNCKEEP, str)

    def test_hsynckeep_value(self):
        """Should match expected value."""
        assert _HSYNCKEEP == ".hsynckeep"


class _FakeCompleted:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout: str = "", stderr: str = ""):
        self.stdout = stdout
        self.stderr = stderr


class TestGetBinaryVersion:
    """Test get_binary_version function."""

    def test_parses_stdout(self, monkeypatch):
        """Should extract X.Y.Z from `hsync --version` stdout."""
        from hsync_desktop import engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="hsync 1.2.3\n")
        )
        assert get_binary_version("/fake/hsync") == "1.2.3"

    def test_parses_stderr(self, monkeypatch):
        """Should also look in stderr for the version string."""
        from hsync_desktop import engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stderr="hsync 2.0.5")
        )
        assert get_binary_version("/fake/hsync") == "2.0.5"

    def test_unparseable_returns_none(self, monkeypatch):
        """Output without a version returns None."""
        from hsync_desktop import engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="no version here")
        )
        assert get_binary_version("/fake/hsync") is None

    def test_os_error_returns_none(self, monkeypatch):
        """A failure to execute the binary returns None."""
        from hsync_desktop import engine

        def _raise(*a, **k):
            raise OSError("cannot exec")

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_version("/fake/hsync") is None

    def test_timeout_returns_none(self, monkeypatch):
        """A timeout while querying the binary returns None."""
        from hsync_desktop import engine

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

        from hsync_desktop import engine

        settings = QSettings(str(tmp_path / "probe.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(engine, "_probe_settings", lambda: settings)
        return settings

    def _make_binary(self, tmp_path, content: str = "x") -> str:
        bin_path = tmp_path / "hsync"
        bin_path.write_text(content)
        return str(bin_path)

    def test_version_cache_miss_then_hit(self, tmp_path, monkeypatch):
        """A stable binary is probed once; the second call is a cache hit."""
        from hsync_desktop import engine

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
        from hsync_desktop import engine

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
        from hsync_desktop import engine

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
        from hsync_desktop import engine

        self._patch_settings(tmp_path, monkeypatch)
        path = self._make_binary(tmp_path)
        raw = '{"schema_version": 2, "app_version": "1.0.0"}'
        doc = {"schema_version": 2, "app_version": "1.0.0"}
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
        from hsync_desktop import engine

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
        from hsync_desktop import engine

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
        from hsync_desktop import engine

        self._patch_settings(tmp_path, monkeypatch)
        stub = tmp_path / "stub"
        stub.write_text("#!/bin/sh\nsleep 10\n")
        stub.chmod(0o755)
        monkeypatch.setattr(engine.BinaryVersionProbe, "_VERSION_PROBE_TIMEOUT_MS", 100)
        probe = engine.BinaryVersionProbe(str(stub))
        with qtbot.waitSignal(probe.finished, timeout=3000) as blocker:
            probe.start()
        assert blocker.args == [""]


class _EnvFakeSettings:
    """Minimal QSettings stand-in for ``apply_settings_env`` (dict-backed)."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def value(self, key: str, default: object = None, type_: object = None) -> object:
        return self._values.get(key, default)


class TestApplySettingsEnv:
    """The engine injects the GUI-configured env vars into the subprocess."""

    def _env_with(self, values: dict[str, object]) -> QProcessEnvironment:
        env = QProcessEnvironment()
        apply_settings_env(env, _EnvFakeSettings(values))
        return env

    def test_ntp_hosts_inserted_when_set(self):
        env = self._env_with({"p2p/ntp_hosts": "ntp.local:123, ntp2.local"})
        assert env.value("HSYNC_NTP_HOSTS") == "ntp.local:123, ntp2.local"

    def test_ntp_hosts_blank_is_skipped(self):
        # A blank value must not insert an empty env var: the client then
        # falls back to its own defaults.
        env = self._env_with({"p2p/ntp_hosts": "   "})
        assert not env.contains("HSYNC_NTP_HOSTS")

    def test_ntp_hosts_missing_is_skipped(self):
        env = self._env_with({})
        assert not env.contains("HSYNC_NTP_HOSTS")

    def test_server_url_inserted_when_set(self):
        env = self._env_with({"connection/server_url": "https://srv.example"})
        assert env.value("HSYNC_SERVER") == "https://srv.example"

    def test_bootnode_inserted_with_upnp_choice(self):
        env = self._env_with({"p2p/bootnode": "boot.example.net", "p2p/upnp_enabled": False})
        assert env.value("HSYNC_BOOTNODE") == "boot.example.net"
        assert env.value("HSYNC_UPNP_ENABLED") == "false"

    def test_bootnode_defaults_upnp_on(self):
        env = self._env_with({"p2p/bootnode": "boot.example.net"})
        assert env.value("HSYNC_UPNP_ENABLED") == "true"

    def test_bootnode_blank_is_skipped(self):
        env = self._env_with({"p2p/bootnode": "   "})
        assert not env.contains("HSYNC_BOOTNODE")
        assert not env.contains("HSYNC_UPNP_ENABLED")

    def test_bootnode_fingerprint_and_tofu_exported(self):
        env = self._env_with(
            {
                "p2p/bootnode": "boot.example.net",
                "p2p/bootnode_fingerprint": "sha256:0" * 1 + "0" * 63,
                "p2p/bootnode_tofu": True,
            }
        )
        assert env.value("HSYNC_BOOTNODE_FINGERPRINT") == "sha256:0" + "0" * 63
        assert env.value("HSYNC_BOOTNODE_TOFU") == "true"

    def test_bootnode_fingerprint_blank_is_skipped(self):
        env = self._env_with({"p2p/bootnode": "boot.example.net", "p2p/bootnode_fingerprint": "  "})
        assert not env.contains("HSYNC_BOOTNODE_FINGERPRINT")
        assert not env.contains("HSYNC_BOOTNODE_TOFU")

    def test_no_values_inserts_nothing(self):
        env = self._env_with({})
        assert not env.contains("HSYNC_SERVER")
        assert not env.contains("HSYNC_NTP_HOSTS")
        assert not env.contains("HSYNC_BOOTNODE")

    def test_gui_value_overrides_ambient(self):
        # The GUI setting is the user's explicit choice: insert() overwrites
        # any pre-existing ambient value.
        env = QProcessEnvironment()
        env.insert("HSYNC_NTP_HOSTS", "ambient.local")
        apply_settings_env(env, _EnvFakeSettings({"p2p/ntp_hosts": "gui.local"}))
        assert env.value("HSYNC_NTP_HOSTS") == "gui.local"


class TestGetBinaryCapabilities:
    """Test get_binary_capabilities function."""

    def test_parses_valid_document(self, monkeypatch):
        """A well-formed --capabilities-json payload is parsed into a document."""
        import json

        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop import engine

        doc = build_capabilities(
            app_version="1.2.3",
            subcommands=["p2p"],
            cli_options_by_subcommand={"p2p": ["--force-master"]},
        )
        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout=json.dumps(doc))
        )
        parsed = get_binary_capabilities("/fake/hsync")
        assert parsed is not None
        assert parsed["cli_options"] == {"p2p": ["--force-master"]}

    def test_no_binary_returns_none(self, monkeypatch):
        """Missing binary yields no capabilities."""
        from hsync_desktop import engine

        monkeypatch.setattr(engine, "find_hsync_binary", lambda: None)
        assert get_binary_capabilities() is None

    def test_malformed_output_returns_none(self, monkeypatch):
        """Unparseable output degrades to None."""
        from hsync_desktop import engine

        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="not json")
        )
        assert get_binary_capabilities("/fake/hsync") is None

    def test_os_error_returns_none(self, monkeypatch):
        """A failure to execute the binary returns None."""
        from hsync_desktop import engine

        def _raise(*a, **k):
            raise OSError("cannot exec")

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_capabilities("/fake/hsync") is None

    def test_timeout_returns_none(self, monkeypatch):
        """A timeout while querying the binary returns None."""
        from hsync_desktop import engine

        def _raise(*a, **k):
            raise engine.subprocess.TimeoutExpired(cmd="hsync", timeout=5)

        monkeypatch.setattr(engine.subprocess, "run", _raise)
        assert get_binary_capabilities("/fake/hsync") is None


def _capture(signal) -> list:
    """Record every emission of *signal* as a tuple of its arguments."""
    received: list = []
    signal.connect(lambda *args: received.append(args))
    return received


class TestHandleEvent:
    """The structured events channel maps each event 1:1 to a Qt signal."""

    @pytest.fixture
    def engine(self, qtbot):
        """A HsyncEngine with a fixed binary path (no discovery side effects)."""
        return HsyncEngine(binary_path="/fake/hsync")

    def test_status_event(self, engine):
        out = _capture(engine.status_changed)
        engine._handle_event(build_event(UiEventName.status, status="connected"))
        assert out == [("connected",)]

    def test_peers_event_dedupes(self, engine):
        out = _capture(engine.peers_changed)
        engine._handle_event(build_event(UiEventName.peers, total=5, connected=3))
        engine._handle_event(build_event(UiEventName.peers, total=5, connected=3))
        engine._handle_event(build_event(UiEventName.peers, total=5, connected=5))
        assert out == [(3, 5), (5, 5)]

    def test_role_event_dedupes(self, engine):
        out = _capture(engine.master_changed)
        engine._handle_event(build_event(UiEventName.role, is_master=True))
        engine._handle_event(build_event(UiEventName.role, is_master=True))
        engine._handle_event(build_event(UiEventName.role, is_master=False))
        assert out == [(True,), (False,)]

    def test_discovery_event(self, engine):
        out = _capture(engine.discovery_changed)
        engine._handle_event(
            build_event(UiEventName.discovery, plan="bootnode", bootnode="boot.example.net")
        )
        engine._handle_event(build_event(UiEventName.discovery, plan="mdns"))
        assert out == [("bootnode", "boot.example.net"), ("mdns", "")]

    def test_bucket_and_group_events(self, engine):
        buckets = _capture(engine.bucket_detected)
        groups = _capture(engine.group_detected)
        engine._handle_event(build_event(UiEventName.bucket, bucket="b1"))
        engine._handle_event(build_event(UiEventName.group, group="g1"))
        assert buckets == [("b1",)]
        assert groups == [("g1",)]

    def test_session_event_sets_cid(self, engine):
        engine._handle_event(build_event(UiEventName.session, cid="abc123"))
        assert engine._cid == "abc123"

    def test_server_event_extracts_hostname(self, engine):
        engine._handle_event(build_event(UiEventName.server, url="https://example.com:8443/x"))
        assert engine._server_ip == "example.com"

    def test_transfer_download(self, engine):
        out = _capture(engine.file_transferred)
        engine._handle_event(
            build_event(UiEventName.transfer, op="download", file="f.txt", size=2048)
        )
        assert out == [("↓", "f.txt")]
        assert engine.stats.files_received == 1
        assert engine.stats.bytes_received == 2048

    def test_transfer_upload(self, engine):
        out = _capture(engine.file_transferred)
        engine._handle_event(
            build_event(UiEventName.transfer, op="upload", file="f.txt", size=1024)
        )
        assert out == [("↑", "f.txt")]
        assert engine.stats.files_sent == 1
        assert engine.stats.bytes_sent == 1024

    def test_transfer_delete(self, engine):
        out = _capture(engine.file_transferred)
        engine._handle_event(build_event(UiEventName.transfer, op="delete", file="f.txt"))
        assert out == [("✕", "f.txt")]

    def test_transfer_skips_hsynckeep(self, engine):
        out = _capture(engine.file_transferred)
        engine._handle_event(
            build_event(UiEventName.transfer, op="download", file=f"dir/{_HSYNCKEEP}", size=1)
        )
        assert out == []
        assert engine.stats.files_received == 0

    def test_rename_event(self, engine):
        out = _capture(engine.file_renamed)
        engine._handle_event(build_event(UiEventName.rename, src="old.txt", dst="new.txt"))
        assert out == [("old.txt", "new.txt")]

    def test_dir_created_event_and_skip(self, engine):
        out = _capture(engine.directory_created)
        engine._handle_event(build_event(UiEventName.dir_created, path="newdir/"))
        engine._handle_event(build_event(UiEventName.dir_created, path=f"d/{_HSYNCKEEP}"))
        assert out == [("newdir/",)]

    def test_progress_event(self, engine):
        out = _capture(engine.file_progress)
        engine._handle_event(
            build_event(UiEventName.progress, file="f.txt", transferred=10, total=100)
        )
        assert out == [("f.txt", 10, 100)]

    def test_sync_complete_event(self, engine):
        out = _capture(engine.sync_completed)
        engine._handle_event(build_event(UiEventName.sync_complete))
        assert out == [()]

    def test_error_event(self, engine):
        out = _capture(engine.error_occurred)
        engine._handle_event(build_event(UiEventName.error, message="boom"))
        assert out == [("boom",)]

    def test_transfer_failed_event(self, engine):
        out = _capture(engine.transfer_failed)
        engine._handle_event(
            build_event(
                UiEventName.transfer_failed,
                op="upload",
                file="f.txt",
                message="gave up",
            )
        )
        assert out == [("upload", "f.txt", "gave up")]

    def test_sync_paused_event(self, engine):
        out = _capture(engine.sync_paused)
        engine._handle_event(
            build_event(
                UiEventName.sync_paused,
                reason="master exposes an empty bucket",
                deletes=42,
                local=100,
            )
        )
        assert out == [("master exposes an empty bucket", 42, 100)]

    def test_path_not_found_event(self, engine):
        paths = _capture(engine.path_not_found)
        status = _capture(engine.status_changed)
        engine._handle_event(build_event(UiEventName.path_not_found, path="/missing"))
        assert paths == [("/missing",)]
        assert status == [("error",)]

    def test_master_conflict_event(self, engine):
        out = _capture(engine.master_conflict)
        engine._handle_event(
            build_event(
                UiEventName.master_conflict,
                conflict_type="conflict_lost",
                peer_cid="cid1",
                peer_address="1.2.3.4",
            )
        )
        assert out == [("conflict_lost", "cid1", "1.2.3.4")]

    def test_no_master_event(self, engine):
        out = _capture(engine.no_master_warning)
        engine._handle_event(build_event(UiEventName.no_master, elapsed=60))
        assert len(out) == 1

    def test_duplicate_identity_event(self, engine):
        out = _capture(engine.duplicate_identity)
        engine._handle_event(
            build_event(
                UiEventName.duplicate_identity,
                peer_cid="cid1",
                peer_address="1.2.3.4",
                message="duplicate",
            )
        )
        assert out == [("cid1", "1.2.3.4")]

    def test_unknown_event_is_ignored(self, engine):
        # Should not raise and should emit nothing observable.
        out = _capture(engine.status_changed)
        engine._handle_event({"schema_version": 1, "ts": "x", "event": "nope"})
        assert out == []

    def test_malformed_event_does_not_raise(self, engine):
        # A wrong-typed payload is swallowed (logged) rather than crashing.
        logs = _capture(engine.log_received)
        engine._handle_event({"schema_version": 1, "ts": "x", "event": "peers", "connected": "NaN"})
        assert any("EVENT ERROR" in args[0] for args in logs)


class TestWriteSecretPipe:
    """Secret pipe fds must survive QProcess fork+exec (not CLOEXEC)."""

    def test_read_fd_is_inheritable_and_delivers_eof(self):
        fd = write_secret_pipe("secret-value")
        try:
            assert os.get_inheritable(fd) is True
            assert os.read(fd, 64) == b"secret-value"
            assert os.read(fd, 64) == b""
        finally:
            os.close(fd)

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
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    apply_settings_env,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_version,
    is_binary_version_compatible,
    list_bootnode_trust,
    list_peer_pins,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    supports_peer_trust,
    write_secret_pipe,
)
from tests._helpers import _capture, _FakeCompleted


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

    def test_record_content_counts_distinct_paths(self):
        """The same path transferred twice is one distinct file, bytes add up."""
        stats = TransferStats()
        stats.record_content("upload", "a.txt", 100)
        stats.record_content("upload", "a.txt", 150)
        stats.record_content("upload", "b.txt", 0)
        assert stats.files_sent == 2
        assert stats.bytes_sent == 250

    def test_record_content_empty_key_keeps_bytes_only(self):
        """A transfer without a path never inflates the distinct-file count."""
        stats = TransferStats()
        stats.record_content("download", "", 42)
        assert stats.files_received == 0
        assert stats.bytes_received == 42

    def test_follow_rename_moves_identity(self):
        """A rename carries the tracked file to its new path without adding one."""
        stats = TransferStats()
        stats.record_content("upload", "old.txt", 10)
        stats.follow_rename("old.txt", "new.txt")
        assert stats.files_sent == 1
        stats.record_content("upload", "new.txt", 10)
        assert stats.files_sent == 1
        stats.record_content("upload", "other.txt", 5)
        assert stats.files_sent == 2

    def test_follow_rename_rewrites_directory_children(self):
        """Renaming a tracked directory moves its tracked descendants too."""
        stats = TransferStats()
        stats.record_content("download", "dir/a.txt", 1)
        stats.record_content("download", "dir/sub/b.txt", 1)
        stats.follow_rename("dir", "dir2")
        assert stats.files_received == 2
        assert stats.received_paths == {"dir2/a.txt", "dir2/sub/b.txt"}

    def test_follow_rename_untracked_is_noop(self):
        """A rename of an untracked path never invents a transferred file."""
        stats = TransferStats()
        stats.follow_rename("ghost.txt", "new.txt")
        assert stats.files_sent == 0
        assert stats.files_received == 0
        assert stats.sent_paths == set()

    def test_follow_rename_merge_drops_one(self):
        """Source and destination both tracked: the merge collapses to one."""
        stats = TransferStats()
        stats.record_content("upload", "old.txt", 1)
        stats.record_content("upload", "new.txt", 1)
        stats.follow_rename("old.txt", "new.txt")
        assert stats.files_sent == 1

    def test_reset_clears_sets(self):
        """Reset drops the tracked paths, not just the derived counts."""
        stats = TransferStats()
        stats.record_content("upload", "a.txt", 1)
        stats.record_content("download", "b.txt", 1)
        stats.reset()
        assert stats.sent_paths == set()
        assert stats.received_paths == set()
        assert stats.files_sent == 0
        assert stats.files_received == 0


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

    def test_bootnode_trust_defaults_to_ask(self):
        env = self._env_with({"p2p/bootnode": "boot.example.net"})
        assert env.value("HSYNC_BOOTNODE_TRUST") == "ask"

    def test_server_trust_policy_is_exported(self):
        env = self._env_with({"connection/server_trust": "strict"})
        assert env.value("HSYNC_SERVER_TRUST") == "strict"

    def test_server_trust_defaults_to_chain(self):
        env = self._env_with({})
        assert env.value("HSYNC_SERVER_TRUST") == "chain"

    def test_server_pin_is_not_exported_as_env(self):
        # The pin lives in the shared server known-hosts store, not a GUI env var.
        env = self._env_with(
            {
                "connection/server_cert_fingerprint": "sha256:" + "0" * 64,
                "connection/server_trust": "strict",
            }
        )
        assert not env.contains("HSYNC_SERVER_CERT_FINGERPRINT")
        assert not env.contains("HSYNC_SERVER_FINGERPRINT")

    def test_bootnode_pin_is_not_exported_as_env(self):
        # The pin lives in the shared known-hosts store, not in a GUI-only env
        # var: a stale HSYNC_BOOTNODE_FINGERPRINT setting must not be sent.
        env = self._env_with(
            {
                "p2p/bootnode": "boot.example.net",
                "p2p/bootnode_fingerprint": "sha256:" + "0" * 64,
                "p2p/bootnode_trust": "strict",
            }
        )
        assert not env.contains("HSYNC_BOOTNODE_FINGERPRINT")
        assert env.value("HSYNC_BOOTNODE_TRUST") == "strict"

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

    def test_auth_events_emit_the_matching_signals(self, engine):
        errors = _capture(engine.auth_error_occurred)
        required = _capture(engine.auth_required_occurred)
        statuses = _capture(engine.status_changed)
        engine._handle_event(build_event(UiEventName.auth_error, message="Invalid API key"))
        engine._handle_event(build_event(UiEventName.auth_required, message="key required"))
        assert errors == [("Invalid API key",)]
        assert required == [("key required",)]
        # Both auth failures put the UI into the error state.
        assert statuses == [("error",)]

    def test_security_rejected_event(self, engine):
        out = _capture(engine.security_rejected)
        engine._handle_event(
            build_event(
                UiEventName.security_rejected,
                op="download",
                path="../../etc/passwd",
                message="unsafe remote path rejected",
            )
        )
        assert out == [("download", "../../etc/passwd", "unsafe remote path rejected")]

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

    def test_repeated_transfer_counts_one_file(self, engine):
        """Ten transfers of one path are one distinct file; bytes keep summing."""
        engine._handle_event(
            build_event(UiEventName.transfer, op="download", file="f.txt", size=10)
        )
        engine._handle_event(build_event(UiEventName.transfer, op="download", file="f.txt", size=5))
        assert engine.stats.files_received == 1
        assert engine.stats.bytes_received == 15

    def test_rename_then_reupload_keeps_one_file(self, engine):
        """The engine follows a rename so a later transfer is not a new file."""
        engine._handle_event(build_event(UiEventName.transfer, op="upload", file="a.txt", size=1))
        engine._handle_event(build_event(UiEventName.rename, src="a.txt", dst="b.txt"))
        engine._handle_event(build_event(UiEventName.transfer, op="upload", file="b.txt", size=1))
        assert engine.stats.files_sent == 1

    def test_absolute_path_under_root_is_one_key(self, engine):
        """An absolute transfer path and its relative sibling collapse to one."""
        engine.local_root = "/bucket"
        engine._handle_event(
            build_event(UiEventName.transfer, op="download", file="/bucket/dir/f.txt", size=1)
        )
        engine._handle_event(
            build_event(UiEventName.transfer, op="download", file="dir/f.txt", size=1)
        )
        assert engine.stats.files_received == 1

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
        assert out == [("boom", "")]

    def test_error_event_carries_its_reason(self, engine):
        """A tagged error (e.g. a connection failure) keeps its reason."""
        out = _capture(engine.error_occurred)
        engine._handle_event(
            build_event(UiEventName.error, message="unreachable", reason="connection")
        )
        assert out == [("unreachable", "connection")]

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

    def test_no_peers_event(self, engine):
        """A p2p one-shot that found no peer is surfaced as its own signal."""
        out = _capture(engine.no_peers_warning)
        engine._handle_event(build_event(UiEventName.no_peers, message="none"))
        assert out == [("none",)]

    def test_duplicate_identity_event(self, engine):
        out = _capture(engine.duplicate_identity)
        engine._handle_event(
            build_event(
                UiEventName.duplicate_identity,
                peer_cid="cid1",
                peer_address="1.2.3.4",
            )
        )
        assert out == [("cid1", "1.2.3.4")]

    def test_pairing_needed_event(self, engine):
        out = _capture(engine.pairing_needed)
        engine._handle_event(
            build_event(
                UiEventName.pairing_needed,
                scope="master",
                peer_cid="cid1",
                peer_address="1.2.3.4",
                fingerprint="a" * 64,
            )
        )
        assert out == [("master", "cid1", "1.2.3.4", "a" * 64)]

    def test_fingerprint_changed_event(self, engine):
        out = _capture(engine.fingerprint_changed)
        engine._handle_event(
            build_event(
                UiEventName.fingerprint_changed,
                scope="bootnode",
                peer_address="boot.example.net:443",
                fingerprint="b" * 64,
            )
        )
        assert out == [("bootnode", "", "boot.example.net:443", "b" * 64)]

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

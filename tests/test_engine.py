# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.engine module."""

import pytest
from hsync_common.protocol.events import UiEventName, build_event

from hsync_desktop.engine import (
    _EXPECTED_VERSION,
    _HSYNCKEEP,
    HsyncEngine,
    TransferStats,
    check_binary_compatibility,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_version,
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


class TestCheckBinaryCompatibility:
    """Test check_binary_compatibility function."""

    def test_no_binary_is_compatible(self, monkeypatch):
        """Missing binary is treated as compatible with no version."""
        from hsync_desktop import engine

        monkeypatch.setattr(engine, "find_hsync_binary", lambda: None)
        assert check_binary_compatibility() == (True, None)

    def test_same_major_is_compatible(self, monkeypatch):
        """Same major version as expected is compatible."""
        from hsync_desktop import engine

        major = _EXPECTED_VERSION.split(".")[0]
        same_major = f"{major}.99.99"
        monkeypatch.setattr(engine, "get_binary_version", lambda p: same_major)
        assert check_binary_compatibility("/fake/hsync") == (True, same_major)

    def test_different_major_is_incompatible(self, monkeypatch):
        """A different major version is incompatible."""
        from hsync_desktop import engine

        bumped = f"{int(_EXPECTED_VERSION.split('.')[0]) + 1}.0.0"
        monkeypatch.setattr(engine, "get_binary_version", lambda p: bumped)
        assert check_binary_compatibility("/fake/hsync") == (False, bumped)

    def test_unparseable_version_is_compatible(self, monkeypatch):
        """When the binary version cannot be determined, do not block startup."""
        from hsync_desktop import engine

        monkeypatch.setattr(engine, "get_binary_version", lambda p: None)
        assert check_binary_compatibility("/fake/hsync") == (True, None)


class TestGetBinaryCapabilities:
    """Test get_binary_capabilities function (DESIGN_REVIEW §8)."""

    def test_parses_valid_document(self, monkeypatch):
        """A well-formed --capabilities-json payload is parsed into a document."""
        import json

        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop import engine

        doc = build_capabilities(app_version="1.2.3", cli_options=["--lan-mode"])
        monkeypatch.setattr(
            engine.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout=json.dumps(doc))
        )
        parsed = get_binary_capabilities("/fake/hsync")
        assert parsed is not None
        assert parsed["cli_options"] == ["--lan-mode"]

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
        engine._handle_event(build_event(UiEventName.peers, count=3))
        engine._handle_event(build_event(UiEventName.peers, count=3))
        engine._handle_event(build_event(UiEventName.peers, count=5))
        assert out == [(3,), (5,)]

    def test_role_event_dedupes(self, engine):
        out = _capture(engine.master_changed)
        engine._handle_event(build_event(UiEventName.role, is_master=True))
        engine._handle_event(build_event(UiEventName.role, is_master=True))
        engine._handle_event(build_event(UiEventName.role, is_master=False))
        assert out == [(True,), (False,)]

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

    def test_auth_error_event(self, engine):
        errors = _capture(engine.auth_error_occurred)
        status = _capture(engine.status_changed)
        engine._handle_event(build_event(UiEventName.auth_error, message="bad key"))
        assert errors == [("bad key",)]
        assert status == [("error",)]
        assert engine._auth_error_active is True

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

    def test_preview_lifecycle_and_file_status(self, engine):
        started = _capture(engine.preview_started)
        ended = _capture(engine.preview_ended)
        statuses = _capture(engine.file_status)
        renames = _capture(engine.file_rename_status)
        engine._handle_event(build_event(UiEventName.preview_start))
        engine._handle_event(
            build_event(UiEventName.file_status, state="to_download", file="f.txt", size=5)
        )
        engine._handle_event(build_event(UiEventName.rename_status, src="a", dst="b", size=7))
        engine._handle_event(build_event(UiEventName.preview_end))
        assert started == [()]
        assert ended == [()]
        assert statuses == [("to_download", "f.txt", 5)]
        assert renames == [("a", "b", 7)]
        assert engine._in_preview is False

    def test_unknown_event_is_ignored(self, engine):
        # Should not raise and should emit nothing observable.
        out = _capture(engine.status_changed)
        engine._handle_event({"schema_version": 1, "ts": "x", "event": "nope"})
        assert out == []

    def test_malformed_event_does_not_raise(self, engine):
        # A wrong-typed payload is swallowed (logged) rather than crashing.
        logs = _capture(engine.log_received)
        engine._handle_event({"schema_version": 1, "ts": "x", "event": "peers", "count": "NaN"})
        assert any("EVENT ERROR" in args[0] for args in logs)

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.engine module."""

import pytest

from hsync_desktop.engine import (
    _EXPECTED_VERSION,
    _HSYNCKEEP,
    _RE_AUTH_ERROR,
    _RE_BUCKET,
    _RE_CLIENT,
    _RE_CONNECTED,
    _RE_DIR_CREATE,
    _RE_DISCONNECTED,
    _RE_DOWNLOAD,
    _RE_ERROR,
    _RE_GROUP,
    _RE_LOG,
    _RE_MASTER,
    _RE_MASTER_CONFLICT,
    _RE_MASTER_TAKEOVER,
    _RE_MASTER_URL,
    _RE_NO_MASTER,
    _RE_PATH_NOT_FOUND,
    _RE_PEERS,
    _RE_PREVIEW_END,
    _RE_PREVIEW_START,
    _RE_REMOVE,
    _RE_RENAME,
    _RE_SERVER_URL,
    _RE_SESSION_CID,
    _RE_SYNC_COMPLETE,
    _RE_SYNCED,
    _RE_TO_DELETE,
    _RE_TO_DOWNLOAD,
    _RE_TO_RENAME,
    _RE_TO_UPLOAD,
    _RE_UPLOAD,
    _RE_WAITING,
    TransferStats,
    _parse_size,
    check_binary_compatibility,
    find_hsync_binary,
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


class TestParseSize:
    """Test _parse_size function."""

    def test_empty_input(self):
        """Test empty/None input returns 0."""
        assert _parse_size("") == 0
        assert _parse_size(None) == 0

    def test_bytes(self):
        """Test bytes parsing."""
        assert _parse_size("100") == 100
        assert _parse_size("0") == 0

    def test_kilobytes(self):
        """Test kilobytes parsing."""
        assert _parse_size("1KB") == 1024
        assert _parse_size("1 KB") == 1024
        assert _parse_size("1.5KB") == 1536
        assert _parse_size("10 KB") == 10240

    def test_megabytes(self):
        """Test megabytes parsing."""
        assert _parse_size("1MB") == 1048576
        assert _parse_size("1 MB") == 1048576
        assert _parse_size("1.5MB") == 1572864

    def test_gigabytes(self):
        """Test gigabytes parsing."""
        assert _parse_size("1GB") == 1073741824
        assert _parse_size("1 GB") == 1073741824

    def test_with_space(self):
        """Test values with spaces."""
        assert _parse_size("1.5 MB") == 1572864
        assert _parse_size("10 KB") == 10240


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


class TestRegexPatterns:
    """Test that all regex patterns are properly defined."""

    def test_log_pattern(self):
        """Test _RE_LOG pattern."""
        test_line = "2024-01-15T10:30:45.123Z - [12345] INFO: Some message"
        match = _RE_LOG.match(test_line)
        assert match is not None
        assert match.group(1) == "2024-01-15T10:30:45.123Z"
        assert match.group(2) == "12345"
        assert match.group(3) == "INFO"
        assert match.group(4) == "Some message"

    def test_peers_pattern(self):
        """Test _RE_PEERS pattern."""
        match = _RE_PEERS.search("Discovered 5 peer")
        assert match is not None
        assert match.group(1) == "5"

    def test_master_pattern(self):
        """Test _RE_MASTER pattern."""
        assert _RE_MASTER.search("I am the master") is not None
        assert _RE_MASTER.search("This client is the master") is not None
        assert _RE_MASTER.search("elected as master") is not None

    def test_client_pattern(self):
        """Test _RE_CLIENT pattern."""
        assert _RE_CLIENT.search("Master is at 192.168.1.1") is not None
        assert _RE_CLIENT.search("Connecting to master") is not None
        assert _RE_CLIENT.search("I am a client") is not None

    def test_bucket_pattern(self):
        """Test _RE_BUCKET pattern."""
        match = _RE_BUCKET.search("bucket 'my-bucket'")
        assert match is not None
        assert match.group(1) == "my-bucket"

    def test_group_pattern(self):
        """Test _RE_GROUP pattern."""
        match = _RE_GROUP.search("group = 'my-group'")
        assert match is not None
        assert match.group(1) == "my-group"

    def test_download_pattern(self):
        """Test _RE_DOWNLOAD pattern."""
        match = _RE_DOWNLOAD.search('[DOWNLOAD] "file.txt" 1.5MB')
        assert match is not None
        assert match.group(1) == "file.txt"
        assert match.group(2) == "1.5MB"

    def test_upload_pattern(self):
        """Test _RE_UPLOAD pattern."""
        match = _RE_UPLOAD.search('[UPLOAD] "file.txt" 1.5MB')
        assert match is not None
        assert match.group(1) == "file.txt"
        assert match.group(2) == "1.5MB"

    def test_remove_pattern(self):
        """Test _RE_REMOVE pattern."""
        match = _RE_REMOVE.search('[DELETE] "file.txt"')
        assert match is not None
        assert match.group(1) == "file.txt"

    def test_rename_pattern(self):
        """Test _RE_RENAME pattern."""
        match = _RE_RENAME.search('[RENAME] "old.txt" -> "new.txt"')
        assert match is not None
        assert match.group(1) == "old.txt"
        assert match.group(2) == "new.txt"

    def test_connected_pattern(self):
        """Test _RE_CONNECTED pattern."""
        assert _RE_CONNECTED.search("Connected to server") is not None
        assert _RE_CONNECTED.search("WebSocket connected") is not None

    def test_waiting_pattern(self):
        """Test _RE_WAITING pattern."""
        assert _RE_WAITING.search("Waiting for peers") is not None
        assert _RE_WAITING.search("No peers found") is not None
        assert _RE_WAITING.search("Searching for peers") is not None

    def test_disconnected_pattern(self):
        """Test _RE_DISCONNECTED pattern."""
        assert _RE_DISCONNECTED.search("WebSocket disconnected") is not None
        assert _RE_DISCONNECTED.search("Connection closed") is not None
        assert _RE_DISCONNECTED.search("All peers disconnected") is not None

    def test_sync_complete_pattern(self):
        """Test _RE_SYNC_COMPLETE pattern."""
        assert _RE_SYNC_COMPLETE.search("Sync complete") is not None
        assert _RE_SYNC_COMPLETE.search("All files in sync") is not None

    def test_error_pattern(self):
        """Test _RE_ERROR pattern."""
        match = _RE_ERROR.search("ERROR: Something went wrong")
        assert match is not None
        assert match.group(1) == "Something went wrong"

    def test_auth_error_pattern(self):
        """Test _RE_AUTH_ERROR pattern."""
        assert _RE_AUTH_ERROR.search("Invalid API key") is not None
        assert _RE_AUTH_ERROR.search("API key required") is not None
        assert _RE_AUTH_ERROR.search("Authentication failed") is not None

    def test_path_not_found_pattern(self):
        """Test _RE_PATH_NOT_FOUND pattern."""
        match = _RE_PATH_NOT_FOUND.search("Directory '/path' does not exist")
        assert match is not None
        assert match.group(1) == "/path"

    def test_master_conflict_pattern(self):
        """Test _RE_MASTER_CONFLICT pattern."""
        match = _RE_MASTER_CONFLICT.search("[MASTER_CONFLICT] another master abc123 at 192.168.1.1")
        assert match is not None

    def test_master_takeover_pattern(self):
        """Test _RE_MASTER_TAKEOVER pattern."""
        match = _RE_MASTER_TAKEOVER.search("[MASTER_TAKEOVER] peer abc123 at 192.168.1.1")
        assert match is not None

    def test_no_master_pattern(self):
        """Test _RE_NO_MASTER pattern."""
        match = _RE_NO_MASTER.search(
            "[NO_MASTER] No master elected after 60s. All discovered peers "
            "may be configured with --never-master."
        )
        assert match is not None
        assert match.group(1).startswith("No master elected")

    def test_session_cid_pattern(self):
        """Test _RE_SESSION_CID pattern."""
        match = _RE_SESSION_CID.search("Session CID: abc123")
        assert match is not None
        assert match.group(1) == "abc123"

    def test_server_url_pattern(self):
        """Test _RE_SERVER_URL pattern."""
        match = _RE_SERVER_URL.search("Checking server connectivity: https://example.com")
        assert match is not None

    def test_preview_start_pattern(self):
        """Test _RE_PREVIEW_START pattern."""
        match = _RE_PREVIEW_START.search("--- Preview (dry-run) ---")
        assert match is not None

    def test_preview_end_pattern(self):
        """Test _RE_PREVIEW_END pattern."""
        match = _RE_PREVIEW_END.search("--- End Preview ---")
        assert match is not None

    def test_synced_pattern(self):
        """Test _RE_SYNCED pattern."""
        match = _RE_SYNCED.search('[SYNCED] "file.txt" (1.5MB)')
        assert match is not None
        assert match.group(1) == "file.txt"
        assert match.group(2) == "1.5MB"

    def test_to_download_pattern(self):
        """Test _RE_TO_DOWNLOAD pattern."""
        match = _RE_TO_DOWNLOAD.search('[TO_DOWNLOAD] "file.txt" (1.5MB)')
        assert match is not None
        assert match.group(1) == "file.txt"

    def test_to_upload_pattern(self):
        """Test _RE_TO_UPLOAD pattern."""
        match = _RE_TO_UPLOAD.search('[TO_UPLOAD] "file.txt" (1.5MB)')
        assert match is not None

    def test_to_delete_pattern(self):
        """Test _RE_TO_DELETE pattern."""
        match = _RE_TO_DELETE.search('[TO_DELETE] "file.txt" (1.5MB)')
        assert match is not None

    def test_to_rename_pattern(self):
        """Test _RE_TO_RENAME pattern."""
        match = _RE_TO_RENAME.search('[TO_RENAME] "old.txt" -> "new.txt" (1.5MB)')
        assert match is not None
        assert match.group(1) == "old.txt"
        assert match.group(2) == "new.txt"
        assert match.group(3) == "1.5MB"

    def test_dir_create_pattern(self):
        """Test _RE_DIR_CREATE pattern."""
        match = _RE_DIR_CREATE.search('[CREATE] "newdir/"')
        assert match is not None
        assert match.group(1) == "newdir/"


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

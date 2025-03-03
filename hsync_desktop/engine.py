# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
HSYNC Engine - subprocess bridge to hsync-client.

Manages the hsync-client binary as a child process, captures its
stdout/stderr in real-time, parses log output and emits Qt signals
so the UI can react to state changes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QSettings, Signal, Slot

from hsync_desktop.crypto import decrypt_value


# ─── Stats dataclass ────────────────────────────────────────────────────────

@dataclass
class TransferStats:
    """Cumulative transfer statistics."""
    files_sent: int = 0
    files_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

    def reset(self) -> None:
        self.files_sent = self.files_received = 0
        self.bytes_sent = self.bytes_received = 0


# Sentinel filename – must match the client constant.  Hardcoded here to avoid
# importing from the client package (different virtualenv / install).
_HSYNCKEEP = ".hsynckeep"

# ─── Log-line regex patterns ────────────────────────────────────────────────

# Timestamp prefix: 2024-01-15T10:30:45.123Z - [PID] LEVEL: msg
_RE_LOG = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s*-\s*"
    r"\[(\d+)\]\s*"
    r"(\w+):\s*(.*)$"
)

_RE_PEERS = re.compile(r"Discovered\s+(\d+)\s+peer")
_RE_MASTER = re.compile(r"I am the (?:new )?master|This client is the master|elected as master", re.I)
_RE_SLAVE = re.compile(r"Master is |Connecting to master|I am a slave", re.I)
_RE_BUCKET = re.compile(r"bucket\s+'([^']+)'", re.I)
_RE_GROUP = re.compile(r"group\s*=\s*'([^']+)'", re.I)
_RE_DOWNLOAD = re.compile(r'\[DOWNLOAD\s*\]\s*"(.+?)"\s+(\S+)\s*$')
_RE_UPLOAD = re.compile(r'\[UPLOAD\s*\]\s*"(.+?)"\s+(\S+)\s*$')
_RE_REMOVE = re.compile(r'\[DELETE\s*\]\s*"(.+?)"')
_RE_RENAME = re.compile(r'\[(?:LAN )?RENAME\s*\]\s*"(.+?)"\s*->\s*"(.+?)"')
_RE_CONNECTED = re.compile(r"Connected to server|WebSocket connected|Initial sync complete", re.I)
_RE_WAITING = re.compile(r"Waiting for peers|No peers found|Searching for peers", re.I)
_RE_DISCONNECTED = re.compile(
    r"WebSocket disconnected|Connection closed|WebSocket connection ended|"
    r"All peers disconnected|re-entering discovery loop",
    re.I,
)
_RE_SYNC_COMPLETE = re.compile(r"Sync complete|All files in sync|Initial sync complete", re.I)
_RE_ERROR = re.compile(r"ERROR:\s*(.+)")
_RE_AUTH_ERROR = re.compile(r"Invalid API key|API key required|Authentication.*failed|401.*Unauthorized", re.I)
_RE_PATH_NOT_FOUND = re.compile(r"Directory '(.+?)' does not exist")

# Master conflict patterns
_RE_MASTER_CONFLICT = re.compile(
    r"\[MASTER_CONFLICT\].*?(?:another master|peer)\s+(\S+)\s+at\s+(\S+)"
)
_RE_MASTER_TAKEOVER = re.compile(
    r"\[MASTER_TAKEOVER\].*?peer\s+(\S+)\s+at\s+(\S+)"
)

# Session CID pattern
_RE_SESSION_CID = re.compile(r"Session CID:\s*(\S+)")

# Server URL patterns – extract hostname for the detail panel
_RE_SERVER_URL = re.compile(r"Checking server connectivity:\s*(https?://\S+)", re.I)
_RE_MASTER_URL = re.compile(r"Connecting to master:.*?at\s+(https?://\S+)", re.I)

# Directory creation patterns
_RE_DIR_CREATE = re.compile(r'\[(?:LAN )?CREATE\s*\]\s*"(.+?)"')

# Preview status patterns (emitted by PREVIEW stdin command)
_RE_PREVIEW_START = re.compile(r"--- Preview \(dry-run\) ---")
_RE_PREVIEW_END = re.compile(r"--- End Preview ---")
_RE_SYNCED = re.compile(r'\[SYNCED\s*\]\s*"(.+?)"\s*\(([^)]+)\)')
_RE_TO_DOWNLOAD = re.compile(r'\[TO_DOWNLOAD\s*\]\s*"(.+?)"\s*\(([^)]+)\)')
_RE_TO_UPLOAD = re.compile(r'\[TO_UPLOAD\s*\]\s*"(.+?)"\s*\(([^)]+)\)')
_RE_TO_DELETE = re.compile(r'\[TO_DELETE\s*\]\s*"(.+?)"\s*\(([^)]+)\)')
_RE_TO_RENAME = re.compile(r'\[TO_RENAME\s*\]\s*"(.+?)"\s*->\s*"(.+?)"\s*\(([^)]+)\)')


def _parse_size(text: str | None) -> int:
    """Parse human-readable size like '1.2MB' or '1.2 MB' to bytes."""
    if not text:
        return 0
    text = text.strip()
    # Check longer suffixes first to avoid "KB" matching "B" first
    multipliers = [("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]
    for suffix, mult in multipliers:
        if text.upper().endswith(suffix):
            try:
                return int(float(text[: -len(suffix)].strip()) * mult)
            except ValueError:
                return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


# ─── Default binary discovery ───────────────────────────────────────────────

def find_hsync_binary() -> str | None:
    """Locate the hsync binary: bundled → PATH → sibling project dist."""
    # 1. Bundled alongside this package
    pkg_dir = Path(__file__).resolve().parent
    bundled = pkg_dir / "bin" / "hsync"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    # 2. On PATH
    on_path = shutil.which("hsync")
    if on_path:
        return on_path
    # 3. Sibling project dist/
    sibling = pkg_dir.parent.parent / "hsync-client" / "dist" / "hsync"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)
    return None


# ─── Engine ──────────────────────────────────────────────────────────────────


class HsyncEngine(QObject):
    """
    Manages the hsync-client subprocess.

    Start/stop the binary, capture log output in real-time, parse
    status information and expose it via Qt signals.
    """

    # ── Signals ──────────────────────────────────────────────────────────
    log_received = Signal(str)              # raw log line
    status_changed = Signal(str)            # disconnected|connecting|connected|waiting|error
    peers_changed = Signal(int)             # number of alive peers
    master_changed = Signal(bool)           # True ⇒ this client is master
    bucket_detected = Signal(str)           # bucket name
    group_detected = Signal(str)            # LAN group name
    file_transferred = Signal(str, str)     # direction ("↓"|"↑"|"✕"), filename
    file_renamed = Signal(str, str)         # old_path, new_path
    directory_created = Signal(str)         # directory path
    sync_completed = Signal()               # a full sync cycle finished
    error_occurred = Signal(str)            # error message
    auth_error_occurred = Signal(str)       # authentication error (invalid/missing API key)
    path_not_found = Signal(str)            # shared path does not exist
    process_finished = Signal(int, str)     # exit code, exit status description
    master_conflict = Signal(str, str, str)  # conflict_type, peer_cid, peer_address

    # Preview signals (emitted during dry-run preview)
    preview_started = Signal()                      # preview scan started
    preview_ended = Signal()                        # preview scan ended
    file_status = Signal(str, str, int)             # status, filepath, size
    # status can be: "synced", "to_download", "to_upload", "to_delete"
    file_rename_status = Signal(str, str, int)       # old_path, new_path, size

    # ── Lifecycle ────────────────────────────────────────────────────────

    def __init__(self, binary_path: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._binary = binary_path or find_hsync_binary()
        self._process: QProcess | None = None
        self._running = False
        self._stopping = False  # True when stop() was called programmatically
        self._auth_error_active = False  # True when auth error is being handled
        self._is_master = False
        self._peers = 0
        self._status = "disconnected"
        self._in_preview = False
        self._cid = ""
        self._server_ip = ""
        self.stats = TransferStats()

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_master(self) -> bool:
        return self._is_master

    @property
    def peer_count(self) -> int:
        return self._peers

    @property
    def status(self) -> str:
        return self._status

    @property
    def cid(self) -> str:
        return self._cid

    @property
    def server_ip(self) -> str:
        return self._server_ip

    @property
    def binary_path(self) -> str | None:
        return self._binary

    @binary_path.setter
    def binary_path(self, path: str) -> None:
        self._binary = path

    # ── Start / Stop ─────────────────────────────────────────────────────

    def start(self, args: list[str]) -> bool:
        """Start the hsync-client with the given CLI arguments.

        Returns True if the process was launched successfully.
        """
        if self._running:
            return False
        if not self._binary:
            self.error_occurred.emit("hsync binary not found.")
            return False

        self.stats.reset()
        self._is_master = False
        self._peers = 0
        self._stopping = False
        self._auth_error_active = False
        self._set_status("connecting")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        # Inject environment variables from QSettings so that hsync-client
        # picks up values configured in the desktop GUI.
        env = QProcessEnvironment.systemEnvironment()
        s = QSettings("HSYNC", "HSYNCDesktop")
        server_url = s.value("connection/server_url", "", str)
        if server_url:
            env.insert("HSYNC_SERVER", str(server_url))
        proc.setProcessEnvironment(env)

        # Pass secrets via pipe file descriptors so they never appear in
        # process arguments (visible in ``ps``) or environment variables
        # (visible in ``/proc/<pid>/environ``).
        pipe_fds: list[int] = []

        api_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        if api_key:
            read_fd, write_fd = os.pipe()
            try:
                os.write(write_fd, api_key.encode("utf-8"))
            finally:
                os.close(write_fd)
            os.set_inheritable(read_fd, True)
            pipe_fds.append(read_fd)
            args = [*args, "--api-key-fd", str(read_fd)]

        lan_key = str(s.value("lan/key", "", str))
        if lan_key:
            read_fd, write_fd = os.pipe()
            try:
                os.write(write_fd, lan_key.encode("utf-8"))
            finally:
                os.close(write_fd)
            os.set_inheritable(read_fd, True)
            pipe_fds.append(read_fd)
            args = [*args, "--lan-key-fd", str(read_fd)]

        proc.start(self._binary, args)
        if not proc.waitForStarted(5000):
            for fd in pipe_fds:
                os.close(fd)
            self.error_occurred.emit("Failed to start hsync process.")
            self._set_status("error")
            return False

        # Close parent's copy of the read fds – child already inherited them.
        for fd in pipe_fds:
            os.close(fd)

        self._process = proc
        self._running = True
        return True

    def stop(self) -> None:
        """Gracefully stop the running process (SIGTERM, then SIGKILL)."""
        if not self._process or not self._running:
            return
        self._stopping = True
        # On Unix send SIGTERM; on Windows terminate()
        pid = self._process.processId()
        if pid and hasattr(signal, "SIGTERM"):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                self._process.terminate()
        else:
            self._process.terminate()
        if not self._process.waitForFinished(5000):
            self._process.kill()
            self._process.waitForFinished(3000)

    def force_sync(self) -> None:
        """Trigger an immediate full sync via stdin command.

        Sends a SYNC command to the running process, which will execute
        a full synchronisation cycle without restarting.
        """
        self.sync()

    def sync(self) -> None:
        """Send SYNC command to the running process.

        In dry-run mode this switches the process to real sync mode
        and performs the synchronisation.  In normal mode it triggers
        an additional full sync cycle.
        """
        self._send_command({"cmd": "SYNC"})

    def preview(self) -> None:
        """Trigger a preview (dry-run) by sending a PREVIEW command via stdin."""
        self._send_command({"cmd": "PREVIEW"})

    def set_sync_direction(self, direction: str) -> None:
        """Change the sync direction at runtime via stdin command.

        Args:
            direction: One of "bidirectional", "upload-only", "download-only".
        """
        self._send_command({"cmd": "SET_SYNC_DIRECTION", "direction": direction})

    # ── Stdin command channel ────────────────────────────────────────

    def _send_command(self, cmd: dict) -> None:
        """Send a JSON command to the hsync-client process via stdin.

        The hsync-client reads one JSON object per line from stdin and
        dispatches it to the matching handler.
        """
        if not self._process or not self._running:
            return
        data = json.dumps(cmd, separators=(",", ":")) + "\n"
        self._process.write(data.encode("utf-8"))

    # ── Internal slots ───────────────────────────────────────────────────

    @Slot()
    def _on_stdout(self) -> None:
        if not self._process:
            return
        data = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.rstrip()
            if line:
                self.log_received.emit(line)
                self._parse_line(line)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._running = False
        if exit_status == QProcess.ExitStatus.NormalExit:
            desc = "normal"
        elif self._stopping:
            desc = "stopped"
        else:
            desc = "crashed"
        self._stopping = False
        self._set_status("disconnected")
        self.process_finished.emit(exit_code, desc)

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        # Suppress "Crashed" errors when the stop was initiated by us
        # (user stop, auth error handling, force sync, app quit, etc.)
        if error == QProcess.ProcessError.Crashed and self._stopping:
            return
        mapping = {
            QProcess.ProcessError.FailedToStart: "Failed to start",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error",
        }
        self.error_occurred.emit(mapping.get(error, "Unknown error"))
        self._set_status("error")

    # ── Log parsing ──────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.status_changed.emit(status)

    def _parse_line(self, line: str) -> None:
        """Parse a single log line and emit signals as needed."""
        try:
            self._parse_line_inner(line)
        except Exception as e:
            # Log parsing errors should not crash the engine
            # Just log and continue processing
            self.log_received.emit(f"[PARSE ERROR] {line[:100]}")

    def _parse_line_inner(self, line: str) -> None:
        """Internal method to parse a single log line."""
        # Strip ANSI escape codes for pattern matching
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)

        # Preview start/end
        if _RE_PREVIEW_START.search(clean):
            self._in_preview = True
            self.preview_started.emit()
            return
        if _RE_PREVIEW_END.search(clean):
            self._in_preview = False
            self.preview_ended.emit()
            return

        # Preview file status messages
        if self._in_preview:
            m = _RE_SYNCED.search(clean)
            if m:
                self.file_status.emit("synced", m.group(1), _parse_size(m.group(2)))
                return
            m = _RE_TO_DOWNLOAD.search(clean)
            if m:
                self.file_status.emit("to_download", m.group(1), _parse_size(m.group(2)))
                return
            m = _RE_TO_UPLOAD.search(clean)
            if m:
                self.file_status.emit("to_upload", m.group(1), _parse_size(m.group(2)))
                return
            m = _RE_TO_RENAME.search(clean)
            if m:
                self.file_rename_status.emit(m.group(1), m.group(2), _parse_size(m.group(3)))
                return
            m = _RE_TO_DELETE.search(clean)
            if m:
                self.file_status.emit("to_delete", m.group(1), _parse_size(m.group(2)))
                return

        # Session CID
        m = _RE_SESSION_CID.search(clean)
        if m:
            self._cid = m.group(1)

        # Server / master URL → extract hostname for IP display
        m = _RE_SERVER_URL.search(clean)
        if not m:
            m = _RE_MASTER_URL.search(clean)
        if m:
            from urllib.parse import urlparse
            parsed = urlparse(m.group(1))
            self._server_ip = parsed.hostname or ""

        # Directory creation
        m = _RE_DIR_CREATE.search(clean)
        if m and not m.group(1).strip().endswith(_HSYNCKEEP):
            self.directory_created.emit(m.group(1).strip())

        # Peer count
        m = _RE_PEERS.search(clean)
        if m:
            count = int(m.group(1))
            if count != self._peers:
                self._peers = count
                self.peers_changed.emit(count)

        # Master / slave detection
        if _RE_MASTER.search(clean):
            if not self._is_master:
                self._is_master = True
                self.master_changed.emit(True)
        elif _RE_SLAVE.search(clean):
            if self._is_master:
                self._is_master = False
                self.master_changed.emit(False)

        # Bucket name
        m = _RE_BUCKET.search(clean)
        if m:
            self.bucket_detected.emit(m.group(1))

        # Group name
        m = _RE_GROUP.search(clean)
        if m:
            self.group_detected.emit(m.group(1))

        # Downloads (actual transfer complete)
        m = _RE_DOWNLOAD.search(clean)
        if m and not m.group(1).strip().endswith(_HSYNCKEEP):
            self.stats.files_received += 1
            self.stats.bytes_received += _parse_size(m.group(2))
            self.file_transferred.emit("↓", m.group(1).strip())

        # Uploads (actual transfer complete)
        m = _RE_UPLOAD.search(clean)
        if m and not m.group(1).strip().endswith(_HSYNCKEEP):
            self.stats.files_sent += 1
            self.stats.bytes_sent += _parse_size(m.group(2))
            self.file_transferred.emit("↑", m.group(1).strip())

        # Renames (file/directory renamed)
        m = _RE_RENAME.search(clean)
        if m:
            self.file_renamed.emit(m.group(1).strip(), m.group(2).strip())
            return

        # Removals (actual deletion)
        m = _RE_REMOVE.search(clean)
        if m and not m.group(1).strip().endswith(_HSYNCKEEP):
            self.file_transferred.emit("✕", m.group(1).strip())

        # Connection status
        if _RE_CONNECTED.search(clean):
            self._set_status("connected")
        elif _RE_DISCONNECTED.search(clean):
            self._set_status("waiting")
        elif _RE_WAITING.search(clean):
            self._set_status("waiting")

        # Sync complete
        if _RE_SYNC_COMPLETE.search(clean):
            self.sync_completed.emit()

        # Master conflict warnings
        m = _RE_MASTER_CONFLICT.search(clean)
        if m:
            # Determine conflict subtype from log message
            if "This client wins" in clean:
                ctype = "conflict_won"
            else:
                ctype = "conflict_lost"
            self.master_conflict.emit(ctype, m.group(1), m.group(2))
        m = _RE_MASTER_TAKEOVER.search(clean)
        if m:
            self.master_conflict.emit("takeover", m.group(1), m.group(2))

        # Path-not-found error (check before generic errors)
        m = _RE_PATH_NOT_FOUND.search(clean)
        if m:
            self.path_not_found.emit(m.group(1))
            self._set_status("error")
            return

        # Authentication errors (check before generic errors)
        if _RE_AUTH_ERROR.search(clean):
            self._auth_error_active = True
            self.auth_error_occurred.emit(clean)
            self._set_status("error")
            return

        # Errors
        m = _RE_ERROR.search(clean)
        if m and "ERROR" in clean:
            self.error_occurred.emit(m.group(1))


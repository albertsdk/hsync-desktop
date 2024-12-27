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

import os
import re
import shutil
import signal
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, Slot


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


# ─── Log-line regex patterns ────────────────────────────────────────────────

# Timestamp prefix: 2024-01-15T10:30:45.123Z - [PID] [CID] LEVEL: msg
_RE_LOG = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s*-\s*"
    r"\[(\d+)\]\s*\[([^\]]+)\]\s*"
    r"(\w+):\s*(.*)$"
)

_RE_PEERS = re.compile(r"Discovered\s+(\d+)\s+peer")
_RE_MASTER = re.compile(r"I am the (?:new )?master|This client is the master|elected as master", re.I)
_RE_SLAVE = re.compile(r"Master is |Connecting to master|I am a slave", re.I)
_RE_BUCKET = re.compile(r"bucket\s+'([^']+)'", re.I)
_RE_GROUP = re.compile(r"group\s*=\s*'([^']+)'", re.I)
_RE_DOWNLOAD = re.compile(r"↓\s*\[DOWNLOAD\s*\]\s*(.+?)(?:\s+\(([^)]+)\))?$")
_RE_UPLOAD = re.compile(r"↑\s*\[UPLOAD\s*\]\s*(.+?)(?:\s+\(([^)]+)\))?$")
_RE_REMOVE = re.compile(r"✕\s*\[REMOVE\s*\]\s*(.+)")
_RE_CONNECTED = re.compile(r"Connected to server|WebSocket connected|Initial sync complete", re.I)
_RE_WAITING = re.compile(r"Waiting for peers|No peers found|Searching for peers", re.I)
_RE_SYNC_COMPLETE = re.compile(r"Sync complete|All files in sync|Initial sync complete", re.I)
_RE_ERROR = re.compile(r"ERROR:\s*(.+)")


def _parse_size(text: str | None) -> int:
    """Parse human-readable size like '1.2 MB' to bytes."""
    if not text:
        return 0
    text = text.strip()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for suffix, mult in multipliers.items():
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
    sync_completed = Signal()               # a full sync cycle finished
    error_occurred = Signal(str)            # error message
    process_finished = Signal(int, str)     # exit code, exit status description

    # ── Lifecycle ────────────────────────────────────────────────────────

    def __init__(self, binary_path: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._binary = binary_path or find_hsync_binary()
        self._process: QProcess | None = None
        self._running = False
        self._is_master = False
        self._peers = 0
        self._status = "disconnected"
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
        self._set_status("connecting")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        proc.start(self._binary, args)
        if not proc.waitForStarted(5000):
            self.error_occurred.emit("Failed to start hsync process.")
            self._set_status("error")
            return False

        self._process = proc
        self._running = True
        return True

    def stop(self) -> None:
        """Gracefully stop the running process (SIGTERM, then SIGKILL)."""
        if not self._process or not self._running:
            return
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
        """Trigger an immediate full re-sync by restarting the process."""
        # hsync-client doesn't expose a signal for this, so we restart
        if not self._running or not self._process:
            return
        args = self._process.arguments()
        self.stop()
        self.start(args)

    def preview(self) -> None:
        """Trigger a preview (dry-run) by sending SIGUSR1 to the running process.

        On Unix, this sends SIGUSR1 which the hsync-client handles by running
        a preview that shows pending sync actions without performing transfers.
        On Windows, SIGUSR1 is not available so this is a no-op.
        """
        if not self._process or not self._running:
            return
        pid = self._process.processId()
        if pid and hasattr(signal, "SIGUSR1"):
            try:
                os.kill(pid, signal.SIGUSR1)
            except OSError as e:
                self.error_occurred.emit(f"Failed to send preview signal: {e}")

    # ── Internal slots ───────────────────────────────────────────────────

    @Slot()
    def _on_stdout(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.rstrip()
            if line:
                self.log_received.emit(line)
                self._parse_line(line)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._running = False
        desc = "normal" if exit_status == QProcess.ExitStatus.NormalExit else "crashed"
        self._set_status("disconnected")
        self.process_finished.emit(exit_code, desc)

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
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
        # Strip ANSI escape codes for pattern matching
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)

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

        # Downloads
        m = _RE_DOWNLOAD.search(clean)
        if m:
            self.stats.files_received += 1
            self.stats.bytes_received += _parse_size(m.group(2))
            self.file_transferred.emit("↓", m.group(1).strip())

        # Uploads
        m = _RE_UPLOAD.search(clean)
        if m:
            self.stats.files_sent += 1
            self.stats.bytes_sent += _parse_size(m.group(2))
            self.file_transferred.emit("↑", m.group(1).strip())

        # Removals
        m = _RE_REMOVE.search(clean)
        if m:
            self.file_transferred.emit("✕", m.group(1).strip())

        # Connection status
        if _RE_CONNECTED.search(clean):
            self._set_status("connected")
        elif _RE_WAITING.search(clean):
            self._set_status("waiting")

        # Sync complete
        if _RE_SYNC_COMPLETE.search(clean):
            self.sync_completed.emit()

        # Errors
        m = _RE_ERROR.search(clean)
        if m and "ERROR" in clean:
            self.error_occurred.emit(m.group(1))


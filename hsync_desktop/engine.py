# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
HSYNC Engine - subprocess bridge to hsync-client.

Manages the hsync-client binary as a child process and consumes the structured
JSON-Lines status events it publishes on a dedicated pipe (``--events-json-fd``),
mapping each event to a Qt signal so the UI can react to state changes
(DESIGN_REVIEW §3 / P0-B). The merged stdout/stderr stream is captured purely as
a diagnostic log feed.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QSocketNotifier,
    Signal,
    Slot,
)

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


# Sentinel filename and protocol version – imported from the shared library
# (single source of truth).
from hsync_common.constants import HSYNCKEEP_FILENAME as _HSYNCKEEP
from hsync_common.constants import VERSION as _EXPECTED_VERSION
from hsync_common.protocol.capabilities import CapabilitiesDoc, parse_capabilities
from hsync_common.protocol.events import UiEventDict, UiEventName, parse_event_line

# Status parsing is no longer regex-based: the child publishes structured
# JSON-Lines events over ``--events-json-fd`` and the engine maps each one to a
# Qt signal in ``_handle_event`` (DESIGN_REVIEW §3 / P0-B). The merged
# stdout/stderr stream is kept purely as a diagnostic log feed.


# ─── Default binary discovery ───────────────────────────────────────────────


def _platform_tag() -> str:
    """Return the platform tag used by both compile scripts (e.g. 'linux-amd64')."""
    import platform as _platform

    system = _platform.system().lower()
    if system.startswith("mingw") or system.startswith("cygwin") or system.startswith("msys"):
        system = "windows"
    elif system not in ("linux", "darwin", "windows"):
        pass  # keep as-is

    machine = _platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armv7",
        "armv7": "armv7",
        "i386": "x86",
        "i686": "x86",
    }
    arch = arch_map.get(machine, machine)
    return f"{system}-{arch}"


def find_hsync_binary() -> str | None:
    """Locate the hsync binary: bundled → PATH → sibling project dist (platform-aware)."""
    bin_name = "hsync.exe" if sys.platform == "win32" else "hsync"

    # 1. Bundled alongside this package
    pkg_dir = Path(__file__).resolve().parent
    bundled = pkg_dir / "bin" / bin_name
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)

    # 2. On PATH
    on_path = shutil.which("hsync")
    if on_path:
        return on_path

    # 3. Sibling project dist/<os>-<arch>/hsync (development / source tree)
    platform_tag = _platform_tag()
    client_root = pkg_dir.parent.parent / "hsync-client"
    sibling = client_root / "dist" / platform_tag / bin_name
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)

    return None


def get_binary_version(binary_path: str) -> str | None:
    """Return the semantic version reported by the hsync binary, or None.

    Runs ``<binary> --version`` and parses the ``hsync X.Y.Z`` output. Returns
    None when the binary cannot be executed or its output cannot be parsed.
    """
    try:
        result = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+\.\d+\.\d+)", f"{result.stdout}\n{result.stderr}")
    return match.group(1) if match else None


def get_binary_capabilities(binary_path: str | None = None) -> CapabilitiesDoc | None:
    """Return the capabilities document advertised by the hsync binary, or None.

    Runs ``<binary> --capabilities-json`` and validates its output against the
    shared schema (DESIGN_REVIEW §8). Returns None when the binary is missing,
    cannot be executed, or emits an unparseable/unsupported document — the UI
    then degrades to a best-effort, fully-enabled state.
    """
    path = binary_path or find_hsync_binary()
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, "--capabilities-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_capabilities(result.stdout)


def check_binary_compatibility(binary_path: str | None = None) -> tuple[bool, str | None]:
    """Check the hsync binary version against the desktop's expected version.

    Returns ``(is_compatible, binary_version)``. Compatibility follows the same
    Semver rule used across HSYNC: only a different *major* version is
    incompatible. When the binary is missing or its version cannot be
    determined the result is treated as compatible (best-effort), so startup is
    never blocked by a parse failure.
    """
    path = binary_path or find_hsync_binary()
    if not path:
        return (True, None)
    binary_version = get_binary_version(path)
    if not binary_version:
        return (True, None)
    is_compatible = binary_version.split(".")[0] == _EXPECTED_VERSION.split(".")[0]
    return (is_compatible, binary_version)


# ─── Engine ──────────────────────────────────────────────────────────────────


class HsyncEngine(QObject):
    """
    Manages the hsync-client subprocess.

    Start/stop the binary, capture log output in real-time, parse
    status information and expose it via Qt signals.
    """

    # ── Signals ──────────────────────────────────────────────────────────
    log_received = Signal(str)  # raw log line
    status_changed = Signal(str)  # disconnected|connecting|connected|waiting|error
    peers_changed = Signal(int)  # number of alive peers
    master_changed = Signal(bool)  # True ⇒ this client is master
    bucket_detected = Signal(str)  # bucket name
    group_detected = Signal(str)  # LAN group name
    file_transferred = Signal(str, str)  # direction ("↓"|"↑"|"✕"), filename
    file_renamed = Signal(str, str)  # old_path, new_path
    directory_created = Signal(str)  # directory path
    file_progress = Signal(str, int, int)  # filepath, bytes_transferred, total_bytes
    sync_completed = Signal()  # a full sync cycle finished
    error_occurred = Signal(str)  # error message
    auth_error_occurred = Signal(str)  # authentication error (invalid/missing API key)
    path_not_found = Signal(str)  # shared path does not exist
    process_finished = Signal(int, str)  # exit code, exit status description
    master_conflict = Signal(str, str, str)  # conflict_type, peer_cid, peer_address
    no_master_warning = Signal(str)  # no master elected (all peers never-master)

    # Preview signals (emitted during dry-run preview)
    preview_started = Signal()  # preview scan started
    preview_ended = Signal()  # preview scan ended
    file_status = Signal(str, str, int)  # status, filepath, size
    # status can be: "synced", "to_download", "to_upload", "to_delete"
    file_rename_status = Signal(str, str, int)  # old_path, new_path, size

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
        # Structured-event channel: parent end of the events pipe plus the
        # notifier/buffer used to turn inbound JSON-Lines into Qt signals.
        self._events_read_fd: int | None = None
        self._events_notifier: QSocketNotifier | None = None
        self._events_buf = ""

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
        #
        # IMPORTANT: We use a more robust approach to avoid race conditions:
        # 1. Write the secret to the pipe BEFORE starting the process
        # 2. Close the WRITE end BEFORE start (so child sees EOF when reading)
        # 3. Keep the READ end open until AFTER waitForStarted confirms success
        #    This ensures the child has time to fork and inherit the fd before
        #    we close it in the parent.
        # 4. On failure to start, we close all fds in the error handler
        #
        # The child process inherits the read end and reads the secret.
        # We defer closing the read fds until after the process starts
        # successfully to avoid a race where the child hasn't yet opened
        # the inherited fd.
        pipe_fds: list[int] = []
        pipe_args: list[str] = []

        api_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        if api_key:
            read_fd, write_fd = os.pipe()
            # Set close-on-exec to prevent accidental inheritance by other processes
            fcntl.fcntl(read_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            fcntl.fcntl(write_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            # Write the secret BEFORE fork so it's available immediately after start
            os.write(write_fd, api_key.encode("utf-8"))
            # Close write end BEFORE start so child sees EOF when it reads
            os.close(write_fd)
            pipe_fds.append(read_fd)
            pipe_args.extend(["--api-key-fd", str(read_fd)])

        lan_key = str(s.value("lan/key", "", str))
        if lan_key:
            read_fd, write_fd = os.pipe()
            # Set close-on-exec to prevent accidental inheritance by other processes
            fcntl.fcntl(read_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            fcntl.fcntl(write_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            # Write the secret BEFORE fork so it's available immediately after start
            os.write(write_fd, lan_key.encode("utf-8"))
            # Close write end BEFORE start so child sees EOF when it reads
            os.close(write_fd)
            pipe_fds.append(read_fd)
            pipe_args.extend(["--lan-key-fd", str(read_fd)])

        # Structured-event channel: the child writes JSON-Lines status events to
        # the write end, which it inherits across exec. Unlike the CLOEXEC secret
        # pipes above, this fd must be explicitly marked inheritable so QProcess'
        # fork+exec child keeps it open.
        events_read_fd, events_write_fd = os.pipe()
        os.set_inheritable(events_write_fd, True)
        pipe_args.extend(["--events-json-fd", str(events_write_fd)])

        # Build final args with pipe fds at the end
        args = [*args, *pipe_args]

        proc.start(self._binary, args)
        if not proc.waitForStarted(5000):
            # Failed to start - close all pipe fds (secrets + events)
            for fd in (*pipe_fds, events_read_fd, events_write_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
            self.error_occurred.emit("Failed to start hsync process.")
            self._set_status("error")
            return False

        # Close parent's copy of the read fds - child has inherited them.
        # We close after waitForStarted to ensure the child has forked
        # and has access to the inherited file descriptors.
        for fd in pipe_fds:
            try:
                os.close(fd)
            except OSError:
                pass  # FD may have been closed already

        # The child now owns the events write end; close the parent's copy so a
        # child exit surfaces as EOF, then watch the read end for inbound events.
        try:
            os.close(events_write_fd)
        except OSError:
            pass
        self._open_events_channel(events_read_fd)

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

    def set_bandwidth(self, upload: int | None, download: int | None) -> None:
        """Change bandwidth limits at runtime via stdin command.

        Args:
            upload: Maximum upload bandwidth in bytes per second, or None for unlimited.
            download: Maximum download bandwidth in bytes per second, or None for unlimited.
        """
        cmd: dict = {"cmd": "SET_BANDWIDTH"}
        # Send 0 for unlimited so the handler clears previous limits;
        # omitting the field would leave old limits in place.
        cmd["upload"] = upload if upload is not None else 0
        cmd["download"] = download if download is not None else 0
        self._send_command(cmd)

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
        # The merged stdout/stderr stream is now purely a diagnostic log feed;
        # all UI state transitions arrive on the structured events channel
        # (see ``_on_events_available`` / ``_handle_event``).
        if not self._process:
            return
        data = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.rstrip()
            if line:
                self.log_received.emit(line)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._running = False
        self._close_events_channel()
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

    # ── Status helper ─────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.status_changed.emit(status)

    # ── Structured events channel ─────────────────────────────────────────

    def _open_events_channel(self, read_fd: int) -> None:
        """Start watching the parent end of the events pipe for JSON-Lines."""
        self._events_read_fd = read_fd
        self._events_buf = ""
        notifier = QSocketNotifier(read_fd, QSocketNotifier.Type.Read, self)
        notifier.activated.connect(self._on_events_available)
        notifier.setEnabled(True)
        self._events_notifier = notifier

    def _close_events_channel(self) -> None:
        """Tear down the events notifier and close the read fd (idempotent)."""
        if self._events_notifier is not None:
            self._events_notifier.setEnabled(False)
            self._events_notifier.deleteLater()
            self._events_notifier = None
        if self._events_read_fd is not None:
            try:
                os.close(self._events_read_fd)
            except OSError:
                pass
            self._events_read_fd = None
        self._events_buf = ""

    @Slot()
    def _on_events_available(self) -> None:
        """Drain the events pipe and dispatch each complete JSON-Lines record."""
        fd = self._events_read_fd
        if fd is None:
            return
        try:
            chunk = os.read(fd, 65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            self._close_events_channel()
            return
        if not chunk:
            # EOF: the child closed its write end (it exited or finished).
            self._close_events_channel()
            return
        self._events_buf += chunk.decode("utf-8", errors="replace")
        *lines, self._events_buf = self._events_buf.split("\n")
        for line in lines:
            event = parse_event_line(line)
            if event is not None:
                self._handle_event(event)

    def _handle_event(self, event: UiEventDict) -> None:
        """Translate one structured client event into Qt signal(s).

        Mirrors the former regex parser 1:1 — each event name maps to the same
        signal/payload the GUI already consumes. A malformed event is logged but
        never crashes the engine.
        """
        name = event.get("event")
        try:
            if name == UiEventName.status:
                self._set_status(str(event.get("status", "")))
            elif name == UiEventName.peers:
                count = int(event.get("count", 0))
                if count != self._peers:
                    self._peers = count
                    self.peers_changed.emit(count)
            elif name == UiEventName.role:
                is_master = bool(event.get("is_master", False))
                if is_master != self._is_master:
                    self._is_master = is_master
                    self.master_changed.emit(is_master)
            elif name == UiEventName.bucket:
                self.bucket_detected.emit(str(event.get("bucket", "")))
            elif name == UiEventName.group:
                self.group_detected.emit(str(event.get("group", "")))
            elif name == UiEventName.session:
                self._cid = str(event.get("cid", ""))
            elif name == UiEventName.server:
                from urllib.parse import urlparse

                self._server_ip = urlparse(str(event.get("url", ""))).hostname or ""
            elif name == UiEventName.transfer:
                self._handle_transfer(event)
            elif name == UiEventName.rename:
                self.file_renamed.emit(str(event.get("src", "")), str(event.get("dst", "")))
            elif name == UiEventName.dir_created:
                path = str(event.get("path", ""))
                if not path.endswith(_HSYNCKEEP):
                    self.directory_created.emit(path)
            elif name == UiEventName.progress:
                self.file_progress.emit(
                    str(event.get("file", "")),
                    int(event.get("transferred", 0)),
                    int(event.get("total", 0)),
                )
            elif name == UiEventName.sync_complete:
                self.sync_completed.emit()
            elif name == UiEventName.error:
                self.error_occurred.emit(str(event.get("message", "")))
            elif name == UiEventName.auth_error:
                self._auth_error_active = True
                self.auth_error_occurred.emit(str(event.get("message", "")))
                self._set_status("error")
            elif name == UiEventName.path_not_found:
                self.path_not_found.emit(str(event.get("path", "")))
                self._set_status("error")
            elif name == UiEventName.master_conflict:
                self.master_conflict.emit(
                    str(event.get("conflict_type", "")),
                    str(event.get("peer_cid", "")),
                    str(event.get("peer_address", "")),
                )
            elif name == UiEventName.no_master:
                self.no_master_warning.emit(str(event.get("message", "")))
            elif name == UiEventName.preview_start:
                self._in_preview = True
                self.preview_started.emit()
            elif name == UiEventName.preview_end:
                self._in_preview = False
                self.preview_ended.emit()
            elif name == UiEventName.file_status:
                self.file_status.emit(
                    str(event.get("state", "")),
                    str(event.get("file", "")),
                    int(event.get("size", 0)),
                )
            elif name == UiEventName.rename_status:
                self.file_rename_status.emit(
                    str(event.get("src", "")),
                    str(event.get("dst", "")),
                    int(event.get("size", 0)),
                )
        except Exception:
            # A malformed payload must never take down the engine.
            self.log_received.emit(f"[EVENT ERROR] {str(event)[:100]}")

    def _handle_transfer(self, event: UiEventDict) -> None:
        """Update transfer stats and emit ``file_transferred`` for a transfer."""
        file = str(event.get("file", ""))
        if file.endswith(_HSYNCKEEP):
            return
        op = str(event.get("op", ""))
        size = int(event.get("size", 0))
        if op == "download":
            self.stats.files_received += 1
            self.stats.bytes_received += size
            self.file_transferred.emit("↓", file)
        elif op == "upload":
            self.stats.files_sent += 1
            self.stats.bytes_sent += size
            self.file_transferred.emit("↑", file)
        elif op == "delete":
            self.file_transferred.emit("✕", file)

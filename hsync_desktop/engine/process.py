# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
HSYNC Engine - subprocess bridge to hsync-client.

Manages the hsync-client binary as a child process and consumes the structured
JSON-Lines status events it publishes on a dedicated pipe (``--events-json-fd``),
mapping each event to a Qt signal so the UI can react to state changes.
The merged stdout/stderr stream is captured purely as a diagnostic log feed.
"""

from __future__ import annotations

import json
import os
import signal
from dataclasses import dataclass, field
from urllib.parse import urlparse

from hsync_common.constants import HSYNCKEEP_FILENAME as _HSYNCKEEP
from hsync_common.protocol.events import UiEventDict, UiEventName, parse_event_line
from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QSocketNotifier,
    Signal,
    Slot,
)

from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_PEER_READ_CAP,
    DEFAULT_P2P_PEER_SOURCES_MAX,
    DEFAULT_SERVER_TRUST,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine.cli import find_hsync_binary


def write_secret_pipe(secret: str) -> int:
    """Write *secret* into a pipe; return the inheritable read fd.

    The write end is closed before return so a reader sees EOF after the
    bytes. The read end is marked inheritable for QProcess fork+exec
    (Python 3.4+ file descriptors are close-on-exec by default). The
    parent must close the returned fd after the child has started.

    Consumers: ``HsyncEngine.start`` (``--api-key-fd`` / ``--p2p-key-fd``).
    """
    read_fd, write_fd = os.pipe()
    os.set_inheritable(read_fd, True)
    try:
        os.write(write_fd, secret.encode("utf-8"))
    finally:
        os.close(write_fd)
    return read_fd


# ─── Stats dataclass ────────────────────────────────────────────────────────


@dataclass
class TransferStats:
    """Cumulative transfer statistics for the current engine session.

    ``files_sent`` / ``files_received`` count the *distinct* file paths moved
    (a repeated or renamed transfer of the same file stays one); the path sets
    are the source of truth for that count. ``bytes_sent`` / ``bytes_received``
    sum every completed content transfer, repeats included.
    """

    files_sent: int = 0
    files_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    sent_paths: set[str] = field(default_factory=set)
    received_paths: set[str] = field(default_factory=set)

    def record_content(self, op: str, key: str, size: int) -> None:
        """Record one completed content transfer of *key*.

        *op* is ``"upload"`` or ``"download"``. Bytes are always summed; the
        path joins the distinct-file set (and the count) only when non-empty, so
        a malformed event without a path never inflates the file total.
        """
        if op == "download":
            self.bytes_received += size
            if key:
                self.received_paths.add(key)
            self.files_received = len(self.received_paths)
        elif op == "upload":
            self.bytes_sent += size
            if key:
                self.sent_paths.add(key)
            self.files_sent = len(self.sent_paths)

    def follow_rename(self, src_key: str, dst_key: str) -> None:
        """Move tracked identity from *src_key* to *dst_key* after a rename.

        Handles a file (exact key) and a directory (every ``src_key + "/"``
        descendant). An untracked source is a no-op, so a rename never invents a
        transferred file.
        """
        if not src_key or src_key == dst_key:
            return
        prefix = src_key + "/"
        for paths in (self.sent_paths, self.received_paths):
            moved = [p for p in paths if p == src_key or p.startswith(prefix)]
            for old in moved:
                paths.discard(old)
                paths.add(dst_key + old[len(src_key) :])
        self.files_sent = len(self.sent_paths)
        self.files_received = len(self.received_paths)

    def reset(self) -> None:
        self.files_sent = self.files_received = 0
        self.bytes_sent = self.bytes_received = 0
        self.sent_paths.clear()
        self.received_paths.clear()


def apply_settings_env(env: QProcessEnvironment, s: QSettings) -> None:
    """Insert the GUI-configured environment variables into *env*.

    Reads the QSettings values that hsync-client consumes from the process
    environment (no CLI flag exists for them) and inserts them when set:

    * ``HSYNC_SERVER`` (``connection/server_url``) — the server-endpoint
      channel: the client CLI takes the bare host, so the full (validated)
      URL travels through the environment;
    * ``HSYNC_NTP_HOSTS`` (``p2p/ntp_hosts``, ADR-0023) — SNTP host list for
      the p2p-mode clock-offset probe.

    ``insert()`` overwrites any pre-existing value: the GUI setting is the
    user's explicit choice and wins over the ambient environment.
    """
    server_url = str(s.value("connection/server_url", "", str)).strip()
    if server_url:
        env.insert("HSYNC_SERVER", server_url)
    # Server TLS trust policy (ADR-0036): env-driven like the bootnode policy,
    # so the client's EnvSettings reads it and no CLI flag/gate is involved. The
    # pin itself lives in the shared server known-hosts store.
    env.insert(
        "HSYNC_SERVER_TRUST",
        str(s.value("connection/server_trust", DEFAULT_SERVER_TRUST, str)),
    )
    # ADR-0023: SNTP host list for p2p-mode clock correction.
    ntp_hosts = str(s.value("p2p/ntp_hosts", "", str)).strip()
    if ntp_hosts:
        env.insert("HSYNC_NTP_HOSTS", ntp_hosts)
    # Cross-network discovery: the bootnode travels through the environment as
    # a HOST[:PORT] endpoint (same grammar as the client's BOOTNODE positional,
    # so no argument plumbing is needed). UPnP is sent explicitly so the user's
    # choice wins over the plan default.
    bootnode = str(s.value("p2p/bootnode", "", str)).strip()
    if bootnode:
        env.insert("HSYNC_BOOTNODE", bootnode)
        env.insert(
            "HSYNC_UPNP_ENABLED",
            "true" if bool(s.value("p2p/upnp_enabled", True, bool)) else "false",
        )
        # Trust policy (ADR-0035): the GUI cannot answer the client's terminal
        # prompt, so it always sends an explicit policy. The pin itself lives in
        # the shared known-hosts store (managed by the client CLI / the GUI's
        # "Manage trusted keys" dialog), not in a GUI-only setting.
        env.insert(
            "HSYNC_BOOTNODE_TRUST",
            str(s.value("p2p/bootnode_trust", DEFAULT_P2P_BOOTNODE_TRUST, str)),
        )
    # p2p peer-download caps are env-only (no CLI flag); the on/off is the
    # --no-peer-download flag. Only meaningful in p2p mode.
    if bool(s.value("p2p/enabled", True, bool)):
        env.insert(
            "HSYNC_P2P_PEER_READ_CAP",
            str(s.value("p2p/peer_read_cap", DEFAULT_P2P_PEER_READ_CAP, int)),
        )
        env.insert(
            "HSYNC_P2P_PEER_SOURCES_MAX",
            str(s.value("p2p/peer_sources_max", DEFAULT_P2P_PEER_SOURCES_MAX, int)),
        )


class HsyncEngine(QObject):
    """
    Manages the hsync-client subprocess.

    Start/stop the binary, capture log output in real-time, parse
    status information and expose it via Qt signals.
    """

    # ── Signals ──────────────────────────────────────────────────────────
    log_received = Signal(str)  # raw log line
    status_changed = Signal(str)  # disconnected|connecting|connected|waiting|error
    peers_changed = Signal(int, int)  # connected clients, total clients (self included)
    master_changed = Signal(bool)  # True ⇒ this client is master
    bucket_detected = Signal(str)  # bucket name
    group_detected = Signal(str)  # p2p group name
    discovery_changed = Signal(
        str, str
    )  # plan ("mdns"|"mdns+bootnode"), bootnode host ("" without one)
    file_transferred = Signal(str, str, int)  # direction ("↓"|"↑"|"✕"), filename, size
    file_renamed = Signal(str, str)  # old_path, new_path
    directory_created = Signal(str)  # directory path
    # filepath, transferred, total, op ("download"|"upload") — a download has
    # no local row yet, so the panel needs the direction to create one.
    file_progress = Signal(str, int, int, str)
    sync_completed = Signal()  # a full sync cycle finished
    folder_size_changed = Signal(int, int)  # (local_bytes, total_bytes)
    transfer_failed = Signal(str, str, str)  # op ("download"|"upload"), filepath, message
    sync_paused = Signal(str, int, int)  # reason, deletes blocked, local files
    # error message + reason: "" (generic), "connection" (network failure in
    # preview/sync), "process" (QProcess error), "start" (engine launch failure).
    error_occurred = Signal(str, str)
    auth_error_occurred = Signal(str)  # authentication error (invalid/missing API key)
    auth_required_occurred = Signal(str)  # a shared key is required but missing
    security_rejected = Signal(str, str, str)  # unsafe remote path rejected (op, path, message)
    path_not_found = Signal(str)  # shared path does not exist
    process_finished = Signal(int, str)  # exit code, exit status description
    master_conflict = Signal(str, str, str)  # conflict_type, peer_cid, peer_address
    no_master_warning = Signal(str)  # no master elected (all peers never-master)
    no_peers_warning = Signal(str)  # a p2p one-shot found no peer to sync with
    conflict_resolved = Signal(str, str)  # filepath, conflict_copy path
    duplicate_identity = Signal(str, str)  # peer_cid, peer_address (cloned device ID)
    # Trust refusal events (SSH-style): the GUI must answer instead of the
    # terminal. Scope is "master" (P2P pin), "bootnode" or "server" (known-hosts).
    pairing_needed = Signal(str, str, str, str)  # scope, peer_cid, peer_address, fingerprint
    fingerprint_changed = Signal(str, str, str, str)  # scope, peer_cid, peer_address, fingerprint

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
        self._is_master = False
        self._peers = 0
        self._peers_total = 0
        self._status = "disconnected"
        self._cid = ""
        self._server_ip = ""
        # Root the distinct-file identity keys are made relative to; fed by the
        # window from the selected local path (empty in unit tests, where event
        # paths are already treated as keys).
        self.local_root = ""
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
            self.error_occurred.emit("hsync binary not found.", "start")
            return False

        self.stats.reset()
        self._is_master = False
        self._peers = 0
        self._peers_total = 0
        self._stopping = False
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
        apply_settings_env(env, s)
        proc.setProcessEnvironment(env)

        # Pass secrets via pipe file descriptors so they never appear in
        # process arguments (visible in ``ps``) or environment variables
        # (visible in ``/proc/<pid>/environ``).
        #
        # write_secret_pipe marks the read end inheritable (required for
        # QProcess fork+exec) and closes the write end so the child sees
        # EOF. The parent keeps the read fd until waitForStarted succeeds.
        pipe_fds: list[int] = []
        pipe_args: list[str] = []

        # Secret fds are subcommand-specific: the server subcommand reads the
        # API key and the p2p subcommand reads the p2p key. Injecting the wrong
        # fd would make the child fail with an unknown-option error.
        mode = args[0] if args else ""

        api_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        if api_key and mode == "server":
            read_fd = write_secret_pipe(api_key)
            pipe_fds.append(read_fd)
            pipe_args.extend(["--api-key-fd", str(read_fd)])

        p2p_key = decrypt_value(str(s.value("p2p/key", "", str)))
        if p2p_key and mode == "p2p":
            read_fd = write_secret_pipe(p2p_key)
            pipe_fds.append(read_fd)
            pipe_args.extend(["--p2p-key-fd", str(read_fd)])
        elif not p2p_key and mode == "p2p":
            # Keyless P2P: the desktop already confirmed via its own pre-flight
            # dialog, so acknowledge the posture for the CLI subprocess.
            pipe_args.append("--allow-unauthenticated-p2p")

        # Structured-event channel: the child writes JSON-Lines status events to
        # the write end, which it inherits across exec. Same inheritable
        # requirement as the secret read fds (Python 3.4+ fds are CLOEXEC).
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
            self.error_occurred.emit("Failed to start hsync process.", "start")
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
        for raw_line in data.splitlines():
            line = raw_line.rstrip()
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
        self.error_occurred.emit(mapping.get(error, "Unknown error"), "process")
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
            # Branch order is deliberate: the high-frequency sync events
            # (progress/transfer/file_status/rename_status...) are checked first
            # so the common case does not walk a long if/elif chain. Branches are
            # mutually exclusive on ``name``, so order never changes behaviour.
            if name == UiEventName.status:
                self._set_status(str(event.get("status", "")))
            elif name == UiEventName.progress:
                self.file_progress.emit(
                    str(event.get("file", "")),
                    int(event.get("transferred", 0)),
                    int(event.get("total", 0)),
                    str(event.get("op", "")),
                )
            elif name == UiEventName.transfer:
                self._handle_transfer(event)
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
            elif name == UiEventName.rename:
                src = str(event.get("src", ""))
                dst = str(event.get("dst", ""))
                self.stats.follow_rename(self._relative_key(src), self._relative_key(dst))
                self.file_renamed.emit(src, dst)
            elif name == UiEventName.dir_created:
                path = str(event.get("path", ""))
                if not path.endswith(_HSYNCKEEP):
                    self.directory_created.emit(path)
            elif name == UiEventName.sync_complete:
                self.sync_completed.emit()
            elif name == UiEventName.folder_size:
                self.folder_size_changed.emit(
                    max(int(event.get("local_bytes", 0)), 0),
                    max(int(event.get("total_bytes", 0)), 0),
                )
            elif name == UiEventName.transfer_failed:
                self.transfer_failed.emit(
                    str(event.get("op", "")),
                    str(event.get("file", "")),
                    str(event.get("message", "")),
                )
            elif name == UiEventName.conflict_resolved:
                self.conflict_resolved.emit(
                    str(event.get("file", "")),
                    str(event.get("conflict_copy", "")),
                )
            elif name == UiEventName.error:
                self.error_occurred.emit(
                    str(event.get("message", "")), str(event.get("reason", ""))
                )
            elif name == UiEventName.sync_paused:
                self.sync_paused.emit(
                    str(event.get("reason", "")),
                    int(event.get("deletes", 0)),
                    int(event.get("local", 0)),
                )
            elif name == UiEventName.security_rejected:
                self.security_rejected.emit(
                    str(event.get("op", "")),
                    str(event.get("path", "")),
                    str(event.get("message", "")),
                )
            elif name == UiEventName.peers:
                connected = int(event.get("connected", 0))
                total = int(event.get("total", 0))
                if (connected, total) != (self._peers, self._peers_total):
                    self._peers = connected
                    self._peers_total = total
                    self.peers_changed.emit(connected, total)
            elif name == UiEventName.role:
                is_master = bool(event.get("is_master", False))
                if is_master != self._is_master:
                    self._is_master = is_master
                    self.master_changed.emit(is_master)
            elif name == UiEventName.bucket:
                self.bucket_detected.emit(str(event.get("bucket", "")))
            elif name == UiEventName.group:
                self.group_detected.emit(str(event.get("group", "")))
            elif name == UiEventName.discovery:
                self.discovery_changed.emit(
                    str(event.get("plan", "")), str(event.get("bootnode", ""))
                )
            elif name == UiEventName.session:
                self._cid = str(event.get("cid", ""))
            elif name == UiEventName.server:
                self._server_ip = urlparse(str(event.get("url", ""))).hostname or ""
            elif name == UiEventName.auth_error:
                self.auth_error_occurred.emit(str(event.get("message", "")))
                self._set_status("error")
            elif name == UiEventName.auth_required:
                self.auth_required_occurred.emit(str(event.get("message", "")))
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
            elif name == UiEventName.no_peers:
                self.no_peers_warning.emit(str(event.get("message", "")))
            elif name == UiEventName.duplicate_identity:
                self.duplicate_identity.emit(
                    str(event.get("peer_cid", "")),
                    str(event.get("peer_address", "")),
                )
            elif name == UiEventName.pairing_needed:
                self.pairing_needed.emit(
                    str(event.get("scope", "")),
                    str(event.get("peer_cid", "")),
                    str(event.get("peer_address", "")),
                    str(event.get("fingerprint", "")),
                )
            elif name == UiEventName.fingerprint_changed:
                self.fingerprint_changed.emit(
                    str(event.get("scope", "")),
                    str(event.get("peer_cid", "")),
                    str(event.get("peer_address", "")),
                    str(event.get("fingerprint", "")),
                )
            elif name == UiEventName.preview_start:
                self.preview_started.emit()
            elif name == UiEventName.preview_end:
                self.preview_ended.emit()
        except Exception:
            # A malformed payload must never take down the engine.
            self.log_received.emit(f"[EVENT ERROR] {str(event)[:100]}")

    def _relative_key(self, path: str) -> str:
        """Normalize an event path to a bucket-relative identity key.

        Separators are unified and a ``local_root`` prefix (or its ``./`` form)
        is stripped, so the absolute download path and the relative upload path
        for the same file collapse to one key. An empty root keeps the path as
        given, which is what unit tests rely on.
        """
        key = path.replace("\\", "/")
        root = self.local_root.replace("\\", "/").rstrip("/")
        if root and (key == root or key.startswith(root + "/")):
            key = key[len(root) :]
        while key.startswith("./"):
            key = key[2:]
        return key.lstrip("/")

    def _handle_transfer(self, event: UiEventDict) -> None:
        """Update transfer stats and emit ``file_transferred`` for a transfer."""
        file = str(event.get("file", ""))
        if file.endswith(_HSYNCKEEP):
            return
        op = str(event.get("op", ""))
        size = int(event.get("size", 0))
        if op == "download":
            self.stats.record_content("download", self._relative_key(file), size)
            self.file_transferred.emit("↓", file, size)
        elif op == "upload":
            self.stats.record_content("upload", self._relative_key(file), size)
            self.file_transferred.emit("↑", file, size)
        elif op == "delete":
            self.file_transferred.emit("✕", file, 0)

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

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
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QSocketNotifier,
    QTimer,
    Signal,
    Slot,
)

from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_SERVER_TRUST,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value


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
from hsync_common.constants import HSYNC_VERSION as _EXPECTED_VERSION
from hsync_common.constants import HSYNCKEEP_FILENAME as _HSYNCKEEP
from hsync_common.protocol.capabilities import (
    CapabilitiesDoc,
    parse_capabilities,
    supports_subcommand,
)
from hsync_common.protocol.events import UiEventDict, UiEventName, parse_event_line

# Status parsing is no longer regex-based: the child publishes structured
# JSON-Lines events over ``--events-json-fd`` and the engine maps each one to a
# Qt signal in ``_handle_event``.
# The merged stdout/stderr stream is kept purely as a diagnostic log feed.


# ─── Default binary discovery ───────────────────────────────────────────────


def _platform_tag() -> str:
    """Return the platform tag used by both compile scripts (e.g. 'linux-amd64')."""
    import platform as _platform

    system = _platform.system().lower()
    if system.startswith(("mingw", "cygwin", "msys")):
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
    # Cross-network discovery: the bootnode travels through the environment
    # (the client CLI takes a bare positional, but HSYNC_BOOTNODE is the
    # documented equivalent and needs no argument plumbing). UPnP is sent
    # explicitly so the user's choice wins over the plan default.
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


def _run_hsync_line(binary: str, args: list[str], timeout: float = 15.0) -> str | None:
    """Run ``<binary> <args>`` and return the last non-empty stdout line, or None."""
    try:
        result = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else None


def fetch_bootnode_fingerprint(binary: str, host: str, port: int | None = None) -> str | None:
    """Read a bootnode certificate fingerprint without trusting it (ADR-0035).

    Runs ``hsync trust bootnode fingerprint <host> [--port <port>]`` with a bounded
    timeout and returns the canonical fingerprint, or ``None`` when the node cannot
    be reached. Used by the GUI pre-flight so the operator can confirm an unknown
    node before the client is started.
    """
    args = ["trust", "bootnode", "fingerprint", host]
    if port:
        args += ["--port", str(port)]
    return _run_hsync_line(binary, args)


def fetch_server_fingerprint(binary: str, host: str, port: int | None = None) -> str | None:
    """Read a sync-server certificate fingerprint without trusting it (ADR-0036).

    Runs ``hsync trust server fingerprint <host> [--port <port>]`` (raw TLS probe).
    """
    args = ["trust", "server", "fingerprint", host]
    if port:
        args += ["--port", str(port)]
    return _run_hsync_line(binary, args)


def _run_hsync_success(binary: str, args: list[str], timeout: float = 15.0) -> bool:
    """Run ``<binary> <args>`` and return True only on a clean exit (code 0)."""
    try:
        result = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _run_hsync_json(binary: str, args: list[str], timeout: float = 15.0) -> object | None:
    """Run ``<binary> <args>`` and parse JSON from stdout; None on any failure."""
    try:
        result = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return None


def _only_dict_entries(payload: object) -> list[dict] | None:
    """Return the list if *payload* is a list of dicts, else None."""
    if not isinstance(payload, list):
        return None
    return [entry for entry in payload if isinstance(entry, dict)]


def _port_args(port: int | None) -> list[str]:
    """The ``[--port PORT]`` tail shared by the host trust subcommands."""
    return ["--port", str(port)] if port else []


def list_bootnode_trust(binary: str) -> list[dict] | None:
    """Return the bootnode known-hosts entries (``hsync trust bootnode list --json``)."""
    return _only_dict_entries(_run_hsync_json(binary, ["trust", "bootnode", "list", "--json"]))


def add_bootnode_trust(binary: str, host: str, fingerprint: str, port: int | None = None) -> bool:
    """Pin a bootnode fingerprint (``hsync trust bootnode add``); True on success."""
    return _run_hsync_success(
        binary, ["trust", "bootnode", "add", host, fingerprint, *_port_args(port)]
    )


def remove_bootnode_trust(binary: str, host: str, port: int | None = None) -> bool:
    """Forget a bootnode pin (``hsync trust bootnode remove``); True on success."""
    return _run_hsync_success(binary, ["trust", "bootnode", "remove", host, *_port_args(port)])


def list_peer_pins(binary: str) -> list[dict] | None:
    """Return the known-peers pins (``hsync trust peer list --json``)."""
    return _only_dict_entries(_run_hsync_json(binary, ["trust", "peer", "list", "--json"]))


def add_peer_pin(binary: str, cid: str, bucket: str, fingerprint: str) -> bool:
    """Pin a P2P peer fingerprint (``hsync trust peer add``); True on success."""
    return _run_hsync_success(
        binary, ["trust", "peer", "add", "--bucket", bucket, cid, fingerprint]
    )


def remove_peer_pin(binary: str, cid: str, bucket: str) -> bool:
    """Forget a P2P peer pin (``hsync trust peer remove``); True on success."""
    return _run_hsync_success(binary, ["trust", "peer", "remove", "--bucket", bucket, cid])


def list_server_trust(binary: str) -> list[dict] | None:
    """Return the sync-server known-hosts entries (``hsync trust server list --json``)."""
    return _only_dict_entries(_run_hsync_json(binary, ["trust", "server", "list", "--json"]))


def add_server_trust(binary: str, host: str, fingerprint: str, port: int | None = None) -> bool:
    """Pin a sync-server fingerprint (``hsync trust server add``); True on success."""
    return _run_hsync_success(
        binary, ["trust", "server", "add", host, fingerprint, *_port_args(port)]
    )


def remove_server_trust(binary: str, host: str, port: int | None = None) -> bool:
    """Forget a sync-server pin (``hsync trust server remove``); True on success."""
    return _run_hsync_success(binary, ["trust", "server", "remove", host, *_port_args(port)])


def supports_peer_trust(binary: str | None = None) -> bool:
    """Return True when the binary offers the ``trust`` subcommand.

    An unknown capabilities document (missing/older binary) is treated
    permissively, mirroring the settings-dialog capability gate.
    """
    doc = get_binary_capabilities_cached(binary)
    if doc is None:
        return True
    return supports_subcommand(doc, "trust")


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


def _parse_version(output: str) -> str | None:
    """Extract the ``X.Y.Z`` version from ``--version`` output, or None."""
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


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
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return _parse_version(f"{result.stdout}\n{result.stderr}")


def get_binary_capabilities(binary_path: str | None = None) -> CapabilitiesDoc | None:
    """Return the capabilities document advertised by the hsync binary, or None.

    Runs ``<binary> --capabilities-json`` and validates its output against the
    shared schema. Returns None when the binary is missing, cannot be executed,
    or emits an unparseable/unsupported document — the UI then degrades to a
    best-effort, fully-enabled state.
    """
    path = binary_path or find_hsync_binary()
    if not path:
        return None
    raw = _get_binary_capabilities_raw(path)
    if raw is None:
        return None
    return parse_capabilities(raw)


def _get_binary_capabilities_raw(path: str) -> str | None:
    """Run ``<path> --capabilities-json`` and return the raw stdout, or None."""
    try:
        result = subprocess.run(
            [path, "--capabilities-json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout


def is_binary_version_compatible(binary_version: str) -> bool:
    """Return True when *binary_version* shares the desktop's major version."""
    return binary_version.split(".")[0] == _EXPECTED_VERSION.split(".")[0]


# ─── Binary-probe cache (QSettings) ──────────────────────────────────────────

_VERSION_CACHE_KEY = "binary/version_cache"
_CAPABILITIES_CACHE_KEY = "binary/capabilities_cache"


def _probe_settings() -> QSettings:
    """Return the QSettings used for binary-probe caching (patchable in tests)."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def _binary_stat(path: str) -> tuple[int, int] | None:
    """Return the ``(size, mtime_ns)`` of *path*, or None if it cannot be stat'd."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _read_probe_cache(key: str, path: str) -> str | None:
    """Return the cached raw value for *key* if it still matches *path*.

    The entry is considered fresh only while the on-disk binary's
    ``(size, mtime_ns)`` match the values captured at caching time, so a
    replaced bundled binary can never be served a stale probe result.
    """
    stat = _binary_stat(path)
    if stat is None:
        return None
    size, mtime_ns = stat
    raw_value = _probe_settings().value(key, "")
    raw = raw_value if isinstance(raw_value, str) else ""
    try:
        payload = json.loads(raw) if raw else None
    except (ValueError, TypeError):
        return None
    if (
        isinstance(payload, dict)
        and payload.get("path") == path
        and payload.get("size") == size
        and payload.get("mtime_ns") == mtime_ns
    ):
        value = payload.get("value")
        return value if isinstance(value, str) else None
    return None


def _write_probe_cache(key: str, path: str, value: str) -> None:
    """Persist *value* for *key* together with the current ``(size, mtime_ns)``."""
    stat = _binary_stat(path)
    if stat is None:
        return
    size, mtime_ns = stat
    _probe_settings().setValue(
        key,
        json.dumps({"path": path, "size": size, "mtime_ns": mtime_ns, "value": value}),
    )


def get_binary_version_cached(binary_path: str) -> str | None:
    """Return ``get_binary_version(binary_path)`` with a QSettings-backed cache."""
    cached = _read_probe_cache(_VERSION_CACHE_KEY, binary_path)
    if cached is not None:
        return cached
    version = get_binary_version(binary_path)
    if version is not None:
        _write_probe_cache(_VERSION_CACHE_KEY, binary_path, version)
    return version


def get_binary_capabilities_cached(binary_path: str | None = None) -> CapabilitiesDoc | None:
    """Return ``get_binary_capabilities`` with a QSettings-backed cache.

    Only a successfully parsed document is cached; a cache hit that no longer
    parses falls through to a fresh probe (never serving a corrupt value).
    """
    path = binary_path or find_hsync_binary()
    if not path:
        return None
    raw = _read_probe_cache(_CAPABILITIES_CACHE_KEY, path)
    if raw is not None:
        doc = parse_capabilities(raw)
        if doc is not None:
            return doc
    raw = _get_binary_capabilities_raw(path)
    if raw is None:
        return None
    doc = parse_capabilities(raw)
    if doc is not None:
        _write_probe_cache(_CAPABILITIES_CACHE_KEY, path, raw)
    return doc


class BinaryVersionProbe(QObject):
    """Resolve the bundled binary's version without blocking the event loop.

    On a cache hit the result is emitted immediately (synchronously); on a miss a
    ``QProcess`` runs ``--version`` in the background and emits when it finishes,
    persisting the result so subsequent launches are instant. A hung binary is
    killed after ``_VERSION_PROBE_TIMEOUT_MS`` and the result degrades to ``""``
    (treated as compatible), mirroring the synchronous probe's 5 s timeout.
    """

    finished = Signal(str)  # the version string, or "" when undeterminable

    _VERSION_PROBE_TIMEOUT_MS = 5000

    def __init__(self, binary_path: str | None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._binary_path = binary_path
        self._path: str | None = None
        self._process: QProcess | None = None
        self._done = False
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(self._VERSION_PROBE_TIMEOUT_MS)
        self._timeout.timeout.connect(self._on_timeout)

    def start(self) -> None:
        path = self._binary_path or find_hsync_binary()
        if not path:
            self._done = True
            self.finished.emit("")
            return
        self._path = path
        cached = _read_probe_cache(_VERSION_CACHE_KEY, path)
        if cached is not None:
            self._done = True
            self.finished.emit(cached)
            return
        process = QProcess(self)
        self._process = process
        process.setProgram(path)
        process.setArguments(["--version"])
        process.finished.connect(self._on_finished)
        process.start()
        self._timeout.start()

    @Slot()
    def _finish(self, version: str) -> None:
        if self._done:
            return
        self._done = True
        self._timeout.stop()
        self.finished.emit(version)

    @Slot()
    def _on_finished(self) -> None:
        process = self._process
        if process is None:
            return
        stdout = cast(bytes, process.readAllStandardOutput().data()).decode(errors="replace")
        stderr = cast(bytes, process.readAllStandardError().data()).decode(errors="replace")
        version = _parse_version(f"{stdout}\n{stderr}") or ""
        if version and self._path:
            _write_probe_cache(_VERSION_CACHE_KEY, self._path, version)
        self._finish(version)

    @Slot()
    def _on_timeout(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
        self._finish("")


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
    peers_changed = Signal(int, int)  # connected clients, total clients (self included)
    master_changed = Signal(bool)  # True ⇒ this client is master
    bucket_detected = Signal(str)  # bucket name
    group_detected = Signal(str)  # p2p group name
    discovery_changed = Signal(str, str)  # plan ("mdns"|"bootnode"), bootnode host ("" with mDNS)
    file_transferred = Signal(str, str)  # direction ("↓"|"↑"|"✕"), filename
    file_renamed = Signal(str, str)  # old_path, new_path
    directory_created = Signal(str)  # directory path
    file_progress = Signal(str, int, int)  # filepath, bytes_transferred, total_bytes
    sync_completed = Signal()  # a full sync cycle finished
    transfer_failed = Signal(str, str, str)  # op ("download"|"upload"), filepath, message
    sync_paused = Signal(str, int, int)  # reason, deletes blocked, local files
    error_occurred = Signal(str)  # error message
    auth_error_occurred = Signal(str)  # authentication error (invalid/missing API key)
    path_not_found = Signal(str)  # shared path does not exist
    process_finished = Signal(int, str)  # exit code, exit status description
    master_conflict = Signal(str, str, str)  # conflict_type, peer_cid, peer_address
    no_master_warning = Signal(str)  # no master elected (all peers never-master)
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
            self.error_occurred.emit("hsync binary not found.")
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
                self.file_renamed.emit(str(event.get("src", "")), str(event.get("dst", "")))
            elif name == UiEventName.dir_created:
                path = str(event.get("path", ""))
                if not path.endswith(_HSYNCKEEP):
                    self.directory_created.emit(path)
            elif name == UiEventName.sync_complete:
                self.sync_completed.emit()
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
                self.error_occurred.emit(str(event.get("message", "")))
            elif name == UiEventName.sync_paused:
                self.sync_paused.emit(
                    str(event.get("reason", "")),
                    int(event.get("deletes", 0)),
                    int(event.get("local", 0)),
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

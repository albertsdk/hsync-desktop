# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Synchronous hsync-client CLI helpers: binary discovery/version/capabilities
(with a QSettings-backed probe cache) and the trust-store subcommands.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from hsync_common.constants import HSYNC_VERSION as _EXPECTED_VERSION
from hsync_common.endpoint import format_authority
from hsync_common.protocol.capabilities import (
    CapabilitiesDoc,
    parse_capabilities,
    supports_subcommand,
)
from PySide6.QtCore import QObject, QProcess, QSettings, QTimer, Signal, Slot

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG


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


def _run_hsync_capture(
    binary: str, args: list[str], timeout: float = 15.0
) -> subprocess.CompletedProcess[str] | None:
    """Run ``<binary> <args>`` and return the completed process, or None.

    The single subprocess entry point for the CLI helpers: callers decide how to
    treat a non-zero exit and how to read stdout/stderr.
    """
    try:
        return subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _run_hsync_line(binary: str, args: list[str], timeout: float = 15.0) -> str | None:
    """Run ``<binary> <args>`` and return the last non-empty stdout line, or None."""
    result = _run_hsync_capture(binary, args, timeout)
    if result is None or result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else None


def _endpoint_arg(host: str, port: int | None) -> str:
    """``HOST[:PORT]`` for a client trust subcommand (the port is part of it)."""
    return format_authority(host, port) if port else host


def fetch_bootnode_fingerprint(binary: str, host: str, port: int | None = None) -> str | None:
    """Read a discovery-server certificate fingerprint without trusting it (ADR-0035).

    Runs ``hsync trust discovery-server fingerprint HOST[:PORT]`` with a bounded
    timeout and returns the canonical fingerprint, or ``None`` when the node cannot
    be reached. Used by the GUI pre-flight so the operator can confirm an unknown
    node before the client is started.
    """
    return _run_hsync_line(
        binary, ["trust", "discovery-server", "fingerprint", _endpoint_arg(host, port)]
    )


def fetch_server_fingerprint(binary: str, host: str, port: int | None = None) -> str | None:
    """Read a sync-server certificate fingerprint without trusting it (ADR-0036).

    Runs ``hsync trust server fingerprint HOST[:PORT]`` (raw TLS probe).
    """
    return _run_hsync_line(binary, ["trust", "server", "fingerprint", _endpoint_arg(host, port)])


def _run_hsync_success(binary: str, args: list[str], timeout: float = 15.0) -> bool:
    """Run ``<binary> <args>`` and return True only on a clean exit (code 0)."""
    result = _run_hsync_capture(binary, args, timeout)
    return result is not None and result.returncode == 0


def _run_hsync_json(binary: str, args: list[str], timeout: float = 15.0) -> object | None:
    """Run ``<binary> <args>`` and parse JSON from stdout; None on any failure."""
    result = _run_hsync_capture(binary, args, timeout)
    if result is None or result.returncode != 0:
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


def list_bootnode_trust(binary: str) -> list[dict] | None:
    """Return the discovery-server entries (``hsync trust discovery-server list --json``)."""
    return _only_dict_entries(
        _run_hsync_json(binary, ["trust", "discovery-server", "list", "--json"])
    )


def add_bootnode_trust(binary: str, host: str, fingerprint: str, port: int | None = None) -> bool:
    """Pin a discovery-server fingerprint; True on success."""
    return _run_hsync_success(
        binary, ["trust", "discovery-server", "add", _endpoint_arg(host, port), fingerprint]
    )


def remove_bootnode_trust(binary: str, host: str, port: int | None = None) -> bool:
    """Forget a discovery-server pin; True on success."""
    return _run_hsync_success(
        binary, ["trust", "discovery-server", "remove", _endpoint_arg(host, port)]
    )


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
    """Pin a sync-server fingerprint; True on success."""
    return _run_hsync_success(
        binary, ["trust", "server", "add", _endpoint_arg(host, port), fingerprint]
    )


def remove_server_trust(binary: str, host: str, port: int | None = None) -> bool:
    """Forget a sync-server pin; True on success."""
    return _run_hsync_success(binary, ["trust", "server", "remove", _endpoint_arg(host, port)])


def supports_peer_trust(binary: str | None = None) -> bool:
    """Return True when the binary offers the ``trust`` subcommand.

    An unknown capabilities document (missing/older binary) is treated
    permissively, mirroring the settings-dialog capability gate.
    """
    doc = get_binary_capabilities_cached(binary)
    if doc is None:
        return True
    return supports_subcommand(doc, "trust")


@dataclass(frozen=True)
class ResetStateResult:
    """Outcome of ``hsync state reset`` for one folder.

    ``found`` is False when the folder had no state yet (a successful no-op);
    ``quarantined`` means an unreadable DB was moved aside instead of deleted.
    ``message`` carries the client's own error text (e.g. the lock holder).
    """

    ok: bool
    found: bool = False
    versions: int = 0
    tombstones: int = 0
    quarantined: bool = False
    message: str = ""


def reset_sync_state(binary: str, folder: str, timeout: float = 60.0) -> ResetStateResult:
    """Forget *folder*'s client-side sync state (``hsync state reset --json``).

    Runs with ``--quarantine`` so an unreadable state DB is moved aside instead
    of failing (``quarantined`` then carries the new path). A longer timeout
    than the trust helpers: the command takes the folder's instance lock and
    rewrites a SQLite file, so a large state DB can take a moment. Every
    non-zero exit carries the client's explanation in ``message`` (notably
    "another hsync process is already syncing").
    """
    args = ["state", "reset", "--folder", folder, "--quarantine", "--json"]
    result = _run_hsync_capture(binary, args, timeout)
    if result is None:
        return ResetStateResult(ok=False)
    if result.returncode != 0:
        lines = [
            line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()
        ]
        return ResetStateResult(ok=False, message=lines[-1] if lines else "")
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            return ResetStateResult(ok=False)
        return ResetStateResult(
            ok=True,
            found=bool(payload.get("found", False)),
            versions=int(payload.get("versions_deleted", 0) or 0),
            tombstones=int(payload.get("tombstones_deleted", 0) or 0),
            quarantined=bool(str(payload.get("quarantined", "") or "").strip()),
        )
    except (ValueError, TypeError):
        return ResetStateResult(ok=False)


def find_hsync_binary() -> str | None:
    """Locate the hsync binary: bundled → PATH → sibling project dist (platform-aware)."""
    bin_name = "hsync.exe" if sys.platform == "win32" else "hsync"

    # 1. Bundled alongside this package
    pkg_root = Path(__file__).resolve().parent.parent
    bundled = pkg_root / "bin" / bin_name
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)

    # 2. On PATH
    on_path = shutil.which("hsync")
    if on_path:
        return on_path

    # 3. Sibling project dist/<os>-<arch>/hsync (development / source tree)
    platform_tag = _platform_tag()
    client_root = pkg_root.parent.parent / "hsync-client"
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

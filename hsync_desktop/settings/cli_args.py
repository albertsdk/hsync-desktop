# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
CLI argument builder and helper functions for settings.

Provides functions to build hsync CLI arguments from saved settings
and utility functions to read common settings.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import cast

from PySide6.QtCore import QSettings

from hsync_desktop.config import (
    DEFAULT_BUCKET,
    DEFAULT_GROUP,
    DEFAULT_MAX_INBOUND_SIZE,
    DEFAULT_P2P_ENABLED,
    SETTINGS_APP,
    SETTINGS_ORG,
)


def secure_config_file() -> None:
    """Restrict the QSettings config file to owner-only access (0600).

    On POSIX systems the native QSettings backend writes a plain-text file under
    ``~/.config`` with umask-derived permissions (typically world-readable
    ``0644``). Secrets are Fernet-encrypted, but the file is still restricted so
    other local users cannot read the configuration. QSaveFile preserves the
    existing file's permissions on subsequent writes, so this only needs to run
    once the file exists (at startup and after the settings dialog saves).
    """
    if os.name != "posix":
        return
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    s.sync()
    path = s.fileName()
    try:
        if path and os.path.exists(path):
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


from hsync_desktop.settings.validators import (
    _validate_bucket,
    _validate_group_name,
    _validate_path,
)
from hsync_desktop.themes import detect_system_theme


def build_hsync_args(local_path: str, force_dry_run: bool = False) -> list[str]:
    """Read persisted settings and return hsync CLI argument list.

    Args:
        local_path: The local directory path to sync.
        force_dry_run: If True, always add --dry-run flag regardless of settings.

    Returns:
        List of command-line arguments for hsync binary.

    Raises:
        ValueError: If input validation fails.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    p2p_enabled = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))
    args: list[str] = ["p2p" if p2p_enabled else "server"]

    # Validate local_path - must be a valid directory
    if local_path:
        validated_path = _validate_path(local_path)
        if validated_path is None:
            raise ValueError(f"Invalid local path: {local_path}")
        # Additional check: path must exist and be a directory
        if not Path(validated_path).is_dir():
            raise ValueError(f"Local path is not a valid directory: {local_path}")

    # Bucket – use default if not set
    bucket_raw = str(s.value("sync/bucket", DEFAULT_BUCKET, str))
    bucket = bucket_raw or DEFAULT_BUCKET
    validated_bucket = _validate_bucket(bucket)
    if validated_bucket is None:
        validated_bucket = DEFAULT_BUCKET  # Fallback to safe default
    args += ["-b", validated_bucket]

    # Path (validated above)
    if local_path:
        args += ["-p", local_path]

    # Connection (server subcommand only). The server endpoint travels on the
    # environment channel (engine.apply_settings_env exports HSYNC_SERVER from
    # the same setting): the client CLI takes the bare host + --port and has no
    # URL flag, so the validated full URL is passed unchanged via env.
    if not p2p_enabled:
        if s.value("connection/insecure", False, bool):
            args.append("--insecure")

        # CA cert - validate it exists if specified
        ca_raw = str(s.value("connection/ca_cert", "", str))
        if ca_raw:
            # Only add if file exists and path is safe
            ca_path = _validate_path(ca_raw, allow_absolute=True)
            if ca_path and Path(ca_path).exists():
                args += ["--ca-cert", ca_path]

    # Validate HTTP timeout is in reasonable range
    http_timeout = cast(int, s.value("connection/http_timeout", 30, int))
    http_timeout = max(1, min(http_timeout, 300))  # Clamp to 1-300 seconds
    args += ["--http-timeout", str(http_timeout)]

    # Sync. Continuous/daemon mode is the client default: only the one-shot
    # opt-out is emitted.
    if not s.value("sync/continuous", True, bool):
        args.append("--once")
    resync = cast(int, s.value("sync/resync", 0, int))
    resync = max(0, min(resync, 86400))  # Clamp to 0-24 hours
    if resync > 0:
        args += ["-i", str(resync)]

    # Validate retry delay
    retry_delay = cast(int, s.value("sync/retry_delay", 5, int))
    retry_delay = max(1, min(retry_delay, 60))  # Clamp to 1-60 seconds
    args += ["--retry-delay", str(retry_delay)]

    # Validate stability delay
    stability_delay = cast(int, s.value("sync/stability_delay", 0, int))
    stability_delay = max(0, min(stability_delay, 3600))  # Clamp to 0-1 hour
    if stability_delay > 0:
        args += ["--stability-delay", str(stability_delay)]

    # Validate max wait
    max_wait = cast(int, s.value("sync/max_wait", 120, int))
    max_wait = max(10, min(max_wait, 3600))  # Clamp to 10-3600 seconds
    args += ["--max-wait-timeout", str(max_wait)]

    # Validate min free disk space
    min_free = cast(int, s.value("sync/min_free_disk_space", 500, int))
    min_free = max(0, min(min_free, 100_000))  # Clamp to 0-100000 MB
    args += ["--min-free-disk-space", str(min_free)]

    # Validate max inbound file size (absolute anti-bomb cap)
    max_dl = cast(int, s.value("sync/max_inbound_size", DEFAULT_MAX_INBOUND_SIZE, int))
    max_dl = max(0, min(max_dl, 10_000_000))  # Clamp to 0-10000000 MB
    args += ["--max-inbound-size", str(max_dl)]

    if s.value(
        "sync/ignore_delete", False, bool
    ):  # default False matches config.py DEFAULT_IGNORE_DELETE
        args.append("--ignore-delete")

    # Validate sync direction
    sync_dir = str(s.value("sync/direction", "bidirectional", str))
    valid_directions = ("bidirectional", "upload-only", "download-only")
    if sync_dir not in valid_directions:
        sync_dir = "bidirectional"
    if sync_dir != "bidirectional":
        args += ["--sync-direction", sync_dir]

    # Validate filter path
    filter_path_raw = str(s.value("sync/filter_path", "", str))
    if filter_path_raw:
        validated_filter = _validate_path(filter_path_raw)
        if validated_filter:
            args += ["--subdir", validated_filter]

    # Sync hidden files (default False: hidden/system files are excluded)

    # Extra ignore patterns (comma-separated, layered on .hsyncignore)
    ignore_patterns_raw = str(s.value("sync/ignore_patterns", "", str)).strip()
    if ignore_patterns_raw:
        for raw_pattern in ignore_patterns_raw.split(","):
            pattern = raw_pattern.strip()
            if pattern:
                args += ["--ignore-pattern", pattern]

    # Read new key; fall back to inverted legacy key for migration
    if s.contains("sync/compression_enabled"):
        compression_on = bool(s.value("sync/compression_enabled", True, bool))
    else:
        compression_on = not bool(s.value("sync/no_compression", False, bool))
    if not compression_on:
        args.append("--no-compression")
    if force_dry_run or s.value("sync/dry_run", False, bool):
        args.append("-n")

    # p2p
    if p2p_enabled:
        port = cast(int, s.value("p2p/port", 0, int))
        port = max(0, min(port, 65535))  # Valid port range
        if port:
            args += ["--listen-port", str(port)]

        # Validate discovery timeout
        discovery_timeout = cast(int, s.value("p2p/discovery_timeout", 10, int))
        discovery_timeout = max(1, min(discovery_timeout, 60))  # 1-60 seconds
        args += ["--discovery-timeout", str(discovery_timeout)]

        # p2p group: an optional partition key (the client's --group is optional;
        # "no group" is its own partition). An emptied setting must clear the
        # group instead of silently re-applying a group name. Only a missing key
        # falls back to the default group (a fresh install seeds it in the UI).
        grp_raw = str(s.value("p2p/group", DEFAULT_GROUP, str)).strip()
        if grp_raw:
            validated_grp = _validate_group_name(grp_raw)
            args += ["--group", validated_grp or DEFAULT_GROUP]

        if s.value("p2p/prefer_master", False, bool):
            args.append("--prefer-master")
        if s.value("p2p/never_master", False, bool):
            args.append("--never-master")
        if s.value("p2p/require_pairing", False, bool):
            args.append("--require-pairing")

    # Bandwidth limits
    upload_bps, download_bps = get_bandwidth_limits()
    if upload_bps is not None:
        args += ["--limit-upload", str(upload_bps)]
    if download_bps is not None:
        args += ["--limit-download", str(download_bps)]

    # Always accept the deletion risk – hsync-desktop handles deletion-risk
    # confirmation via its own dialog.
    args.append("--allow-deletions")

    # Output – always use --no-color for machine-friendly parsing
    # NOTE: We intentionally NEVER pass -q (quiet) because hsync-desktop
    # depends on parsing stdout for status updates, file transfers,
    # authentication errors, etc. Quiet mode would break all UI feedback.
    args.append("--no-color")
    if s.value("output/verbose", False, bool):
        args.append("-v")

    # Validate logfile path
    logfile_raw = str(s.value("output/logfile", "", str))
    if logfile_raw:
        validated_logfile = _validate_path(logfile_raw, allow_absolute=True)
        if validated_logfile:
            args += ["--log-file", validated_logfile]

    return args


def get_saved_theme() -> str:
    """Return the persisted theme name, defaulting to system theme."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    # Use system theme as default if no theme has been saved
    default_theme = detect_system_theme()
    return str(s.value("appearance/theme", default_theme, str))


def are_notifications_enabled() -> bool:
    """Return whether notifications are enabled."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/notifications", True, bool))


def is_log_panel_visible() -> bool:
    """Return whether the log panel should be visible (default: hidden)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/show_log", False, bool))


def is_auto_sync_enabled() -> bool:
    """Return whether auto-sync on startup is enabled (default: disabled)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("sync/auto_sync", False, bool))


def get_bandwidth_limits() -> tuple[int | None, int | None]:
    """Return the saved bandwidth limits (upload, download) in bytes/sec.

    Returns:
        Tuple of (upload_bps, download_bps) where None means unlimited.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    upload_raw = s.value("sync/bandwidth_upload", None)
    download_raw = s.value("sync/bandwidth_download", None)

    upload: int | None = None
    download: int | None = None

    # Validate and convert from MB/s to bytes/s if stored as float
    if upload_raw is not None:
        try:
            upload_val = float(
                str(upload_raw)
            )  # Convert to string first to handle weird QSettings values
            upload = int(upload_val * 1024 * 1024)
        except (ValueError, TypeError):
            # Invalid stored value - remove and treat as unlimited
            s.remove("sync/bandwidth_upload")

    if download_raw is not None:
        try:
            download_val = float(
                str(download_raw)
            )  # Convert to string first to handle weird QSettings values
            download = int(download_val * 1024 * 1024)
        except (ValueError, TypeError):
            # Invalid stored value - remove and treat as unlimited
            s.remove("sync/bandwidth_download")

    return upload, download


def save_bandwidth_limits(upload_mbps: float | None, download_mbps: float | None) -> None:
    """Save bandwidth limits to QSettings.

    Args:
        upload_mbps: Upload limit in MB/s, or None for unlimited.
        download_mbps: Download limit in MB/s, or None for unlimited.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    if upload_mbps is not None and upload_mbps > 0:
        s.setValue("sync/bandwidth_upload", upload_mbps)
    else:
        s.remove("sync/bandwidth_upload")

    if download_mbps is not None and download_mbps > 0:
        s.setValue("sync/bandwidth_download", download_mbps)
    else:
        s.remove("sync/bandwidth_download")

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
CLI argument builder and helper functions for settings.

Provides functions to build hsync CLI arguments from saved settings
and utility functions to read common settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QSettings

from hsync_desktop.config import (
    DEFAULT_BUCKET,
    DEFAULT_GROUP,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.settings.validators import (
    _validate_bucket,
    _validate_group_name,
    _validate_path,
    _validate_url,
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
    args: list[str] = []

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

    # Connection - validate URL
    url_raw = str(s.value("connection/server_url", "", str))
    validated_url = _validate_url(url_raw)
    if validated_url:
        args += ["-s", validated_url]
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
    args += ["--timeout", str(http_timeout)]

    # Sync
    if s.value("sync/continuous", True, bool):
        args.append("-w")
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

    if s.value("sync/ignore_delete", True, bool):
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
            args += ["--filter-path", validated_filter]

    if s.value("sync/no_compression", False, bool):
        args.append("--no-compression")
    if force_dry_run or s.value("sync/dry_run", False, bool):
        args.append("-n")

    # LAN
    if s.value("lan/enabled", False, bool):
        args.append("--lan-mode")
        port = cast(int, s.value("lan/port", 0, int))
        port = max(0, min(port, 65535))  # Valid port range
        if port:
            args += ["--lan-port", str(port)]

        # Validate discovery timeout
        discovery_timeout = cast(int, s.value("lan/discovery_timeout", 10, int))
        discovery_timeout = max(1, min(discovery_timeout, 60))  # 1-60 seconds
        args += ["--discovery-timeout", str(discovery_timeout)]

        # Validate LAN group
        grp_raw = str(s.value("lan/group", DEFAULT_GROUP, str))
        grp = grp_raw or DEFAULT_GROUP
        validated_grp = _validate_group_name(grp)
        if validated_grp is None:
            validated_grp = DEFAULT_GROUP
        args += ["--lan-group", validated_grp]

        if not s.value("lan/https", True, bool):
            args.append("--no-lan-https")
        if not s.value("lan/persistent", True, bool):
            args.append("--no-lan-persistent")
        if s.value("lan/force_master", False, bool):
            args.append("--force-master")

    # Bandwidth limits
    upload_bps, download_bps = get_bandwidth_limits()
    if upload_bps is not None:
        args += ["--max-bandwidth-upload", str(upload_bps)]
    if download_bps is not None:
        args += ["--max-bandwidth-download", str(download_bps)]

    # Always skip CLI confirmation prompts – hsync-desktop handles
    # deletion-risk confirmation via its own dialog.
    args.append("--yes")

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
            args += ["-o", validated_logfile]

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
    upload = s.value("sync/bandwidth_upload", None)
    download = s.value("sync/bandwidth_download", None)

    # Convert from MB/s to bytes/s if stored as float
    if upload is not None:
        upload = int(cast(float, upload) * 1024 * 1024)
    if download is not None:
        download = int(cast(float, download) * 1024 * 1024)

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

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

from hsync_common.protocol.pairing import (
    SYNC_DIRECTION_BIDIRECTIONAL,
    SYNC_DIRECTION_DOWNLOAD_ONLY,
    SYNC_DIRECTION_UPLOAD_ONLY,
)
from PySide6.QtCore import QSettings

from hsync_desktop.config import (
    BANDWIDTH_MAX_BPS,
    BANDWIDTH_MAX_MBPS,
    BANDWIDTH_MIN_BPS,
    DEFAULT_AUTOTUNE,
    DEFAULT_BUCKET,
    DEFAULT_DELETION_POLICY,
    DEFAULT_DELTA_ENABLED,
    DEFAULT_DELTA_MIN_FILE_SIZE_KB,
    DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB,
    DEFAULT_FONT_SCALE,
    DEFAULT_GROUP,
    DEFAULT_MASS_DELETE_GUARD,
    DEFAULT_MASS_DELETE_PERCENT,
    DEFAULT_MASS_DELETE_THRESHOLD,
    DEFAULT_MAX_INBOUND_SIZE,
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_FREE_DISK_SPACE,
    DEFAULT_P2P_ENABLED,
    DEFAULT_P2P_PEER_DOWNLOAD,
    DEFAULT_P2P_TRUST,
    DEFAULT_RESYNC_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_STABILITY_DELAY,
    DEFAULT_SYNC_DIRECTION,
    DELETION_POLICIES,
    FONT_SCALE_COMPACT,
    FONT_SCALE_STANDARD,
    GUI_MAX_WAIT_MIN,
    GUI_RETRY_DELAY_MIN,
    MAX_INBOUND_SIZE_MB_MAX,
    MAX_INBOUND_SIZE_MB_MIN,
    MAX_WAIT_MAX,
    MIN_FREE_DISK_SPACE_MB_MAX,
    MIN_FREE_DISK_SPACE_MB_MIN,
    MIN_RESYNC_INTERVAL,
    NOTIFICATION_CATEGORIES,
    RESYNC_MAX,
    RETRY_DELAY_MAX,
    SETTINGS_APP,
    SETTINGS_ORG,
    STABILITY_DELAY_MAX,
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
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, detect_system_theme


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
    _append_target_args(args, s, local_path)
    _append_connection_args(args, s, p2p_enabled)
    _append_sync_args(args, s, force_dry_run)
    _append_advanced_args(args, s)
    _append_p2p_args(args, s, p2p_enabled)
    _append_output_args(args, s)

    return args


def _append_target_args(args: list[str], s: QSettings, local_path: str) -> None:
    """Append the bucket and the validated local path."""
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


def _append_connection_args(args: list[str], s: QSettings, p2p_enabled: bool) -> None:
    """Append the server connection flags and the shared HTTP timeout."""
    # Connection (server subcommand only). The server endpoint travels on the
    # environment channel (engine.apply_settings_env exports HSYNC_SERVER_URL from
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
    http_timeout = max(5, min(http_timeout, 300))
    args += ["--http-timeout", str(http_timeout)]


def _append_sync_args(args: list[str], s: QSettings, force_dry_run: bool) -> None:
    """Append the sync/timing/compression flags."""
    # Sync. Continuous/daemon mode is the client default: only the one-shot
    # opt-out is emitted. A simulation is inherently one-shot: the client must
    # exit after its preview, otherwise the preview's confirm step (a SYNC
    # command) would switch it to a real sync and apply the very changes the
    # setting promises to skip.
    simulation = bool(s.value("sync/dry_run", False, bool))
    if simulation or not s.value("sync/continuous", True, bool):
        args.append("--once")
    _append_timing_args(args, s)
    _append_sync_mode_args(args, s, simulation, force_dry_run)


def _append_timing_args(args: list[str], s: QSettings) -> None:
    """Append the periodic/timing and size-limit flags."""
    resync = cast(int, s.value("sync/resync", DEFAULT_RESYNC_INTERVAL, int))
    resync = max(0, min(resync, RESYNC_MAX))
    if 0 < resync < MIN_RESYNC_INTERVAL:
        resync = MIN_RESYNC_INTERVAL
    if resync > 0:
        args += ["-i", str(resync)]

    retry_delay = cast(int, s.value("sync/retry_delay", DEFAULT_RETRY_DELAY, int))
    retry_delay = max(GUI_RETRY_DELAY_MIN, min(retry_delay, RETRY_DELAY_MAX))
    args += ["--retry-delay", str(retry_delay)]

    stability_delay = cast(int, s.value("sync/stability_delay", 0, int))
    stability_delay = max(0, min(stability_delay, STABILITY_DELAY_MAX))
    if stability_delay > 0:
        args += ["--stability-delay", str(stability_delay)]

    max_wait = cast(int, s.value("sync/max_wait", DEFAULT_MAX_WAIT, int))
    max_wait = max(GUI_MAX_WAIT_MIN, min(max_wait, MAX_WAIT_MAX))
    args += ["--max-wait-timeout", str(max_wait)]

    min_free = cast(int, s.value("sync/min_free_disk_space", DEFAULT_MIN_FREE_DISK_SPACE, int))
    min_free = max(MIN_FREE_DISK_SPACE_MB_MIN, min(min_free, MIN_FREE_DISK_SPACE_MB_MAX))
    # The CLI takes a size with an explicit unit (a bare number is rejected).
    args += ["--min-free-disk-space", f"{min_free}MB"]

    max_dl = cast(int, s.value("sync/max_inbound_size", DEFAULT_MAX_INBOUND_SIZE, int))
    max_dl = max(MAX_INBOUND_SIZE_MB_MIN, min(max_dl, MAX_INBOUND_SIZE_MB_MAX))
    args += ["--max-inbound-size", str(max_dl)]


def _append_sync_mode_args(
    args: list[str], s: QSettings, simulation: bool, force_dry_run: bool
) -> None:
    """Append the sync-mode, filter, ignore and compression flags."""
    args += ["--deletion-policy", get_deletion_policy()]

    sync_dir = get_sync_direction()
    if sync_dir != DEFAULT_SYNC_DIRECTION:
        args += ["--sync-direction", sync_dir]

    _append_filter_args(args, s)
    _append_compression_args(args, s, simulation, force_dry_run)


def _append_filter_args(args: list[str], s: QSettings) -> None:
    """Append the subdirectory filter and extra ignore patterns."""
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


def _append_compression_args(
    args: list[str], s: QSettings, simulation: bool, force_dry_run: bool
) -> None:
    """Append the compression and dry-run flags."""
    # Read new key; fall back to inverted legacy key for migration
    if s.contains("sync/compression_enabled"):
        compression_on = bool(s.value("sync/compression_enabled", True, bool))
    else:
        compression_on = not bool(s.value("sync/no_compression", False, bool))
    if not compression_on:
        args.append("--no-compression")
    if force_dry_run or simulation:
        args.append("-n")


def _append_advanced_args(args: list[str], s: QSettings) -> None:
    """Append the engine tuning flags."""
    # Advanced tab (engine tuning). Values matching the client default are
    # omitted so the engine keeps its own default/auto behaviour.
    if not s.value("advanced/autotune", DEFAULT_AUTOTUNE, bool):
        args.append("--no-autotune")
    max_concurrent = cast(int, s.value("advanced/max_concurrent_transfers", 0, int))
    max_concurrent = max(0, min(max_concurrent, 20))
    if max_concurrent > 0:
        args += ["--max-concurrent-transfers", str(max_concurrent)]

    if not s.value("advanced/delta_enabled", DEFAULT_DELTA_ENABLED, bool):
        args.append("--no-delta")
    delta_remote_kb = cast(
        int, s.value("advanced/delta_min_file_size_kb", DEFAULT_DELTA_MIN_FILE_SIZE_KB, int)
    )
    if delta_remote_kb != DEFAULT_DELTA_MIN_FILE_SIZE_KB:
        args += ["--delta-min-file-size", str(max(0, delta_remote_kb) * 1024)]
    delta_p2p_kb = cast(
        int, s.value("advanced/delta_min_file_size_p2p_kb", DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB, int)
    )
    if delta_p2p_kb != DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB:
        args += ["--delta-min-file-size-p2p", str(max(0, delta_p2p_kb) * 1024)]

    if not s.value("advanced/mass_delete_guard", DEFAULT_MASS_DELETE_GUARD, bool):
        args.append("--no-mass-delete-guard")
    guard_threshold = cast(
        int, s.value("advanced/mass_delete_threshold", DEFAULT_MASS_DELETE_THRESHOLD, int)
    )
    guard_threshold = max(0, min(guard_threshold, 1_000_000))
    args += ["--mass-delete-threshold", str(guard_threshold)]
    guard_percent = cast(
        int, s.value("advanced/mass_delete_percent", DEFAULT_MASS_DELETE_PERCENT, int)
    )
    guard_percent = max(0, min(guard_percent, 100))
    args += ["--mass-delete-percent", str(guard_percent)]


# P2P master trust policies the client accepts (ADR-0040). A stored value
# outside this set comes from a hand-edited settings file and is dropped.
_P2P_TRUST_POLICIES = frozenset({"ask", "accept-new", "strict"})


def _append_p2p_args(args: list[str], s: QSettings, p2p_enabled: bool) -> None:
    """Append the p2p flags; a no-op in server mode."""
    # p2p
    if p2p_enabled:
        port = cast(int, s.value("p2p/port", 0, int))
        port = max(0, min(port, 65535))  # Valid port range
        if port:
            args += ["--listen-port", str(port)]

        # Validate rendezvous timeout (the client names it peer-rendezvous-timeout,
        # so the peer-rendezvous surface is distinct from the rendezvous-server one).
        rendezvous_timeout = cast(int, s.value("p2p/rendezvous_timeout", 10, int))
        rendezvous_timeout = max(5, min(rendezvous_timeout, 60))
        args += ["--peer-rendezvous-timeout", str(rendezvous_timeout)]

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
        trust = str(s.value("p2p/trust", DEFAULT_P2P_TRUST, str))
        args += ["--p2p-trust", trust if trust in _P2P_TRUST_POLICIES else DEFAULT_P2P_TRUST]
        if not s.value("p2p/peer_download", DEFAULT_P2P_PEER_DOWNLOAD, bool):
            args.append("--no-peer-download")


def _append_output_args(args: list[str], s: QSettings) -> None:
    """Append bandwidth, deletion, output and log-file flags."""
    # Bandwidth limits
    upload_bps, download_bps = get_bandwidth_limits()
    if upload_bps is not None:
        args += ["--limit-upload", str(upload_bps)]
    if download_bps is not None:
        args += ["--limit-download", str(download_bps)]

    # Always accept the deletion risk – hsync-desktop handles deletion-risk
    # confirmation via its own dialog.
    args.append("--allow-deletions")

    # Output – keep the client's own palette: --color=always forces the SGR
    # sequences over the (non-TTY) pipe so the log panel can render them. The
    # structured events fd, not stdout, is what drives the UI.
    # NOTE: We intentionally NEVER pass -q (quiet) because hsync-desktop needs
    # stdout for the log panel.
    args.append("--color=always")
    if s.value("output/verbose", False, bool):
        args.append("-v")

    # Validate logfile path
    logfile_raw = str(s.value("output/logfile", "", str))
    if logfile_raw:
        validated_logfile = _validate_path(logfile_raw, allow_absolute=True)
        if validated_logfile:
            args += ["--log-file", validated_logfile]


def _drop_option(args: list[str], flag: str, takes_value: bool = False) -> list[str]:
    """Return *args* without *flag* (and its following value when requested)."""
    out: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == flag:
            i += 2 if takes_value else 1
            continue
        out.append(args[i])
        i += 1
    return out


def build_selection_args(
    local_path: str, subdir: str, direction: str, *, dry_run: bool = False
) -> list[str]:
    """Build a one-shot Send/Receive of a subdirectory.

    Starts from :func:`build_hsync_args` and forces a single cycle in a single
    direction scoped to *subdir*, so "Send/Receive now" on a selection never
    changes the persisted continuous flag, sync direction or folder filter.
    ``dry_run=True`` adds ``--dry-run`` for the confirmation preview.
    """
    args = build_hsync_args(local_path)
    args = _drop_option(args, "--once")
    args = _drop_option(args, "--sync-direction", takes_value=True)
    args = _drop_option(args, "--subdir", takes_value=True)
    if direction != "bidirectional":
        # The client rejects --prefer-master with a non-bidirectional
        # --sync-direction (the p2p master always syncs both ways,
        # hsync-client cli.py). build_hsync_args emits --prefer-master from the
        # persisted setting, which the settings dialog only screens for the
        # continuous combination; this transient one-shot override is not, so it
        # must drop the flag itself. A directed one-shot cannot act as a
        # bidirectional master anyway.
        args = _drop_option(args, "--prefer-master")
        args += ["--sync-direction", direction]
    if subdir:
        # ``--subdir`` is bucket-relative: keep it relative (never absolutize)
        # and reject traversal. ``_validate_path`` would resolve it to an
        # absolute path, so it is not used here.
        rel = subdir.replace("\\", "/").strip("/")
        if rel and ".." not in rel.split("/"):
            args += ["--subdir", rel]
    if dry_run:
        args.append("--dry-run")
    args.append("--once")
    return args


def get_theme_setting() -> str:
    """Return the raw theme preference: ``system``, ``light`` or ``dark``."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return str(s.value("appearance/theme", THEME_SYSTEM, str))


def get_saved_theme() -> str:
    """Return the effective theme name, resolving "system" to the OS scheme."""
    setting = get_theme_setting()
    if setting in (THEME_LIGHT, THEME_DARK):
        return setting
    return detect_system_theme()


def get_saved_font_scale() -> str:
    """Return the saved global font scale ("standard" or "compact")."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    value = str(s.value("appearance/font_scale", DEFAULT_FONT_SCALE, str))
    return value if value in (FONT_SCALE_STANDARD, FONT_SCALE_COMPACT) else DEFAULT_FONT_SCALE


def are_notifications_enabled() -> bool:
    """Return whether notifications are enabled."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/notifications", True, bool))


def get_enabled_notification_categories() -> frozenset[str]:
    """Return the notification categories the user enabled (default: all)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return frozenset(
        category
        for category in NOTIFICATION_CATEGORIES
        if bool(s.value(f"appearance/notifications/{category}", True, bool))
    )


def is_log_panel_visible() -> bool:
    """Return whether the log panel should be visible (default: hidden)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/show_log", False, bool))


def is_auto_sync_enabled() -> bool:
    """Return whether auto-sync on startup is enabled (default: disabled)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("sync/auto_sync", False, bool))


def is_simulation_mode() -> bool:
    """Return whether Simulation Mode is enabled (default: disabled).

    Simulation Mode makes every run a preview-only one-shot (``--once -n``), so
    nothing is transferred or deleted. Callers use it to skip the prompts and
    follow-ups that only make sense for a run that applies changes.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("sync/dry_run", False, bool))


SYNC_DIRECTIONS: tuple[str, ...] = (
    SYNC_DIRECTION_BIDIRECTIONAL,
    SYNC_DIRECTION_UPLOAD_ONLY,
    SYNC_DIRECTION_DOWNLOAD_ONLY,
)


def get_sync_direction() -> str:
    """Return the saved sync direction, falling back to the product default.

    One read site for the engine arguments and for the confirmation dialog, so
    the direction a run applies and the direction the dialog states can never
    disagree.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    direction = str(s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str))
    return direction if direction in SYNC_DIRECTIONS else DEFAULT_SYNC_DIRECTION


def get_deletion_policy() -> str:
    """Return the saved deletion policy (``propagate`` or ``keep``).

    One read site for the main-window badge and for the engine arguments, so the
    indicator can never disagree with the flag the engine actually receives.
    An unreadable value falls back to the product default.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    policy = str(s.value("sync/deletion_policy", DEFAULT_DELETION_POLICY, str))
    return policy if policy in DELETION_POLICIES else DEFAULT_DELETION_POLICY


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
            upload = max(BANDWIDTH_MIN_BPS, min(int(upload_val * 1024 * 1024), BANDWIDTH_MAX_BPS))
        except (ValueError, TypeError):
            # Invalid stored value - remove and treat as unlimited
            s.remove("sync/bandwidth_upload")

    if download_raw is not None:
        try:
            download_val = float(
                str(download_raw)
            )  # Convert to string first to handle weird QSettings values
            download = max(
                BANDWIDTH_MIN_BPS, min(int(download_val * 1024 * 1024), BANDWIDTH_MAX_BPS)
            )
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
        s.setValue("sync/bandwidth_upload", min(float(upload_mbps), BANDWIDTH_MAX_MBPS))
    else:
        s.remove("sync/bandwidth_upload")

    if download_mbps is not None and download_mbps > 0:
        s.setValue("sync/bandwidth_download", min(float(download_mbps), BANDWIDTH_MAX_MBPS))
    else:
        s.remove("sync/bandwidth_download")

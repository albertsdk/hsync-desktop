# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Configuration defaults for HSYNC Desktop.

Centralizes all default values used throughout the application
to avoid hardcoding and ensure consistency.
"""

from __future__ import annotations

# QSettings organization and application name
# These are used by QSettings to store application settings
SETTINGS_ORG = "HSYNC"
SETTINGS_APP = "HSYNCDesktop"

# Start hidden in the tray. Shared contract between the OS autostart entry
# (autostart.py writes it) and the startup gate (main.py recognizes it).
MINIMIZED_FLAG = "--minimized"

# Default sync settings
DEFAULT_BUCKET = "my-bucket"
DEFAULT_GROUP = "my-group"

# Connection defaults
DEFAULT_INSECURE = False
DEFAULT_CA_CERT = ""
# Server TLS trust policy (ADR-0036): chain (default) | ask | accept-new |
# strict | none. Passed to hsync-client via --server-trust.
DEFAULT_SERVER_TRUST = "chain"
DEFAULT_HTTP_TIMEOUT = 30

# Sync defaults
DEFAULT_CONTINUOUS = True
DEFAULT_IGNORE_DELETE = False
DEFAULT_SYNC_DIRECTION = "bidirectional"
DEFAULT_RESYNC_INTERVAL = 0
# The client rejects a periodic check below this interval (0 = disabled).
MIN_RESYNC_INTERVAL = 20
DEFAULT_RETRY_DELAY = 5
DEFAULT_STABILITY_DELAY = 5
DEFAULT_MAX_WAIT = 600
DEFAULT_FILTER_PATH = ""
DEFAULT_NO_COMPRESSION = False  # Default for migrating the legacy sync/no_compression setting
DEFAULT_COMPRESSION_ENABLED = True
DEFAULT_DRY_RUN = False
DEFAULT_AUTO_SYNC = False
DEFAULT_MIN_FREE_DISK_SPACE = 500  # MB
# Absolute cap on a single inbound file (--max-inbound-size); mirrors the
# client CLI default. 0 = disabled.
DEFAULT_MAX_INBOUND_SIZE = 10240  # MB
DEFAULT_IGNORE_PATTERNS = ""

# Advanced tab — engine tuning mirrors of the client CLI/env (hsync-client
# constants.py). Values are omitted from the CLI when they match the client
# default so the engine keeps its own default/auto behaviour.
DEFAULT_MASS_DELETE_GUARD = True
DEFAULT_MASS_DELETE_THRESHOLD = 50  # deletions per cycle that trip the guard (0 = off)
DEFAULT_MASS_DELETE_PERCENT = 50  # percent of local files (0 = off)
DEFAULT_AUTOTUNE = True
DEFAULT_MAX_CONCURRENT_TRANSFERS = 0  # 0 = omit (client default 5, autotuned)
DEFAULT_DELTA_ENABLED = True
DEFAULT_DELTA_MIN_FILE_SIZE_KB = 256  # client default 256 KB (remote)
DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB = 1024  # client default 1 MB (p2p)

# p2p defaults
# p2p is the default mode on a fresh install (no stored p2p/enabled yet).
DEFAULT_P2P_ENABLED = True
DEFAULT_P2P_KEY = ""
DEFAULT_P2P_PORT = 0  # 0 = auto-assign
DEFAULT_DISCOVERY_TIMEOUT = 10
DEFAULT_PREFER_MASTER = False
DEFAULT_NEVER_MASTER = False
DEFAULT_P2P_REQUIRE_PAIRING = False
# Optional bootnode host for cross-network discovery (bare hostname; empty =
# mDNS-only). Passed to hsync-client via HSYNC_BOOTNODE.
DEFAULT_P2P_BOOTNODE = ""
# Bootnode TLS trust policy (ADR-0035): ask | accept-new | strict | none.
# Passed via HSYNC_BOOTNODE_TRUST.
DEFAULT_P2P_BOOTNODE_TRUST = "ask"
# Map the master TCP port with UPnP when a bootnode is used. Passed via
# HSYNC_UPNP_ENABLED; the client treats it as on only with a bootnode by default.
DEFAULT_P2P_UPNP_ENABLED = True
# Comma-separated SNTP servers (ADR-0023) passed to hsync-client via the
# HSYNC_NTP_HOSTS environment variable. Empty = client defaults
# (pool.ntp.org, time.cloudflare.com, time.google.com); entries may carry a
# port override (host:port).
DEFAULT_NTP_HOSTS = ""
# Download file blocks from other peers in p2p mode (--no-peer-download when
# off); the read/source caps are env-only (HSYNC_P2P_PEER_READ_CAP,
# HSYNC_P2P_PEER_SOURCES_MAX).
DEFAULT_P2P_PEER_DOWNLOAD = True
DEFAULT_P2P_PEER_READ_CAP = 2
DEFAULT_P2P_PEER_SOURCES_MAX = 3

# Bandwidth limits: the client enforces [1 KB/s, 100 MB/s] on
# --limit-upload/--limit-download (hsync-client constants.py::BANDWIDTH_MIN/MAX),
# so the GUI caps its fields and clamps stored values to the same range.
BANDWIDTH_MIN_BPS = 1024
BANDWIDTH_MAX_MBPS = 100.0
BANDWIDTH_MAX_BPS = int(BANDWIDTH_MAX_MBPS * 1024 * 1024)

# Output defaults
DEFAULT_VERBOSE = False
DEFAULT_QUIET = False
DEFAULT_LOGFILE = ""
DEFAULT_SHOW_LOG_PANEL = False

# Appearance defaults
DEFAULT_NOTIFICATIONS = True
# Per-event notification categories (all enabled by default).
NOTIFICATION_CATEGORIES = ("errors", "connection", "sync", "peers")
DEFAULT_TOOLTIPS = True
# Global font size: follow the desktop ("standard") or reduce every
# application font by one point ("compact").
FONT_SCALE_STANDARD = "standard"
FONT_SCALE_COMPACT = "compact"
DEFAULT_FONT_SCALE = FONT_SCALE_STANDARD
# Start the GUI at OS login, minimized to the tray (desktop-only; writes an OS
# autostart entry on save, no client CLI flag).
DEFAULT_START_AT_LOGIN = False

# File panel
FILE_BATCH_SIZE = 50
CONSISTENCY_CHECK_INTERVAL_MS = 5000

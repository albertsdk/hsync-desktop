# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Configuration defaults for HSYNC Desktop.

Centralizes all default values used throughout the application
to avoid hardcoding and ensure consistency.
"""

from __future__ import annotations

from hsync_common import defaults
from hsync_common.constants import DELTA_MIN_FILE_SIZE, DELTA_MIN_FILE_SIZE_P2P
from hsync_common.disk import BYTES_PER_MB

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
DEFAULT_HTTP_TIMEOUT = defaults.HTTP_TIMEOUT_DEFAULT

# Sync defaults
DEFAULT_CONTINUOUS = True
# Deletion policy (shared vocabulary with the client): ``propagate`` applies
# deletions in both directions, ``keep`` never deletes on this device (an
# additive backup target).
DELETION_POLICIES = defaults.DELETION_POLICIES
DEFAULT_DELETION_POLICY = defaults.DELETION_POLICY_DEFAULT
DEFAULT_SYNC_DIRECTION = defaults.SYNC_DIRECTION_DEFAULT
DEFAULT_RESYNC_INTERVAL = 0
# The client rejects a periodic check below this interval (0 = disabled).
MIN_RESYNC_INTERVAL = 20
DEFAULT_RETRY_DELAY = defaults.RECONNECT_DELAY_DEFAULT
DEFAULT_STABILITY_DELAY = defaults.STABILITY_DELAY_DEFAULT
# Upper bound on one upload's stability wait; the same value the client uses
# (``hsync_common.defaults``) so the GUI and the CLI behave identically.
DEFAULT_MAX_WAIT = defaults.MAX_WAIT_TIMEOUT_DEFAULT
DEFAULT_FILTER_PATH = ""
DEFAULT_NO_COMPRESSION = False  # Default for migrating the legacy sync/no_compression setting
DEFAULT_COMPRESSION_ENABLED = True
DEFAULT_DRY_RUN = False
DEFAULT_AUTO_SYNC = False
# The release update check is opt-in: an installation that never asked about
# updates makes no request outside the servers the operator configured
# (ADR-0048).
DEFAULT_UPDATE_CHECK = False
DEFAULT_MIN_FREE_DISK_SPACE = defaults.MIN_FREE_DISK_SPACE_DEFAULT // BYTES_PER_MB  # MB
# Absolute cap on a single inbound file (--max-inbound-size); the same shared
# default the client uses. 0 = disabled.
DEFAULT_MAX_INBOUND_SIZE = defaults.MAX_INBOUND_SIZE_MB_DEFAULT  # MB
DEFAULT_IGNORE_PATTERNS = ""

# Accepted ranges shared with the CLI (``hsync_common.defaults``): the spin boxes
# and the emitted flags clamp to them, so the GUI never emits a value the CLI
# rejects. GUI_MAX_WAIT_MIN and GUI_RETRY_DELAY_MIN are intentionally taller than
# the CLI minimum: a stale or hand-edited settings file must not park a transfer
# slot (max wait) or hammer a peer (retry delay) below a useful granularity.
RETRY_DELAY_MIN = defaults.RECONNECT_DELAY_MIN
RETRY_DELAY_MAX = defaults.RECONNECT_DELAY_MAX
STABILITY_DELAY_MAX = defaults.STABILITY_DELAY_MAX
MAX_WAIT_MIN = defaults.MAX_WAIT_TIMEOUT_MIN
MAX_WAIT_MAX = defaults.MAX_WAIT_TIMEOUT_MAX
RESYNC_MAX = defaults.RESYNC_MAX
# Free-space reserve: the GUI edits whole MB (spin box) while the shared SSOT is
# bytes and the emitted CLI flag is a size string ("500MB", see cli_args.py).
MIN_FREE_DISK_SPACE_MB_MIN = defaults.MIN_FREE_DISK_SPACE_MIN // BYTES_PER_MB
MIN_FREE_DISK_SPACE_MB_MAX = defaults.MIN_FREE_DISK_SPACE_MAX // BYTES_PER_MB
MAX_INBOUND_SIZE_MB_MIN = defaults.MAX_INBOUND_SIZE_MB_MIN
MAX_INBOUND_SIZE_MB_MAX = defaults.MAX_INBOUND_SIZE_MB_MAX
GUI_MAX_WAIT_MIN = 60
GUI_RETRY_DELAY_MIN = 5

# Advanced tab — engine tuning values from the shared defaults
# (``hsync_common.defaults``). Values matching the client default are omitted
# from the CLI so the engine keeps its own default/auto behaviour.
DEFAULT_MASS_DELETE_GUARD = defaults.MASS_DELETE_GUARD_DEFAULT
DEFAULT_MASS_DELETE_THRESHOLD = defaults.MASS_DELETE_THRESHOLD_DEFAULT  # deletions per cycle
DEFAULT_MASS_DELETE_PERCENT = defaults.MASS_DELETE_PERCENT_DEFAULT  # percent of local files
DEFAULT_AUTOTUNE = True
DEFAULT_MAX_CONCURRENT_TRANSFERS = 0  # 0 = omit (client default, autotuned)
DEFAULT_DELTA_ENABLED = True
# The client's delta floors are byte constants; the dialog works in KB.
DEFAULT_DELTA_MIN_FILE_SIZE_KB = DELTA_MIN_FILE_SIZE // 1024
DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB = DELTA_MIN_FILE_SIZE_P2P // 1024

# p2p defaults
# p2p is the default mode on a fresh install (no stored p2p/enabled yet).
DEFAULT_P2P_ENABLED = True
DEFAULT_P2P_KEY = ""
DEFAULT_P2P_PORT = 0  # 0 = auto-assign
DEFAULT_RENDEZVOUS_TIMEOUT = 10
DEFAULT_PREFER_MASTER = False
DEFAULT_NEVER_MASTER = False
# P2P master trust policy (ADR-0040): ask (default) | accept-new | strict.
# Passed to hsync-client via --p2p-trust; chain/none never pin, so they are not
# selectable here.
DEFAULT_P2P_TRUST = "ask"
# Optional rendezvous host for cross-network rendezvous (bare hostname; empty =
# mDNS-only). Passed to hsync-client via HSYNC_RENDEZVOUS_SERVER_ENDPOINTS.
DEFAULT_P2P_RENDEZVOUS = ""
# Rendezvous TLS trust policy (ADR-0035): ask | accept-new | strict | none.
# Passed via HSYNC_RENDEZVOUS_TRUST.
DEFAULT_P2P_RENDEZVOUS_TRUST = "ask"
# Map the master TCP port with UPnP when a rendezvous is used. Passed via
# HSYNC_MAP_DATA_PORT; the client treats it as on only with a rendezvous server by
# default.
DEFAULT_P2P_UPNP_ENABLED = True
# Comma-separated SNTP servers (ADR-0023) passed to hsync-client via the
# HSYNC_NTP_HOSTS environment variable. Empty = client defaults
# (pool.ntp.org, time.cloudflare.com, time.google.com); entries may carry a
# port override (host:port).
DEFAULT_NTP_HOSTS = ""
# Download file blocks from other peers in p2p mode (--no-peer-download when
# off); the read/source caps are env-only (HSYNC_P2P_PEER_READ_CAP,
# HSYNC_P2P_PEER_SOURCES_MAX).
DEFAULT_P2P_PEER_DOWNLOAD = defaults.P2P_PEER_DOWNLOAD_DEFAULT
DEFAULT_P2P_PEER_READ_CAP = defaults.P2P_PEER_READ_CAP_DEFAULT
DEFAULT_P2P_PEER_SOURCES_MAX = defaults.P2P_PEER_SOURCES_MAX_DEFAULT

# Bandwidth limits: the client enforces the same [min, max] bounds on
# --limit-upload/--limit-download (``hsync_common.defaults``), so the GUI caps
# its fields and clamps stored values to the same range.
BANDWIDTH_MIN_BPS = defaults.BANDWIDTH_MIN_BPS
BANDWIDTH_MAX_BPS = defaults.BANDWIDTH_MAX_BPS
BANDWIDTH_MAX_MBPS = BANDWIDTH_MAX_BPS / (1024 * 1024)

# Output defaults
DEFAULT_VERBOSE = False
DEFAULT_QUIET = False
DEFAULT_LOGFILE = ""
DEFAULT_SHOW_LOG_PANEL = False

# Appearance defaults
DEFAULT_NOTIFICATIONS = True
# Per-event notification categories (all enabled by default).
NOTIFICATION_CATEGORIES = ("errors", "warnings", "connection", "sync", "peers")
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

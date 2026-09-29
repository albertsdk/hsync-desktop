# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

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
DEFAULT_RETRY_DELAY = 5
DEFAULT_STABILITY_DELAY = 5
DEFAULT_MAX_WAIT = 120
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

# p2p defaults
DEFAULT_P2P_ENABLED = False
DEFAULT_P2P_KEY = ""
DEFAULT_P2P_PORT = 0  # 0 = auto-assign
DEFAULT_DISCOVERY_TIMEOUT = 10
DEFAULT_FORCE_MASTER = False
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

# Output defaults
DEFAULT_VERBOSE = False
DEFAULT_QUIET = False
DEFAULT_LOGFILE = ""
DEFAULT_SHOW_LOG_PANEL = False

# Appearance defaults
DEFAULT_NOTIFICATIONS = True
DEFAULT_TOOLTIPS = True

# File panel
FILE_BATCH_SIZE = 50
CONSISTENCY_CHECK_INTERVAL_MS = 5000

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

# Application info
APP_NAME = "HSYNC Desktop"
APP_ORG = "HSYNC"
APP_ID = "HSYNCDesktop"

# QSettings organization and application name
# These are used by QSettings to store application settings
SETTINGS_ORG = "HSYNC"
SETTINGS_APP = "HSYNCDesktop"

# Default sync settings
DEFAULT_BUCKET = "my-bucket"
DEFAULT_GROUP = "my-group"

# Connection defaults
DEFAULT_SERVER_URL = ""
DEFAULT_INSECURE = False
DEFAULT_CA_CERT = ""
DEFAULT_SERVER_CERT_FINGERPRINT = ""
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
DEFAULT_NO_COMPRESSION = False  # Legacy: keep for backward compatibility
DEFAULT_COMPRESSION_ENABLED = True
DEFAULT_DRY_RUN = False
DEFAULT_AUTO_SYNC = False
DEFAULT_MIN_FREE_DISK_SPACE = 500  # MB
DEFAULT_SYNC_HIDDEN = False
DEFAULT_IGNORE_PATTERNS = ""

# LAN defaults
DEFAULT_LAN_ENABLED = False
DEFAULT_LAN_KEY = ""
DEFAULT_LAN_PORT = 0  # 0 = auto-assign
DEFAULT_DISCOVERY_TIMEOUT = 10
DEFAULT_LAN_HTTPS = True
DEFAULT_LAN_PERSISTENT = True
DEFAULT_FORCE_MASTER = False
DEFAULT_NEVER_MASTER = False
DEFAULT_LAN_REQUIRE_PAIRING = False

# Output defaults
DEFAULT_VERBOSE = False
DEFAULT_QUIET = False
DEFAULT_LOGFILE = ""
DEFAULT_SHOW_LOG_PANEL = False

# Appearance defaults
DEFAULT_THEME = "system"  # "light", "dark", or "system"
DEFAULT_NOTIFICATIONS = True
DEFAULT_TOOLTIPS = True
DEFAULT_LANGUAGE = "en"

# File panel
FILE_BATCH_SIZE = 50
CONSISTENCY_CHECK_INTERVAL_MS = 5000
DELETED_FILE_DISPLAY_MS = 3000

# UI constants
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
SPLASH_DURATION_MS = 3000

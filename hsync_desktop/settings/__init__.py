# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Settings module for HSYNC Desktop.

Provides settings dialog, validators, and CLI argument builder.
"""

from hsync_desktop.settings.cli_args import (
    SETTINGS_APP,
    SETTINGS_ORG,
    are_notifications_enabled,
    build_hsync_args,
    get_bandwidth_limits,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
    save_bandwidth_limits,
    secure_config_file,
)
from hsync_desktop.settings.dialog import ApiKeyDialog, P2PKeyDialog, SettingsDialog

__all__ = [
    "ApiKeyDialog",
    "P2PKeyDialog",
    "SettingsDialog",
    "SETTINGS_ORG",
    "SETTINGS_APP",
    "are_notifications_enabled",
    "build_hsync_args",
    "get_bandwidth_limits",
    "get_saved_theme",
    "is_auto_sync_enabled",
    "is_log_panel_visible",
    "save_bandwidth_limits",
    "secure_config_file",
]

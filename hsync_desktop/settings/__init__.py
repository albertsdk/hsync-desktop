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
    are_notifications_enabled,
    build_hsync_args,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
)
from hsync_desktop.settings.dialog import ApiKeyDialog, LanKeyDialog, SettingsDialog

__all__ = [
    "ApiKeyDialog",
    "LanKeyDialog",
    "SettingsDialog",
    "are_notifications_enabled",
    "build_hsync_args",
    "get_saved_theme",
    "is_auto_sync_enabled",
    "is_log_panel_visible",
]

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Settings dialog for HSYNC Desktop.

This module is now a compatibility wrapper. The actual implementation
has been moved to hsync_desktop.settings package.
"""

from hsync_desktop.settings.cli_args import (
    SETTINGS_APP,
    SETTINGS_ORG,
    are_notifications_enabled,
    build_hsync_args,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
)
from hsync_desktop.settings.dialog import (
    ApiKeyDialog,
    LanKeyDialog,
    SettingsDialog,
)

__all__ = [
    "ApiKeyDialog",
    "LanKeyDialog",
    "SettingsDialog",
    "SETTINGS_ORG",
    "SETTINGS_APP",
    "are_notifications_enabled",
    "build_hsync_args",
    "get_saved_theme",
    "is_auto_sync_enabled",
    "is_log_panel_visible",
]

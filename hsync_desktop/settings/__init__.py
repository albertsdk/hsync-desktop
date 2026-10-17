# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Settings module for HSYNC Desktop.

Provides settings dialog, validators, and CLI argument builder.
"""

from hsync_desktop.settings.cli_args import (
    SETTINGS_APP,
    SETTINGS_ORG,
    are_notifications_enabled,
    build_hsync_args,
    build_selection_args,
    get_bandwidth_limits,
    get_saved_theme,
    get_theme_setting,
    is_auto_sync_enabled,
    is_log_panel_visible,
    save_bandwidth_limits,
    secure_config_file,
)
from hsync_desktop.settings.credential_dialogs import ApiKeyDialog, P2PKeyDialog
from hsync_desktop.settings.dialog import SettingsDialog

__all__ = [
    "SETTINGS_APP",
    "SETTINGS_ORG",
    "ApiKeyDialog",
    "P2PKeyDialog",
    "SettingsDialog",
    "are_notifications_enabled",
    "build_hsync_args",
    "build_selection_args",
    "get_bandwidth_limits",
    "get_saved_theme",
    "get_theme_setting",
    "is_auto_sync_enabled",
    "is_log_panel_visible",
    "save_bandwidth_limits",
    "secure_config_file",
]

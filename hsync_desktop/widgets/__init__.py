# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Custom Qt widgets for hsync-desktop."""

from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.name_dialog import ask_name
from hsync_desktop.widgets.toggle_switch import ToggleSwitch

__all__ = ["ToggleSwitch", "ask_name", "muted_label"]

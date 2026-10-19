# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Wizard pages package."""

from __future__ import annotations

from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.pages.connection import ConnectionPage
from hsync_desktop.wizard.pages.folder import FolderPage
from hsync_desktop.wizard.pages.mode import ModePage
from hsync_desktop.wizard.pages.review import ReviewPage
from hsync_desktop.wizard.pages.success import SuccessPage

__all__ = [
    "ConnectionPage",
    "FolderPage",
    "ModePage",
    "ReviewPage",
    "SuccessPage",
    "WizardPage",
]

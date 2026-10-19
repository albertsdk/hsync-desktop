# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Setup wizard package (desktop-only guided configuration)."""

from __future__ import annotations

from hsync_desktop.wizard.dialog import SetupWizard
from hsync_desktop.wizard.model import WizardDraft, WizardMode, WizardProfile

__all__ = ["SetupWizard", "WizardDraft", "WizardMode", "WizardProfile"]

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Brand assets shared by the welcome splash and the About window.

Consumers: ``hsync_desktop/splash_screen.py`` and ``hsync_desktop/about_dialog.py``
"""

from __future__ import annotations

from pathlib import Path

# Horizontal wordmark shared with the README top banner (bundled, unthemed).
LOGO_PATH = Path(__file__).parent / "resources" / "icons" / "hsync-logo-horizontal.svg"
LOGO_WIDTH = 240

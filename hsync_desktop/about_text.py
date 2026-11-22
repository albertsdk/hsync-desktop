# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Version line shared by the welcome splash and the About window.

Consumers: ``hsync_desktop/splash_screen.py`` and ``hsync_desktop/about_dialog.py``
"""

from __future__ import annotations

from hsync_desktop.i18n import tr


def version_text(version: str, engine: str) -> str:
    """Render the app and engine versions on one line (``about.version``)."""
    return tr("about.version").replace("{version}", version).replace("{engine}", engine)

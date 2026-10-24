# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Defensive readers for the desktop-friendly INI files used for theming.

Both the theme detection (``themes.py``) and the font detection (``fonts.py``)
read KDE/GTK configuration files. The parsing policy is identical — no
interpolation (values are raw, e.g. ``'BreezeDark'``), and any missing or
malformed file yields ``None`` instead of raising — so it lives here once.

Consumers: ``hsync-desktop`` (``themes.py``, ``fonts.py``), tests.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

__all__ = ["config_home", "read_ini"]


def config_home() -> Path:
    """Return the XDG config directory (``$XDG_CONFIG_HOME`` or ``~/.config``)."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))


def read_ini(path: Path) -> configparser.ConfigParser | None:
    """Parse *path* as an INI file, or return ``None``.

    ``interpolation=None`` keeps values verbatim (a ``%`` in a theme name is not
    a format directive), and any unreadable/malformed file is treated as absent
    so a partially-written config never breaks startup.
    """
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    return parser

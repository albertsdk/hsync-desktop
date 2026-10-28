# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Guard for the launcher assets declared in ``snap/snapcraft.yaml``.

Snapcraft resolves ``apps.<app>.desktop`` inside the project's ``snap/``
directory, so a value that repeats the ``snap/`` prefix points at
``snap/snap/gui/...`` and priming aborts with "Failed to generate desktop
file". The top-level ``icon`` is resolved from the project root instead, as is
the dump part's ``source``.

Consumers: hsync-desktop maintainers (drift guard for the snap release build).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "snap"
MANIFEST = SNAP_DIR / "snapcraft.yaml"


def _scalar(key: str) -> str:
    """Return the single ``key: value`` scalar declared in the manifest."""
    values = re.findall(
        rf"^[ \t]*{key}:[ \t]*(\S+)[ \t]*$",
        MANIFEST.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert len(values) == 1, f"expected one {key!r} entry, found {values}"
    return values[0]


def test_desktop_file_is_declared_inside_the_snap_directory():
    desktop = _scalar("desktop")
    assert not desktop.startswith("snap/"), (
        f"snapcraft resolves desktop: inside snap/, so {desktop!r} points at snap/{desktop}"
    )
    assert (SNAP_DIR / desktop).is_file()


def test_desktop_entry_is_launchable():
    text = (SNAP_DIR / _scalar("desktop")).read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]\n")
    assert "Type=Application" in text
    # Snapcraft rewrites both keys to the snap's own command and icon file.
    assert "\nExec=" in text
    assert "\nIcon=" in text


def test_icon_is_declared_from_the_project_root():
    icon = _scalar("icon")
    assert Path(icon).suffix in {".png", ".svg"}
    assert (ROOT / icon).is_file()


def test_payload_staging_directory_ships_with_the_manifest():
    source = _scalar("source")
    assert (ROOT / source / ".gitkeep").is_file()
    assert _scalar("command").startswith("bin/")

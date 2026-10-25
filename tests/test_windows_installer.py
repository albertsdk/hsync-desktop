# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Guard for the Windows platform floor promised by the docs and the installer.

The frozen bundle runs on the PySide6/Qt wheel, which supports Windows 10 1809
(build 17763) or later and Windows 11 on x86_64 only; no Arm64 artifact is
published. The Windows installer must refuse everything below that floor, and
the user docs must state the same floor, so the promise and the enforced check
cannot drift apart.

Consumers: hsync-desktop maintainers (drift guard).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "packaging" / "windows" / "hsync-desktop.iss"
WINDOWS_GUIDE = ROOT / "docs" / "getting-started-windows.md"
GETTING_STARTED = ROOT / "docs" / "getting-started.md"
BINARY_GUIDE = ROOT / "docs" / "getting-started-binary.md"
SOURCE_GUIDE = ROOT / "docs" / "getting-started-source.md"

# Windows 10 version 1809, the oldest release Qt 6.x supports.
MIN_WINDOWS_VERSION = "10.0.17763"


def _setup_value(name: str) -> str:
    """Return the raw value of a ``[Setup]`` directive in the Inno Setup script."""
    match = re.search(rf"^{name}=(.+)$", ISS.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None, f"{name} is missing from {ISS}"
    return match.group(1).strip()


def test_installer_refuses_windows_below_the_qt_floor():
    assert _setup_value("MinVersion") == MIN_WINDOWS_VERSION


def test_installer_refuses_arm64():
    architectures = _setup_value("ArchitecturesAllowed")
    assert "x64compatible" in architectures
    assert "not arm64" in architectures


@pytest.mark.parametrize(
    "doc",
    [WINDOWS_GUIDE, GETTING_STARTED, BINARY_GUIDE, SOURCE_GUIDE],
    ids=["windows-installer", "getting-started", "standalone-binary", "from-source"],
)
def test_user_docs_state_the_supported_windows_versions(doc):
    text = doc.read_text(encoding="utf-8")
    assert "1809" in text
    assert "Windows 11" in text


@pytest.mark.parametrize(
    "doc",
    [WINDOWS_GUIDE, GETTING_STARTED, SOURCE_GUIDE],
    ids=["windows-installer", "getting-started", "from-source"],
)
def test_user_docs_state_that_only_x64_is_published(doc):
    assert "x64" in doc.read_text(encoding="utf-8")

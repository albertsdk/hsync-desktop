# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Guard for the macOS platform floor and bundle name promised by the docs.

The .app embeds the locked PySide6/Qt wheels, whose ``macosx_X_Y`` tag is the
dyld load floor. ``LSMinimumSystemVersion`` (from ``compile.sh``) and the user
guide must not promise an older macOS than that, and the guide's Gatekeeper
commands must name the bundle the build really produces.

Consumers: hsync-desktop maintainers (drift guard).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILE_SH = ROOT / "compile.sh"
LOCK = ROOT / "poetry.lock"
MACOS_GUIDE = ROOT / "docs" / "getting-started-macos.md"


def _compile_var(name: str) -> str:
    match = re.search(rf'^readonly {name}="([^"]+)"$', COMPILE_SH.read_text(), re.MULTILINE)
    assert match is not None, f"{name} is missing from compile.sh"
    return match.group(1)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _pyside_macos_floor() -> str:
    tags = re.findall(r"pyside6[a-z_]*-[\d.]+-cp\d+-abi3-macosx_(\d+)_(\d+)_", LOCK.read_text())
    assert tags, "no PySide6 macOS wheel in poetry.lock"
    return max((f"{major}.{minor}" for major, minor in tags), key=_version_key)


def test_declared_minimum_is_not_below_the_qt_wheel_floor():
    assert _version_key(_compile_var("MACOS_MIN_VERSION")) >= _version_key(_pyside_macos_floor())


def test_guide_states_the_declared_minimum():
    major = _compile_var("MACOS_MIN_VERSION").split(".")[0]
    assert f"macOS {major} " in MACOS_GUIDE.read_text(encoding="utf-8")


def test_guide_names_the_built_bundle():
    bundle = f"{_compile_var('APP_NAME')}.app"
    text = MACOS_GUIDE.read_text(encoding="utf-8")
    assert f"/Applications/{bundle}" in text
    assert "HSYNC.app" not in text

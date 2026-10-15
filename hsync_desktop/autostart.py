# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Launch-at-login integration for the GUI.

Registers HSYNC Desktop with the OS per-user autostart mechanism so it starts
(minimized to the tray) when the user logs in:

* Linux/BSD — a freedesktop XDG autostart entry under ``~/.config/autostart``.
* macOS — a LaunchAgent plist under ``~/Library/LaunchAgents``.
* Windows — the per-user ``Run`` registry value.

The generated entry always launches ``hsync-desktop --minimized`` so the app
stays in the tray; a later manual launch is handled by the running instance's
single-instance activation. Consumed by ``settings/dialog.py`` (the Appearance
toggle); nothing else imports it.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from hsync_desktop.config import MINIMIZED_FLAG

_APP_NAME = "hsync-desktop"
# Reverse-DNS label for the macOS LaunchAgent; matches the bundle id used by
# packaging/macos/Info.plist.
_MACOS_LABEL = "io.hsync.desktop"
_WINDOWS_RUN_VALUE = "HSYNC Desktop"
_WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Reserved characters that force double-quoting in an XDG Exec field.
_EXEC_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")


def _platform() -> str:
    """The current platform string (a seam for tests)."""
    return sys.platform


def _home_dir() -> Path:
    """The current user's home directory (a seam for tests)."""
    return Path.home()


def is_supported() -> bool:
    """Whether this platform has an autostart mechanism the GUI can manage."""
    plat = _platform()
    return plat.startswith("linux") or plat == "darwin" or plat == "win32"


def is_enabled() -> bool:
    """Whether the app is currently registered to start at login."""
    plat = _platform()
    if plat.startswith("linux"):
        return _linux_entry_path().is_file()
    if plat == "darwin":
        return _macos_plist_path().is_file()
    if plat == "win32":
        return _windows_has_entry()
    return False


def set_enabled(enabled: bool) -> None:
    """Register or unregister the login item.

    Raises ``OSError`` when the OS rejects the change (e.g. a permission
    problem); the caller surfaces the failure to the user.
    """
    plat = _platform()
    if plat.startswith("linux"):
        _linux_write() if enabled else _linux_remove()
    elif plat == "darwin":
        _macos_write() if enabled else _macos_remove()
    elif plat == "win32":
        _windows_write() if enabled else _windows_remove()


def _launch_command() -> list[str]:
    """The command that starts the GUI minimized, for the autostart entry.

    Resolves the running app: an AppImage via ``$APPIMAGE``, a frozen bundle
    via ``sys.executable``, the installed ``hsync-desktop`` launcher on ``PATH``,
    and finally the module form for a source run.
    """
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return [appimage, MINIMIZED_FLAG]
    if getattr(sys, "frozen", False):
        return [sys.executable, MINIMIZED_FLAG]
    installed = shutil.which(_APP_NAME)
    if installed:
        return [installed, MINIMIZED_FLAG]
    return [sys.executable, "-m", "hsync_desktop", MINIMIZED_FLAG]


def _autostart_command() -> list[str]:
    """The launch command, validated for a login-time autostart entry.

    The entry runs at login with the user's privileges, so the program must be
    an absolute path and must not carry control characters: a newline would
    break the line-oriented `.desktop`/registry formats and could inject extra
    keys. Raises ``OSError`` so the caller surfaces the failure.
    """
    command = _launch_command()
    program = command[0]
    if not os.path.isabs(program) or any(ord(char) < 0x20 for char in program):
        raise OSError(f"unsafe autostart command: {program!r}")
    return command


# ── Linux / freedesktop ──────────────────────────────────────────────────────


def _linux_entry_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    # The XDG spec ignores a non-absolute XDG_CONFIG_HOME (GLib/Qt do too);
    # accepting a relative value would write the entry under the process CWD.
    config_home = Path(base) if base and os.path.isabs(base) else _home_dir() / ".config"
    return config_home / "autostart" / f"{_APP_NAME}.desktop"


def _exec_field_quote(arg: str) -> str:
    """Quote one argument for a Desktop Entry ``Exec`` field."""
    # Drop line breaks: the format is line-oriented, so an embedded newline
    # would terminate the value and could inject further keys.
    arg = arg.replace("\n", "").replace("\r", "")
    if arg and not any(char in _EXEC_RESERVED for char in arg):
        return arg
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("`", "\\`").replace("$", "\\$")
    return f'"{escaped}"'


def _linux_write() -> None:
    path = _linux_entry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(_exec_field_quote(arg) for arg in _autostart_command())
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=HSYNC\n"
        "Comment=Sync your folders across devices\n"
        f"Exec={exec_line}\n"
        f"Icon={_APP_NAME}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )


def _linux_remove() -> None:
    try:
        _linux_entry_path().unlink()
    except FileNotFoundError:
        pass


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_plist_path() -> Path:
    return _home_dir() / "Library" / "LaunchAgents" / f"{_MACOS_LABEL}.plist"


def _macos_write() -> None:
    import plistlib

    payload = {
        "Label": _MACOS_LABEL,
        "ProgramArguments": _autostart_command(),
        "RunAtLoad": True,
    }
    path = _macos_plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def _macos_remove() -> None:
    try:
        _macos_plist_path().unlink()
    except FileNotFoundError:
        pass


# ── Windows ──────────────────────────────────────────────────────────────────


def _winreg() -> Any:
    """Import ``winreg`` lazily (Windows-only) without a platform stub."""
    return importlib.import_module("winreg")


def _windows_has_entry() -> bool:
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY) as key:
            winreg.QueryValueEx(key, _WINDOWS_RUN_VALUE)
            return True
    except FileNotFoundError:
        return False


def _windows_write() -> None:
    winreg = _winreg()
    command = subprocess.list2cmdline(_autostart_command())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY) as key:
        winreg.SetValueEx(key, _WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, command)


def _windows_remove() -> None:
    winreg = _winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _WINDOWS_RUN_VALUE)
    except FileNotFoundError:
        pass

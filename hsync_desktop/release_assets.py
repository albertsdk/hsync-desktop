# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Which release artifact belongs to the running installation.

The update dialog offers a single **Download** button, and where it lands decides
whether the operator can actually get their package: the releases *index* page
renders only the first ten assets behind a ``Show all N assets`` toggle, so a
``.deb``/``.rpm``/``.snap`` (they sort past the archives) looks missing, while
the release's **tag** page lists every asset and a ``download/vX.Y.Z/<asset>``
URL serves one file directly.

This module answers "which of those files is mine?" from what the process can
observe about its own packaging — the snap and AppImage markers, the platform,
and the Linux distribution family — and names the **fixed-name alias** every
release publishes for that format (``RELEASES.md`` §5.8): the alias stays stable
while the version is pinned in the URL path. A channel it cannot resolve (a snap,
which refreshes itself; an architecture with no build; an unknown distribution)
falls back to the tag page, which carries the complete list.

Consumers: ``main_window/actions.py::ActionsMixin._offer_update``.
"""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Mapping
from pathlib import Path

from hsync_desktop.docs_links import release_download_url, release_tag_url

__all__ = [
    "APPIMAGE_ENV",
    "OS_RELEASE_PATH",
    "SNAP_ENV",
    "install_channel",
    "package_asset",
    "package_url",
]

#: Set by snapd inside a snap (``/snap/hsync-desktop/<rev>``).
SNAP_ENV = "SNAP"
#: Set by the AppImage runtime to the image being executed.
APPIMAGE_ENV = "APPIMAGE"
#: Linux distribution identity; a module constant so tests can point elsewhere.
OS_RELEASE_PATH = Path("/etc/os-release")

# Distribution families whose system package manager owns the artifact, matched
# against ``ID`` and ``ID_LIKE`` of ``/etc/os-release``. ``ID_LIKE`` is what
# carries a derivative (``linuxmint`` → ``ubuntu``, ``rocky`` → ``rhel``).
_DEB_FAMILIES = frozenset(
    {"debian", "ubuntu", "linuxmint", "pop", "raspbian", "elementary", "zorin", "kali", "deepin"}
)
_RPM_FAMILIES = frozenset(
    {
        "fedora",
        "rhel",
        "centos",
        "rocky",
        "almalinux",
        "ol",
        "oracle",
        "amzn",
        "opensuse",
        "opensuse-leap",
        "opensuse-tumbleweed",
        "sles",
    }
)

# Fixed-name aliases every release publishes (RELEASES.md §5.8), per channel and
# architecture key. A missing pair means the project ships no build for it: the
# AppImage exists for x86_64 only, the Windows installer for x64 only.
_ASSETS: dict[str, dict[str, str]] = {
    "deb": {"amd64": "hsync-desktop-amd64.deb", "arm64": "hsync-desktop-arm64.deb"},
    "rpm": {"x86_64": "hsync-desktop-x86_64.rpm", "aarch64": "hsync-desktop-aarch64.rpm"},
    "appimage": {"x86_64": "hsync-desktop-x86_64.AppImage"},
    "windows": {"amd64": "hsync-desktop-windows-amd64-setup.exe"},
    "macos": {
        "arm64": "hsync-desktop-darwin-arm64.dmg",
        "amd64": "hsync-desktop-darwin-amd64.dmg",
    },
}

# ``platform.machine()`` → the architecture key each channel names it with: the
# Debian and macOS artifacts use ``amd64``/``arm64``, the RPM and AppImage ones
# ``x86_64``/``aarch64``.
_ARCH_KEYS: dict[str, dict[str, str]] = {
    "deb": {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"},
    "rpm": {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"},
    "appimage": {"x86_64": "x86_64", "amd64": "x86_64"},
    "windows": {"x86_64": "amd64", "amd64": "amd64"},
    "macos": {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "amd64": "amd64"},
}


def install_channel(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the packaging channel this process runs from.

    ``platform_name``/``environ`` default to the real probes (``sys.platform``
    and ``os.environ``); tests pass them explicitly. The runtime markers are
    checked first: a snap on Ubuntu is a snap before it is a ``.deb`` host, and an
    AppImage runs on a distribution whose package manager is not its upgrade path.
    """
    env = os.environ if environ is None else environ
    name = sys.platform if platform_name is None else platform_name
    if env.get(SNAP_ENV):
        return "snap"
    if env.get(APPIMAGE_ENV):
        return "appimage"
    if name == "win32":
        return "windows"
    if name == "darwin":
        return "macos"
    return _linux_channel() or "unknown"


def package_asset(channel: str, machine: str) -> str | None:
    """The fixed-name alias *channel* publishes for *machine*, or ``None``.

    ``None`` is every case one file cannot serve: a snap (it refreshes itself,
    and the tag page carries the offline ``.snap``), an architecture without a
    build (an arm64 AppImage), an unknown channel or machine.
    """
    key = _ARCH_KEYS.get(channel, {}).get(machine.lower())
    if key is None:
        return None
    return _ASSETS.get(channel, {}).get(key)


def package_url(
    version: str,
    *,
    channel: str | None = None,
    machine: str | None = None,
) -> str:
    """Return the URL the update dialog should open for *version*.

    The running installation's own artifact when it can be named, the release's
    tag page otherwise (the releases index only when the version itself is
    unusable) — never the index's truncated asset list by default.
    """
    resolved_channel = install_channel() if channel is None else channel
    resolved_machine = platform.machine() if machine is None else machine
    asset = package_asset(resolved_channel, resolved_machine)
    if asset is None:
        return release_tag_url(version)
    return release_download_url(version, asset)


def _linux_channel() -> str | None:
    """Return ``deb``/``rpm`` for the host distribution family, or ``None``."""
    fields = _os_release_fields()
    candidates = [fields.get("ID", ""), *fields.get("ID_LIKE", "").split()]
    for candidate in candidates:
        family = candidate.strip().lower()
        if family in _DEB_FAMILIES:
            return "deb"
        if family in _RPM_FAMILIES:
            return "rpm"
    return None


def _os_release_fields() -> dict[str, str]:
    """Parse ``/etc/os-release`` into a mapping; empty when it is unreadable.

    The first assignment of a key wins and quotes are stripped, so the probe
    never raises on a missing or unusual file (the caller then reports an unknown
    channel instead of guessing one).
    """
    try:
        text = OS_RELEASE_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key.strip() or key.strip() in fields:
            continue
        fields[key.strip()] = value.strip().strip("\"'")
    return fields
